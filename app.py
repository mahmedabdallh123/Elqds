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
    "FILE_PATH": "l9.xlsx",
    "LOCAL_FILE": "l9.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    
    # إعدادات الصور
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    
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
# 🔧 دوال إنشاء شيت جديد في ملف Excel على GitHub
# ===============================
def create_new_sheet_in_excel(sheets_edit, new_sheet_name, template_columns=None):
    """إنشاء شيت جديد في ملف Excel"""
    if template_columns is None:
        # أعمدة افتراضية للشيت الجديد
        template_columns = ["Date", "Event", "Correction", "Servised by", "Tones", "Images", "Notes"]
    
    new_df = pd.DataFrame(columns=template_columns)
    sheets_edit[new_sheet_name] = new_df
    return sheets_edit

def add_new_sheet_to_github(sheets_edit):
    """وظيفة إضافة شيت جديد إلى ملف Excel على GitHub"""
    st.subheader("➕ إضافة شيت جديد إلى ملف Excel")
    
    st.markdown("### 📝 إنشاء شيت جديد")
    st.info("يمكنك إنشاء شيت جديد وإضافته إلى ملف Excel الموجود على GitHub")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_sheet_name = st.text_input("اسم الشيت الجديد:", key="new_sheet_name", placeholder="مثال: Sheet6 أو بيانات_2025")
        
        if new_sheet_name:
            # التحقق من وجود الشيت مسبقاً
            if new_sheet_name in sheets_edit:
                st.warning(f"⚠ الشيت '{new_sheet_name}' موجود بالفعل في الملف!")
    
    with col2:
        default_columns = st.text_area(
            "الأعمدة الافتراضية (كل عمود في سطر جديد):",
            value="Date\nEvent\nCorrection\nServised by\nTones\nImages\nNotes",
            key="new_sheet_columns",
            height=150,
            help="أدخل اسم كل عمود في سطر منفصل"
        )
    
    st.markdown("---")
    st.markdown("### 📋 معاينة الشيت الجديد")
    
    # معاينة الأعمدة التي سيتم إنشاؤها
    columns_list = [col.strip() for col in default_columns.split("\n") if col.strip()]
    if not columns_list:
        columns_list = ["Date", "Event", "Correction", "Servised by", "Tones", "Images", "Notes"]
    
    preview_df = pd.DataFrame(columns=columns_list)
    st.dataframe(preview_df, use_container_width=True)
    st.caption(f"عدد الأعمدة: {len(columns_list)} | سيتم إنشاء شيت فارغ بهذه الأعمدة")
    
    st.markdown("---")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        if st.button("✅ إنشاء وإضافة الشيت الجديد", key="create_sheet_btn", type="primary", use_container_width=True):
            if not new_sheet_name:
                st.error("❌ الرجاء إدخال اسم الشيت الجديد")
                return sheets_edit
            
            if new_sheet_name in sheets_edit:
                st.error(f"❌ الشيت '{new_sheet_name}' موجود بالفعل في الملف!")
                return sheets_edit
            
            # إنشاء الشيت الجديد
            sheets_edit = create_new_sheet_in_excel(sheets_edit, new_sheet_name, columns_list)
            
            # حفظ التغييرات ورفعها إلى GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"إنشاء شيت جديد: {new_sheet_name}"
            )
            
            if new_sheets is not None:
                st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' بنجاح ورفعه إلى GitHub!")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ فشل إنشاء الشيت أو رفعه إلى GitHub")
    
    return sheets_edit

# ===============================
# 🖥 دالة عرض البيانات
# ===============================
def display_data_simple(all_sheets):
    """عرض البيانات بشكل بسيط (جميع الشيتات)"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    st.subheader("📋 عرض البيانات (جميع الشيتات)")
    
    sheet_tabs = st.tabs(list(all_sheets.keys()))
    
    for i, (sheet_name, df) in enumerate(all_sheets.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📄 {sheet_name}")
            st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
            
            display_df = df.copy()
            for col in display_df.columns:
                if display_df[col].dtype == 'object':
                    display_df[col] = display_df[col].astype(str).apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
            
            st.dataframe(display_df, use_container_width=True, height=400)

# ===============================
# 🖥 دالة تعديل البيانات
# ===============================
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

def manage_images():
    """إدارة الصور المخزنة"""
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

def manage_data_edit(sheets_edit):
    """إدارة البيانات (عرض وتعديل وإضافة)"""
    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        return sheets_edit
    
    # عرض جميع الشيتات
    st.subheader("📂 جميع الشيتات")
    
    if not sheets_edit:
        st.warning("⚠ لا توجد شيتات متاحة")
        return sheets_edit
    
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
    
    # تبويبات التعديل
    tab_names = [
        "✏ تعديل بيانات شيت",
        "➕ إضافة شيت جديد",
        "📷 إدارة الصور"
    ]
    
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        sheets_edit = edit_sheet_with_save_button(sheets_edit)
    
    with tabs_edit[1]:
        sheets_edit = add_new_sheet_to_github(sheets_edit)
    
    with tabs_edit[2]:
        manage_images()
    
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية
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
can_edit = (user_role == "admin" or user_role == "editor" or "edit" in user_permissions or "all" in user_permissions)

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

# تبويبات التطبيق
tabs_list = ["📋 عرض البيانات"]

if can_edit:
    tabs_list.append("🛠 تعديل وإدارة البيانات")

tabs = st.tabs(tabs_list)

# تبويب عرض البيانات
with tabs[0]:
    st.header("📋 عرض البيانات")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        display_data_simple(all_sheets)

# تبويب تعديل البيانات
if can_edit and len(tabs) > 1:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")
        sheets_edit = manage_data_edit(sheets_edit)
