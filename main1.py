from flet import *
import uuid
import os
from datetime import *
#import subprocess
import asyncio
#import shutil
from pathlib import Path
#import time
#from cryptography.fernet import Fernet
import base64
#from Cryptodome.Cipher import AES
#from Cryptodome.Util.Padding import pad, unpad
import re
import tempfile
import pandas as pd
import requests
#import json
from typing import List, Dict, Optional
# import certifi
# import ssl
# ssl_context = ssl.create_default_context(cafile=certifi.where())

# ------------------------- إعدادات API -------------------------
API_BASE_URL = "http://localhost:5000"

def api_request(endpoint: str, method: str = "get", data: Optional[Dict] = None) -> Dict:
    """إرسال طلب إلى API"""
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        if method.lower() == "get":
            response = requests.get(url, params=data)
        elif method.lower() == "post":
            response = requests.post(url, json=data)
        elif method.lower() == "put":
            response = requests.put(url, json=data)
        elif method.lower() == "delete":
            response = requests.delete(url, json=data)
        else:
            raise ValueError("Invalid HTTP method")

        # تحقق من وجود أخطاء في الاستجابة
        if response.status_code >= 400:
            error_detail = response.json().get('detail', 'Unknown error')
            raise Exception(f"API error: {error_detail}")
            
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        raise Exception(f"فشل الاتصال بالخادم: {str(e)}")


################################################# إضافة حقل البحث إلى واجهة الدردشة
    

# ------------------------- وظائف مساعدة -------------------------

def seed_users():
    """إضافة مستخدمين افتراضيين إذا لم يكونوا موجودين"""
    users = [
        ('admin', 'admin123', 'admin'),
        ('moderator', 'mod123', 'moderator'),
        ('user1', 'user123', 'user')
    ]
    
    for username, password, role in users:
        try:
            # التحقق من وجود المستخدم
            existing_users = api_request("users").get("users", [])
            if not any(u["username"] == username for u in existing_users):
                # إنشاء المستخدم
                api_request("users", "post", {
                    "username": username,
                    "password": password,
                    "role": role,
                    "active": True
                })
        except Exception as e:
            print(f"Error seeding user {username}: {e}")

def create_images_folder():
    """إنشاء مجلد images إذا لم يكن موجودًا"""
    images_dir = os.path.join(os.getcwd(), "images")
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
        print(f"تم إنشاء مجلد الصور في: {images_dir}")
    return images_dir

# استدعاء الدالة لإنشاء المجلد عند بدء التشغيل
IMAGES_FOLDER = create_images_folder()

# ------------------------- دوال التصدير -------------------------
def export_to_excel(messages, filename="chat_history.xlsx"):
    """تصدير المحادثة إلى ملف Excel"""
    try:
        # تحويل الرسائل إلى DataFrame
        df = pd.DataFrame(messages, columns=["ID", "المرسل", "المستقبل", "النص", "الوقت"])
        
        # إنشاء ملف مؤقت
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        # حفظ الملف
        df.to_excel(filepath, index=False, engine='openpyxl')
        return filepath
    except Exception as e:
        print(f"Error exporting to Excel: {e}")
        return None

# ------------------------- الوظيفة الرئيسية للتطبيق -------------------------
def main(page: Page):
    """الدالة الرئيسية لتطبيق Yemen Wallet"""
    # إعدادات الصفحة الأساسية
    page.title = "Yemen Wallet"
    page.theme_mode = ThemeMode.LIGHT
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"
    page.bgcolor = 'white'
    page.scroll = 'auto'
    page.padding = 10
    page.window_full_screen = False
    page.window_resizable = True
    
    # ضبط أبعاد النافذة حسب الجهاز
    if page.platform in ["android", "ios"]:
        page.window_width = 400
        page.window_height = 800
    else:
        page.window_width = 390
        page.window_height = 740

    # ------------------------- دوال التنقل بين الصفحات -------------------------
    def go_login():
        """عرض صفحة تسجيل الدخول"""
        page.views.clear()
        
        def validate_username(e):
            """التحقق من صحة اسم المستخدم (حروف وأرقام فقط)"""
            username.value = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', username.value)
            username.error_text = None if username.value else "اسم المستخدم يجب أن يحتوي على حروف أو أرقام فقط"
            username.update()
        
        # حقول إدخال البيانات
        username = TextField(
            label="اسم المستخدم",
            icon=Icons.PERSON,
            width=page.width * 0.9,
            rtl=True,
            max_length=20,
            on_change=validate_username
        )
        
        password = TextField(
            label="كلمة المرور", 
            icon=Icons.PASSWORD, 
            password=True, 
            width=page.width*0.9, 
            can_reveal_password=True, 
            rtl=True,
            max_length=12
        )
        
        error = Text("", color="red")

        def login(e):
            """معالجة عملية تسجيل الدخول"""
            try:
                # استخدام endpoint الجديد للتحقق من صحة المستخدم
                user_data = api_request("login", "post", {
                    "username": username.value,
                    "password": password.value
                })
                
                # تخزين بيانات المستخدم في الجلسة
                page.session.set("username", user_data["username"])
                page.session.set("role", user_data["role"])
                
                # توجيه المستخدم حسب صلاحياته
                if user_data["role"] == "admin":
                    go_admin()
                else:
                    go_user_list()
                    
            except Exception as e:
                print("❌ خطأ في تسجيل الدخول:", str(e))
                error.value = str(e)
                page.update()

        # بناء واجهة تسجيل الدخول
        page.views.append(
            View(
                "/",
                [
                    AppBar(
                        title=Text("Yemen Wallet", size=20,color=Colors.WHITE), 
                        bgcolor=Colors.GREEN, 
                        center_title=True
                    ),
                    Container(
                        Column([
                            Container(
                                Image(src="YemenWallet.jpg", 
                                     width=min(page.width*0.5, 170),
                                     height=min(page.width*0.5, 170),
                                     fit=ImageFit.CONTAIN),
                                alignment=alignment.center
                            ),
                            Text("تسجيل الدخول", size=20),
                            username,
                            password,
                            error,
                            Container(
                                ElevatedButton(
                                    "دخول", 
                                    on_click=login, 
                                    width=page.width*0.7, 
                                    height=40,
                                    style=ButtonStyle(
                                        color=Colors.WHITE,
                                        bgcolor=Colors.GREEN
                                    )
                                ),
                                padding=padding.only(top=10)
                            )
                        ], 
                        horizontal_alignment=CrossAxisAlignment.CENTER,
                        spacing=10),
                        padding=10,
                        expand=True
                    )
                ],
                padding=10
            )
        )
        page.update()

    def go_change_password():
        """عرض صفحة تغيير كلمة المرور"""
        page.views.clear()
        current_user = page.session.get("username")

        # حقول إدخال كلمات المرور
        old_pass = TextField(
            label="كلمة المرور الحالية", 
            password=True, 
            can_reveal_password=True, 
            rtl=True,
            max_length=12,
            width=page.width*0.9, 
            icon=Icons.PASSWORD
        )
        
        new_pass = TextField(
            label="كلمة المرور الجديدة", 
            password=True, 
            can_reveal_password=True, 
            rtl=True,
            max_length=12,
            width=page.width*0.9, 
            icon=Icons.PASSWORD
        )
        
        confirm_pass = TextField(
            label="تأكيد كلمة المرور الجديدة", 
            password=True, 
            can_reveal_password=True, 
            rtl=True,
            width=page.width*0.9,
            max_length=12, 
            icon=Icons.PASSWORD
        )
        
        result = Text("", color="red")

        def update_password(e):
            """تحديث كلمة المرور في قاعدة البيانات"""
            try:
                # التحقق من كلمة المرور الحالية أولاً
                api_request("login", "post", {
                    "username": current_user,
                    "password": old_pass.value
                })
                
                if new_pass.value != confirm_pass.value:
                    result.value = "كلمة المرور الجديدة غير متطابقة"
                elif len(new_pass.value) < 4:
                    result.value = "كلمة المرور الجديدة ضعيفة (4 أحرف على الأقل)"
                else:
                    api_request(f"users/{current_user}", "put", {
                        "username": current_user,
                        "password": new_pass.value,
                        "role": page.session.get("role"),
                        "active": True
                    })
                    result.value = "تم تغيير كلمة المرور بنجاح"
                    result.color = "green"
                page.update()
            except Exception as e:
                result.value = str(e)
                page.update()

        # بناء واجهة تغيير كلمة المرور
        page.views.append(
            View(
                "/change_password",
                [
                    AppBar(
                        title=Text("تغيير كلمة المرور", size=18, color=Colors.WHITE),
                        center_title=True, 
                        bgcolor=Colors.GREEN,
                        leading=IconButton(icon=Icons.ARROW_BACK, on_click=lambda e: go_user_list())
                    ),
                    Container(
                        Column([
                            old_pass,
                            new_pass,
                            confirm_pass,
                            result,
                            Container(
                                ElevatedButton(
                                    "تغيير", 
                                    on_click=update_password,
                                    width=page.width*0.9
                                ),
                                padding=padding.only(top=10)
                            ),
                            Container(
                                ElevatedButton(
                                    "رجوع", 
                                    on_click=lambda e: go_user_list(),
                                    width=page.width*0.9
                                ),
                                padding=padding.only(top=10)
                            )
                        ], 
                        horizontal_alignment=CrossAxisAlignment.CENTER,
                        scroll=ScrollMode.AUTO),
                        padding=10,
                        expand=True
                    )
                ]
            )
        )
        page.update()

    def go_user_list():
        """عرض قائمة المستخدمين المتاحين للدردشة"""
        page.views.clear()
        my_user = page.session.get("username")
        role = page.session.get("role")
        users_column = Column(scroll=ScrollMode.AUTO, spacing=5)

        try:
            # جلب المستخدمين حسب صلاحية المستخدم الحالي
            users = api_request("users").get("users", [])
            
            if role in ["admin"]:
                filtered_users = [u for u in users if u["username"] != my_user and u["active"]]
            elif role in ["moderator"]:
                filtered_users = [u for u in users if u["role"] in ["user"] and u["active"] and u["username"] != my_user]
            else:
                filtered_users = [u for u in users if u["role"] in ["moderator"] and u["active"] and u["username"] != my_user]

            # عرض كل مستخدم مع عدد الرسائل غير المقروءة
            for user in filtered_users:
                contact = user["username"]
                
                # جلب عدد الرسائل غير المقروءة
                unread_count = 0
                
                users_column.controls.append(
                    Container(
                        ListTile(
                            title=Row([
                                Text(contact, size=16),
                                Text(f" 🔔 {unread_count} جديدة", color="red", size=14) if unread_count > 0 else Text("")
                            ]),
                            on_click=lambda e, u=contact: go_chat(u),
                            dense=True
                        ),
                        border=border.all(1, Colors.GREY_300),
                        border_radius=5,
                        padding=5
                    )
                )
        except Exception as e:
            page.snack_bar = SnackBar(Text(f"حدث خطأ في جلب قائمة المستخدمين: {str(e)}"))
            page.snack_bar.open = True

        # بناء واجهة قائمة المستخدمين
        page.views.append(
            View(
                "/users",
                [
                    AppBar(
                        title=Text(f"مرحباً {my_user}", size=18, color=Colors.WHITE), 
                        center_title=True,
                        bgcolor=Colors.GREEN,
                        leading=IconButton(
                            icon=Icons.ARROW_BACK, 
                            on_click=lambda e: go_admin() if role=="admin" else go_login()
                        ),
                        actions=[
                            IconButton(
                                icon=Icons.LOGOUT, 
                                on_click=lambda e: go_login(), 
                                tooltip="تسجيل الخروج"
                            )
                        ]
                    ),
                    Container(
                        Column([
                            Container(
                                Text("المستخدمون المتاحون", size=18, weight=FontWeight.BOLD),
                                padding=padding.only(bottom=10)
                            ),
                            Container(
                                users_column,
                                height=page.height*0.6,
                                width=page.width*0.95
                            ),
                            Container(
                                ElevatedButton(
                                    "تغيير كلمة المرور", 
                                    on_click=lambda e: go_change_password(),
                                    width=page.width*0.9
                                ),
                                padding=padding.only(top=10)
                            ),
                            Container(
                                ElevatedButton(
                                    "رجوع", 
                                    on_click=lambda e: go_admin() if role=="admin" else go_login(),
                                    width=page.width*0.9
                                ),
                                padding=padding.only(top=10)
                            ),
                            Container(
                                ElevatedButton(
                                    "تسجيل الخروج", 
                                    on_click=lambda e: go_login(),
                                    width=page.width*0.9,
                                    height=50,
                                    style=ButtonStyle(
                                        bgcolor=Colors.RED_700,
                                        color=Colors.WHITE
                                    )
                                ),
                                padding=padding.only(top=10)
                            )
                        ], 
                        horizontal_alignment=CrossAxisAlignment.CENTER,
                        scroll=ScrollMode.AUTO),
                        padding=10,
                        expand=True,
                        rtl=True
                    )
                ]
            )
        )
        page.update()
    search_field = TextField(
        hint_text="ابحث في الرسائل...",
        width=300,
        on_change=lambda e: find_text_in_messages, # type: ignore
        suffix_icon=Icons.SEARCH,
        height=40
    )
        
    def go_chat(other_user):
        """عرض نافذة الدردشة مع مستخدم معين"""
        page.views.clear()
        my_user = page.session.get("username")
        role = page.session.get("role")

        # عناصر واجهة الدردشة
        messages_column = ListView(
            expand=True,
            spacing=10,
            padding=10,
            auto_scroll=True
        )

        message_input = TextField(
            label="اكتب رسالتك",
            multiline=True,
            min_lines=1,
            max_lines=3,
            expand=True,
            rtl=True,
            prefix=IconButton(
                icon=Icons.IMAGE,
                on_click=lambda e: upload.pick_files(
                    allow_multiple=False,
                    allowed_extensions=["png", "jpg", "jpeg"],
                    dialog_title="اختر صورة"
                ),
                tooltip="إرسال صورة"
            )
        )

        # عناصر البحث في المحادثة
        search_input = TextField(
            label="بحث",
            width=page.width*0.2,
            rtl=True,
            visible=True
        )

        search_results = []
        current_search_index = -1

        def clear_search_highlight(e=None):
            for control in messages_column.controls:
                 if hasattr(control, 'bgcolor'):
                     control.bgcolor = Colors.GREY_100 if hasattr(control.content, 'alignment') and control.content.alignment == alignment.center else Colors.WHITE
            page.update()

        def scroll_to_message_by_key(key_str):
            """التمرير إلى رسالة عبر المفتاح الخاص بها"""
            try:
                messages_column.scroll_to(key=key_str)
                page.update()
            except Exception as ex:
                print(f"خطأ في التمرير: {ex}")

        def highlight_message(index):
            if 0 <= index < len(search_results):
                clear_search_highlight()
                msg_index = search_results[index]
                target_msg = messages_column.controls[msg_index]
                target_msg.bgcolor = Colors.YELLOW_100
                scroll_to_message_by_key(target_msg.key)

        def find_text_in_messages():
            nonlocal search_results, current_search_index
            search_text = search_input.value.strip().lower()
            search_results = []

            if not search_text:
                page.snack_bar = SnackBar(Text("الرجاء إدخال نص للبحث"))
                page.snack_bar.open = True
                page.update()
                return

            for i, control in enumerate(messages_column.controls):
                found = False
                if hasattr(control, 'content') and hasattr(control.content, 'controls'):
                    for sub_control in control.content.controls:
                        if hasattr(sub_control, 'value') and sub_control.value and search_text in sub_control.value.lower():
                            found = True
                        elif hasattr(sub_control, 'data') and sub_control.data and search_text in str(sub_control.data).lower():
                            found = True
                elif hasattr(control.content, 'value') and control.content.value and search_text in control.content.value.lower():
                    found = True
                elif hasattr(control.content, 'data') and control.content.data and search_text in str(control.content.data).lower():
                    found = True

                if found:
                    search_results.append(i)

            if search_results:
                current_search_index = 0
                highlight_message(current_search_index)
                page.snack_bar = SnackBar(Text(f"تم العثور على {len(search_results)} نتيجة"))
            else:
                current_search_index = -1
                page.snack_bar = SnackBar(Text("لا توجد نتائج مطابقة للبحث"))

            page.snack_bar.open = True
            prev_btn.visible = len(search_results) > 0
            next_btn.visible = len(search_results) > 0
            page.update()

        def next_result(e):
            nonlocal current_search_index
            if search_results:
                current_search_index = (current_search_index + 1) % len(search_results)
                highlight_message(current_search_index)

        def prev_result(e):
            nonlocal current_search_index
            if search_results:
                current_search_index = (current_search_index - 1) % len(search_results)
                highlight_message(current_search_index)

        def copy_message(e):
            """نسخ نص الرسالة"""
            message_text = e.control.data
            page.set_clipboard(message_text)
            page.snack_bar = SnackBar(Text("تم نسخ الرسالة بنجاح"))
            page.snack_bar.open = True
            page.update()

        def export_chat(e, format_type):
            """تصدير المحادثة إلى Excel أو PDF"""
            try:
                # جلب الرسائل من API
                response = api_request("messages", "get", {
                    'sender': my_user, 'receiver': other_user
                })
                messages = response.get("messages", [])
                
                # الرسائل مخزنة بدون تشفير الآن
                decrypted_messages = []
                for msg in messages:
                    msg_id = msg.get("id")
                    sender = msg.get("sender")
                    receiver = other_user if sender == my_user else my_user
                    text_value = msg.get("text", "")
                    timestamp = msg.get("timestamp")
                    
                    if text_value.startswith("image:"):
                        decrypted_text = "[صورة]"
                    else:
                        decrypted_text = text_value
                    
                    decrypted_messages.append((msg_id, sender, receiver, decrypted_text, timestamp))
                
                # التصدير حسب النوع المطلوب
                if format_type == "excel":
                    filepath = export_to_excel(decrypted_messages)
                    file_type = "Excel"
                # else:
                #     filepath = export_to_pdf(decrypted_messages)
                #     file_type = "PDF"
                
                if filepath:
                    # فتح الملف المصدر
                    if os.name == "nt":
                        os.startfile(filepath)
                    elif os.name == "posix":
                        subprocess.Popen(["xdg-open", filepath])
                    
                    page.snack_bar = SnackBar(Text(f"تم تصدير المحادثة إلى {file_type} بنجاح"))
                else:
                    page.snack_bar = SnackBar(Text(f"حدث خطأ أثناء تصدير المحادثة إلى {file_type}"))
                
                page.snack_bar.open = True
                page.update()
            except Exception as e:
                page.snack_bar = SnackBar(Text("حدث خطأ في جلب المحادثة"))
                page.snack_bar.open = True
                page.update()

        # إعدادات رفع الملفات
        upload = FilePicker()
        page.overlay.append(upload)
        last_msg_id = [0]
        selected_contact = {"name": None}
        def search_messages():
            """تصفية الرسائل حسب نص البحث"""
            try:
                if selected_contact["name"]:
                    load_messages(
                        filter_by_contact=selected_contact["name"],
                        search_text=search_field.value if search_field.value else None,
                        reset_list=True
                    )
            except:
                pass


        def load_messages(filter_by_contact=None, older_than=None, reset_list=True, search_text=None,play_notify=False):
            """تحميل الرسائل من API"""
            try:
                response = api_request("messages", "get", {
                    'sender': my_user, 'receiver': other_user
                })
                msgs = response.get("messages", [])
                
                if msgs and msgs[-1].get("id") != last_msg_id[0]:
                    last_msg_id[0] = msgs[-1].get("id")
                    messages_column.controls.clear()

                    for msg in msgs:
                        msg_id = msg.get("id")
                        sender = msg.get("sender")
                        text_value = msg.get("text", "")
                        timestamp_str = msg.get("timestamp")
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S") if timestamp_str else datetime.now()

                        if text_value.startswith("image:"):
                            # معالجة الصورة
                            image_data = text_value[6:]
                            temp_img_path = f"temp_{uuid.uuid4().hex}.jpg"
                            with open(temp_img_path, "wb") as img_file:
                                img_file.write(base64.b64decode(image_data))
                            
                            def open_image(p=temp_img_path):
                                """فتح الصورة في عارض الصور الافتراضي"""
                                try:
                                    if os.name == "nt":
                                        os.startfile(p)
                                    elif os.name == "posix":
                                        subprocess.Popen(["xdg-open", p])
                                except Exception as ex:
                                    page.snack_bar = SnackBar(Text(f"خطأ في فتح الصورة: {ex}"))
                                    page.snack_bar.open = True
                                    page.update()

                            message_content = Column([
                                Text(f"{sender} أرسل صورة:", size=14),
                                Container(
                                    Image(src=temp_img_path, 
                                        width=min(page.width * 0.7, 300), 
                                        height=min(page.width * 0.7, 300), 
                                        fit=ImageFit.CONTAIN),
                                ),
                                ElevatedButton("فتح الصورة", on_click=lambda e: open_image(), height=40),
                                Text(timestamp.strftime('%Y-%m-%d %H:%M'), size=12, color=Colors.GREY)
                            ], spacing=5)

                            messages_column.controls.append(
                                Container(
                                    message_content,
                                    padding=10,
                                    border=border.all(1, Colors.GREY_300),
                                    border_radius=10,
                                    bgcolor=Colors.GREEN_100 if sender == my_user else Colors.WHITE,
                                    alignment=alignment.center_left if sender == my_user else alignment.center_right
                                )
                            )
                        else:
                            # عرض الرسالة النصية مباشرة بدون فك تشفير
                            message_menu = PopupMenuButton(
                                items=[PopupMenuItem(text="نسخ الرسالة", on_click=copy_message, data=text_value)]
                            )

                            messages_column.controls.append(
                            Container(
                                content=Column([
                                    Row([Text(f"{sender}:", size=14, weight=FontWeight.BOLD), message_menu]),
                                    Text(text_value, size=16),
                                    Text(timestamp.strftime('%Y-%m-%d %H:%M'), size=12, color=Colors.GREY)
                                ], spacing=5, rtl=False if sender == my_user else True),
                                padding=10,
                                border=border.all(1, Colors.GREY_300),
                                border_radius=10,
                                bgcolor=Colors.GREEN_100 if sender == my_user else Colors.WHITE,
                                alignment=alignment.center_left if sender == my_user else alignment.center_right,
                                key=f"msg_{msg_id}"
                            )
                        )

                    if play_notify:
                        notify_sound = Audio("https://www.myinstants.com/media/sounds/android-notifacation.mp3", autoplay=True)
                        page.overlay.append(notify_sound)

                page.update()
            except Exception as e:
                page.snack_bar = SnackBar(Text("حدث خطأ في جلب الرسائل"))
                page.snack_bar.open = True
                page.update()

        def send_msg(e):
            """إرسال رسالة نصية"""
            if message_input.value.strip() != "":
                try:
                    # إرسال الرسالة النصية مباشرة بدون تشفير
                    api_request("messages", "post", {
                        "sender": my_user,
                        "receiver": other_user,
                        "text": message_input.value.strip()  # إرسال النص مباشرة بدون تشفير
                    })
                    
                    message_input.value = ""
                    load_messages(play_notify=False)

                except Exception as ex:
                    page.snack_bar = SnackBar(Text(f"خطأ في إرسال الرسالة: {ex}"))
                    page.snack_bar.open = True
                    page.update()

        def send_image_result(e: FilePickerResultEvent):
            """معالجة إرسال الصورة"""
            if e.files:
                file = e.files[0]
                
                try:
                    # قراءة محتوى الصورة الأصلية
                    with open(file.path, "rb") as original_file:
                        file_data = original_file.read()
                    # حفظ نسخة من الصورة الأصلية في مجلد images
                    image_filename = f"image_{uuid.uuid4().hex}.jpg"
                    image_path = os.path.join(IMAGES_FOLDER, image_filename)
                    with open(image_path, "wb") as image_file:
                        image_file.write(file_data)    

                    # تحويل الصورة إلى base64 بدون تشفير
                    image_base64 = base64.b64encode(file_data).decode('utf-8')

                    # إرسال الصورة عبر API
                    api_request("messages", "post", {
                        "sender": my_user,
                        "receiver": other_user,
                        "text": f"image:{image_base64}"  # إرسال الصورة بدون تشفير
                    })
                    
                    load_messages(play_notify=False)
                    # إظهار إشعار بنجاح الحفظ
                    page.snack_bar = SnackBar(Text(f"تم حفظ الصورة في: {image_path}"))
                    page.snack_bar.open = True
                    page.update()

                except Exception as ex:
                    page.snack_bar = SnackBar(Text(f"خطأ في معالجة الصورة: {ex}"))
                    page.snack_bar.open = True
                    page.update()

        upload.on_result = send_image_result
        load_messages()

        async def refresh_loop():
            """حلقة التحديث التلقائي للرسائل"""
            while True:
                await asyncio.sleep(1)
                load_messages(play_notify=False)

        # عناصر واجهة البحث
        prev_btn = IconButton(
            icon=Icons.ARROW_UPWARD,
            on_click=prev_result,
            tooltip="النتيجة السابقة",
            visible=False
        )

        next_btn = IconButton(
            icon=Icons.ARROW_DOWNWARD,
            on_click=next_result,
            tooltip="النتيجة التالية",
            visible=False
        )
        closee_btn = IconButton(
            icon=Icons.CLOSE,
            on_click=clear_search_highlight,
            tooltip="اغلاق",
            visible=True
        )


        # بناء واجهة الدردشة
        page.views.append(
        View(
            f"/chat/{other_user}",
            [  
                AppBar(
                    title=Text(f"{other_user}المحادثة مع ", size=18, color=Colors.WHITE), 
                    center_title=True, 
                    bgcolor=Colors.GREEN,
                    leading=IconButton(icon=Icons.ARROW_BACK, on_click=lambda e: go_user_list()),
                    actions=[
                        PopupMenuButton(
                            icon=Icons.DOWNLOAD,
                            tooltip="تصدير المحادثة",
                            items=[
                                PopupMenuItem(text="تصدير إلى Excel", on_click=lambda e: export_chat(e, "excel")),
                            ]
                        ),
                    ]
                ),
                    Column([
                        Container(
                            Row([
                                search_input,
                                IconButton(
                                    icon=Icons.SEARCH,
                                    on_click=lambda e: find_text_in_messages(),
                                    tooltip="ابحث",
                                    bgcolor=Colors.GREEN,
                                    icon_color=Colors.WHITE
                                ),
                                prev_btn,
                                next_btn,
                                closee_btn
                            ], spacing=5),
                            padding=padding.symmetric(horizontal=10, vertical=5),
                            visible=search_input.visible,
                            bgcolor=Colors.GREY_200,
                            border_radius=10
                        ),
                        
                        Container(
                            messages_column,
                            expand=True,
                            width=page.width
                        ),
                        Container(
                            Row([
                                message_input,
                                IconButton(
                                    icon=Icons.SEND, 
                                    on_click=send_msg,
                                    tooltip="إرسال",
                                    bgcolor=Colors.GREEN,
                                    icon_color=Colors.WHITE
                                )
                            ], 
                            alignment=MainAxisAlignment.SPACE_BETWEEN),
                            padding=padding.symmetric(horizontal=10, vertical=5),
                            bgcolor=Colors.GREY_100,
                            border_radius=10
                        )
                    ], 
                    expand=True,
                    spacing=0)
                ]
            )
        )
        page.update()
        page.loop.create_task(refresh_loop())


    def go_admin():
        """عرض لوحة تحكم المدير"""
        if page.session.get("role") != "admin":
            page.snack_bar = SnackBar(Text("لا تملك صلاحية الوصول إلى لوحة التحكم"))
            page.snack_bar.open = True
            page.update()
            go_user_list()
            return

        page.views.clear()
        username = page.session.get("username")
        
        page.views.append(
            View(
                "/admin",
                [
                    AppBar(
                        title=Text(f"لوحة التحكم {username}", size=18, color=Colors.WHITE), 
                        center_title=True,
                        bgcolor=Colors.GREEN, 
                        leading=IconButton(icon=Icons.ARROW_BACK, on_click=lambda e: go_login())
                    ),
                    Container(
                        Column([
                            Container(
                                Text("شاشة الأدمن الرئيسية", size=20, weight=FontWeight.BOLD),
                                padding=padding.only(bottom=20)
                            ),
                            Container(
                                Image(src="YemenWallet.jpg", 
                                    width=min(page.width*0.5, 170),
                                    height=min(page.width*0.5, 170),
                                    fit=ImageFit.CONTAIN),
                                alignment=alignment.center
                            ),
                            Container(
                                ElevatedButton(
                                    "إدارة المستخدمين", 
                                    on_click=go_admin_control,
                                    width=page.width*0.9,
                                    height=50,
                                    style=ButtonStyle(
                                        bgcolor=Colors.GREEN,
                                        color=Colors.WHITE
                                    )
                                ),
                                padding=padding.only(bottom=10)
                            ),
                            Container(
                                ElevatedButton(
                                    "الانتقال للمحادثات", 
                                    on_click=lambda e: go_user_list(),
                                    width=page.width*0.9,
                                    height=50
                                ),
                                padding=padding.only(bottom=10)
                            ),
                            Container(
                                ElevatedButton(
                                    "تسجيل الخروج", 
                                    on_click=lambda e: go_login(),
                                    width=page.width*0.9,
                                    height=50,
                                    style=ButtonStyle(
                                        bgcolor=Colors.RED_700,
                                        color=Colors.WHITE
                                    )
                                ),
                                padding=padding.only(bottom=10)
                            )
                        ],
                        scroll=ScrollMode.AUTO,
                        horizontal_alignment=CrossAxisAlignment.CENTER),
                        padding=10,
                        expand=True,
                        rtl=True
                    )
                ]
            )
        )
        page.update()

    def go_admin_control(e=None):
        """عرض لوحة إدارة المستخدمين"""
        def validate_new_username(e):
            """التحقق من صحة اسم المستخدم (حروف وأرقام فقط)"""
            new_username.value = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', new_username.value)
            new_username.error_text = None if new_username.value else "اسم المستخدم يجب أن يحتوي على حروف أو أرقام فقط"
            new_username.update()
        
        if page.session.get("role") != "admin":
            page.snack_bar = SnackBar(Text("لا تملك صلاحية الوصول إلى لوحة التحكم"))
            page.snack_bar.open = True
            page.update()
            go_user_list()
            return

        page.views.clear()
        
        new_username = TextField(
            label="اسم المستخدم",
            icon=Icons.PERSON,
            width=page.width * 0.9,
            rtl=True,
            max_length=20,
            on_change=validate_new_username
        )
        
        new_password = TextField(
            label="كلمة السر", 
            password=True, 
            can_reveal_password=True, 
            width=page.width*0.9, 
            rtl=True,
            max_length=12, 
            icon=Icons.PASSWORD
        )
        
        new_role = Dropdown(
            label="الدور", 
            width=page.width*0.9,
            options=[
                dropdown.Option("admin"),
                dropdown.Option("moderator"),
                dropdown.Option("user")
            ]
        )
        
        users_column = ListView(expand=True, spacing=5)

        # حقول تعديل المستخدم
        edit_username = TextField(
            label="اسم المستخدم الجديد", 
            width=page.width*0.9, 
            visible=False, 
            rtl=True
        )
        
        reset_password = TextField(
            label="كلمة المرور الجديدة", 
            password=True, 
            can_reveal_password=True, 
            width=page.width*0.9, 
            visible=False, 
            rtl=True
        )
        
        edit_role = Dropdown(
            label="الدور", 
            width=page.width*0.9,
            options=[
                dropdown.Option("admin"),
                dropdown.Option("moderator"),
                dropdown.Option("user")
            ], 
            visible=False
        )
        
        save_edit_btn = ElevatedButton("حفظ التعديلات", visible=False)
        cancel_edit_btn = ElevatedButton("إلغاء", visible=False)
        
        current_editing_user = [None]

        def load_users():
            """تحميل قائمة المستخدمين من API"""
            users_column.controls.clear()
            try:
                users = api_request("users").get("users", [])
                for user in users:
                    uname = user["username"]
                    users_column.controls.append(
                        Container(
                            Row([
                                Text(uname, width=page.width*0.1, size=12),
                                Text(user["role"], width=page.width*0.2, size=12),
                                Switch(
                                    value=user["active"], 
                                    on_change=lambda e, u=uname: toggle_user(u), 
                                    width=30
                                ),
                                IconButton(
                                    icon=Icons.EDIT, 
                                    on_click=lambda e, u=uname: start_edit_user(u),
                                    icon_size=15
                                ),
                                IconButton(
                                    icon=Icons.DELETE, 
                                    on_click=lambda e, u=uname: delete_user(u),
                                    icon_size=15
                                )
                            ], 
                            alignment=MainAxisAlignment.SPACE_EVENLY,
                            vertical_alignment=CrossAxisAlignment.CENTER),
                            padding=5,
                            border=border.all(1, Colors.GREY_300),
                            border_radius=3,
                            rtl=True
                        )
                    )
                page.update()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في جلب المستخدمين: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        def toggle_user(username):
            """تفعيل/تعطيل مستخدم"""
            try:
                user = next((u for u in api_request("users").get("users", []) if u["username"] == username), None)
                if user:
                    api_request(f"users/{username}", "put", {
                        "username": user["username"],
                        "password": "",  # لا تغيير لكلمة السر
                        "role": user["role"],
                        "active": not user["active"]
                    })
                    load_users()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في تعديل حالة المستخدم: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        def delete_user(username):
            """حذف مستخدم"""
            if username == "admin":
                page.snack_bar = SnackBar(Text("لا يمكن حذف المدير الرئيسي"))
                page.snack_bar.open = True
                page.update()
                return
            
            try:
                api_request(f"users/{username}", "delete")
                load_users()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في حذف المستخدم: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        def start_edit_user(username):
            """بدء عملية تعديل مستخدم"""
            new_username.visible = False
            new_password.visible = False
            new_role.visible = False
            add_user_btn.visible = False
            
            edit_username.visible = True
            reset_password.visible = True
            edit_role.visible = True
            save_edit_btn.visible = True
            cancel_edit_btn.visible = True
            
            try:
                user = next((u for u in api_request("users").get("users", []) if u["username"] == username), None)
                if user:
                    current_editing_user[0] = username
                    edit_username.value = user["username"]
                    edit_role.value = user["role"]
                    reset_password.value = ""
                
                page.update()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في جلب بيانات المستخدم: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        def cancel_edit(e):
            """إلغاء عملية التعديل"""
            new_username.visible = True
            new_password.visible = True
            new_role.visible = True
            add_user_btn.visible = True
            
            edit_username.visible = False
            reset_password.visible = False
            edit_role.visible = False
            save_edit_btn.visible = False
            cancel_edit_btn.visible = False
            
            current_editing_user[0] = None
            page.update()

        def save_edit(e):
            """حفظ التعديلات على المستخدم"""
            if not current_editing_user[0]:
                return
                
            new_username_val = edit_username.value
            new_password_val = reset_password.value
            new_role_val = edit_role.value
            
            try:
                update_data = {
                    "username": new_username_val,
                    "password": new_password_val if new_password_val else "keep_original",  # إذا لم يتم تغيير كلمة السر
                    "role": new_role_val,
                    "active": True  # أو يمكنك إضافة حقل للتحكم في الحالة
                }
                
                api_request(f"users/{current_editing_user[0]}", "put", update_data)
                
                page.snack_bar = SnackBar(Text("تم تحديث بيانات المستخدم بنجاح"))
                page.snack_bar.open = True
                
                cancel_edit(e)
                load_users()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في تحديث المستخدم: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        def add_user(e):
            """إضافة مستخدم جديد"""
            if not new_username.value or not new_password.value or not new_role.value:
                page.snack_bar = SnackBar(Text("جميع الحقول مطلوبة"))
                page.snack_bar.open = True
                page.update()
                return
            try:
                api_request("users", "post", {
                    "username": new_username.value,
                    "password": new_password.value,
                    "role": new_role.value,
                    "active": True
                })
                new_username.value = ""
                new_password.value = ""
                new_role.value = ""
                load_users()
            except Exception as e:
                page.snack_bar = SnackBar(Text(f"حدث خطأ في إضافة المستخدم: {str(e)}"))
                page.snack_bar.open = True
                page.update()

        add_user_btn = ElevatedButton("إضافة مستخدم", on_click=add_user, width=page.width*0.9)
        save_edit_btn.on_click = save_edit
        cancel_edit_btn.on_click = cancel_edit
        
        load_users()

        # بناء واجهة إدارة المستخدمين
        page.views.append(
            View(
                "/admin_control",
                [
                    AppBar(
                        title=Text("إدارة المستخدمين", size=18, color=Colors.WHITE),
                        center_title=True,
                        bgcolor=Colors.GREEN,
                        leading=IconButton(icon=Icons.ARROW_BACK, on_click=lambda e: go_admin())
                    ),
                    Container(
                        Column([
                            Text("إدارة المستخدمين", size=18, weight=FontWeight.BOLD),
                            Container(
                                users_column,
                                height=page.height*0.5,
                                width=page.width*0.9
                            ),
                            Divider(),
                            new_username,
                            new_password,
                            new_role,
                            add_user_btn,
                            ElevatedButton(
                                "رجوع", 
                                on_click=lambda e: go_admin(),
                                width=page.width*0.9
                            ),
                            edit_username,
                            reset_password,
                            edit_role,
                            Row([save_edit_btn, cancel_edit_btn], spacing=10, alignment='center')
                        ],
                        scroll=ScrollMode.AUTO,
                        horizontal_alignment=CrossAxisAlignment.CENTER),
                        padding=10,
                        expand=True,
                        rtl=True
                    )
                ]
            )
        )
        page.update()

    # ------------------------- معالجة تغيير المسارات -------------------------
    def route_change(e):
        """معالجة تغيير المسارات في التطبيق"""
        if page.route == "/":
            go_login()
        elif page.route == "/change_password":
            go_change_password()
        elif page.route == "/users":
            go_user_list()
        elif page.route.startswith("/chat/"):
            other_user = page.route.split("/")[-1]
            go_chat(other_user)
        elif page.route == "/admin":
            go_admin()
        elif page.route == "/admin_control":
            go_admin_control()

    def view_pop(e):
        """معالجة الضغط على زر الرجوع"""
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    # ------------------------- معالجة تغيير حجم النافذة -------------------------
    def on_resize(e):
        """إعادة تحميل الواجهة عند تغيير حجم النافذة"""
        if page.views:
            current_view = page.views[-1]
            if current_view.route == "/":
                go_login()
            elif current_view.route == "/change_password":
                go_change_password()
            elif current_view.route == "/users":
                go_user_list()
            elif current_view.route.startswith("/chat/"):
                other_user = current_view.route.split("/")[-1]
                go_chat(other_user)
            elif current_view.route == "/admin":
                go_admin()
            elif current_view.route == "/admin_control":
                go_admin_control()

    # ------------------------- إعداد معالجي الأحداث -------------------------
    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.on_resize = on_resize

    # بدء التطبيق بالصفحة الحالية
    page.go(page.route)

# تشغيل التطبيق
app(main)
#app(main,port=5521,host="0.0.0.0",view=WEB_BROWSER)