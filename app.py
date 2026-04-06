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
