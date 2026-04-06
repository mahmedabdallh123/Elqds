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
    "MAX_ACTIVE_USERS": 10,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "EXPECTED_COLUMNS": {
        "card": ["card", "machine", "رقم", "ماكينة", "جهاز", "كارد"],
        "date": ["date", "تاريخ", "time", "وقت"],
        "event": ["event", "حدث", "issue", "مشكلة"],
        "correction": ["correction", "تصحيح", "solution", "حل"],
        "servised_by": ["servised", "serviced", "technician", "فني"],
        "tones": ["tones", "طن", "أطنان", "ton"],
        "images": ["images", "pictures", "صور", "مرفقات"]
    }
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ===============================
# دوال الصور
# ===============================
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)

def save_uploaded_images(uploaded_files):
    if not uploaded_files:
        return []
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
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
    except:
        pass
    return False

# ===============================
# دوال المستخدمين والجلسات
# ===============================
def download_users_from_github():
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        return users_data
    except:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"admin": {"password": "0000", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def upload_users_to_github(users_data):
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            return False
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO_USERS)
        users_json = json.dumps(users_data, indent=4, ensure_ascii=False, sort_keys=True)
        try:
            contents = repo.get_contents("users.json", ref="main")
            repo.update_file(path="users.json", message="تحديث المستخدمين", content=users_json, sha=contents.sha, branch="main")
        except:
            repo.create_file(path="users.json", message="إنشاء ملف المستخدمين", content=users_json, branch="main")
        return True
    except:
        return False

def load_users():
    try:
        users_data = download_users_from_github()
        if "admin" not in users_data:
            users_data["admin"] = {"password": "0000", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}
            upload_users_to_github(users_data)
        return users_data
    except:
        return {"admin": {"password": "0000", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def save_users_to_github(users_data):
    return upload_users_to_github(users_data)

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

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
    for k in list(st.session_state.keys()):
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
    
    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")
    
    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون: {active_count} / {MAX_ACTIVE_USERS}")

    if st.button("تسجيل الدخول", key="login_button"):
        current_users = load_users()
        
        if username_input in current_users:
            if current_users[username_input]["password"] == password:
                if username_input in active_users:
                    st.error("⚠ هذا المستخدم مسجل دخول بالفعل من جهاز آخر")
                    return False
                
                if active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                    st.error(f"🚫 الحد الأقصى للمستخدمين المتصلين ({MAX_ACTIVE_USERS}) تم الوصول إليه")
                    return False
                
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                
                st.success(f"✅ تم تسجيل الدخول بنجاح! مرحباً {username_input}")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة")
        else:
            st.error("❌ اسم المستخدم غير موجود")
        return False
    
    if st.session_state.logged_in:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
        
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        
        if st.button("🚪 تسجيل الخروج", key="logout_button"):
            logout_action()
        return True
    
    return False

# ===============================
# دوال إدارة المستخدمين
# ===============================
def manage_users_ui():
    """واجهة إدارة المستخدمين"""
    st.subheader("👥 إدارة المستخدمين")
    
    users = load_users()
    
    # عرض المستخدمين الحاليين
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
    
    # إضافة مستخدم جديد
    st.markdown("### ➕ إضافة مستخدم جديد")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_username = st.text_input("اسم المستخدم:", key="new_username")
        new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
    
    with col2:
        new_role = st.selectbox("الدور:", ["viewer", "editor", "admin"], key="new_role")
        new_permissions = st.multiselect(
            "الصلاحيات (لغير الأدمن):",
            ["view", "edit", "manage_sheets", "manage_users"],
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
                users[new_username] = user_data
                if save_users_to_github(users):
                    st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح")
                    st.rerun()
                else:
                    st.error("❌ فشل إضافة المستخدم")
        else:
            st.warning("⚠ الرجاء إدخال اسم المستخدم وكلمة المرور")
    
    st.markdown("---")
    
    # تعديل مستخدم موجود
    st.markdown("### ✏️ تعديل مستخدم")
    
    existing_users = [u for u in users.keys()]
    if existing_users:
        user_to_edit = st.selectbox("اختر المستخدم للتعديل:", existing_users, key="user_to_edit")
        
        if user_to_edit:
            current_user_data = users[user_to_edit]
            
            col1, col2 = st.columns(2)
            
            with col1:
                edit_password = st.text_input("كلمة المرور الجديدة (اتركها فارغة إذا لم تريد التغيير):", type="password", key="edit_password")
                edit_role = st.selectbox("الدور:", ["viewer", "editor", "admin"], index=["viewer", "editor", "admin"].index(current_user_data.get("role", "viewer")), key="edit_role")
            
            with col2:
                current_perms = current_user_data.get("permissions", [])
                if current_perms == ["all"]:
                    current_perms = ["view", "edit", "manage_sheets", "manage_users"]
                edit_permissions = st.multiselect(
                    "الصلاحيات:",
                    ["view", "edit", "manage_sheets", "manage_users"],
                    default=current_perms if current_perms != ["all"] else ["view", "edit", "manage_sheets", "manage_users"],
                    key="edit_permissions"
                )
            
            if st.button("💾 حفظ التعديلات", key="save_user_edit"):
                if edit_password:
                    current_user_data["password"] = edit_password
                current_user_data["role"] = edit_role
                current_user_data["permissions"] = ["all"] if edit_role == "admin" else edit_permissions
                
                users[user_to_edit] = current_user_data
                if save_users_to_github(users):
                    st.success(f"✅ تم تحديث بيانات المستخدم '{user_to_edit}'")
                    st.rerun()
                else:
                    st.error("❌ فشل تحديث المستخدم")
    
    st.markdown("---")
    
    # حذف مستخدم
    st.markdown("### 🗑️ حذف مستخدم")
    
    users_to_delete = [u for u in users.keys() if u != "admin"]
    
    if users_to_delete:
        user_to_delete = st.selectbox("اختر المستخدم للحذف:", users_to_delete, key="user_to_delete")
        
        if st.button("🗑️ حذف المستخدم", key="delete_user_btn"):
            if user_to_delete:
                confirm = st.checkbox(f"تأكيد حذف المستخدم '{user_to_delete}'؟ لا يمكن التراجع عن هذا الإجراء")
                if confirm:
                    del users[user_to_delete]
                    if save_users_to_github(users):
                        st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح")
                        st.rerun()
                    else:
                        st.error("❌ فشل حذف المستخدم")
    else:
        st.info("ℹ️ لا توجد مستخدمين للحذف غير المشرف")

# ===============================
# دوال ملف Excel
# ===============================
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث: {e}")
        return False

@st.cache_data(show_spinner=False)
def load_all_sheets():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        for name, df in sheets.items():
            if df.empty:
                continue
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                sh.to_excel(writer, sheet_name=name, index=False)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"⚠ خطأ: {e}")
        return None

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
        st.success("✅ تم الحفظ في GitHub")
        return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    return result if result is not None else sheets_dict

# ===============================
# دوال الصلاحيات
# ===============================
def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_sheets": True, "can_manage_users": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_sheets": True, "can_manage_users": False}
    else:
        return {"can_view": True, "can_edit": "edit" in user_permissions, "can_manage_sheets": False, "can_manage_users": False}

# ===============================
# دوال العرض والتعديل
# ===============================
def display_dynamic_sheets(sheets_edit):
    st.subheader("📂 جميع الشيتات")
    if not sheets_edit:
        st.warning("⚠ لا توجد شيتات")
        return
    sheet_tabs = st.tabs(list(sheets_edit.keys()))
    for i, (sheet_name, df) in enumerate(sheets_edit.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📋 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            st.dataframe(df, use_container_width=True)

def display_data(all_sheets):
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات")
        return
    st.subheader("📋 عرض البيانات")
    sheet_tabs = st.tabs(list(all_sheets.keys()))
    for i, (sheet_name, df) in enumerate(all_sheets.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📄 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            st.dataframe(df, use_container_width=True, height=400)

def edit_sheet_with_save_button(sheets_edit):
    st.subheader("✏ تعديل البيانات")
    if not sheets_edit:
        return sheets_edit
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    df = sheets_edit[sheet_name].astype(str).copy()
    st.markdown(f"### 📋 تحرير: {sheet_name}")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{sheet_name}")
    if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
        sheets_edit[sheet_name] = edited_df.astype(object)
        new_sheets = auto_save_to_github(sheets_edit, f"تعديل شيت {sheet_name}")
        if new_sheets is not None:
            st.success("✅ تم حفظ التغييرات")
            st.rerun()
    return sheets_edit

def add_new_sheet(sheets_edit):
    st.subheader("➕ إضافة شيت جديد")
    col1, col2 = st.columns(2)
    with col1:
        new_sheet_name = st.text_input("اسم الشيت الجديد:", key="new_sheet_name")
    with col2:
        num_columns = st.number_input("عدد الأعمدة:", min_value=1, max_value=20, value=3, key="num_columns")
    
    st.markdown("### 📋 الأعمدة")
    columns_data = []
    for i in range(num_columns):
        col_name = st.text_input(f"اسم العمود {i+1}:", value=f"عمود_{i+1}", key=f"col_name_{i}")
        columns_data.append({"name": col_name})
    
    if st.button("✨ إنشاء الشيت", key="create_new_sheet", type="primary"):
        if not new_sheet_name:
            st.warning("⚠ أدخل اسم الشيت")
            return
        if new_sheet_name in sheets_edit:
            st.warning(f"⚠ الشيت '{new_sheet_name}' موجود")
            return
        new_df_data = {col_info["name"]: [] for col_info in columns_data if col_info["name"]}
        new_df = pd.DataFrame(new_df_data)
        sheets_edit[new_sheet_name] = new_df
        new_sheets = auto_save_to_github(sheets_edit, f"إضافة شيت: {new_sheet_name}")
        if new_sheets is not None:
            st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}'")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 🗑️ حذف شيت")
    existing_sheets = [s for s in sheets_edit.keys()]
    if existing_sheets:
        sheet_to_delete = st.selectbox("اختر الشيت للحذف:", existing_sheets, key="sheet_to_delete")
        if st.button("🗑️ حذف", key="delete_sheet_btn"):
            if sheet_to_delete:
                del sheets_edit[sheet_to_delete]
                new_sheets = auto_save_to_github(sheets_edit, f"حذف شيت: {sheet_to_delete}")
                if new_sheets is not None:
                    st.success(f"✅ تم حذف الشيت")
                    st.rerun()

def manage_data_edit(sheets_edit):
    if sheets_edit is None:
        st.warning("❗ الملف غير موجود. استخدم زر التحديث أولاً")
        return sheets_edit
    
    display_dynamic_sheets(sheets_edit)
    
    tab_names = ["✏ تعديل البيانات", "📄 إدارة الشيتات"]
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        sheets_edit = edit_sheet_with_save_button(sheets_edit)
    
    with tabs_edit[1]:
        add_new_sheet(sheets_edit)
    
    return sheets_edit

# ===============================
# الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
setup_images_folder()

# الشريط الجانبي
with st.sidebar:
    st.header("👤 الجلسة")
    
    users = load_users()
    state = cleanup_sessions(load_state())
    
    if not st.session_state.get("logged_in", False):
        username_input = st.selectbox("👤 المستخدم", list(users.keys()), key="sidebar_user")
        password_input = st.text_input("🔑 كلمة المرور", type="password", key="sidebar_pass")
        
        if st.button("🔐 تسجيل الدخول", key="sidebar_login"):
            if username_input in users and users[username_input]["password"] == password_input:
                active_users = [u for u, v in state.items() if v.get("active")]
                if username_input not in active_users or username_input == "admin":
                    state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                    save_state(state)
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.user_role = users[username_input].get("role", "viewer")
                    st.session_state.user_permissions = users[username_input].get("permissions", ["view"])
                    st.success(f"✅ مرحباً {username_input}")
                    st.rerun()
                else:
                    st.error("⚠ هذا المستخدم مسجل دخول بالفعل")
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        
        st.stop()
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مرحباً {username} ({user_role})")
        
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        
        if st.button("🚪 تسجيل الخروج", key="sidebar_logout"):
            logout_action()
    
    st.markdown("---")
    
    if st.button("🔄 تحديث الملف", key="refresh_github"):
        if fetch_from_github_requests():
            st.rerun()
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        st.cache_data.clear()
        st.rerun()

# تحميل البيانات
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# عرض معلومات الشيتات في sidebar
if all_sheets and st.session_state.get("logged_in"):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 الشيتات")
    for sheet in list(all_sheets.keys()):
        df_info = all_sheets[sheet]
        st.sidebar.caption(f"📄 {sheet}: {len(df_info)} صف")

# التبويبات الرئيسية
if st.session_state.get("logged_in", False):
    # تحديد التبويبات حسب الصلاحيات
    tabs_list = ["📋 عرض البيانات"]
    
    if permissions["can_edit"]:
        tabs_list.append("🛠 تعديل البيانات")
    
    if permissions["can_manage_users"]:
        tabs_list.append("👥 إدارة المستخدمين")
    
    tabs = st.tabs(tabs_list)
    tab_index = 0
    
    # تبويب عرض البيانات
    with tabs[0]:
        st.header("📋 عرض البيانات")
        if all_sheets is None:
            st.warning("❗ الملف غير موجود. استخدم زر التحديث")
        else:
            display_data(all_sheets)
    
    # تبويب تعديل البيانات
    if permissions["can_edit"] and len(tabs) > 1:
        with tabs[1]:
            st.header("🛠 تعديل البيانات")
            sheets_edit = manage_data_edit(sheets_edit)
    
    # تبويب إدارة المستخدمين
    if permissions["can_manage_users"] and len(tabs) > 2:
        with tabs[2]:
            manage_users_ui()
else:
    st.info("👈 الرجاء تسجيل الدخول من الشريط الجانبي")import streamlit as st
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
    "EXPECTED_COLUMNS": {
        "card": ["card", "machine", "رقم", "ماكينة", "جهاز", "كارد"],
        "date": ["date", "تاريخ", "time", "وقت"],
        "event": ["event", "حدث", "issue", "مشكلة"],
        "correction": ["correction", "تصحيح", "solution", "حل"],
        "servised_by": ["servised", "serviced", "technician", "فني"],
        "tones": ["tones", "طن", "أطنان", "ton"],
        "images": ["images", "pictures", "صور", "مرفقات"]
    }
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ===============================
# دوال الصور
# ===============================
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)

def save_uploaded_images(uploaded_files):
    if not uploaded_files:
        return []
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
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
    except:
        pass
    return False

# ===============================
# دوال المستخدمين والجلسات
# ===============================
def download_users_from_github():
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        return users_data
    except:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def upload_users_to_github(users_data):
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            return False
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO_USERS)
        users_json = json.dumps(users_data, indent=4, ensure_ascii=False, sort_keys=True)
        try:
            contents = repo.get_contents("users.json", ref="main")
            repo.update_file(path="users.json", message="تحديث المستخدمين", content=users_json, sha=contents.sha, branch="main")
        except:
            repo.create_file(path="users.json", message="إنشاء ملف المستخدمين", content=users_json, branch="main")
        return True
    except:
        return False

def load_users():
    try:
        users_data = download_users_from_github()
        if "admin" not in users_data:
            users_data["admin"] = {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}
            upload_users_to_github(users_data)
        return users_data
    except:
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

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
    for k in list(st.session_state.keys()):
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
    
    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")
    
    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون: {active_count} / {MAX_ACTIVE_USERS}")

    if st.button("تسجيل الدخول", key="login_button"):
        current_users = load_users()
        
        # التحقق من صحة اسم المستخدم وكلمة المرور
        if username_input in current_users:
            if current_users[username_input]["password"] == password:
                # التحقق من عدم وجود جلسة نشطة لنفس المستخدم
                if username_input in active_users:
                    st.error("⚠ هذا المستخدم مسجل دخول بالفعل من جهاز آخر")
                    return False
                
                # التحقق من عدم تجاوز الحد الأقصى
                if active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                    st.error(f"🚫 الحد الأقصى للمستخدمين المتصلين ({MAX_ACTIVE_USERS}) تم الوصول إليه")
                    return False
                
                # تسجيل الدخول
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                
                st.success(f"✅ تم تسجيل الدخول بنجاح! مرحباً {username_input}")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة")
        else:
            st.error("❌ اسم المستخدم غير موجود")
        return False
    
    # إذا كان المستخدم مسجل الدخول بالفعل
    if st.session_state.logged_in:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
        
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        
        if st.button("🚪 تسجيل الخروج", key="logout_button"):
            logout_action()
        return True
    
    return False

# ===============================
# دوال ملف Excel
# ===============================
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث: {e}")
        return False

@st.cache_data(show_spinner=False)
def load_all_sheets():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        for name, df in sheets.items():
            if df.empty:
                continue
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
            df = df.fillna('')
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                sh.to_excel(writer, sheet_name=name, index=False)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"⚠ خطأ: {e}")
        return None

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
        st.success("✅ تم الحفظ في GitHub")
        return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    return result if result is not None else sheets_dict

# ===============================
# دوال الصلاحيات
# ===============================
def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_sheets": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_sheets": True}
    else:
        return {"can_view": True, "can_edit": "edit" in user_permissions, "can_manage_sheets": False}

# ===============================
# دوال العرض والتعديل
# ===============================
def find_column_by_keywords(df, keywords_list):
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for keyword in keywords_list:
            if keyword.lower() in col_lower:
                return col
    return None

def display_dynamic_sheets(sheets_edit):
    st.subheader("📂 جميع الشيتات")
    if not sheets_edit:
        st.warning("⚠ لا توجد شيتات")
        return
    sheet_tabs = st.tabs(list(sheets_edit.keys()))
    for i, (sheet_name, df) in enumerate(sheets_edit.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📋 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            st.dataframe(df, use_container_width=True)

def display_data(all_sheets):
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات")
        return
    st.subheader("📋 عرض البيانات")
    sheet_tabs = st.tabs(list(all_sheets.keys()))
    for i, (sheet_name, df) in enumerate(all_sheets.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📄 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            st.dataframe(df, use_container_width=True, height=400)

def edit_sheet_with_save_button(sheets_edit):
    st.subheader("✏ تعديل البيانات")
    if not sheets_edit:
        return sheets_edit
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    df = sheets_edit[sheet_name].astype(str).copy()
    st.markdown(f"### 📋 تحرير: {sheet_name}")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{sheet_name}")
    if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
        sheets_edit[sheet_name] = edited_df.astype(object)
        new_sheets = auto_save_to_github(sheets_edit, f"تعديل شيت {sheet_name}")
        if new_sheets is not None:
            st.success("✅ تم حفظ التغييرات")
            st.rerun()
    return sheets_edit

def add_new_sheet(sheets_edit):
    st.subheader("➕ إضافة شيت جديد")
    col1, col2 = st.columns(2)
    with col1:
        new_sheet_name = st.text_input("اسم الشيت الجديد:", key="new_sheet_name")
    with col2:
        num_columns = st.number_input("عدد الأعمدة:", min_value=1, max_value=20, value=3, key="num_columns")
    
    st.markdown("### 📋 الأعمدة")
    columns_data = []
    for i in range(num_columns):
        col_name = st.text_input(f"اسم العمود {i+1}:", value=f"عمود_{i+1}", key=f"col_name_{i}")
        columns_data.append({"name": col_name})
    
    if st.button("✨ إنشاء الشيت", key="create_new_sheet", type="primary"):
        if not new_sheet_name:
            st.warning("⚠ أدخل اسم الشيت")
            return
        if new_sheet_name in sheets_edit:
            st.warning(f"⚠ الشيت '{new_sheet_name}' موجود")
            return
        new_df_data = {col_info["name"]: [] for col_info in columns_data if col_info["name"]}
        new_df = pd.DataFrame(new_df_data)
        sheets_edit[new_sheet_name] = new_df
        new_sheets = auto_save_to_github(sheets_edit, f"إضافة شيت: {new_sheet_name}")
        if new_sheets is not None:
            st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}'")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 🗑️ حذف شيت")
    existing_sheets = [s for s in sheets_edit.keys()]
    if existing_sheets:
        sheet_to_delete = st.selectbox("اختر الشيت للحذف:", existing_sheets, key="sheet_to_delete")
        if st.button("🗑️ حذف", key="delete_sheet_btn"):
            if sheet_to_delete:
                del sheets_edit[sheet_to_delete]
                new_sheets = auto_save_to_github(sheets_edit, f"حذف شيت: {sheet_to_delete}")
                if new_sheets is not None:
                    st.success(f"✅ تم حذف الشيت")
                    st.rerun()

def manage_data_edit(sheets_edit):
    if sheets_edit is None:
        st.warning("❗ الملف غير موجود. استخدم زر التحديث أولاً")
        return sheets_edit
    
    display_dynamic_sheets(sheets_edit)
    
    tab_names = ["✏ تعديل البيانات", "📄 إدارة الشيتات"]
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        sheets_edit = edit_sheet_with_save_button(sheets_edit)
    
    with tabs_edit[1]:
        add_new_sheet(sheets_edit)
    
    return sheets_edit

# ===============================
# الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
setup_images_folder()

# الشريط الجانبي
with st.sidebar:
    st.header("👤 الجلسة")
    
    # عرض واجهة تسجيل الدخول في الشريط الجانبي
    users = load_users()
    state = cleanup_sessions(load_state())
    
    if not st.session_state.get("logged_in", False):
        username_input = st.selectbox("👤 المستخدم", list(users.keys()), key="sidebar_user")
        password_input = st.text_input("🔑 كلمة المرور", type="password", key="sidebar_pass")
        
        if st.button("🔐 تسجيل الدخول", key="sidebar_login"):
            if username_input in users and users[username_input]["password"] == password_input:
                # التحقق من الجلسات النشطة
                active_users = [u for u, v in state.items() if v.get("active")]
                if username_input not in active_users or username_input == "admin":
                    state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                    save_state(state)
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.user_role = users[username_input].get("role", "viewer")
                    st.session_state.user_permissions = users[username_input].get("permissions", ["view"])
                    st.success(f"✅ مرحباً {username_input}")
                    st.rerun()
                else:
                    st.error("⚠ هذا المستخدم مسجل دخول بالفعل")
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        
        st.stop()
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مرحباً {username} ({user_role})")
        
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        
        if st.button("🚪 تسجيل الخروج", key="sidebar_logout"):
            logout_action()
    
    st.markdown("---")
    
    if st.button("🔄 تحديث الملف", key="refresh_github"):
        if fetch_from_github_requests():
            st.rerun()
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        st.cache_data.clear()
        st.rerun()

# تحميل البيانات
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# عرض معلومات الشيتات في sidebar
if all_sheets and st.session_state.get("logged_in"):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 الشيتات")
    for sheet in list(all_sheets.keys()):
        df_info = all_sheets[sheet]
        st.sidebar.caption(f"📄 {sheet}: {len(df_info)} صف")

# التبويبات الرئيسية (تظهر فقط بعد تسجيل الدخول)
if st.session_state.get("logged_in", False):
    if permissions["can_edit"]:
        tabs = st.tabs(["📋 عرض البيانات", "🛠 تعديل البيانات"])
    else:
        tabs = st.tabs(["📋 عرض البيانات"])

    with tabs[0]:
        st.header("📋 عرض البيانات")
        if all_sheets is None:
            st.warning("❗ الملف غير موجود. استخدم زر التحديث")
        else:
            display_data(all_sheets)

    if permissions["can_edit"] and len(tabs) > 1:
        with tabs[1]:
            st.header("🛠 تعديل البيانات")
            sheets_edit = manage_data_edit(sheets_edit)
else:
    st.info("👈 الرجاء تسجيل الدخول من الشريط الجانبي")
