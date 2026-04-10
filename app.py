import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import requests
import shutil
import re
from datetime import datetime, timedelta
from base64 import b64decode
import uuid
import io

# محاولة استيراد Plotly مع معالجة الخطأ
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        plt.rcParams['font.family'] = 'Arial'
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False

try:
    from github import Github, GithubException
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

APP_CONFIG = {
    "APP_TITLE": "نظام إدارة الصيانة - CMMS",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l9.xlsx",
    "LOCAL_FILE": "l9.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "DEFAULT_SHEET_COLUMNS": ["التاريخ", " رقم الماكينة", "الحدث/العطل", "الإجراء التصحيحي", "تم بواسطة", "الطن", "الصور", "قسم"],
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ------------------------------- دوال المستخدمين -------------------------------
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
            return False
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO_USERS)
        users_json = json.dumps(users_data, indent=4, ensure_ascii=False, sort_keys=True)
        try:
            contents = repo.get_contents("users.json", ref="main")
            repo.update_file(path="users.json", message="تحديث ملف المستخدمين", content=users_json, sha=contents.sha, branch="main")
            return True
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
        return users_data
    except:
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"], "active": False}}

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
    username_input = st.selectbox("اختر المستخدم", list(users.keys()))
    password = st.text_input("كلمة المرور", type="password")
    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"المستخدمون النشطون: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            current_users = load_users()
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input != "admin" and username_input in active_users:
                    st.warning("هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                    st.error("الحد الأقصى للمستخدمين المتصلين.")
                    return False
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                st.success(f"تم تسجيل الدخول: {username_input}")
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة.")
        return False
    else:
        st.success(f"مسجل الدخول كـ: {st.session_state.username}")
        rem = remaining_time(state, st.session_state.username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"الوقت المتبقي: {mins:02d}:{secs:02d}")
        if st.button("تسجيل الخروج"):
            logout_action()
        return True

# ------------------------------- دوال الملفات -------------------------------
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"فشل التحديث: {e}")
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
        st.error(f"خطأ في تحميل الشيتات: {e}")
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
        st.error(f"خطأ في تحميل الشيتات: {e}")
        return None

def save_to_github(sheets_dict, commit_message):
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.error("❌ لم يتم العثور على GitHub token في secrets")
            return False
        
        if not GITHUB_AVAILABLE:
            st.error("❌ PyGithub غير متوفر")
            return False
        
        temp_file = APP_CONFIG["LOCAL_FILE"]
        try:
            with pd.ExcelWriter(temp_file, engine="openpyxl") as writer:
                for name, sh in sheets_dict.items():
                    try:
                        sh.to_excel(writer, sheet_name=name, index=False)
                    except Exception:
                        sh.astype(object).to_excel(writer, sheet_name=name, index=False)
        except Exception as e:
            st.error(f"❌ خطأ في إنشاء ملف Excel: {e}")
            return False
        
        try:
            g = Github(token)
            repo = g.get_repo(APP_CONFIG["REPO_NAME"])
            with open(temp_file, "rb") as f:
                content = f.read()
            try:
                contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
                repo.update_file(
                    path=APP_CONFIG["FILE_PATH"],
                    message=commit_message,
                    content=content,
                    sha=contents.sha,
                    branch=APP_CONFIG["BRANCH"]
                )
                st.success(f"✅ تم تحديث الملف على GitHub")
                return True
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=APP_CONFIG["FILE_PATH"],
                        message=commit_message,
                        content=content,
                        branch=APP_CONFIG["BRANCH"]
                    )
                    st.success(f"✅ تم إنشاء الملف على GitHub")
                    return True
                else:
                    st.error(f"❌ خطأ في GitHub: {e}")
                    return False
        except Exception as e:
            st.error(f"❌ فشل الرفع إلى GitHub: {str(e)}")
            return False
    except Exception as e:
        st.error(f"❌ خطأ عام: {str(e)}")
        return False

# ------------------------------- دوال العرض -------------------------------
def display_sheet_data(sheet_name, df, unique_id):
    st.markdown(f"### {sheet_name}")
    st.info(f"عدد السجلات: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # فلتر حسب المعدة (عرض فقط)
    equipment_list = []
    if "المعدة" in df.columns:
        equipment_list = df["المعدة"].dropna().unique()
        equipment_list = [str(e).strip() for e in equipment_list if str(e).strip() != ""]
        equipment_list = sorted(equipment_list)
    
    if equipment_list:
        st.markdown("#### فلتر حسب المعدة (عرض فقط):")
        selected_filter = st.selectbox(
            "اختر المعدة:", 
            ["جميع المعدات"] + equipment_list,
            key=f"filter_{unique_id}"
        )
        if selected_filter != "جميع المعدات":
            df = df[df["المعدة"] == selected_filter]
            st.info(f"عرض للمعدة: {selected_filter} - السجلات: {len(df)}")
    
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype == 'object':
            display_df[col] = display_df[col].astype(str).apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
    st.dataframe(display_df, use_container_width=True, height=400)

# ==================== دوال إضافة ماكينة فقط ====================
def add_new_machine_only(sheets_edit):
    st.subheader("➕ إضافة ماكينة جديدة")
    st.info("سيتم إضافة الماكينة الجديدة كشيت منفصل في ملف Excel الموجود على GitHub")
    
    col1, col2 = st.columns(2)
    with col1:
        new_sheet_name = st.text_input("📝 اسم الماكينة الجديدة:", key="new_sheet_name_github",
                                       placeholder="مثال: ماكينة الخراطة, ماكينة اللحام, الكسارة")
        if new_sheet_name and new_sheet_name in sheets_edit:
            st.error(f"❌ الماكينة '{new_sheet_name}' موجودة بالفعل!")
        elif new_sheet_name:
            st.success(f"✅ اسم الماكينة '{new_sheet_name}' متاح")
    with col2:
        use_default = st.checkbox("استخدام الأعمدة الافتراضية", value=True, key="use_default_columns")
        if use_default:
            columns_list = APP_CONFIG["DEFAULT_SHEET_COLUMNS"]
            st.info(f"📊 الأعمدة: {', '.join(columns_list)}")
        else:
            columns_text = st.text_area("✏️ الأعمدة (كل عمود في سطر):", 
                                        value="\n".join(APP_CONFIG["DEFAULT_SHEET_COLUMNS"]), 
                                        key="custom_columns", height=150)
            columns_list = [col.strip() for col in columns_text.split("\n") if col.strip()]
            if not columns_list:
                columns_list = APP_CONFIG["DEFAULT_SHEET_COLUMNS"]
    
    st.markdown("---")
    st.markdown("### 📋 معاينة الماكينة الجديدة")
    preview_df = pd.DataFrame(columns=columns_list)
    st.dataframe(preview_df, use_container_width=True)
    st.caption(f"📊 عدد الأعمدة: {len(columns_list)} | سيتم إنشاء شيت فارغ بهذه الأعمدة للماكينة الجديدة")
    
    if st.button("✅ إنشاء وإضافة الماكينة إلى GitHub", key="create_sheet_github_btn", type="primary", use_container_width=True):
        if not new_sheet_name:
            st.error("❌ الرجاء إدخال اسم الماكينة")
            return sheets_edit
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', new_sheet_name.strip())
        if clean_name != new_sheet_name:
            st.warning(f"⚠ تم تعديل اسم الماكينة إلى: {clean_name}")
            new_sheet_name = clean_name
        if new_sheet_name in sheets_edit:
            st.error(f"❌ الماكينة '{new_sheet_name}' موجودة بالفعل!")
            return sheets_edit
        
        try:
            with st.spinner("جاري إنشاء الماكينة ورفعها إلى GitHub..."):
                new_df = pd.DataFrame(columns=columns_list)
                sheets_edit[new_sheet_name] = new_df
                commit_msg = f"إضافة ماكينة جديدة: {new_sheet_name} بواسطة {st.session_state.get('username', 'user')}"
                if save_to_github(sheets_edit, commit_msg):
                    st.success(f"✅ تم إنشاء الماكينة '{new_sheet_name}' بنجاح ورفعها إلى GitHub!")
                    st.cache_data.clear()
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ فشل رفع الماكينة إلى GitHub")
                    return sheets_edit
        except Exception as e:
            st.error(f"❌ حدث خطأ: {str(e)}")
            return sheets_edit
    
    st.markdown("---")
    st.markdown("### 📋 الماكينات الموجودة حالياً على GitHub:")
    if sheets_edit:
        for sheet_name in sheets_edit.keys():
            st.write(f"- 🏭 {sheet_name}")
    else:
        st.info("لا توجد ماكينات بعد")
    return sheets_edit

def manage_data_view_only(sheets_edit):
    if sheets_edit is None:
        st.warning("الملف غير موجود. استخدم زر 'تحديث من GitHub' في الشريط الجانبي أولاً")
        return sheets_edit
    
    # تبويبان فقط: عرض البيانات + إضافة ماكينة
    tab_names = ["📋 عرض البيانات", "➕ إضافة ماكينة"]
    tabs_view = st.tabs(tab_names)
    
    with tabs_view[0]:
        st.subheader("جميع الماكينات (عرض فقط)")
        if sheets_edit:
            sheet_tabs = st.tabs(list(sheets_edit.keys()))
            for i, (sheet_name, df) in enumerate(sheets_edit.items()):
                with sheet_tabs[i]:
                    # عرض البيانات فقط بدون أي تعديل
                    display_sheet_data(sheet_name, df, f"view_{sheet_name}")
        else:
            st.info("لا توجد ماكينات لعرضها")
    
    with tabs_view[1]:
        sheets_edit = add_new_machine_only(sheets_edit)
    
    return sheets_edit

# ------------------------------- الواجهة الرئيسية -------------------------------
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

with st.sidebar:
    st.header("الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | ⏳ {mins:02d}:{secs:02d}")
        st.markdown("---")
        if st.button("🔄 تحديث من GitHub"):
            if fetch_from_github_requests():
                st.rerun()
        if st.button("🗑 مسح الكاش"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()

all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
can_edit = (user_role == "admin" or user_role == "editor" or "edit" in user_permissions)

# تبويب واحد فقط للعرض، وتبويب الإدارة سيظهر فقط للمستخدمين المصرح لهم ويحتوي على إضافة ماكينة فقط
tabs_list = ["📊 عرض البيانات"]
if can_edit:
    tabs_list.append("🛠 إدارة التعديلات (إضافة ماكينة فقط)")

tabs = st.tabs(tabs_list)

with tabs[0]:
    # عرض البيانات فقط بدون بحث متقدم أو تحليل أعطال
    if all_sheets:
        st.subheader("جميع الماكينات")
        sheet_tabs = st.tabs(list(all_sheets.keys()))
        for i, (sheet_name, df) in enumerate(all_sheets.items()):
            with sheet_tabs[i]:
                display_sheet_data(sheet_name, df, f"main_view_{sheet_name}")
    else:
        st.warning("لا توجد بيانات لعرضها. يرجى تحديث الملف من GitHub.")

if can_edit and len(tabs) > 1:
    with tabs[1]:
        sheets_edit = manage_data_view_only(sheets_edit)
