# fastapi_app_with_encryption.py

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import cx_Oracle
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uvicorn
import traceback
from cryptography.fernet import Fernet
#import base64
#import os

# مفتاح التشفير الحقيقي (خزنه بأمان)
FERNET_KEY = b"xSXYpH5fP8l8qX_2jIxkYdwaC9Z9aH10IYhHyMez_Y4="
cipher = Fernet(FERNET_KEY)

def encrypt_data(data: str) -> str:
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(data: str) -> str:
    return cipher.decrypt(data.encode()).decode()

def encrypt_file_bytes(data: bytes) -> str:
    return cipher.encrypt(data).decode()

def decrypt_file_bytes(data: str) -> bytes:
    return cipher.decrypt(data.encode())

# إعدادات الاتصال بقاعدة البيانات
ORACLE_DSN = cx_Oracle.makedsn("localhost", 1521, service_name="Wallet_chat")
ORACLE_USER = "Wallet_chat"
ORACLE_PASSWORD = "Wallet_2025"

def get_connection():
    try:
        return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
    except cx_Oracle.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to Oracle: {e}")

# نماذج البيانات
class User(BaseModel):
    username: str
    password: str
    role: str
    active: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

class Message(BaseModel):
    sender: str
    receiver: str
    text: str
    timestamp: Optional[datetime] = None

class ImageMessage(BaseModel):
    sender: str
    receiver: str
    image_base64: str

# تهيئة قاعدة البيانات
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 بدء تهيئة قاعدة البيانات...")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE TABLE users (
                    id NUMBER PRIMARY KEY,
                    username VARCHAR2(100) UNIQUE,
                    password VARCHAR2(500),
                    role VARCHAR2(20),
                    active NUMBER(1) DEFAULT 1
                )';
            EXCEPTION WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE SEQUENCE users_seq START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE';
            EXCEPTION WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE '
                    CREATE OR REPLACE TRIGGER trg_users_id
                    BEFORE INSERT ON users
                    FOR EACH ROW
                    WHEN (new.id IS NULL)
                    BEGIN
                        SELECT users_seq.NEXTVAL INTO :new.id FROM dual;
                    END;
                ';
            EXCEPTION WHEN OTHERS THEN
                IF SQLCODE != -4080 THEN RAISE; END IF;
            END;
        """)

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE SEQUENCE messages_seq START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE';
            EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE TABLE messages (
                    id NUMBER PRIMARY KEY,
                    sender VARCHAR2(100),
                    receiver VARCHAR2(100),
                    text CLOB,
                    timestamp TIMESTAMP
                )';
            EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)

        cursor.execute("""
            BEGIN
                EXECUTE IMMEDIATE 'CREATE TABLE last_seen_messages (
                    user_msg VARCHAR2(100),
                    contact VARCHAR2(100),
                    last_seen TIMESTAMP,
                    PRIMARY KEY (user_msg, contact)
                )';
            EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
            END;
        """)

        default_users = [
            ('admin', 'admin123', 'admin'),
            ('moderator', 'mod123', 'moderator'),
            ('user1', 'user123', 'user')
        ]

        for username, password, role in default_users:
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = :username", {'username': username})
            user_exists = cursor.fetchone()[0]
            if user_exists == 0:
                encrypted_password = encrypt_data(password)
                cursor.execute(
                    "INSERT INTO users (username, password, role, active) VALUES (:username, :password, :role, 1)",
                    {'username': username, 'password': encrypted_password, 'role': role}
                )
                conn.commit()
        print("✅ قاعدة البيانات جاهزة.")
    except Exception as e:
        print("❌ فشل التهيئة:")
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    yield
    print("🛑 تم إيقاف التطبيق.")

app = FastAPI(lifespan=lifespan)

@app.post("/login")
def login(login_request: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username, password, role, active FROM users WHERE username=:username", 
                      {'username': login_request.username})
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="المستخدم غير موجود")

        decrypted_password = decrypt_data(user[1])
        if decrypted_password != login_request.password:
            raise HTTPException(status_code=401, detail="كلمة المرور خاطئة")

        return {"username": user[0], "role": user[2], "active": bool(user[3])}
    finally:
        cursor.close()
        conn.close()

@app.put("/change-password")
def change_password(request: ChangePasswordRequest):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT password FROM users WHERE username = :username", {'username': request.username})
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        decrypted_password = decrypt_data(result[0])
        if decrypted_password != request.old_password:
            raise HTTPException(status_code=401, detail="كلمة المرور الحالية غير صحيحة")

        encrypted_new_password = encrypt_data(request.new_password)
        cursor.execute("UPDATE users SET password = :password WHERE username = :username",
                       {'password': encrypted_new_password, 'username': request.username})
        conn.commit()
        return {"message": "تم تغيير كلمة المرور بنجاح"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/users")
def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username, role, active FROM users")
        users = [{"username": row[0], "role": row[1], "active": bool(row[2])} for row in cursor.fetchall()]
        return {"users": users}
    finally:
        cursor.close()
        conn.close()

@app.post("/users")
def create_user(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username=:username", {'username': user.username})
        if cursor.fetchone()[0] > 0:
            raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")

        encrypted_password = encrypt_data(user.password)

        cursor.execute(
            "INSERT INTO users (username, password, role, active) VALUES (:username, :password, :role, :active)",
            {
                'username': user.username,
                'password': encrypted_password,
                'role': user.role,
                'active': 1 if user.active else 0
            }
        )
        conn.commit()
        return {"message": "تم إنشاء المستخدم بنجاح"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.put("/users/{username}")
def update_user(username: str, user: User):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username=:username", {'username': username})
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        encrypted_password = encrypt_data(user.password)

        cursor.execute("""
            UPDATE users 
            SET username=:new_username, 
                password=:password, 
                role=:role, 
                active=:active 
            WHERE username=:old_username
        """, {
            'new_username': user.username,
            'password': encrypted_password,
            'role': user.role,
            'active': 1 if user.active else 0,
            'old_username': username
        })
        conn.commit()
        return {"message": "تم تحديث المستخدم بنجاح"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.delete("/users/{username}")
def delete_user(username: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username=:username", {'username': username})
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        cursor.execute("DELETE FROM users WHERE username=:username", {'username': username})
        conn.commit()
        return {"message": "تم حذف المستخدم بنجاح"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.post("/messages")
def send_message(message: Message):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        encrypted_text = encrypt_data(message.text)
        cursor.execute("""
            INSERT INTO messages (id, sender, receiver, text, timestamp)
            VALUES (messages_seq.NEXTVAL, :sender, :receiver, :text, SYSTIMESTAMP)
        """, {
            'sender': message.sender,
            'receiver': message.receiver,
            'text': encrypted_text
        })
        conn.commit()
        return {"message": "تم إرسال الرسالة"}
    finally:
        cursor.close()
        conn.close()

@app.get("/messages")
def get_messages(sender: str, receiver: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, sender, receiver, text, TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') 
            FROM messages 
            WHERE (sender = :sender AND receiver = :receiver) OR (sender = :receiver AND receiver = :sender)
            ORDER BY timestamp ASC
        """, {'sender': sender, 'receiver': receiver})
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            raw_text = row[3].read() if hasattr(row[3], 'read') else row[3]
            decrypted_text = decrypt_data(raw_text)
            messages.append({
                "id": row[0],
                "sender": row[1],
                "receiver": row[2],
                "text": decrypted_text,
                "timestamp": row[4]
            })
        return {"messages": messages}
    finally:
        cursor.close()
        conn.close()

# @app.post("/images")
# def send_image(message: ImageMessage):
#     conn = get_connection()
#     cursor = conn.cursor()
#     try:
#         raw_bytes = base64.b64decode(message.image_base64)
#         encrypted_data = encrypt_file_bytes(raw_bytes)
#         cursor.execute("""
#             INSERT INTO images (id, sender, receiver, image_data, timestamp)
#             VALUES (messages_seq.NEXTVAL, :sender, :receiver, :image_data, SYSTIMESTAMP)
#         """, {
#             'sender': message.sender,
#             'receiver': message.receiver,
#             'image_data': encrypted_data
#         })
#         conn.commit()
#         return {"message": "تم إرسال الصورة"}
#     finally:
#         cursor.close()
#         conn.close()

# @app.get("/images")
# def get_images(sender: str, receiver: str):
#     conn = get_connection()
#     cursor = conn.cursor()
#     try:
#         cursor.execute("""
#             SELECT id, sender, receiver, image_data, TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') 
#             FROM images 
#             WHERE (sender = :sender AND receiver = :receiver) OR (sender = :receiver AND receiver = :sender)
#             ORDER BY timestamp ASC
#         """, {'sender': sender, 'receiver': receiver})
#         rows = cursor.fetchall()
#         images = []
#         for row in rows:
#             decrypted_bytes = decrypt_file_bytes(row[3])
#             image_base64 = base64.b64encode(decrypted_bytes).decode()
#             images.append({
#                 "id": row[0],
#                 "sender": row[1],
#                 "receiver": row[2],
#                 "image_base64": image_base64,
#                 "timestamp": row[4]
#             })
#         return {"images": images}
#     finally:
#         cursor.close()
#         conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
