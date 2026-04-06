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
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["📋 عرض البيانات", "🛠 تعديل وإدارة البيانات"],
    
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

# ملف الهيكل التنظيمي (الأقسام والماكينات والشيتات)
STRUCTURE_FILE = "structure.json"

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

# ===============================
# 🧩 دوال إدارة الهيكل التنظيمي
# ===============================
def load_structure():
    """تحميل هيكل الأقسام والماكينات والشيتات"""
    if not os.path.exists(STRUCTURE_FILE):
        # هيكل افتراضي
        default_structure = {
            "departments": {
                "الميكانيكا": {
                    "machines": {
                        "ماكينة 1": {
                            "sheets": ["Sheet1", "Sheet2"],
                            "created_at": datetime.now().isoformat()
                        },
                        "ماكينة 2": {
                            "sheets": ["Sheet3"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                },
                "الكهرباء": {
                    "machines": {
                        "محول 1": {
                            "sheets": ["Sheet4"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                },
                "الإنتاج": {
                    "machines": {
                        "خط إنتاج 1": {
                            "sheets": ["Sheet5"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(default_structure, f, indent=4, ensure_ascii=False)
        return default_structure
    
    try:
        with open(STRUCTURE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"departments": {}}

def save_structure(structure):
    """حفظ هيكل الأقسام والماكينات والشيتات"""
    try:
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ الهيكل: {e}")
        return False

def add_department(structure, dept_name):
    """إضافة قسم جديد"""
    if dept_name in structure["departments"]:
        return False, "القسم موجود بالفعل"
    
    structure["departments"][dept_name] = {
        "machines": {},
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة القسم {dept_name} بنجاح"

def delete_department(structure, dept_name):
    """حذف قسم (مع جميع ماكيناته وشيتاته)"""
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    
    del structure["departments"][dept_name]
    save_structure(structure)
    return True, f"تم حذف القسم {dept_name} بنجاح"

def add_machine(structure, dept_name, machine_name):
    """إضافة ماكينة جديدة في قسم معين"""
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    
    if machine_name in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة موجودة بالفعل في هذا القسم"
    
    structure["departments"][dept_name]["machines"][machine_name] = {
        "sheets": [],
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة الماكينة {machine_name} في قسم {dept_name}"

def delete_machine(structure, dept_name, machine_name):
    """حذف ماكينة"""
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    del structure["departments"][dept_name]["machines"][machine_name]
    save_structure(structure)
    return True, f"تم حذف الماكينة {machine_name} بنجاح"

def add_sheet_to_machine(structure, dept_name, machine_name, sheet_name, all_sheets=None):
    """إضافة شيت جديد لماكينة معينة"""
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    if sheet_name in structure["departments"][dept_name]["machines"][machine_name]["sheets"]:
        return False, "الشيت موجود بالفعل في هذه الماكينة"
    
    structure["departments"][dept_name]["machines"][machine_name]["sheets"].append(sheet_name)
    save_structure(structure)
    return True, f"تم إضافة الشيت {sheet_name} إلى الماكينة {machine_name}"

def delete_sheet_from_machine(structure, dept_name, machine_name, sheet_name):
    """حذف شيت من ماكينة"""
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    if sheet_name not in structure["departments"][dept_name]["machines"][machine_name]["sheets"]:
        return False, "الشيت غير موجود في هذه الماكينة"
    
    structure["departments"][dept_name]["machines"][machine_name]["sheets"].remove(sheet_name)
    save_structure(structure)
    return True, f"تم حذف الشيت {sheet_name} من الماكينة {machine_name}"

def create_new_sheet_in_excel(sheets_edit, new_sheet_name, template_columns=None):
    """إنشاء شيت جديد في ملف Excel"""
    if template_columns is None:
        # أعمدة افتراضية للشيت الجديد
        template_columns = ["Date", "Event", "Correction", "Servised by", "Tones", "Images", "Notes"]
    
    new_df = pd.DataFrame(columns=template_columns)
    sheets_edit[new_sheet_name] = new_df
    return sheets_edit

def get_machine_sheets(structure, dept_name, machine_name):
    """الحصول على قائمة شيتات ماكينة معينة"""
    if dept_name in structure["departments"] and machine_name in structure["departments"][dept_name]["machines"]:
        return structure["departments"][dept_name]["machines"][machine_name]["sheets"]
    return []

def get_all_machines(structure):
    """الحصول على جميع الماكينات مع أقسامها"""
    machines = []
    for dept_name, dept_data in structure["departments"].items():
        for machine_name in dept_data["machines"].keys():
            machines.append({
                "department": dept_name,
                "machine": machine_name,
                "sheets": dept_data["machines"][machine_name]["sheets"]
            })
    return machines

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
            "can_manage_sheets": True,
            "can_manage_structure": True
        }
    
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False,
            "can_manage_sheets": True,
            "can_manage_structure": False
        }
    
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions,
            "can_manage_sheets": "manage_sheets" in user_permissions or "all" in user_permissions,
            "can_manage_structure": "manage_structure" in user_permissions or "all" in user_permissions
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

# ===============================
# 🖥 دالة عرض البيانات (بدون فحص)
# ===============================
def display_data_organized(all_sheets, structure):
    """عرض البيانات بشكل منظم حسب الأقسام والماكينات"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    st.subheader("📋 عرض البيانات (حسب الأقسام والماكينات)")
    
    if not structure["departments"]:
        st.info("ℹ️ لا توجد أقسام. قم بإضافة أقسام وماكينات أولاً.")
        return
    
    # إنشاء تبويبات للأقسام
    dept_tabs = st.tabs(list(structure["departments"].keys()))
    
    for i, (dept_name, dept_data) in enumerate(structure["departments"].items()):
        with dept_tabs[i]:
            st.markdown(f"## 🏭 قسم: {dept_name}")
            
            if not dept_data["machines"]:
                st.info(f"ℹ️ لا توجد ماكينات في قسم {dept_name}")
                continue
            
            # إنشاء تبويبات للماكينات داخل القسم
            machine_tabs = st.tabs(list(dept_data["machines"].keys()))
            
            for j, (machine_name, machine_data) in enumerate(dept_data["machines"].items()):
                with machine_tabs[j]:
                    st.markdown(f"### 🔧 ماكينة: {machine_name}")
                    
                    sheets_list = machine_data["sheets"]
                    
                    if not sheets_list:
                        st.info(f"ℹ️ لا توجد شيتات مرتبطة بهذه الماكينة")
                        continue
                    
                    # عرض الشيتات الخاصة بالماكينة
                    for sheet_name in sheets_list:
                        if sheet_name in all_sheets:
                            df = all_sheets[sheet_name]
                            
                            with st.expander(f"📄 {sheet_name} - ({len(df)} صف)", expanded=False):
                                st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
                                
                                display_df = df.copy()
                                for col in display_df.columns:
                                    if display_df[col].dtype == 'object':
                                        display_df[col] = display_df[col].astype(str).apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
                                
                                st.dataframe(display_df, use_container_width=True, height=300)
                        else:
                            st.warning(f"⚠ الشيت '{sheet_name}' غير موجود في ملف Excel")

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
# 🖥 دالة إدارة المستخدمين
# ===============================
def manage_users():
    """إدارة المستخدمين (للمشرفين فقط)"""
    st.subheader("👥 إدارة المستخدمين")
    
    users = load_users()
    
    st.markdown("### 📋 قائمة المستخدمين")
    
    users_list = []
    for username, user_data in users.items():
        users_list.append({
            "اسم المستخدم": username,
            "الدور": user_data.get("role", "viewer"),
            "الصلاحيات": ", ".join(user_data.get("permissions", ["view"])),
            "تاريخ الإنشاء": user_data.get("created_at", "").split("T")[0] if "T" in user_data.get("created_at", "") else user_data.get("created_at", ""),
            "نشط": "✅" if user_data.get("active", False) else "❌"
        })
    
    users_df = pd.DataFrame(users_list)
    st.dataframe(users_df, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### ➕ إضافة مستخدم جديد")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_username = st.text_input("اسم المستخدم:", key="new_username")
        new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
    
    with col2:
        new_role = st.selectbox("الدور:", ["viewer", "editor", "admin"], key="new_role")
        new_permissions = st.multiselect(
            "الصلاحيات (لغير الأدمن):",
            ["view", "edit", "manage_sheets", "tech_support", "manage_users", "manage_structure"],
            default=["view"],
            key="new_permissions"
        )
    
    if st.button("➕ إضافة مستخدم", key="add_user_btn"):
        if new_username and new_password:
            if new_username in users:
                st.warning(f"⚠ المستخدم '{new_username}' موجود بالفعل")
            else:
                user_data = {
                    "password": new_password,
                    "role": new_role,
                    "created_at": datetime.now().isoformat(),
                    "permissions": ["all"] if new_role == "admin" else new_permissions,
                    "active": False
                }
                if add_user_to_github(new_username, user_data):
                    st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح")
                    st.rerun()
                else:
                    st.error("❌ فشل إضافة المستخدم")
        else:
            st.warning("⚠ الرجاء إدخال اسم المستخدم وكلمة المرور")
    
    st.markdown("---")
    st.markdown("### 🗑️ حذف مستخدم")
    
    users_to_delete = [u for u in users.keys() if u != "admin"]
    
    if users_to_delete:
        user_to_delete = st.selectbox("اختر المستخدم للحذف:", users_to_delete, key="user_to_delete")
        
        if st.button("🗑️ حذف المستخدم", key="delete_user_btn"):
            if delete_user_from_github(user_to_delete):
                st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح")
                st.rerun()
            else:
                st.error("❌ فشل حذف المستخدم")
    else:
        st.info("ℹ️ لا توجد مستخدمين للحذف غير المشرف")

# ===============================
# 🖥 دالة إدارة الهيكل التنظيمي (الأقسام والماكينات والشيتات)
# ===============================
def manage_structure(sheets_edit):
    """إدارة الأقسام والماكينات والشيتات"""
    st.subheader("🏗️ إدارة الهيكل التنظيمي (الأقسام - الماكينات - الشيتات)")
    
    structure = load_structure()
    
    # تبويبات منفصلة للإدارة
    tab1, tab2, tab3, tab4 = st.tabs(["🏭 إدارة الأقسام", "🔧 إدارة الماكينات", "📄 إدارة الشيتات", "📊 عرض الهيكل"])
    
    # ==================== تبويب إدارة الأقسام ====================
    with tab1:
        st.markdown("### 🏭 إدارة الأقسام")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ إضافة قسم جديد")
            new_dept = st.text_input("اسم القسم:", key="new_dept")
            if st.button("➕ إضافة قسم", key="add_dept_btn"):
                if new_dept:
                    success, msg = add_department(structure, new_dept)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("⚠ الرجاء إدخال اسم القسم")
        
        with col2:
            st.markdown("#### 🗑️ حذف قسم")
            depts_list = list(structure["departments"].keys())
            if depts_list:
                dept_to_delete = st.selectbox("اختر القسم للحذف:", depts_list, key="dept_to_delete")
                if st.button("🗑️ حذف القسم", key="delete_dept_btn"):
                    success, msg = delete_department(structure, dept_to_delete)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("ℹ️ لا توجد أقسام للحذف")
        
        # عرض الأقسام الحالية
        st.markdown("#### 📋 الأقسام الحالية")
        if structure["departments"]:
            depts_data = []
            for dept_name, dept_data in structure["departments"].items():
                depts_data.append({
                    "القسم": dept_name,
                    "عدد الماكينات": len(dept_data["machines"]),
                    "تاريخ الإنشاء": dept_data.get("created_at", "").split("T")[0] if "T" in dept_data.get("created_at", "") else dept_data.get("created_at", "")
                })
            st.dataframe(pd.DataFrame(depts_data), use_container_width=True)
        else:
            st.info("ℹ️ لا توجد أقسام حالياً")
    
    # ==================== تبويب إدارة الماكينات ====================
    with tab2:
        st.markdown("### 🔧 إدارة الماكينات")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ إضافة ماكينة جديدة")
            depts_list = list(structure["departments"].keys())
            if depts_list:
                selected_dept = st.selectbox("اختر القسم:", depts_list, key="machine_dept")
                new_machine = st.text_input("اسم الماكينة:", key="new_machine")
                if st.button("➕ إضافة ماكينة", key="add_machine_btn"):
                    if new_machine:
                        success, msg = add_machine(structure, selected_dept, new_machine)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("⚠ الرجاء إدخال اسم الماكينة")
            else:
                st.warning("⚠ الرجاء إضافة قسم أولاً")
        
        with col2:
            st.markdown("#### 🗑️ حذف ماكينة")
            if depts_list:
                dept_for_delete = st.selectbox("اختر القسم:", depts_list, key="delete_machine_dept")
                machines_list = list(structure["departments"].get(dept_for_delete, {}).get("machines", {}).keys())
                if machines_list:
                    machine_to_delete = st.selectbox("اختر الماكينة للحذف:", machines_list, key="machine_to_delete")
                    if st.button("🗑️ حذف الماكينة", key="delete_machine_btn"):
                        success, msg = delete_machine(structure, dept_for_delete, machine_to_delete)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("ℹ️ لا توجد ماكينات في هذا القسم")
            else:
                st.info("ℹ️ لا توجد أقسام")
        
        # عرض الماكينات الحالية
        st.markdown("#### 📋 الماكينات الحالية")
        if structure["departments"]:
            machines_data = []
            for dept_name, dept_data in structure["departments"].items():
                for machine_name, machine_data in dept_data["machines"].items():
                    machines_data.append({
                        "القسم": dept_name,
                        "الماكينة": machine_name,
                        "عدد الشيتات": len(machine_data["sheets"]),
                        "تاريخ الإنشاء": machine_data.get("created_at", "").split("T")[0] if "T" in machine_data.get("created_at", "") else machine_data.get("created_at", "")
                    })
            if machines_data:
                st.dataframe(pd.DataFrame(machines_data), use_container_width=True)
            else:
                st.info("ℹ️ لا توجد ماكينات حالياً")
        else:
            st.info("ℹ️ لا توجد أقسام")
    
    # ==================== تبويب إدارة الشيتات ====================
    with tab3:
        st.markdown("### 📄 إدارة الشيتات")
        
        # التأكد من وجود sheets_edit
        if sheets_edit is None:
            st.warning("⚠ لا يمكن تحميل ملف Excel. تأكد من وجود الملف.")
        else:
            all_sheet_names = list(sheets_edit.keys())
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🔗 ربط شيت موجود بماكينة")
                if depts_list:
                    selected_dept_link = st.selectbox("اختر القسم:", depts_list, key="link_sheet_dept")
                    machines_list_link = list(structure["departments"].get(selected_dept_link, {}).get("machines", {}).keys())
                    
                    if machines_list_link:
                        selected_machine_link = st.selectbox("اختر الماكينة:", machines_list_link, key="link_sheet_machine")
                        
                        if all_sheet_names:
                            selected_sheet = st.selectbox("اختر الشيت للربط:", all_sheet_names, key="sheet_to_link")
                            
                            current_sheets = get_machine_sheets(structure, selected_dept_link, selected_machine_link)
                            if selected_sheet in current_sheets:
                                st.info(f"ℹ️ الشيت '{selected_sheet}' مرتبط بالفعل بهذه الماكينة")
                            else:
                                if st.button("🔗 ربط الشيت", key="link_sheet_btn"):
                                    success, msg = add_sheet_to_machine(structure, selected_dept_link, selected_machine_link, selected_sheet)
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                        else:
                            st.warning("⚠ لا توجد شيتات في ملف Excel")
                    else:
                        st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept_link}")
                else:
                    st.warning("⚠ الرجاء إضافة قسم أولاً")
            
            with col2:
                st.markdown("#### 🗑️ إلغاء ربط شيت من ماكينة")
                if depts_list:
                    selected_dept_unlink = st.selectbox("اختر القسم:", depts_list, key="unlink_sheet_dept")
                    machines_list_unlink = list(structure["departments"].get(selected_dept_unlink, {}).get("machines", {}).keys())
                    
                    if machines_list_unlink:
                        selected_machine_unlink = st.selectbox("اختر الماكينة:", machines_list_unlink, key="unlink_sheet_machine")
                        
                        current_sheets = get_machine_sheets(structure, selected_dept_unlink, selected_machine_unlink)
                        if current_sheets:
                            sheet_to_unlink = st.selectbox("اختر الشيت لإلغاء الربط:", current_sheets, key="sheet_to_unlink")
                            if st.button("🗑️ إلغاء الربط", key="unlink_sheet_btn"):
                                success, msg = delete_sheet_from_machine(structure, selected_dept_unlink, selected_machine_unlink, sheet_to_unlink)
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        else:
                            st.info("ℹ️ لا توجد شيتات مرتبطة بهذه الماكينة")
                    else:
                        st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept_unlink}")
                else:
                    st.warning("⚠ الرجاء إضافة قسم أولاً")
            
            st.markdown("---")
            st.markdown("#### ➕ إنشاء شيت جديد")
            
            col_create1, col_create2 = st.columns(2)
            
            with col_create1:
                new_sheet_name = st.text_input("اسم الشيت الجديد:", key="new_sheet_name")
            
            with col_create2:
                default_columns = st.text_area(
                    "الأعمدة الافتراضية (كل عمود في سطر جديد):",
                    value="Date\nEvent\nCorrection\nServised by\nTones\nImages\nNotes",
                    key="new_sheet_columns",
                    height=150
                )
            
            if st.button("➕ إنشاء شيت جديد", key="create_sheet_btn"):
                if new_sheet_name:
                    if new_sheet_name in sheets_edit:
                        st.warning(f"⚠ الشيت '{new_sheet_name}' موجود بالفعل")
                    else:
                        columns_list = [col.strip() for col in default_columns.split("\n") if col.strip()]
                        if not columns_list:
                            columns_list = ["Date", "Event", "Correction", "Servised by", "Tones", "Images", "Notes"]
                        
                        sheets_edit = create_new_sheet_in_excel(sheets_edit, new_sheet_name, columns_list)
                        
                        # حفظ التغييرات
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إنشاء شيت جديد: {new_sheet_name}"
                        )
                        
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' بنجاح")
                            st.rerun()
                        else:
                            st.error("❌ فشل إنشاء الشيت")
                else:
                    st.warning("⚠ الرجاء إدخال اسم الشيت")
    
    # ==================== تبويب عرض الهيكل ====================
    with tab4:
        st.markdown("### 📊 عرض الهيكل التنظيمي")
        
        if structure["departments"]:
            for dept_name, dept_data in structure["departments"].items():
                with st.expander(f"🏭 {dept_name}", expanded=True):
                    if dept_data["machines"]:
                        for machine_name, machine_data in dept_data["machines"].items():
                            st.markdown(f"**🔧 {machine_name}**")
                            if machine_data["sheets"]:
                                for sheet_name in machine_data["sheets"]:
                                    st.markdown(f"  - 📄 {sheet_name}")
                            else:
                                st.markdown(f"  - *لا توجد شيتات مرتبطة*")
                    else:
                        st.markdown("*لا توجد ماكينات*")
        else:
            st.info("ℹ️ لا توجد أقسام حالياً")
    
    return sheets_edit

# ===============================
# 🖥 دالة إدارة البيانات (بدون أقسام وشيتات)
# ===============================
def manage_data_edit(sheets_edit):
    """إدارة البيانات (عرض وتعديل وإضافة) بدون إدارة أقسام وشيتات"""
    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        return sheets_edit
    
    display_dynamic_sheets(sheets_edit)
    
    tab_names = [
        "✏ تعديل بيانات شيت",
        "➕ إضافة حدث جديد",
        "✏ تعديل حدث",
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
        manage_images()
    
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
structure = load_structure()

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

# تحديد التبويبات بناءً على الصلاحيات
tabs_list = []

# تبويب عرض البيانات (بشكل منظم)
tabs_list.append("📋 عرض البيانات (منظم)")

# تبويب عرض البيانات (جميع الشيتات)
tabs_list.append("📋 عرض البيانات (جميع الشيتات)")

# تبويب تعديل البيانات
if permissions["can_edit"]:
    tabs_list.append("🛠 تعديل وإدارة البيانات")

# تبويب إدارة الهيكل التنظيمي
if permissions["can_manage_structure"]:
    tabs_list.append("🏗️ إدارة الأقسام والماكينات")

# تبويب إدارة المستخدمين
if permissions["can_manage_users"]:
    tabs_list.append("👥 إدارة المستخدمين")

tabs = st.tabs(tabs_list)

tab_index = 0

# تبويب عرض البيانات (منظم)
with tabs[tab_index]:
    st.header("📋 عرض البيانات حسب الأقسام والماكينات")
    display_data_organized(all_sheets, structure)
tab_index += 1

# تبويب عرض البيانات (جميع الشيتات)
with tabs[tab_index]:
    st.header("📋 عرض البيانات (جميع الشيتات)")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        display_data_simple(all_sheets)
tab_index += 1

# تبويب تعديل البيانات
if permissions["can_edit"] and tab_index < len(tabs):
    with tabs[tab_index]:
        st.header("🛠 تعديل وإدارة البيانات")
        sheets_edit = manage_data_edit(sheets_edit)
    tab_index += 1

# تبويب إدارة الهيكل التنظيمي
if permissions["can_manage_structure"] and tab_index < len(tabs):
    with tabs[tab_index]:
        st.header("🏗️ إدارة الأقسام والماكينات")
        sheets_edit = manage_structure(sheets_edit)
    tab_index += 1

# تبويب إدارة المستخدمين
if permissions["can_manage_users"] and tab_index < len(tabs):
    with tabs[tab_index]:
        st.header("👥 إدارة المستخدمين")
        manage_users()
    tab_index += 1import streamlit as st
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
# ⚙ إعدادات التطبيق
# ===============================
APP_CONFIG = {
    "APP_TITLE": "CMMS - نظام إدارة الصيانة الشامل",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "DEFAULT_COLUMNS": ["Date", "Part", "Event", "Correction", "Serviced_by", "Tones", "Images"],
}

# ملف الهيكل التنظيمي
STRUCTURE_FILE = "structure.json"

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ===============================
# 🧩 دوال إدارة الهيكل التنظيمي (مُحسنة)
# ===============================
def load_structure():
    """تحميل هيكل الأقسام والماكينات والأجزاء مع التوافق مع الإصدارات القديمة"""
    if not os.path.exists(STRUCTURE_FILE):
        default_structure = {
            "departments": {
                "الميكانيكا": {
                    "machines": {
                        "ماطور 1": {
                            "parts": ["محرك", "طرمبة زيت", "فلتر هواء", "شاحن تيربو", "مبرد"],
                            "sheets": ["ماطور 1"],
                            "created_at": datetime.now().isoformat()
                        },
                        "ضاغط 1": {
                            "parts": ["بساتم", "صمامات", "محرك كهربائي", "خزان هواء", "منظم ضغط"],
                            "sheets": ["ضاغط 1"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                },
                "الكهرباء": {
                    "machines": {
                        "محول 1": {
                            "parts": ["ملفات", "قلب حديدي", "عوازل", "مراوح تبريد", "نظام حماية"],
                            "sheets": ["محول 1"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(default_structure, f, indent=4, ensure_ascii=False)
        return default_structure
    
    try:
        with open(STRUCTURE_FILE, "r", encoding="utf-8") as f:
            structure = json.load(f)
        
        # تحديث الهيكل القديم ليشمل الحقول المطلوبة
        updated = False
        for dept_name, dept_data in structure.get("departments", {}).items():
            for machine_name, machine_data in dept_data.get("machines", {}).items():
                if "parts" not in machine_data:
                    machine_data["parts"] = ["جزء رئيسي", "جزء فرعي 1", "جزء فرعي 2"]
                    updated = True
                if "sheets" not in machine_data:
                    machine_data["sheets"] = []
                    updated = True
                if "created_at" not in machine_data:
                    machine_data["created_at"] = datetime.now().isoformat()
                    updated = True
        
        if updated:
            save_structure(structure)
        
        return structure
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الهيكل: {e}")
        return {"departments": {}}

def save_structure(structure):
    try:
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ الهيكل: {e}")
        return False

def add_department(structure, dept_name):
    if dept_name in structure["departments"]:
        return False, "القسم موجود بالفعل"
    structure["departments"][dept_name] = {
        "machines": {},
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة القسم {dept_name}"

def delete_department(structure, dept_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    del structure["departments"][dept_name]
    save_structure(structure)
    return True, f"تم حذف القسم {dept_name}"

def add_machine(structure, dept_name, machine_name, parts_list=None):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة موجودة بالفعل"
    
    if parts_list is None:
        parts_list = ["جزء رئيسي", "جزء فرعي 1", "جزء فرعي 2"]
    
    structure["departments"][dept_name]["machines"][machine_name] = {
        "parts": parts_list,
        "sheets": [],
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة الماكينة {machine_name}"

def delete_machine(structure, dept_name, machine_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    del structure["departments"][dept_name]["machines"][machine_name]
    save_structure(structure)
    return True, f"تم حذف الماكينة {machine_name}"

def add_part_to_machine(structure, dept_name, machine_name, part_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    # التأكد من وجود مفتاح parts
    if "parts" not in structure["departments"][dept_name]["machines"][machine_name]:
        structure["departments"][dept_name]["machines"][machine_name]["parts"] = []
    
    if part_name in structure["departments"][dept_name]["machines"][machine_name]["parts"]:
        return False, "الجزء موجود بالفعل"
    
    structure["departments"][dept_name]["machines"][machine_name]["parts"].append(part_name)
    save_structure(structure)
    return True, f"تم إضافة الجزء {part_name}"

def delete_part_from_machine(structure, dept_name, machine_name, part_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    # التأكد من وجود مفتاح parts
    if "parts" not in structure["departments"][dept_name]["machines"][machine_name]:
        return False, "لا توجد أجزاء مسجلة"
    
    if part_name not in structure["departments"][dept_name]["machines"][machine_name]["parts"]:
        return False, "الجزء غير موجود"
    
    structure["departments"][dept_name]["machines"][machine_name]["parts"].remove(part_name)
    save_structure(structure)
    return True, f"تم حذف الجزء {part_name}"

def add_sheet_to_machine(structure, dept_name, machine_name, sheet_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    # التأكد من وجود مفتاح sheets
    if "sheets" not in structure["departments"][dept_name]["machines"][machine_name]:
        structure["departments"][dept_name]["machines"][machine_name]["sheets"] = []
    
    if sheet_name in structure["departments"][dept_name]["machines"][machine_name]["sheets"]:
        return False, "الشيت موجود بالفعل"
    
    structure["departments"][dept_name]["machines"][machine_name]["sheets"].append(sheet_name)
    save_structure(structure)
    return True, f"تم إضافة الشيت {sheet_name}"

def delete_sheet_from_machine(structure, dept_name, machine_name, sheet_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    # التأكد من وجود مفتاح sheets
    if "sheets" not in structure["departments"][dept_name]["machines"][machine_name]:
        return False, "لا توجد شيتات مرتبطة"
    
    if sheet_name not in structure["departments"][dept_name]["machines"][machine_name]["sheets"]:
        return False, "الشيت غير موجود"
    
    structure["departments"][dept_name]["machines"][machine_name]["sheets"].remove(sheet_name)
    save_structure(structure)
    return True, f"تم حذف الشيت {sheet_name}"

def get_machine_parts(structure, dept_name, machine_name):
    """الحصول على قائمة أجزاء ماكينة معينة مع التحقق من وجودها"""
    if dept_name in structure["departments"]:
        if machine_name in structure["departments"][dept_name]["machines"]:
            machine_data = structure["departments"][dept_name]["machines"][machine_name]
            return machine_data.get("parts", [])
    return []

def get_machine_sheets(structure, dept_name, machine_name):
    """الحصول على قائمة شيتات ماكينة معينة مع التحقق من وجودها"""
    if dept_name in structure["departments"]:
        if machine_name in structure["departments"][dept_name]["machines"]:
            machine_data = structure["departments"][dept_name]["machines"][machine_name]
            return machine_data.get("sheets", [])
    return []

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def save_uploaded_images(uploaded_files):
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل {uploaded_file.name} - نوع غير مدعوم")
            continue
        
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل {uploaded_file.name} - حجم كبير جداً")
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
    try:
        file_path = os.path.join(IMAGES_FOLDER, image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        st.error(f"❌ خطأ في حذف الصورة: {e}")
    return False

def display_images(image_filenames, caption="الصور المرفقة"):
    if not image_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    
    for img in images:
        img = img.strip()
        img_path = os.path.join(IMAGES_FOLDER, img)
        if os.path.exists(img_path):
            try:
                st.image(img_path, caption=img, use_container_width=True)
            except:
                st.write(f"📷 {img}")

# -------------------------------
# 🧩 دوال المستخدمين والجلسات
# -------------------------------
def download_users_from_github():
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل المستخدمين: {e}")
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def upload_users_to_github(users_data):
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
            repo.update_file(path="users.json", message=f"تحديث المستخدمين", content=users_json, sha=contents.sha, branch="main")
            return True
        except:
            repo.create_file(path="users.json", message=f"إنشاء ملف المستخدمين", content=users_json, branch="main")
            return True
    except Exception as e:
        st.error(f"❌ خطأ في رفع المستخدمين: {e}")
        return False

def load_users():
    try:
        users_data = download_users_from_github()
        if "admin" not in users_data:
            users_data["admin"] = {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}
            upload_users_to_github(users_data)
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل المستخدمين: {e}")
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def add_user_to_github(username, user_data):
    try:
        users = load_users()
        if username in users:
            return False
        users[username] = user_data
        return upload_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في إضافة المستخدم: {e}")
        return False

def delete_user_from_github(username):
    try:
        users = load_users()
        if username in users and username != "admin":
            del users[username]
            return upload_users_to_github(users)
        return False
    except Exception as e:
        st.error(f"❌ خطأ في حذف المستخدم: {e}")
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
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
    st.caption(f"🔒 المستخدمون النشطون: {active_count} / {APP_CONFIG['MAX_ACTIVE_USERS']}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            current_users = load_users()
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input not in active_users or username_input == "admin":
                    if active_count >= APP_CONFIG['MAX_ACTIVE_USERS'] and username_input != "admin":
                        st.error("🚫 الحد الأقصى للمستخدمين المتصلين")
                        return False
                    
                    state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                    save_state(state)
                    
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.user_role = current_users[username_input].get("role", "viewer")
                    st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                    
                    st.success(f"✅ تم تسجيل الدخول: {username_input}")
                    st.rerun()
                else:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل")
            else:
                st.error("❌ كلمة المرور غير صحيحة")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول: {username} ({user_role})")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_users": True, "can_manage_structure": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_users": False, "can_manage_structure": False}
    else:
        return {"can_view": "view" in user_permissions, "can_edit": "edit" in user_permissions, "can_manage_users": False, "can_manage_structure": False}

# -------------------------------
# 🔄 دوال ملف Excel
# -------------------------------
def fetch_from_github_requests():
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

@st.cache_data(show_spinner=False)
def load_all_sheets():
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
        st.error(f"❌ خطأ في تحميل الشيتات: {e}")
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ في الحفظ المحلي: {e}")
        return None

    try:
        st.cache_data.clear()
    except:
        pass

    token = st.secrets.get("github", {}).get("token", None)
    if not token or not GITHUB_AVAILABLE:
        return load_sheets_for_edit()

    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
        except:
            repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
        return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات")
        return result
    return sheets_dict

# ===============================
# 🖥 دوال عرض وإدارة الأحداث (المطورة مع التحقق من الأخطاء)
# ===============================
def display_events_by_machine_and_part(all_sheets, structure):
    """عرض الأحداث منظمة حسب القسم والماكينة والجزء"""
    st.subheader("📋 الأحداث حسب القسم والماكينة والجزء")
    
    if not structure.get("departments"):
        st.info("ℹ️ لا توجد أقسام. قم بإضافة أقسام وماكينات أولاً من تبويب 'إدارة الهيكل'")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("اختر القسم:", dept_names, key="filter_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data.get("machines"):
            st.info(f"ℹ️ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("اختر الماكينة:", machine_names, key="filter_machine")
        
        if selected_machine:
            machine_data = dept_data["machines"][selected_machine]
            # استخدام get مع قيمة افتراضية فارغة لتجنب KeyError
            parts_list = machine_data.get("parts", [])
            sheets_list = machine_data.get("sheets", [])
            
            if not sheets_list:
                st.warning(f"⚠ لا توجد شيتات مرتبطة بهذه الماكينة. قم بربط شيت من تبويب 'إدارة الهيكل'")
                return
            
            # اختيار الجزء
            if parts_list:
                selected_part = st.selectbox("اختر الجزء الميكانيكي:", ["الكل"] + parts_list, key="filter_part")
            else:
                selected_part = "الكل"
                st.info("ℹ️ لا توجد أجزاء ميكانيكية مسجلة لهذه الماكينة. قم بإضافة أجزاء من تبويب 'إدارة الهيكل'")
            
            st.markdown("---")
            
            # جمع الأحداث من جميع الشيتات المرتبطة
            all_events = []
            for sheet_name in sheets_list:
                if sheet_name in all_sheets:
                    df = all_sheets[sheet_name]
                    # البحث عن عمود الجزء (قد يكون Part أو الجزء)
                    part_col = None
                    for col in df.columns:
                        if col in ["Part", "الجزء", "part"]:
                            part_col = col
                            break
                    
                    if part_col:
                        events_df = df.copy()
                        events_df["الماكينة"] = selected_machine
                        events_df["القسم"] = selected_dept
                        events_df["الشيت"] = sheet_name
                        all_events.append(events_df)
                    else:
                        st.warning(f"⚠ الشيت '{sheet_name}' لا يحتوي على عمود للجزء الميكانيكي")
            
            if all_events:
                combined_df = pd.concat(all_events, ignore_index=True)
                
                # فلترة حسب الجزء
                if selected_part != "الكل" and part_col:
                    combined_df = combined_df[combined_df[part_col] == selected_part]
                
                if not combined_df.empty:
                    st.success(f"✅ تم العثور على {len(combined_df)} حدث")
                    
                    # تحديد الأعمدة للعرض
                    display_cols = []
                    for col in ["Date", "التاريخ", "Part", "الجزء", "Event", "الحدث", "Correction", "التصحيح", "Serviced_by", "الفني", "Tones", "الأطنان"]:
                        if col in combined_df.columns:
                            display_cols.append(col)
                    
                    if "Images" in combined_df.columns:
                        display_cols.append("Images")
                    
                    st.dataframe(combined_df[display_cols], use_container_width=True)
                    
                    # عرض تفاصيل كل حدث
                    for idx, row in combined_df.iterrows():
                        title = f"📅 {row.get('Date', row.get('التاريخ', 'بدون تاريخ'))} - {row.get(part_col, 'بدون جزء') if part_col else 'بدون جزء'}"
                        with st.expander(title[:80]):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**التاريخ:** {row.get('Date', row.get('التاريخ', '-'))}")
                                if part_col:
                                    st.markdown(f"**الجزء:** {row.get(part_col, '-')}")
                                st.markdown(f"**الحدث:** {row.get('Event', row.get('الحدث', '-'))}")
                            with col2:
                                st.markdown(f"**التصحيح:** {row.get('Correction', row.get('التصحيح', '-'))}")
                                st.markdown(f"**الفني:** {row.get('Serviced_by', row.get('الفني', '-'))}")
                                st.markdown(f"**الأطنان:** {row.get('Tones', row.get('الأطنان', '-'))}")
                            
                            if "Images" in row and row.get("Images"):
                                display_images(row["Images"])
                else:
                    st.info("ℹ️ لا توجد أحداث للجزء المحدد")
            else:
                st.info("ℹ️ لا توجد أحداث مسجلة")

def add_event_with_part(sheets_edit, structure):
    """إضافة حدث جديد مع اختيار الجزء من الفهرس"""
    st.subheader("➕ إضافة حدث جديد (مع اختيار الجزء الميكانيكي)")
    
    if not structure.get("departments"):
        st.warning("⚠ الرجاء إضافة أقسام وماكينات أولاً من تبويب 'إدارة الهيكل'")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("القسم:", dept_names, key="event_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data.get("machines"):
            st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("الماكينة:", machine_names, key="event_machine")
        
        if selected_machine:
            machine_data = dept_data["machines"][selected_machine]
            parts_list = machine_data.get("parts", [])
            sheets_list = machine_data.get("sheets", [])
            
            if not sheets_list:
                st.warning(f"⚠ لا توجد شيتات مرتبطة بهذه الماكينة. قم بربط شيت من تبويب 'إدارة الهيكل'")
                return
            
            if not parts_list:
                st.warning(f"⚠ لا توجد أجزاء ميكانيكية مسجلة لهذه الماكينة. قم بإضافة أجزاء من تبويب 'إدارة الهيكل'")
                return
            
            # اختيار الشيت
            selected_sheet = st.selectbox("الشيت:", sheets_list, key="event_sheet")
            
            # اختيار الجزء من الفهرس
            selected_part = st.selectbox("الجزء الميكانيكي:", parts_list, key="event_part")
            
            st.markdown("---")
            st.markdown(f"### 📝 إضافة حدث جديد في {selected_sheet}")
            
            # نموذج إدخال البيانات
            col1, col2 = st.columns(2)
            
            with col1:
                event_date = st.text_input("التاريخ:", value=datetime.now().strftime("%Y-%m-%d"), key="event_date")
                event_desc = st.text_area("الحدث/المشكلة:", height=100, key="event_desc")
            
            with col2:
                correction = st.text_area("التصحيح/الإجراء:", height=100, key="event_correction")
                serviced_by = st.text_input("الفني/القائم بالعمل:", key="event_serviced")
            
            tones = st.text_input("الأطنان/الكمية:", key="event_tones")
            
            # رفع الصور
            uploaded_images = st.file_uploader(
                "📷 الصور المرفقة:",
                type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
                accept_multiple_files=True,
                key="event_images"
            )
            
            notes = st.text_area("ملاحظات إضافية:", key="event_notes")
            
            if st.button("💾 حفظ الحدث", key="save_event_btn", type="primary"):
                # تحضير البيانات
                new_row = {
                    "Date": event_date,
                    "Part": selected_part,
                    "Event": event_desc,
                    "Correction": correction,
                    "Serviced_by": serviced_by,
                    "Tones": tones,
                    "Notes": notes
                }
                
                # حفظ الصور
                if uploaded_images:
                    saved_images = save_uploaded_images(uploaded_images)
                    if saved_images:
                        new_row["Images"] = ",".join(saved_images)
                
                # إضافة إلى الشيت
                if selected_sheet in sheets_edit:
                    df = sheets_edit[selected_sheet].copy()
                    
                    # التأكد من وجود الأعمدة المطلوبة
                    for col in new_row.keys():
                        if col not in df.columns:
                            df[col] = ""
                    
                    new_row_df = pd.DataFrame([new_row])
                    df_new = pd.concat([df, new_row_df], ignore_index=True)
                    sheets_edit[selected_sheet] = df_new
                    
                    # الحفظ التلقائي
                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"إضافة حدث - {selected_machine} - {selected_part}"
                    )
                    
                    if new_sheets is not None:
                        st.success(f"✅ تم إضافة الحدث بنجاح في {selected_sheet}")
                        st.balloons()
                        st.rerun()
                else:
                    st.error(f"❌ الشيت {selected_sheet} غير موجود")

def search_events_by_part(all_sheets, structure):
    """البحث عن الأحداث حسب الجزء الميكانيكي"""
    st.subheader("🔍 بحث الأحداث حسب الجزء الميكانيكي")
    
    if not structure.get("departments"):
        st.info("ℹ️ لا توجد أقسام")
        return
    
    # جمع كل الأجزاء من جميع الماكينات
    all_parts = {}
    for dept_name, dept_data in structure["departments"].items():
        for machine_name, machine_data in dept_data.get("machines", {}).items():
            for part in machine_data.get("parts", []):
                key = f"{dept_name} → {machine_name} → {part}"
                all_parts[key] = {
                    "department": dept_name,
                    "machine": machine_name,
                    "part": part,
                    "sheets": machine_data.get("sheets", [])
                }
    
    if not all_parts:
        st.info("ℹ️ لا توجد أجزاء ميكانيكية مسجلة. قم بإضافة أجزاء من تبويب 'إدارة الهيكل'")
        return
    
    # اختيار الجزء
    selected_key = st.selectbox("اختر الجزء الميكانيكي:", list(all_parts.keys()), key="search_part")
    
    if selected_key:
        part_info = all_parts[selected_key]
        
        st.markdown(f"""
        **المعلومات:**
        - **القسم:** {part_info['department']}
        - **الماكينة:** {part_info['machine']}
        - **الجزء:** {part_info['part']}
        """)
        
        # جمع الأحداث لهذا الجزء
        events_list = []
        for sheet_name in part_info["sheets"]:
            if sheet_name in all_sheets:
                df = all_sheets[sheet_name]
                # البحث عن عمود الجزء
                part_col = None
                for col in df.columns:
                    if col in ["Part", "الجزء", "part"]:
                        part_col = col
                        break
                
                if part_col:
                    part_events = df[df[part_col] == part_info["part"]].copy()
                    if not part_events.empty:
                        part_events["المصدر"] = sheet_name
                        events_list.append(part_events)
        
        if events_list:
            combined = pd.concat(events_list, ignore_index=True)
            st.success(f"✅ تم العثور على {len(combined)} حدث للجزء {part_info['part']}")
            
            # عرض الإحصائيات
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("عدد الأحداث", len(combined))
            with col2:
                date_col = None
                for col in ["Date", "التاريخ"]:
                    if col in combined.columns:
                        date_col = col
                        break
                if date_col:
                    latest = combined[date_col].max()
                    st.metric("آخر حدث", latest if latest else "-")
                else:
                    st.metric("آخر حدث", "-")
            with col3:
                tech_col = None
                for col in ["Serviced_by", "الفني"]:
                    if col in combined.columns:
                        tech_col = col
                        break
                if tech_col:
                    techs = combined[tech_col].nunique()
                    st.metric("عدد الفنيين", techs)
                else:
                    st.metric("عدد الفنيين", "-")
            
            # عرض الجدول
            display_cols = []
            for col in ["Date", "التاريخ", "Event", "الحدث", "Correction", "التصحيح", "Serviced_by", "الفني", "Tones", "الأطنان", "المصدر"]:
                if col in combined.columns:
                    display_cols.append(col)
            
            st.dataframe(combined[display_cols], use_container_width=True)
            
            # عرض التفاصيل
            for idx, row in combined.iterrows():
                title = f"📅 {row.get('Date', row.get('التاريخ', '-'))} - {row.get('Event', row.get('الحدث', 'بدون حدث'))[:60]}"
                with st.expander(title):
                    st.markdown(f"**التاريخ:** {row.get('Date', row.get('التاريخ', '-'))}")
                    st.markdown(f"**الحدث:** {row.get('Event', row.get('الحدث', '-'))}")
                    st.markdown(f"**التصحيح:** {row.get('Correction', row.get('التصحيح', '-'))}")
                    st.markdown(f"**الفني:** {row.get('Serviced_by', row.get('الفني', '-'))}")
                    st.markdown(f"**الأطنان:** {row.get('Tones', row.get('الأطنان', '-'))}")
                    if "Images" in row and row.get("Images"):
                        display_images(row["Images"])
        else:
            st.info(f"ℹ️ لا توجد أحداث مسجلة للجزء {part_info['part']}")

def manage_parts(structure):
    """إدارة الأجزاء الميكانيكية (إضافة/حذف أجزاء من الماكينات)"""
    st.subheader("🔧 إدارة الأجزاء الميكانيكية")
    
    if not structure.get("departments"):
        st.warning("⚠ الرجاء إضافة أقسام أولاً")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("اختر القسم:", dept_names, key="parts_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data.get("machines"):
            st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("اختر الماكينة:", machine_names, key="parts_machine")
        
        if selected_machine:
            current_parts = dept_data["machines"][selected_machine].get("parts", [])
            
            st.markdown(f"### الأجزاء الحالية في {selected_machine}")
            if current_parts:
                for i, part in enumerate(current_parts, 1):
                    st.markdown(f"{i}. {part}")
            else:
                st.info("لا توجد أجزاء مسجلة")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### ➕ إضافة جزء جديد")
                new_part = st.text_input("اسم الجزء:", key="new_part_name")
                if st.button("إضافة جزء", key="add_part_btn"):
                    if new_part:
                        success, msg = add_part_to_machine(structure, selected_dept, selected_machine, new_part)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("⚠ الرجاء إدخال اسم الجزء")
            
            with col2:
                st.markdown("#### 🗑️ حذف جزء")
                if current_parts:
                    part_to_delete = st.selectbox("اختر الجزء للحذف:", current_parts, key="part_to_delete")
                    if st.button("حذف الجزء", key="delete_part_btn"):
                        success, msg = delete_part_from_machine(structure, selected_dept, selected_machine, part_to_delete)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("لا توجد أجزاء للحذف")

def manage_structure_full(sheets_edit):
    """إدارة كاملة للهيكل التنظيمي"""
    st.subheader("🏗️ الإدارة الكاملة للهيكل التنظيمي")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏭 الأقسام", "🔧 الماكينات", "🔩 الأجزاء الميكانيكية", "📄 ربط الشيتات"])
    
    with tab1:
        st.markdown("### إدارة الأقسام")
        structure = load_structure()
        
        col1, col2 = st.columns(2)
        with col1:
            new_dept = st.text_input("اسم القسم الجديد:", key="new_dept")
            if st.button("➕ إضافة قسم", key="add_dept"):
                if new_dept:
                    success, msg = add_department(structure, new_dept)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col2:
            depts = list(structure["departments"].keys())
            if depts:
                dept_to_delete = st.selectbox("اختر القسم للحذف:", depts, key="del_dept")
                if st.button("🗑️ حذف القسم", key="del_dept_btn"):
                    success, msg = delete_department(structure, dept_to_delete)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        st.markdown("#### الأقسام الحالية")
        if structure["departments"]:
            for dept_name, dept_data in structure["departments"].items():
                st.markdown(f"- **{dept_name}** ({len(dept_data.get('machines', {}))} ماكينات)")
    
    with tab2:
        st.markdown("### إدارة الماكينات")
        structure = load_structure()
        
        depts = list(structure["departments"].keys())
        if not depts:
            st.warning("⚠ الرجاء إضافة قسم أولاً")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_dept = st.selectbox("القسم:", depts, key="machine_dept")
                new_machine = st.text_input("اسم الماكينة الجديدة:", key="new_machine")
                if st.button("➕ إضافة ماكينة", key="add_machine"):
                    if new_machine:
                        success, msg = add_machine(structure, selected_dept, new_machine)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col2:
                selected_dept_del = st.selectbox("القسم:", depts, key="del_machine_dept")
                machines = list(structure["departments"].get(selected_dept_del, {}).get("machines", {}).keys())
                if machines:
                    machine_to_delete = st.selectbox("الماكينة للحذف:", machines, key="del_machine")
                    if st.button("🗑️ حذف ماكينة", key="del_machine_btn"):
                        success, msg = delete_machine(structure, selected_dept_del, machine_to_delete)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("#### الماكينات الحالية")
            for dept_name, dept_data in structure["departments"].items():
                if dept_data.get("machines"):
                    st.markdown(f"**{dept_name}:**")
                    for machine_name, machine_data in dept_data["machines"].items():
                        st.markdown(f"  - {machine_name} ({len(machine_data.get('parts', []))} أجزاء)")
    
    with tab3:
        manage_parts(load_structure())
    
    with tab4:
        st.markdown("### ربط الشيتات بالماكينات")
        structure = load_structure()
        
        if sheets_edit is None:
            st.warning("⚠ لا يمكن تحميل ملف Excel")
        else:
            all_sheets_names = list(sheets_edit.keys())
            
            depts = list(structure["departments"].keys())
            if not depts:
                st.warning("⚠ الرجاء إضافة قسم أولاً")
            else:
                selected_dept = st.selectbox("القسم:", depts, key="link_dept")
                machines = list(structure["departments"].get(selected_dept, {}).get("machines", {}).keys())
                
                if machines:
                    selected_machine = st.selectbox("الماكينة:", machines, key="link_machine")
                    current_sheets = structure["departments"][selected_dept]["machines"][selected_machine].get("sheets", [])
                    
                    st.markdown(f"**الشيتات المرتبطة حالياً بـ {selected_machine}:**")
                    if current_sheets:
                        for s in current_sheets:
                            st.markdown(f"- {s}")
                    else:
                        st.info("لا توجد شيتات مرتبطة")
                    
                    st.markdown("---")
                    
                    available_sheets = [s for s in all_sheets_names if s not in current_sheets]
                    if available_sheets:
                        sheet_to_link = st.selectbox("اختر شيت للربط:", available_sheets, key="sheet_to_link")
                        if st.button("🔗 ربط الشيت", key="link_sheet"):
                            success, msg = add_sheet_to_machine(structure, selected_dept, selected_machine, sheet_to_link)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    if current_sheets:
                        sheet_to_unlink = st.selectbox("اختر شيت لإلغاء الربط:", current_sheets, key="sheet_to_unlink")
                        if st.button("🗑️ إلغاء الربط", key="unlink_sheet"):
                            success, msg = delete_sheet_from_machine(structure, selected_dept, selected_machine, sheet_to_unlink)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                else:
                    st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
    
    return sheets_edit

def manage_users_ui():
    st.subheader("👥 إدارة المستخدمين")
    users = load_users()
    
    st.markdown("### المستخدمون الحاليون")
    users_list = []
    for username, user_data in users.items():
        users_list.append({
            "اسم المستخدم": username,
            "الدور": user_data.get("role", "viewer"),
            "الصلاحيات": ", ".join(user_data.get("permissions", [])),
            "تاريخ الإنشاء": user_data.get("created_at", "").split("T")[0]
        })
    st.dataframe(pd.DataFrame(users_list), use_container_width=True)
    
    st.markdown("---")
    st.markdown("### إضافة مستخدم جديد")
    
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("اسم المستخدم:", key="new_user")
        new_password = st.text_input("كلمة المرور:", type="password", key="new_pass")
    with col2:
        new_role = st.selectbox("الدور:", ["viewer", "editor", "admin"], key="new_role")
        new_perms = st.multiselect("الصلاحيات الإضافية:", ["view", "edit", "manage_structure"], default=["view"], key="new_perms")
    
    if st.button("➕ إضافة مستخدم", key="add_user"):
        if new_username and new_password:
            user_data = {
                "password": new_password,
                "role": new_role,
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"] if new_role == "admin" else new_perms,
                "active": False
            }
            if add_user_to_github(new_username, user_data):
                st.success(f"✅ تم إضافة {new_username}")
                st.rerun()
            else:
                st.error("❌ فشل الإضافة")
    
    st.markdown("---")
    st.markdown("### حذف مستخدم")
    users_to_delete = [u for u in users.keys() if u != "admin"]
    if users_to_delete:
        user_to_delete = st.selectbox("اختر المستخدم للحذف:", users_to_delete, key="del_user")
        if st.button("🗑️ حذف المستخدم", key="del_user_btn"):
            if delete_user_from_github(user_to_delete):
                st.success(f"✅ تم حذف {user_to_delete}")
                st.rerun()
            else:
                st.error("❌ فشل الحذف")

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

setup_images_folder()

# شريط جانبي لتسجيل الدخول
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
            st.success(f"👋 {username} | {user_role} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()
    
    st.markdown("---")
    st.write("🔧 أدوات:")
    
    if st.button("🔄 تحديث الملف من GitHub", key="refresh"):
        if fetch_from_github_requests():
            st.rerun()
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except:
            pass
    
    if st.button("🚪 تسجيل الخروج", key="logout"):
        logout_action()

# تحميل البيانات
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()
structure = load_structure()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# إنشاء التبويبات
tabs_list = ["📋 عرض الأحداث", "➕ إضافة حدث", "🔍 بحث حسب الجزء"]

if permissions["can_edit"]:
    tabs_list.append("🏗️ إدارة الهيكل")

if permissions["can_manage_users"]:
    tabs_list.append("👥 إدارة المستخدمين")

tabs = st.tabs(tabs_list)

# تبويب عرض الأحداث
with tabs[0]:
    display_events_by_machine_and_part(all_sheets, structure)

# تبويب إضافة حدث
with tabs[1]:
    if permissions["can_edit"]:
        add_event_with_part(sheets_edit, structure)
    else:
        st.warning("⚠ ليس لديك صلاحية لإضافة أحداث")

# تبويب بحث حسب الجزء
with tabs[2]:
    search_events_by_part(all_sheets, structure)

# تبويب إدارة الهيكل
if permissions["can_edit"] and len(tabs) > 3:
    with tabs[3]:
        sheets_edit = manage_structure_full(sheets_edit)

# تبويب إدارة المستخدمين
if permissions["can_manage_users"] and len(tabs) > 4:
    with tabs[4]:
        manage_users_ui()import streamlit as st
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
# ⚙ إعدادات التطبيق
# ===============================
APP_CONFIG = {
    "APP_TITLE": "CMMS - نظام إدارة الصيانة الشامل",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "DEFAULT_COLUMNS": ["Date", "Part", "Event", "Correction", "Serviced_by", "Tones", "Images"],
}

# ملف الهيكل التنظيمي
STRUCTURE_FILE = "structure.json"

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ===============================
# 🧩 دوال إدارة الهيكل التنظيمي
# ===============================
def load_structure():
    """تحميل هيكل الأقسام والماكينات والأجزاء"""
    if not os.path.exists(STRUCTURE_FILE):
        default_structure = {
            "departments": {
                "الميكانيكا": {
                    "machines": {
                        "ماطور 1": {
                            "parts": ["محرك", "طرمبة زيت", "فلتر هواء", "شاحن تيربو", "مبرد"],
                            "sheets": ["ماطور 1"],
                            "created_at": datetime.now().isoformat()
                        },
                        "ضاغط 1": {
                            "parts": ["بساتم", "صمامات", "محرك كهربائي", "خزان هواء", "منظم ضغط"],
                            "sheets": ["ضاغط 1"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                },
                "الكهرباء": {
                    "machines": {
                        "محول 1": {
                            "parts": ["ملفات", "قلب حديدي", "عوازل", "مراوح تبريد", "نظام حماية"],
                            "sheets": ["محول 1"],
                            "created_at": datetime.now().isoformat()
                        }
                    },
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(default_structure, f, indent=4, ensure_ascii=False)
        return default_structure
    
    try:
        with open(STRUCTURE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"departments": {}}

def save_structure(structure):
    try:
        with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ الهيكل: {e}")
        return False

def add_department(structure, dept_name):
    if dept_name in structure["departments"]:
        return False, "القسم موجود بالفعل"
    structure["departments"][dept_name] = {
        "machines": {},
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة القسم {dept_name}"

def delete_department(structure, dept_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    del structure["departments"][dept_name]
    save_structure(structure)
    return True, f"تم حذف القسم {dept_name}"

def add_machine(structure, dept_name, machine_name, parts_list=None):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة موجودة بالفعل"
    
    if parts_list is None:
        parts_list = ["جزء رئيسي", "جزء فرعي 1", "جزء فرعي 2"]
    
    structure["departments"][dept_name]["machines"][machine_name] = {
        "parts": parts_list,
        "sheets": [],
        "created_at": datetime.now().isoformat()
    }
    save_structure(structure)
    return True, f"تم إضافة الماكينة {machine_name}"

def delete_machine(structure, dept_name, machine_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    del structure["departments"][dept_name]["machines"][machine_name]
    save_structure(structure)
    return True, f"تم حذف الماكينة {machine_name}"

def add_part_to_machine(structure, dept_name, machine_name, part_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    if part_name in structure["departments"][dept_name]["machines"][machine_name]["parts"]:
        return False, "الجزء موجود بالفعل"
    
    structure["departments"][dept_name]["machines"][machine_name]["parts"].append(part_name)
    save_structure(structure)
    return True, f"تم إضافة الجزء {part_name}"

def delete_part_from_machine(structure, dept_name, machine_name, part_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    if part_name not in structure["departments"][dept_name]["machines"][machine_name]["parts"]:
        return False, "الجزء غير موجود"
    
    structure["departments"][dept_name]["machines"][machine_name]["parts"].remove(part_name)
    save_structure(structure)
    return True, f"تم حذف الجزء {part_name}"

def add_sheet_to_machine(structure, dept_name, machine_name, sheet_name):
    if dept_name not in structure["departments"]:
        return False, "القسم غير موجود"
    if machine_name not in structure["departments"][dept_name]["machines"]:
        return False, "الماكينة غير موجودة"
    
    if sheet_name in structure["departments"][dept_name]["machines"][machine_name]["sheets"]:
        return False, "الشيت موجود بالفعل"
    
    structure["departments"][dept_name]["machines"][machine_name]["sheets"].append(sheet_name)
    save_structure(structure)
    return True, f"تم إضافة الشيت {sheet_name}"

def get_machine_parts(structure, dept_name, machine_name):
    if dept_name in structure["departments"] and machine_name in structure["departments"][dept_name]["machines"]:
        return structure["departments"][dept_name]["machines"][machine_name]["parts"]
    return []

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def save_uploaded_images(uploaded_files):
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل {uploaded_file.name} - نوع غير مدعوم")
            continue
        
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل {uploaded_file.name} - حجم كبير جداً")
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
    try:
        file_path = os.path.join(IMAGES_FOLDER, image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        st.error(f"❌ خطأ في حذف الصورة: {e}")
    return False

def display_images(image_filenames, caption="الصور المرفقة"):
    if not image_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    
    for img in images:
        img = img.strip()
        img_path = os.path.join(IMAGES_FOLDER, img)
        if os.path.exists(img_path):
            try:
                st.image(img_path, caption=img, use_container_width=True)
            except:
                st.write(f"📷 {img}")

# -------------------------------
# 🧩 دوال المستخدمين والجلسات
# -------------------------------
def download_users_from_github():
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل المستخدمين: {e}")
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def upload_users_to_github(users_data):
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
            repo.update_file(path="users.json", message=f"تحديث المستخدمين", content=users_json, sha=contents.sha, branch="main")
            return True
        except:
            repo.create_file(path="users.json", message=f"إنشاء ملف المستخدمين", content=users_json, branch="main")
            return True
    except Exception as e:
        st.error(f"❌ خطأ في رفع المستخدمين: {e}")
        return False

def load_users():
    try:
        users_data = download_users_from_github()
        if "admin" not in users_data:
            users_data["admin"] = {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}
            upload_users_to_github(users_data)
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل المستخدمين: {e}")
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def add_user_to_github(username, user_data):
    try:
        users = load_users()
        if username in users:
            return False
        users[username] = user_data
        return upload_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في إضافة المستخدم: {e}")
        return False

def delete_user_from_github(username):
    try:
        users = load_users()
        if username in users and username != "admin":
            del users[username]
            return upload_users_to_github(users)
        return False
    except Exception as e:
        st.error(f"❌ خطأ في حذف المستخدم: {e}")
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
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
    st.caption(f"🔒 المستخدمون النشطون: {active_count} / {APP_CONFIG['MAX_ACTIVE_USERS']}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            current_users = load_users()
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input not in active_users or username_input == "admin":
                    if active_count >= APP_CONFIG['MAX_ACTIVE_USERS'] and username_input != "admin":
                        st.error("🚫 الحد الأقصى للمستخدمين المتصلين")
                        return False
                    
                    state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                    save_state(state)
                    
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.user_role = current_users[username_input].get("role", "viewer")
                    st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                    
                    st.success(f"✅ تم تسجيل الدخول: {username_input}")
                    st.rerun()
                else:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل")
            else:
                st.error("❌ كلمة المرور غير صحيحة")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول: {username} ({user_role})")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_users": True, "can_manage_structure": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_users": False, "can_manage_structure": False}
    else:
        return {"can_view": "view" in user_permissions, "can_edit": "edit" in user_permissions, "can_manage_users": False, "can_manage_structure": False}

# -------------------------------
# 🔄 دوال ملف Excel
# -------------------------------
def fetch_from_github_requests():
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

@st.cache_data(show_spinner=False)
def load_all_sheets():
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
        st.error(f"❌ خطأ في تحميل الشيتات: {e}")
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ في الحفظ المحلي: {e}")
        return None

    try:
        st.cache_data.clear()
    except:
        pass

    token = st.secrets.get("github", {}).get("token", None)
    if not token or not GITHUB_AVAILABLE:
        return load_sheets_for_edit()

    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
        except:
            repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
        return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات")
        return result
    return sheets_dict

# ===============================
# 🖥 دوال عرض وإدارة الأحداث (المطورة)
# ===============================
def display_events_by_machine_and_part(all_sheets, structure):
    """عرض الأحداث منظمة حسب القسم والماكينة والجزء"""
    st.subheader("📋 الأحداث حسب القسم والماكينة والجزء")
    
    if not structure["departments"]:
        st.info("ℹ️ لا توجد أقسام. قم بإضافة أقسام وماكينات أولاً")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("اختر القسم:", dept_names, key="filter_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data["machines"]:
            st.info(f"ℹ️ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("اختر الماكينة:", machine_names, key="filter_machine")
        
        if selected_machine:
            machine_data = dept_data["machines"][selected_machine]
            parts_list = machine_data["parts"]
            sheets_list = machine_data["sheets"]
            
            if not sheets_list:
                st.warning(f"⚠ لا توجد شيتات مرتبطة بهذه الماكينة")
                return
            
            # اختيار الجزء
            selected_part = st.selectbox("اختر الجزء الميكانيكي:", ["الكل"] + parts_list, key="filter_part")
            
            st.markdown("---")
            
            # جمع الأحداث من جميع الشيتات المرتبطة
            all_events = []
            for sheet_name in sheets_list:
                if sheet_name in all_sheets:
                    df = all_sheets[sheet_name]
                    if "Part" in df.columns or "الجزء" in df.columns:
                        part_col = "Part" if "Part" in df.columns else "الجزء"
                        events_df = df.copy()
                        events_df["الماكينة"] = selected_machine
                        events_df["القسم"] = selected_dept
                        events_df["الشيت"] = sheet_name
                        all_events.append(events_df)
            
            if all_events:
                combined_df = pd.concat(all_events, ignore_index=True)
                
                # فلترة حسب الجزء
                if selected_part != "الكل" and part_col in combined_df.columns:
                    combined_df = combined_df[combined_df[part_col] == selected_part]
                
                if not combined_df.empty:
                    st.success(f"✅ تم العثور على {len(combined_df)} حدث")
                    
                    # عرض البيانات
                    display_cols = ["Date", "Part", "Event", "Correction", "Serviced_by", "Tones"]
                    available_cols = [c for c in display_cols if c in combined_df.columns]
                    
                    if "Images" in combined_df.columns:
                        available_cols.append("Images")
                    
                    st.dataframe(combined_df[available_cols], use_container_width=True)
                    
                    # عرض تفاصيل كل حدث
                    for idx, row in combined_df.iterrows():
                        with st.expander(f"📅 {row.get('Date', 'بدون تاريخ')} - {row.get('Part', 'بدون جزء')} - {row.get('Event', 'بدون حدث')[:50]}..."):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**التاريخ:** {row.get('Date', '-')}")
                                st.markdown(f"**الجزء:** {row.get('Part', '-')}")
                                st.markdown(f"**الحدث:** {row.get('Event', '-')}")
                            with col2:
                                st.markdown(f"**التصحيح:** {row.get('Correction', '-')}")
                                st.markdown(f"**الفني:** {row.get('Serviced_by', '-')}")
                                st.markdown(f"**الأطنان:** {row.get('Tones', '-')}")
                            
                            if "Images" in row and row.get("Images"):
                                display_images(row["Images"])
                else:
                    st.info("ℹ️ لا توجد أحداث للجزء المحدد")
            else:
                st.info("ℹ️ لا توجد أحداث مسجلة")

def add_event_with_part(sheets_edit, structure):
    """إضافة حدث جديد مع اختيار الجزء من الفهرس"""
    st.subheader("➕ إضافة حدث جديد (مع اختيار الجزء الميكانيكي)")
    
    if not structure["departments"]:
        st.warning("⚠ الرجاء إضافة أقسام وماكينات أولاً")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("القسم:", dept_names, key="event_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data["machines"]:
            st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("الماكينة:", machine_names, key="event_machine")
        
        if selected_machine:
            machine_data = dept_data["machines"][selected_machine]
            parts_list = machine_data["parts"]
            sheets_list = machine_data["sheets"]
            
            if not sheets_list:
                st.warning(f"⚠ لا توجد شيتات مرتبطة بهذه الماكينة")
                return
            
            # اختيار الشيت
            selected_sheet = st.selectbox("الشيت:", sheets_list, key="event_sheet")
            
            # اختيار الجزء من الفهرس
            selected_part = st.selectbox("الجزء الميكانيكي:", parts_list, key="event_part")
            
            st.markdown("---")
            st.markdown(f"### 📝 إضافة حدث جديد في {selected_sheet}")
            
            # نموذج إدخال البيانات
            col1, col2 = st.columns(2)
            
            with col1:
                event_date = st.text_input("التاريخ:", value=datetime.now().strftime("%Y-%m-%d"), key="event_date")
                event_desc = st.text_area("الحدث/المشكلة:", height=100, key="event_desc")
            
            with col2:
                correction = st.text_area("التصحيح/الإجراء:", height=100, key="event_correction")
                serviced_by = st.text_input("الفني/القائم بالعمل:", key="event_serviced")
            
            tones = st.text_input("الأطنان/الكمية:", key="event_tones")
            
            # رفع الصور
            uploaded_images = st.file_uploader(
                "📷 الصور المرفقة:",
                type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
                accept_multiple_files=True,
                key="event_images"
            )
            
            notes = st.text_area("ملاحظات إضافية:", key="event_notes")
            
            if st.button("💾 حفظ الحدث", key="save_event_btn", type="primary"):
                # تحضير البيانات
                new_row = {
                    "Date": event_date,
                    "Part": selected_part,
                    "Event": event_desc,
                    "Correction": correction,
                    "Serviced_by": serviced_by,
                    "Tones": tones,
                    "Notes": notes
                }
                
                # حفظ الصور
                if uploaded_images:
                    saved_images = save_uploaded_images(uploaded_images)
                    if saved_images:
                        new_row["Images"] = ",".join(saved_images)
                
                # إضافة إلى الشيت
                if selected_sheet in sheets_edit:
                    df = sheets_edit[selected_sheet].copy()
                    
                    # التأكد من وجود الأعمدة المطلوبة
                    for col in new_row.keys():
                        if col not in df.columns:
                            df[col] = ""
                    
                    new_row_df = pd.DataFrame([new_row])
                    df_new = pd.concat([df, new_row_df], ignore_index=True)
                    sheets_edit[selected_sheet] = df_new
                    
                    # الحفظ التلقائي
                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"إضافة حدث - {selected_machine} - {selected_part}"
                    )
                    
                    if new_sheets is not None:
                        st.success(f"✅ تم إضافة الحدث بنجاح في {selected_sheet}")
                        st.balloons()
                        st.rerun()
                else:
                    st.error(f"❌ الشيت {selected_sheet} غير موجود")

def search_events_by_part(all_sheets, structure):
    """البحث عن الأحداث حسب الجزء الميكانيكي"""
    st.subheader("🔍 بحث الأحداث حسب الجزء الميكانيكي")
    
    if not structure["departments"]:
        st.info("ℹ️ لا توجد أقسام")
        return
    
    # جمع كل الأجزاء من جميع الماكينات
    all_parts = {}
    for dept_name, dept_data in structure["departments"].items():
        for machine_name, machine_data in dept_data["machines"].items():
            for part in machine_data["parts"]:
                key = f"{dept_name} → {machine_name} → {part}"
                all_parts[key] = {
                    "department": dept_name,
                    "machine": machine_name,
                    "part": part,
                    "sheets": machine_data["sheets"]
                }
    
    if not all_parts:
        st.info("ℹ️ لا توجد أجزاء ميكانيكية مسجلة")
        return
    
    # اختيار الجزء
    selected_key = st.selectbox("اختر الجزء الميكانيكي:", list(all_parts.keys()), key="search_part")
    
    if selected_key:
        part_info = all_parts[selected_key]
        
        st.markdown(f"""
        **المعلومات:**
        - **القسم:** {part_info['department']}
        - **الماكينة:** {part_info['machine']}
        - **الجزء:** {part_info['part']}
        """)
        
        # جمع الأحداث لهذا الجزء
        events_list = []
        for sheet_name in part_info["sheets"]:
            if sheet_name in all_sheets:
                df = all_sheets[sheet_name]
                if "Part" in df.columns:
                    part_events = df[df["Part"] == part_info["part"]].copy()
                    if not part_events.empty:
                        part_events["المصدر"] = sheet_name
                        events_list.append(part_events)
        
        if events_list:
            combined = pd.concat(events_list, ignore_index=True)
            st.success(f"✅ تم العثور على {len(combined)} حدث للجزء {part_info['part']}")
            
            # عرض الإحصائيات
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("عدد الأحداث", len(combined))
            with col2:
                if "Date" in combined.columns:
                    latest = combined["Date"].max()
                    st.metric("آخر حدث", latest if latest else "-")
            with col3:
                if "Serviced_by" in combined.columns:
                    techs = combined["Serviced_by"].nunique()
                    st.metric("عدد الفنيين", techs)
            
            # عرض الجدول
            display_cols = ["Date", "Event", "Correction", "Serviced_by", "Tones", "المصدر"]
            available = [c for c in display_cols if c in combined.columns]
            st.dataframe(combined[available], use_container_width=True)
            
            # عرض التفاصيل
            for idx, row in combined.iterrows():
                with st.expander(f"📅 {row.get('Date', '-')} - {row.get('Event', 'بدون حدث')[:60]}..."):
                    st.markdown(f"**التاريخ:** {row.get('Date', '-')}")
                    st.markdown(f"**الحدث:** {row.get('Event', '-')}")
                    st.markdown(f"**التصحيح:** {row.get('Correction', '-')}")
                    st.markdown(f"**الفني:** {row.get('Serviced_by', '-')}")
                    st.markdown(f"**الأطنان:** {row.get('Tones', '-')}")
                    if "Images" in row and row.get("Images"):
                        display_images(row["Images"])
        else:
            st.info(f"ℹ️ لا توجد أحداث مسجلة للجزء {part_info['part']}")

def manage_parts(structure):
    """إدارة الأجزاء الميكانيكية (إضافة/حذف أجزاء من الماكينات)"""
    st.subheader("🔧 إدارة الأجزاء الميكانيكية")
    
    if not structure["departments"]:
        st.warning("⚠ الرجاء إضافة أقسام أولاً")
        return
    
    # اختيار القسم
    dept_names = list(structure["departments"].keys())
    selected_dept = st.selectbox("اختر القسم:", dept_names, key="parts_dept")
    
    if selected_dept:
        dept_data = structure["departments"][selected_dept]
        
        if not dept_data["machines"]:
            st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
            return
        
        # اختيار الماكينة
        machine_names = list(dept_data["machines"].keys())
        selected_machine = st.selectbox("اختر الماكينة:", machine_names, key="parts_machine")
        
        if selected_machine:
            current_parts = dept_data["machines"][selected_machine]["parts"]
            
            st.markdown(f"### الأجزاء الحالية في {selected_machine}")
            if current_parts:
                for i, part in enumerate(current_parts, 1):
                    st.markdown(f"{i}. {part}")
            else:
                st.info("لا توجد أجزاء مسجلة")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### ➕ إضافة جزء جديد")
                new_part = st.text_input("اسم الجزء:", key="new_part_name")
                if st.button("إضافة جزء", key="add_part_btn"):
                    if new_part:
                        success, msg = add_part_to_machine(structure, selected_dept, selected_machine, new_part)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("⚠ الرجاء إدخال اسم الجزء")
            
            with col2:
                st.markdown("#### 🗑️ حذف جزء")
                if current_parts:
                    part_to_delete = st.selectbox("اختر الجزء للحذف:", current_parts, key="part_to_delete")
                    if st.button("حذف الجزء", key="delete_part_btn"):
                        success, msg = delete_part_from_machine(structure, selected_dept, selected_machine, part_to_delete)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("لا توجد أجزاء للحذف")

def manage_structure_full(sheets_edit):
    """إدارة كاملة للهيكل التنظيمي"""
    st.subheader("🏗️ الإدارة الكاملة للهيكل التنظيمي")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏭 الأقسام", "🔧 الماكينات", "🔩 الأجزاء الميكانيكية", "📄 ربط الشيتات"])
    
    with tab1:
        st.markdown("### إدارة الأقسام")
        structure = load_structure()
        
        col1, col2 = st.columns(2)
        with col1:
            new_dept = st.text_input("اسم القسم الجديد:", key="new_dept")
            if st.button("➕ إضافة قسم", key="add_dept"):
                if new_dept:
                    success, msg = add_department(structure, new_dept)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col2:
            depts = list(structure["departments"].keys())
            if depts:
                dept_to_delete = st.selectbox("اختر القسم للحذف:", depts, key="del_dept")
                if st.button("🗑️ حذف القسم", key="del_dept_btn"):
                    success, msg = delete_department(structure, dept_to_delete)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        st.markdown("#### الأقسام الحالية")
        if structure["departments"]:
            for dept_name, dept_data in structure["departments"].items():
                st.markdown(f"- **{dept_name}** ({len(dept_data['machines'])} ماكينات)")
    
    with tab2:
        st.markdown("### إدارة الماكينات")
        structure = load_structure()
        
        depts = list(structure["departments"].keys())
        if not depts:
            st.warning("⚠ الرجاء إضافة قسم أولاً")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_dept = st.selectbox("القسم:", depts, key="machine_dept")
                new_machine = st.text_input("اسم الماكينة الجديدة:", key="new_machine")
                if st.button("➕ إضافة ماكينة", key="add_machine"):
                    if new_machine:
                        success, msg = add_machine(structure, selected_dept, new_machine)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col2:
                selected_dept_del = st.selectbox("القسم:", depts, key="del_machine_dept")
                machines = list(structure["departments"].get(selected_dept_del, {}).get("machines", {}).keys())
                if machines:
                    machine_to_delete = st.selectbox("الماكينة للحذف:", machines, key="del_machine")
                    if st.button("🗑️ حذف ماكينة", key="del_machine_btn"):
                        success, msg = delete_machine(structure, selected_dept_del, machine_to_delete)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("#### الماكينات الحالية")
            for dept_name, dept_data in structure["departments"].items():
                if dept_data["machines"]:
                    st.markdown(f"**{dept_name}:**")
                    for machine_name, machine_data in dept_data["machines"].items():
                        st.markdown(f"  - {machine_name} ({len(machine_data['parts'])} أجزاء)")
    
    with tab3:
        manage_parts(load_structure())
    
    with tab4:
        st.markdown("### ربط الشيتات بالماكينات")
        structure = load_structure()
        
        if sheets_edit is None:
            st.warning("⚠ لا يمكن تحميل ملف Excel")
        else:
            all_sheets_names = list(sheets_edit.keys())
            
            depts = list(structure["departments"].keys())
            if not depts:
                st.warning("⚠ الرجاء إضافة قسم أولاً")
            else:
                selected_dept = st.selectbox("القسم:", depts, key="link_dept")
                machines = list(structure["departments"].get(selected_dept, {}).get("machines", {}).keys())
                
                if machines:
                    selected_machine = st.selectbox("الماكينة:", machines, key="link_machine")
                    current_sheets = structure["departments"][selected_dept]["machines"][selected_machine]["sheets"]
                    
                    st.markdown(f"**الشيتات المرتبطة حالياً بـ {selected_machine}:**")
                    if current_sheets:
                        for s in current_sheets:
                            st.markdown(f"- {s}")
                    else:
                        st.info("لا توجد شيتات مرتبطة")
                    
                    st.markdown("---")
                    
                    available_sheets = [s for s in all_sheets_names if s not in current_sheets]
                    if available_sheets:
                        sheet_to_link = st.selectbox("اختر شيت للربط:", available_sheets, key="sheet_to_link")
                        if st.button("🔗 ربط الشيت", key="link_sheet"):
                            success, msg = add_sheet_to_machine(structure, selected_dept, selected_machine, sheet_to_link)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    if current_sheets:
                        sheet_to_unlink = st.selectbox("اختر شيت لإلغاء الربط:", current_sheets, key="sheet_to_unlink")
                        if st.button("🗑️ إلغاء الربط", key="unlink_sheet"):
                            success, msg = delete_sheet_from_machine(structure, selected_dept, selected_machine, sheet_to_unlink)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                else:
                    st.warning(f"⚠ لا توجد ماكينات في قسم {selected_dept}")
    
    return sheets_edit

def manage_users_ui():
    st.subheader("👥 إدارة المستخدمين")
    users = load_users()
    
    st.markdown("### المستخدمون الحاليون")
    users_list = []
    for username, user_data in users.items():
        users_list.append({
            "اسم المستخدم": username,
            "الدور": user_data.get("role", "viewer"),
            "الصلاحيات": ", ".join(user_data.get("permissions", [])),
            "تاريخ الإنشاء": user_data.get("created_at", "").split("T")[0]
        })
    st.dataframe(pd.DataFrame(users_list), use_container_width=True)
    
    st.markdown("---")
    st.markdown("### إضافة مستخدم جديد")
    
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("اسم المستخدم:", key="new_user")
        new_password = st.text_input("كلمة المرور:", type="password", key="new_pass")
    with col2:
        new_role = st.selectbox("الدور:", ["viewer", "editor", "admin"], key="new_role")
        new_perms = st.multiselect("الصلاحيات الإضافية:", ["view", "edit", "manage_structure"], default=["view"], key="new_perms")
    
    if st.button("➕ إضافة مستخدم", key="add_user"):
        if new_username and new_password:
            user_data = {
                "password": new_password,
                "role": new_role,
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"] if new_role == "admin" else new_perms,
                "active": False
            }
            if add_user_to_github(new_username, user_data):
                st.success(f"✅ تم إضافة {new_username}")
                st.rerun()
            else:
                st.error("❌ فشل الإضافة")
    
    st.markdown("---")
    st.markdown("### حذف مستخدم")
    users_to_delete = [u for u in users.keys() if u != "admin"]
    if users_to_delete:
        user_to_delete = st.selectbox("اختر المستخدم للحذف:", users_to_delete, key="del_user")
        if st.button("🗑️ حذف المستخدم", key="del_user_btn"):
            if delete_user_from_github(user_to_delete):
                st.success(f"✅ تم حذف {user_to_delete}")
                st.rerun()
            else:
                st.error("❌ فشل الحذف")

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

setup_images_folder()

# شريط جانبي لتسجيل الدخول
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
            st.success(f"👋 {username} | {user_role} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()
    
    st.markdown("---")
    st.write("🔧 أدوات:")
    
    if st.button("🔄 تحديث الملف من GitHub", key="refresh"):
        if fetch_from_github_requests():
            st.rerun()
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except:
            pass
    
    if st.button("🚪 تسجيل الخروج", key="logout"):
        logout_action()

# تحميل البيانات
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()
structure = load_structure()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# إنشاء التبويبات
tabs_list = ["📋 عرض الأحداث", "➕ إضافة حدث", "🔍 بحث حسب الجزء"]

if permissions["can_edit"]:
    tabs_list.append("🏗️ إدارة الهيكل")

if permissions["can_manage_users"]:
    tabs_list.append("👥 إدارة المستخدمين")

tabs = st.tabs(tabs_list)

# تبويب عرض الأحداث
with tabs[0]:
    display_events_by_machine_and_part(all_sheets, structure)

# تبويب إضافة حدث
with tabs[1]:
    if permissions["can_edit"]:
        add_event_with_part(sheets_edit, structure)
    else:
        st.warning("⚠ ليس لديك صلاحية لإضافة أحداث")

# تبويب بحث حسب الجزء
with tabs[2]:
    search_events_by_part(all_sheets, structure)

# تبويب إدارة الهيكل
if permissions["can_edit"] and len(tabs) > 3:
    with tabs[3]:
        sheets_edit = manage_structure_full(sheets_edit)

# تبويب إدارة المستخدمين
if permissions["can_manage_users"] and len(tabs) > 4:
    with tabs[4]:
        manage_users_ui()
