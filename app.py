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
import plotly.graph_objects as go
from github import Github, GithubException

# إعدادات التطبيق
APP_CONFIG = {
    "APP_TITLE": "نظام إدارة التشحيم والزيوت - Lubrication CMMS",
    "APP_ICON": "🛢️",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "lubrication_data.xlsx",
    "LOCAL_FILE": "lubrication_data.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "DEFAULT_LUBRICATION_COLUMNS": [
        "المعدة", "نوع المادة", "الكمية (لتر/جرام)", "تاريخ التشحيم", 
        "التاريخ القادم", "عدد الأيام المتبقية", "تم بواسطة", "ملاحظات", 
        "المدة (أيام)", "آخر كمية", "حالة التشحيم"
    ],
    "LUBRICATION_TYPES": ["زيت محرك", "زيت هيدروليك", "زيت تروس", "شحم عام", "شحم عالي الحرارة", "زيت فرامل", "سائل تبريد"],
    "DEFAULT_INTERVALS": {
        "زيت محرك": 90,
        "زيت هيدروليك": 180,
        "زيت تروس": 365,
        "شحم عام": 60,
        "شحم عالي الحرارة": 45,
        "زيت فرامل": 365,
        "سائل تبريد": 365
    }
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

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

# ------------------------------- دوال إدارة البيانات -------------------------------
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        st.cache_data.clear()
        return True
    except Exception as e:
        create_initial_file()
        return True

def create_initial_file():
    try:
        initial_df = pd.DataFrame(columns=APP_CONFIG["DEFAULT_LUBRICATION_COLUMNS"])
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            initial_df.to_excel(writer, sheet_name="سجل التشحيم", index=False)
        return True
    except:
        return False

@st.cache_data(show_spinner=False)
def load_lubrication_data():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        create_initial_file()
        return pd.DataFrame(columns=APP_CONFIG["DEFAULT_LUBRICATION_COLUMNS"])
    try:
        df = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name="سجل التشحيم")
        df = df.fillna('')
        return df
    except:
        return pd.DataFrame(columns=APP_CONFIG["DEFAULT_LUBRICATION_COLUMNS"])

def save_to_github(df, commit_message):
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.error("❌ لم يتم العثور على GitHub token في secrets")
            return False
        
        temp_file = APP_CONFIG["LOCAL_FILE"]
        try:
            with pd.ExcelWriter(temp_file, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="سجل التشحيم", index=False)
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
                return True
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=APP_CONFIG["FILE_PATH"],
                        message=commit_message,
                        content=content,
                        branch=APP_CONFIG["BRANCH"]
                    )
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

# ------------------------------- دوال إدارة الماكينات والتشحيم -------------------------------
def get_machines_list(df):
    if df.empty or "المعدة" not in df.columns:
        return []
    machines = df["المعدة"].dropna().unique()
    machines = [str(m).strip() for m in machines if str(m).strip() != ""]
    return sorted(machines)

def add_new_machine(df, machine_name, lubrication_type, interval_days):
    if machine_name in get_machines_list(df):
        return df, False, f"الماكينة '{machine_name}' موجودة بالفعل!"
    
    new_record = {
        "المعدة": machine_name,
        "نوع المادة": lubrication_type,
        "الكمية (لتر/جرام)": "",
        "تاريخ التشحيم": "",
        "التاريخ القادم": "",
        "عدد الأيام المتبقية": "",
        "تم بواسطة": "",
        "ملاحظات": f"مدة التشحيم: {interval_days} يوم",
        "المدة (أيام)": interval_days,
        "آخر كمية": "",
        "حالة التشحيم": "جديد - يحتاج تشحيم"
    }
    new_df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    return new_df, True, f"تم إضافة الماكينة '{machine_name}' بنجاح"

def update_lubrication(df, machine_name, lubrication_date, quantity, notes, username):
    mask = df["المعدة"] == machine_name
    if not mask.any():
        return df, False, "الماكينة غير موجودة"
    
    lubrication_type = df.loc[mask, "نوع المادة"].iloc[0]
    interval_days = df.loc[mask, "المدة (أيام)"].iloc[0]
    
    if pd.isna(interval_days) or interval_days == "":
        interval_days = APP_CONFIG["DEFAULT_INTERVALS"].get(lubrication_type, 90)
    
    next_date = lubrication_date + timedelta(days=int(interval_days))
    days_remaining = int(interval_days)
    
    df.loc[mask, "تاريخ التشحيم"] = lubrication_date.strftime("%Y-%m-%d")
    df.loc[mask, "التاريخ القادم"] = next_date.strftime("%Y-%m-%d")
    df.loc[mask, "عدد الأيام المتبقية"] = days_remaining
    df.loc[mask, "تم بواسطة"] = username
    df.loc[mask, "الكمية (لتر/جرام)"] = quantity
    df.loc[mask, "آخر كمية"] = quantity
    df.loc[mask, "ملاحظات"] = notes if notes else f"آخر تشحيم: {lubrication_date.strftime('%Y-%m-%d')}"
    
    if days_remaining <= 0:
        df.loc[mask, "حالة التشحيم"] = "⚠️ متأخر - يحتاج تشحيم فوري"
    elif days_remaining <= 7:
        df.loc[mask, "حالة التشحيم"] = "⚠️ ينتهي قريباً - متبقي {} أيام".format(days_remaining)
    else:
        df.loc[mask, "حالة التشحيم"] = "✅ سليم - متبقي {} أيام".format(days_remaining)
    
    return df, True, f"تم تسجيل تشحيم الماكينة '{machine_name}' بنجاح"

def update_daily_counters(df):
    if df.empty:
        return df
    
    today = datetime.now().date()
    df = df.copy()
    
    for idx, row in df.iterrows():
        next_date_str = row.get("التاريخ القادم", "")
        if next_date_str and next_date_str != "":
            try:
                next_date = datetime.strptime(str(next_date_str), "%Y-%m-%d").date()
                days_remaining = (next_date - today).days
                df.loc[idx, "عدد الأيام المتبقية"] = days_remaining
                
                if days_remaining < 0:
                    df.loc[idx, "حالة التشحيم"] = "🔴 متأخر - يحتاج تشحيم فوري"
                elif days_remaining == 0:
                    df.loc[idx, "حالة التشحيم"] = "🟠 يجب التشحيم اليوم"
                elif days_remaining <= 7:
                    df.loc[idx, "حالة التشحيم"] = "🟡 ينتهي قريباً - متبقي {} أيام".format(days_remaining)
                else:
                    df.loc[idx, "حالة التشحيم"] = "🟢 سليم - متبقي {} أيام".format(days_remaining)
            except:
                pass
    
    return df

def get_overdue_machines(df):
    if df.empty:
        return pd.DataFrame()
    
    today = datetime.now().date()
    overdue = []
    
    for idx, row in df.iterrows():
        next_date_str = row.get("التاريخ القادم", "")
        if next_date_str and next_date_str != "":
            try:
                next_date = datetime.strptime(str(next_date_str), "%Y-%m-%d").date()
                if next_date < today:
                    overdue.append(row)
            except:
                pass
    
    return pd.DataFrame(overdue)

def get_upcoming_machines(df, days=7):
    if df.empty:
        return pd.DataFrame()
    
    today = datetime.now().date()
    upcoming = []
    
    for idx, row in df.iterrows():
        next_date_str = row.get("التاريخ القادم", "")
        if next_date_str and next_date_str != "":
            try:
                next_date = datetime.strptime(str(next_date_str), "%Y-%m-%d").date()
                days_diff = (next_date - today).days
                if 0 <= days_diff <= days:
                    upcoming.append(row)
            except:
                pass
    
    return pd.DataFrame(upcoming)

# ------------------------------- واجهة المستخدم -------------------------------
def show_dashboard(df):
    st.header("📊 لوحة التحكم - حالة التشحيم")
    
    df = update_daily_counters(df)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_machines = len(df)
    overdue_machines = len(get_overdue_machines(df))
    upcoming_machines = len(get_upcoming_machines(df, 7))
    good_machines = total_machines - overdue_machines - upcoming_machines
    
    with col1:
        st.metric("🏭 إجمالي الماكينات", total_machines)
    with col2:
        st.metric("🔴 متأخرة", overdue_machines, delta="يجب التشحيم فوراً" if overdue_machines > 0 else None, delta_color="inverse")
    with col3:
        st.metric("🟡 تحتاج تشحيم قريباً", upcoming_machines, delta="خلال 7 أيام")
    with col4:
        st.metric("🟢 سليمة", good_machines)
    
    st.markdown("---")
    
    if overdue_machines > 0:
        st.error("🚨 تنبيه: ماكينات متأخرة عن موعد التشحيم!")
        overdue_df = get_overdue_machines(df)
        display_cols = ["المعدة", "نوع المادة", "التاريخ القادم", "عدد الأيام المتبقية", "حالة التشحيم"]
        st.dataframe(overdue_df[display_cols], use_container_width=True)
        st.markdown("---")
    
    if upcoming_machines > 0:
        st.warning("⚠️ تنبيه: ماكينات تحتاج تشحيم خلال الأيام القادمة")
        upcoming_df = get_upcoming_machines(df, 7)
        display_cols = ["المعدة", "نوع المادة", "التاريخ القادم", "عدد الأيام المتبقية", "حالة التشحيم"]
        st.dataframe(upcoming_df[display_cols], use_container_width=True)
        st.markdown("---")
    
    st.subheader("📋 جميع الماكينات وحالة التشحيم")
    
    status_filter = st.selectbox("فلتر حسب الحالة:", ["الكل", "🟢 سليم", "🟡 ينتهي قريباً", "🟠 يجب التشحيم اليوم", "🔴 متأخر"])
    
    display_df = df.copy()
    if status_filter != "الكل":
        display_df = display_df[display_df["حالة التشحيم"].str.contains(status_filter, na=False)]
    
    display_cols = ["المعدة", "نوع المادة", "تاريخ التشحيم", "التاريخ القادم", "عدد الأيام المتبقية", "الكمية (لتر/جرام)", "حالة التشحيم"]
    available_cols = [col for col in display_cols if col in display_df.columns]
    st.dataframe(display_df[available_cols], use_container_width=True, height=400)

def show_add_machine(df):
    st.header("➕ إضافة ماكينة جديدة")
    
    col1, col2 = st.columns(2)
    
    with col1:
        machine_name = st.text_input("🏭 اسم الماكينة:", placeholder="مثال: مضخة الزيت الرئيسية")
        lubrication_type = st.selectbox("🛢️ نوع مادة التشحيم:", APP_CONFIG["LUBRICATION_TYPES"])
    
    with col2:
        default_interval = APP_CONFIG["DEFAULT_INTERVALS"].get(lubrication_type, 90)
        interval_days = st.number_input("📅 المدة بين عمليات التشحيم (أيام):", min_value=1, max_value=730, value=default_interval)
        st.caption(f"💡 المدة الافتراضية لـ {lubrication_type}: {default_interval} يوم")
    
    if st.button("✅ إضافة الماكينة", type="primary", use_container_width=True):
        if not machine_name:
            st.error("❌ الرجاء إدخال اسم الماكينة")
        else:
            new_df, success, msg = add_new_machine(df, machine_name, lubrication_type, interval_days)
            if success:
                if save_to_github(new_df, f"إضافة ماكينة جديدة: {machine_name} بواسطة {st.session_state.get('username', 'user')}"):
                    st.success(msg)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ البيانات")
            else:
                st.error(msg)

def show_record_lubrication(df):
    st.header("🛢️ تسجيل تشحيم جديد")
    
    machines = get_machines_list(df)
    if not machines:
        st.warning("⚠️ لا توجد ماكينات مسجلة. الرجاء إضافة ماكينة أولاً.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        machine_name = st.selectbox("🏭 اختر الماكينة:", machines)
        
        machine_data = df[df["المعدة"] == machine_name].iloc[0]
        st.info(f"""
        **معلومات الماكينة:**
        - نوع المادة: {machine_data.get('نوع المادة', 'غير محدد')}
        - آخر تشحيم: {machine_data.get('تاريخ التشحيم', 'لا يوجد')}
        - التاريخ القادم: {machine_data.get('التاريخ القادم', 'غير محدد')}
        - الأيام المتبقية: {machine_data.get('عدد الأيام المتبقية', 'غير محدد')}
        """)
        
        lubrication_date = st.date_input("📅 تاريخ التشحيم:", value=datetime.now())
    
    with col2:
        quantity = st.text_input("⚖️ الكمية المستخدمة:", placeholder="مثال: 5 لتر / 200 جرام")
        notes = st.text_area("📝 ملاحظات:", placeholder="أي ملاحظات إضافية...")
    
    if st.button("✅ تسجيل التشحيم", type="primary", use_container_width=True):
        new_df, success, msg = update_lubrication(
            df, machine_name, lubrication_date, quantity, notes, 
            st.session_state.get('username', 'user')
        )
        if success:
            if save_to_github(new_df, f"تسجيل تشحيم للماكينة: {machine_name} بواسطة {st.session_state.get('username', 'user')}"):
                st.success(msg)
                st.balloons()
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("❌ فشل حفظ البيانات")
        else:
            st.error(msg)

def show_machine_details(df):
    st.header("🔍 تفاصيل الماكينة")
    
    machines = get_machines_list(df)
    if not machines:
        st.warning("⚠️ لا توجد ماكينات مسجلة")
        return
    
    machine_name = st.selectbox("اختر الماكينة:", machines)
    
    if machine_name:
        machine_data = df[df["المعدة"] == machine_name].iloc[0]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🏭 الماكينة", machine_name)
            st.metric("🛢️ نوع المادة", machine_data.get('نوع المادة', 'غير محدد'))
        
        with col2:
            last_date = machine_data.get('تاريخ التشحيم', 'لا يوجد')
            st.metric("📅 آخر تشحيم", last_date if last_date else "لا يوجد")
            st.metric("📅 التاريخ القادم", machine_data.get('التاريخ القادم', 'غير محدد'))
        
        with col3:
            days_left = machine_data.get('عدد الأيام المتبقية', 'غير محدد')
            st.metric("⏳ الأيام المتبقية", days_left)
            st.metric("⚖️ آخر كمية", machine_data.get('آخر كمية', 'غير محدد'))
        
        if machine_data.get('عدد الأيام المتبقية') and str(machine_data.get('عدد الأيام المتبقية')).isdigit():
            days_left = int(machine_data.get('عدد الأيام المتبقية'))
            interval = int(machine_data.get('المدة (أيام)', 90))
            
            st.subheader("📊 العداد التنازلي")
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=days_left,
                title={"text": f"الأيام المتبقية حتى موعد التشحيم التالي"},
                delta={"reference": 0, "increasing": {"color": "red"}},
                gauge={
                    "axis": {"range": [0, interval]},
                    "bar": {"color": "darkorange"},
                    "steps": [
                        {"range": [0, interval*0.3], "color": "red"},
                        {"range": [interval*0.3, interval*0.7], "color": "orange"},
                        {"range": [interval*0.7, interval], "color": "lightgreen"}
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": 0
                    }
                }
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

def show_reports(df):
    st.header("📊 التقارير والإحصائيات")
    
    df = update_daily_counters(df)
    
    tab1, tab2, tab3 = st.tabs(["📈 إحصائيات عامة", "📋 تقرير الماكينات المتأخرة", "📅 تقرير التشحيم القادم"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🛢️ توزيع الماكينات حسب نوع المادة")
            material_stats = df["نوع المادة"].value_counts().reset_index()
            material_stats.columns = ["نوع المادة", "العدد"]
            st.dataframe(material_stats, use_container_width=True)
        
        with col2:
            st.subheader("📊 حالة الماكينات")
            status_stats = df["حالة التشحيم"].value_counts().reset_index()
            status_stats.columns = ["الحالة", "العدد"]
            st.dataframe(status_stats, use_container_width=True)
        
        st.subheader("📊 توزيع الماكينات حسب نوع المادة")
        if not material_stats.empty:
            fig = go.Figure(data=[go.Pie(labels=material_stats["نوع المادة"], values=material_stats["العدد"], hole=0.3)])
            fig.update_layout(title="نسبة الماكينات حسب نوع مادة التشحيم")
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("🔴 الماكينات المتأخرة عن موعد التشحيم")
        overdue_df = get_overdue_machines(df)
        if not overdue_df.empty:
            display_cols = ["المعدة", "نوع المادة", "التاريخ القادم", "عدد الأيام المتبقية", "الكمية (لتر/جرام)"]
            st.dataframe(overdue_df[display_cols], use_container_width=True)
            
            csv = overdue_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل التقرير", csv, "overdue_machines.csv", "text/csv")
        else:
            st.success("🎉 لا توجد ماكينات متأخرة! كل الماكينات في حالة جيدة.")
    
    with tab3:
        st.subheader("🟡 الماكينات التي تحتاج تشحيم خلال 30 يوماً")
        days_filter = st.slider("عدد الأيام القادمة:", 7, 90, 30)
        upcoming_df = get_upcoming_machines(df, days_filter)
        if not upcoming_df.empty:
            display_cols = ["المعدة", "نوع المادة", "التاريخ القادم", "عدد الأيام المتبقية", "الكمية (لتر/جرام)"]
            st.dataframe(upcoming_df[display_cols], use_container_width=True)
            
            csv = upcoming_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل التقرير", csv, "upcoming_machines.csv", "text/csv")
        else:
            st.info(f"لا توجد ماكينات تحتاج تشحيم خلال {days_filter} يوماً القادمة.")

def show_settings(df):
    st.header("⚙️ إعدادات النظام")
    
    st.subheader("📅 المدة الافتراضية بين عمليات التشحيم")
    st.info("يمكنك تعديل المدة الافتراضية لكل نوع من أنواع مواد التشحيم")
    
    new_intervals = {}
    cols = st.columns(2)
    
    for i, lub_type in enumerate(APP_CONFIG["LUBRICATION_TYPES"]):
        with cols[i % 2]:
            current = APP_CONFIG["DEFAULT_INTERVALS"].get(lub_type, 90)
            new_val = st.number_input(f"{lub_type}:", min_value=1, max_value=730, value=current, key=f"interval_{lub_type}")
            new_intervals[lub_type] = new_val
    
    if st.button("💾 حفظ الإعدادات", type="primary"):
        APP_CONFIG["DEFAULT_INTERVALS"] = new_intervals
        st.success("✅ تم حفظ الإعدادات بنجاح!")
        st.rerun()
    
    st.markdown("---")
    st.subheader("🗑️ حذف ماكينة")
    
    machines = get_machines_list(df)
    if machines:
        machine_to_delete = st.selectbox("اختر الماكينة للحذف:", machines)
        st.warning("⚠️ تحذير: حذف الماكينة سيؤدي إلى حذف جميع سجلات التشحيم الخاصة بها!")
        if st.button("🗑️ حذف الماكينة", type="secondary"):
            new_df = df[df["المعدة"] != machine_to_delete].copy()
            if save_to_github(new_df, f"حذف ماكينة: {machine_to_delete} بواسطة {st.session_state.get('username', 'user')}"):
                st.success(f"تم حذف الماكينة '{machine_to_delete}' بنجاح")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("فشل الحذف")
    else:
        st.info("لا توجد ماكينات للحذف")

# ------------------------------- الواجهة الرئيسية -------------------------------
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide", page_icon="🛢️")

with st.sidebar:
    st.header("🔐 الجلسة")
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
        if st.button("🔄 تحديث البيانات"):
            if fetch_from_github_requests():
                st.cache_data.clear()
                st.rerun()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()

df = load_lubrication_data()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
st.caption("نظام متخصص لإدارة عمليات التشحيم والزيوت مع عدادات تنازلية وتنبيهات")

user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
can_edit = (user_role == "admin" or user_role == "editor" or "edit" in user_permissions)

tabs_list = ["📊 لوحة التحكم", "🔍 تفاصيل الماكينات"]
if can_edit:
    tabs_list.extend(["➕ إضافة ماكينة", "🛢️ تسجيل تشحيم", "📊 تقارير", "⚙️ إعدادات"])

tabs = st.tabs(tabs_list)

with tabs[0]:
    show_dashboard(df)

with tabs[1]:
    show_machine_details(df)

if can_edit:
    with tabs[2]:
        show_add_machine(df)
    
    with tabs[3]:
        show_record_lubrication(df)
    
    with tabs[4]:
        show_reports(df)
    
    with tabs[5]:
        show_settings(df)
