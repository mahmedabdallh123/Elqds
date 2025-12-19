import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
from datetime import datetime, timedelta
from base64 import b64decode
import uuid

# محاولة استيراد PyGithub (لرفع التعديلات)
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق - يمكن تعديلها بسهولة
# ===============================
APP_CONFIG = {
    # إعدادات التطبيق العامة
    "APP_TITLE": "CMMS - سيرفيس تحضيرات بيل يارن",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/BELYARN",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"],
    
    # إعدادات الصور
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp"],
    "MAX_IMAGE_SIZE_MB": 5
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    """إنشاء وإعداد مجلد الصور"""
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        # إنشاء ملف .gitkeep لجعل المجلد فارغاً في GitHub
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass
        st.info(f"📁 تم إنشاء مجلد الصور: {IMAGES_FOLDER}")

def save_uploaded_images(uploaded_files):
    """حفظ الصور المرفوعة وإرجاع أسماء الملفات"""
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        # التحقق من نوع الملف
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن نوعه غير مدعوم")
            continue
        
        # التحقق من حجم الملف
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن حجمه ({file_size_mb:.2f}MB) يتجاوز الحد المسموح ({APP_CONFIG['MAX_IMAGE_SIZE_MB']}MB)")
            continue
        
        # إنشاء اسم فريد للملف
        unique_id = str(uuid.uuid4())[:8]
        original_name = uploaded_file.name.split('.')[0]
        safe_name = re.sub(r'[^\w\-_]', '_', original_name)
        new_filename = f"{safe_name}_{unique_id}.{file_extension}"
        
        # حفظ الملف
        file_path = os.path.join(IMAGES_FOLDER, new_filename)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        saved_files.append(new_filename)
    
    return saved_files

def delete_image_file(image_filename):
    """حذف ملف صورة"""
    try:
        file_path = os.path.join(IMAGES_FOLDER, image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        st.error(f"❌ خطأ في حذف الصورة {image_filename}: {e}")
    return False

def get_image_url(image_filename):
    """الحصول على رابط الصورة للعرض"""
    if not image_filename:
        return None
    
    file_path = os.path.join(IMAGES_FOLDER, image_filename)
    if os.path.exists(file_path):
        # في Streamlit Cloud، نستخدم absolute path
        return file_path
    return None

def display_images(image_filenames, caption="الصور المرفقة"):
    """عرض الصور في واجهة المستخدم"""
    if not image_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    
    # تقسيم الصور إلى أعمدة
    images_per_row = 3
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    
    for i in range(0, len(images), images_per_row):
        cols = st.columns(images_per_row)
        for j in range(images_per_row):
            idx = i + j
            if idx < len(images):
                image_filename = images[idx].strip()
                with cols[j]:
                    image_path = get_image_url(image_filename)
                    if image_path and os.path.exists(image_path):
                        try:
                            st.image(image_path, caption=image_filename, use_column_width=True)
                        except:
                            st.write(f"📷 {image_filename}")
                    else:
                        st.write(f"📷 {image_filename} (غير موجود)")

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON - نسخة محسنة"""
    if not os.path.exists(USERS_FILE):
        # إنشاء مستخدمين افتراضيين مع الصلاحيات المطلوبة
        default_users = {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        # التأكد من أن الملف يحتوي على المستخدم admin الأساسي
        if "admin" not in users:
            users["admin"] = {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
            # حفظ الإضافة مباشرة
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
        
        # التأكد من وجود جميع الحقول المطلوبة لكل مستخدم
        for username, user_data in users.items():
            if "role" not in user_data:
                if username == "admin":
                    user_data["role"] = "admin"
                    user_data["permissions"] = ["all"]
                else:
                    user_data["role"] = "viewer"
                    user_data["permissions"] = ["view"]
            
            if "permissions" not in user_data:
                if user_data.get("role") == "admin":
                    user_data["permissions"] = ["all"]
                elif user_data.get("role") == "editor":
                    user_data["permissions"] = ["view", "edit"]
                else:
                    user_data["permissions"] = ["view"]
                    
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.now().isoformat()
        
        # حفظ أي تحديثات
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        
        return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        # إرجاع المستخدمين الافتراضيين في حالة الخطأ
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }

def save_users(users):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف users.json: {e}")
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    now = datetime.now()
    changed = False
    for user, info in list(state.items()):
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    if not username or username not in state:
        return None
    info = state.get(username)
    if not info or not info.get("active"):
        return None
    try:
        lt = datetime.fromisoformat(info["login_time"])
        remaining = SESSION_DURATION - (datetime.now() - lt)
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    except:
        return None

# -------------------------------
# 🔐 تسجيل الخروج
# -------------------------------
def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    keys = list(st.session_state.keys())
    for k in keys:
        st.session_state.pop(k, None)
    st.rerun()

# -------------------------------
# 🧠 واجهة تسجيل الدخول
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    # تحميل قائمة المستخدمين مباشرة من الملف
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            current_users = json.load(f)
        user_list = list(current_users.keys())
    except:
        user_list = list(users.keys())

    # اختيار المستخدم
    username_input = st.selectbox("👤 اختر المستخدم", user_list)
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            # تحميل المستخدمين من جديد للتأكد من أحدث بيانات
            current_users = load_users()
            
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input == "admin":
                    pass
                elif username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS:
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False
                
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                
                st.success(f"✅ تم تسجيل الدخول: {username_input} ({st.session_state.user_role})")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        else:
            st.warning("⏰ انتهت الجلسة، سيتم تسجيل الخروج.")
            logout_action()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

# -------------------------------
# 🔄 طرق جلب الملف من GitHub
# -------------------------------
def fetch_from_github_requests():
    """تحميل بإستخدام رابط RAW (requests)"""
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        # امسح الكاش
        try:
            st.cache_data.clear()
        except:
            pass
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {e}")
        return False

def fetch_from_github_api():
    """تحميل عبر GitHub API (باستخدام PyGithub token في secrets)"""
    if not GITHUB_AVAILABLE:
        return fetch_from_github_requests()
    
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            return fetch_from_github_requests()
        
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        file_content = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
        content = b64decode(file_content.content)
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            f.write(content)
        try:
            st.cache_data.clear()
        except:
            pass
        return True
    except Exception as e:
        st.error(f"⚠ فشل تحميل الملف من GitHub: {e}")
        return False

# -------------------------------
# 📂 تحميل الشيتات (مخبأ) - معدل لقراءة جميع الشيتات
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# نسخة مع dtype=object لواجهة التحرير
@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    """تحميل جميع الشيتات للتحرير"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات مع dtype=object للحفاظ على تنسيق البيانات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub + مسح الكاش + إعادة تحميل
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    """دالة محسنة للحفظ التلقائي المحلي والرفع إلى GitHub"""
    # احفظ محلياً
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
        return None

    # امسح الكاش
    try:
        st.cache_data.clear()
    except:
        pass

    # حاول الرفع عبر PyGithub token في secrets
    token = st.secrets.get("github", {}).get("token", None)
    if not token:
        st.warning("⚠ لم يتم العثور على GitHub token. سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()

    if not GITHUB_AVAILABLE:
        st.warning("⚠ PyGithub غير متوفر. سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()

    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            result = repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح: {commit_message}")
            return load_sheets_for_edit()
        except Exception as e:
            # حاول رفع كملف جديد أو إنشاء
            try:
                result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                return load_sheets_for_edit()
            except Exception as create_error:
                st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                return None

    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    """دالة الحفظ التلقائي المحسنة"""
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات تلقائياً في GitHub")
        return result
    else:
        st.error("❌ فشل الحفظ التلقائي")
        return sheets_dict

# -------------------------------
# 🧰 دوال مساعدة للمعالجة والنصوص
# -------------------------------
def normalize_name(s):
    if s is None: return ""
    s = str(s).replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

def highlight_cell(val, col_name):
    color_map = {
        "Service Needed": "background-color: #fff3cd; color:#856404; font-weight:bold;",
        "Service Done": "background-color: #d4edda; color:#155724; font-weight:bold;",
        "Service Didn't Done": "background-color: #f8d7da; color:#721c24; font-weight:bold;",
        "Date": "background-color: #e7f1ff; color:#004085; font-weight:bold;",
        "Tones": "background-color: #e8f8f5; color:#0d5c4a; font-weight:bold;",
        "Event": "background-color: #e2f0d9; color:#2e6f32; font-weight:bold;",
        "Correction": "background-color: #fdebd0; color:#7d6608; font-weight:bold;",
        "Servised by": "background-color: #f0f0f0; color:#333; font-weight:bold;",
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;",
        "Images": "background-color: #d6eaf8; color:#1b4f72; font-weight:bold;"
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم بناءً على الدور والصلاحيات"""
    # إذا كان الدور admin، يعطى جميع الصلاحيات
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    
    # إذا كان الدور editor
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    
    # إذا كان الدور viewer أو أي دور آخر
    else:
        # التحقق من الصلاحيات الفردية
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions
        }

def get_servised_by_value(row):
    """استخراج قيمة فني الخدمة من الصف"""
    # قائمة بالأعمدة المحتملة لفني الخدمة
    servised_columns = [
        "Servised by", "SERVISED BY", "servised by", "Servised By",
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    ]
    
    # البحث في الأعمدة المعروفة
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    # البحث في جميع الأعمدة التي قد تحتوي على فني الخدمة
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    return "-"

def get_images_value(row):
    """استخراج قيمة الصور من الصف"""
    # قائمة بالأعمدة المحتملة للصور
    images_columns = [
        "Images", "images", "Pictures", "pictures", "Attachments", "attachments",
        "صور", "الصور", "مرفقات", "المرفقات", "صور الحدث"
    ]
    
    # البحث في الأعمدة المعروفة
    for col in images_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    # البحث في جميع الأعمدة التي قد تحتوي على صور
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["images", "pictures", "attachments", "صور", "مرفقات"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    return ""

# -------------------------------
# 🖥 دالة فحص السيرفيس فقط - من الشيتات الجديدة
# -------------------------------
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس فقط"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_services_sheet_name = f"Card{card_num}_Services"
    
    # إذا لم يكن هناك شيت خدمات منفصل، نبحث في الشيت القديم
    if card_services_sheet_name not in all_sheets:
        # محاولة البحث في الشيت القديم
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
            # فلترة فقط الصفوف التي لها Min_Tones و Max_Tones
            services_df = card_df[
                (card_df.get("Min_Tones", pd.NA).notna()) & 
                (card_df.get("Max_Tones", pd.NA).notna()) &
                (card_df.get("Min_Tones", "") != "") & 
                (card_df.get("Max_Tones", "") != "")
            ].copy()
        else:
            st.warning(f"⚠ لا يوجد شيت باسم {card_services_sheet_name} أو {card_old_sheet_name}")
            return
    else:
        card_df = all_sheets[card_services_sheet_name]
        services_df = card_df.copy()

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key=f"service_view_option_{card_num}"
    )

    min_range = st.session_state.get(f"service_min_range_{card_num}", max(0, current_tons - 500))
    max_range = st.session_state.get(f"service_max_range_{card_num}", current_tons + 500)
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key=f"service_min_range_{card_num}")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key=f"service_max_range_{card_num}")

    # اختيار الشرائح
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] <= current_tons) & (service_plan_df["Max_Tones"] >= current_tons)]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] >= min_range) & (service_plan_df["Max_Tones"] <= max_range)]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    all_results = []
    service_stats = {
        "service_counts": {},  # تعداد كل خدمة مطلوبة
        "service_done_counts": {},  # تعداد الخدمات المنفذة
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {}  # إحصائيات حسب الشريحة
    }
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
        # تحديث إحصائيات الخدمات المطلوبة
        service_stats["by_slice"][slice_key] = {
            "needed": needed_parts,
            "done": [],
            "not_done": [],
            "total_needed": len(needed_parts),
            "total_done": 0
        }
        
        for service in needed_parts:
            service_stats["service_counts"][service] = service_stats["service_counts"].get(service, 0) + 1
        service_stats["total_needed_services"] += len(needed_parts)

        # البحث في خدمات الماكينة
        mask = (services_df.get("Min_Tones", 0).fillna(0) <= slice_max) & (services_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                # تحديد الأعمدة التي تحتوي على خدمات منجزة (استبعاد أعمدة البيانات الوصفية)
                metadata_columns = {
                    "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
                    "Other", "Servised by", "Event", "Correction", "Images",
                    "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
                    "OTHER", "EVENT", "CORRECTION", "SERVISED BY", "IMAGES",
                    "servised by", "Servised By", 
                    "Serviced by", "Service by", "Serviced By", "Service By",
                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة",
                    "صور", "الصور", "مرفقات", "المرفقات"
                }
                
                all_columns = set(services_df.columns)
                service_columns = all_columns - metadata_columns
                
                final_service_columns = set()
                for col in service_columns:
                    col_normalized = normalize_name(col)
                    metadata_normalized = {normalize_name(mc) for mc in metadata_columns}
                    if col_normalized not in metadata_normalized:
                        final_service_columns.add(col)
                
                for col in final_service_columns:
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", "", "null", "0"]:
                        if val.lower() not in ["no", "false", "not done", "لم تتم", "x", "-"]:
                            done_services_set.add(col)
                            # تحديث إحصائيات الخدمات المنفذة
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1

                # جمع بيانات السيرفيس فقط
                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                # البحث عن فني الخدمة
                servised_by_value = get_servised_by_value(row)
                
                # البحث عن الصور
                images_value = get_images_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                # تحديث إحصائيات الشريحة
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
                # مقارنة الخدمات المنجزة مع المطلوبة
                not_done = []
                for needed_part, needed_norm_part in zip(needed_parts, needed_norm):
                    if needed_norm_part not in done_norm:
                        not_done.append(needed_part)
                
                service_stats["by_slice"][slice_key]["not_done"].extend(not_done)

                all_results.append({
                    "Card Number": card_num,
                    "Min_Tons": slice_min,
                    "Max_Tons": slice_max,
                    "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                    "Service Done": ", ".join(done_services) if done_services else "-",
                    "Service Didn't Done": ", ".join(not_done) if not_done else "-",
                    "Tones": current_tones,
                    "Servised by": servised_by_value,
                    "Date": current_date,
                    "Images": images_value if images_value else "-"
                })
        else:
            # إذا لم توجد سجلات سيرفيس
            all_results.append({
                "Card Number": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                "Service Done": "-",
                "Service Didn't Done": ", ".join(needed_parts) if needed_parts else "-",
                "Tones": "-",
                "Servised by": "-",
                "Date": "-",
                "Images": "-"
            })
            
            # تحديث إحصائيات الشريحة (لا يوجد خدمات منفذة)
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

        # عرض الإحصائيات والنسب
        show_service_statistics(service_stats, result_df)

        # عرض الصور إذا كانت موجودة
        if "Images" in result_df.columns:
            for idx, row in result_df.iterrows():
                images_value = row.get("Images", "")
                if images_value and images_value != "-":
                    display_images(images_value, f"📷 صور للحدث #{idx+1}")

        # تنزيل النتائج
        buffer = io.BytesIO()
        result_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Service_Report_Card{card_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ لا توجد خدمات مسجلة لهذه الماكينة.")

def show_service_statistics(service_stats, result_df):
    """عرض الإحصائيات والنسب المئوية لفحص السيرفيس"""
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    
    if service_stats["total_needed_services"] == 0:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    
    # حساب النسبة العامة
    completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100 if service_stats["total_needed_services"] > 0 else 0
    
    # عرض النسب العامة
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📈 نسبة الإنجاز العامة",
            value=f"{completion_rate:.1f}%",
            delta=f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}"
        )
    
    with col2:
        st.metric(
            label="🔢 عدد الخدمات المطلوبة",
            value=service_stats["total_needed_services"]
        )
    
    with col3:
        st.metric(
            label="✅ الخدمات المنفذة",
            value=service_stats["total_done_services"]
        )
    
    with col4:
        remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
        st.metric(
            label="⏳ الخدمات المتبقية",
            value=remaining
        )
    
    st.markdown("---")
    
    # تبويبات للإحصائيات التفصيلية
    stat_tabs = st.tabs([
        "📝 إحصائيات الخدمات",
        "📋 توزيع الخدمات",
        "📊 حسب الشريحة"
    ])
    
    with stat_tabs[0]:
        st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
        
        # إنشاء DataFrame للإحصائيات
        stat_data = []
        all_services = set(service_stats["service_counts"].keys()).union(
            set(service_stats["service_done_counts"].keys())
        )
        
        for service in sorted(all_services):
            needed_count = service_stats["service_counts"].get(service, 0)
            done_count = service_stats["service_done_counts"].get(service, 0)
            completion_rate_service = (done_count / needed_count * 100) if needed_count > 0 else 0
            
            stat_data.append({
                "الخدمة": service,
                "مطلوبة": needed_count,
                "منفذة": done_count,
                "متبقية": needed_count - done_count,
                "نسبة الإنجاز": f"{completion_rate_service:.1f}%",
                "حالة": "✅ ممتاز" if completion_rate_service >= 90 else 
                       "🟢 جيد" if completion_rate_service >= 70 else 
                       "🟡 متوسط" if completion_rate_service >= 50 else 
                       "🔴 ضعيف"
            })
        
        if stat_data:
            stat_df = pd.DataFrame(stat_data)
            st.dataframe(stat_df, use_container_width=True, height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للخدمات.")
    
    with stat_tabs[1]:
        st.markdown("#### 📋 توزيع الخدمات")
        
        if service_stats["service_counts"]:
            # محاولة استخدام plotly إذا كان متاحاً
            try:
                import plotly.express as px
                
                plot_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "مطلوبة",
                        "العدد": needed_count
                    })
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "منفذة",
                        "العدد": done_count
                    })
                
                plot_df = pd.DataFrame(plot_data)
                
                # عرض المخطط
                fig = px.bar(
                    plot_df, 
                    x="الخدمة", 
                    y="العدد", 
                    color="النوع",
                    barmode="group",
                    title="توزيع الخدمات المطلوبة والمنفذة",
                    color_discrete_map={
                        "مطلوبة": "#FF6B6B",
                        "منفذة": "#4ECDC4"
                    }
                )
                fig.update_layout(
                    xaxis_title="الخدمة",
                    yaxis_title="العدد",
                    showlegend=True,
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # مخطط دائري للنسبة العامة
                fig2 = px.pie(
                    names=["✅ منفذة", "⏳ غير منفذة"],
                    values=[service_stats["total_done_services"], 
                           service_stats["total_needed_services"] - service_stats["total_done_services"]],
                    title="نسبة الإنجاز العامة",
                    color_discrete_sequence=["#4ECDC4", "#FF6B6B"]
                )
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
                
            except ImportError:
                # استخدام streamlit native charts بدلاً من plotly
                st.info("📊 عرض البيانات باستخدام الرسوم البيانية المضمنة في Streamlit")
                
                # عرض جدول بسيط للتوزيع
                st.markdown("**📋 توزيع الخدمات:**")
                
                dist_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    completion_rate = (done_count / needed_count * 100) if needed_count > 0 else 0
                    
                    dist_data.append({
                        "الخدمة": service,
                        "مطلوبة": needed_count,
                        "منفذة": done_count,
                        "نسبة": f"{completion_rate:.1f}%"
                    })
                
                if dist_data:
                    dist_df = pd.DataFrame(dist_data).sort_values("نسبة", ascending=False)
                    st.dataframe(dist_df, use_container_width=True, height=300)
                
                # مخطط شريطي بسيط باستخدام streamlit
                st.markdown("**📊 مخطط الخدمات المطلوبة مقابل المنفذة:**")
                
                # تحضير البيانات للرسم البياني
                chart_data = pd.DataFrame({
                    "الخدمة": list(service_stats["service_counts"].keys()),
                    "مطلوبة": list(service_stats["service_counts"].values()),
                    "منفذة": [service_stats["service_done_counts"].get(service, 0) 
                              for service in service_stats["service_counts"].keys()]
                })
                
                # أخذ أول 10 خدمات لعرضها بشكل أوضح
                if len(chart_data) > 10:
                    chart_data = chart_data.nlargest(10, "مطلوبة")
                
                st.bar_chart(
                    chart_data.set_index("الخدمة"),
                    height=400
                )
                
                # عرض النسبة العامة كـ progress bar
                st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
                st.progress(completion_rate / 100)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض المخططات.")
    
    with stat_tabs[2]:
        st.markdown("#### 📊 الإحصائيات حسب الشريحة")
        
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            completion_rate_slice = (slice_data["total_done"] / slice_data["total_needed"] * 100) if slice_data["total_needed"] > 0 else 0
            
            slice_stats_data.append({
                "الشريحة": slice_key,
                "الخدمات المطلوبة": slice_data["total_needed"],
                "الخدمات المنفذة": slice_data["total_done"],
                "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                "نسبة الإنجاز": f"{completion_rate_slice:.1f}%",
                "حالة الشريحة": "✅ ممتازة" if completion_rate_slice >= 90 else 
                               "🟢 جيدة" if completion_rate_slice >= 70 else 
                               "🟡 متوسطة" if completion_rate_slice >= 50 else 
                               "🔴 ضعيفة"
            })
        
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            st.dataframe(slice_stats_df, use_container_width=True, height=400)
            
            # محاولة استخدام plotly للمخططات التفاعلية
            try:
                import plotly.graph_objects as go
                
                # تحليل نطاقات الشرائح
                slice_ranges = []
                completion_rates = []
                
                for slice_item in slice_stats_data:
                    slice_key = slice_item["الشريحة"]
                    slice_range = slice_key.split("-")
                    if len(slice_range) == 2:
                        try:
                            mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                            slice_ranges.append(mid_point)
                            
                            # استخراج النسبة من النص
                            rate_text = slice_item["نسبة الإنجاز"]
                            rate_value = float(rate_text.replace("%", "").strip())
                            completion_rates.append(rate_value)
                        except:
                            continue
                
                if slice_ranges and completion_rates:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(
                        x=slice_ranges,
                        y=completion_rates,
                        mode='lines+markers',
                        name='نسبة الإنجاز',
                        line=dict(color='#4ECDC4', width=3),
                        marker=dict(size=10, color='#FF6B6B')
                    ))
                    
                    fig3.update_layout(
                        title="نسبة الإنجاز حسب نطاق الأطنان",
                        xaxis_title="نطاق الأطنان (منتصف الشريحة)",
                        yaxis_title="نسبة الإنجاز (%)",
                        height=400,
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
                    
            except ImportError:
                # استخدام streamlit line chart بديل
                if slice_stats_data:
                    # تحضير البيانات للرسم البياني
                    chart_data = []
                    for slice_item in slice_stats_data:
                        slice_key = slice_item["الشريحة"]
                        slice_range = slice_key.split("-")
                        if len(slice_range) == 2:
                            try:
                                mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                                rate_text = slice_item["نسبة الإنجاز"]
                                rate_value = float(rate_text.replace("%", "").strip())
                                
                                chart_data.append({
                                    "نطاق الأطنان": mid_point,
                                    "نسبة الإنجاز": rate_value
                                })
                            except:
                                continue
                    
                    if chart_data:
                        chart_df = pd.DataFrame(chart_data).sort_values("نطاق الأطنان")
                        st.line_chart(chart_df.set_index("نطاق الأطنان"), height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للشرائح.")

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن - مع خاصية حساب المدة وعرض الصور (مصححة)
# -------------------------------
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن مع خاصية حساب المدة بين الأحداث"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تهيئة session state
    if "search_params" not in st.session_state:
        st.session_state.search_params = {
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "sort_by": "رقم الماكينة",
            "calculate_duration": False,
            "duration_type": "أيام",
            "duration_filter_min": 0,
            "duration_filter_max": 365,
            "group_by_type": False,
            "show_images": True
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    # قسم البحث - مع إضافة خيارات حساب المدة
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك ملء واحد أو أكثر من الحقول.")
        
        # تبويبات للبحث وخيارات المدة
        main_tabs = st.tabs(["🔍 معايير البحث", "⏱️ خيارات المدة", "📊 تحليل زمني"])
        
        with main_tabs[0]:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # قسم أرقام الماكينات
                with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                    st.caption("أدخل أرقام الماكينات (مفصولة بفواصل أو نطاقات)")
                    card_numbers = st.text_input(
                        "مثال: 1,3,5 أو 1-5 أو 2,4,7-10",
                        value=st.session_state.search_params.get("card_numbers", ""),
                        key="input_cards",
                        placeholder="اتركه فارغاً للبحث في كل الماكينات"
                    )
                    
                    # أزرار سريعة لأرقام الماكينات
                    st.caption("أو اختر من:")
                    quick_cards_col1, quick_cards_col2, quick_cards_col3 = st.columns(3)
                    with quick_cards_col1:
                        if st.button("🔟 أول 10 ماكينات", key="quick_10"):
                            st.session_state.search_params["card_numbers"] = "1-10"
                            st.session_state.search_triggered = True
                            st.rerun()
                    with quick_cards_col2:
                        if st.button("🔟 ماكينات 11-20", key="quick_20"):
                            st.session_state.search_params["card_numbers"] = "11-20"
                            st.session_state.search_triggered = True
                            st.rerun()
                    with quick_cards_col3:
                        if st.button("🗑 مسح", key="clear_cards"):
                            st.session_state.search_params["card_numbers"] = ""
                            st.rerun()
                
                # قسم التواريخ
                with st.expander("📅 **التواريخ**", expanded=True):
                    st.caption("ابحث بالتاريخ (سنة، شهر/سنة)")
                    date_input = st.text_input(
                        "مثال: 2024 أو 1/2024 أو 2024,2025",
                        value=st.session_state.search_params.get("date_range", ""),
                        key="input_date",
                        placeholder="اتركه فارغاً للبحث في كل التواريخ"
                    )
            
            with col2:
                # قسم فنيي الخدمة
                with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                    st.caption("ابحث بأسماء فنيي الخدمة")
                    tech_names = st.text_input(
                        "مثال: أحمد, محمد, علي",
                        value=st.session_state.search_params.get("tech_names", ""),
                        key="input_techs",
                        placeholder="اتركه فارغاً للبحث في كل الفنيين"
                    )
                
                # قسم نص البحث
                with st.expander("📝 **نص البحث**", expanded=True):
                    st.caption("ابحث في وصف الحدث أو التصحيح")
                    search_text = st.text_input(
                        "مثال: صيانة, إصلاح, تغيير",
                        value=st.session_state.search_params.get("search_text", ""),
                        key="input_text",
                        placeholder="اتركه فارغاً للبحث في كل النصوص"
                    )
            
            # قسم خيارات البحث المتقدمة
            with st.expander("⚙ **خيارات متقدمة**", expanded=False):
                col_adv1, col_adv2, col_adv3 = st.columns(3)
                with col_adv1:
                    search_mode = st.radio(
                        "🔍 طريقة البحث:",
                        ["بحث جزئي", "مطابقة كاملة"],
                        index=0 if not st.session_state.search_params.get("exact_match") else 1,
                        key="radio_search_mode",
                        help="بحث جزئي: يبحث عن النص في أي مكان. مطابقة كاملة: يبحث عن النص مطابق تماماً"
                    )
                with col_adv2:
                    include_empty = st.checkbox(
                        "🔍 تضمين الحقول الفارغة",
                        value=st.session_state.search_params.get("include_empty", True),
                        key="checkbox_include_empty",
                        help="تضمين النتائج التي تحتوي على حقول فارغة"
                    )
                with col_adv3:
                    sort_by = st.selectbox(
                        "📊 ترتيب النتائج:",
                        ["رقم الماكينة", "التاريخ", "فني الخدمة", "مدة الحدث"],
                        index=["رقم الماكينة", "التاريخ", "فني الخدمة", "مدة الحدث"].index(
                            st.session_state.search_params.get("sort_by", "رقم الماكينة")
                        ),
                        key="select_sort_by"
                    )
        
        with main_tabs[1]:
            st.markdown("#### ⏱️ خيارات حساب المدة بين الأحداث")
            
            col_dur1, col_dur2 = st.columns(2)
            
            with col_dur1:
                calculate_duration = st.checkbox(
                    "📅 حساب المدة بين الأحداث",
                    value=st.session_state.search_params.get("calculate_duration", False),
                    key="checkbox_calculate_duration",
                    help="حساب المدة بين الأحداث لنفس الماكينة"
                )
                
                if calculate_duration:
                    duration_type = st.selectbox(
                        "وحدة حساب المدة:",
                        ["أيام", "أسابيع", "أشهر"],
                        index=["أيام", "أسابيع", "أشهر"].index(
                            st.session_state.search_params.get("duration_type", "أيام")
                        ),
                        key="select_duration_type"
                    )
                    
                    group_by_type = st.checkbox(
                        "📊 تجميع حسب نوع الحدث",
                        value=st.session_state.search_params.get("group_by_type", False),
                        key="checkbox_group_by_type",
                        help="فصل حساب المدة حسب نوع الحدث (حدث/تصحيح)"
                    )
            
            with col_dur2:
                if calculate_duration:
                    st.markdown("#### 🔍 فلترة حسب المدة")
                    
                    duration_filter_min = st.number_input(
                        "الحد الأدنى للمدة:",
                        min_value=0,
                        value=st.session_state.search_params.get("duration_filter_min", 0),
                        step=1,
                        key="input_duration_min"
                    )
                    
                    duration_filter_max = st.number_input(
                        "الحد الأقصى للمدة:",
                        min_value=duration_filter_min,
                        value=st.session_state.search_params.get("duration_filter_max", 365),
                        step=1,
                        key="input_duration_max"
                    )
                    
                    st.caption(f"سيتم عرض الأحداث التي تتراوح مدتها بين {duration_filter_min} و {duration_filter_max} {duration_type}")
        
        with main_tabs[2]:
            st.markdown("#### 📊 تحليل زمني متقدم")
            
            analysis_options = st.multiselect(
                "اختر نوع التحليل:",
                ["معدل تكرار الأحداث", "مقارنة المدة حسب الفني", "توزيع الأحداث زمنياً", "مقارنة بين الحدث والتصحيح"],
                default=[],
                key="select_analysis_options"
            )
            
            if "معدل تكرار الأحداث" in analysis_options:
                st.info("📈 سيتم حساب متوسط المدة بين الأحداث لكل ماكينة")
            
            if "مقارنة المدة حسب الفني" in analysis_options:
                st.info("👨‍🔧 سيتم مقارنة متوسط المدة التي يستغرقها كل فني")
            
            if "توزيع الأحداث زمنياً" in analysis_options:
                st.info("📅 سيتم تحليل توزيع الأحداث على مدار السنة")
            
            if "مقارنة بين الحدث والتصحيح" in analysis_options:
                st.info("⚖️ سيتم مقارنة المدة بين الأحداث العادية والتصحيحات")
        
        # تحديث معايير البحث
        st.session_state.search_params.update({
            "card_numbers": card_numbers,
            "date_range": date_input,
            "tech_names": tech_names,
            "search_text": search_text,
            "exact_match": search_mode == "مطابقة كاملة",
            "include_empty": include_empty,
            "sort_by": sort_by,
            "calculate_duration": calculate_duration,
            "duration_type": duration_type if calculate_duration else "أيام",
            "duration_filter_min": duration_filter_min if calculate_duration else 0,
            "duration_filter_max": duration_filter_max if calculate_duration else 365,
            "group_by_type": group_by_type if calculate_duration else False,
            "analysis_options": analysis_options,
            "show_images": True
        })
        
        # زر البحث الرئيسي
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        with col_btn1:
            search_clicked = st.button(
                "🔍 **بدء البحث والتحليل**",
                type="primary",
                use_container_width=True,
                key="main_search_btn"
            )
        with col_btn2:
            if st.button("🗑 **مسح الحقول**", use_container_width=True, key="clear_fields"):
                st.session_state.search_params = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة",
                    "calculate_duration": False,
                    "duration_type": "أيام",
                    "duration_filter_min": 0,
                    "duration_filter_max": 365,
                    "group_by_type": False,
                    "analysis_options": [],
                    "show_images": True
                }
                st.session_state.search_triggered = False
                st.rerun()
        with col_btn3:
            if st.button("📊 **عرض كل البيانات**", use_container_width=True, key="show_all"):
                st.session_state.search_params = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة",
                    "calculate_duration": True,
                    "duration_type": "أيام",
                    "duration_filter_min": 0,
                    "duration_filter_max": 365,
                    "group_by_type": True,
                    "analysis_options": ["معدل تكرار الأحداث", "توزيع الأحداث زمنياً"],
                    "show_images": True
                }
                st.session_state.search_triggered = True
                st.rerun()
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        # جمع معايير البحث
        search_params = st.session_state.search_params.copy()
        
        # عرض معايير البحث
        show_search_params(search_params)
        
        # تنفيذ البحث
        show_advanced_search_results_with_duration(search_params, all_sheets)

def calculate_durations_between_events(events_data, duration_type="أيام", group_by_type=False):
    """حساب المدة بين الأحداث لنفس الماكينة"""
    if not events_data:
        return events_data
    
    # تحويل إلى DataFrame
    df = pd.DataFrame(events_data)
    
    # تحويل التواريخ إلى تنسيق datetime
    def parse_date(date_str):
        try:
            # محاولة تحليل تنسيقات مختلفة
            date_str = str(date_str).strip()
            if not date_str or date_str.lower() in ["nan", "none", "-", ""]:
                return None
            
            # تجربة تنسيقات مختلفة
            formats = [
                "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
                "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            
            # إذا فشلت جميع المحاولات
            return None
        except:
            return None
    
    df['Date_Parsed'] = df['Date'].apply(parse_date)
    
    # فرز البيانات حسب الماكينة ثم التاريخ
    df = df.sort_values(['Card Number', 'Date_Parsed'])
    
    # إضافة أعمدة المدة
    df['Previous_Date'] = None
    df['Duration'] = None
    df['Duration_Unit'] = None
    df['Event_Type'] = None
    
    # تحديد نوع الحدث (حدث أو تصحيح)
    def determine_event_type(event, correction):
        event_str = str(event).strip().lower()
        correction_str = str(correction).strip().lower()
        
        if event_str not in ['-', 'nan', 'none', ''] and correction_str not in ['-', 'nan', 'none', '']:
            return "تصحيح"
        elif event_str not in ['-', 'nan', 'none', '']:
            return "حدث"
        elif correction_str not in ['-', 'nan', 'none', '']:
            return "تصحيح"
        else:
            return "غير محدد"
    
    df['Event_Type'] = df.apply(lambda row: determine_event_type(row.get('Event', '-'), row.get('Correction', '-')), axis=1)
    
    # حساب المدة بين الأحداث لكل ماكينة
    durations_data = []
    
    for card_num in df['Card Number'].unique():
        card_events = df[df['Card Number'] == card_num].copy()
        
        if len(card_events) > 1:
            for i in range(1, len(card_events)):
                current_event = card_events.iloc[i]
                previous_event = card_events.iloc[i-1]
                
                current_date = current_event['Date_Parsed']
                previous_date = previous_event['Date_Parsed']
                
                if current_date and previous_date:
                    # حساب المدة بالأيام
                    duration_days = (current_date - previous_date).days
                    
                    # تحويل إلى الوحدة المطلوبة
                    if duration_type == "أسابيع":
                        duration_value = duration_days / 7
                        duration_unit = "أسبوع"
                    elif duration_type == "أشهر":
                        duration_value = duration_days / 30.44  # متوسط أيام الشهر
                        duration_unit = "شهر"
                    else:  # أيام
                        duration_value = duration_days
                        duration_unit = "يوم"
                    
                    # التحقق من تجميع حسب النوع
                    if group_by_type:
                        current_type = current_event['Event_Type']
                        previous_type = previous_event['Event_Type']
                        
                        if current_type == previous_type:
                            duration_info = {
                                'Card Number': card_num,
                                'Current_Event_Date': current_event['Date'],
                                'Previous_Event_Date': previous_event['Date'],
                                'Duration': round(duration_value, 1),
                                'Duration_Unit': duration_unit,
                                'Event_Type': current_type,
                                'Current_Event': current_event.get('Event', '-'),
                                'Previous_Event': previous_event.get('Event', '-'),
                                'Current_Correction': current_event.get('Correction', '-'),
                                'Previous_Correction': previous_event.get('Correction', '-'),
                                'Technician': current_event.get('Servised by', '-')
                            }
                            durations_data.append(duration_info)
                    else:
                        duration_info = {
                            'Card Number': card_num,
                            'Current_Event_Date': current_event['Date'],
                            'Previous_Event_Date': previous_event['Date'],
                            'Duration': round(duration_value, 1),
                            'Duration_Unit': duration_unit,
                            'Event_Type': f"{previous_event['Event_Type']} → {current_event['Event_Type']}",
                            'Current_Event': current_event.get('Event', '-'),
                            'Previous_Event': previous_event.get('Event', '-'),
                            'Current_Correction': current_event.get('Correction', '-'),
                            'Previous_Correction': previous_event.get('Correction', '-'),
                            'Technician': current_event.get('Servised by', '-')
                        }
                        durations_data.append(duration_info)
    
    return durations_data

def show_search_params(search_params):
    """عرض معايير البحث المستخدمة"""
    with st.container():
        st.markdown("### ⚙ معايير البحث المستخدمة")
        
        params_display = []
        if search_params["card_numbers"]:
            params_display.append(f"**🔢 أرقام الماكينات:** {search_params['card_numbers']}")
        if search_params["date_range"]:
            params_display.append(f"**📅 التواريخ:** {search_params['date_range']}")
        if search_params["tech_names"]:
            params_display.append(f"**👨‍🔧 فنيو الخدمة:** {search_params['tech_names']}")
        if search_params["search_text"]:
            params_display.append(f"**📝 نص البحث:** {search_params['search_text']}")
        
        if params_display:
            st.info(" | ".join(params_display))
        else:
            st.info("🔍 **بحث في كل البيانات**")

def show_advanced_search_results_with_duration(search_params, all_sheets):
    """عرض نتائج البحث مع حساب المدة"""
    st.markdown("### 📊 نتائج البحث")
    
    # شريط التقدم
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # البحث في البيانات
    all_results = []
    total_machines = 0
    processed_machines = 0
    
    # حساب إجمالي عدد الماكينات
    for sheet_name in all_sheets.keys():
        if sheet_name != "ServicePlan" and sheet_name.startswith("Card"):
            total_machines += 1
    
    # معالجة أرقام الماكينات المطلوبة
    target_card_numbers = parse_card_numbers(search_params["card_numbers"])
    
    # معالجة أسماء الفنيين
    target_techs = []
    if search_params["tech_names"]:
        techs = search_params["tech_names"].split(',')
        target_techs = [tech.strip().lower() for tech in techs if tech.strip()]
    
    # معالجة التواريخ
    target_dates = []
    if search_params["date_range"]:
        dates = search_params["date_range"].split(',')
        target_dates = [date.strip().lower() for date in dates if date.strip()]
    
    # معالجة نص البحث
    search_terms = []
    if search_params["search_text"]:
        terms = search_params["search_text"].split(',')
        search_terms = [term.strip().lower() for term in terms if term.strip()]
    
    # البحث في جميع الشيتات
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        # استخراج رقم الماكينة
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
            
        card_num = int(card_num_match.group(1))
        
        # التحقق من رقم الماكينة إذا كان هناك تحديد
        if target_card_numbers and card_num not in target_card_numbers:
            continue
        
        processed_machines += 1
        if total_machines > 0:
            progress_bar.progress(processed_machines / total_machines)
        status_text.text(f"🔍 جاري معالجة الماكينة {card_num}...")
        
        df = all_sheets[sheet_name].copy()
        
        # البحث في الصفوف
        for _, row in df.iterrows():
            # تطبيق معايير البحث
            if not check_row_criteria(row, df, card_num, target_techs, target_dates, 
                                     search_terms, search_params):
                continue
            
            # استخراج البيانات
            result = extract_row_data(row, df, card_num)
            if result:
                all_results.append(result)
    
    # إخفاء شريط التقدم
    progress_bar.empty()
    status_text.empty()
    
    # عرض النتائج مع حساب المدة
    if all_results:
        display_search_results_with_duration(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def display_search_results_with_duration(results, search_params):
    """عرض نتائج البحث مع خاصية حساب المدة"""
    # تحويل النتائج إلى DataFrame
    if not results:
        st.warning("⚠ لا توجد نتائج لعرضها")
        return
    
    result_df = pd.DataFrame(results)
    
    # التأكد من وجود البيانات
    if result_df.empty:
        st.warning("⚠ لا توجد بيانات لعرضها")
        return
    
    # إنشاء نسخة للعرض مع معالجة الترتيب
    display_df = result_df.copy()
    
    # تحويل رقم الماكينة إلى رقم صحيح للترتيب
    display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    
    # تحويل التواريخ لترتيب زمني
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    
    # ترتيب النتائج حسب رقم الماكينة ثم التاريخ
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Card_Number_Clean'], 
                                          ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, True, False], na_position='last')
    elif search_params["sort_by"] == "مدة الحدث":
        # سنحتاج إلى حساب المدة أولاً
        pass
    else:  # رقم الماكينة (الافتراضي)
        display_df = display_df.sort_values(by=['Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, False], na_position='last')
    
    # إضافة ترتيب الأحداث لكل ماكينة
    display_df['Event_Order'] = display_df.groupby('Card Number').cumcount() + 1
    display_df['Total_Events'] = display_df.groupby('Card Number')['Card Number'].transform('count')
    
    # عرض الإحصائيات
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    
    with col2:
        unique_machines = display_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        # عدد الماكينات التي لديها أكثر من حدث
        if not display_df.empty:
            machine_counts = display_df.groupby('Card Number').size()
            multi_event_machines = (machine_counts > 1).sum()
            st.metric("🔢 مكن متعددة الأحداث", multi_event_machines)
        else:
            st.metric("🔢 مكن متعددة الأحداث", 0)
    
    with col4:
        # التحقق من وجود عمود الصور في display_df
        has_images_column = 'Images' in display_df.columns
        if has_images_column:
            with_images = display_df[display_df["Images"].notna() & (display_df["Images"] != "-")].shape[0]
            st.metric("📷 تحتوي على صور", with_images)
        else:
            st.metric("📷 تحتوي على صور", 0)
    
    # حساب المدة بين الأحداث إذا كان مطلوباً
    if search_params.get("calculate_duration", False):
        st.markdown("---")
        st.markdown("### ⏱️ تحليل المدة بين الأحداث")
        
        # حساب المدة
        durations_data = calculate_durations_between_events(
            results,
            search_params.get("duration_type", "أيام"),
            search_params.get("group_by_type", False)
        )
        
        if durations_data:
            # تحويل إلى DataFrame
            durations_df = pd.DataFrame(durations_data)
            
            # فلترة حسب نطاق المدة
            duration_min = search_params.get("duration_filter_min", 0)
            duration_max = search_params.get("duration_filter_max", 365)
            
            filtered_durations = durations_df[
                (durations_df['Duration'] >= duration_min) & 
                (durations_df['Duration'] <= duration_max)
            ]
            
            # عرض إحصائيات المدة
            st.markdown("#### 📊 إحصائيات المدة")
            
            col_dur1, col_dur2, col_dur3, col_dur4 = st.columns(4)
            
            with col_dur1:
                avg_duration = filtered_durations['Duration'].mean() if not filtered_durations.empty else 0
                st.metric(f"⏳ متوسط المدة", f"{avg_duration:.1f} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur2:
                min_duration = filtered_durations['Duration'].min() if not filtered_durations.empty else 0
                st.metric(f"⚡ أقصر مدة", f"{min_duration} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur3:
                max_duration = filtered_durations['Duration'].max() if not filtered_durations.empty else 0
                st.metric(f"🐌 أطول مدة", f"{max_duration} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur4:
                total_durations = len(filtered_durations)
                st.metric("🔢 عدد الفترات", total_durations)
            
            # عرض جدول المدة
            st.markdown("#### 📋 جدول المدة بين الأحداث")
            
            # تنسيق الأعمدة للعرض
            display_columns = [
                'Card Number', 'Previous_Event_Date', 'Current_Event_Date',
                'Duration', 'Duration_Unit', 'Event_Type', 'Technician'
            ]
            
            available_columns = [col for col in display_columns if col in filtered_durations.columns]
            
            st.dataframe(
                filtered_durations[available_columns],
                use_container_width=True,
                height=400
            )
            
            # تحليلات إضافية
            analysis_options = search_params.get("analysis_options", [])
            if analysis_options:
                st.markdown("---")
                st.markdown("### 📈 تحليلات متقدمة")
                
                for analysis in analysis_options:
                    if analysis == "معدل تكرار الأحداث":
                        show_event_frequency_analysis(filtered_durations, search_params.get("duration_type", "أيام"))
                    
                    elif analysis == "مقارنة المدة حسب الفني":
                        show_technician_comparison_analysis(filtered_durations)
                    
                    elif analysis == "توزيع الأحداث زمنياً":
                        show_temporal_distribution_analysis(durations_df)
                    
                    elif analysis == "مقارنة بين الحدث والتصحيح":
                        show_event_correction_comparison(filtered_durations)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لحساب المدة بين الأحداث (تحتاج إلى حدثين على الأقل لكل ماكينة)")
    
    # عرض النتائج الأصلية
    st.markdown("---")
    st.markdown("### 📋 النتائج التفصيلية")
    
    # استخدام تبويبات لعرض النتائج
    display_tabs = st.tabs(["📊 عرض جدولي", "📋 عرض تفصيلي حسب الماكينة", "📷 عرض الصور"])
    
    with display_tabs[0]:
        # العرض الجدولي التقليدي
        columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date', 'Event_Order', 'Total_Events']
        
        # إضافة عمود الصور إذا كان موجوداً في النتائج
        has_images_in_results = any('Images' in result for result in results)
        if has_images_in_results and 'Images' not in columns_to_show:
            columns_to_show.append('Images')
        
        columns_to_show = [col for col in columns_to_show if col in display_df.columns]
        
        st.dataframe(
            display_df[columns_to_show].style.apply(style_table, axis=1),
            use_container_width=True,
            height=500
        )
    
    with display_tabs[1]:
        # عرض تفصيلي لكل ماكينة بشكل منفصل
        unique_machines = sorted(display_df['Card Number'].unique(), 
                               key=lambda x: pd.to_numeric(x, errors='coerce') if str(x).isdigit() else float('inf'))
        
        for machine in unique_machines:
            machine_data = display_df[display_df['Card Number'] == machine].copy()
            machine_data = machine_data.sort_values('Event_Order')
            
            with st.expander(f"🔧 الماكينة {machine} - عدد الأحداث: {len(machine_data)}", expanded=len(unique_machines) <= 5):
                
                # عرض إحصائيات الماكينة
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        first_date = machine_data['Date'].iloc[0]
                        st.metric("📅 أول حدث", first_date if first_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 أول حدث", "-")
                with col_stats2:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        last_date = machine_data['Date'].iloc[-1]
                        st.metric("📅 آخر حدث", last_date if last_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 آخر حدث", "-")
                with col_stats3:
                    if not machine_data.empty and 'Servised by' in machine_data.columns:
                        tech_count = machine_data['Servised by'].nunique()
                        st.metric("👨‍🔧 فنيين مختلفين", tech_count)
                    else:
                        st.metric("👨‍🔧 فنيين مختلفين", 0)
                
                # عرض أحداث الماكينة
                for idx, row in machine_data.iterrows():
                    st.markdown("---")
                    col_event1, col_event2 = st.columns([3, 2])
                    
                    with col_event1:
                        event_order = row.get('Event_Order', '?')
                        total_events = row.get('Total_Events', '?')
                        st.markdown(f"**الحدث #{event_order} من {total_events}**")
                        if 'Date' in row:
                            st.markdown(f"**📅 التاريخ:** {row['Date']}")
                        if 'Event' in row and row['Event'] != '-':
                            st.markdown(f"**📝 الحدث:** {row['Event']}")
                        if 'Correction' in row and row['Correction'] != '-':
                            st.markdown(f"**✏ التصحيح:** {row['Correction']}")
                    
                    with col_event2:
                        if 'Servised by' in row and row['Servised by'] != '-':
                            st.markdown(f"**👨‍🔧 فني الخدمة:** {row['Servised by']}")
                        if 'Tones' in row and row['Tones'] != '-':
                            st.markdown(f"**⚖️ الأطنان:** {row['Tones']}")
                        
                        # عرض معلومات الصور إذا كانت موجودة
                        if 'Images' in row and row['Images'] not in ['-', '', None, 'nan']:
                            images_str = str(row['Images'])
                            if images_str.strip():
                                images_count = len(images_str.split(',')) if images_str else 0
                                st.markdown(f"**📷 عدد الصور:** {images_count}")
    
    with display_tabs[2]:
        # عرض الصور للأحداث التي تحتوي على صور
        # جمع الصور من النتائج
        events_with_images = []
        
        for result in results:
            # التحقق من وجود الصور في كل نتيجة
            if 'Images' in result and result['Images'] and result['Images'] != "-":
                # نسخ النتيجة وإضافة المعلومات اللازمة
                event_with_images = result.copy()
                event_with_images['has_images'] = True
                events_with_images.append(event_with_images)
        
        if events_with_images:
            st.markdown("### 📷 الصور المرفقة بالأحداث")
            
            # تحويل إلى DataFrame للعرض المنظم
            images_df = pd.DataFrame(events_with_images)
            
            for idx, row in images_df.iterrows():
                card_num = row.get('Card Number', 'غير معروف')
                event_date = row.get('Date', 'غير معروف')
                event_text = row.get('Event', 'لا يوجد')
                
                with st.expander(f"📸 صور للحدث - الماكينة {card_num} - {event_date}", expanded=False):
                    # عرض تفاصيل الحدث
                    col_img1, col_img2 = st.columns([2, 3])
                    
                    with col_img1:
                        st.markdown("**تفاصيل الحدث:**")
                        st.markdown(f"**رقم الماكينة:** {card_num}")
                        st.markdown(f"**التاريخ:** {event_date}")
                        st.markdown(f"**الحدث:** {event_text[:50]}{'...' if len(event_text) > 50 else ''}")
                        st.markdown(f"**التصحيح:** {row.get('Correction', '-')}")
                        st.markdown(f"**فني الخدمة:** {row.get('Servised by', '-')}")
                    
                    with col_img2:
                        # عرض الصور
                        images_value = row.get('Images', '')
                        if images_value:
                            display_images(images_value, "الصور المرفقة")
        else:
            st.info("ℹ️ لا توجد أحداث تحتوي على صور في نتائج البحث")
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        # تصدير Excel
        if not result_df.empty:
            buffer_excel = io.BytesIO()
            
            export_df = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_df['Card_Number_Clean_Export'] = pd.to_numeric(export_df['Card Number'], errors='coerce')
            export_df['Date_Clean_Export'] = pd.to_datetime(export_df['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_df = export_df.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                             ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_df = export_df.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
            # حفظ الملف
            export_df.to_excel(buffer_excel, index=False, engine="openpyxl")
            
            st.download_button(
                label="📊 حفظ كملف Excel",
                data=buffer_excel.getvalue(),
                file_name=f"بحث_أحداث_مرتب_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("⚠ لا توجد بيانات للتصدير")
    
    with export_col2:
        # تصدير CSV
        if not result_df.empty:
            buffer_csv = io.BytesIO()
            
            export_csv = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_csv['Card_Number_Clean_Export'] = pd.to_numeric(export_csv['Card Number'], errors='coerce')
            export_csv['Date_Clean_Export'] = pd.to_datetime(export_csv['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_csv = export_csv.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                               ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_csv = export_csv.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
            # حفظ الملف
            export_csv.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="📄 حفظ كملف CSV",
                data=buffer_csv.getvalue(),
                file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("⚠ لا توجد بيانات للتصدير")
    
    with export_col3:
        # تصدير تقرير المدة
        if search_params.get("calculate_duration", False) and 'durations_data' in locals():
            if durations_data:
                buffer_duration = io.BytesIO()
                
                duration_export_df = pd.DataFrame(durations_data)
                
                with pd.ExcelWriter(buffer_duration, engine='openpyxl') as writer:
                    duration_export_df.to_excel(writer, sheet_name='المدة_بين_الأحداث', index=False)
                    
                    # إضافة ملخص إحصائي
                    summary_data = []
                    for event_type in duration_export_df['Event_Type'].unique():
                        type_data = duration_export_df[duration_export_df['Event_Type'] == event_type]
                        summary_data.append({
                            'نوع الحدث': event_type,
                            'عدد الفترات': len(type_data),
                            f'متوسط المدة ({search_params.get("duration_type", "أيام")})': type_data['Duration'].mean(),
                            'أقل مدة': type_data['Duration'].min(),
                            'أعلى مدة': type_data['Duration'].max()
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='ملخص_إحصائي', index=False)
                
                st.download_button(
                    label="⏱️ حفظ تقرير المدة",
                    data=buffer_duration.getvalue(),
                    file_name=f"تقرير_المدة_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("⚠ لا توجد بيانات مدة للتصدير")

def show_event_frequency_analysis(durations_df, duration_unit):
    """تحليل معدل تكرار الأحداث"""
    st.markdown("#### 📈 معدل تكرار الأحداث")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات لتحليل التكرار")
        return
    
    # تجميع حسب الماكينة
    machine_stats = durations_df.groupby('Card Number').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max']
    }).round(2)
    
    machine_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة']
    machine_stats = machine_stats.reset_index()
    
    # عرض أفضل 10 ماكينات من حيث التكرار
    st.markdown("##### 🥇 أفضل 10 ماكينات من حيث تكرار الصيانة")
    top_10_frequent = machine_stats.sort_values('عدد_الفترات', ascending=False).head(10)
    st.dataframe(top_10_frequent, use_container_width=True)
    
    # عرض ماكينات بأطول مدة بين الأحداث
    st.markdown("##### 🐌 ماكينات بأطول مدة بين الأحداث")
    top_10_longest = machine_stats.sort_values('متوسط_المدة', ascending=False).head(10)
    st.dataframe(top_10_longest, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط توزيع المدة
        fig1 = px.histogram(durations_df, x='Duration', 
                           title=f'توزيع المدة بين الأحداث (بوحدة {duration_unit})',
                           labels={'Duration': f'المدة ({duration_unit})'},
                           nbins=20)
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط العلاقة بين عدد الفترات والمتوسط
        fig2 = px.scatter(machine_stats, x='عدد_الفترات', y='متوسط_المدة',
                         title='العلاقة بين عدد الفترات ومتوسط المدة',
                         hover_data=['Card Number'])
        fig2.update_layout(xaxis_title="عدد الفترات", yaxis_title=f"متوسط المدة ({duration_unit})")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_technician_comparison_analysis(durations_df):
    """مقارنة المدة حسب الفني"""
    st.markdown("#### 👨‍🔧 مقارنة أداء الفنيين")
    
    if durations_df.empty or 'Technician' not in durations_df.columns:
        st.info("ℹ️ لا توجد بيانات فنيين للمقارنة")
        return
    
    # فلترة الفنيين غير المعروفين
    filtered_df = durations_df[durations_df['Technician'] != '-'].copy()
    
    if filtered_df.empty:
        st.info("ℹ️ لا توجد بيانات كافية للمقارنة")
        return
    
    # تجميع حسب الفني
    tech_stats = filtered_df.groupby('Technician').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max'],
        'Card Number': 'nunique'
    }).round(2)
    
    tech_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة', 'عدد_الماكينات']
    tech_stats = tech_stats.reset_index()
    
    # ترتيب حسب متوسط المدة (الأسرع أولاً)
    tech_stats = tech_stats.sort_values('متوسط_المدة')
    
    st.dataframe(tech_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط شريطي لمتوسط المدة حسب الفني
        fig = px.bar(tech_stats, x='Technician', y='متوسط_المدة',
                    title='متوسط المدة بين الأحداث حسب الفني',
                    color='عدد_الماكينات',
                    hover_data=['عدد_الفترات', 'أقل_مدة', 'أعلى_مدة'])
        fig.update_layout(xaxis_title="الفني", yaxis_title="متوسط المدة")
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_temporal_distribution_analysis(durations_df):
    """تحليل التوزيع الزمني"""
    st.markdown("#### 📅 تحليل التوزيع الزمني")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات للتحليل الزمني")
        return
    
    # استخراج الشهر والسنة من التواريخ
    def extract_month_year(date_str):
        try:
            date_obj = datetime.strptime(str(date_str), "%d/%m/%Y")
            return date_obj.strftime("%Y-%m")
        except:
            return "غير معروف"
    
    durations_df['Month_Year'] = durations_df['Current_Event_Date'].apply(extract_month_year)
    
    # تجميع حسب الشهر
    monthly_stats = durations_df[durations_df['Month_Year'] != 'غير معروف'].groupby('Month_Year').agg({
        'Duration': ['count', 'mean'],
        'Card Number': 'nunique'
    }).round(2)
    
    monthly_stats.columns = ['عدد_الأحداث', 'متوسط_المدة', 'عدد_الماكينات']
    monthly_stats = monthly_stats.reset_index()
    
    if monthly_stats.empty:
        st.info("ℹ️ لا توجد بيانات تاريخية صالحة")
        return
    
    st.dataframe(monthly_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط خطي لتطور عدد الأحداث مع الوقت
        fig1 = px.line(monthly_stats, x='Month_Year', y='عدد_الأحداث',
                      title='تطور عدد الأحداث الشهري',
                      markers=True)
        fig1.update_layout(xaxis_title="الشهر", yaxis_title="عدد الأحداث")
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط خطي لمتوسط المدة مع الوقت
        fig2 = px.line(monthly_stats, x='Month_Year', y='متوسط_المدة',
                      title='تطور متوسط المدة بين الأحداث',
                      markers=True)
        fig2.update_layout(xaxis_title="الشهر", yaxis_title="متوسط المدة")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_event_correction_comparison(durations_df):
    """مقارنة بين الحدث العادي والتصحيح"""
    st.markdown("#### ⚖️ مقارنة بين الحدث والتصحيح")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات للمقارنة")
        return
    
    # تحليل حسب نوع الحدث
    event_type_stats = durations_df.groupby('Event_Type').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max'],
        'Card Number': 'nunique'
    }).round(2)
    
    event_type_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة', 'عدد_الماكينات']
    event_type_stats = event_type_stats.reset_index()
    
    st.dataframe(event_type_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط دائري لتوزيع أنواع الأحداث
        fig1 = px.pie(event_type_stats, values='عدد_الفترات', names='Event_Type',
                     title='توزيع أنواع الأحداث')
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط شريطي لمتوسط المدة حسب النوع
        fig2 = px.bar(event_type_stats, x='Event_Type', y='متوسط_المدة',
                     title='متوسط المدة حسب نوع الحدث',
                     color='عدد_الماكينات',
                     hover_data=['عدد_الفترات', 'أقل_مدة', 'أعلى_مدة'])
        fig2.update_layout(xaxis_title="نوع الحدث", yaxis_title="متوسط المدة")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def check_row_criteria(row, df, card_num, target_techs, target_dates, 
                      search_terms, search_params):
    """التحقق من مطابقة الصف لمعايير البحث"""
    
    # 1. التحقق من فني الخدمة
    if target_techs:
        row_tech = get_servised_by_value(row).lower()
        if row_tech == "-" and not search_params["include_empty"]:
            return False
        
        tech_match = False
        if row_tech != "-":
            for tech in target_techs:
                if search_params["exact_match"]:
                    if tech == row_tech:
                        tech_match = True
                        break
                else:
                    if tech in row_tech:
                        tech_match = True
                        break
        
        if not tech_match:
            return False
    
    # 2. التحقق من التاريخ
    if target_dates:
        row_date = str(row.get("Date", "")).strip().lower() if pd.notna(row.get("Date")) else ""
        if not row_date and not search_params["include_empty"]:
            return False
        
        date_match = False
        if row_date:
            for date_term in target_dates:
                if search_params["exact_match"]:
                    if date_term == row_date:
                        date_match = True
                        break
                else:
                    if date_term in row_date:
                        date_match = True
                        break
        
        if not date_match:
            return False
    
    # 3. التحقق من نص البحث
    if search_terms:
        row_event, row_correction = extract_event_correction(row, df)
        row_event_lower = row_event.lower()
        row_correction_lower = row_correction.lower()
        
        if not row_event and not row_correction and not search_params["include_empty"]:
            return False
        
        text_match = False
        combined_text = f"{row_event_lower} {row_correction_lower}"
        
        for term in search_terms:
            if search_params["exact_match"]:
                if term == row_event_lower or term == row_correction_lower:
                    text_match = True
                    break
            else:
                if term in combined_text:
                    text_match = True
                    break
        
        if not text_match:
            return False
    
    return True

def extract_event_correction(row, df):
    """استخراج الحدث والتصحيح من الصف"""
    event_value = "-"
    correction_value = "-"
    
    for col in df.columns:
        col_normalized = normalize_name(col)
        if "event" in col_normalized or "الحدث" in col_normalized:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                event_value = str(row[col]).strip()
        
        if "correction" in col_normalized or "تصحيح" in col_normalized:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                correction_value = str(row[col]).strip()
    
    return event_value, correction_value

def extract_row_data(row, df, card_num):
    """استخراج بيانات الصف"""
    card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
    date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    
    event_value, correction_value = extract_event_correction(row, df)
    
    # استخراج الصور
    images_value = get_images_value(row)
    
    # إذا كانت كل الحقول فارغة، نتجاهل الصف
    if (event_value == "-" and correction_value == "-" and 
        date == "-" and tones == "-" and not images_value):
        return None
    
    servised_by_value = get_servised_by_value(row)
    
    result = {
        "Card Number": card_num_value,
        "Event": event_value,
        "Correction": correction_value,
        "Servised by": servised_by_value,
        "Tones": tones,
        "Date": date
    }
    
    # إضافة الصور إذا كانت موجودة
    if images_value and images_value.strip():
        result["Images"] = images_value.strip()
    
    return result

def parse_card_numbers(card_numbers_str):
    """تحليل سلسلة أرقام الماكينات إلى قائمة أرقام"""
    if not card_numbers_str:
        return set()
    
    numbers = set()
    
    try:
        parts = card_numbers_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    numbers.update(range(start, end + 1))
                except:
                    continue
            else:
                try:
                    num = int(part)
                    numbers.add(num)
                except:
                    continue
    except:
        return set()
    
    return numbers

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد - مع خاصية رفع الصور (مصححة)
# -------------------------------
def add_new_event(sheets_edit):
    """إضافة إيفينت جديد في شيت منفصل مع خاصية رفع الصور"""
    st.subheader("➕ إضافة حدث جديد مع صور")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    st.markdown("أدخل بيانات الحدث الجديد:")
    
    col1, col2 = st.columns(2)
    with col1:
        card_num = st.text_input("رقم الماكينة:", key="new_event_card")
        event_text = st.text_area("الحدث:", key="new_event_text")
    with col2:
        correction_text = st.text_area("التصحيح:", key="new_correction_text")
        serviced_by = st.text_input("فني الخدمة:", key="new_serviced_by")
    
    event_date = st.text_input("التاريخ (مثال: 20/5/2025):", key="new_event_date")
    
    # قسم رفع الصور
    st.markdown("---")
    st.markdown("### 📷 رفع صور للحدث (اختياري)")
    
    # خيارات رفع الصور
    uploaded_files = st.file_uploader(
        "اختر الصور المرفقة للحدث:",
        type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
        accept_multiple_files=True,
        key="event_images_uploader"
    )
    
    if uploaded_files:
        st.info(f"📁 تم اختيار {len(uploaded_files)} صورة")
        # عرض معاينة للصور المختارة
        preview_cols = st.columns(min(3, len(uploaded_files)))
        for idx, uploaded_file in enumerate(uploaded_files):
            with preview_cols[idx % 3]:
                try:
                    st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)
                except:
                    st.write(f"📷 {uploaded_file.name}")
    
    if st.button("💾 إضافة الحدث الجديد مع الصور", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        
        # حفظ الصور المرفوعة
        saved_images = []
        if uploaded_files:
            saved_images = save_uploaded_images(uploaded_files)
            if saved_images:
                st.success(f"✅ تم حفظ {len(saved_images)} صورة بنجاح")
        
        # إنشاء صف جديد
        new_row = {}
        
        # إضافة البيانات الأساسية للأحداث
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
        # إضافة بيانات الإيفينت والكوريكشن
        event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
        if event_columns and event_text.strip():
            new_row[event_columns[0]] = event_text.strip()
        elif not event_columns and event_text.strip():
            new_row["Event"] = event_text.strip()
        
        correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
        if correction_columns and correction_text.strip():
            new_row[correction_columns[0]] = correction_text.strip()
        elif not correction_columns and correction_text.strip():
            new_row["Correction"] = correction_text.strip()
        
        # البحث عن عمود Servised by
        servised_col = None
        servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
        if servised_columns:
            servised_col = servised_columns[0]
        else:
            for col in df.columns:
                if "servis" in normalize_name(col) or "service" in normalize_name(col) or "فني" in col:
                    servised_col = col
                    break
            if not servised_col:
                servised_col = "Servised by"
        
        if serviced_by.strip():
            new_row[servised_col] = serviced_by.strip()
        
        # إضافة الصور إذا كانت موجودة
        if saved_images:
            # البحث عن عمود الصور أو إنشاؤه
            images_col = None
            images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
            
            if images_columns:
                images_col = images_columns[0]
            else:
                # إنشاء عمود جديد للصور
                images_col = "Images"
                if images_col not in df.columns:
                    df[images_col] = ""
            
            # حفظ أسماء الملفات كسلسلة مفصولة بفواصل
            new_row[images_col] = ", ".join(saved_images)
        
        # إضافة الصف الجديد
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new.astype(object)
        
        # حفظ تلقائي في GitHub
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}" + (f" مع {len(saved_images)} صورة" if saved_images else "")
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            
            # عرض ملخص
            with st.expander("📋 ملخص الحدث المضافة", expanded=True):
                st.markdown(f"**رقم الماكينة:** {card_num}")
                st.markdown(f"**الحدث:** {event_text[:100]}{'...' if len(event_text) > 100 else ''}")
                if saved_images:
                    st.markdown(f"**عدد الصور المرفقة:** {len(saved_images)}")
                    display_images(saved_images, "الصور المحفوظة")
            
            st.rerun()

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن - مع خاصية إدارة الصور
# -------------------------------
def edit_events_and_corrections(sheets_edit):
    """تعديل الإيفينت والكوريكشن مع إدارة الصور"""
    st.subheader("✏ تعديل الحدث والتصحيح والصور")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    # عرض البيانات الحالية
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح والصور)")
    
    # استخراج الأعمدة المطلوبة
    display_columns = ["card", "Date"]
    
    event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
    if event_columns:
        display_columns.append(event_columns[0])
    
    correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
    if correction_columns:
        display_columns.append(correction_columns[0])
    
    servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
    if servised_columns:
        display_columns.append(servised_columns[0])
    
    images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
    if images_columns:
        display_columns.append(images_columns[0])
    
    # عرض البيانات
    display_df = df[display_columns].copy()
    st.dataframe(display_df, use_container_width=True)
    
    # اختيار الصف للتعديل
    st.markdown("### ✏ اختر الصف للتعديل")
    row_index = st.number_input("رقم الصف (ابدأ من 0):", min_value=0, max_value=len(df)-1, step=1, key="edit_row_index")
    
    if st.button("تحميل بيانات الصف", key="load_row_data"):
        if 0 <= row_index < len(df):
            st.session_state["editing_row"] = row_index
            st.session_state["editing_data"] = df.iloc[row_index].to_dict()
    
    if "editing_data" in st.session_state:
        editing_data = st.session_state["editing_data"]
        
        st.markdown("### تعديل البيانات")
        col1, col2 = st.columns(2)
        with col1:
            new_card = st.text_input("رقم الماكينة:", value=editing_data.get("card", ""), key="edit_card")
            new_date = st.text_input("التاريخ:", value=editing_data.get("Date", ""), key="edit_date")
        with col2:
            new_serviced_by = st.text_input("فني الخدمة:", value=editing_data.get("Servised by", ""), key="edit_serviced_by")
        
        # حقول الإيفينت والكوريكشن
        event_col = None
        correction_col = None
        
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["event", "events", "الحدث", "الأحداث"]:
                event_col = col
            elif col_norm in ["correction", "correct", "تصحيح", "تصويب"]:
                correction_col = col
        
        if event_col:
            new_event = st.text_area("الحدث:", value=editing_data.get(event_col, ""), key="edit_event")
        if correction_col:
            new_correction = st.text_area("التصحيح:", value=editing_data.get(correction_col, ""), key="edit_correction")
        
        # قسم إدارة الصور
        st.markdown("---")
        st.markdown("### 📷 إدارة صور الحدث")
        
        # البحث عن عمود الصور
        images_col = None
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["images", "pictures", "attachments", "صور", "مرفقات"]:
                images_col = col
                break
        
        existing_images = []
        if images_col and images_col in editing_data:
            existing_images_str = editing_data.get(images_col, "")
            if existing_images_str and existing_images_str != "-":
                existing_images = [img.strip() for img in existing_images_str.split(",") if img.strip()]
        
        # عرض الصور الحالية
        if existing_images:
            st.markdown("**الصور الحالية:**")
            display_images(existing_images, "")
            
            # خيار حذف الصور
            if st.checkbox("🗑️ حذف كل الصور الحالية", key="delete_existing_images"):
                existing_images = []
        
        # إضافة صور جديدة
        st.markdown("**إضافة صور جديدة:**")
        new_uploaded_files = st.file_uploader(
            "اختر صور جديدة لإضافتها:",
            type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
            accept_multiple_files=True,
            key="edit_images_uploader"
        )
        
        all_images = existing_images.copy()
        
        if new_uploaded_files:
            st.info(f"📁 تم اختيار {len(new_uploaded_files)} صورة جديدة")
            # حفظ الصور الجديدة
            new_saved_images = save_uploaded_images(new_uploaded_files)
            if new_saved_images:
                all_images.extend(new_saved_images)
                st.success(f"✅ تم حفظ {len(new_saved_images)} صورة جديدة")
        
        if st.button("💾 حفظ التعديلات والصور", key="save_edits_btn"):
            # تحديث البيانات
            df.at[row_index, "card"] = new_card
            df.at[row_index, "Date"] = new_date
            
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            
            # البحث عن عمود Servised by
            servised_col = None
            for col in df.columns:
                if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]:
                    servised_col = col
                    break
            
            if servised_col and new_serviced_by.strip():
                df.at[row_index, servised_col] = new_serviced_by.strip()
            
            # تحديث الصور
            if images_col:
                if all_images:
                    df.at[row_index, images_col] = ", ".join(all_images)
                else:
                    df.at[row_index, images_col] = ""
            elif all_images:
                # إنشاء عمود جديد للصور
                images_col = "Images"
                df[images_col] = ""
                df.at[row_index, images_col] = ", ".join(all_images)
            
            sheets_edit[sheet_name] = df.astype(object)
            
            # حفظ تلقائي في GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"تعديل حدث في {sheet_name} - الصف {row_index}" + (f" مع تحديث الصور" if all_images else "")
            )
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                
                # عرض ملخص
                if all_images:
                    st.info(f"📷 العدد النهائي للصور: {len(all_images)}")
                    display_images(all_images, "الصور المحفوظة")
                
                # مسح بيانات الجلسة
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# -------------------------------
# 🖥 دالة تعديل الشيت مع زر حفظ يدوي
# -------------------------------
def edit_sheet_with_save_button(sheets_edit):
    """تعديل بيانات الشيت مع زر حفظ يدوي"""
    st.subheader("✏ تعديل البيانات")
    
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    
    df = sheets_edit[sheet_name].astype(str).copy()
    
    # عرض البيانات للتحرير
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # محرر البيانات
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )
    
    # التحقق من وجود تغييرات
    has_changes = not edited_df.equals(df)
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        
        # عرض إشعار بالتغييرات غير المحفوظة
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        
        # أزرار الإدارة
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                # حفظ التغييرات
                sheets_edit[sheet_name] = edited_df.astype(object)
                
                # حفظ تلقائي في GitHub
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل يدوي في شيت {sheet_name}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    
                    # تحديث البيانات الأصلية
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    
                    # إعادة التحميل بعد ثانية
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                # استعادة البيانات الأصلية
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info(f"↩️ تم التراجع عن التغييرات في شيت {sheet_name}")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
        
        with col3:
            # عرض ملخص التغييرات
            with st.expander("📊 ملخص التغييرات", expanded=False):
                # حساب الاختلافات
                changes_count = 0
                
                # التحقق من الصفوف المضافة
                if len(edited_df) > len(df):
                    added_rows = len(edited_df) - len(df)
                    st.write(f"➕ **صفوف مضافة:** {added_rows}")
                    changes_count += added_rows
                
                # التحقق من الصفوف المحذوفة
                elif len(edited_df) < len(df):
                    deleted_rows = len(df) - len(edited_df)
                    st.write(f"🗑️ **صفوف محذوفة:** {deleted_rows}")
                    changes_count += deleted_rows
                
                # التحقق من التغييرات في القيم
                changed_cells = 0
                if len(edited_df) == len(df) and edited_df.columns.equals(df.columns):
                    for col in df.columns:
                        if not edited_df[col].equals(df[col]):
                            col_changes = (edited_df[col] != df[col]).sum()
                            changed_cells += col_changes
                
                if changed_cells > 0:
                    st.write(f"✏️ **خلايا معدلة:** {changed_cells}")
                    changes_count += changed_cells
                
                if changes_count == 0:
                    st.write("🔄 **لا توجد تغييرات**")
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
            st.session_state.unsaved_changes[sheet_name] = False
        
        # زر لإعادة تحميل البيانات
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    
    return sheets_edit

# -------------------------------
# 👥 إدارة المستخدمين (للمسؤولين فقط)
# -------------------------------
def manage_users():
    """إدارة المستخدمين والصلاحيات مع حفظ دائم في ملف JSON"""
    st.header("👥 إدارة المستخدمين")
    
    # تحميل أحدث بيانات المستخدمين من الملف
    users = load_users()
    
    # التحقق من أن المستخدم الحالي هو admin
    current_user = st.session_state.get("username")
    if current_user != "admin":
        st.error("❌ الصلاحية مقتصرة على المسؤول (admin) فقط.")
        return
    
    # عرض المستخدمين الحاليين
    st.markdown("### 📋 المستخدمون الحاليون")
    
    if users:
        # إنشاء DataFrame للمستخدمين
        users_data = []
        for username, user_info in users.items():
            users_data.append({
                "اسم المستخدم": username,
                "الدور": user_info.get("role", "viewer"),
                "الصلاحيات": ", ".join(user_info.get("permissions", ["view"])),
                "تاريخ الإنشاء": user_info.get("created_at", "غير معروف")
            })
        
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True)
    else:
        st.info("ℹ️ لا توجد مستخدمين مسجلين بعد.")
    
    st.markdown("---")
    
    # تبويبات لإدارة المستخدمين
    user_tabs = st.tabs(["➕ إضافة مستخدم جديد", "✏ تعديل مستخدم", "🗑 حذف مستخدم", "🔄 تحديث الملف"])
    
    with user_tabs[0]:
        st.markdown("#### ➕ إضافة مستخدم جديد")
        
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("اسم المستخدم الجديد:", key="new_username")
            new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
            confirm_password = st.text_input("تأكيد كلمة المرور:", type="password", key="confirm_password")
        
        with col2:
            user_role = st.selectbox(
                "دور المستخدم:",
                ["admin", "editor", "viewer"],
                index=2,
                key="new_user_role"
            )
            
            # اختيار الصلاحيات بناءً على الدور
            if user_role == "admin":
                default_permissions = ["all"]
                available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
            elif user_role == "editor":
                default_permissions = ["view", "edit"]
                available_permissions = ["view", "edit", "export"]
            else:
                default_permissions = ["view"]
                available_permissions = ["view", "export"]
            
            selected_permissions = st.multiselect(
                "الصلاحيات:",
                options=available_permissions,
                default=default_permissions,
                key="new_user_permissions"
            )
        
        if st.button("💾 إضافة المستخدم", key="add_user_btn"):
            if not new_username:
                st.warning("⚠ الرجاء إدخال اسم المستخدم.")
                return
            
            # تحميل أحدث بيانات قبل الإضافة
            current_users = load_users()
            
            if new_username in current_users:
                st.error("❌ اسم المستخدم موجود بالفعل.")
                return
            
            if not new_password:
                st.warning("⚠ الرجاء إدخال كلمة المرور.")
                return
            
            if new_password != confirm_password:
                st.error("❌ كلمة المرور غير مطابقة.")
                return
            
            if len(new_password) < 6:
                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                return
            
            # إضافة المستخدم الجديد
            current_users[new_username] = {
                "password": new_password,
                "role": user_role,
                "permissions": selected_permissions if selected_permissions else default_permissions,
                "created_at": datetime.now().isoformat()
            }
            
            # حفظ في الملف JSON
            if save_users(current_users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح!")
                st.rerun()
            else:
                st.error("❌ حدث خطأ أثناء حفظ المستخدم.")
    
    with user_tabs[1]:
        st.markdown("#### ✏ تعديل مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لتعديلهم.")
        else:
            # استثناء المستخدم admin من القائمة إذا كان المستخدم الحالي ليس admin
            user_list = list(users.keys())
            if current_user != "admin":
                user_list = [u for u in user_list if u != "admin"]
            
            user_to_edit = st.selectbox(
                "اختر المستخدم للتعديل:",
                user_list,
                key="select_user_to_edit"
            )
            
            if user_to_edit:
                # تحميل أحدث بيانات المستخدم
                current_users = load_users()
                user_info = current_users.get(user_to_edit, {})
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**المستخدم:** {user_to_edit}")
                    st.info(f"**الدور الحالي:** {user_info.get('role', 'viewer')}")
                    
                    # تغيير كلمة المرور
                    st.markdown("##### 🔐 تغيير كلمة المرور")
                    new_password_edit = st.text_input("كلمة المرور الجديدة:", type="password", 
                                                      key="edit_password")
                    confirm_password_edit = st.text_input("تأكيد كلمة المرور:", type="password", 
                                                         key="edit_confirm_password")
                
                with col2:
                    # تغيير الدور
                    new_role = st.selectbox(
                        "تغيير الدور:",
                        ["admin", "editor", "viewer"],
                        index=["admin", "editor", "viewer"].index(user_info.get("role", "viewer")),
                        key="edit_user_role"
                    )
                    
                    # تغيير الصلاحيات بناءً على الدور الجديد
                    if new_role == "admin":
                        default_permissions = ["all"]
                        available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
                    elif new_role == "editor":
                        default_permissions = ["view", "edit"]
                        available_permissions = ["view", "edit", "export"]
                    else:
                        default_permissions = ["view"]
                        available_permissions = ["view", "export"]
                    
                    current_permissions = user_info.get("permissions", default_permissions)
                    new_permissions = st.multiselect(
                        "تغيير الصلاحيات:",
                        options=available_permissions,
                        default=current_permissions,
                        key="edit_user_permissions"
                    )
                
                # أزرار التعديل
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("💾 حفظ التعديلات", key="save_user_edit"):
                        updated = False
                        
                        # تحميل أحدث البيانات قبل التعديل
                        latest_users = load_users()
                        
                        if user_to_edit not in latest_users:
                            st.error("❌ المستخدم غير موجود.")
                            return
                        
                        # تحديث الدور والصلاحيات
                        if latest_users[user_to_edit].get("role") != new_role or \
                           latest_users[user_to_edit].get("permissions") != new_permissions:
                            latest_users[user_to_edit]["role"] = new_role
                            latest_users[user_to_edit]["permissions"] = new_permissions if new_permissions else default_permissions
                            updated = True
                        
                        # تحديث كلمة المرور إذا تم إدخالها
                        if new_password_edit:
                            if new_password_edit != confirm_password_edit:
                                st.error("❌ كلمة المرور غير مطابقة.")
                                return
                            if len(new_password_edit) < 6:
                                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                                return
                            
                            latest_users[user_to_edit]["password"] = new_password_edit
                            updated = True
                        
                        if updated:
                            if save_users(latest_users):
                                st.success(f"✅ تم تحديث المستخدم '{user_to_edit}' بنجاح!")
                                
                                # إذا كان المستخدم الحالي هو الذي تم تعديله، قم بتحديث session state
                                if st.session_state.get("username") == user_to_edit:
                                    st.session_state.user_role = new_role
                                    st.session_state.user_permissions = new_permissions if new_permissions else default_permissions
                                    st.info("🔁 تم تحديث بيانات جلسة العمل الحالية.")
                                
                                st.rerun()
                            else:
                                st.error("❌ حدث خطأ أثناء حفظ التعديلات.")
                        else:
                            st.info("ℹ️ لم يتم إجراء أي تغييرات.")
                
                with col_btn2:
                    # زر إعادة تعيين كلمة المرور
                    if st.button("🔄 إعادة تعيين كلمة المرور", key="reset_password"):
                        # كلمة مرور افتراضية
                        default_password = "user123"
                        
                        # تحميل أحدث البيانات
                        latest_users = load_users()
                        latest_users[user_to_edit]["password"] = default_password
                        
                        if save_users(latest_users):
                            st.warning(f"⚠ تم إعادة تعيين كلمة مرور '{user_to_edit}' إلى: {default_password}")
                            st.info("📋 يجب على المستخدم تغيير كلمة المرور عند أول تسجيل دخول.")
                            st.rerun()
                
                with col_btn3:
                    # زر تحديث البيانات من الملف
                    if st.button("🔄 تحديث البيانات", key="refresh_user_data"):
                        # تحميل أحدث البيانات من الملف
                        users = load_users()
                        st.success("✅ تم تحديث البيانات من الملف.")
                        st.rerun()
    
    with user_tabs[2]:
        st.markdown("#### 🗑 حذف مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لحذفهم.")
        else:
            # قائمة المستخدمين المتاحة للحذف (لا يمكن حذف المسؤول الرئيسي أو المستخدم الحالي)
            deletable_users = [u for u in users.keys() 
                             if u != "admin" and u != current_user]
            
            if not deletable_users:
                st.warning("⚠ لا يمكن حذف أي مستخدمين.")
            else:
                user_to_delete = st.selectbox(
                    "اختر المستخدم للحذف:",
                    deletable_users,
                    key="select_user_to_delete"
                )
                
                if user_to_delete:
                    user_info = users[user_to_delete]
                    
                    st.warning(f"⚠ **تحذير:** أنت على وشك حذف المستخدم '{user_to_delete}'")
                    st.info(f"**الدور:** {user_info.get('role', 'viewer')}")
                    st.info(f"**تاريخ الإنشاء:** {user_info.get('created_at', 'غير معروف')}")
                    
                    # تأكيد الحذف
                    confirm_delete = st.checkbox(f"أؤكد أنني أريد حذف المستخدم '{user_to_delete}'", 
                                                key="confirm_delete")
                    
                    if confirm_delete:
                        if st.button("🗑️ حذف المستخدم نهائياً", type="primary", 
                                    key="delete_user_final"):
                            # التحقق من أن المستخدم ليس مسجلاً دخولاً حالياً
                            state = load_state()
                            if user_to_delete in state and state[user_to_delete].get("active"):
                                st.error("❌ لا يمكن حذف المستخدم أثناء تسجيل دخوله.")
                                return
                            
                            # تحميل أحدث البيانات قبل الحذف
                            latest_users = load_users()
                            
                            # حذف المستخدم
                            if user_to_delete in latest_users:
                                del latest_users[user_to_delete]
                                
                                if save_users(latest_users):
                                    st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح!")
                                    st.rerun()
                                else:
                                    st.error("❌ حدث خطأ أثناء حذف المستخدم.")
                            else:
                                st.error("❌ المستخدم غير موجود.")
    
    with user_tabs[3]:
        st.markdown("#### 🔄 تحديث وإدارة ملف المستخدمين")
        
        # عرض معلومات الملف
        if os.path.exists(USERS_FILE):
            file_stats = os.stat(USERS_FILE)
            file_size_kb = file_stats.st_size / 1024
            file_mod_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            st.info(f"**اسم الملف:** {USERS_FILE}")
            st.info(f"**حجم الملف:** {file_size_kb:.2f} كيلوبايت")
            st.info(f"**آخر تعديل:** {file_mod_time}")
            
            # عرض محتوى الملف الخام
            with st.expander("📄 عرض محتوى ملف users.json"):
                try:
                    with open(USERS_FILE, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    st.code(file_content, language="json")
                except Exception as e:
                    st.error(f"❌ خطأ في قراءة الملف: {e}")
        
        # زر تحديث البيانات من الملف
        if st.button("🔄 تحديث جميع البيانات من الملف", key="refresh_all_data"):
            # تحميل أحدث البيانات
            users = load_users()
            
            # تحديث حالة الجلسة للمستخدم الحالي
            current_user = st.session_state.get("username")
            if current_user and current_user in users:
                st.session_state.user_role = users[current_user].get("role", "viewer")
                st.session_state.user_permissions = users[current_user].get("permissions", ["view"])
                st.success(f"✅ تم تحديث بيانات جلسة {current_user}")
            
            st.success("✅ تم تحديث جميع البيانات من الملف بنجاح!")
            st.rerun()
        
        # زر تنزيل نسخة احتياطية
        if st.button("💾 تنزيل نسخة احتياطية", key="download_backup"):
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, "rb") as f:
                    file_data = f.read()
                
                st.download_button(
                    label="📥 تحميل ملف users.json",
                    data=file_data,
                    file_name=f"users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="download_users_file"
                )
            else:
                st.warning("⚠ ملف users.json غير موجود.")

# -------------------------------
# 📞 الدعم الفني
# -------------------------------
def tech_support():
    """قسم الدعم الفني"""
    st.header("📞 الدعم الفني")
    
    st.markdown(f"""
    ### ℹ️ معلومات التطبيق
    
    **اسم التطبيق:** {APP_CONFIG["APP_TITLE"]}
    **الملف الرئيسي:** {APP_CONFIG["FILE_PATH"]}
    **مستودع GitHub:** {APP_CONFIG["REPO_NAME"]}
    **فرع العمل:** {APP_CONFIG["BRANCH"]}
    
    ### 🔧 استكشاف الأخطاء وإصلاحها
    
    1. **المشكلة:** لا يمكن تحميل الملف من GitHub
       **الحل:** 
       - تأكد من اتصال الإنترنت
       - تحقق من رابط الملف في GitHub
       - اضغط على زر "🔄 تحديث الملف من GitHub"
    
    2. **المشكلة:** لا يمكن حفظ التعديلات
       **الحل:**
       - تأكد من وجود token GitHub في الإعدادات
       - تحقق من صلاحيات الرفع إلى المستودع
    
    3. **المشكلة:** التطبيق يعمل ببطء
       **الحل:**
       - اضغط على زر "🗑 مسح الكاش"
       - قلل عدد الصفوف المعروضة
       - استخدم فلاتر البحث
    
    4. **المشكلة:** الصور لا تظهر
       **الحل:**
       - تأكد من أن ملفات الصور موجودة في مجلد {IMAGES_FOLDER}
       - تحقق من أذونات المجلد
       - حاول رفع الصور مرة أخرى
    
    ### 📊 إحصائيات النظام
    """)
    
    # عرض إحصائيات النظام
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # عدد المستخدمين
        users = load_users()
        st.metric("👥 عدد المستخدمين", len(users))
    
    with col2:
        # عدد الجلسات النشطة
        state = load_state()
        active_sessions = sum(1 for u in state.values() if u.get("active"))
        st.metric("🔒 جلسات نشطة", f"{active_sessions}/{MAX_ACTIVE_USERS}")
    
    with col3:
        # حجم الملف المحلي
        if os.path.exists(APP_CONFIG["LOCAL_FILE"]):
            file_size = os.path.getsize(APP_CONFIG["LOCAL_FILE"]) / (1024 * 1024)  # بالميجابايت
            st.metric("💾 حجم الملف", f"{file_size:.2f} MB")
        else:
            st.metric("💾 حجم الملف", "غير موجود")
    
    # إحصائيات الصور
    st.markdown("---")
    st.markdown("### 📷 إحصائيات الصور")
    
    if os.path.exists(IMAGES_FOLDER):
        image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
        total_images = len(image_files)
        
        if image_files:
            total_size = sum(os.path.getsize(os.path.join(IMAGES_FOLDER, f)) for f in image_files) / (1024 * 1024)
            
            col_img1, col_img2 = st.columns(2)
            with col_img1:
                st.metric("📸 عدد الصور", total_images)
            with col_img2:
                st.metric("💾 حجم الصور", f"{total_size:.2f} MB")
            
            # عرض عينة من الصور
            with st.expander("📋 عرض قائمة الصور", expanded=False):
                sample_images = image_files[:10]
                for img in sample_images:
                    st.write(f"📷 {img}")
                
                if total_images > 10:
                    st.write(f"... و {total_images - 10} صورة أخرى")
        else:
            st.info("ℹ️ لا توجد صور مخزنة بعد")
    else:
        st.warning(f"⚠ مجلد الصور {IMAGES_FOLDER} غير موجود")
    
    # معلومات الجلسة الحالية
    st.markdown("---")
    st.markdown("### 🖥 معلومات الجلسة الحالية")
    
    if st.session_state.get("logged_in"):
        session_info = {
            "المستخدم": st.session_state.get("username", "غير معروف"),
            "الدور": st.session_state.get("user_role", "غير معروف"),
            "الصلاحيات": ", ".join(st.session_state.get("user_permissions", [])),
            "وقت التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for key, value in session_info.items():
            st.text(f"**{key}:** {value}")
    else:
        st.info("ℹ️ لم يتم تسجيل الدخول")
    
    # زر إدارة مجلد الصور
    st.markdown("---")
    if st.button("🗑️ تنظيف مجلد الصور المؤقتة", key="clean_images"):
        if os.path.exists(IMAGES_FOLDER):
            image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
            if image_files:
                for img_file in image_files:
                    try:
                        # يمكن إضافة منطق لحذف الصور القديمة هنا
                        pass
                    except:
                        pass
                st.info(f"ℹ️ يوجد {len(image_files)} صورة في المجلد")
            else:
                st.info("ℹ️ لا توجد صور في المجلد")
        else:
            st.warning("⚠ مجلد الصور غير موجود")
    
    # زر إعادة التشغيل
    if st.button("🔄 إعادة تشغيل التطبيق", key="restart_app"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في إعادة التشغيل: {e}")

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
# إعداد الصفحة
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# إعداد مجلد الصور
setup_images_folder()

# شريط تسجيل الدخول / معلومات الجلسة في الشريط الجانبي
with st.sidebar:
    st.header("👤 الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        user_role = st.session_state.user_role
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | الدور: {user_role} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()

    st.markdown("---")
    st.write("🔧 أدوات:")
    if st.button("🔄 تحديث الملف من GitHub", key="refresh_github"):
        if fetch_from_github_requests():
            st.rerun()
    
    # زر مسح الكاش
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    # زر تحديث الجلسة
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        # تحميل أحدث بيانات المستخدم
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    
    # زر لحفظ جميع التغييرات غير المحفوظة
    if st.session_state.get("unsaved_changes", {}):
        unsaved_count = sum(1 for v in st.session_state.unsaved_changes.values() if v)
        if unsaved_count > 0:
            st.markdown("---")
            st.warning(f"⚠ لديك {unsaved_count} شيت به تغييرات غير محفوظة")
            if st.button("💾 حفظ جميع التغييرات", key="save_all_changes", type="primary"):
                # سيتم التعامل مع هذا في الواجهة الرئيسية
                st.session_state["save_all_requested"] = True
                st.rerun()
    
    # زر إدارة الصور
    st.markdown("---")
    st.markdown("**📷 إدارة الصور:**")
    if os.path.exists(IMAGES_FOLDER):
        image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
        st.caption(f"عدد الصور: {len(image_files)}")
    
    st.markdown("---")
    # زر لإعادة تسجيل الخروج
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

# تحميل الشيتات (عرض وتحليل)
all_sheets = load_all_sheets()

# تحميل الشيتات للتحرير (dtype=object)
sheets_edit = load_sheets_for_edit()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# التحقق من الصلاحيات - استخدم .get() لمنع الأخطاء
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# تحديد التبويبات بناءً على الصلاحيات
if permissions["can_manage_users"]:  # admin
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
    
    # Tab: إدارة المستخدمين (للمسؤولين فقط)
    with tabs[3]:
        manage_users()
    
    # Tab: الدعم الفني (للمسؤولين فقط أو إذا كان الإعداد يسمح للجميع)
    if APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"] or permissions["can_manage_users"]:
        with tabs[4]:
            tech_support()
    
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"])
else:  # viewer
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن"])

# -------------------------------
# Tab: فحص السيرفيس (لجميع المستخدمين)
# -------------------------------
with tabs[0]:
    st.header("📊 فحص السيرفيس")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
        with col2:
            current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")

        if st.button("عرض حالة السيرفيس", key="show_service"):
            st.session_state["show_service_results"] = True

        if st.session_state.get("show_service_results", False):
            check_service_status(card_num, current_tons, all_sheets)

# -------------------------------
# Tab: فحص الإيفينت والكوريكشن (لجميع المستخدمين)
# -------------------------------
with tabs[1]:
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        # واجهة بحث متعدد المعايير
        check_events_and_corrections(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        st.header("🛠 تعديل وإدارة البيانات")

        # تحقق صلاحية الرفع
        token_exists = bool(st.secrets.get("github", {}).get("token", None))
        can_push = token_exists and GITHUB_AVAILABLE

        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "عرض وتعديل شيت",
                "إضافة صف جديد", 
                "إضافة عمود جديد",
                "➕ إضافة حدث جديد مع صور",
                "✏ تعديل الحدث والصور",
                "📷 إدارة الصور"
            ])

            # Tab 1: تعديل بيانات وعرض
            with tab1:
                # التحقق من طلب حفظ جميع التغييرات
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    # هنا يمكنك إضافة منطق لحفظ جميع التغييرات
                    st.session_state["save_all_requested"] = False
                
                # استخدام دالة التعديل مع زر الحفظ
                sheets_edit = edit_sheet_with_save_button(sheets_edit)

            # Tab 2: إضافة صف جديد
            with tab2:
                st.subheader("➕ إضافة صف جديد")
                sheet_name_add = st.selectbox("اختر الشيت لإضافة صف:", list(sheets_edit.keys()), key="add_sheet")
                df_add = sheets_edit[sheet_name_add].astype(str).reset_index(drop=True)
                
                st.markdown("أدخل بيانات الصف الجديد:")

                new_data = {}
                cols = st.columns(3)
                for i, col in enumerate(df_add.columns):
                    with cols[i % 3]:
                        new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}", type="primary"):
                        new_row_df = pd.DataFrame([new_data]).astype(str)
                        df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                        
                        sheets_edit[sheet_name_add] = df_new.astype(object)

                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إضافة صف جديد في {sheet_name_add}"
                        )
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success("✅ تم إضافة الصف الجديد بنجاح!")
                            st.rerun()
                
                with col_btn2:
                    if st.button("🗑 مسح الحقول", key=f"clear_{sheet_name_add}"):
                        st.rerun()

            # Tab 3: إضافة عمود جديد
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                
                new_col_name = st.text_input("اسم العمود الجديد:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "", key="default_value")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}", type="primary"):
                        if new_col_name:
                            df_col[new_col_name] = default_value
                            sheets_edit[sheet_name_col] = df_col.astype(object)
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}"
                            )
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success("✅ تم إضافة العمود الجديد بنجاح!")
                                st.rerun()
                        else:
                            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
                
                with col_btn2:
                    if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
                        st.rerun()

            # Tab 4: إضافة إيفينت جديد مع صور
            with tab4:
                add_new_event(sheets_edit)

            # Tab 5: تعديل الإيفينت والكوريكشن والصور
            with tab5:
                edit_events_and_corrections(sheets_edit)
            
            # Tab 6: إدارة الصور
            with tab6:
                st.subheader("📷 إدارة الصور المخزنة")
                
                if os.path.exists(IMAGES_FOLDER):
                    image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
                    
                    if image_files:
                        st.info(f"عدد الصور المخزنة: {len(image_files)}")
                        
                        # فلترة الصور
                        search_term = st.text_input("🔍 بحث عن صور:", placeholder="ابحث باسم الصورة")
                        
                        filtered_images = image_files
                        if search_term:
                            filtered_images = [img for img in image_files if search_term.lower() in img.lower()]
                            st.caption(f"تم العثور على {len(filtered_images)} صورة")
                        
                        # عرض الصور
                        images_per_page = 9
                        if "image_page" not in st.session_state:
                            st.session_state.image_page = 0
                        
                        total_pages = (len(filtered_images) + images_per_page - 1) // images_per_page
                        
                        if filtered_images:
                            # أزرار التنقل بين الصفحات
                            col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
                            with col_nav1:
                                if st.button("⏪ السابق", disabled=st.session_state.image_page == 0):
                                    st.session_state.image_page = max(0, st.session_state.image_page - 1)
                                    st.rerun()
                            
                            with col_nav2:
                                st.caption(f"الصفحة {st.session_state.image_page + 1} من {total_pages}")
                            
                            with col_nav3:
                                if st.button("التالي ⏩", disabled=st.session_state.image_page == total_pages - 1):
                                    st.session_state.image_page = min(total_pages - 1, st.session_state.image_page + 1)
                                    st.rerun()
                            
                            # عرض الصور
                            start_idx = st.session_state.image_page * images_per_page
                            end_idx = min(start_idx + images_per_page, len(filtered_images))
                            
                            for i in range(start_idx, end_idx, 3):
                                cols = st.columns(3)
                                for j in range(3):
                                    idx = i + j
                                    if idx < end_idx:
                                        with cols[j]:
                                            img_file = filtered_images[idx]
                                            img_path = os.path.join(IMAGES_FOLDER, img_file)
                                            
                                            try:
                                                st.image(img_path, caption=img_file, use_column_width=True)
                                                
                                                # زر حذف الصورة
                                                if st.button(f"🗑 حذف", key=f"delete_{img_file}"):
                                                    if delete_image_file(img_file):
                                                        st.success(f"✅ تم حذف {img_file}")
                                                        st.rerun()
                                                    else:
                                                        st.error(f"❌ فشل حذف {img_file}")
                                            except:
                                                st.write(f"📷 {img_file}")
                                                st.caption("⚠ لا يمكن عرض الصورة")
                    else:
                        st.info("ℹ️ لا توجد صور مخزنة بعد")
                else:
                    st.warning(f"⚠ مجلد الصور {IMAGES_FOLDER} غير موجود")
