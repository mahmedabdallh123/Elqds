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
    "APP_TITLE": "CMMS - نظام إدارة الصيانة الشامل",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l7.xlsx",
    "LOCAL_FILE": "l7.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "📊 تحليلات متقدمة"],
    
    # إعدادات الصور
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    
    # إعدادات الأعمدة الافتراضية
    "DEFAULT_COLUMNS": [
        "card", "Date", "Event", "Correction", "Servised by", "Tones", "Images"
    ],
    
    # أسماء الأعمدة المتوقعة (للبحث الديناميكي)
    "EXPECTED_COLUMNS": {
        "card": ["card", "machine", "رقم", "ماكينة", "جهاز", "كارد", "Card Number", "Card", "Machine No", "Machine", "الماكينة", "رقم الماكينة", "رقم الجهاز"],
        "date": ["date", "تاريخ", "time", "وقت", "Date", "DATE", "التاريخ", "التوقيت", "تاريخ الحدث", "تاريخ التصحيح"],
        "event": ["event", "حدث", "issue", "مشكلة", "Event", "الحدث", "المشكلة", "Issue", "وصف المشكلة", "الحدث/المشكلة"],
        "correction": ["correction", "تصحيح", "solution", "حل", "Correction", "التصحيح", "الحل", "Solution", "الإجراء", "الإجراء المتخذ"],
        "servised_by": ["servised", "serviced", "service", "technician", "فني", "تم بواسطة", "Servised by", "Serviced by", "Technician", "الفني", "المشغل", "اسم الفني", "القائم بالعمل"],
        "tones": ["tones", "طن", "أطنان", "ton", "tone", "Tones", "TON", "الطن", "الوزن", "الإنتاج", "الكمية"],
        "images": ["images", "pictures", "صور", "مرفقات", "Images", "الصور", "المرفقات", "صورة", "رفق"]
    }
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
CATEGORIES_FILE = "categories.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    """إنشاء وإعداد مجلد الصور"""
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def save_uploaded_images(uploaded_files):
    """حفظ الصور المرفوعة وإرجاع أسماء الملفات"""
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن نوعه غير مدعوم")
            continue
        
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن حجمه ({file_size_mb:.2f}MB) يتجاوز الحد المسموح ({APP_CONFIG['MAX_IMAGE_SIZE_MB']}MB)")
            continue
        
        unique_id = str(uuid.uuid4())[:8]
        original_name = uploaded_file.name.split('.')[0]
        safe_name = re.sub(r'[^\w\-_]', '_', original_name)
        new_filename = f"{safe_name}_{unique_id}.{file_extension}"
        
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
        return file_path
    return None

def display_images(image_filenames, caption="الصور المرفقة"):
    """عرض الصور في واجهة المستخدم"""
    if not image_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    
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
                            st.image(image_path, caption=image_filename, use_container_width=True)
                        except:
                            st.write(f"📷 {image_filename}")
                    else:
                        st.write(f"📷 {image_filename} (غير موجود)")

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def download_users_from_github():
    """تحميل ملف المستخدمين من GitHub"""
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل ملف المستخدمين من GitHub: {e}")
        
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    users_data = json.load(f)
                return users_data
            except:
                pass
        
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
        }

def upload_users_to_github(users_data):
    """رفع ملف المستخدمين إلى GitHub"""
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.error("❌ لم يتم العثور على GitHub token")
            return False
        
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO_USERS)
        
        users_json = json.dumps(users_data, indent=4, ensure_ascii=False, sort_keys=True)
        
        try:
            contents = repo.get_contents("users.json", ref="main")
            result = repo.update_file(
                path="users.json",
                message=f"تحديث ملف المستخدمين بواسطة {st.session_state.get('username', 'admin')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                content=users_json,
                sha=contents.sha,
                branch="main"
            )
            return True
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "sha" in error_msg.lower() or "not found" in error_msg.lower():
                try:
                    result = repo.create_file(
                        path="users.json",
                        message=f"إنشاء ملف المستخدمين بواسطة {st.session_state.get('username', 'admin')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        content=users_json,
                        branch="main"
                    )
                    return True
                except Exception as create_error:
                    st.error(f"❌ خطأ في إنشاء ملف المستخدمين على GitHub: {create_error}")
                    return False
            else:
                st.error(f"❌ خطأ في تحديث ملف المستخدمين على GitHub: {e}")
                return False
                
    except Exception as e:
        st.error(f"❌ خطأ في رفع ملف المستخدمين إلى GitHub: {e}")
        return False

def load_users():
    """تحميل بيانات المستخدمين من GitHub"""
    try:
        users_data = download_users_from_github()
        
        if "admin" not in users_data:
            users_data["admin"] = {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
            upload_users_to_github(users_data)
        
        for username, user_data in users_data.items():
            required_fields = ["password", "role", "created_at", "permissions", "active"]
            for field in required_fields:
                if field not in user_data:
                    if field == "password" and username == "admin":
                        user_data[field] = "admin123"
                    elif field == "role" and username == "admin":
                        user_data[field] = "admin"
                    elif field == "role":
                        user_data[field] = "viewer"
                    elif field == "permissions" and username == "admin":
                        user_data[field] = ["all"]
                    elif field == "permissions" and user_data.get("role") == "editor":
                        user_data[field] = ["view", "edit"]
                    elif field == "permissions":
                        user_data[field] = ["view"]
                    elif field == "created_at":
                        user_data[field] = datetime.now().isoformat()
                    elif field == "active":
                        user_data[field] = False
        
        upload_users_to_github(users_data)
        
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل بيانات المستخدمين: {e}")
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
        }

def save_users_to_github(users_data):
    """حفظ بيانات المستخدمين إلى GitHub"""
    return upload_users_to_github(users_data)

def update_user_in_github(username, user_data):
    """تحديث بيانات مستخدم محدد في GitHub"""
    try:
        users = load_users()
        users[username] = user_data
        return save_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في تحديث المستخدم {username}: {e}")
        return False

def add_user_to_github(username, user_data):
    """إضافة مستخدم جديد إلى GitHub"""
    try:
        users = load_users()
        if username in users:
            st.warning(f"⚠ المستخدم '{username}' موجود بالفعل")
            return False
        users[username] = user_data
        return save_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في إضافة المستخدم {username}: {e}")
        return False

def delete_user_from_github(username):
    """حذف مستخدم من GitHub"""
    try:
        users = load_users()
        if username in users:
            del users[username]
            return save_users_to_github(users)
        return False
    except Exception as e:
        st.error(f"❌ خطأ في حذف المستخدم {username}: {e}")
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

    try:
        user_list = list(users.keys())
    except:
        user_list = list(users.keys())

    username_input = st.selectbox("👤 اختر المستخدم", user_list)
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
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
# 📂 تحميل الشيتات (مخبأ)
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel بشكل ديناميكي"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        
        if not sheets:
            return None
        
        for name, df in sheets.items():
            if df.empty:
                continue
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الشيتات: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    """تحميل جميع الشيتات للتحرير"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        
        if not sheets:
            return None
        
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الشيتات للتحرير: {e}")
        return None

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    """دالة محسنة للحفظ التلقائي المحلي والرفع إلى GitHub"""
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

    try:
        st.cache_data.clear()
    except:
        pass

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
            error_msg = str(e)
            if "404" in error_msg or "sha" in error_msg.lower():
                try:
                    result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                    st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                    return load_sheets_for_edit()
                except Exception as create_error:
                    st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                    return None
            else:
                st.error(f"❌ فشل الرفع إلى GitHub: {e}")
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

# ===============================
# 📁 دوال إدارة الأقسام الديناميكية - المعدلة لحل مشكلة التداخل
# ===============================
def load_categories():
    """تحميل الأقسام من ملف JSON"""
    categories_file = "categories.json"
    
    if os.path.exists(categories_file):
        try:
            with open(categories_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    else:
        default_categories = {
            "جميع الأقسام": []  # سيتم تعبئتها بكل الشيتات ديناميكياً
        }
        save_categories(default_categories)
        return default_categories

def save_categories(categories):
    """حفظ الأقسام إلى ملف JSON"""
    try:
        with open("categories.json", "w", encoding="utf-8") as f:
            json.dump(categories, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ الأقسام: {e}")
        return False

def add_category(category_name):
    """إضافة قسم جديد"""
    categories = load_categories()
    
    if category_name not in categories:
        categories[category_name] = []
        save_categories(categories)
        return True
    return False

def delete_category(category_name):
    """حذف قسم"""
    if category_name == "جميع الأقسام":
        return False
    
    categories = load_categories()
    if category_name in categories:
        del categories[category_name]
        save_categories(categories)
        return True
    return False

def add_sheet_to_category(category_name, sheet_name):
    """إضافة شيت إلى قسم معين (إضافة دقيقة بدون أنماط)"""
    categories = load_categories()
    
    if category_name in categories:
        # إضافة اسم الشيت بالكامل (بدون أنماط بحث)
        if sheet_name not in categories[category_name]:
            categories[category_name].append(sheet_name)
            save_categories(categories)
            return True
    return False

def remove_sheet_from_category(category_name, sheet_name):
    """إزالة شيت من قسم"""
    categories = load_categories()
    
    if category_name in categories:
        if sheet_name in categories[category_name]:
            categories[category_name].remove(sheet_name)
            save_categories(categories)
            return True
    return False

def get_sheets_in_category(category_name, all_sheets):
    """
    الحصول على أسماء الشيتات في قسم معين - معدلة لحل مشكلة التداخل
    الآن تعتمد فقط على الأسماء الدقيقة في القسم، وليس على أنماط البحث
    """
    categories = load_categories()
    
    if category_name == "جميع الأقسام":
        # قسم "جميع الأقسام" يعرض كل الشيتات
        return list(all_sheets.keys())
    
    if category_name not in categories:
        return []
    
    # استخدام الأسماء الدقيقة فقط من القسم
    exact_sheet_names = categories[category_name]
    
    # التحقق من وجود هذه الشيتات فعلياً في البيانات
    matched_sheets = []
    for sheet_name in exact_sheet_names:
        if sheet_name in all_sheets:
            matched_sheets.append(sheet_name)
    
    return matched_sheets

def get_category_stats(all_sheets):
    """الحصول على إحصائيات الأقسام"""
    categories = load_categories()
    stats = {}
    
    for category_name in categories.keys():
        sheets_in_cat = get_sheets_in_category(category_name, all_sheets)
        stats[category_name] = {
            "count": len(sheets_in_cat),
            "sheets": sheets_in_cat,
            "patterns": categories[category_name]  # للتوثيق فقط
        }
    
    return stats

def update_all_sheets_category(all_sheets):
    """تحديث قسم 'جميع الأقسام' بكل الشيتات المتاحة"""
    categories = load_categories()
    
    if "جميع الأقسام" in categories:
        categories["جميع الأقسام"] = list(all_sheets.keys())
        save_categories(categories)
    
    return categories

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
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True,
            "can_manage_sheets": True
        }
    
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False,
            "can_manage_sheets": True
        }
    
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions,
            "can_manage_sheets": "manage_sheets" in user_permissions or "all" in user_permissions
        }

# ===============================
# 🔧 دوال مساعدة للعثور على الأعمدة
# ===============================
def find_column_by_keywords(df, keywords_list):
    """البحث عن عمود في DataFrame بناءً على قائمة كلمات مفتاحية"""
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for keyword in keywords_list:
            if keyword.lower() in col_lower:
                return col
    return None

def find_all_matching_columns(df, keywords_list):
    """البحث عن جميع الأعمدة المطابقة لقائمة كلمات مفتاحية"""
    matching_cols = []
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for keyword in keywords_list:
            if keyword.lower() in col_lower:
                matching_cols.append(col)
                break
    return matching_cols

def get_column_mapping(df):
    """الحصول على تعيين الأعمدة المهمة بناءً على الكلمات المفتاحية"""
    mapping = {
        "card": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["card"]),
        "date": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["date"]),
        "event": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["event"]),
        "correction": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["correction"]),
        "servised_by": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["servised_by"]),
        "tones": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["tones"]),
        "images": find_column_by_keywords(df, APP_CONFIG["EXPECTED_COLUMNS"]["images"])
    }
    return mapping

def get_all_detected_columns(all_sheets):
    """الحصول على جميع الأعمدة المكتشفة من كل الشيتات"""
    detected = {
        "card": set(),
        "date": set(),
        "event": set(),
        "correction": set(),
        "servised_by": set(),
        "tones": set(),
        "images": set(),
        "other": set()
    }
    
    for sheet_name, df in all_sheets.items():
        mapping = get_column_mapping(df)
        
        for key, col in mapping.items():
            if col:
                detected[key].add(col)
        
        mapped_cols = set([v for v in mapping.values() if v])
        all_cols = set(df.columns)
        detected["other"].update(all_cols - mapped_cols)
    
    return detected

# ===============================
# 🏭 دوال لاستخراج معلومات الشيت
# ===============================
def get_sheet_info(sheet_name):
    """استخراج معلومات من اسم الشيت (مثل الرقم)"""
    numbers = re.findall(r'\d+', sheet_name)
    if numbers:
        return {
            "name": sheet_name,
            "has_number": True,
            "numbers": numbers,
            "first_number": int(numbers[0]) if numbers else None
        }
    else:
        return {
            "name": sheet_name,
            "has_number": False,
            "numbers": [],
            "first_number": None
        }

# ===============================
# 🔧 دوال استخراج البيانات الديناميكية
# ===============================
def extract_sheet_data(df, sheet_name):
    """استخراج البيانات من أي شيت بشكل ديناميكي"""
    if df.empty:
        return []
    
    results = []
    
    col_mapping = get_column_mapping(df)
    
    for idx, row in df.iterrows():
        try:
            result = {
                "Sheet Name": sheet_name,
                "Row Index": idx,
                "Sheet Info": get_sheet_info(sheet_name)
            }
            
            for key, col_name in col_mapping.items():
                if col_name and col_name in row:
                    value = row[col_name]
                    if pd.notna(value):
                        result[key] = str(value)
                    else:
                        result[key] = ""
                else:
                    result[key] = ""
            
            for col in df.columns:
                if col not in [v for v in col_mapping.values() if v]:
                    col_name = str(col).strip()
                    value = row[col] if col in row and pd.notna(row[col]) else ""
                    
                    if isinstance(value, (datetime, pd.Timestamp)):
                        value = value.strftime("%Y-%m-%d %H:%M:%S")
                    elif value == "" or pd.isna(value):
                        value = ""
                    else:
                        value = str(value)
                    
                    result[col_name] = value
            
            has_data = any(v != "" for k, v in result.items() if k not in ["Sheet Name", "Row Index", "Sheet Info"])
            if has_data:
                results.append(result)
        except Exception as e:
            continue
    
    return results

def check_row_criteria(result, search_params, col_mapping):
    """التحقق من مطابقة الصف لمعايير البحث"""
    
    if search_params.get("sheet_name_search") and search_params["sheet_name_search"].strip():
        sheet_name = result.get("Sheet Name", "").lower()
        search_terms = [term.strip().lower() for term in search_params["sheet_name_search"].split(',') if term.strip()]
        
        match_found = False
        for term in search_terms:
            if search_params.get("exact_match", False):
                if term == sheet_name:
                    match_found = True
                    break
            else:
                if term in sheet_name:
                    match_found = True
                    break
        
        if not match_found:
            return False
    
    if search_params.get("card_numbers") and search_params["card_numbers"].strip():
        card_col = col_mapping.get("card")
        if card_col and card_col in result:
            card_val = str(result[card_col]).lower()
            search_terms = [term.strip().lower() for term in search_params["card_numbers"].split(',') if term.strip()]
            
            match_found = False
            for term in search_terms:
                if search_params.get("exact_match", False):
                    if term == card_val:
                        match_found = True
                        break
                else:
                    if term in card_val:
                        match_found = True
                        break
            
            if not match_found:
                return False
        elif not search_params.get("include_empty", True):
            return False
    
    if search_params.get("date_range") and search_params["date_range"].strip():
        date_col = col_mapping.get("date")
        if date_col and date_col in result:
            date_val = str(result[date_col]).lower()
            search_terms = [term.strip().lower() for term in search_params["date_range"].split(',') if term.strip()]
            
            match_found = False
            for term in search_terms:
                if search_params.get("exact_match", False):
                    if term == date_val:
                        match_found = True
                        break
                else:
                    if term in date_val:
                        match_found = True
                        break
            
            if not match_found:
                return False
        elif not search_params.get("include_empty", True):
            return False
    
    if search_params.get("tech_names") and search_params["tech_names"].strip():
        tech_col = col_mapping.get("servised_by")
        if tech_col and tech_col in result:
            tech_val = str(result[tech_col]).lower()
            search_terms = [term.strip().lower() for term in search_params["tech_names"].split(',') if term.strip()]
            
            match_found = False
            for term in search_terms:
                if search_params.get("exact_match", False):
                    if term == tech_val:
                        match_found = True
                        break
                else:
                    if term in tech_val:
                        match_found = True
                        break
            
            if not match_found:
                return False
        elif not search_params.get("include_empty", True):
            return False
    
    if search_params.get("search_text") and search_params["search_text"].strip():
        event_col = col_mapping.get("event")
        correction_col = col_mapping.get("correction")
        
        event_val = str(result.get(event_col, "")).lower() if event_col and event_col in result else ""
        correction_val = str(result.get(correction_col, "")).lower() if correction_col and correction_col in result else ""
        combined_text = f"{event_val} {correction_val}"
        
        search_terms = [term.strip().lower() for term in search_params["search_text"].split(',') if term.strip()]
        
        match_found = False
        for term in search_terms:
            if search_params.get("exact_match", False):
                if term == event_val or term == correction_val:
                    match_found = True
                    break
            else:
                if term in combined_text:
                    match_found = True
                    break
        
        if not match_found:
            return False
    
    return True

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

def calculate_durations_between_events(events_data, duration_type="أيام", group_by_type=False):
    """حساب المدة بين الأحداث لنفس الماكينة"""
    if not events_data:
        return events_data
    
    df = pd.DataFrame(events_data)
    
    date_column = None
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['date', 'تاريخ', 'time', 'وقت']):
            date_column = col
            break
    
    if not date_column:
        return []
    
    card_column = None
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['card', 'machine', 'رقم', 'ماكينة', 'جهاز', 'كارد']):
            card_column = col
            break
    
    if not card_column:
        card_column = "Sheet Name"
    
    event_column = None
    correction_column = None
    tech_column = None
    
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['event', 'حدث']):
            event_column = col
        elif any(keyword in col_lower for keyword in ['correction', 'تصحيح', 'solution']):
            correction_column = col
        elif any(keyword in col_lower for keyword in ['servised', 'serviced', 'service', 'فني', 'tech']):
            tech_column = col
    
    def parse_date(date_str):
        try:
            date_str = str(date_str).strip()
            if not date_str or date_str.lower() in ["nan", "none", "-", ""]:
                return None
            
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
            
            return None
        except:
            return None
    
    df['Date_Parsed'] = df[date_column].apply(parse_date)
    
    df = df.sort_values([card_column, 'Date_Parsed'])
    
    def determine_event_type(row):
        if event_column and correction_column:
            event_val = str(row.get(event_column, "")).strip().lower()
            correction_val = str(row.get(correction_column, "")).strip().lower()
            
            if event_val not in ['-', 'nan', 'none', ''] and correction_val not in ['-', 'nan', 'none', '']:
                return "تصحيح"
            elif event_val not in ['-', 'nan', 'none', '']:
                return "حدث"
            elif correction_val not in ['-', 'nan', 'none', '']:
                return "تصحيح"
        return "غير محدد"
    
    df['Event_Type'] = df.apply(determine_event_type, axis=1)
    
    durations_data = []
    
    for card_num in df[card_column].unique():
        card_events = df[df[card_column] == card_num].copy()
        
        if len(card_events) > 1:
            for i in range(1, len(card_events)):
                current_event = card_events.iloc[i]
                previous_event = card_events.iloc[i-1]
                
                current_date = current_event['Date_Parsed']
                previous_date = previous_event['Date_Parsed']
                
                if current_date and previous_date:
                    duration_days = (current_date - previous_date).days
                    
                    if duration_type == "أسابيع":
                        duration_value = duration_days / 7
                        duration_unit = "أسبوع"
                    elif duration_type == "أشهر":
                        duration_value = duration_days / 30.44
                        duration_unit = "شهر"
                    else:
                        duration_value = duration_days
                        duration_unit = "يوم"
                    
                    if group_by_type:
                        current_type = current_event['Event_Type']
                        previous_type = previous_event['Event_Type']
                        
                        if current_type == previous_type:
                            duration_info = {
                                'Card Number': card_num,
                                'Current_Event_Date': current_event[date_column],
                                'Previous_Event_Date': previous_event[date_column],
                                'Duration': round(duration_value, 1),
                                'Duration_Unit': duration_unit,
                                'Event_Type': current_type,
                                'Technician': current_event[tech_column] if tech_column and tech_column in current_event else '-'
                            }
                            
                            if event_column and event_column in current_event:
                                duration_info['Current_Event'] = current_event[event_column]
                            if correction_column and correction_column in current_event:
                                duration_info['Current_Correction'] = current_event[correction_column]
                            
                            durations_data.append(duration_info)
                    else:
                        duration_info = {
                            'Card Number': card_num,
                            'Current_Event_Date': current_event[date_column],
                            'Previous_Event_Date': previous_event[date_column],
                            'Duration': round(duration_value, 1),
                            'Duration_Unit': duration_unit,
                            'Event_Type': f"{previous_event['Event_Type']} → {current_event['Event_Type']}",
                            'Technician': current_event[tech_column] if tech_column and tech_column in current_event else '-'
                        }
                        
                        if event_column and event_column in current_event:
                            duration_info['Current_Event'] = current_event[event_column]
                        if correction_column and correction_column in current_event:
                            duration_info['Current_Correction'] = current_event[correction_column]
                        if event_column and event_column in previous_event:
                            duration_info['Previous_Event'] = previous_event[event_column]
                        
                        durations_data.append(duration_info)
    
    return durations_data

# ===============================
# 🖥 دوال ديناميكية للتعامل مع أي شيت وأي أعمدة
# ===============================
def get_all_columns_from_sheets(sheets_dict):
    """الحصول على جميع الأعمدة من جميع الشيتات"""
    all_columns = set()
    for sheet_name, df in sheets_dict.items():
        all_columns.update(df.columns.tolist())
    return sorted(list(all_columns))

def get_sheet_columns(sheets_dict, sheet_name):
    """الحصول على أعمدة شيت معين"""
    if sheet_name in sheets_dict:
        return sheets_dict[sheet_name].columns.tolist()
    return []

def create_dynamic_event_form(df, prefix="", default_values=None):
    """إنشاء نموذج ديناميكي لإدخال بيانات الحدث بناءً على أعمدة الشيت"""
    if default_values is None:
        default_values = {}
    
    col_mapping = get_column_mapping(df)
    
    columns = df.columns.tolist()
    
    text_columns = []
    date_columns = []
    number_columns = []
    image_columns = []
    other_columns = []
    
    for col in columns:
        col_lower = str(col).lower()
        
        if any(keyword in col_lower for keyword in ['image', 'صور', 'picture', 'صورة', 'مرفق']):
            image_columns.append(col)
        elif any(keyword in col_lower for keyword in ['date', 'تاريخ', 'time', 'وقت']):
            date_columns.append(col)
        elif any(keyword in col_lower for keyword in ['ton', 'طن', 'عدد', 'quantity', 'qty']):
            number_columns.append(col)
        elif any(keyword in col_lower for keyword in ['event', 'حدث', 'correction', 'تصحيح', 'notes', 'ملاحظات']):
            text_columns.append(col)
        else:
            other_columns.append(col)
    
    form_data = {}
    
    st.markdown("#### 📝 البيانات الأساسية")
    col1, col2 = st.columns(2)
    
    for i, col in enumerate(text_columns):
        with col1 if i % 2 == 0 else col2:
            default = default_values.get(col, "")
            form_data[col] = st.text_area(f"{col}:", value=default, key=f"{prefix}_{col}_text", height=100)
    
    if date_columns:
        st.markdown("#### 📅 التواريخ")
        date_cols = st.columns(min(3, len(date_columns)))
        for i, col in enumerate(date_columns):
            with date_cols[i % 3]:
                default = default_values.get(col, "")
                form_data[col] = st.text_input(f"{col}:", value=default, key=f"{prefix}_{col}_date", placeholder="مثال: 20/5/2025")
    
    if number_columns:
        st.markdown("#### 🔢 القيم الرقمية")
        num_cols = st.columns(min(3, len(number_columns)))
        for i, col in enumerate(number_columns):
            with num_cols[i % 3]:
                default = default_values.get(col, "")
                form_data[col] = st.text_input(f"{col}:", value=default, key=f"{prefix}_{col}_num")
    
    if other_columns:
        st.markdown("#### 📋 حقول إضافية")
        other_cols = st.columns(3)
        for i, col in enumerate(other_columns):
            with other_cols[i % 3]:
                default = default_values.get(col, "")
                form_data[col] = st.text_input(f"{col}:", value=default, key=f"{prefix}_{col}_other")
    
    if image_columns:
        st.markdown("#### 📷 الصور المرفقة")
        for col in image_columns:
            st.markdown(f"**{col}:**")
            default_images = default_values.get(col, "")
            if default_images:
                st.info(f"الصور الحالية: {default_images}")
                if st.checkbox(f"🗑️ حذف الصور الحالية لـ {col}", key=f"{prefix}_delete_{col}"):
                    default_images = ""
            
            uploaded_files = st.file_uploader(
                f"اختر الصور لـ {col}:",
                type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
                accept_multiple_files=True,
                key=f"{prefix}_{col}_uploader"
            )
            
            if uploaded_files:
                saved_images = save_uploaded_images(uploaded_files)
                if saved_images:
                    if default_images:
                        form_data[col] = default_images + "," + ",".join(saved_images)
                    else:
                        form_data[col] = ",".join(saved_images)
            else:
                form_data[col] = default_images
    
    return form_data

# ===============================
# 🖥 دالة فحص الإيفينت والكوريكشن - المعدلة لحل مشكلة الأقسام
# ===============================
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن مع محركات بحث متعددة وأقسام مستقلة"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تحديث قسم "جميع الأقسام" بكل الشيتات
    update_all_sheets_category(all_sheets)
    
    # اكتشاف الأعمدة الموجودة في كل الشيتات
    detected_columns = get_all_detected_columns(all_sheets)
    
    # عرض ملخص الأعمدة المكتشفة
    with st.expander("📊 الأعمدة المكتشفة في الشيتات", expanded=False):
        col_det1, col_det2 = st.columns(2)
        
        with col_det1:
            st.markdown("**الأعمدة الرئيسية المكتشفة:**")
            for key, cols in detected_columns.items():
                if key != "other" and cols:
                    st.markdown(f"- **{key}:** {', '.join(cols)}")
        
        with col_det2:
            if detected_columns["other"]:
                st.markdown("**أعمدة إضافية:**")
                st.markdown(f"- {', '.join(list(detected_columns['other'])[:10])}")
                if len(detected_columns["other"]) > 10:
                    st.caption(f"... و {len(detected_columns['other']) - 10} أعمدة أخرى")
    
    # تهيئة session state
    if "search_params" not in st.session_state:
        st.session_state.search_params = {
            "selected_category": "جميع الأقسام",
            "sheet_name_search": "",
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "calculate_duration": False,
            "duration_type": "أيام",
            "duration_filter_min": 0,
            "duration_filter_max": 365,
            "group_by_type": False
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    # إحصائيات التصنيفات
    category_stats = get_category_stats(all_sheets)
    
    # قسم اختيار القسم
    st.markdown("### 🔍 فحص الإيفينت والكوريكشن")
    
    # ===============================
    # قسم اختيار القسم - معروض بشكل بارز
    # ===============================
    with st.container():
        col_cat1, col_cat2, col_cat3 = st.columns([3, 2, 1])
        
        with col_cat1:
            categories = load_categories()
            category_list = list(categories.keys())
            
            selected_category = st.selectbox(
                "🏭 اختر القسم الذي تريد البحث فيه:",
                category_list,
                index=category_list.index(st.session_state.search_params.get("selected_category", "جميع الأقسام")) if st.session_state.search_params.get("selected_category") in category_list else 0,
                key="select_category_main"
            )
            
            st.session_state.search_params["selected_category"] = selected_category
        
        with col_cat2:
            if selected_category in category_stats:
                sheets_count = len(category_stats[selected_category]["sheets"])
                st.metric("📊 عدد الشيتات في هذا القسم", sheets_count)
        
        with col_cat3:
            st.markdown("####")
            if st.button("🔄 عرض الإحصائيات", key="show_stats_btn"):
                st.session_state.show_stats = not st.session_state.get("show_stats", False)
    
    # عرض إحصائيات القسم
    if st.session_state.get("show_stats", False) and selected_category in category_stats:
        with st.expander("📊 تفاصيل القسم المختار", expanded=True):
            cat_stat = category_stats[selected_category]
            st.info(f"**{selected_category}**")
            
            if cat_stat["sheets"]:
                st.write(f"**الشيتات في هذا القسم ({len(cat_stat['sheets'])}):**")
                sheet_cols = st.columns(3)
                for i, sheet in enumerate(cat_stat["sheets"]):
                    with sheet_cols[i % 3]:
                        st.write(f"- {sheet}")
            else:
                st.warning("⚠ لا توجد شيتات في هذا القسم")
    
    st.markdown("---")
    
    # ===============================
    # محركات البحث المتعددة
    # ===============================
    with st.container():
        st.markdown("### 🔍 محركات البحث")
        st.markdown("يمكنك استخدام محرك بحث واحد أو أكثر من المحركات التالية:")
        
        search_tabs = st.tabs([
            "🔢 محرك بحث رقم الماكينة", 
            "📅 محرك بحث التاريخ", 
            "👨‍🔧 محرك بحث فني الخدمة",
            "📝 محرك بحث النص",
            "📄 محرك بحث اسم الشيت"
        ])
        
        # محرك بحث رقم الماكينة
        with search_tabs[0]:
            if detected_columns["card"]:
                st.markdown("#### 🔢 محرك بحث رقم الماكينة/الكارد")
                st.caption(f"الأعمدة المكتشفة: {', '.join(detected_columns['card'])}")
                
                col_card1, col_card2, col_card3 = st.columns([3, 1, 1])
                
                with col_card1:
                    card_numbers = st.text_input(
                        "أدخل أرقام الماكينات (مثال: 1,3,5 أو Card1,Card3 أو 1-10):",
                        value=st.session_state.search_params.get("card_numbers", ""),
                        key="input_cards_main",
                        placeholder="اتركه فارغاً للبحث في كل الماكينات",
                        help="يمكنك إدخال أرقام مفصولة بفواصل، أو نطاق مثل 1-10"
                    )
                
                with col_card2:
                    card_exact = st.checkbox(
                        "مطابقة تامة",
                        value=st.session_state.search_params.get("exact_match", False),
                        key="card_exact_match"
                    )
                
                with col_card3:
                    if st.button("🗑 مسح", key="clear_cards"):
                        card_numbers = ""
                        st.rerun()
                
                st.session_state.search_params["card_numbers"] = card_numbers
                st.session_state.search_params["exact_match"] = card_exact
            else:
                st.info("ℹ️ لم يتم العثور على أعمدة أرقام ماكينات في البيانات")
        
        # محرك بحث التاريخ
        with search_tabs[1]:
            if detected_columns["date"]:
                st.markdown("#### 📅 محرك بحث التاريخ")
                st.caption(f"الأعمدة المكتشفة: {', '.join(detected_columns['date'])}")
                
                col_date1, col_date2 = st.columns([3, 1])
                
                with col_date1:
                    date_input = st.text_input(
                        "أدخل التاريخ (مثال: 2024, 1/2024, 20/5/2025):",
                        value=st.session_state.search_params.get("date_range", ""),
                        key="input_date_main",
                        placeholder="اتركه فارغاً للبحث في كل التواريخ",
                        help="يمكنك البحث بسنة أو شهر/سنة أو تاريخ كامل"
                    )
                
                with col_date2:
                    if st.button("🗑 مسح", key="clear_date"):
                        date_input = ""
                        st.rerun()
                
                st.session_state.search_params["date_range"] = date_input
            else:
                st.info("ℹ️ لم يتم العثور على أعمدة تاريخ في البيانات")
        
        # محرك بحث فني الخدمة
        with search_tabs[2]:
            if detected_columns["servised_by"]:
                st.markdown("#### 👨‍🔧 محرك بحث فني الخدمة")
                st.caption(f"الأعمدة المكتشفة: {', '.join(detected_columns['servised_by'])}")
                
                col_tech1, col_tech2 = st.columns([3, 1])
                
                with col_tech1:
                    tech_names = st.text_input(
                        "أدخل أسماء الفنيين (مثال: أحمد, محمد, علي):",
                        value=st.session_state.search_params.get("tech_names", ""),
                        key="input_techs_main",
                        placeholder="اتركه فارغاً للبحث عن كل الفنيين",
                        help="يمكنك إدخال أسماء مفصولة بفواصل"
                    )
                
                with col_tech2:
                    if st.button("🗑 مسح", key="clear_techs"):
                        tech_names = ""
                        st.rerun()
                
                st.session_state.search_params["tech_names"] = tech_names
            else:
                st.info("ℹ️ لم يتم العثور على أعمدة فنيين في البيانات")
        
        # محرك بحث النص
        with search_tabs[3]:
            st.markdown("#### 📝 محرك بحث النص (يبحث في الحدث والتصحيح)")
            
            col_text1, col_text2, col_text3 = st.columns([3, 1, 1])
            
            with col_text1:
                search_text = st.text_input(
                    "أدخل النص للبحث (مثال: صيانة, إصلاح, تغيير):",
                    value=st.session_state.search_params.get("search_text", ""),
                    key="input_text_main",
                    placeholder="اتركه فارغاً للبحث عن كل النصوص",
                    help="يبحث في أعمدة الحدث والتصحيح إذا وجدت"
                )
            
            with col_text2:
                text_exact = st.checkbox(
                    "مطابقة تامة",
                    value=st.session_state.search_params.get("exact_match", False),
                    key="text_exact_match"
                )
            
            with col_text3:
                if st.button("🗑 مسح", key="clear_text"):
                    search_text = ""
                    st.rerun()
            
            st.session_state.search_params["search_text"] = search_text
            st.session_state.search_params["exact_match"] = text_exact
        
        # محرك بحث اسم الشيت
        with search_tabs[4]:
            st.markdown("#### 📄 محرك بحث اسم/رقم الشيت")
            
            col_sheet1, col_sheet2, col_sheet3 = st.columns([3, 1, 1])
            
            with col_sheet1:
                sheet_name_search = st.text_input(
                    "أدخل اسم أو رقم الشيت (مثال: Card, 101, قسم الحلج):",
                    value=st.session_state.search_params.get("sheet_name_search", ""),
                    key="input_sheet_name_main",
                    placeholder="اتركه فارغاً للبحث في كل الشيتات",
                    help="يبحث في أسماء الشيتات فقط"
                )
            
            with col_sheet2:
                sheet_exact = st.checkbox(
                    "مطابقة تامة",
                    value=st.session_state.search_params.get("exact_match", False),
                    key="sheet_exact_match"
                )
            
            with col_sheet3:
                if st.button("🗑 مسح", key="clear_sheet"):
                    sheet_name_search = ""
                    st.rerun()
            
            st.session_state.search_params["sheet_name_search"] = sheet_name_search
            st.session_state.search_params["exact_match"] = sheet_exact
    
    st.markdown("---")
    
    # ===============================
    # خيارات متقدمة
    # ===============================
    with st.expander("⚙ خيارات متقدمة", expanded=False):
        col_adv1, col_adv2 = st.columns(2)
        
        with col_adv1:
            include_empty = st.checkbox(
                "🔍 تضمين الحقول الفارغة في النتائج",
                value=st.session_state.search_params.get("include_empty", True),
                key="include_empty_global",
                help="إذا لم يتم التحديد، سيتم استبعاد النتائج التي تحتوي على حقول فارغة"
            )
            
            st.session_state.search_params["include_empty"] = include_empty
        
        with col_adv2:
            calculate_duration = st.checkbox(
                "⏱️ حساب المدة بين الأحداث",
                value=st.session_state.search_params.get("calculate_duration", False) and (detected_columns["date"] and detected_columns["card"]),
                key="calculate_duration_global",
                disabled=not (detected_columns["date"] and detected_columns["card"]),
                help="حساب المدة بين الأحداث لنفس الماكينة (يتطلب وجود أعمدة تاريخ وأرقام ماكينات)"
            )
            
            if calculate_duration and (detected_columns["date"] and detected_columns["card"]):
                st.session_state.search_params["calculate_duration"] = True
                
                duration_type = st.selectbox(
                    "وحدة حساب المدة:",
                    ["أيام", "أسابيع", "أشهر"],
                    index=["أيام", "أسابيع", "أشهر"].index(
                        st.session_state.search_params.get("duration_type", "أيام")
                    ),
                    key="duration_type_global"
                )
                st.session_state.search_params["duration_type"] = duration_type
                
                col_dur_min, col_dur_max = st.columns(2)
                with col_dur_min:
                    duration_filter_min = st.number_input(
                        "الحد الأدنى للمدة:",
                        min_value=0,
                        value=st.session_state.search_params.get("duration_filter_min", 0),
                        step=1,
                        key="duration_min_global"
                    )
                    st.session_state.search_params["duration_filter_min"] = duration_filter_min
                
                with col_dur_max:
                    duration_filter_max = st.number_input(
                        "الحد الأقصى للمدة:",
                        min_value=duration_filter_min,
                        value=st.session_state.search_params.get("duration_filter_max", 365),
                        step=1,
                        key="duration_max_global"
                    )
                    st.session_state.search_params["duration_filter_max"] = duration_filter_max
                
                group_by_type = st.checkbox(
                    "📊 تجميع حسب نوع الحدث (حدث/تصحيح)",
                    value=st.session_state.search_params.get("group_by_type", False),
                    key="group_by_type_global"
                )
                st.session_state.search_params["group_by_type"] = group_by_type
            else:
                st.session_state.search_params["calculate_duration"] = False
        
        global_exact = st.checkbox(
            "🎯 تفعيل المطابقة التامة لجميع محركات البحث",
            value=st.session_state.search_params.get("exact_match", False),
            key="global_exact_match"
        )
        st.session_state.search_params["exact_match"] = global_exact
    
    st.markdown("---")
    
    # ===============================
    # أزرار التحكم الرئيسية
    # ===============================
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([2, 1, 1, 1])
    
    with col_btn1:
        search_clicked = st.button(
            "🔍 **بدء البحث المتقدم**",
            type="primary",
            use_container_width=True,
            key="main_search_btn_final"
        )
    
    with col_btn2:
        if st.button("🗑 **مسح الكل**", use_container_width=True, key="clear_all_final"):
            st.session_state.search_params = {
                "selected_category": "جميع الأقسام",
                "sheet_name_search": "",
                "card_numbers": "",
                "date_range": "",
                "tech_names": "",
                "search_text": "",
                "exact_match": False,
                "include_empty": True,
                "calculate_duration": False,
                "duration_type": "أيام",
                "duration_filter_min": 0,
                "duration_filter_max": 365,
                "group_by_type": False,
            }
            st.session_state.search_triggered = False
            st.rerun()
    
    with col_btn3:
        if st.button("📊 **عرض الكل**", use_container_width=True, key="show_all_final"):
            st.session_state.search_params = {
                "selected_category": "جميع الأقسام",
                "sheet_name_search": "",
                "card_numbers": "",
                "date_range": "",
                "tech_names": "",
                "search_text": "",
                "exact_match": False,
                "include_empty": True,
                "calculate_duration": False,
                "duration_type": "أيام",
                "duration_filter_min": 0,
                "duration_filter_max": 365,
                "group_by_type": False,
            }
            st.session_state.search_triggered = True
            st.rerun()
    
    with col_btn4:
        if st.button("🔄 **تحديث**", use_container_width=True, key="refresh_final"):
            st.rerun()
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        search_params = st.session_state.search_params.copy()
        
        show_search_params(search_params)
        
        show_search_results(search_params, all_sheets, detected_columns, category_stats)

def show_search_params(search_params):
    """عرض معايير البحث المستخدمة"""
    with st.container():
        st.markdown("### ⚙ معايير البحث المستخدمة")
        
        params_display = []
        
        if search_params.get("selected_category"):
            params_display.append(f"**🏭 القسم:** {search_params['selected_category']}")
        
        if search_params.get("sheet_name_search"):
            params_display.append(f"**📄 اسم الشيت:** {search_params['sheet_name_search']}")
        
        if search_params.get("card_numbers"):
            params_display.append(f"**🔢 رقم الماكينة:** {search_params['card_numbers']}")
        
        if search_params.get("date_range"):
            params_display.append(f"**📅 التاريخ:** {search_params['date_range']}")
        
        if search_params.get("tech_names"):
            params_display.append(f"**👨‍🔧 فني الخدمة:** {search_params['tech_names']}")
        
        if search_params.get("search_text"):
            params_display.append(f"**📝 نص البحث:** {search_params['search_text']}")
        
        if search_params.get("exact_match"):
            params_display.append("**🎯 مطابقة تامة**")
        
        if params_display:
            st.info(" | ".join(params_display))
        else:
            st.info("🔍 **بحث في كل البيانات (بدون معايير)**")

def filter_sheets_by_search(sheets_list, search_term):
    """تصفية الشيتات حسب مصطلح البحث"""
    if not search_term or not search_term.strip():
        return sheets_list
    
    search_terms = [term.strip().lower() for term in search_term.split(',') if term.strip()]
    filtered = []
    
    for sheet in sheets_list:
        sheet_lower = sheet.lower()
        for term in search_terms:
            if term in sheet_lower:
                filtered.append(sheet)
                break
    
    return filtered

def show_search_results(search_params, all_sheets, detected_columns, category_stats):
    """عرض نتائج البحث بشكل منظم مع مراعاة التصنيف"""
    st.markdown("### 📊 نتائج البحث")
    
    # تحديد الشيتات المطلوب البحث فيها بناءً على التصنيف
    selected_category = search_params.get("selected_category", "جميع الأقسام")
    
    if selected_category in category_stats:
        sheets_to_search = category_stats[selected_category]["sheets"]
    else:
        sheets_to_search = list(all_sheets.keys())
    
    # تطبيق البحث الإضافي في أسماء الشيتات (اختياري)
    sheet_name_search = search_params.get("sheet_name_search", "")
    if sheet_name_search:
        sheets_to_search = filter_sheets_by_search(sheets_to_search, sheet_name_search)
    
    st.info(f"🔍 جاري البحث في **{len(sheets_to_search)}** شيت من تصنيف **{selected_category}**")
    
    if not sheets_to_search:
        st.warning("⚠ لا توجد شيتات تطابق معايير البحث في التصنيف")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    all_results = []
    total_sheets = len(sheets_to_search)
    processed_sheets = 0
    
    for sheet_name in sheets_to_search:
        if sheet_name not in all_sheets:
            continue
            
        df = all_sheets[sheet_name]
        processed_sheets += 1
        if total_sheets > 0:
            progress_bar.progress(processed_sheets / total_sheets)
        
        status_text.text(f"🔍 جاري معالجة الشيت: {sheet_name}...")
        
        col_mapping = get_column_mapping(df)
        
        sheet_results = extract_sheet_data(df, sheet_name)
        
        for result in sheet_results:
            if check_row_criteria(result, search_params, col_mapping):
                all_results.append(result)
    
    progress_bar.empty()
    status_text.empty()
    
    if all_results:
        display_search_results(all_results, search_params, all_sheets, detected_columns)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 تأكد من صحة البيانات المدخلة وجرب مصطلحات بحث مختلفة")

def display_search_results(results, search_params, all_sheets, detected_columns):
    """عرض نتائج البحث في واجهة منظمة"""
    result_df = pd.DataFrame(results)
    
    if "Sheet Info" in result_df.columns:
        result_df["رقم الشيت"] = result_df["Sheet Info"].apply(
            lambda x: x.get("first_number") if isinstance(x, dict) and x.get("first_number") else "-"
        )
    
    first_sheet = list(all_sheets.keys())[0]
    col_mapping = get_column_mapping(all_sheets[first_sheet])
    
    main_columns = ["Sheet Name", "رقم الشيت"]
    display_names = {
        "Sheet Name": "اسم الشيت",
        "رقم الشيت": "رقم الشيت"
    }
    
    if detected_columns["card"]:
        for col in detected_columns["card"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "رقم الماكينة"
                break
    
    if detected_columns["date"]:
        for col in detected_columns["date"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "التاريخ"
                break
    
    if detected_columns["event"]:
        for col in detected_columns["event"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "الحدث"
                break
    
    if detected_columns["correction"]:
        for col in detected_columns["correction"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "التصحيح"
                break
    
    if detected_columns["servised_by"]:
        for col in detected_columns["servised_by"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "تم بواسطة"
                break
    
    if detected_columns["tones"]:
        for col in detected_columns["tones"]:
            if col in result_df.columns:
                main_columns.append(col)
                display_names[col] = "الأطنان"
                break
    
    other_columns = [col for col in result_df.columns if col not in main_columns and col not in ["Sheet Name", "Row Index", "Sheet Info", "رقم الشيت"]]
    
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(result_df))
    
    with col2:
        unique_sheets = result_df["Sheet Name"].nunique()
        st.metric("📂 عدد الشيتات", unique_sheets)
    
    with col3:
        if detected_columns["servised_by"]:
            tech_col = None
            for col in detected_columns["servised_by"]:
                if col in result_df.columns:
                    tech_col = col
                    break
            
            if tech_col:
                unique_techs = result_df[tech_col].nunique()
                st.metric("👨‍🔧 عدد الفنيين", unique_techs)
            else:
                st.metric("👨‍🔧 عدد الفنيين", 0)
        else:
            st.metric("👨‍🔧 عدد الفنيين", 0)
    
    with col4:
        if detected_columns["images"]:
            img_col = None
            for col in detected_columns["images"]:
                if col in result_df.columns:
                    img_col = col
                    break
            
            if img_col:
                with_images = result_df[img_col].notna() & (result_df[img_col] != "").sum()
                st.metric("📷 تحتوي على صور", with_images)
            else:
                st.metric("📷 تحتوي على صور", 0)
        else:
            st.metric("📷 تحتوي على صور", 0)
    
    st.markdown("---")
    st.markdown("### 📋 النتائج التفصيلية")
    
    display_tabs = st.tabs(["📊 عرض جدولي", "📋 عرض تفصيلي حسب الشيت"])
    
    with display_tabs[0]:
        all_display_columns = main_columns + other_columns
        
        selected_columns = st.multiselect(
            "اختر الأعمدة للعرض:",
            all_display_columns,
            default=main_columns[:min(6, len(main_columns))],
            key="select_columns_display"
        )
        
        if not selected_columns:
            selected_columns = main_columns[:min(6, len(main_columns))]
        
        display_df = result_df[selected_columns].copy()
        display_df.columns = [display_names.get(col, col) for col in selected_columns]
        
        st.dataframe(display_df, use_container_width=True, height=500)
        st.caption(f"إجمالي النتائج: {len(result_df)}")
    
    with display_tabs[1]:
        for sheet_name in result_df["Sheet Name"].unique():
            sheet_results = result_df[result_df["Sheet Name"] == sheet_name]
            
            with st.expander(f"📂 {sheet_name} - عدد الأحداث: {len(sheet_results)}"):
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("عدد الأحداث", len(sheet_results))
                with col_s2:
                    if detected_columns["servised_by"]:
                        tech_col = None
                        for col in detected_columns["servised_by"]:
                            if col in sheet_results.columns:
                                tech_col = col
                                break
                        
                        if tech_col:
                            tech_count = sheet_results[tech_col].nunique()
                            st.metric("فنيين مختلفين", tech_count)
                with col_s3:
                    if detected_columns["date"]:
                        date_col = None
                        for col in detected_columns["date"]:
                            if col in sheet_results.columns:
                                date_col = col
                                break
                        
                        if date_col:
                            date_count = sheet_results[date_col].notna().sum()
                            st.metric("تواريخ مسجلة", date_count)
                
                sheet_display = sheet_results[main_columns + other_columns].copy()
                if not sheet_display.empty:
                    st.dataframe(sheet_display, use_container_width=True)
    
    if search_params.get("calculate_duration", False):
        st.markdown("---")
        st.markdown("### ⏱️ تحليل المدة بين الأحداث")
        
        durations_data = calculate_durations_between_events(
            results,
            search_params.get("duration_type", "أيام"),
            search_params.get("group_by_type", False)
        )
        
        if durations_data:
            durations_df = pd.DataFrame(durations_data)
            
            duration_min = search_params.get("duration_filter_min", 0)
            duration_max = search_params.get("duration_filter_max", 365)
            
            filtered_durations = durations_df[
                (durations_df['Duration'] >= duration_min) & 
                (durations_df['Duration'] <= duration_max)
            ]
            
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
            
            st.markdown("#### 📋 جدول المدة بين الأحداث")
            
            display_columns = []
            for col in ['Card Number', 'Previous_Event_Date', 'Current_Event_Date', 'Duration', 'Duration_Unit', 'Event_Type', 'Technician']:
                if col in filtered_durations.columns:
                    display_columns.append(col)
            
            st.dataframe(
                filtered_durations[display_columns],
                use_container_width=True,
                height=400
            )
        else:
            st.info("ℹ️ لا توجد بيانات كافية لحساب المدة بين الأحداث (تحتاج إلى حدثين على الأقل لكل ماكينة)")
    
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        if not result_df.empty:
            buffer_excel = io.BytesIO()
            
            export_df = result_df.copy()
            if 'Row Index' in export_df.columns:
                export_df = export_df.drop(columns=['Row Index'])
            if 'Sheet Info' in export_df.columns:
                export_df = export_df.drop(columns=['Sheet Info'])
            
            export_df.to_excel(buffer_excel, index=False, engine="openpyxl")
            
            st.download_button(
                label="📊 حفظ كملف Excel",
                data=buffer_excel.getvalue(),
                file_name=f"نتائج_البحث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with export_col2:
        if not result_df.empty:
            buffer_csv = io.BytesIO()
            
            export_csv = result_df.copy()
            if 'Row Index' in export_csv.columns:
                export_csv = export_csv.drop(columns=['Row Index'])
            if 'Sheet Info' in export_csv.columns:
                export_csv = export_csv.drop(columns=['Sheet Info'])
            
            export_csv.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="📄 حفظ كملف CSV",
                data=buffer_csv.getvalue(),
                file_name=f"نتائج_البحث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

# ===============================
# 🖥 دوال العرض والتعديل الديناميكية
# ===============================
def display_dynamic_sheets(sheets_edit):
    """عرض جميع الشيتات بشكل ديناميكي"""
    st.subheader("📂 جميع الشيتات")
    
    if not sheets_edit:
        st.warning("⚠ لا توجد شيتات متاحة")
        return
    
    sheet_tabs = st.tabs(list(sheets_edit.keys()))
    
    for i, (sheet_name, df) in enumerate(sheets_edit.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📋 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            
            if st.checkbox(f"عرض جميع الأعمدة", key=f"show_all_{sheet_name}"):
                st.dataframe(df, use_container_width=True)
            else:
                display_cols = []
                for col in df.columns:
                    col_lower = str(col).lower()
                    if any(keyword in col_lower for keyword in ['card', 'date', 'event', 'correction', 'servised', 'serviced', 'images', 'صور', 'technician', 'فني']):
                        display_cols.append(col)
                
                if display_cols:
                    st.dataframe(df[display_cols], use_container_width=True)
                else:
                    st.dataframe(df.head(10), use_container_width=True)
            
            with st.expander("📊 إحصائيات الشيت", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("عدد الصفوف", len(df))
                with col2:
                    st.metric("عدد الأعمدة", len(df.columns))
                with col3:
                    non_empty = df.notna().sum().sum()
                    total_cells = len(df) * len(df.columns)
                    st.metric("خلايا غير فارغة", f"{non_empty}/{total_cells}")

def add_new_event_dynamic(sheets_edit):
    """إضافة إيفينت جديد في أي شيت مع أي أعمدة"""
    st.subheader("➕ إضافة حدث جديد")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet_dynamic")
    df = sheets_edit[sheet_name].copy()
    
    st.markdown(f"### 📝 إضافة حدث جديد في شيت: {sheet_name}")
    st.info(f"الأعمدة المتاحة: {', '.join(df.columns.tolist())}")
    
    form_data = create_dynamic_event_form(df, prefix=f"add_{sheet_name}")
    
    if st.button("💾 إضافة الحدث الجديد", key=f"add_dynamic_event_btn_{sheet_name}"):
        if not form_data:
            st.warning("⚠ لم يتم إدخال أي بيانات")
            return
        
        new_row = {}
        for col in df.columns:
            if col in form_data and form_data[col]:
                new_row[col] = form_data[col]
            else:
                new_row[col] = ""
        
        new_row_df = pd.DataFrame([new_row])
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new
        
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}"
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            st.rerun()

def edit_event_dynamic(sheets_edit):
    """تعديل حدث في أي شيت مع أي أعمدة"""
    st.subheader("✏ تعديل حدث")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_event_sheet_dynamic")
    df = sheets_edit[sheet_name].copy()
    
    st.markdown(f"### 📋 البيانات الحالية في شيت: {sheet_name}")
    
    display_df = df.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].astype(str).apply(lambda x: x[:50] + "..." if len(x) > 50 else x)
    
    st.dataframe(display_df.head(20), use_container_width=True)
    
    st.markdown("### 🔍 اختيار الصف للتعديل")
    
    search_col = st.selectbox("ابحث في عمود:", df.columns.tolist(), key="search_col_dynamic")
    search_value = st.text_input("قيمة البحث:", key="search_val_dynamic")
    
    if search_value:
        mask = df[search_col].astype(str).str.contains(search_value, case=False, na=False)
        matching_rows = df[mask]
        
        if not matching_rows.empty:
            st.success(f"✅ تم العثور على {len(matching_rows)} صف")
            
            matching_display = matching_rows.copy()
            for col in matching_display.columns:
                matching_display[col] = matching_display[col].astype(str).apply(lambda x: x[:50] + "..." if len(x) > 50 else x)
            
            st.dataframe(matching_display, use_container_width=True)
            
            row_indices = matching_rows.index.tolist()
            selected_idx = st.selectbox(
                "اختر رقم الصف للتعديل:",
                row_indices,
                format_func=lambda x: f"الصف {x}: {str(matching_rows.loc[x, search_col])[:50]}"
            )
            
            if st.button("تحميل بيانات الصف", key="load_dynamic_row"):
                st.session_state["editing_dynamic_row"] = selected_idx
                st.session_state["editing_dynamic_sheet"] = sheet_name
                st.session_state["editing_dynamic_data"] = df.loc[selected_idx].to_dict()
                st.rerun()
        else:
            st.warning("⚠ لا توجد نتائج مطابقة")
    
    if "editing_dynamic_row" in st.session_state and st.session_state.get("editing_dynamic_sheet") == sheet_name:
        row_idx = st.session_state["editing_dynamic_row"]
        original_data = st.session_state["editing_dynamic_data"]
        
        st.markdown(f"### ✏ تعديل الصف رقم {row_idx}")
        
        form_data = create_dynamic_event_form(df, prefix=f"edit_{sheet_name}_{row_idx}", default_values=original_data)
        
        col_edit1, col_edit2 = st.columns(2)
        
        with col_edit1:
            if st.button("💾 حفظ التعديلات", key=f"save_dynamic_edit_{row_idx}", type="primary"):
                for col in df.columns:
                    if col in form_data:
                        df.at[row_idx, col] = form_data[col]
                
                sheets_edit[sheet_name] = df
                
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل حدث في {sheet_name} - الصف {row_idx}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.success("✅ تم حفظ التعديلات بنجاح!")
                    
                    del st.session_state["editing_dynamic_row"]
                    del st.session_state["editing_dynamic_sheet"]
                    del st.session_state["editing_dynamic_data"]
                    st.rerun()
        
        with col_edit2:
            if st.button("↩️ إلغاء", key=f"cancel_dynamic_edit_{row_idx}"):
                del st.session_state["editing_dynamic_row"]
                del st.session_state["editing_dynamic_sheet"]
                del st.session_state["editing_dynamic_data"]
                st.rerun()

# ===============================
# 🖥 دالة إدارة الشيتات والأقسام - المعدلة
# ===============================
def manage_sheets_and_columns(sheets_edit):
    """إدارة الشيتات والأقسام مع أقسام مستقلة"""
    st.subheader("🗂 إدارة الشيتات والأعمدة")
    
    if not sheets_edit:
        st.warning("⚠ لا توجد بيانات متاحة")
        return sheets_edit
    
    categories = load_categories()
    
    manage_tabs = st.tabs(["➕ إنشاء شيت جديد", "✏ إدارة أعمدة شيت", "🗑 حذف شيت", "🏭 إدارة الأقسام", "📋 إدارة الشيتات في الأقسام"])
    
    with manage_tabs[0]:
        st.markdown("### ➕ إنشاء شيت جديد")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏭 معلومات القسم")
            
            category_option = st.radio(
                "خيارات القسم:",
                ["اختيار من الأقسام الموجودة", "إضافة قسم جديد"],
                key="category_option"
            )
            
            if category_option == "اختيار من الأقسام الموجودة":
                available_categories = [cat for cat in categories.keys() if cat != "جميع الأقسام"]
                
                if available_categories:
                    selected_category = st.selectbox(
                        "اختر القسم:",
                        available_categories,
                        key="existing_category"
                    )
                else:
                    st.info("ℹ️ لا توجد أقسام بعد. اختر 'إضافة قسم جديد'")
                    selected_category = None
            else:
                st.markdown("##### إضافة قسم جديد")
                new_category = st.text_input(
                    "اسم القسم الجديد:",
                    placeholder="مثال: سحب أول",
                    key="new_category"
                )
                
                if new_category:
                    if new_category not in categories:
                        add_category(new_category)
                        categories = load_categories()
                        st.success(f"✅ تم إضافة قسم '{new_category}'")
                    selected_category = new_category
                else:
                    selected_category = None
        
        with col2:
            st.markdown("#### 📋 معلومات الشيت")
            
            new_sheet_name = st.text_input(
                "اسم الشيت الجديد:", 
                placeholder="مثال: سحب1", 
                key="new_sheet_name",
                help="أدخل اسم الشيت كما سيظهر في الملف"
            )
            
            st.markdown("##### 📋 نموذج الأعمدة")
            column_template = st.selectbox(
                "اختر نموذج الأعمدة:",
                ["استخدام الأعمدة الافتراضية", "نسخ أعمدة من شيت موجود", "تحديد أعمدة مخصصة"],
                key="column_template"
            )
            
            if column_template == "نسخ أعمدة من شيت موجود":
                source_sheet = st.selectbox(
                    "اختر الشيت لنسخ أعمدة منه:",
                    list(sheets_edit.keys()),
                    key="source_sheet_for_columns"
                )
            elif column_template == "تحديد أعمدة مخصصة":
                custom_columns = st.text_area(
                    "أدخل أسماء الأعمدة (مفصولة بفواصل):",
                    placeholder="مثال: card, Date, Event, Correction, Servised by",
                    key="custom_columns"
                )
            
            initial_rows = st.number_input("عدد الصفوف الأولية:", min_value=0, max_value=100, value=0, step=1, key="initial_rows")
        
        if selected_category and new_sheet_name:
            st.markdown("---")
            st.markdown("#### 📋 ملخص الشيت الجديد")
            col_sum1, col_sum2 = st.columns(2)
            with col_sum1:
                st.info(f"**القسم:** {selected_category}")
            with col_sum2:
                st.info(f"**اسم الشيت:** {new_sheet_name}")
            
            if st.button("🚀 إنشاء الشيت الجديد", key="create_new_sheet_btn", type="primary"):
                if new_sheet_name in sheets_edit:
                    st.warning(f"⚠ الشيت '{new_sheet_name}' موجود بالفعل!")
                    return sheets_edit
                
                columns_to_use = APP_CONFIG["DEFAULT_COLUMNS"]
                
                if column_template == "نسخ أعمدة من شيت موجود" and source_sheet in sheets_edit:
                    columns_to_use = list(sheets_edit[source_sheet].columns)
                
                elif column_template == "تحديد أعمدة مخصصة" and custom_columns.strip():
                    columns_to_use = [col.strip() for col in custom_columns.split(',') if col.strip()]
                
                new_df = pd.DataFrame(columns=columns_to_use)
                sheets_edit[new_sheet_name] = new_df
                
                if initial_rows > 0:
                    empty_data = {col: [""] * initial_rows for col in columns_to_use}
                    sheets_edit[new_sheet_name] = pd.DataFrame(empty_data)
                
                add_sheet_to_category(selected_category, new_sheet_name)
                
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"إنشاء شيت جديد '{new_sheet_name}' في قسم {selected_category}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' في قسم '{selected_category}' بنجاح!")
                    st.rerun()
        else:
            st.warning("⚠ الرجاء اختيار قسم وإدخال اسم للشيت")
    
    with manage_tabs[1]:
        st.markdown("### ✏ إدارة أعمدة شيت")
        
        selected_sheet = st.selectbox(
            "اختر الشيت:",
            list(sheets_edit.keys()),
            key="selected_sheet_for_columns"
        )
        
        if selected_sheet:
            df = sheets_edit[selected_sheet]
            columns = list(df.columns)
            
            st.markdown(f"**الأعمدة الحالية في '{selected_sheet}':**")
            st.info(f"عدد الأعمدة: {len(columns)}")
            
            columns_df = pd.DataFrame({
                "الرقم": range(1, len(columns) + 1),
                "اسم العمود": columns,
                "نوع البيانات": [str(df[col].dtype) for col in columns]
            })
            
            st.dataframe(columns_df, use_container_width=True)
            
            column_ops_tabs = st.tabs(["إعادة تسمية عمود", "إضافة عمود", "حذف عمود"])
            
            with column_ops_tabs[0]:
                st.markdown("#### إعادة تسمية عمود")
                
                col_rename1, col_rename2 = st.columns(2)
                
                with col_rename1:
                    old_column_name = st.selectbox(
                        "اختر العمود لإعادة التسمية:",
                        columns,
                        key="old_column_name"
                    )
                
                with col_rename2:
                    new_column_name = st.text_input(
                        "الاسم الجديد للعمود:",
                        value=old_column_name if 'old_column_name' in locals() else "",
                        key="new_column_name_input"
                    )
                
                if st.button("✏️ إعادة تسمية", key="rename_column_btn"):
                    if old_column_name and new_column_name and old_column_name != new_column_name:
                        df.rename(columns={old_column_name: new_column_name}, inplace=True)
                        sheets_edit[selected_sheet] = df
                        
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إعادة تسمية عمود في شيت '{selected_sheet}'"
                        )
                        
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success(f"✅ تم إعادة تسمية العمود")
                            st.rerun()
                    else:
                        st.warning("⚠ الرجاء اختيار عمود وإدخال اسم جديد مختلف")
            
            with column_ops_tabs[1]:
                st.markdown("#### إضافة عمود جديد")
                
                new_column_name_add = st.text_input("اسم العمود الجديد:", key="new_column_to_add")
                default_value_add = st.text_input("القيمة الافتراضية (اختياري):", key="default_value_for_new_column")
                
                if st.button("➕ إضافة العمود", key="add_new_column_btn"):
                    if new_column_name_add:
                        if new_column_name_add not in df.columns:
                            df[new_column_name_add] = default_value_add if default_value_add else ""
                            sheets_edit[selected_sheet] = df
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"إضافة عمود جديد إلى شيت '{selected_sheet}'"
                            )
                            
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success(f"✅ تم إضافة العمود")
                                st.rerun()
                        else:
                            st.warning(f"⚠ العمود موجود بالفعل!")
                    else:
                        st.warning("⚠ الرجاء إدخال اسم للعمود الجديد")
            
            with column_ops_tabs[2]:
                st.markdown("#### حذف عمود")
                
                column_to_delete = st.selectbox(
                    "اختر العمود للحذف:",
                    columns,
                    key="column_to_delete"
                )
                
                if st.button("🗑 حذف العمود", key="delete_column_btn", type="secondary"):
                    if column_to_delete:
                        confirm = st.checkbox(f"هل أنت متأكد من حذف العمود؟")
                        
                        if confirm:
                            df.drop(columns=[column_to_delete], inplace=True)
                            sheets_edit[selected_sheet] = df
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"حذف عمود من شيت '{selected_sheet}'"
                            )
                            
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success(f"✅ تم حذف العمود")
                                st.rerun()
    
    with manage_tabs[2]:
        st.markdown("### 🗑 حذف شيت")
        
        sheet_to_delete = st.selectbox(
            "اختر الشيت للحذف:",
            list(sheets_edit.keys()),
            key="sheet_to_delete"
        )
        
        if sheet_to_delete:
            st.warning(f"⚠ تحذير: سيتم حذف الشيت بشكل دائم!")
            
            if sheet_to_delete in sheets_edit:
                df_to_delete = sheets_edit[sheet_to_delete]
                st.info(f"الشيت يحتوي على: {len(df_to_delete)} صف و {len(df_to_delete.columns)} عمود")
            
            categories_with_sheet = []
            for cat_name, cat_patterns in categories.items():
                if sheet_to_delete in cat_patterns:
                    categories_with_sheet.append(cat_name)
            
            if categories_with_sheet:
                st.info(f"هذا الشيت موجود في الأقسام: {', '.join(categories_with_sheet)}")
            
            confirm_delete = st.checkbox(f"أنا أدرك أن حذف الشيت لا يمكن التراجع عنه", key="confirm_sheet_delete")
            
            if st.button("🗑️ حذف الشيت نهائياً", key="delete_sheet_btn", disabled=not confirm_delete, type="secondary"):
                if confirm_delete:
                    for cat_name in categories_with_sheet:
                        remove_sheet_from_category(cat_name, sheet_to_delete)
                    
                    del sheets_edit[sheet_to_delete]
                    
                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"حذف شيت '{sheet_to_delete}'"
                    )
                    
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.success(f"✅ تم حذف الشيت بنجاح!")
                        st.rerun()
    
    with manage_tabs[3]:
        st.markdown("### 🏭 إدارة الأقسام")
        
        st.markdown("#### الأقسام الحالية:")
        
        if categories:
            categories_data = []
            for cat_name, cat_patterns in categories.items():
                matched_sheets = get_sheets_in_category(cat_name, sheets_edit)
                categories_data.append({
                    "القسم": cat_name,
                    "الشيتات المضافة": ", ".join(cat_patterns) if cat_patterns else "لا يوجد",
                    "عدد الشيتات المطابقة": len(matched_sheets)
                })
            
            categories_df = pd.DataFrame(categories_data)
            st.dataframe(categories_df, use_container_width=True)
            
            with st.expander("➕ إضافة قسم جديد", expanded=False):
                new_category_name = st.text_input("اسم القسم الجديد:", key="new_category_name_manage")
                
                if st.button("إضافة قسم", key="add_category_btn"):
                    if new_category_name:
                        if new_category_name not in categories:
                            add_category(new_category_name)
                            st.success(f"✅ تم إضافة القسم '{new_category_name}' بنجاح!")
                            st.rerun()
                        else:
                            st.warning(f"⚠ القسم '{new_category_name}' موجود بالفعل!")
                    else:
                        st.warning("⚠ الرجاء إدخال اسم للقسم الجديد")
            
            with st.expander("🗑️ حذف قسم", expanded=False):
                categories_to_delete = [cat for cat in categories.keys() if cat != "جميع الأقسام"]
                
                if categories_to_delete:
                    category_to_delete = st.selectbox(
                        "اختر القسم للحذف:",
                        categories_to_delete,
                        key="category_to_delete"
                    )
                    
                    if category_to_delete:
                        st.warning(f"⚠ سيتم حذف قسم '{category_to_delete}' بشكل دائم!")
                        
                        patterns_in_cat = categories[category_to_delete]
                        if patterns_in_cat:
                            st.info(f"الشيتات في هذا القسم: {', '.join(patterns_in_cat[:10])}")
                        
                        confirm_delete_cat = st.checkbox("أنا متأكد من حذف هذا القسم", key="confirm_category_delete")
                        
                        if st.button("🗑️ حذف القسم", key="delete_category_btn", disabled=not confirm_delete_cat):
                            if delete_category(category_to_delete):
                                st.success(f"✅ تم حذف القسم '{category_to_delete}' بنجاح!")
                                st.rerun()
                            else:
                                st.error("❌ لا يمكن حذف القسم الافتراضي")
                else:
                    st.info("ℹ️ لا توجد أقسام للحذف غير القسم الافتراضي")
        else:
            st.info("ℹ️ لا توجد أقسام بعد")
    
    with manage_tabs[4]:
        st.markdown("### 📋 إدارة الشيتات في الأقسام")
        st.markdown("هنا يمكنك إضافة أو إزالة الشيتات من الأقسام يدوياً")
        
        col_manage1, col_manage2 = st.columns(2)
        
        with col_manage1:
            st.markdown("#### إضافة شيت إلى قسم")
            
            available_categories = [cat for cat in categories.keys() if cat != "جميع الأقسام"]
            
            if available_categories:
                target_category = st.selectbox(
                    "اختر القسم:",
                    available_categories,
                    key="target_category_add"
                )
                
                all_sheets_list = list(sheets_edit.keys())
                sheets_in_category = categories.get(target_category, [])
                available_sheets = [s for s in all_sheets_list if s not in sheets_in_category]
                
                if available_sheets:
                    sheet_to_add = st.selectbox(
                        "اختر الشيت للإضافة:",
                        available_sheets,
                        key="sheet_to_add"
                    )
                    
                    if st.button("➕ إضافة الشيت إلى القسم", key="add_sheet_to_cat_btn"):
                        if add_sheet_to_category(target_category, sheet_to_add):
                            st.success(f"✅ تم إضافة '{sheet_to_add}' إلى قسم '{target_category}'")
                            st.rerun()
                        else:
                            st.error("❌ فشلت الإضافة")
                else:
                    st.info(f"ℹ️ كل الشيتات موجودة بالفعل في قسم '{target_category}'")
            else:
                st.info("ℹ️ لا توجد أقسام لإضافة شيتات إليها")
        
        with col_manage2:
            st.markdown("#### إزالة شيت من قسم")
            
            available_categories_remove = [cat for cat in categories.keys() if cat != "جميع الأقسام"]
            
            if available_categories_remove:
                source_category = st.selectbox(
                    "اختر القسم:",
                    available_categories_remove,
                    key="source_category_remove"
                )
                
                sheets_in_source = categories.get(source_category, [])
                
                if sheets_in_source:
                    sheet_to_remove = st.selectbox(
                        "اختر الشيت للإزالة:",
                        sheets_in_source,
                        key="sheet_to_remove"
                    )
                    
                    if st.button("🗑️ إزالة الشيت من القسم", key="remove_sheet_from_cat_btn"):
                        if remove_sheet_from_category(source_category, sheet_to_remove):
                            st.success(f"✅ تم إزالة '{sheet_to_remove}' من قسم '{source_category}'")
                            st.rerun()
                        else:
                            st.error("❌ فشلت الإزالة")
                else:
                    st.info(f"ℹ️ لا توجد شيتات في قسم '{source_category}'")
            else:
                st.info("ℹ️ لا توجد أقسام لإزالة شيتات منها")
    
    return sheets_edit

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
    
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )
    
    has_changes = not edited_df.equals(df)
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل يدوي في شيت {sheet_name}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success(f"✅ تم حفظ التغييرات بنجاح!")
                    
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info(f"↩️ تم التراجع عن التغييرات")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
            st.session_state.unsaved_changes[sheet_name] = False
        
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

setup_images_folder()

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
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    
    st.markdown("---")
    st.markdown("**📷 إدارة الصور:**")
    if os.path.exists(IMAGES_FOLDER):
        image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
        st.caption(f"عدد الصور: {len(image_files)}")
    
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

if all_sheets:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 الشيتات المتاحة")
    
    sheet_list = list(all_sheets.keys())
    selected_sheet_info = st.sidebar.selectbox("عرض معلومات شيت:", sheet_list)
    
    if selected_sheet_info in all_sheets:
        df_info = all_sheets[selected_sheet_info]
        st.sidebar.info(f"**{selected_sheet_info}:** {len(df_info)} صف × {len(df_info.columns)} عمود")
        
        if st.sidebar.checkbox("عرض عينة من البيانات"):
            st.sidebar.dataframe(df_info.head(3), use_container_width=True)

if permissions["can_manage_users"]:
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
elif permissions["can_edit"]:
    tabs = st.tabs(["📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"])
else:
    tabs = st.tabs(["📋 فحص الإيفينت والكوريكشن"])

with tabs[0]:
    st.header("📋 فحص الإيفينت والكوريكشن - بحث متعدد المحركات")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        check_events_and_corrections(all_sheets)

if permissions["can_edit"] and len(tabs) > 1:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")

        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            display_dynamic_sheets(sheets_edit)
            
            tab_names = [
                "عرض وتعديل شيت",
                "➕ إضافة حدث جديد",
                "✏ تعديل حدث",
                "🗂 إدارة الشيتات والأقسام",
                "📷 إدارة الصور"
            ]
            
            tabs_edit = st.tabs(tab_names)

            with tabs_edit[0]:
                sheets_edit = edit_sheet_with_save_button(sheets_edit)

            with tabs_edit[1]:
                add_new_event_dynamic(sheets_edit)

            with tabs_edit[2]:
                edit_event_dynamic(sheets_edit)
            
            with tabs_edit[3]:
                sheets_edit = manage_sheets_and_columns(sheets_edit)
            
            with tabs_edit[4]:
                st.subheader("📷 إدارة الصور المخزنة")
                
                if os.path.exists(IMAGES_FOLDER):
                    image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
                    
                    if image_files:
                        st.info(f"عدد الصور المخزنة: {len(image_files)}")
                        
                        search_term = st.text_input("🔍 بحث عن صور:", placeholder="ابحث باسم الصورة")
                        
                        filtered_images = image_files
                        if search_term:
                            filtered_images = [img for img in image_files if search_term.lower() in img.lower()]
                            st.caption(f"تم العثور على {len(filtered_images)} صورة")
                        
                        images_per_page = 9
                        if "image_page" not in st.session_state:
                            st.session_state.image_page = 0
                        
                        total_pages = (len(filtered_images) + images_per_page - 1) // images_per_page
                        
                        if filtered_images:
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
                                                st.image(img_path, caption=img_file, use_container_width=True)
                                                
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

if permissions["can_manage_users"] and len(tabs) > 2:
    with tabs[2]:
        st.header("📊 تحليلات متقدمة")
        
        if all_sheets is None:
            st.warning("❗ الملف المحلي غير موجود.")
        else:
            st.markdown("### 📈 تحليلات شاملة")
            
            total_sheets = len(all_sheets)
            total_rows = sum(len(df) for df in all_sheets.values())
            total_columns = sum(len(df.columns) for df in all_sheets.values())
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("📂 عدد الشيتات", total_sheets)
            with col_stat2:
                st.metric("📊 عدد الصفوف", total_rows)
            with col_stat3:
                st.metric("📋 عدد الأعمدة", total_columns)
            
            st.markdown("### 📊 تحليل الشيتات")
            
            sheets_analysis = []
            for sheet_name, df in all_sheets.items():
                non_empty = df.notna().sum().sum()
                total_cells = len(df) * len(df.columns)
                fill_rate = (non_empty / total_cells * 100) if total_cells > 0 else 0
                
                col_mapping = get_column_mapping(df)
                
                sheet_info = get_sheet_info(sheet_name)
                
                sheets_analysis.append({
                    "اسم الشيت": sheet_name,
                    "الرقم": sheet_info["first_number"] if sheet_info["first_number"] else "-",
                    "عدد الصفوف": len(df),
                    "عدد الأعمدة": len(df.columns),
                    "معدل التعبئة %": round(fill_rate, 2),
                    "رقم الماكينة": "✅" if col_mapping["card"] else "❌",
                    "التاريخ": "✅" if col_mapping["date"] else "❌",
                    "الحدث": "✅" if col_mapping["event"] else "❌",
                    "التصحيح": "✅" if col_mapping["correction"] else "❌",
                    "فني": "✅" if col_mapping["servised_by"] else "❌"
                })
            
            analysis_df = pd.DataFrame(sheets_analysis)
            st.dataframe(analysis_df, use_container_width=True)
            
            st.markdown("### 🏭 تحليل الأقسام")
            
            category_stats = get_category_stats(all_sheets)
            cat_analysis = []
            for cat_name, cat_stat in category_stats.items():
                if cat_name != "جميع الأقسام":
                    cat_analysis.append({
                        "القسم": cat_name,
                        "عدد الشيتات": cat_stat["count"],
                        "نسبة من الإجمالي": f"{cat_stat['count']/total_sheets*100:.1f}%" if total_sheets > 0 else "0%",
                        "الشيتات": ", ".join(cat_stat["sheets"][:5]) + ("..." if len(cat_stat["sheets"]) > 5 else "")
                    })
            
            if cat_analysis:
                cat_df = pd.DataFrame(cat_analysis)
                st.dataframe(cat_df, use_container_width=True)
