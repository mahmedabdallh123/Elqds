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
    
    # إعدادات الأعمدة الافتراضية للشيت الجديد (مع إضافة عمود المعدة)
    "DEFAULT_SHEET_COLUMNS": ["Date", "Equipment", "Event", "Correction", "Servised by", "Tones", "Images", "Notes"],
    
    # أسماء الأعمدة المتوقعة (للبحث الديناميكي)
    "EXPECTED_COLUMNS": {
        "equipment": ["equipment", "machine", "معدة", "ماكينة", "جهاز", "Equipment", "Machine", "القطعة", "المعدة", "المحرك"],
        "date": ["date", "تاريخ", "time", "وقت", "Date", "DATE", "التاريخ", "التوقيت"],
        "event": ["event", "حدث", "issue", "مشكلة", "Event", "الحدث", "المشكلة", "Issue"],
        "correction": ["correction", "تصحيح", "solution", "حل", "Correction", "التصحيح", "الحل", "Solution"],
        "servised_by": ["servised", "serviced", "service", "technician", "فني", "تم بواسطة", "Servised by", "Serviced by", "Technician"],
        "tones": ["tones", "طن", "أطنان", "ton", "tone", "Tones", "TON", "الطن", "الوزن", "الإنتاج"],
        "images": ["images", "pictures", "صور", "مرفقات", "Images", "الصور", "المرفقات"]
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
EQUIPMENT_CONFIG_FILE = "equipment_config.json"

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# -------------------------------
# 🧩 دوال إدارة تكوينات المعدات لكل شيت
# -------------------------------
def load_equipment_config():
    """تحميل تكوينات المعدات لكل شيت"""
    if not os.path.exists(EQUIPMENT_CONFIG_FILE):
        default_config = {}
        with open(EQUIPMENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    
    try:
        with open(EQUIPMENT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_equipment_config(config):
    """حفظ تكوينات المعدات لكل شيت"""
    try:
        with open(EQUIPMENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ تكوين المعدات: {e}")
        return False

def get_sheet_equipment(sheet_name, config):
    """الحصول على قائمة المعدات لشيت معين"""
    if sheet_name in config:
        return config[sheet_name].get("equipment_list", [])
    return []

def add_equipment_to_sheet(sheet_name, equipment_name, config):
    """إضافة معدة جديدة لشيت معين"""
    if sheet_name not in config:
        config[sheet_name] = {"equipment_list": [], "created_at": datetime.now().isoformat()}
    
    if equipment_name in config[sheet_name]["equipment_list"]:
        return False, f"المعدة '{equipment_name}' موجودة بالفعل في هذا الشيت"
    
    config[sheet_name]["equipment_list"].append(equipment_name)
    save_equipment_config(config)
    return True, f"تم إضافة المعدة '{equipment_name}' بنجاح"

def remove_equipment_from_sheet(sheet_name, equipment_name, config):
    """حذف معدة من شيت معين"""
    if sheet_name not in config:
        return False, "الشيت غير موجود في التكوين"
    
    if equipment_name not in config[sheet_name]["equipment_list"]:
        return False, "المعدة غير موجودة في هذا الشيت"
    
    config[sheet_name]["equipment_list"].remove(equipment_name)
    save_equipment_config(config)
    return True, f"تم حذف المعدة '{equipment_name}' بنجاح"

def update_equipment_in_sheet(sheet_name, old_name, new_name, config):
    """تحديث اسم معدة في شيت معين"""
    if sheet_name not in config:
        return False, "الشيت غير موجود في التكوين"
    
    if old_name not in config[sheet_name]["equipment_list"]:
        return False, "المعدة غير موجودة"
    
    idx = config[sheet_name]["equipment_list"].index(old_name)
    config[sheet_name]["equipment_list"][idx] = new_name
    save_equipment_config(config)
    return True, f"تم تحديث اسم المعدة بنجاح"

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
# 🔧 دوال إنشاء وإدارة الشيتات مع فهرس المعدات
# ===============================
def create_new_sheet_in_excel(sheets_edit, new_sheet_name, template_columns=None):
    """إنشاء شيت جديد في ملف Excel مع أعمدة تشمل Equipment"""
    if template_columns is None:
        template_columns = APP_CONFIG["DEFAULT_SHEET_COLUMNS"]
    
    new_df = pd.DataFrame(columns=template_columns)
    sheets_edit[new_sheet_name] = new_df
    return sheets_edit

def add_new_event_with_equipment(sheets_edit, sheet_name, equipment_list):
    """إضافة حدث جديد مع اختيار المعدة من القائمة"""
    st.markdown(f"### 📝 إضافة حدث جديد في شيت: {sheet_name}")
    
    if not equipment_list:
        st.warning("⚠ لا توجد معدات مضافة في هذا الشيت. يرجى إضافة معدات أولاً من قسم 'إدارة المعدات'")
        return sheets_edit
    
    df = sheets_edit[sheet_name].copy()
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_equipment = st.selectbox("🔧 اختر المعدة:", equipment_list, key=f"equipment_select_{sheet_name}")
        event_date = st.date_input("📅 التاريخ:", value=datetime.now(), key=f"date_{sheet_name}")
        event_desc = st.text_area("📝 الحدث/العطل:", height=100, key=f"event_{sheet_name}", placeholder="وصف العطل أو المشكلة...")
    
    with col2:
        correction_desc = st.text_area("🔧 التصحيح/الإجراء المتخذ:", height=100, key=f"correction_{sheet_name}", placeholder="ما الذي تم إصلاحه أو الإجراء الذي تم...")
        servised_by = st.text_input("👨‍🔧 تم بواسطة (الفني):", key=f"servised_{sheet_name}", placeholder="اسم الفني أو المشغل")
        tones = st.text_input("⚖️ الأطنان/الكمية:", key=f"tones_{sheet_name}", placeholder="مثال: 5.5 طن")
    
    st.markdown("#### 📷 الصور المرفقة")
    uploaded_files = st.file_uploader(
        "اختر الصور:",
        type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
        accept_multiple_files=True,
        key=f"images_{sheet_name}"
    )
    
    images_str = ""
    if uploaded_files:
        saved_images = save_uploaded_images(uploaded_files)
        if saved_images:
            images_str = ",".join(saved_images)
    
    notes = st.text_area("📝 ملاحظات إضافية:", key=f"notes_{sheet_name}", placeholder="أي ملاحظات إضافية...")
    
    if st.button("✅ إضافة الحدث", key=f"submit_event_{sheet_name}", type="primary"):
        new_row = {
            "Date": event_date.strftime("%Y-%m-%d"),
            "Equipment": selected_equipment,
            "Event": event_desc,
            "Correction": correction_desc,
            "Servised by": servised_by,
            "Tones": tones,
            "Images": images_str,
            "Notes": notes
        }
        
        for col in df.columns:
            if col not in new_row:
                new_row[col] = ""
        
        new_row_df = pd.DataFrame([new_row])
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        sheets_edit[sheet_name] = df_new
        
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name} - المعدة: {selected_equipment}"
        )
        
        if new_sheets is not None:
            st.success(f"✅ تم إضافة الحدث بنجاح للمعدة '{selected_equipment}'!")
            st.rerun()
    
    return sheets_edit

def manage_sheet_equipment(sheet_name, config):
    """إدارة قائمة المعدات لشيت معين"""
    st.markdown(f"### 🔧 إدارة المعدات في شيت: {sheet_name}")
    
    equipment_list = get_sheet_equipment(sheet_name, config)
    
    if equipment_list:
        st.markdown("#### 📋 المعدات الحالية:")
        for eq in equipment_list:
            st.markdown(f"- 🔹 {eq}")
    else:
        st.info("ℹ️ لا توجد معدات مضافة بعد. أضف معدات جديدة باستخدام النموذج أدناه.")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ➕ إضافة معدة جديدة")
        new_equipment = st.text_input("اسم المعدة:", key=f"new_eq_{sheet_name}", placeholder="مثال: محرك رئيسي 1, مضخة مياه, ضاغط هواء")
        
        if st.button("➕ إضافة", key=f"add_eq_{sheet_name}"):
            if new_equipment:
                success, msg = add_equipment_to_sheet(sheet_name, new_equipment, config)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("⚠ الرجاء إدخال اسم المعدة")
    
    with col2:
        st.markdown("#### 🗑️ حذف معدة")
        if equipment_list:
            eq_to_delete = st.selectbox("اختر المعدة للحذف:", equipment_list, key=f"del_eq_{sheet_name}")
            if st.button("🗑️ حذف", key=f"delete_eq_{sheet_name}"):
                success, msg = remove_equipment_from_sheet(sheet_name, eq_to_delete, config)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("ℹ️ لا توجد معدات لحذفها")
    
    if equipment_list:
        st.markdown("---")
        st.markdown("#### ✏️ تعديل اسم معدة")
        col_edit1, col_edit2 = st.columns(2)
        
        with col_edit1:
            eq_to_edit = st.selectbox("اختر المعدة للتعديل:", equipment_list, key=f"edit_eq_select_{sheet_name}")
        
        with col_edit2:
            new_eq_name = st.text_input("الاسم الجديد:", key=f"edit_eq_name_{sheet_name}")
        
        if st.button("💾 حفظ التعديل", key=f"save_eq_edit_{sheet_name}"):
            if new_eq_name:
                success, msg = update_equipment_in_sheet(sheet_name, eq_to_edit, new_eq_name, config)
                if success:
                    st.success(msg)
                    st.info("⚠ ملاحظة: سيتم تحديث اسم المعدة في السجلات المستقبلية فقط. السجلات السابقة ستبقى بالاسم القديم.")
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("⚠ الرجاء إدخال الاسم الجديد")

def display_sheet_data_with_filter(sheet_name, df, equipment_list):
    """عرض بيانات الشيت مع فلتر حسب المعدة"""
    st.markdown(f"### 📄 {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    if equipment_list and "Equipment" in df.columns:
        st.markdown("#### 🔍 فلتر حسب المعدة:")
        filter_col1, filter_col2 = st.columns([2, 1])
        
        with filter_col1:
            selected_filter = st.selectbox(
                "اختر المعدة:", 
                ["جميع المعدات"] + equipment_list,
                key=f"filter_{sheet_name}"
            )
        
        with filter_col2:
            if st.button("🔄 عرض الكل", key=f"reset_filter_{sheet_name}"):
                st.rerun()
        
        if selected_filter != "جميع المعدات":
            df = df[df["Equipment"] == selected_filter]
            st.info(f"🔍 عرض الأعطال للمعدة: {selected_filter} - عدد السجلات: {len(df)}")
    
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype == 'object':
            display_df[col] = display_df[col].astype(str).apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    if "Equipment" in df.columns and len(df) > 0:
        with st.expander("📊 إحصائيات الأعطال حسب المعدة", expanded=False):
            stats = df["Equipment"].value_counts().reset_index()
            stats.columns = ["المعدة", "عدد الأعطال"]
            st.dataframe(stats, use_container_width=True)

def search_across_sheets(all_sheets, equipment_config):
    """البحث في جميع الشيتات مع فلتر حسب المعدة"""
    st.subheader("🔍 بحث متقدم في جميع السجلات")
    
    if not all_sheets:
        st.warning("لا توجد بيانات للبحث")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔎 كلمة البحث:", placeholder="أدخل نصاً للبحث...")
    
    with col2:
        all_equipment = []
        for sheet_name in all_sheets.keys():
            all_equipment.extend(get_sheet_equipment(sheet_name, equipment_config))
        all_equipment = list(set(all_equipment))
        
        filter_equipment = st.selectbox(
            "🔧 فلتر حسب المعدة:",
            ["الكل"] + all_equipment,
            key="search_equipment_filter"
        )
    
    with col3:
        search_in_column = st.selectbox(
            "📋 البحث في عمود:",
            ["الكل", "Equipment", "Event", "Correction", "Notes"],
            key="search_column"
        )
    
    if st.button("🔍 بحث", key="search_button", type="primary"):
        results = []
        
        for sheet_name, df in all_sheets.items():
            df_filtered = df.copy()
            
            if filter_equipment != "الكل" and "Equipment" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["Equipment"] == filter_equipment]
            
            if search_term:
                if search_in_column == "الكل":
                    mask = pd.Series([False] * len(df_filtered))
                    for col in df_filtered.select_dtypes(include=['object']).columns:
                        mask = mask | df_filtered[col].astype(str).str.contains(search_term, case=False, na=False)
                    df_filtered = df_filtered[mask]
                else:
                    if search_in_column in df_filtered.columns:
                        df_filtered = df_filtered[df_filtered[search_in_column].astype(str).str.contains(search_term, case=False, na=False)]
            
            if not df_filtered.empty:
                df_filtered["المصدر"] = sheet_name
                results.append(df_filtered)
        
        if results:
            combined_results = pd.concat(results, ignore_index=True)
            st.success(f"✅ تم العثور على {len(combined_results)} نتيجة")
            
            display_results = combined_results.copy()
            for col in display_results.columns:
                if display_results[col].dtype == 'object':
                    display_results[col] = display_results[col].astype(str).apply(lambda x: x[:80] + "..." if len(x) > 80 else x)
            
            st.dataframe(display_results, use_container_width=True, height=500)
            
            csv = combined_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 تحميل النتائج كملف CSV",
                csv,
                f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning("⚠ لا توجد نتائج مطابقة للبحث")

def add_new_sheet_to_github(sheets_edit, equipment_config):
    """وظيفة إضافة شيت جديد إلى ملف Excel على GitHub مع إعدادات المعدات"""
    st.subheader("➕ إضافة شيت جديد إلى ملف Excel")
    
    st.markdown("### 📝 إنشاء شيت جديد")
    st.info("سيتم إنشاء شيت جديد يمثل قسماً أو محطة، ويمكنك لاحقاً إضافة المعدات الخاصة بهذا القسم")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_sheet_name = st.text_input("اسم الشيت الجديد:", key="new_sheet_name", placeholder="مثال: قسم الميكانيكا, محطة الكهرباء")
        
        if new_sheet_name:
            if new_sheet_name in sheets_edit:
                st.warning(f"⚠ الشيت '{new_sheet_name}' موجود بالفعل في الملف!")
    
    with col2:
        default_columns = st.text_area(
            "الأعمدة الافتراضية (كل عمود في سطر جديد):",
            value="\n".join(APP_CONFIG["DEFAULT_SHEET_COLUMNS"]),
            key="new_sheet_columns",
            height=150,
            help="تأكد من وجود عمود 'Equipment' لتتمكن من إضافة المعدات"
        )
    
    st.markdown("---")
    st.markdown("### 📋 معاينة الشيت الجديد")
    
    columns_list = [col.strip() for col in default_columns.split("\n") if col.strip()]
    if "Equipment" not in columns_list:
        st.warning("⚠ تأكد من وجود عمود 'Equipment' في الأعمدة لتتمكن من ربط المعدات بالأعطال")
    
    preview_df = pd.DataFrame(columns=columns_list)
    st.dataframe(preview_df, use_container_width=True)
    st.caption(f"عدد الأعمدة: {len(columns_list)}")
    
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
            
            sheets_edit = create_new_sheet_in_excel(sheets_edit, new_sheet_name, columns_list)
            
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"إنشاء شيت جديد: {new_sheet_name}"
            )
            
            if new_sheets is not None:
                if new_sheet_name not in equipment_config:
                    equipment_config[new_sheet_name] = {"equipment_list": [], "created_at": datetime.now().isoformat()}
                    save_equipment_config(equipment_config)
                
                st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' بنجاح ورفعه إلى GitHub!")
                st.info(f"ℹ️ يمكنك الآن إضافة المعدات لهذا القسم من قسم 'إدارة المعدات'")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ فشل إنشاء الشيت أو رفعه إلى GitHub")
    
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

def manage_data_edit(sheets_edit, equipment_config):
    """إدارة البيانات (عرض وتعديل وإضافة) مع نظام المعدات"""
    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        return sheets_edit
    
    tab_names = [
        "📋 عرض وإدارة البيانات",
        "➕ إضافة حدث جديد",
        "🔧 إدارة المعدات",
        "➕ إضافة شيت جديد",
        "📷 إدارة الصور"
    ]
    
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        st.subheader("📋 جميع الشيتات")
        
        if not sheets_edit:
            st.warning("⚠ لا توجد شيتات متاحة")
        else:
            sheet_tabs = st.tabs(list(sheets_edit.keys()))
            
            for i, (sheet_name, df) in enumerate(sheets_edit.items()):
                with sheet_tabs[i]:
                    equipment_list = get_sheet_equipment(sheet_name, equipment_config)
                    display_sheet_data_with_filter(sheet_name, df, equipment_list)
                    
                    with st.expander("✏️ تعديل البيانات المباشر", expanded=False):
                        st.warning("⚠ كن حذراً عند التعديل المباشر للبيانات")
                        edited_df = st.data_editor(
                            df.astype(str),
                            num_rows="dynamic",
                            use_container_width=True,
                            key=f"editor_{sheet_name}"
                        )
                        
                        if st.button(f"💾 حفظ التغييرات في {sheet_name}", key=f"save_edit_{sheet_name}"):
                            sheets_edit[sheet_name] = edited_df.astype(object)
                            new_sheets = auto_save_to_github(sheets_edit, f"تعديل بيانات في {sheet_name}")
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success("✅ تم حفظ التغييرات!")
                                st.rerun()
    
    with tabs_edit[1]:
        if not sheets_edit:
            st.warning("⚠ لا توجد شيتات متاحة")
        else:
            sheet_name = st.selectbox("اختر الشيت (القسم/المحطة):", list(sheets_edit.keys()), key="add_event_sheet")
            equipment_list = get_sheet_equipment(sheet_name, equipment_config)
            
            if not equipment_list:
                st.warning(f"⚠ لا توجد معدات مضافة في شيت '{sheet_name}'. يرجى إضافة معدات أولاً من تبويب 'إدارة المعدات'")
            else:
                sheets_edit = add_new_event_with_equipment(sheets_edit, sheet_name, equipment_list)
    
    with tabs_edit[2]:
        if not sheets_edit:
            st.warning("⚠ لا توجد شيتات متاحة")
        else:
            sheet_name = st.selectbox("اختر الشيت (القسم/المحطة):", list(sheets_edit.keys()), key="manage_eq_sheet")
            manage_sheet_equipment(sheet_name, equipment_config)
    
    with tabs_edit[3]:
        sheets_edit = add_new_sheet_to_github(sheets_edit, equipment_config)
    
    with tabs_edit[4]:
        manage_images()
    
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

setup_images_folder()
equipment_config = load_equipment_config()

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
        
        equipment_count = len(get_sheet_equipment(selected_sheet_info, equipment_config))
        st.sidebar.caption(f"🔧 عدد المعدات في هذا القسم: {equipment_count}")
        
        if st.sidebar.checkbox("عرض عينة من البيانات"):
            st.sidebar.dataframe(df_info.head(3), use_container_width=True)

tabs_list = ["📋 عرض البيانات", "🔍 بحث متقدم"]

if can_edit:
    tabs_list.append("🛠 تعديل وإدارة البيانات")

tabs = st.tabs(tabs_list)

with tabs[0]:
    st.header("📋 عرض البيانات حسب الأقسام")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        sheet_tabs = st.tabs(list(all_sheets.keys()))
        for i, (sheet_name, df) in enumerate(all_sheets.items()):
            with sheet_tabs[i]:
                equipment_list = get_sheet_equipment(sheet_name, equipment_config)
                display_sheet_data_with_filter(sheet_name, df, equipment_list)

with tabs[1]:
    st.header("🔍 بحث متقدم في جميع السجلات")
    search_across_sheets(all_sheets, equipment_config)

if can_edit and len(tabs) > 2:
    with tabs[2]:
        st.header("🛠 تعديل وإدارة البيانات")
        sheets_edit = manage_data_edit(sheets_edit, equipment_config)
