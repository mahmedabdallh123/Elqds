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
    "FILE_PATH": "2.xlsx",
    "LOCAL_FILE": "2.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "DEFAULT_SHEET_COLUMNS": ["التاريخ", "المعدة", "اسم قطعه الغيار", "المقاس", "العدد ف معده", "نوع التشحيم", "الكميه", "عدد ساعات التشغيل"],
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]
EQUIPMENT_CONFIG_FILE = "equipment_config.json"

GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# ------------------------------- دوال تصدير البيانات -------------------------------
def export_sheet_to_excel(sheets_dict, sheet_name):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df = sheets_dict[sheet_name]
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

def export_all_sheets_to_excel(sheets_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

def export_filtered_results_to_excel(results_df, sheet_name):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

# ------------------------------- دوال إدارة المعدات -------------------------------
def load_equipment_config():
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
    try:
        with open(EQUIPMENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"خطأ في حفظ تكوين المعدات: {e}")
        return False

def get_equipment_list_from_sheet(df):
    if df is None or df.empty or "المعدة" not in df.columns:
        return []
    equipment = df["المعدة"].dropna().unique()
    equipment = [str(e).strip() for e in equipment if str(e).strip() != ""]
    return sorted(equipment)

def add_equipment_to_sheet_data(sheets_edit, sheet_name, new_equipment):
    if sheet_name not in sheets_edit:
        return False, "القسم غير موجود"
    
    df = sheets_edit[sheet_name]
    if "المعدة" not in df.columns:
        return False, "عمود 'المعدة' غير موجود في هذا القسم"
    
    existing = get_equipment_list_from_sheet(df)
    if new_equipment in existing:
        return False, f"الماكينة '{new_equipment}' موجودة بالفعل في هذا القسم"
    
    new_row = {col: "" for col in df.columns}
    new_row["المعدة"] = new_equipment
    new_row_df = pd.DataFrame([new_row])
    sheets_edit[sheet_name] = pd.concat([df, new_row_df], ignore_index=True)
    
    return True, f"تم إضافة الماكينة '{new_equipment}' بنجاح إلى قسم {sheet_name}"

def remove_equipment_from_sheet_data(sheets_edit, sheet_name, equipment_name):
    if sheet_name not in sheets_edit:
        return False, "القسم غير موجود"
    df = sheets_edit[sheet_name]
    if "المعدة" not in df.columns:
        return False, "عمود 'المعدة' غير موجود"
    if equipment_name not in get_equipment_list_from_sheet(df):
        return False, "الماكينة غير موجودة"
    
    new_df = df[df["المعدة"] != equipment_name]
    sheets_edit[sheet_name] = new_df
    return True, f"تم حذف جميع سجلات الماكينة '{equipment_name}'"

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
            st.error("❌ لم يتم العثور على GitHub token")
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
    except Exception as e:
        st.error(f"❌ فشل رفع المستخدمين: {e}")
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

# ------------------------------- دوال الملفات (المعدلة) -------------------------------
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
        st.error(f"خطأ في تحميل الأقسام: {e}")
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
        st.error(f"خطأ في تحميل الأقسام: {e}")
        return None

def save_excel_locally(sheets_dict):
    """حفظ ملف Excel محلياً فقط"""
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في الحفظ المحلي: {e}")
        return False

def push_to_github():
    """رفع الملف المحلي إلى GitHub"""
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.error("❌ لم يتم العثور على GitHub token في secrets")
            return False
        
        if not GITHUB_AVAILABLE:
            st.error("❌ PyGithub غير متوفر")
            return False
        
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            result = repo.update_file(
                path=APP_CONFIG["FILE_PATH"],
                message=f"تحديث البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                content=content,
                sha=contents.sha,
                branch=APP_CONFIG["BRANCH"]
            )
            st.success(f"✅ تم رفع التغييرات إلى GitHub بنجاح!")
            return True
        except GithubException as e:
            if e.status == 404:
                result = repo.create_file(
                    path=APP_CONFIG["FILE_PATH"],
                    message=f"إنشاء ملف جديد - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content,
                    branch=APP_CONFIG["BRANCH"]
                )
                st.success(f"✅ تم إنشاء الملف على GitHub بنجاح!")
                return True
            else:
                st.error(f"❌ خطأ في GitHub: {e}")
                return False
    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {str(e)}")
        return False

def save_and_push_to_github(sheets_dict, operation_name):
    """حفظ محلياً ثم رفع إلى GitHub"""
    st.info(f"💾 جاري حفظ {operation_name}...")
    
    if save_excel_locally(sheets_dict):
        st.success("✅ تم الحفظ محلياً")
        
        if push_to_github():
            st.success("✅ تم الرفع إلى GitHub")
            st.cache_data.clear()
            return True
        else:
            st.warning("⚠️ تم الحفظ محلياً فقط، فشل الرفع إلى GitHub")
            return True
    else:
        st.error("❌ فشل الحفظ المحلي")
        return False

# ------------------------------- دوال العرض -------------------------------
def display_sheet_data(sheet_name, df, unique_id, sheets_edit):
    st.markdown(f"### 🏭 {sheet_name}")
    st.info(f"عدد الماكينات المسجلة: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    equipment_list = get_equipment_list_from_sheet(df)
    if equipment_list and "المعدة" in df.columns:
        st.markdown("#### 🔍 فلتر حسب الماكينة:")
        selected_filter = st.selectbox(
            "اختر الماكينة:", 
            ["جميع الماكينات"] + equipment_list,
            key=f"filter_{unique_id}"
        )
        if selected_filter != "جميع الماكينات":
            df = df[df["المعدة"] == selected_filter]
            st.info(f"عرض لماكينة: {selected_filter} - السجلات: {len(df)}")
    
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype == 'object':
            display_df[col] = display_df[col].astype(str).apply(lambda x: x[:100] + "..." if len(x) > 100 else x)
    st.dataframe(display_df, use_container_width=True, height=400)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        excel_file = export_sheet_to_excel({sheet_name: df}, sheet_name)
        st.download_button(
            "📥 تحميل بيانات هذا القسم كملف Excel",
            excel_file,
            f"{sheet_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_sheet_{unique_id}"
        )
    with col_btn2:
        all_sheets_excel = export_all_sheets_to_excel({sheet_name: df})
        st.download_button(
            "📥 تحميل جميع البيانات كملف Excel",
            all_sheets_excel,
            f"all_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_all_{unique_id}"
        )

def search_across_sheets(all_sheets):
    st.subheader("بحث متقدم في السجلات")
    
    if not all_sheets:
        st.warning("لا توجد بيانات للبحث")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        sheet_options = ["جميع الأقسام"] + list(all_sheets.keys())
        selected_sheet = st.selectbox("اختر القسم للبحث:", sheet_options, key="search_sheet")
        
        if selected_sheet != "جميع الأقسام":
            df_temp = all_sheets[selected_sheet]
            equipment_list = get_equipment_list_from_sheet(df_temp)
        else:
            all_eq = set()
            for sh_name, sh_df in all_sheets.items():
                all_eq.update(get_equipment_list_from_sheet(sh_df))
            equipment_list = sorted(all_eq)
        
        filter_equipment = st.selectbox("فلتر حسب الماكينة:", ["الكل"] + equipment_list, key="search_eq")
        search_term = st.text_input("كلمة البحث:", placeholder="أدخل نصاً للبحث...", key="search_term")
    
    with col2:
        st.markdown("#### نطاق التاريخ")
        use_date_filter = st.checkbox("تفعيل البحث بالتاريخ", key="use_date_filter")
        if use_date_filter:
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("من تاريخ:", value=datetime.now() - timedelta(days=30), key="start_date")
            with col_date2:
                end_date = st.date_input("إلى تاريخ:", value=datetime.now(), key="end_date")
        else:
            start_date = None
            end_date = None
        search_in_notes = st.checkbox("البحث في الملاحظات أيضاً", value=True, key="search_notes")
    
    if st.button("بحث", key="search_btn", type="primary"):
        results = []
        sheets_to_search = all_sheets.items()
        if selected_sheet != "جميع الأقسام":
            sheets_to_search = [(selected_sheet, all_sheets[selected_sheet])]
        
        for sheet_name, df in sheets_to_search:
            df_filtered = df.copy()
            if filter_equipment != "الكل" and "المعدة" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["المعدة"] == filter_equipment]
            if use_date_filter and start_date and end_date and "التاريخ" in df_filtered.columns:
                try:
                    df_filtered["التاريخ"] = pd.to_datetime(df_filtered["التاريخ"], errors='coerce')
                    mask = (df_filtered["التاريخ"].dt.date >= start_date) & (df_filtered["التاريخ"].dt.date <= end_date)
                    df_filtered = df_filtered[mask]
                except:
                    pass
            if search_term:
                search_columns = ["اسم قطعه الغيار", "نوع التشحيم", "ملاحظات"] if "ملاحظات" in df_filtered.columns else ["اسم قطعه الغيار", "نوع التشحيم"]
                mask = pd.Series([False] * len(df_filtered))
                for col in search_columns:
                    if col in df_filtered.columns:
                        mask = mask | df_filtered[col].astype(str).str.contains(search_term, case=False, na=False)
                df_filtered = df_filtered[mask]
            if not df_filtered.empty:
                df_filtered["القسم"] = sheet_name
                results.append(df_filtered)
        
        if results:
            combined_results = pd.concat(results, ignore_index=True)
            st.success(f"تم العثور على {len(combined_results)} نتيجة")
            st.dataframe(combined_results, use_container_width=True, height=500)
            
            excel_file = export_filtered_results_to_excel(combined_results, "نتائج_البحث")
            st.download_button(
                "📥 تحميل نتائج البحث كملف Excel",
                excel_file,
                f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key='download-excel'
            )
        else:
            st.warning("لا توجد نتائج مطابقة للبحث")

# ==================== دوال إضافة البيانات (معدلة) ====================
def add_new_data_entry(sheets_edit, sheet_name):
    """إضافة بيانات جديدة (بدلاً من حدث عطل)"""
    st.markdown(f"### 📝 إضافة بيانات جديدة في قسم: {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    
    if not equipment_list:
        st.warning("⚠ لا توجد ماكينات مسجلة في هذا القسم. يرجى إضافة ماكينة أولاً من تبويب 'إدارة الماكينات'")
        return sheets_edit
    
    with st.form(key="add_data_form"):
        st.markdown("#### 📋 بيانات الصيانة")
        
        col1, col2 = st.columns(2)
        with col1:
            selected_equipment = st.selectbox("🔧 الماكينة:", equipment_list)
            event_date = st.date_input("📅 التاريخ:", value=datetime.now())
            spare_part = st.text_input("🔩 اسم قطعه الغيار:", placeholder="مثال: فلتر زيت, سير, محمل...")
            size = st.text_input("📏 المقاس:", placeholder="مثال: 20x30, M12, 5/8...")
        
        with col2:
            quantity_in_equipment = st.number_input("🔢 العدد ف معده:", min_value=0, step=1, value=0)
            lubrication_type = st.text_input("🛢️ نوع التشحيم:", placeholder="مثال: زيت 10W40, شحم, زيت هيدروليك...")
            quantity = st.number_input("📦 الكميه:", min_value=0.0, step=0.1, value=0.0)
            operating_hours = st.number_input("⏱️ عدد ساعات التشغيل:", min_value=0.0, step=0.5, value=0.0)
        
        notes = st.text_area("📝 ملاحظات إضافية:", height=80, placeholder="أي ملاحظات إضافية...")
        
        submitted = st.form_submit_button("✅ إضافة البيانات", type="primary")
        
        if submitted:
            new_row = {
                "التاريخ": event_date.strftime("%Y-%m-%d"),
                "المعدة": selected_equipment,
                "اسم قطعه الغيار": spare_part,
                "المقاس": size,
                "العدد ف معده": quantity_in_equipment,
                "نوع التشحيم": lubrication_type,
                "الكميه": quantity,
                "عدد ساعات التشغيل": operating_hours,
                "ملاحظات": notes
            }
            
            # إضافة أي أعمدة موجودة في DataFrame ولكن ليست في new_row
            for col in df.columns:
                if col not in new_row:
                    new_row[col] = ""
            
            new_row_df = pd.DataFrame([new_row])
            df_new = pd.concat([df, new_row_df], ignore_index=True)
            sheets_edit[sheet_name] = df_new
            
            if save_and_push_to_github(sheets_edit, f"إضافة بيانات جديدة في قسم {sheet_name} للماكينة {selected_equipment}"):
                st.cache_data.clear()
                st.success("✅ تم إضافة البيانات بنجاح ورفعها إلى GitHub!")
                st.rerun()
            else:
                st.error("❌ فشل الحفظ")
    
    return sheets_edit

def add_new_department(sheets_edit):
    """إضافة قسم جديد (شيت جديد)"""
    st.subheader("➕ إضافة قسم جديد")
    st.info("سيتم إنشاء قسم جديد (شيت جديد) في ملف Excel لإدارة ماكينات هذا القسم")
    
    col1, col2 = st.columns(2)
    with col1:
        new_department_name = st.text_input("📝 اسم القسم الجديد:", key="new_department_name",
                                            placeholder="مثال: قسم الميكانيكا, قسم الكهرباء, محطة المياه")
        if new_department_name and new_department_name in sheets_edit:
            st.error(f"❌ القسم '{new_department_name}' موجود بالفعل!")
        elif new_department_name:
            st.success(f"✅ اسم القسم '{new_department_name}' متاح")
    with col2:
        st.markdown("#### 📋 إعدادات الأعمدة")
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
    st.markdown("### 📋 معاينة القسم الجديد")
    preview_df = pd.DataFrame(columns=columns_list)
    st.dataframe(preview_df, use_container_width=True)
    st.caption(f"📊 عدد الأعمدة: {len(columns_list)} | سيتم إنشاء قسم فارغ بهذه الأعمدة")
    
    if st.button("✅ إنشاء وإضافة القسم الجديد", key="create_department_btn", type="primary", use_container_width=True):
        if not new_department_name:
            st.error("❌ الرجاء إدخال اسم القسم")
            return sheets_edit
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', new_department_name.strip())
        if clean_name != new_department_name:
            st.warning(f"⚠ تم تعديل اسم القسم إلى: {clean_name}")
            new_department_name = clean_name
        if new_department_name in sheets_edit:
            st.error(f"❌ القسم '{new_department_name}' موجود بالفعل!")
            return sheets_edit
        
        new_df = pd.DataFrame(columns=columns_list)
        sheets_edit[new_department_name] = new_df
        
        if save_and_push_to_github(sheets_edit, f"إنشاء قسم جديد: {new_department_name}"):
            st.success(f"✅ تم إنشاء القسم '{new_department_name}' بنجاح!")
            st.cache_data.clear()
            st.balloons()
            st.rerun()
        else:
            st.error("❌ فشل حفظ القسم")
            return sheets_edit
    
    st.markdown("---")
    st.markdown("### 📋 الأقسام الموجودة حالياً:")
    if sheets_edit:
        for dept_name in sheets_edit.keys():
            st.write(f"- 🏭 {dept_name}")
    else:
        st.info("لا توجد أقسام بعد")
    return sheets_edit

def add_new_machine(sheets_edit, sheet_name):
    """إضافة ماكينة جديدة داخل قسم"""
    st.markdown(f"### 🔧 إضافة ماكينة جديدة في قسم: {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    
    st.markdown(f"**الماكينات الموجودة حالياً في هذا القسم:**")
    if equipment_list:
        for eq in equipment_list:
            st.markdown(f"- 🔹 {eq}")
    else:
        st.info("لا توجد ماكينات مسجلة بعد في هذا القسم")
    
    st.markdown("---")
    
    new_machine = st.text_input("📝 اسم الماكينة الجديدة:", key=f"new_machine_{sheet_name}",
                                 placeholder="مثال: محرك رئيسي 1, مضخة مياه, ضاغط هواء")
    
    if st.button("➕ إضافة ماكينة", key=f"add_machine_{sheet_name}", type="primary"):
        if new_machine:
            success, msg = add_equipment_to_sheet_data(sheets_edit, sheet_name, new_machine)
            if success:
                if save_and_push_to_github(sheets_edit, f"إضافة ماكينة جديدة: {new_machine} في قسم {sheet_name}"):
                    st.success(msg)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("فشل الحفظ")
            else:
                st.error(msg)
        else:
            st.warning("يرجى إدخال اسم الماكينة")
    
    return sheets_edit

def manage_machines(sheets_edit, sheet_name):
    """إدارة الماكينات داخل قسم - عرض، إضافة، حذف"""
    st.markdown(f"### 🔧 إدارة الماكينات في قسم: {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    
    if equipment_list:
        st.markdown("#### 📋 قائمة الماكينات في هذا القسم:")
        for eq in equipment_list:
            st.markdown(f"- 🔹 {eq}")
    else:
        st.info("لا توجد ماكينات مسجلة في هذا القسم بعد")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        new_machine = st.text_input("➕ اسم الماكينة الجديدة:", key=f"new_machine_{sheet_name}")
        if st.button("➕ إضافة ماكينة", key=f"add_machine_{sheet_name}"):
            if new_machine:
                success, msg = add_equipment_to_sheet_data(sheets_edit, sheet_name, new_machine)
                if success:
                    if save_and_push_to_github(sheets_edit, f"إضافة ماكينة: {new_machine} في قسم {sheet_name}"):
                        st.success(msg)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("فشل الحفظ")
                else:
                    st.error(msg)
            else:
                st.warning("يرجى إدخال اسم الماكينة")
    with col2:
        if equipment_list:
            machine_to_delete = st.selectbox("🗑️ اختر الماكينة للحذف:", equipment_list, key=f"delete_machine_{sheet_name}")
            st.warning("⚠️ تحذير: حذف الماكينة سيؤدي إلى حذف جميع سجلات البيانات المرتبطة بها نهائياً!")
            if st.button("🗑️ حذف الماكينة نهائياً", key=f"delete_machine_btn_{sheet_name}"):
                success, msg = remove_equipment_from_sheet_data(sheets_edit, sheet_name, machine_to_delete)
                if success:
                    if save_and_push_to_github(sheets_edit, f"حذف ماكينة: {machine_to_delete} من قسم {sheet_name}"):
                        st.success(msg)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("فشل الحفظ")
                else:
                    st.error(msg)

def manage_data_edit(sheets_edit):
    if sheets_edit is None:
        st.warning("الملف غير موجود. استخدم زر 'تحديث من GitHub' في الشريط الجانبي أولاً")
        return sheets_edit
    
    tab_names = ["📋 عرض الأقسام", "📝 إضافة بيانات", "🔧 إدارة الماكينات", "➕ إضافة قسم جديد"]
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        st.subheader("جميع الأقسام")
        if sheets_edit:
            dept_tabs = st.tabs(list(sheets_edit.keys()))
            for i, (dept_name, df) in enumerate(sheets_edit.items()):
                with dept_tabs[i]:
                    display_sheet_data(dept_name, df, f"view_{dept_name}", sheets_edit)
                    with st.expander("✏️ تعديل مباشر للبيانات", expanded=False):
                        edited_df = st.data_editor(df.astype(str), num_rows="dynamic", use_container_width=True, key=f"editor_{dept_name}")
                        if st.button(f"💾 حفظ", key=f"save_{dept_name}"):
                            sheets_edit[dept_name] = edited_df.astype(object)
                            if save_and_push_to_github(sheets_edit, f"تعديل بيانات في قسم {dept_name}"):
                                st.cache_data.clear()
                                st.success("تم الحفظ والرفع إلى GitHub!")
                                st.rerun()
    
    with tabs_edit[1]:
        if sheets_edit:
            sheet_name = st.selectbox("اختر القسم:", list(sheets_edit.keys()), key="add_data_sheet")
            sheets_edit = add_new_data_entry(sheets_edit, sheet_name)
    
    with tabs_edit[2]:
        if sheets_edit:
            sheet_name = st.selectbox("اختر القسم:", list(sheets_edit.keys()), key="manage_machines_sheet")
            manage_machines(sheets_edit, sheet_name)
    
    with tabs_edit[3]:
        sheets_edit = add_new_department(sheets_edit)
    
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

tabs_list = ["🔍 بحث متقدم"]
if can_edit:
    tabs_list.append("🛠 تعديل وإدارة البيانات")

tabs = st.tabs(tabs_list)

with tabs[0]:
    search_across_sheets(all_sheets)

if can_edit and len(tabs) > 1:
    with tabs[1]:
        sheets_edit = manage_data_edit(sheets_edit)
