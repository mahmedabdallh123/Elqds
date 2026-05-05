import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import requests
import shutil
import re
from datetime import datetime, timedelta
import io
import uuid
from PIL import Image
from github import Github, GithubException

# ------------------------------- إعدادات وضع عدم الاتصال -------------------------------
PENDING_OPS_FILE = "pending_operations.json"

def load_pending_operations():
    if "pending_operations" not in st.session_state:
        st.session_state.pending_operations = []
        if os.path.exists(PENDING_OPS_FILE):
            try:
                with open(PENDING_OPS_FILE, "r", encoding="utf-8") as f:
                    st.session_state.pending_operations = json.load(f)
            except:
                pass
    return st.session_state.pending_operations

def save_pending_operations():
    try:
        with open(PENDING_OPS_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.pending_operations, f, indent=2, ensure_ascii=False)
    except:
        pass

def add_pending_operation(op_type, data):
    op = {
        "id": str(uuid.uuid4()),
        "type": op_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "retries": 0
    }
    st.session_state.pending_operations.append(op)
    save_pending_operations()
    return op["id"]

def remove_pending_operation(op_id):
    st.session_state.pending_operations = [op for op in st.session_state.pending_operations if op["id"] != op_id]
    save_pending_operations()

def is_github_accessible():
    try:
        requests.get("https://raw.githubusercontent.com/mahmedabdallh123/Elqds/main/users.json", timeout=5)
        return True
    except:
        return False

# ------------------------------- الإعدادات الثابتة -------------------------------
APP_CONFIG = {
    "APP_TITLE": "القدس - CMMS",
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
    "DEFAULT_SHEET_COLUMNS": ["مده الاصلاح", "التاريخ", "المعدة", "الحدث/العطل", "الإجراء التصحيحي", "تم بواسطة", "قطع غيار مستخدمة", "نوع العطل", "قدرة الفني (حل/تفكير/مبادرة/قرار)", "الالتزام بتعليمات السلامة", "رابط الصورة"],
    "SPARE_PARTS_SHEET": "قطع_الغيار",
    "SPARE_PARTS_COLUMNS": ["اسم القطعة", "المقاس", "قوه الشد", "الرصيد الموجود", "مدة التوريد", "ضرورية", "القسم", "رابط_الصورة", "حد_الإنذار"],
    "MAINTENANCE_SHEET": "صيانة_وقائية",
    "MAINTENANCE_COLUMNS": ["المعدة", "نوع_الصيانة", "اسم_البند", "الفترة_بالأيام", "آخر_تنفيذ", "التاريخ_التالي", "ملاحظات", "قطع_غيار_مستخدمة_افتراضية", "رابط_الصورة"],
    "GENERAL_SECTION": "عام"
}

st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# ------------------------------- ثوابت إضافية -------------------------------
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]
EQUIPMENT_CONFIG_FILE = "equipment_config.json"

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"
GITHUB_TOKEN = st.secrets.get("github", {}).get("token", None)
GITHUB_AVAILABLE = GITHUB_TOKEN is not None
ACTIVITY_LOG_FILE = "activity_log.json"

# ------------------------------- دوال رفع الصور -------------------------------
def upload_image_to_github(image_file, entity_type, entity_id, custom_filename=None):
    if not GITHUB_AVAILABLE:
        st.error("❌ GitHub token غير متوفر")
        return None
    try:
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        buffer.seek(0)
        filename = custom_filename or f"{entity_type}_{entity_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        repo_path = f"{IMAGES_FOLDER}/{entity_type}/{filename}"
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        try:
            repo.get_contents(f"{IMAGES_FOLDER}/{entity_type}/", ref=APP_CONFIG["BRANCH"])
        except GithubException:
            repo.create_file(f"{IMAGES_FOLDER}/{entity_type}/.gitkeep", "Create folder", "", branch=APP_CONFIG["BRANCH"])
        result = repo.create_file(path=repo_path, message=f"Add image for {entity_type}", content=buffer.getvalue(), branch=APP_CONFIG["BRANCH"])
        return f"https://raw.githubusercontent.com/{APP_CONFIG['REPO_NAME']}/{APP_CONFIG['BRANCH']}/{repo_path}"
    except Exception as e:
        st.error(f"خطأ في رفع الصورة: {e}")
        return None

# ------------------------------- دوال قطع الغيار -------------------------------
def load_spare_parts():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return pd.DataFrame(columns=APP_CONFIG["SPARE_PARTS_COLUMNS"])
    try:
        df = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=APP_CONFIG["SPARE_PARTS_SHEET"])
        df.columns = df.columns.astype(str).str.strip()
        for col in APP_CONFIG["SPARE_PARTS_COLUMNS"]:
            if col not in df.columns:
                df[col] = ""
        df = df.fillna("")
        df["الرصيد الموجود"] = pd.to_numeric(df["الرصيد الموجود"], errors='coerce').fillna(0)
        if "حد_الإنذار" not in df.columns:
            df["حد_الإنذار"] = 1
        else:
            df["حد_الإنذار"] = pd.to_numeric(df["حد_الإنذار"], errors='coerce').fillna(1)
        return df
    except:
        return pd.DataFrame(columns=APP_CONFIG["SPARE_PARTS_COLUMNS"])

def get_spare_parts_for_section(section_name):
    df = load_spare_parts()
    if df.empty:
        return []
    filtered = df[(df["القسم"] == section_name) | (df["القسم"] == APP_CONFIG["GENERAL_SECTION"])]
    return list(zip(filtered["اسم القطعة"], filtered["الرصيد الموجود"]))

def consume_spare_part(part_name, quantity=1):
    df = load_spare_parts()
    if df.empty:
        return False, "لا توجد قطع غيار", None
    mask = df["اسم القطعة"] == part_name
    if not mask.any():
        return False, f"القطعة '{part_name}' غير موجودة", None
    current_qty = df.loc[mask, "الرصيد الموجود"].values[0]
    if current_qty < quantity:
        return False, f"الرصيد غير كافٍ (الموجود {current_qty})", current_qty
    new_qty = current_qty - quantity
    df.loc[mask, "الرصيد الموجود"] = new_qty
    st.session_state.temp_spare_parts_df = df
    return True, f"تم خصم {quantity} من '{part_name}'، الرصيد الجديد: {new_qty}", new_qty

def get_critical_spare_parts():
    df = load_spare_parts()
    if df.empty:
        return []
    df["الرصيد الموجود"] = pd.to_numeric(df["الرصيد الموجود"], errors='coerce').fillna(0)
    if "حد_الإنذار" not in df.columns:
        df["حد_الإنذار"] = 1
    else:
        df["حد_الإنذار"] = pd.to_numeric(df["حد_الإنذار"], errors='coerce').fillna(1)
    if "القسم" not in df.columns:
        return []
    df["القسم"] = df["القسم"].fillna("").astype(str)
    df = df[df["القسم"].str.strip() != ""]
    df["ضرورية"] = df["ضرورية"].astype(str).str.strip()
    critical = df[(df["ضرورية"] == "نعم") & (df["الرصيد الموجود"] < df["حد_الإنذار"])]
    return critical[["اسم القطعة", "القسم", "الرصيد الموجود", "حد_الإنذار"]].to_dict('records')

# ------------------------------- دوال سجل النشاطات -------------------------------
def log_activity(action_type, details, username=None):
    if username is None:
        username = st.session_state.get("username", "غير معروف")
    log_entry = {"timestamp": datetime.now().isoformat(), "username": username, "action_type": action_type, "details": details}
    log = []
    if os.path.exists(ACTIVITY_LOG_FILE):
        try:
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                log = json.load(f)
        except:
            log = []
    log.append(log_entry)
    if len(log) > 100:
        log = log[-100:]
    with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    if GITHUB_AVAILABLE:
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(APP_CONFIG["REPO_NAME"])
            content = json.dumps(log, indent=2, ensure_ascii=False)
            try:
                contents = repo.get_contents(ACTIVITY_LOG_FILE, ref=APP_CONFIG["BRANCH"])
                repo.update_file(ACTIVITY_LOG_FILE, "تحديث سجل النشاطات", content, contents.sha, branch=APP_CONFIG["BRANCH"])
            except:
                repo.create_file(ACTIVITY_LOG_FILE, "إنشاء سجل النشاطات", content, branch=APP_CONFIG["BRANCH"])
        except:
            pass

# ------------------------------- دوال الصيانة الوقائية -------------------------------
def load_maintenance_tasks():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return pd.DataFrame(columns=APP_CONFIG["MAINTENANCE_COLUMNS"])
    try:
        df = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=APP_CONFIG["MAINTENANCE_SHEET"])
        df.columns = df.columns.astype(str).str.strip()
        for col in APP_CONFIG["MAINTENANCE_COLUMNS"]:
            if col not in df.columns:
                df[col] = ""
        df = df.fillna("")
        if "آخر_تنفيذ" in df.columns:
            df["آخر_تنفيذ"] = pd.to_datetime(df["آخر_تنفيذ"], errors='coerce')
        if "التاريخ_التالي" in df.columns:
            df["التاريخ_التالي"] = pd.to_datetime(df["التاريخ_التالي"], errors='coerce')
        if "الفترة_بالأيام" in df.columns:
            df["الفترة_بالأيام"] = pd.to_numeric(df["الفترة_بالأيام"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=APP_CONFIG["MAINTENANCE_COLUMNS"])

def get_upcoming_maintenance(days_ahead=3):
    df = load_maintenance_tasks()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    today = datetime.now().date()
    overdue = df[df["التاريخ_التالي"] < pd.Timestamp(today)]
    upcoming = df[(df["التاريخ_التالي"] >= pd.Timestamp(today)) & (df["التاريخ_التالي"] <= pd.Timestamp(today + timedelta(days=days_ahead)))]
    return overdue, upcoming

def add_maintenance_task(sheets_edit, equipment, task_name, period_hours, start_date=None, notes="", default_spare="", image_url=None):
    df = sheets_edit.get(APP_CONFIG["MAINTENANCE_SHEET"])
    if df is None:
        df = pd.DataFrame(columns=APP_CONFIG["MAINTENANCE_COLUMNS"])
    if start_date is None:
        start_date = datetime.now().date()
    period_days = period_hours / 24.0
    next_date = start_date + timedelta(days=period_days)
    new_row = pd.DataFrame([{
        "المعدة": equipment, "نوع_الصيانة": f"{period_hours} ساعة", "اسم_البند": task_name,
        "الفترة_بالأيام": period_days, "آخر_تنفيذ": pd.NaT, "التاريخ_التالي": next_date,
        "ملاحظات": notes, "قطع_غيار_مستخدمة_افتراضية": default_spare, "رابط_الصورة": image_url or ""
    }])
    sheets_edit[APP_CONFIG["MAINTENANCE_SHEET"]] = pd.concat([df, new_row], ignore_index=True)
    log_activity("add_maintenance_task", f"تم إضافة بند صيانة '{task_name}' للماكينة {equipment}")
    return sheets_edit

# ------------------------------- دوال تحليل الأعطال -------------------------------
def flexible_date_parser(date_series):
    def parse_single(val):
        if pd.isna(val) or val == "":
            return pd.NaT
        if isinstance(val, (pd.Timestamp, datetime)):
            return val
        val_str = str(val).strip().replace('\\', '/')
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d']:
            try:
                return pd.to_datetime(val_str, format=fmt)
            except:
                continue
        return pd.to_datetime(val_str, errors='coerce')
    return date_series.apply(parse_single)

def analyze_time_between_corrections(df, filter_text=None):
    if df is None or df.empty:
        return pd.DataFrame()
    data = df.copy()
    if "التاريخ" not in data.columns or "المعدة" not in data.columns or "الإجراء التصحيحي" not in data.columns:
        return pd.DataFrame()
    data["التاريخ"] = flexible_date_parser(data["التاريخ"])
    data = data.dropna(subset=["التاريخ"]).sort_values(["المعدة", "التاريخ"])
    if filter_text:
        data["الإجراء التصحيحي"] = data["الإجراء التصحيحي"].fillna("").astype(str)
        data = data[data["الإجراء التصحيحي"].str.contains(filter_text, case=False, na=False)]
    results = []
    for equipment in data["المعدة"].unique():
        eq_data = data[data["المعدة"] == equipment].copy()
        if len(eq_data) < 2:
            continue
        for i in range(len(eq_data)-1):
            gap_days = (eq_data.iloc[i+1]["التاريخ"] - eq_data.iloc[i]["التاريخ"]).total_seconds() / (24*3600)
            results.append({
                "المعدة": equipment,
                "الإجراء السابق": eq_data.iloc[i]["الإجراء التصحيحي"] if i>=0 else "---",
                "تاريخ الإجراء السابق": eq_data.iloc[i]["التاريخ"].strftime("%Y-%m-%d"),
                "الإجراء التالي": eq_data.iloc[i+1]["الإجراء التصحيحي"],
                "تاريخ الإجراء التالي": eq_data.iloc[i+1]["التاريخ"].strftime("%Y-%m-%d"),
                "المدة الزمنية (أيام)": round(gap_days, 1)
            })
    return pd.DataFrame(results)

def failures_analysis_tab(all_sheets):
    st.header("📊 تحليل الإجراءات التصحيحية المتكررة")
    if not all_sheets:
        st.warning("لا توجد بيانات")
        return
    all_section_names = [name for name in all_sheets.keys() if name not in [APP_CONFIG["SPARE_PARTS_SHEET"], APP_CONFIG["MAINTENANCE_SHEET"]]]
    if not all_section_names:
        st.warning("لا توجد أقسام")
        return
    selected_section = st.selectbox("اختر القسم:", all_section_names)
    df = all_sheets[selected_section].copy()
    if "المعدة" not in df.columns:
        st.error("لا يوجد عمود 'المعدة'")
        return
    equipment_list = sorted(df["المعدة"].dropna().unique())
    selected_equipment = st.selectbox("اختر الماكينة:", ["جميع الماكينات"] + equipment_list)
    col1, col2 = st.columns(2)
    start_date = col1.date_input("من تاريخ:", value=None)
    end_date = col2.date_input("إلى تاريخ:", value=None)
    search_text = st.text_input("كلمة البحث في الإجراء التصحيحي:")
    if st.button("تشغيل التحليل"):
        filtered = df.copy()
        if selected_equipment != "جميع الماكينات":
            filtered = filtered[filtered["المعدة"] == selected_equipment]
        if "التاريخ" in filtered.columns:
            filtered["التاريخ"] = flexible_date_parser(filtered["التاريخ"])
            filtered = filtered.dropna(subset=["التاريخ"])
            if start_date:
                filtered = filtered[filtered["التاريخ"] >= pd.to_datetime(start_date)]
            if end_date:
                filtered = filtered[filtered["التاريخ"] <= pd.to_datetime(end_date) + timedelta(days=1)]
        if filtered.empty:
            st.warning("لا توجد بيانات")
            return
        gaps = analyze_time_between_corrections(filtered, search_text if search_text else None)
        st.success(f"عدد الإجراءات: {len(filtered)}")
        if not gaps.empty:
            st.dataframe(gaps)
            csv = gaps.to_csv(index=False).encode('utf-8')
            st.download_button("تحميل CSV", csv, "gaps.csv", "text/csv")
        else:
            st.info("لا توجد فجوات زمنية كافية")

# ------------------------------- دوال المستخدمين والصلاحيات -------------------------------
def download_users_from_github():
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        for username, user_info in users_data.items():
            if "permissions" in user_info and isinstance(user_info["permissions"], list):
                user_info["permissions"] = {"all_sections": "all" in user_info["permissions"]}
                user_info["sections_permissions"] = {}
            elif "permissions" not in user_info:
                user_info["permissions"] = {"all_sections": False}
                user_info["sections_permissions"] = {}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        return users_data
    except:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

def load_users():
    try:
        users_data = download_users_from_github()
        if not users_data or "admin" not in users_data:
            default = {"admin": {"password": "1234", "role": "admin", "permissions": {"all_sections": True}, "sections_permissions": {}}}
            return default
        return users_data
    except:
        return {"admin": {"password": "1234", "role": "admin", "permissions": {"all_sections": True}, "sections_permissions": {}}}

def load_state():
    if not os.path.exists(STATE_FILE):
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
        return remaining if remaining.total_seconds() > 0 else None
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
    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول")
    username_input = st.selectbox("المستخدم", list(users.keys()))
    password = st.text_input("كلمة المرور", type="password")
    active_count = len([u for u, v in state.items() if v.get("active")])
    st.caption(f"المستخدمون النشطون: {active_count} / {MAX_ACTIVE_USERS}")
    if st.button("تسجيل الدخول"):
        current_users = load_users()
        if username_input in current_users and current_users[username_input]["password"] == password:
            if username_input != "admin" and username_input in [u for u,v in state.items() if v.get("active")]:
                st.warning("هذا المستخدم مسجل بالفعل")
                return False
            if active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                st.error("الحد الأقصى للمستخدمين")
                return False
            state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
            save_state(state)
            st.session_state.logged_in = True
            st.session_state.username = username_input
            st.session_state.user_role = current_users[username_input].get("role", "viewer")
            st.success(f"مرحباً {username_input}")
            st.rerun()
        else:
            st.error("كلمة مرور خاطئة")
    return st.session_state.logged_in

def get_user_permissions(username):
    users = load_users()
    if username not in users:
        return {"all_sections": False, "sections_permissions": {}}
    user_data = users[username]
    perms = user_data.get("permissions", {})
    if isinstance(perms, list):
        perms = {"all_sections": "all" in perms}
    return {"all_sections": perms.get("all_sections", False), "sections_permissions": user_data.get("sections_permissions", {})}

def has_section_permission(username, section_name, required="view"):
    if username == "admin":
        return True
    perms = get_user_permissions(username)
    if perms.get("all_sections"):
        return True
    section_perms = perms.get("sections_permissions", {}).get(section_name, [])
    return required in section_perms

def get_allowed_sections(all_sheets, username, required="view"):
    allowed = []
    for sheet_name in all_sheets.keys():
        if sheet_name in [APP_CONFIG["SPARE_PARTS_SHEET"], APP_CONFIG["MAINTENANCE_SHEET"]]:
            continue
        if has_section_permission(username, sheet_name, required):
            allowed.append(sheet_name)
    return allowed

# ------------------------------- دوال الملفات (تحميل، حفظ، رفع) -------------------------------
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
            sheets[name] = df.fillna('')
        return sheets
    except:
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
            sheets[name] = df.fillna('')
        return sheets
    except:
        return None

def save_excel_locally(sheets_dict):
    try:
        if "temp_spare_parts_df" in st.session_state:
            sheets_dict[APP_CONFIG["SPARE_PARTS_SHEET"]] = st.session_state.temp_spare_parts_df
            del st.session_state.temp_spare_parts_df
        if APP_CONFIG["MAINTENANCE_SHEET"] not in sheets_dict:
            sheets_dict[APP_CONFIG["MAINTENANCE_SHEET"]] = load_maintenance_tasks()
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                sh.to_excel(writer, sheet_name=name, index=False)
        return True
    except Exception as e:
        st.error(f"خطأ في الحفظ المحلي: {e}")
        return False

def push_to_github():
    if not GITHUB_AVAILABLE or not GITHUB_TOKEN:
        return False
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            repo.update_file(APP_CONFIG["FILE_PATH"], "تحديث البيانات", content, contents.sha, branch=APP_CONFIG["BRANCH"])
        except GithubException as e:
            if e.status == 404:
                repo.create_file(APP_CONFIG["FILE_PATH"], "إنشاء ملف", content, branch=APP_CONFIG["BRANCH"])
            else:
                raise
        return True
    except Exception as e:
        st.error(f"فشل الرفع: {e}")
        return False

# ------------------------------- دالة الحفظ مع دعم عدم الاتصال -------------------------------
def save_with_offline_support(sheets_edit, operation_name, operation_type, operation_data):
    if not save_excel_locally(sheets_edit):
        st.error("فشل الحفظ المحلي!")
        return False
    if is_github_accessible():
        if push_to_github():
            st.success(f"✅ {operation_name} - تم الرفع إلى GitHub")
            return True
        else:
            st.warning(f"⚠️ {operation_name} - فشل الرفع، تم الحفظ محلياً وسيتم إعادة المحاولة")
            add_pending_operation(operation_type, operation_data)
            return True
    else:
        st.info(f"📴 وضع عدم الاتصال: '{operation_name}' تم الحفظ محلياً، سيتم المزامنة لاحقاً")
        add_pending_operation(operation_type, operation_data)
        return True

def execute_pending_add_event(sheets_edit, data):
    sheet_name = data["sheet_name"]
    new_row = data["new_row"]
    if sheet_name not in sheets_edit:
        return False
    df = sheets_edit[sheet_name]
    sheets_edit[sheet_name] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return True

def sync_pending_operations(sheets_edit):
    if not is_github_accessible():
        st.warning("لا يوجد اتصال بالإنترنت")
        return sheets_edit
    pending = load_pending_operations()
    if not pending:
        return sheets_edit
    st.info(f"🔄 جاري مزامنة {len(pending)} عملية...")
    progress = st.progress(0)
    removed = []
    for i, op in enumerate(pending):
        success = False
        if op["type"] == "add_event":
            success = execute_pending_add_event(sheets_edit, op["data"])
        else:
            st.error(f"نوع غير معروف: {op['type']}")
        if success:
            removed.append(op["id"])
        else:
            op["retries"] += 1
            if op["retries"] >= 5:
                st.error(f"تم التخلي عن العملية {op['id']}")
                removed.append(op["id"])
        progress.progress((i+1)/len(pending))
    st.session_state.pending_operations = [op for op in pending if op["id"] not in removed]
    save_pending_operations()
    if save_excel_locally(sheets_edit) and push_to_github():
        st.success("✅ تمت المزامنة والرفع إلى GitHub")
    else:
        st.warning("⚠️ تمت المزامنة لكن فشل الرفع النهائي")
    return sheets_edit

# ------------------------------- دوال عرض البيانات -------------------------------
def get_equipment_list_from_sheet(df):
    if df is None or "المعدة" not in df.columns:
        return []
    return sorted([str(e).strip() for e in df["المعدة"].dropna().unique() if str(e).strip() != ""])

def display_sheet_data(sheet_name, df, unique_id, sheets_edit):
    st.markdown(f"### {sheet_name}")
    st.info(f"عدد الماكينات: {len(df)}")
    equipment_list = get_equipment_list_from_sheet(df)
    if equipment_list:
        selected = st.selectbox("فلتر ماكينة:", ["جميع الماكينات"] + equipment_list, key=f"filter_{unique_id}")
        if selected != "جميع الماكينات":
            df = df[df["المعدة"] == selected]
    st.dataframe(df.drop(columns=["رابط الصورة"], errors='ignore'), use_container_width=True)
    if "رابط الصورة" in df.columns:
        for idx, row in df.iterrows():
            if row["رابط الصورة"]:
                with st.expander(f"صورة الصف {idx+1}"):
                    st.image(row["رابط الصورة"])

def export_filtered_results_to_excel(df, sheet_name):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

def search_across_sheets(all_sheets):
    st.subheader("بحث متقدم")
    if not all_sheets:
        return
    search_type = st.selectbox("نوع البحث:", ["الأقسام (الأعطال)", "قطع الغيار", "الصيانة الوقائية"])
    username = st.session_state.get("username")
    allowed = get_allowed_sections(all_sheets, username, "view")
    if search_type == "الأقسام (الأعطال)":
        sheet_opt = ["جميع الأقسام"] + allowed
        selected_sheet = st.selectbox("القسم:", sheet_opt)
        equipment_list = []
        if selected_sheet != "جميع الأقسام":
            equipment_list = get_equipment_list_from_sheet(all_sheets[selected_sheet])
        else:
            all_eq = set()
            for sh in allowed:
                all_eq.update(get_equipment_list_from_sheet(all_sheets[sh]))
            equipment_list = sorted(all_eq)
        filter_eq = st.selectbox("الماكينة:", ["الكل"] + equipment_list)
        general_search = st.text_input("كلمة في الحدث/الإجراء:")
        tech_search = st.text_input("بحث بالفني:")
        use_date = st.checkbox("فلتر بالتاريخ")
        start_date = end_date = None
        if use_date:
            col1, col2 = st.columns(2)
            start_date = col1.date_input("من تاريخ:")
            end_date = col2.date_input("إلى تاريخ:")
        if st.button("بحث"):
            results = []
            sheets_to_search = [(selected_sheet, all_sheets[selected_sheet])] if selected_sheet != "جميع الأقسام" else [(sh, all_sheets[sh]) for sh in allowed]
            for sh_name, df in sheets_to_search:
                filtered = df.copy()
                if filter_eq != "الكل" and "المعدة" in filtered.columns:
                    filtered = filtered[filtered["المعدة"] == filter_eq]
                if "التاريخ" in filtered.columns:
                    filtered["التاريخ"] = flexible_date_parser(filtered["التاريخ"])
                    filtered = filtered.dropna(subset=["التاريخ"])
                    if use_date and start_date and end_date:
                        filtered = filtered[(filtered["التاريخ"] >= pd.to_datetime(start_date)) & (filtered["التاريخ"] <= pd.to_datetime(end_date)+timedelta(days=1))]
                if general_search:
                    mask = pd.Series([False]*len(filtered))
                    if "الحدث/العطل" in filtered.columns:
                        mask |= filtered["الحدث/العطل"].fillna("").astype(str).str.contains(general_search, case=False)
                    if "الإجراء التصحيحي" in filtered.columns:
                        mask |= filtered["الإجراء التصحيحي"].fillna("").astype(str).str.contains(general_search, case=False)
                    filtered = filtered[mask]
                if tech_search and "تم بواسطة" in filtered.columns:
                    filtered = filtered[filtered["تم بواسطة"].fillna("").astype(str).str.contains(tech_search, case=False)]
                if not filtered.empty:
                    filtered["القسم"] = sh_name
                    results.append(filtered)
            if results:
                combined = pd.concat(results)
                st.success(f"عدد النتائج: {len(combined)}")
                st.dataframe(combined)
                excel = export_filtered_results_to_excel(combined, "بحث")
                st.download_button("تحميل Excel", excel, "search.xlsx")
            else:
                st.warning("لا توجد نتائج")
    # قطع الغيار والصيانة الوقائية (اختصاراً)
    elif search_type == "قطع الغيار":
        df = load_spare_parts()
        if df.empty:
            st.warning("لا توجد قطع غيار")
            return
        search_term = st.text_input("كلمة البحث:")
        if search_term:
            mask = df["اسم القطعة"].fillna("").astype(str).str.contains(search_term, case=False)
            df = df[mask]
        st.dataframe(df)
    else:
        df = load_maintenance_tasks()
        if df.empty:
            st.warning("لا توجد مهام صيانة")
            return
        search_term = st.text_input("كلمة البحث:")
        if search_term:
            mask = df["اسم_البند"].fillna("").astype(str).str.contains(search_term, case=False)
            df = df[mask]
        st.dataframe(df)

# ------------------------------- دوال إدارة الأقسام والماكينات والأحداث -------------------------------
def add_new_department(sheets_edit):
    if st.session_state.get("username") != "admin":
        st.info("فقط المدير يمكنه إضافة أقسام")
        return sheets_edit
    st.subheader("إضافة قسم جديد")
    new_name = st.text_input("اسم القسم الجديد:")
    if st.button("إنشاء"):
        if new_name and new_name not in sheets_edit:
            sheets_edit[new_name] = pd.DataFrame(columns=APP_CONFIG["DEFAULT_SHEET_COLUMNS"])
            if save_and_push_to_github(sheets_edit, f"إنشاء قسم {new_name}"):
                st.success("تم إنشاء القسم")
                st.rerun()
    return sheets_edit

def add_new_event(sheets_edit, sheet_name):
    st.markdown(f"### إضافة حدث عطل - {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    if not equipment_list:
        st.warning("لا توجد ماكينات، أضف ماكينة أولاً")
        return sheets_edit

    if "selected_equipment_temp" not in st.session_state:
        st.session_state.selected_equipment_temp = equipment_list[0]
    selected_equipment = st.selectbox("الماكينة:", equipment_list, index=equipment_list.index(st.session_state.selected_equipment_temp))
    if selected_equipment != st.session_state.selected_equipment_temp:
        st.session_state.selected_equipment_temp = selected_equipment
        st.rerun()

    spare_parts = get_spare_parts_for_section(sheet_name)

    with st.form("add_event_form"):
        col1, col2 = st.columns(2)
        with col1:
            event_date = st.date_input("التاريخ:", datetime.now())
            repair_duration = st.number_input("مدة الإصلاح (ساعات):", 0.0, step=0.5)
            event_desc = st.text_area("الحدث/العطل:", height=100)
            fault_type = st.selectbox("نوع العطل:", ["", "ميكانيكي", "كهربائي", "هيدروليكي"])
            uploaded_image = st.file_uploader("صورة:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"])
        with col2:
            correction_desc = st.text_area("الإجراء التصحيحي:", height=100)
            servised_by = st.text_input("تم بواسطة:")
            technician_rating = st.slider("قدرة الفني:", 1, 5, 3)
            safety = st.selectbox("السلامة:", ["", "ملتزم", "غير ملتزم"])
            part_name = ""
            consume_qty = 0
            if spare_parts:
                selected_part = st.selectbox("قطعة غيار:", [""] + [f"{n} (الرصيد: {q})" for n,q in spare_parts])
                if selected_part:
                    part_name = selected_part.split(" (")[0]
                    current = next((q for n,q in spare_parts if n==part_name), 0)
                    consume_qty = st.number_input("الكمية:", 1, max(1, current), 1)
        submitted = st.form_submit_button("إضافة الحدث")
        if submitted:
            spare_used = ""
            warning = ""
            if part_name and consume_qty:
                success, msg, new_qty = consume_spare_part(part_name, consume_qty)
                if not success:
                    st.error(msg)
                    return sheets_edit
                spare_used = f"{part_name} (كمية {consume_qty})"
                if new_qty < 1 and any(c["اسم القطعة"]==part_name for c in get_critical_spare_parts()):
                    warning = f"⚠️ تحذير: القطعة {part_name} أصبح رصيدها {new_qty}"
            image_url = None
            if uploaded_image:
                if is_github_accessible():
                    image_url = upload_image_to_github(uploaded_image, "event", str(uuid.uuid4())[:8])
                else:
                    st.info("سيتم رفع الصورة لاحقاً")
            new_row = {
                "مده الاصلاح": repair_duration if repair_duration>0 else "",
                "التاريخ": event_date.strftime("%Y-%m-%d"),
                "المعدة": selected_equipment,
                "الحدث/العطل": event_desc,
                "الإجراء التصحيحي": correction_desc,
                "تم بواسطة": servised_by,
                "قطع غيار مستخدمة": spare_used,
                "نوع العطل": fault_type,
                "قدرة الفني (حل/تفكير/مبادرة/قرار)": technician_rating,
                "الالتزام بتعليمات السلامة": safety,
                "رابط الصورة": image_url or ""
            }
            for col in df.columns:
                if col not in new_row:
                    new_row[col] = ""
            sheets_edit[sheet_name] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            if "temp_spare_parts_df" in st.session_state:
                sheets_edit[APP_CONFIG["SPARE_PARTS_SHEET"]] = st.session_state.temp_spare_parts_df
                del st.session_state.temp_spare_parts_df
            offline_data = {
                "sheet_name": sheet_name,
                "new_row": new_row,
                "part_name": part_name,
                "consume_qty": consume_qty,
                "image_url": image_url,
                "event_desc": event_desc[:50],
                "selected_equipment": selected_equipment,
                "warning_msg": warning
            }
            if save_with_offline_support(sheets_edit, f"إضافة حدث {selected_equipment}", "add_event", offline_data):
                st.cache_data.clear()
                log_activity("add_event", f"تم إضافة عطل: {event_desc[:50]} للماكينة {selected_equipment}")
                if warning:
                    st.warning(warning)
                st.rerun()
    return sheets_edit

def manage_machines(sheets_edit, sheet_name):
    st.markdown(f"### إدارة الماكينات - {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    st.write("الماكينات الحالية:", equipment_list if equipment_list else "لا توجد")
    new_machine = st.text_input("ماكينة جديدة:")
    if st.button("إضافة"):
        if new_machine and new_machine not in equipment_list:
            new_row = {col: "" for col in df.columns}
            new_row["المعدة"] = new_machine
            sheets_edit[sheet_name] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            if save_with_offline_support(sheets_edit, f"إضافة ماكينة {new_machine}", "add_machine", {"sheet_name": sheet_name, "new_machine": new_machine}):
                st.rerun()
    return sheets_edit

def manage_spare_parts_tab(sheets_edit):
    st.header("قطع الغيار")
    username = st.session_state.get("username")
    all_sheets = load_all_sheets()
    allowed = get_allowed_sections(all_sheets, username, "view")
    if APP_CONFIG["GENERAL_SECTION"] not in allowed:
        allowed.insert(0, APP_CONFIG["GENERAL_SECTION"])
    selected_section = st.selectbox("القسم:", allowed)
    spare_df = load_spare_parts()
    filtered = spare_df[spare_df["القسم"] == selected_section].copy()
    st.dataframe(filtered)
    with st.form("add_spare"):
        name = st.text_input("اسم القطعة")
        size = st.text_input("المقاس")
        qty = st.number_input("الرصيد", 0, step=1)
        lead = st.text_input("مدة التوريد")
        critical = st.checkbox("ضرورية")
        threshold = st.number_input("حد الإنذار", 1, step=1)
        if st.form_submit_button("إضافة"):
            new_row = pd.DataFrame([{
                "اسم القطعة": name, "المقاس": size, "الرصيد الموجود": qty,
                "مدة التوريد": lead, "ضرورية": "نعم" if critical else "لا",
                "القسم": selected_section, "حد_الإنذار": threshold, "رابط_الصورة": ""
            }])
            new_df = pd.concat([spare_df, new_row], ignore_index=True)
            sheets_edit[APP_CONFIG["SPARE_PARTS_SHEET"]] = new_df
            offline_data = {"section": selected_section, "new_row": new_row.to_dict()}
            if save_with_offline_support(sheets_edit, f"إضافة قطعة {name}", "add_spare_part", offline_data):
                st.rerun()
    return sheets_edit

def preventive_maintenance_tab(sheets_edit):
    st.header("الصيانة الوقائية")
    # تبسيط: عرض وإضافة مهام (يمكن توسيعه)
    maint_df = sheets_edit.get(APP_CONFIG["MAINTENANCE_SHEET"], load_maintenance_tasks())
    st.dataframe(maint_df)
    return sheets_edit

def manage_data_edit(sheets_edit):
    if sheets_edit is None:
        st.warning("لا يوجد ملف")
        return sheets_edit
    if APP_CONFIG["SPARE_PARTS_SHEET"] not in sheets_edit:
        sheets_edit[APP_CONFIG["SPARE_PARTS_SHEET"]] = load_spare_parts()
    if APP_CONFIG["MAINTENANCE_SHEET"] not in sheets_edit:
        sheets_edit[APP_CONFIG["MAINTENANCE_SHEET"]] = load_maintenance_tasks()
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["عرض الأقسام", "إضافة حدث", "إدارة الماكينات", "إضافة قسم", "قطع الغيار", "الصيانة الوقائية"])
    with tab1:
        depts = [n for n in sheets_edit.keys() if n not in [APP_CONFIG["SPARE_PARTS_SHEET"], APP_CONFIG["MAINTENANCE_SHEET"]]]
        if depts:
            for d in depts:
                with st.expander(d):
                    display_sheet_data(d, sheets_edit[d], d, sheets_edit)
    with tab2:
        if depts:
            sel = st.selectbox("اختر القسم:", depts, key="event_sheet")
            sheets_edit = add_new_event(sheets_edit, sel)
    with tab3:
        if depts:
            sel = st.selectbox("القسم:", depts, key="machine_sheet")
            sheets_edit = manage_machines(sheets_edit, sel)
    with tab4:
        sheets_edit = add_new_department(sheets_edit)
    with tab5:
        sheets_edit = manage_spare_parts_tab(sheets_edit)
    with tab6:
        sheets_edit = preventive_maintenance_tab(sheets_edit)
    return sheets_edit

# ------------------------------- الواجهة الرئيسية -------------------------------
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
        if st.button("🔄 تحديث"):
            if fetch_from_github_requests():
                st.rerun()
        if st.button("🗑️ مسح الكاش"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        # عرض العمليات المعلقة
        pending = load_pending_operations()
        if pending:
            st.markdown("---")
            st.warning(f"⏳ عمليات معلقة: {len(pending)}")
            if st.button("🔄 مزامنة الآن"):
                sheets_edit = load_sheets_for_edit()
                sheets_edit = sync_pending_operations(sheets_edit)
                st.rerun()
            with st.expander("تفاصيل"):
                for op in pending:
                    st.write(f"{op['type']} - {op['timestamp'][:16]} (محاولات {op['retries']})")
                    if st.button(f"حذف {op['id'][:8]}", key=f"del_{op['id']}"):
                        remove_pending_operation(op['id'])
                        st.rerun()

# ------------------------------- تحميل البيانات والمزامنة التلقائية -------------------------------
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()
if is_github_accessible() and load_pending_operations():
    sheets_edit = sync_pending_operations(sheets_edit)

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
user_role = st.session_state.get("user_role", "viewer")
can_edit = user_role == "admin" or user_role == "editor"

tabs = st.tabs(["🔍 بحث متقدم", "📊 تحليل الأعطال", "🔔 الإشعارات"] + (["🛠 تعديل البيانات"] if can_edit else []))
with tabs[0]:
    search_across_sheets(all_sheets)
with tabs[1]:
    failures_analysis_tab(all_sheets)
with tabs[2]:
    st.header("الإشعارات")
    if st.session_state.get("username") == "admin":
        st.subheader("آخر النشاطات")
        # تبسيط: عرض آخر 10 نشاطات من الملف المحلي
        if os.path.exists(ACTIVITY_LOG_FILE):
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)[-10:]
                for l in logs:
                    st.info(f"{l['timestamp'][:16]} - {l['username']}: {l['details']}")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("قطع غيار حرجة")
        critical = get_critical_spare_parts()
        if critical:
            for p in critical:
                st.error(f"{p['اسم القطعة']} (رصيد {p['الرصيد الموجود']} < {p['حد_الإنذار']})")
        else:
            st.success("لا توجد قطع حرجة")
    with col2:
        st.subheader("صيانة مستحقة")
        overdue, upcoming = get_upcoming_maintenance(3)
        if not overdue.empty:
            for _, row in overdue.iterrows():
                st.warning(f"{row['المعدة']} - {row['اسم_البند']} (مستحق {row['التاريخ_التالي'].date()})")
        else:
            st.info("لا توجد صيانات متأخرة")

if can_edit and len(tabs) > 3:
    with tabs[3]:
        sheets_edit = manage_data_edit(sheets_edit)
