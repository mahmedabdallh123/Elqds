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
from PIL import Image

# محاولة استيراد Plotly مع معالجة الخطأ
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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
    "DEFAULT_SHEET_COLUMNS": ["التاريخ", "رقم الماكينة", "الحدث/العطل", "الإجراء التصحيحي", "تم بواسطة", "الطن", "الصور", "القسم", "ملاحظات"],
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

# إنشاء مجلد الصور إذا لم يكن موجوداً
if not os.path.exists(IMAGES_FOLDER):
    os.makedirs(IMAGES_FOLDER)

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

# ------------------------------- دوال الصور -------------------------------
def save_image(image_file, event_id):
    try:
        ext = image_file.name.split('.')[-1]
        filename = f"{event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        filepath = os.path.join(IMAGES_FOLDER, filename)
        with open(filepath, "wb") as f:
            f.write(image_file.getbuffer())
        return filename
    except Exception as e:
        st.error(f"خطأ في حفظ الصورة: {e}")
        return None

def delete_image(filename):
    try:
        filepath = os.path.join(IMAGES_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except:
        pass
    return False

# ------------------------------- دوال الأحداث -------------------------------
def get_all_events(all_sheets):
    """جمع جميع الأحداث من جميع الشيتات في DataFrame واحد"""
    if not all_sheets:
        return pd.DataFrame()
    
    all_events = []
    for sheet_name, df in all_sheets.items():
        if not df.empty:
            df_copy = df.copy()
            df_copy["اسم الشيت"] = sheet_name
            all_events.append(df_copy)
    
    if all_events:
        return pd.concat(all_events, ignore_index=True)
    return pd.DataFrame()

def add_event_to_sheet(sheets_edit, sheet_name, event_data, images):
    """إضافة حدث جديد مع الصور"""
    if sheet_name not in sheets_edit:
        return sheets_edit, False, "الشيت غير موجود"
    
    df = sheets_edit[sheet_name]
    
    # حفظ الصور
    image_names = []
    for img in images:
        event_id = str(uuid.uuid4())[:8]
        img_name = save_image(img, event_id)
        if img_name:
            image_names.append(img_name)
    
    # إنشاء السجل الجديد
    new_row = {
        "التاريخ": event_data.get("التاريخ", datetime.now().strftime("%Y-%m-%d")),
        "رقم الماكينة": event_data.get("رقم الماكينة", ""),
        "الحدث/العطل": event_data.get("الحدث/العطل", ""),
        "الإجراء التصحيحي": event_data.get("الإجراء التصحيحي", ""),
        "تم بواسطة": event_data.get("تم بواسطة", st.session_state.get("username", "")),
        "الطن": event_data.get("الطن", ""),
        "الصور": ", ".join(image_names) if image_names else "",
        "القسم": event_data.get("القسم", ""),
        "ملاحظات": event_data.get("ملاحظات", "")
    }
    
    # إضافة الأعمدة المفقودة
    for col in df.columns:
        if col not in new_row:
            new_row[col] = ""
    
    new_row_df = pd.DataFrame([new_row])
    sheets_edit[sheet_name] = pd.concat([df, new_row_df], ignore_index=True)
    
    return sheets_edit, True, "تم إضافة الحدث بنجاح"

def update_event_in_sheet(sheets_edit, sheet_name, row_index, event_data, new_images, images_to_delete):
    """تحديث حدث موجود"""
    if sheet_name not in sheets_edit:
        return sheets_edit, False, "الشيت غير موجود"
    
    df = sheets_edit[sheet_name]
    
    if row_index >= len(df):
        return sheets_edit, False, "الحدث غير موجود"
    
    # حذف الصور المحددة للحذف
    current_images = df.loc[row_index, "الصور"] if "الصور" in df.columns else ""
    if current_images and isinstance(current_images, str):
        old_images = current_images.split(", ")
        for img in images_to_delete:
            if img in old_images:
                delete_image(img)
    
    # حفظ الصور الجديدة
    new_image_names = []
    for img in new_images:
        event_id = str(uuid.uuid4())[:8]
        img_name = save_image(img, event_id)
        if img_name:
            new_image_names.append(img_name)
    
    # تجميع الصور النهائية
    remaining_images = [img for img in old_images if img not in images_to_delete] if current_images else []
    all_images = remaining_images + new_image_names
    
    # تحديث البيانات
    df.loc[row_index, "التاريخ"] = event_data.get("التاريخ", df.loc[row_index, "التاريخ"])
    df.loc[row_index, "رقم الماكينة"] = event_data.get("رقم الماكينة", df.loc[row_index, "رقم الماكينة"])
    df.loc[row_index, "الحدث/العطل"] = event_data.get("الحدث/العطل", df.loc[row_index, "الحدث/العطل"])
    df.loc[row_index, "الإجراء التصحيحي"] = event_data.get("الإجراء التصحيحي", df.loc[row_index, "الإجراء التصحيحي"])
    df.loc[row_index, "تم بواسطة"] = event_data.get("تم بواسطة", st.session_state.get("username", ""))
    df.loc[row_index, "الطن"] = event_data.get("الطن", df.loc[row_index, "الطن"])
    df.loc[row_index, "القسم"] = event_data.get("القسم", df.loc[row_index, "القسم"])
    df.loc[row_index, "ملاحظات"] = event_data.get("ملاحظات", df.loc[row_index, "ملاحظات"])
    df.loc[row_index, "الصور"] = ", ".join(all_images) if all_images else ""
    
    sheets_edit[sheet_name] = df
    return sheets_edit, True, "تم تحديث الحدث بنجاح"

def delete_event_from_sheet(sheets_edit, sheet_name, row_index):
    """حذف حدث مع حذف الصور المرتبطة"""
    if sheet_name not in sheets_edit:
        return sheets_edit, False, "الشيت غير موجود"
    
    df = sheets_edit[sheet_name]
    
    if row_index >= len(df):
        return sheets_edit, False, "الحدث غير موجود"
    
    # حذف الصور المرتبطة
    if "الصور" in df.columns:
        images_str = df.loc[row_index, "الصور"]
        if images_str and isinstance(images_str, str):
            for img in images_str.split(", "):
                delete_image(img)
    
    # حذف السجل
    sheets_edit[sheet_name] = df.drop(row_index).reset_index(drop=True)
    
    return sheets_edit, True, "تم حذف الحدث بنجاح"

# ------------------------------- دوال البحث المتقدم -------------------------------
def advanced_search(all_sheets, search_text, machine_number, section, start_date, end_date):
    """بحث متقدم في جميع الأحداث"""
    results = []
    
    if not all_sheets:
        return pd.DataFrame()
    
    for sheet_name, df in all_sheets.items():
        if df.empty:
            continue
        
        df_filtered = df.copy()
        
        # فلتر حسب النص
        if search_text:
            mask = pd.Series([False] * len(df_filtered))
            search_cols = ["الحدث/العطل", "الإجراء التصحيحي", "ملاحظات"]
            for col in search_cols:
                if col in df_filtered.columns:
                    mask = mask | df_filtered[col].astype(str).str.contains(search_text, case=False, na=False)
            df_filtered = df_filtered[mask]
        
        # فلتر حسب رقم الماكينة
        if machine_number and "رقم الماكينة" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["رقم الماكينة"].astype(str).str.contains(machine_number, case=False, na=False)]
        
        # فلتر حسب القسم
        if section and section != "الكل" and "القسم" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["القسم"] == section]
        
        # فلتر حسب التاريخ
        if start_date and end_date and "التاريخ" in df_filtered.columns:
            try:
                df_filtered["التاريخ"] = pd.to_datetime(df_filtered["التاريخ"], errors='coerce')
                mask = (df_filtered["التاريخ"].dt.date >= start_date) & (df_filtered["التاريخ"].dt.date <= end_date)
                df_filtered = df_filtered[mask]
            except:
                pass
        
        if not df_filtered.empty:
            df_filtered["اسم الشيت"] = sheet_name
            results.append(df_filtered)
    
    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()

# ------------------------------- دوال العرض -------------------------------
def display_sheet_data_with_events(sheet_name, df, unique_id, sheets_edit, can_edit):
    """عرض بيانات الشيت مع إمكانية تعديل وحذف الأحداث"""
    st.markdown(f"### {sheet_name}")
    st.info(f"عدد السجلات: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # فلتر
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        if "رقم الماكينة" in df.columns:
            machines = ["الكل"] + sorted(df["رقم الماكينة"].dropna().unique().astype(str).tolist())
            selected_machine = st.selectbox("فلتر حسب رقم الماكينة:", machines, key=f"machine_filter_{unique_id}")
            if selected_machine != "الكل":
                df = df[df["رقم الماكينة"].astype(str) == selected_machine]
    
    with col_filter2:
        if "القسم" in df.columns:
            sections = ["الكل"] + sorted(df["القسم"].dropna().unique().tolist())
            selected_section = st.selectbox("فلتر حسب القسم:", sections, key=f"section_filter_{unique_id}")
            if selected_section != "الكل":
                df = df[df["القسم"] == selected_section]
    
    st.markdown("---")
    
    # عرض البيانات في جدول قابل للتعديل
    if not df.empty:
        for idx, row in df.iterrows():
            with st.expander(f"📋 {row.get('التاريخ', 'تاريخ غير محدد')} - {row.get('رقم الماكينة', 'رقم غير محدد')} - {row.get('الحدث/العطل', 'حدث غير محدد')[:50]}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**📅 التاريخ:** {row.get('التاريخ', '')}")
                    st.markdown(f"**🔢 رقم الماكينة:** {row.get('رقم الماكينة', '')}")
                    st.markdown(f"**⚙️ الحدث/العطل:** {row.get('الحدث/العطل', '')}")
                    st.markdown(f"**🔧 الإجراء التصحيحي:** {row.get('الإجراء التصحيحي', '')}")
                    st.markdown(f"**👨‍🔧 تم بواسطة:** {row.get('تم بواسطة', '')}")
                
                with col2:
                    st.markdown(f"**⚖️ الطن:** {row.get('الطن', '')}")
                    st.markdown(f"**🏢 القسم:** {row.get('القسم', '')}")
                    st.markdown(f"**📝 ملاحظات:** {row.get('ملاحظات', '')}")
                    
                    # عرض الصور
                    images_str = row.get('الصور', '')
                    if images_str and isinstance(images_str, str):
                        st.markdown("**🖼️ الصور:**")
                        for img in images_str.split(", "):
                            img_path = os.path.join(IMAGES_FOLDER, img)
                            if os.path.exists(img_path):
                                st.image(img_path, width=150)
                
                # أزرار التعديل والحذف للمستخدمين المصرح لهم
                if can_edit:
                    col_edit, col_delete = st.columns(2)
                    with col_edit:
                        if st.button(f"✏️ تعديل", key=f"edit_{unique_id}_{idx}"):
                            st.session_state[f"editing_{unique_id}_{idx}"] = True
                            st.session_state[f"edit_sheet_{unique_id}"] = sheet_name
                            st.session_state[f"edit_row_{unique_id}"] = idx
                            st.rerun()
                    
                    with col_delete:
                        if st.button(f"🗑️ حذف", key=f"delete_{unique_id}_{idx}"):
                            sheets_edit, success, msg = delete_event_from_sheet(sheets_edit, sheet_name, idx)
                            if success:
                                if save_to_github(sheets_edit, f"حذف حدث من {sheet_name}"):
                                    st.success(msg)
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error("فشل الحفظ")
                            else:
                                st.error(msg)
                
                # نموذج التعديل
                if can_edit and st.session_state.get(f"editing_{unique_id}_{idx}", False):
                    st.markdown("---")
                    st.subheader("✏️ تعديل الحدث")
                    
                    with st.form(key=f"edit_form_{unique_id}_{idx}"):
                        edit_date = st.date_input("التاريخ:", value=pd.to_datetime(row.get('التاريخ', datetime.now())).date() if row.get('التاريخ') else datetime.now().date())
                        edit_machine = st.text_input("رقم الماكينة:", value=row.get('رقم الماكينة', ''))
                        edit_event = st.text_area("الحدث/العطل:", value=row.get('الحدث/العطل', ''), height=100)
                        edit_correction = st.text_area("الإجراء التصحيحي:", value=row.get('الإجراء التصحيحي', ''), height=100)
                        edit_done_by = st.text_input("تم بواسطة:", value=row.get('تم بواسطة', ''))
                        edit_tones = st.text_input("الطن:", value=row.get('الطن', ''))
                        edit_section = st.selectbox("القسم:", APP_CONFIG["SECTIONS"], index=APP_CONFIG["SECTIONS"].index(row.get('القسم', '')) if row.get('القسم', '') in APP_CONFIG["SECTIONS"] else 0)
                        edit_notes = st.text_area("ملاحظات:", value=row.get('ملاحظات', ''), height=100)
                        
                        # إدارة الصور
                        st.markdown("**🖼️ الصور الحالية:**")
                        current_images = row.get('الصور', '')
                        images_to_delete = []
                        if current_images and isinstance(current_images, str):
                            for img in current_images.split(", "):
                                col_img, col_check = st.columns([3, 1])
                                with col_img:
                                    img_path = os.path.join(IMAGES_FOLDER, img)
                                    if os.path.exists(img_path):
                                        st.image(img_path, width=100)
                                with col_check:
                                    if st.checkbox(f"حذف", key=f"del_img_{unique_id}_{idx}_{img}"):
                                        images_to_delete.append(img)
                        
                        st.markdown("**➕ إضافة صور جديدة:**")
                        new_images = st.file_uploader("اختر الصور:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True, key=f"edit_images_{unique_id}_{idx}")
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            submitted = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
                        with col_cancel:
                            cancel = st.form_submit_button("❌ إلغاء", use_container_width=True)
                        
                        if submitted:
                            event_data = {
                                "التاريخ": edit_date.strftime("%Y-%m-%d"),
                                "رقم الماكينة": edit_machine,
                                "الحدث/العطل": edit_event,
                                "الإجراء التصحيحي": edit_correction,
                                "تم بواسطة": edit_done_by,
                                "الطن": edit_tones,
                                "القسم": edit_section,
                                "ملاحظات": edit_notes
                            }
                            sheets_edit, success, msg = update_event_in_sheet(sheets_edit, sheet_name, idx, event_data, new_images, images_to_delete)
                            if success:
                                if save_to_github(sheets_edit, f"تعديل حدث في {sheet_name}"):
                                    st.success(msg)
                                    st.session_state[f"editing_{unique_id}_{idx}"] = False
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error("فشل الحفظ")
                            else:
                                st.error(msg)
                        
                        if cancel:
                            st.session_state[f"editing_{unique_id}_{idx}"] = False
                            st.rerun()
    else:
        st.info("لا توجد سجلات")

def show_add_event(all_sheets, sheets_edit):
    """إضافة حدث جديد"""
    st.header("➕ إضافة حدث جديد")
    
    if not sheets_edit:
        st.warning("لا توجد بيانات. يرجى تحديث الملف أولاً")
        return
    
    with st.form(key="add_event_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
            event_date = st.date_input("📅 التاريخ:", value=datetime.now())
            machine_number = st.text_input("🔢 رقم الماكينة:", placeholder="مثال: MC-001, PUMP-01")
            event_desc = st.text_area("⚙️ الحدث/العطل:", height=100, placeholder="وصف العطل أو الحدث...")
        
        with col2:
            correction_desc = st.text_area("🔧 الإجراء التصحيحي:", height=100, placeholder="الإجراء الذي تم اتخاذه...")
            done_by = st.text_input("👨‍🔧 تم بواسطة:", value=st.session_state.get("username", ""))
            tones = st.text_input("⚖️ الطن:", placeholder="الطن (إن وجد)")
            section = st.selectbox("🏢 القسم:", APP_CONFIG["SECTIONS"])
            notes = st.text_area("📝 ملاحظات:", height=80, placeholder="ملاحظات إضافية...")
        
        images = st.file_uploader("🖼️ رفع الصور:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True)
        
        if images:
            total_size = sum(img.size for img in images)
            if total_size > APP_CONFIG["MAX_IMAGE_SIZE_MB"] * 1024 * 1024:
                st.error(f"حجم الصور كبير جداً. الحد الأقصى {APP_CONFIG['MAX_IMAGE_SIZE_MB']} ميجابايت")
        
        submitted = st.form_submit_button("✅ إضافة الحدث", type="primary", use_container_width=True)
        
        if submitted:
            if not machine_number:
                st.error("❌ الرجاء إدخال رقم الماكينة")
            elif not event_desc:
                st.error("❌ الرجاء إدخال الحدث/العطل")
            else:
                event_data = {
                    "التاريخ": event_date.strftime("%Y-%m-%d"),
                    "رقم الماكينة": machine_number,
                    "الحدث/العطل": event_desc,
                    "الإجراء التصحيحي": correction_desc,
                    "تم بواسطة": done_by,
                    "الطن": tones,
                    "القسم": section,
                    "ملاحظات": notes
                }
                sheets_edit, success, msg = add_event_to_sheet(sheets_edit, sheet_name, event_data, images)
                if success:
                    if save_to_github(sheets_edit, f"إضافة حدث جديد في {sheet_name}"):
                        st.success(msg)
                        st.balloons()
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ فشل حفظ البيانات")
                else:
                    st.error(msg)

def show_advanced_search(all_sheets):
    """تبويب البحث المتقدم"""
    st.header("🔍 بحث متقدم")
    
    if not all_sheets:
        st.warning("لا توجد بيانات للبحث")
        return
    
    with st.form(key="search_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            search_text = st.text_input("🔎 بحث بالنص:", placeholder="ابحث في الحدث/العطل أو الإجراء التصحيحي...")
            machine_number = st.text_input("🔢 رقم الماكينة:", placeholder="أدخل رقم الماكينة...")
        
        with col2:
            sections = ["الكل"] + APP_CONFIG["SECTIONS"]
            section = st.selectbox("🏢 القسم:", sections)
            
            use_date_filter = st.checkbox("فلتر بالتاريخ")
            if use_date_filter:
                col_date1, col_date2 = st.columns(2)
                with col_date1:
                    start_date = st.date_input("من تاريخ:", value=datetime.now() - timedelta(days=30))
                with col_date2:
                    end_date = st.date_input("إلى تاريخ:", value=datetime.now())
            else:
                start_date = None
                end_date = None
        
        submitted = st.form_submit_button("🔍 بحث", type="primary", use_container_width=True)
        
        if submitted:
            with st.spinner("جاري البحث..."):
                results = advanced_search(all_sheets, search_text, machine_number, section, start_date, end_date)
                
                if not results.empty:
                    st.success(f"✅ تم العثور على {len(results)} نتيجة")
                    
                    # عرض النتائج
                    for idx, row in results.iterrows():
                        with st.expander(f"📋 {row.get('التاريخ', '')} - {row.get('رقم الماكينة', '')} - {row.get('الحدث/العطل', '')[:50]}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"**📅 التاريخ:** {row.get('التاريخ', '')}")
                                st.markdown(f"**🔢 رقم الماكينة:** {row.get('رقم الماكينة', '')}")
                                st.markdown(f"**⚙️ الحدث/العطل:** {row.get('الحدث/العطل', '')}")
                                st.markdown(f"**🔧 الإجراء التصحيحي:** {row.get('الإجراء التصحيحي', '')}")
                                st.markdown(f"**🏢 القسم:** {row.get('القسم', '')}")
                                st.markdown(f"**📝 الشيت:** {row.get('اسم الشيت', '')}")
                            
                            with col2:
                                st.markdown(f"**👨‍🔧 تم بواسطة:** {row.get('تم بواسطة', '')}")
                                st.markdown(f"**⚖️ الطن:** {row.get('الطن', '')}")
                                st.markdown(f"**📝 ملاحظات:** {row.get('ملاحظات', '')}")
                                
                                # عرض الصور
                                images_str = row.get('الصور', '')
                                if images_str and isinstance(images_str, str):
                                    st.markdown("**🖼️ الصور:**")
                                    for img in images_str.split(", "):
                                        img_path = os.path.join(IMAGES_FOLDER, img)
                                        if os.path.exists(img_path):
                                            st.image(img_path, width=150)
                    
                    # تصدير النتائج
                    csv = results.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 تحميل نتائج البحث", csv, f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
                else:
                    st.warning("❌ لا توجد نتائج مطابقة للبحث")

def show_add_machine(sheets_edit):
    """إضافة ماكينة جديدة"""
    st.subheader("➕ إضافة ماكينة جديدة")
    st.info("سيتم إضافة الماكينة الجديدة كشيت منفصل في ملف Excel")
    
    col1, col2 = st.columns(2)
    with col1:
        new_sheet_name = st.text_input("📝 اسم الماكينة الجديدة:", key="new_machine_name",
                                       placeholder="مثال: ماكينة الخراطة, ماكينة اللحام")
        if new_sheet_name and new_sheet_name in sheets_edit:
            st.error(f"❌ الماكينة '{new_sheet_name}' موجودة بالفعل!")
        elif new_sheet_name:
            st.success(f"✅ اسم الماكينة '{new_sheet_name}' متاح")
    
    with col2:
        use_default = st.checkbox("استخدام الأعمدة الافتراضية", value=True, key="use_default")
        if use_default:
            columns_list = APP_CONFIG["DEFAULT_SHEET_COLUMNS"]
            st.info(f"📊 الأعمدة: {', '.join(columns_list)}")
        else:
            columns_text = st.text_area("✏️ الأعمدة:", value="\n".join(APP_CONFIG["DEFAULT_SHEET_COLUMNS"]), height=150)
            columns_list = [col.strip() for col in columns_text.split("\n") if col.strip()]
            if not columns_list:
                columns_list = APP_CONFIG["DEFAULT_SHEET_COLUMNS"]
    
    if st.button("✅ إنشاء وإضافة الماكينة", type="primary", use_container_width=True):
        if not new_sheet_name:
            st.error("❌ الرجاء إدخال اسم الماكينة")
            return sheets_edit
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', new_sheet_name.strip())
        if clean_name != new_sheet_name:
            st.warning(f"⚠ تم تعديل الاسم إلى: {clean_name}")
            new_sheet_name = clean_name
        if new_sheet_name in sheets_edit:
            st.error(f"❌ الماكينة '{new_sheet_name}' موجودة بالفعل!")
            return sheets_edit
        
        try:
            with st.spinner("جاري الإنشاء..."):
                new_df = pd.DataFrame(columns=columns_list)
                sheets_edit[new_sheet_name] = new_df
                if save_to_github(sheets_edit, f"إضافة ماكينة جديدة: {new_sheet_name}"):
                    st.success(f"✅ تم إنشاء الماكينة '{new_sheet_name}' بنجاح!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ فشل الرفع")
                    return sheets_edit
        except Exception as e:
            st.error(f"❌ خطأ: {str(e)}")
            return sheets_edit
    
    st.markdown("---")
    st.markdown("### 📋 الماكينات الموجودة:")
    if sheets_edit:
        for sheet_name in sheets_edit.keys():
            st.write(f"- 🏭 {sheet_name}")
    else:
        st.info("لا توجد ماكينات بعد")
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

# تبويبات التطبيق
tabs_list = ["📊 عرض البيانات", "🔍 بحث متقدم"]
if can_edit:
    tabs_list.extend(["➕ إضافة حدث", "➕ إضافة ماكينة"])

tabs = st.tabs(tabs_list)

with tabs[0]:
    if all_sheets:
        st.subheader("جميع الماكينات")
        sheet_tabs = st.tabs(list(all_sheets.keys()))
        for i, (sheet_name, df) in enumerate(all_sheets.items()):
            with sheet_tabs[i]:
                display_sheet_data_with_events(sheet_name, df, f"main_{sheet_name}", sheets_edit, can_edit)
    else:
        st.warning("لا توجد بيانات. يرجى تحديث الملف من GitHub.")

with tabs[1]:
    show_advanced_search(all_sheets)

if can_edit:
    with tabs[2]:
        show_add_event(all_sheets, sheets_edit)
    
    with tabs[3]:
        if sheets_edit:
            show_add_machine(sheets_edit)
        else:
            st.warning("الملف غير موجود. استخدم زر 'تحديث من GitHub' أولاً")
