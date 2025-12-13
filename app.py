import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
import numpy as np
from datetime import datetime, timedelta
from base64 import b64decode

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
    "APP_TITLE": "CMMS - bel",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# إعدادات الألوان
COLOR_CONFIG = {
    "service_done": "#d4edda",  # أخضر فاتح
    "service_not_done": "#f8d7da",  # أحمر فاتح
    "service_partial": "#fff3cd",  # أصفر فاتح
    "row_added": "#e8f5e8",  # أخضر شفاف
    "row_deleted": "#ffebee",  # أحمر شفاف
    "row_modified": "#e3f2fd",  # أزرق شفاف
    "header": "#f0f2f6",  # لون الرأس
    "even_row": "#ffffff",  # صف زوجي
    "odd_row": "#f9f9f9"  # صف فردي
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# ===============================
# 🧠 وظائف المصادقة
# ===============================
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        if "admin" not in users:
            users["admin"] = {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
        
        for username, user_data in users.items():
            if "role" not in user_data:
                user_data["role"] = "admin" if username == "admin" else "viewer"
                user_data["permissions"] = ["all"] if username == "admin" else ["view"]
                    
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.now().isoformat()
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        
        return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف users.json: {e}")
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
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            current_users = json.load(f)
        user_list = list(current_users.keys())
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

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions
        }

# ===============================
# 📁 وظائف إدارة الملفات
# ===============================
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
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
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
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف للتحرير: {e}")
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
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
            try:
                result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                return load_sheets_for_edit()
            except Exception as create_error:
                st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                return None

    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
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
# 🛠 وظائف مساعدة
# ===============================
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
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;"
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

def get_servised_by_value(row):
    servised_columns = [
        "Servised by", "SERVISED BY", "servised by", "Servised By",
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    ]
    
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    return "-"

# ===============================
# 🎨 وظائف التلوين
# ===============================
def color_service_row(row):
    """تلوين صفوف فحص السيرفيس حسب الحالة"""
    service_needed = row.get("Service Needed", "-")
    service_done = row.get("Service Done", "-")
    service_not_done = row.get("Service Didn't Done", "-")
    
    if service_done == "-":
        # لا يوجد أي خدمة منفذة
        return [f"background-color: {COLOR_CONFIG['service_not_done']}"] * len(row)
    elif service_not_done == "-":
        # كل الخدمات منفذة
        return [f"background-color: {COLOR_CONFIG['service_done']}"] * len(row)
    else:
        # بعض الخدمات منفذة والبعض الآخر لا
        return [f"background-color: {COLOR_CONFIG['service_partial']}"] * len(row)

def color_edit_row(row, row_index, added_rows=None, deleted_rows=None):
    """تلوين صفوف التحرير"""
    added_rows = added_rows or []
    deleted_rows = deleted_rows or []
    
    if row_index in added_rows:
        return [f"background-color: {COLOR_CONFIG['row_added']}"] * len(row)
    elif row_index in deleted_rows:
        return [f"background-color: {COLOR_CONFIG['row_deleted']}"] * len(row)
    else:
        if row_index % 2 == 0:
            return [f"background-color: {COLOR_CONFIG['even_row']}"] * len(row)
        else:
            return [f"background-color: {COLOR_CONFIG['odd_row']}"] * len(row)

def apply_table_styling(df, row_coloring_func, row_indices=None):
    """تطبيق التنسيق على الجدول"""
    if row_indices is None:
        row_indices = df.index
    
    styled_df = df.style.apply(row_coloring_func, axis=1, row_indices=row_indices)
    
    # تنسيق الرأس
    styled_df = styled_df.set_properties(**{
        'background-color': COLOR_CONFIG['header'],
        'font-weight': 'bold',
        'border': '1px solid #ddd'
    }, subset=pd.IndexSlice[:, :])
    
    # تنسيق الخلايا
    styled_df = styled_df.set_properties(**{
        'border': '1px solid #ddd',
        'padding': '5px'
    })
    
    return styled_df

# ===============================
# 📊 فحص السيرفيس مع تلوين وإحصائيات محسنة (من الكود الثاني)
# ===============================
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس فقط - من الكود الثاني"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_services_sheet_name = f"Card{card_num}_Services"
    
    # إذا لم يكن هناك شيت خدمات منفصل، نبحث في الشيت القديم
    if card_services_sheet_name not in all_sheets:
        # محاولة البحث في الشيت القديم
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
            # فلترة فقط الصفوف التي لها Min_Tones و Max_Tones
            services_df = card_df[
                (card_df.get("Min_Tones", pd.NA).notna()) & 
                (card_df.get("Max_Tones", pd.NA).notna()) &
                (card_df.get("Min_Tones", "") != "") & 
                (card_df.get("Max_Tones", "") != "")
            ].copy()
        else:
            st.warning(f"⚠ لا يوجد شيت باسم {card_services_sheet_name} أو {card_old_sheet_name}")
            return
    else:
        card_df = all_sheets[card_services_sheet_name]
        services_df = card_df.copy()

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key=f"service_view_option_{card_num}"
    )

    min_range = st.session_state.get(f"service_min_range_{card_num}", max(0, current_tons - 500))
    max_range = st.session_state.get(f"service_max_range_{card_num}", current_tons + 500)
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key=f"service_min_range_{card_num}")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key=f"service_max_range_{card_num}")

    # اختيار الشرائح
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] <= current_tons) & (service_plan_df["Max_Tones"] >= current_tons)]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] >= min_range) & (service_plan_df["Max_Tones"] <= max_range)]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    all_results = []
    service_stats = {
        "service_counts": {},  # تعداد كل خدمة مطلوبة
        "service_done_counts": {},  # تعداد الخدمات المنفذة
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {}  # إحصائيات حسب الشريحة
    }
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
        # تحديث إحصائيات الخدمات المطلوبة
        service_stats["by_slice"][slice_key] = {
            "needed": needed_parts,
            "done": [],
            "not_done": [],
            "total_needed": len(needed_parts),
            "total_done": 0
        }
        
        for service in needed_parts:
            service_stats["service_counts"][service] = service_stats["service_counts"].get(service, 0) + 1
        service_stats["total_needed_services"] += len(needed_parts)

        # البحث في خدمات الماكينة
        mask = (services_df.get("Min_Tones", 0).fillna(0) <= slice_max) & (services_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                # تحديد الأعمدة التي تحتوي على خدمات منجزة (استبعاد أعمدة البيانات الوصفية)
                metadata_columns = {
                    "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
                    "Other", "Servised by", "Event", "Correction",
                    "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
                    "OTHER", "EVENT", "CORRECTION", "SERVISED BY",
                    "servised by", "Servised By", 
                    "Serviced by", "Service by", "Serviced By", "Service By",
                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
                }
                
                all_columns = set(services_df.columns)
                service_columns = all_columns - metadata_columns
                
                final_service_columns = set()
                for col in service_columns:
                    col_normalized = normalize_name(col)
                    metadata_normalized = {normalize_name(mc) for mc in metadata_columns}
                    if col_normalized not in metadata_normalized:
                        final_service_columns.add(col)
                
                for col in final_service_columns:
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", "", "null", "0"]:
                        if val.lower() not in ["no", "false", "not done", "لم تتم", "x", "-"]:
                            done_services_set.add(col)
                            # تحديث إحصائيات الخدمات المنفذة
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1

                # جمع بيانات السيرفيس فقط
                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                # البحث عن فني الخدمة
                servised_by_value = get_servised_by_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                # تحديث إحصائيات الشريحة
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
                # مقارنة الخدمات المنجزة مع المطلوبة
                not_done = []
                for needed_part, needed_norm_part in zip(needed_parts, needed_norm):
                    if needed_norm_part not in done_norm:
                        not_done.append(needed_part)
                
                service_stats["by_slice"][slice_key]["not_done"].extend(not_done)

                all_results.append({
                    "Card Number": card_num,
                    "Min_Tons": slice_min,
                    "Max_Tons": slice_max,
                    "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                    "Service Done": ", ".join(done_services) if done_services else "-",
                    "Service Didn't Done": ", ".join(not_done) if not_done else "-",
                    "Tones": current_tones,
                    "Servised by": servised_by_value,
                    "Date": current_date
                })
        else:
            # إذا لم توجد سجلات سيرفيس
            all_results.append({
                "Card Number": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                "Service Done": "-",
                "Service Didn't Done": ", ".join(needed_parts) if needed_parts else "-",
                "Tones": "-",
                "Servised by": "-",
                "Date": "-"
            })
            
            # تحديث إحصائيات الشريحة (لا يوجد خدمات منفذة)
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        # تطبيق التلوين على النتائج من الكود الأول
        styled_df = result_df.style.apply(color_service_row, axis=1)
        
        # عرض الجدول مع التلوين
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # عرض الإحصائيات من الكود الثاني
        show_service_statistics(service_stats, result_df)
        
        # تنزيل النتائج
        buffer = io.BytesIO()
        result_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Service_Report_Card{card_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ لا توجد خدمات مسجلة لهذه الماكينة.")

def show_service_statistics(service_stats, result_df):
    """عرض الإحصائيات والنسب المئوية لفحص السيرفيس - من الكود الثاني"""
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    
    if service_stats["total_needed_services"] == 0:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    
    # حساب النسبة العامة
    completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100 if service_stats["total_needed_services"] > 0 else 0
    
    # عرض النسب العامة
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📈 نسبة الإنجاز العامة",
            value=f"{completion_rate:.1f}%",
            delta=f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}"
        )
    
    with col2:
        st.metric(
            label="🔢 عدد الخدمات المطلوبة",
            value=service_stats["total_needed_services"]
        )
    
    with col3:
        st.metric(
            label="✅ الخدمات المنفذة",
            value=service_stats["total_done_services"]
        )
    
    with col4:
        remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
        st.metric(
            label="⏳ الخدمات المتبقية",
            value=remaining
        )
    
    st.markdown("---")
    
    # تبويبات للإحصائيات التفصيلية
    stat_tabs = st.tabs([
        "📝 إحصائيات الخدمات",
        "📋 توزيع الخدمات",
        "📊 حسب الشريحة"
    ])
    
    with stat_tabs[0]:
        st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
        
        # إنشاء DataFrame للإحصائيات
        stat_data = []
        all_services = set(service_stats["service_counts"].keys()).union(
            set(service_stats["service_done_counts"].keys())
        )
        
        for service in sorted(all_services):
            needed_count = service_stats["service_counts"].get(service, 0)
            done_count = service_stats["service_done_counts"].get(service, 0)
            completion_rate_service = (done_count / needed_count * 100) if needed_count > 0 else 0
            
            stat_data.append({
                "الخدمة": service,
                "مطلوبة": needed_count,
                "منفذة": done_count,
                "متبقية": needed_count - done_count,
                "نسبة الإنجاز": f"{completion_rate_service:.1f}%",
                "حالة": "✅ ممتاز" if completion_rate_service >= 90 else 
                       "🟢 جيد" if completion_rate_service >= 70 else 
                       "🟡 متوسط" if completion_rate_service >= 50 else 
                       "🔴 ضعيف"
            })
        
        if stat_data:
            stat_df = pd.DataFrame(stat_data)
            st.dataframe(stat_df, use_container_width=True, height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للخدمات.")
    
    with stat_tabs[1]:
        st.markdown("#### 📋 توزيع الخدمات")
        
        if service_stats["service_counts"]:
            # محاولة استخدام plotly إذا كان متاحاً
            try:
                import plotly.express as px
                
                plot_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "مطلوبة",
                        "العدد": needed_count
                    })
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "منفذة",
                        "العدد": done_count
                    })
                
                plot_df = pd.DataFrame(plot_data)
                
                # عرض المخطط
                fig = px.bar(
                    plot_df, 
                    x="الخدمة", 
                    y="العدد", 
                    color="النوع",
                    barmode="group",
                    title="توزيع الخدمات المطلوبة والمنفذة",
                    color_discrete_map={
                        "مطلوبة": "#FF6B6B",
                        "منفذة": "#4ECDC4"
                    }
                )
                fig.update_layout(
                    xaxis_title="الخدمة",
                    yaxis_title="العدد",
                    showlegend=True,
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # مخطط دائري للنسبة العامة
                fig2 = px.pie(
                    names=["✅ منفذة", "⏳ غير منفذة"],
                    values=[service_stats["total_done_services"], 
                           service_stats["total_needed_services"] - service_stats["total_done_services"]],
                    title="نسبة الإنجاز العامة",
                    color_discrete_sequence=["#4ECDC4", "#FF6B6B"]
                )
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
                
            except ImportError:
                # استخدام streamlit native charts بدلاً من plotly
                st.info("📊 عرض البيانات باستخدام الرسوم البيانية المضمنة في Streamlit")
                
                # عرض جدول بسيط للتوزيع
                st.markdown("**📋 توزيع الخدمات:**")
                
                dist_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    completion_rate = (done_count / needed_count * 100) if needed_count > 0 else 0
                    
                    dist_data.append({
                        "الخدمة": service,
                        "مطلوبة": needed_count,
                        "منفذة": done_count,
                        "نسبة": f"{completion_rate:.1f}%"
                    })
                
                if dist_data:
                    dist_df = pd.DataFrame(dist_data).sort_values("نسبة", ascending=False)
                    st.dataframe(dist_df, use_container_width=True, height=300)
                
                # مخطط شريطي بسيط باستخدام streamlit
                st.markdown("**📊 مخطط الخدمات المطلوبة مقابل المنفذة:**")
                
                # تحضير البيانات للرسم البياني
                chart_data = pd.DataFrame({
                    "الخدمة": list(service_stats["service_counts"].keys()),
                    "مطلوبة": list(service_stats["service_counts"].values()),
                    "منفذة": [service_stats["service_done_counts"].get(service, 0) 
                              for service in service_stats["service_counts"].keys()]
                })
                
                # أخذ أول 10 خدمات لعرضها بشكل أوضح
                if len(chart_data) > 10:
                    chart_data = chart_data.nlargest(10, "مطلوبة")
                
                st.bar_chart(
                    chart_data.set_index("الخدمة"),
                    height=400
                )
                
                # عرض النسبة العامة كـ progress bar
                st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
                st.progress(completion_rate / 100)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض المخططات.")
    
    with stat_tabs[2]:
        st.markdown("#### 📊 الإحصائيات حسب الشريحة")
        
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            completion_rate_slice = (slice_data["total_done"] / slice_data["total_needed"] * 100) if slice_data["total_needed"] > 0 else 0
            
            slice_stats_data.append({
                "الشريحة": slice_key,
                "الخدمات المطلوبة": slice_data["total_needed"],
                "الخدمات المنفذة": slice_data["total_done"],
                "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                "نسبة الإنجاز": f"{completion_rate_slice:.1f}%",
                "حالة الشريحة": "✅ ممتازة" if completion_rate_slice >= 90 else 
                               "🟢 جيدة" if completion_rate_slice >= 70 else 
                               "🟡 متوسطة" if completion_rate_slice >= 50 else 
                               "🔴 ضعيفة"
            })
        
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            st.dataframe(slice_stats_df, use_container_width=True, height=400)

# ===============================
# ⏱️ التحليل الزمني المحسن للأحداث
# ===============================
def parse_date(date_str):
    """تحويل التاريخ إلى كائن datetime"""
    if not date_str or pd.isna(date_str) or str(date_str).strip() in ["-", "nan", "null", "none"]:
        return None
    
    date_str = str(date_str).strip()
    
    # تحويل الأرقام العربية إلى إنجليزية
    arabic_to_english = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    
    converted_date = ""
    for char in date_str:
        converted_date += arabic_to_english.get(char, char)
    
    # أنماط التاريخ المحتملة
    patterns = [
        (r'(\d{1,2})[/\-\\\.](\d{1,2})[/\-\\\.](\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
        (r'(\d{4})[/\-\\\.](\d{1,2})[/\-\\\.](\d{1,2})', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r'(\d{1,2})[/\-\\\.](\d{1,2})[/\-\\\.](\d{2})', lambda m: datetime(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))),
    ]
    
    for pattern, converter in patterns:
        match = re.match(pattern, converted_date)
        if match:
            try:
                return converter(match)
            except:
                continue
    
    return None

def analyze_event_time_intervals_enhanced(results_df, event_keyword):
    """تحليل زمني محسّن للأحداث مع ترتيب حسب الماكينة"""
    if results_df.empty or 'Event' not in results_df.columns or 'Date' not in results_df.columns:
        return None
    
    filtered_events = results_df[results_df['Event'].astype(str).str.contains(event_keyword, case=False, na=False)].copy()
    
    if filtered_events.empty:
        return None
    
    filtered_events['Parsed_Date'] = filtered_events['Date'].apply(parse_date)
    filtered_events = filtered_events[filtered_events['Parsed_Date'].notna()]
    
    if filtered_events.empty:
        return None
    
    filtered_events['Card_Number_Clean'] = pd.to_numeric(filtered_events['Card Number'], errors='coerce')
    filtered_events = filtered_events.sort_values(['Card_Number_Clean', 'Parsed_Date'])
    
    machine_analysis = {}
    all_intervals = []
    
    for machine in filtered_events['Card Number'].unique():
        machine_events = filtered_events[filtered_events['Card Number'] == machine]
        machine_events = machine_events.sort_values('Parsed_Date')
        
        machine_intervals = []
        total_events = len(machine_events)
        
        if total_events > 1:
            for i in range(total_events - 1):
                current = machine_events.iloc[i]
                next_event = machine_events.iloc[i + 1]
                
                days_between = (next_event['Parsed_Date'] - current['Parsed_Date']).days
                
                interval_data = {
                    'الماكينة': machine,
                    'رقم الحدث': f"{i+1} → {i+2}",
                    'الحدث الأول': str(current['Event'])[:50] + ('...' if len(str(current['Event'])) > 50 else ''),
                    'التاريخ الأول': current['Date'],
                    'الحدث التالي': str(next_event['Event'])[:50] + ('...' if len(str(next_event['Event'])) > 50 else ''),
                    'التاريخ التالي': next_event['Date'],
                    'الأيام بينهما': days_between,
                    'الأسابيع بينهما': round(days_between / 7, 1),
                    'الأشهر بينهما': round(days_between / 30, 1),
                    'فني الخدمة (الأول)': current.get('Servised by', '-'),
                    'فني الخدمة (التالي)': next_event.get('Servised by', '-')
                }
                
                machine_intervals.append(interval_data)
                all_intervals.append(interval_data)
        
        if machine_intervals:
            days_list = [interval['الأيام بينهما'] for interval in machine_intervals]
            machine_analysis[machine] = {
                'عدد الأحداث': total_events,
                'عدد الفترات': len(machine_intervals),
                'أقصر فترة (يوم)': min(days_list) if days_list else 0,
                'أطول فترة (يوم)': max(days_list) if days_list else 0,
                'متوسط الفترة (يوم)': round(np.mean(days_list), 1) if days_list else 0,
                'الوسيط (يوم)': np.median(days_list) if days_list else 0,
                'الفترات': machine_intervals
            }
    
    if all_intervals:
        days_list = [interval['الأيام بينهما'] for interval in all_intervals]
        general_stats = {
            'إجمالي الأحداث': len(filtered_events),
            'عدد الماكينات': filtered_events['Card Number'].nunique(),
            'إجمالي الفترات': len(all_intervals),
            'أقصر فترة عامة (يوم)': min(days_list),
            'أطول فترة عامة (يوم)': max(days_list),
            'المتوسط العام (يوم)': round(np.mean(days_list), 1),
            'الوسيط العام (يوم)': np.median(days_list),
            'الانحراف المعياري (يوم)': round(np.std(days_list), 1) if len(days_list) > 1 else 0
        }
    else:
        general_stats = None
    
    return {
        'event_keyword': event_keyword,
        'filtered_events': filtered_events,
        'machine_analysis': machine_analysis,
        'all_intervals': all_intervals,
        'general_stats': general_stats
    }

# ===============================
# 🔍 فحص الإيفينت والكوريكشن مع التحليل الزمني
# ===============================
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "search_params" not in st.session_state:
        st.session_state.search_params = {
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "sort_by": "رقم الماكينة"
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    st.markdown("### 🔍 بحث متعدد المعايير")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        card_numbers = st.text_input(
            "🔢 أرقام الماكينات (مثال: 1,3,5 أو 1-5):",
            value=st.session_state.search_params.get("card_numbers", ""),
            key="input_cards",
            placeholder="اتركه فارغاً للبحث في كل الماكينات"
        )
        
        date_input = st.text_input(
            "📅 التواريخ (مثال: 2024 أو 1/2024):",
            value=st.session_state.search_params.get("date_range", ""),
            key="input_date",
            placeholder="اتركه فارغاً للبحث في كل التواريخ"
        )
    
    with col2:
        tech_names = st.text_input(
            "👨‍🔧 فنيو الخدمة (مثال: أحمد, محمد, علي):",
            value=st.session_state.search_params.get("tech_names", ""),
            key="input_techs",
            placeholder="اتركه فارغاً للبحث في كل الفنيين"
        )
        
        search_text = st.text_input(
            "📝 نص البحث (مثال: صيانة, إصلاح, تغيير):",
            value=st.session_state.search_params.get("search_text", ""),
            key="input_text",
            placeholder="اتركه فارغاً للبحث في كل النصوص"
        )
    
    with st.expander("⚙ خيارات متقدمة", expanded=False):
        col_adv1, col_adv2, col_adv3 = st.columns(3)
        with col_adv1:
            search_mode = st.radio(
                "طريقة البحث:",
                ["بحث جزئي", "مطابقة كاملة"],
                index=0 if not st.session_state.search_params.get("exact_match") else 1,
                key="radio_search_mode"
            )
        with col_adv2:
            include_empty = st.checkbox(
                "تضمين الحقول الفارغة",
                value=st.session_state.search_params.get("include_empty", True),
                key="checkbox_include_empty"
            )
        with col_adv3:
            sort_by = st.selectbox(
                "ترتيب النتائج:",
                ["رقم الماكينة", "التاريخ", "فني الخدمة"],
                index=["رقم الماكينة", "التاريخ", "فني الخدمة"].index(
                    st.session_state.search_params.get("sort_by", "رقم الماكينة")
                ),
                key="select_sort_by"
            )
    
    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        search_clicked = st.button(
            "🔍 **بدء البحث**",
            type="primary",
            use_container_width=True,
            key="main_search_btn"
        )
    with col_btn2:
        if st.button("🗑 **مسح الحقول**", use_container_width=True, key="clear_fields"):
            st.session_state.search_params = {
                "card_numbers": "",
                "date_range": "",
                "tech_names": "",
                "search_text": "",
                "exact_match": False,
                "include_empty": True,
                "sort_by": "رقم الماكينة"
            }
            st.session_state.search_triggered = False
            st.rerun()
    with col_btn3:
        if st.button("📊 **عرض كل البيانات**", use_container_width=True, key="show_all"):
            st.session_state.search_params = {
                "card_numbers": "",
                "date_range": "",
                "tech_names": "",
                "search_text": "",
                "exact_match": False,
                "include_empty": True,
                "sort_by": "رقم الماكينة"
            }
            st.session_state.search_triggered = True
            st.rerun()
    
    if card_numbers != st.session_state.search_params.get("card_numbers", ""):
        st.session_state.search_params["card_numbers"] = card_numbers
    
    if date_input != st.session_state.search_params.get("date_range", ""):
        st.session_state.search_params["date_range"] = date_input
    
    if tech_names != st.session_state.search_params.get("tech_names", ""):
        st.session_state.search_params["tech_names"] = tech_names
    
    if search_text != st.session_state.search_params.get("search_text", ""):
        st.session_state.search_params["search_text"] = search_text
    
    st.session_state.search_params["exact_match"] = (search_mode == "مطابقة كاملة")
    st.session_state.search_params["include_empty"] = include_empty
    st.session_state.search_params["sort_by"] = sort_by
    
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        search_params = st.session_state.search_params.copy()
        
        search_results = perform_search(search_params, all_sheets)
        
        if search_results is not None and not search_results.empty:
            display_search_results(search_results, search_params)
            
            add_enhanced_time_analysis_section(search_results)
        else:
            st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")

def perform_search(search_params, all_sheets):
    """تنفيذ البحث"""
    all_results = []
    
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
            
        card_num = int(card_num_match.group(1))
        
        if search_params["card_numbers"]:
            target_numbers = parse_card_numbers(search_params["card_numbers"])
            if target_numbers and card_num not in target_numbers:
                continue
        
        df = all_sheets[sheet_name].copy()
        
        for _, row in df.iterrows():
            event_value = "-"
            correction_value = "-"
            
            for col in df.columns:
                col_normalized = normalize_name(col)
                if "event" in col_normalized or "الحدث" in col_normalized:
                    if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                        event_value = str(row[col]).strip()
                
                if "correction" in col_normalized or "تصحيح" in col_normalized:
                    if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                        correction_value = str(row[col]).strip()
            
            if event_value == "-" and correction_value == "-":
                continue
            
            if search_params["tech_names"]:
                tech_names = [t.strip().lower() for t in search_params["tech_names"].split(',') if t.strip()]
                row_tech = get_servised_by_value(row).lower()
                
                if row_tech == "-" and not search_params["include_empty"]:
                    continue
                
                tech_match = False
                if row_tech != "-":
                    for tech in tech_names:
                        if search_params["exact_match"]:
                            if tech == row_tech:
                                tech_match = True
                                break
                        else:
                            if tech in row_tech:
                                tech_match = True
                                break
                
                if not tech_match:
                    continue
            
            if search_params["date_range"]:
                row_date = str(row.get("Date", "")).strip().lower() if pd.notna(row.get("Date")) else ""
                date_terms = [d.strip().lower() for d in search_params["date_range"].split(',') if d.strip()]
                
                if not row_date and not search_params["include_empty"]:
                    continue
                
                date_match = False
                if row_date:
                    for date_term in date_terms:
                        if search_params["exact_match"]:
                            if date_term == row_date:
                                date_match = True
                                break
                        else:
                            if date_term in row_date:
                                date_match = True
                                break
                
                if not date_match:
                    continue
            
            if search_params["search_text"]:
                search_terms = [t.strip().lower() for t in search_params["search_text"].split(',') if t.strip()]
                combined_text = f"{event_value.lower()} {correction_value.lower()}"
                
                if not event_value and not correction_value and not search_params["include_empty"]:
                    continue
                
                text_match = False
                for term in search_terms:
                    if search_params["exact_match"]:
                        if term == event_value.lower() or term == correction_value.lower():
                            text_match = True
                            break
                    else:
                        if term in combined_text:
                            text_match = True
                            break
                
                if not text_match:
                    continue
            
            card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
            date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
            tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
            servised_by_value = get_servised_by_value(row)
            
            all_results.append({
                "Card Number": card_num_value,
                "Event": event_value,
                "Correction": correction_value,
                "Servised by": servised_by_value,
                "Tones": tones,
                "Date": date
            })
    
    if all_results:
        return pd.DataFrame(all_results)
    return pd.DataFrame()

def parse_card_numbers(card_numbers_str):
    """تحليل أرقام الماكينات"""
    if not card_numbers_str:
        return set()
    
    numbers = set()
    
    try:
        parts = card_numbers_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    numbers.update(range(start, end + 1))
                except:
                    continue
            else:
                try:
                    num = int(part)
                    numbers.add(num)
                except:
                    continue
    except:
        return set()
    
    return numbers

def display_search_results(results, search_params):
    """عرض نتائج البحث"""
    if results.empty:
        st.warning("⚠ لا توجد نتائج لعرضها")
        return
    
    display_df = results.copy()
    
    display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Card_Number_Clean'], 
                                          ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, True, False], na_position='last')
    else:
        display_df = display_df.sort_values(by=['Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, False], na_position='last')
    
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    
    with col2:
        unique_machines = display_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        if 'Correction' in display_df.columns:
            with_correction = display_df[display_df["Correction"] != "-"].shape[0]
            st.metric("✏ تحتوي على تصحيح", with_correction)
        else:
            st.metric("✏ تحتوي على تصحيح", 0)
    
    st.markdown("### 📋 النتائج التفصيلية")
    
    columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date']
    columns_to_show = [col for col in columns_to_show if col in display_df.columns]
    
    # تطبيق تلوين للجدول
    def color_events_corrections_row(row):
        event = row.get('Event', '-')
        correction = row.get('Correction', '-')
        
        if event != '-' and correction != '-':
            return [f"background-color: {COLOR_CONFIG['service_done']}"] * len(row)
        elif event != '-' and correction == '-':
            return [f"background-color: {COLOR_CONFIG['service_partial']}"] * len(row)
        else:
            if row.name % 2 == 0:
                return [f"background-color: {COLOR_CONFIG['even_row']}"] * len(row)
            else:
                return [f"background-color: {COLOR_CONFIG['odd_row']}"] * len(row)
    
    styled_display_df = display_df[columns_to_show].style.apply(color_events_corrections_row, axis=1)
    
    st.dataframe(
        styled_display_df,
        use_container_width=True,
        height=500
    )
    
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    if not results.empty:
        buffer_excel = io.BytesIO()
        results.to_excel(buffer_excel, index=False, engine="openpyxl")
        
        st.download_button(
            label="📊 حفظ كملف Excel",
            data=buffer_excel.getvalue(),
            file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def add_enhanced_time_analysis_section(results_df):
    """إضافة قسم التحليل الزمني المحسن"""
    st.markdown("---")
    st.markdown("## ⏱️ التحليل الزمني المحسن للأحداث")
    
    st.markdown("#### 🔍 تحليل الفترات الزمنية بين الأحداث")
    
    event_keyword = st.text_input(
        "الكلمة المطلوبة (مثال: سير، محرك، صيانة):",
        placeholder="أدخل كلمة أو جزء من الحدث للتحليل الزمني",
        key="enhanced_time_analysis_keyword"
    )
    
    if event_keyword and st.button("🔬 تحليل الفترات الزمنية", type="primary", key="enhanced_analysis_btn"):
        with st.spinner("🔄 جاري تحليل الفترات الزمنية..."):
            analysis_result = analyze_event_time_intervals_enhanced(results_df, event_keyword)
            
            if analysis_result:
                display_enhanced_time_analysis(analysis_result)
            else:
                st.warning(f"⚠ لم يتم العثور على أحداث تحتوي على '{event_keyword}' أو لا يمكن تحليل الفترات الزمنية.")

def display_enhanced_time_analysis(analysis_result):
    """عرض التحليل الزمني المحسن"""
    if not analysis_result:
        return
    
    event_keyword = analysis_result['event_keyword']
    machine_analysis = analysis_result['machine_analysis']
    general_stats = analysis_result['general_stats']
    
    st.markdown(f"### ⏱️ التحليل الزمني لكلمة: **{event_keyword}**")
    
    if general_stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🔄 إجمالي الأحداث", general_stats['إجمالي الأحداث'])
        
        with col2:
            st.metric("🔢 عدد الماكينات", general_stats['عدد الماكينات'])
        
        with col3:
            st.metric("📊 متوسط الأيام", f"{general_stats['المتوسط العام (يوم)']}")
        
        with col4:
            st.metric("📈 إجمالي الفترات", general_stats['إجمالي الفترات'])
    
    st.markdown("---")
    
    if general_stats:
        st.markdown("#### 📊 الإحصائيات العامة")
        
        stats_data = []
        for key, value in general_stats.items():
            if key not in ['إجمالي الأحداث', 'عدد الماكينات', 'إجمالي الفترات']:
                stats_data.append({'المقياس': key, 'القيمة': value})
        
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True)
    
    if machine_analysis:
        st.markdown("#### 🏭 التحليل حسب الماكينة")
        
        machine_stats_data = []
        for machine, stats in machine_analysis.items():
            machine_stats_data.append({
                'الماكينة': machine,
                'عدد الأحداث': stats['عدد الأحداث'],
                'عدد الفترات': stats['عدد الفترات'],
                'أقصر فترة': stats['أقصر فترة (يوم)'],
                'أطول فترة': stats['أطول فترة (يوم)'],
                'المتوسط': stats['متوسط الفترة (يوم)'],
                'الوسيط': stats['الوسيط (يوم)']
            })
        
        machine_stats_df = pd.DataFrame(machine_stats_data)
        
        st.dataframe(
            machine_stats_df.sort_values('الماكينة'),
            use_container_width=True,
            height=300
        )
        
        st.markdown("##### 🔍 عرض تفاصيل ماكينة محددة")
        selected_machine = st.selectbox(
            "اختر الماكينة:",
            options=list(machine_analysis.keys()),
            key="select_machine_for_details"
        )
        
        if selected_machine:
            machine_stats = machine_analysis[selected_machine]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🔢 عدد الأحداث", machine_stats['عدد الأحداث'])
            with col2:
                st.metric("📈 عدد الفترات", machine_stats['عدد الفترات'])
            with col3:
                st.metric("📊 متوسط الأيام", machine_stats['متوسط الفترة (يوم)'])
            with col4:
                st.metric("⚖️ الوسيط", machine_stats['الوسيط (يوم)'])
            
            if machine_stats['الفترات']:
                st.markdown("##### 📋 الفترات الزمنية التفصيلية")
                
                machine_intervals_df = pd.DataFrame(machine_stats['الفترات'])
                
                col1, col2 = st.columns(2)
                with col1:
                    min_days = st.number_input("الحد الأدنى للأيام:", min_value=0, value=0, step=1, 
                                               key=f"min_days_{selected_machine}")
                with col2:
                    max_days = st.number_input("الحد الأقصى للأيام:", min_value=min_days, value=365, step=1,
                                               key=f"max_days_{selected_machine}")
                
                filtered_intervals = machine_intervals_df[
                    (machine_intervals_df['الأيام بينهما'] >= min_days) & 
                    (machine_intervals_df['الأيام بينهما'] <= max_days)
                ]
                
                st.dataframe(
                    filtered_intervals,
                    use_container_width=True,
                    height=400
                )
                
                st.markdown("---")
                buffer = io.BytesIO()
                filtered_intervals.to_excel(buffer, index=False, engine='openpyxl')
                
                st.download_button(
                    label=f"📊 حفظ فترات الماكينة {selected_machine}",
                    data=buffer.getvalue(),
                    file_name=f"فترات_ماكينة_{selected_machine}_{event_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    if analysis_result['all_intervals']:
        st.markdown("#### 📋 جميع الفترات الزمنية")
        
        all_intervals_df = pd.DataFrame(analysis_result['all_intervals'])
        
        st.markdown("##### 🔍 فلترة عامة")
        col1, col2, col3 = st.columns(3)
        with col1:
            global_min_days = st.number_input("الحد الأدنى للأيام:", min_value=0, value=0, step=1, key="global_min_days")
        with col2:
            global_max_days = st.number_input("الحد الأقصى للأيام:", min_value=global_min_days, value=365, step=1, key="global_max_days")
        with col3:
            sort_by = st.selectbox("ترتيب حسب:", ["الماكينة", "الأيام بينهما"], key="global_sort")
        
        filtered_all = all_intervals_df[
            (all_intervals_df['الأيام بينهما'] >= global_min_days) & 
            (all_intervals_df['الأيام بينهما'] <= global_max_days)
        ]
        
        if sort_by == "الأيام بينهما":
            filtered_all = filtered_all.sort_values('الأيام بينهما')
        else:
            filtered_all = filtered_all.sort_values('الماكينة')
        
        st.dataframe(
            filtered_all,
            use_container_width=True,
            height=400
        )
        
        st.markdown("---")
        buffer_all = io.BytesIO()
        filtered_all.to_excel(buffer_all, index=False, engine='openpyxl')
        
        st.download_button(
            label="📊 حفظ كل الفترات",
            data=buffer_all.getvalue(),
            file_name=f"كل_الفترات_{event_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ===============================
# 🛠 إدارة وتعديل البيانات مع تلوين وإضافة/حذف صفوف (من الكود الأول)
# ===============================
def edit_sheet_with_save_button(sheets_edit):
    """تعديل بيانات الشيت مع إضافة/حذف صفوف وتلوين"""
    st.subheader("✏ تعديل البيانات")
    
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    
    if "added_rows" not in st.session_state:
        st.session_state.added_rows = {}
    
    if "deleted_rows" not in st.session_state:
        st.session_state.deleted_rows = {}
    
    if "modified_rows" not in st.session_state:
        st.session_state.modified_rows = {}
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    
    df = sheets_edit[sheet_name].astype(str).copy()
    
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # عرض الصفوف المضاف حديثاً ضمن الرنج المناسب
    if sheet_name in st.session_state.added_rows and st.session_state.added_rows[sheet_name]:
        st.markdown("#### ➕ الصفوف المضاف حديثاً")
        added_rows_list = st.session_state.added_rows[sheet_name]
        
        if added_rows_list:
            added_df = df.iloc[added_rows_list].copy()
            
            # إضافة عمود للإشارة إلى أن الصف مضاف
            added_df.insert(0, "💡 الحالة", ["مضاف حديثاً"] * len(added_df))
            
            # تلوين الصفوف المضاف
            def color_added_row(row):
                return [f"background-color: {COLOR_CONFIG['row_added']}"] * len(row)
            
            styled_added_df = added_df.style.apply(color_added_row, axis=1)
            
            st.dataframe(
                styled_added_df,
                use_container_width=True,
                height=200
            )
    
    # محرر البيانات مع إضافة وحذف ديناميكي للصفوف
    st.markdown("#### 🛠 محرر البيانات الديناميكي")
    
    # أزرار للتحكم بالصفوف
    col_buttons1, col_buttons2, col_buttons3 = st.columns(3)
    
    with col_buttons1:
        if st.button("➕ إضافة صف جديد في النهاية", key=f"add_row_{sheet_name}"):
            new_row = pd.Series({col: "" for col in df.columns})
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.unsaved_changes[sheet_name] = True
            
            # تسجيل الصف المضاف
            if sheet_name not in st.session_state.added_rows:
                st.session_state.added_rows[sheet_name] = []
            st.session_state.added_rows[sheet_name].append(len(df) - 1)
            
            st.success("✅ تم إضافة صف جديد. سيظهر بعد حفظ التغييرات.")
    
    with col_buttons2:
        if st.button("🗑 حذف الصف المحدد", key=f"delete_selected_{sheet_name}"):
            if "selected_rows" in st.session_state and st.session_state.selected_rows:
                rows_to_delete = sorted(st.session_state.selected_rows, reverse=True)
                
                if sheet_name not in st.session_state.deleted_rows:
                    st.session_state.deleted_rows[sheet_name] = []
                
                for row_idx in rows_to_delete:
                    if 0 <= row_idx < len(df):
                        # تسجيل الصف المحذوف
                        st.session_state.deleted_rows[sheet_name].append(row_idx)
                        
                        # إزالة الصف من المضاف إن كان مضافاً
                        if sheet_name in st.session_state.added_rows:
                            if row_idx in st.session_state.added_rows[sheet_name]:
                                st.session_state.added_rows[sheet_name].remove(row_idx)
                        
                        df = df.drop(row_idx).reset_index(drop=True)
                
                st.session_state.unsaved_changes[sheet_name] = True
                st.success(f"✅ تم حذف {len(rows_to_delete)} صفوف.")
                st.session_state.selected_rows = []
            else:
                st.warning("⚠ الرجاء تحديد الصفوف أولاً باستخدام زر التحديد في الجدول.")
    
    with col_buttons3:
        if st.button("🔄 استعادة الصفوف المحذوفة", key=f"restore_deleted_{sheet_name}"):
            if sheet_name in st.session_state.deleted_rows and st.session_state.deleted_rows[sheet_name]:
                st.info(f"📋 هناك {len(st.session_state.deleted_rows[sheet_name])} صفوف محذوفة.")
                
                if st.checkbox("تأكيد استعادة جميع الصفوف المحذوفة"):
                    st.session_state.deleted_rows[sheet_name] = []
                    st.success("✅ تم استعادة الصفوف المحذوفة.")
                    st.session_state.unsaved_changes[sheet_name] = True
    
    st.markdown("---")
    
    # محرر البيانات
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        key=f"editor_{sheet_name}",
        column_config={
            "_index": st.column_config.NumberColumn(
                "رقم الصف",
                help="رقم الصف في الجدول",
                width="small"
            )
        }
    )
    
    # التحقق من وجود تغييرات
    has_changes = not edited_df.equals(df)
    
    # اكتشاف الصفوف المعدلة
    if not has_changes and len(edited_df) == len(df):
        for idx in range(len(df)):
            if not df.iloc[idx].equals(edited_df.iloc[idx]):
                has_changes = True
                if sheet_name not in st.session_state.modified_rows:
                    st.session_state.modified_rows[sheet_name] = []
                if idx not in st.session_state.modified_rows[sheet_name]:
                    st.session_state.modified_rows[sheet_name].append(idx)
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        
        # حساب التغييرات
        changes_summary = calculate_changes_summary(df, edited_df, sheet_name)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل يدوي في شيت {sheet_name} - {changes_summary}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    
                    # تحديث البيانات بعد الحفظ
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    st.session_state.unsaved_changes[sheet_name] = False
                    
                    # مسح سجلات الصفوف المضاف/محذوف بعد الحفظ الناجح
                    if sheet_name in st.session_state.added_rows:
                        st.session_state.added_rows[sheet_name] = []
                    if sheet_name in st.session_state.deleted_rows:
                        st.session_state.deleted_rows[sheet_name] = []
                    if sheet_name in st.session_state.modified_rows:
                        st.session_state.modified_rows[sheet_name] = []
                    
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    
                    # مسح سجلات التغييرات
                    st.session_state.unsaved_changes[sheet_name] = False
                    if sheet_name in st.session_state.added_rows:
                        st.session_state.added_rows[sheet_name] = []
                    if sheet_name in st.session_state.deleted_rows:
                        st.session_state.deleted_rows[sheet_name] = []
                    if sheet_name in st.session_state.modified_rows:
                        st.session_state.modified_rows[sheet_name] = []
                    
                    st.info(f"↩️ تم التراجع عن التغييرات في شيت {sheet_name}")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
        
        with col3:
            with st.expander("📊 ملخص التغييرات", expanded=True):
                st.write(f"**🔄 تغييرات في شيت:** {sheet_name}")
                st.write(f"**➕ صفوف مضافة:** {changes_summary.get('added', 0)}")
                st.write(f"**🗑️ صفوف محذوفة:** {changes_summary.get('deleted', 0)}")
                st.write(f"**✏️ صفوف معدلة:** {changes_summary.get('modified', 0)}")
                st.write(f"**🔢 إجمالي التغييرات:** {changes_summary.get('total', 0)}")
                
                if changes_summary.get('added', 0) > 0:
                    st.info("💡 **ملاحظة:** الصفوف المضاف حديثاً سوف تظهر في عرض البيانات ضمن الرنج المناسب بعد الحفظ.")
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
            st.session_state.unsaved_changes[sheet_name] = False
        
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    
    return sheets_edit

def calculate_changes_summary(original_df, edited_df, sheet_name):
    """حساب ملخص التغييرات"""
    summary = {
        "added": 0,
        "deleted": 0,
        "modified": 0,
        "total": 0
    }
    
    # حساب الصفوف المضافة والمحذوفة
    if len(edited_df) > len(original_df):
        summary["added"] = len(edited_df) - len(original_df)
    elif len(edited_df) < len(original_df):
        summary["deleted"] = len(original_df) - len(edited_df)
    
    # حساب الصفوف المعدلة
    if sheet_name in st.session_state.modified_rows:
        summary["modified"] = len(st.session_state.modified_rows[sheet_name])
    
    # حساب إجمالي التغييرات
    summary["total"] = summary["added"] + summary["deleted"] + summary["modified"]
    
    # إنشاء نص وصفي
    changes_text = ""
    if summary["added"] > 0:
        changes_text += f"أضيف {summary['added']} صف"
        if summary["added"] > 1:
            changes_text += "وف"
    
    if summary["deleted"] > 0:
        if changes_text:
            changes_text += "، "
        changes_text += f"حذف {summary['deleted']} صف"
        if summary["deleted"] > 1:
            changes_text += "وف"
    
    if summary["modified"] > 0:
        if changes_text:
            changes_text += "، "
        changes_text += f"عدل {summary['modified']} صف"
        if summary["modified"] > 1:
            changes_text += "وف"
    
    if not changes_text:
        changes_text = "لا توجد تغييرات"
    
    summary["text"] = changes_text
    return summary

def add_new_event(sheets_edit):
    """إضافة حدث جديد"""
    st.subheader("➕ إضافة حدث جديد")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    st.markdown("أدخل بيانات الحدث الجديد:")
    
    col1, col2 = st.columns(2)
    with col1:
        card_num = st.text_input("رقم الماكينة:", key="new_event_card")
        event_text = st.text_area("الحدث:", key="new_event_text")
    with col2:
        correction_text = st.text_area("التصحيح:", key="new_correction_text")
        serviced_by = st.text_input("فني الخدمة:", key="new_serviced_by")
    
    event_date = st.text_input("التاريخ (مثال: 20\\5\\2025):", key="new_event_date")
    
    # تحديد الرنج المناسب إذا أمكن
    if "Min_Tones" in df.columns and "Max_Tones" in df.columns:
        st.markdown("### 🎯 تحديد الرنج المناسب")
        
        col_range1, col_range2 = st.columns(2)
        with col_range1:
            min_tones = st.number_input("الحد الأدنى للطن:", min_value=0, value=0, step=100, key="new_min_tones")
        with col_range2:
            max_tones = st.number_input("الحد الأقصى للطن:", min_value=min_tones, value=1000, step=100, key="new_max_tones")
    
    if st.button("💾 إضافة الحدث الجديد", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        
        new_row = {}
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
        # إضافة بيانات الرنج إذا تم تحديدها
        if "min_tones" in locals() and "max_tones" in locals():
            new_row["Min_Tones"] = str(min_tones)
            new_row["Max_Tones"] = str(max_tones)
        
        event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
        if event_columns and event_text.strip():
            new_row[event_columns[0]] = event_text.strip()
        elif not event_columns and event_text.strip():
            new_row["Event"] = event_text.strip()
        
        correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
        if correction_columns and correction_text.strip():
            new_row[correction_columns[0]] = correction_text.strip()
        elif not correction_columns and correction_text.strip():
            new_row["Correction"] = correction_text.strip()
        
        servised_col = None
        servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
        if servised_columns:
            servised_col = servised_columns[0]
        else:
            for col in df.columns:
                if "servis" in normalize_name(col) or "service" in normalize_name(col) or "فني" in col:
                    servised_col = col
                    break
            if not servised_col:
                servised_col = "Servised by"
        
        if serviced_by.strip():
            new_row[servised_col] = serviced_by.strip()
        
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new.astype(object)
        
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}"
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            st.rerun()

def edit_events_and_corrections(sheets_edit):
    """تعديل الإيفينت والكوريكشن"""
    st.subheader("✏ تعديل الحدث والتصحيح")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح)")
    
    display_columns = ["card", "Date"]
    
    event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
    if event_columns:
        display_columns.append(event_columns[0])
    
    correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
    if correction_columns:
        display_columns.append(correction_columns[0])
    
    servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
    if servised_columns:
        display_columns.append(servised_columns[0])
    
    display_df = df[display_columns].copy()
    
    # تطبيق تلوين على الجدول
    def color_events_display(row):
        event_val = row.get(event_columns[0] if event_columns else "", "-")
        correction_val = row.get(correction_columns[0] if correction_columns else "", "-")
        
        if event_val != "-" and correction_val != "-":
            return [f"background-color: {COLOR_CONFIG['service_done']}"] * len(row)
        elif event_val != "-" and correction_val == "-":
            return [f"background-color: {COLOR_CONFIG['service_partial']}"] * len(row)
        else:
            if row.name % 2 == 0:
                return [f"background-color: {COLOR_CONFIG['even_row']}"] * len(row)
            else:
                return [f"background-color: {COLOR_CONFIG['odd_row']}"] * len(row)
    
    styled_display_df = display_df.style.apply(color_events_display, axis=1)
    
    st.dataframe(styled_display_df, use_container_width=True)
    
    st.markdown("### ✏ اختر الصف للتعديل")
    row_index = st.number_input("رقم الصف (ابدأ من 0):", min_value=0, max_value=len(df)-1, step=1, key="edit_row_index")
    
    if st.button("تحميل بيانات الصف", key="load_row_data"):
        if 0 <= row_index < len(df):
            st.session_state["editing_row"] = row_index
            st.session_state["editing_data"] = df.iloc[row_index].to_dict()
    
    if "editing_data" in st.session_state:
        editing_data = st.session_state["editing_data"]
        
        st.markdown("### تعديل البيانات")
        col1, col2 = st.columns(2)
        with col1:
            new_card = st.text_input("رقم الماكينة:", value=editing_data.get("card", ""), key="edit_card")
            new_date = st.text_input("التاريخ:", value=editing_data.get("Date", ""), key="edit_date")
        with col2:
            new_serviced_by = st.text_input("فني الخدمة:", value=editing_data.get("Servised by", ""), key="edit_serviced_by")
        
        event_col = None
        correction_col = None
        
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["event", "events", "الحدث", "الأحداث"]:
                event_col = col
            elif col_norm in ["correction", "correct", "تصحيح", "تصويب"]:
                correction_col = col
        
        if event_col:
            new_event = st.text_area("الحدث:", value=editing_data.get(event_col, ""), key="edit_event")
        if correction_col:
            new_correction = st.text_area("التصحيح:", value=editing_data.get(correction_col, ""), key="edit_correction")
        
        if st.button("💾 حفظ التعديلات", key="save_edits_btn"):
            df.at[row_index, "card"] = new_card
            df.at[row_index, "Date"] = new_date
            
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            
            servised_col = None
            for col in df.columns:
                if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]:
                    servised_col = col
                    break
            
            if servised_col and new_serviced_by.strip():
                df.at[row_index, servised_col] = new_serviced_by.strip()
            
            sheets_edit[sheet_name] = df.astype(object)
            
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"تعديل حدث في {sheet_name} - الصف {row_index}"
            )
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# ===============================
# 👥 إدارة المستخدمين
# ===============================
def manage_users():
    """إدارة المستخدمين والصلاحيات"""
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    
    current_user = st.session_state.get("username")
    if current_user != "admin":
        st.error("❌ الصلاحية مقتصرة على المسؤول (admin) فقط.")
        return
    
    st.markdown("### 📋 المستخدمون الحاليون")
    
    if users:
        users_data = []
        for username, user_info in users.items():
            users_data.append({
                "اسم المستخدم": username,
                "الدور": user_info.get("role", "viewer"),
                "الصلاحيات": ", ".join(user_info.get("permissions", ["view"])),
                "تاريخ الإنشاء": user_info.get("created_at", "غير معروف")
            })
        
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True)
    else:
        st.info("ℹ️ لا توجد مستخدمين مسجلين بعد.")
    
    st.markdown("---")
    
    user_tabs = st.tabs(["➕ إضافة مستخدم جديد", "✏ تعديل مستخدم", "🗑 حذف مستخدم"])
    
    with user_tabs[0]:
        st.markdown("#### ➕ إضافة مستخدم جديد")
        
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("اسم المستخدم الجديد:", key="new_username")
            new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
            confirm_password = st.text_input("تأكيد كلمة المرور:", type="password", key="confirm_password")
        
        with col2:
            user_role = st.selectbox(
                "دور المستخدم:",
                ["admin", "editor", "viewer"],
                index=2,
                key="new_user_role"
            )
            
            if user_role == "admin":
                default_permissions = ["all"]
                available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
            elif user_role == "editor":
                default_permissions = ["view", "edit"]
                available_permissions = ["view", "edit", "export"]
            else:
                default_permissions = ["view"]
                available_permissions = ["view", "export"]
            
            selected_permissions = st.multiselect(
                "الصلاحيات:",
                options=available_permissions,
                default=default_permissions,
                key="new_user_permissions"
            )
        
        if st.button("💾 إضافة المستخدم", key="add_user_btn"):
            if not new_username:
                st.warning("⚠ الرجاء إدخال اسم المستخدم.")
                return
            
            current_users = load_users()
            
            if new_username in current_users:
                st.error("❌ اسم المستخدم موجود بالفعل.")
                return
            
            if not new_password:
                st.warning("⚠ الرجاء إدخال كلمة المرور.")
                return
            
            if new_password != confirm_password:
                st.error("❌ كلمة المرور غير مطابقة.")
                return
            
            if len(new_password) < 6:
                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                return
            
            current_users[new_username] = {
                "password": new_password,
                "role": user_role,
                "permissions": selected_permissions if selected_permissions else default_permissions,
                "created_at": datetime.now().isoformat()
            }
            
            if save_users(current_users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح!")
                st.rerun()
            else:
                st.error("❌ حدث خطأ أثناء حفظ المستخدم.")
    
    with user_tabs[1]:
        st.markdown("#### ✏ تعديل مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لتعديلهم.")
        else:
            user_list = list(users.keys())
            
            user_to_edit = st.selectbox(
                "اختر المستخدم للتعديل:",
                user_list,
                key="select_user_to_edit"
            )
            
            if user_to_edit:
                current_users = load_users()
                user_info = current_users.get(user_to_edit, {})
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**المستخدم:** {user_to_edit}")
                    st.info(f"**الدور الحالي:** {user_info.get('role', 'viewer')}")
                    
                    st.markdown("##### 🔐 تغيير كلمة المرور")
                    new_password_edit = st.text_input("كلمة المرور الجديدة:", type="password", 
                                                      key="edit_password")
                    confirm_password_edit = st.text_input("تأكيد كلمة المرور:", type="password", 
                                                         key="edit_confirm_password")
                
                with col2:
                    new_role = st.selectbox(
                        "تغيير الدور:",
                        ["admin", "editor", "viewer"],
                        index=["admin", "editor", "viewer"].index(user_info.get("role", "viewer")),
                        key="edit_user_role"
                    )
                    
                    if new_role == "admin":
                        default_permissions = ["all"]
                        available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
                    elif new_role == "editor":
                        default_permissions = ["view", "edit"]
                        available_permissions = ["view", "edit", "export"]
                    else:
                        default_permissions = ["view"]
                        available_permissions = ["view", "export"]
                    
                    current_permissions = user_info.get("permissions", default_permissions)
                    new_permissions = st.multiselect(
                        "تغيير الصلاحيات:",
                        options=available_permissions,
                        default=current_permissions,
                        key="edit_user_permissions"
                    )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 حفظ التعديلات", key="save_user_edit"):
                        updated = False
                        
                        latest_users = load_users()
                        
                        if user_to_edit not in latest_users:
                            st.error("❌ المستخدم غير موجود.")
                            return
                        
                        if latest_users[user_to_edit].get("role") != new_role or \
                           latest_users[user_to_edit].get("permissions") != new_permissions:
                            latest_users[user_to_edit]["role"] = new_role
                            latest_users[user_to_edit]["permissions"] = new_permissions if new_permissions else default_permissions
                            updated = True
                        
                        if new_password_edit:
                            if new_password_edit != confirm_password_edit:
                                st.error("❌ كلمة المرور غير مطابقة.")
                                return
                            if len(new_password_edit) < 6:
                                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                                return
                            
                            latest_users[user_to_edit]["password"] = new_password_edit
                            updated = True
                        
                        if updated:
                            if save_users(latest_users):
                                st.success(f"✅ تم تحديث المستخدم '{user_to_edit}' بنجاح!")
                                
                                if st.session_state.get("username") == user_to_edit:
                                    st.session_state.user_role = new_role
                                    st.session_state.user_permissions = new_permissions if new_permissions else default_permissions
                                    st.info("🔁 تم تحديث بيانات جلسة العمل الحالية.")
                                
                                st.rerun()
                            else:
                                st.error("❌ حدث خطأ أثناء حفظ التعديلات.")
                        else:
                            st.info("ℹ️ لم يتم إجراء أي تغييرات.")
                
                with col_btn2:
                    if st.button("🔄 تحديث البيانات", key="refresh_user_data"):
                        users = load_users()
                        st.success("✅ تم تحديث البيانات من الملف.")
                        st.rerun()
    
    with user_tabs[2]:
        st.markdown("#### 🗑 حذف مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لحذفهم.")
        else:
            deletable_users = [u for u in users.keys() 
                             if u != "admin" and u != current_user]
            
            if not deletable_users:
                st.warning("⚠ لا يمكن حذف أي مستخدمين.")
            else:
                user_to_delete = st.selectbox(
                    "اختر المستخدم للحذف:",
                    deletable_users,
                    key="select_user_to_delete"
                )
                
                if user_to_delete:
                    user_info = users[user_to_delete]
                    
                    st.warning(f"⚠ **تحذير:** أنت على وشك حذف المستخدم '{user_to_delete}'")
                    st.info(f"**الدور:** {user_info.get('role', 'viewer')}")
                    st.info(f"**تاريخ الإنشاء:** {user_info.get('created_at', 'غير معروف')}")
                    
                    confirm_delete = st.checkbox(f"أؤكد أنني أريد حذف المستخدم '{user_to_delete}'", 
                                                key="confirm_delete")
                    
                    if confirm_delete:
                        if st.button("🗑️ حذف المستخدم نهائياً", type="primary", 
                                    key="delete_user_final"):
                            state = load_state()
                            if user_to_delete in state and state[user_to_delete].get("active"):
                                st.error("❌ لا يمكن حذف المستخدم أثناء تسجيل دخوله.")
                                return
                            
                            latest_users = load_users()
                            
                            if user_to_delete in latest_users:
                                del latest_users[user_to_delete]
                                
                                if save_users(latest_users):
                                    st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح!")
                                    st.rerun()
                                else:
                                    st.error("❌ حدث خطأ أثناء حذف المستخدم.")
                            else:
                                st.error("❌ المستخدم غير موجود.")

# ===============================
# 📞 الدعم الفني
# ===============================
def tech_support():
    """قسم الدعم الفني"""
    st.header("📞 الدعم الفني")
    
    st.markdown(f"""
    ### ℹ️ معلومات التطبيق
    
    **اسم التطبيق:** {APP_CONFIG["APP_TITLE"]}
    **الملف الرئيسي:** {APP_CONFIG["FILE_PATH"]}
    **مستودع GitHub:** {APP_CONFIG["REPO_NAME"]}
    **فرع العمل:** {APP_CONFIG["BRANCH"]}
    
    ### 🔧 استكشاف الأخطاء وإصلاحها
    
    1. **المشكلة:** لا يمكن تحميل الملف من GitHub
       **الحل:** 
       - تأكد من اتصال الإنترنت
       - تحقق من رابط الملف في GitHub
       - اضغط على زر "🔄 تحديث الملف من GitHub"
    
    2. **المشكلة:** لا يمكن حفظ التعديلات
       **الحل:**
       - تأكد من وجود token GitHub في الإعدادات
       - تحقق من صلاحيات الرفع إلى المستودع
    
    3. **المشكلة:** التطبيق يعمل ببطء
       **الحل:**
       - اضغط على زر "🗑 مسح الكاش"
       - قلل عدد الصفوف المعروضة
       - استخدم فلاتر البحث
    
    ### 📊 إحصائيات النظام
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        users = load_users()
        st.metric("👥 عدد المستخدمين", len(users))
    
    with col2:
        state = load_state()
        active_sessions = sum(1 for u in state.values() if u.get("active"))
        st.metric("🔒 جلسات نشطة", f"{active_sessions}/{MAX_ACTIVE_USERS}")
    
    with col3:
        if os.path.exists(APP_CONFIG["LOCAL_FILE"]):
            file_size = os.path.getsize(APP_CONFIG["LOCAL_FILE"]) / (1024 * 1024)
            st.metric("💾 حجم الملف", f"{file_size:.2f} MB")
        else:
            st.metric("💾 حجم الملف", "غير موجود")
    
    st.markdown("---")
    
    st.markdown("### 🖥 معلومات الجلسة الحالية")
    
    if st.session_state.get("logged_in"):
        session_info = {
            "المستخدم": st.session_state.get("username", "غير معروف"),
            "الدور": st.session_state.get("user_role", "غير معروف"),
            "الصلاحيات": ", ".join(st.session_state.get("user_permissions", [])),
            "وقت التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for key, value in session_info.items():
            st.text(f"**{key}:** {value}")
    else:
        st.info("ℹ️ لم يتم تسجيل الدخول")
    
    st.markdown("---")
    if st.button("🔄 إعادة تشغيل التطبيق", key="restart_app"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في إعادة التشغيل: {e}")

# ===============================
# 🏠 الواجهة الرئيسية
# ===============================
def main():
    """الدالة الرئيسية للتطبيق"""
    st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
    
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
        
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج", key="logout_btn"):
            logout_action()
    
    all_sheets = load_all_sheets()
    sheets_edit = load_sheets_for_edit()
    
    st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
    
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    user_permissions = st.session_state.get("user_permissions", ["view"])
    permissions = get_user_permissions(user_role, user_permissions)
    
    if permissions["can_manage_users"]:
        tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
        
        with tabs[0]:
            st.header("📊 فحص السيرفيس")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
                with col2:
                    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")

                if st.button("عرض حالة السيرفيس", key="show_service"):
                    st.session_state["show_service_results"] = True

                if st.session_state.get("show_service_results", False):
                    check_service_status(card_num, current_tons, all_sheets)
        
        with tabs[1]:
            st.header("📋 فحص الإيفينت والكوريكشن")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                check_events_and_corrections(all_sheets)
        
        with tabs[2]:
            st.header("🛠 تعديل وإدارة البيانات")

            token_exists = bool(st.secrets.get("github", {}).get("token", None))
            can_push = token_exists and GITHUB_AVAILABLE

            if sheets_edit is None:
                st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
            else:
                tab1, tab2, tab3 = st.tabs([
                    "عرض وتعديل شيت",
                    "➕ إضافة حدث جديد",
                    "✏ تعديل الحدث"
                ])

                with tab1:
                    sheets_edit = edit_sheet_with_save_button(sheets_edit)

                with tab2:
                    add_new_event(sheets_edit)

                with tab3:
                    edit_events_and_corrections(sheets_edit)
        
        with tabs[3]:
            manage_users()
        
        with tabs[4]:
            tech_support()
    
    elif permissions["can_edit"]:
        tabs = st.tabs([
            "📊 فحص السيرفيس", 
            "📋 فحص الإيفينت والكوريكشن", 
            "🛠 تعديل وإدارة البيانات"
        ])
        
        with tabs[0]:
            st.header("📊 فحص السيرفيس")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
                with col2:
                    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")

                if st.button("عرض حالة السيرفيس", key="show_service"):
                    st.session_state["show_service_results"] = True

                if st.session_state.get("show_service_results", False):
                    check_service_status(card_num, current_tons, all_sheets)
        
        with tabs[1]:
            st.header("📋 فحص الإيفينت والكوريكشن")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                check_events_and_corrections(all_sheets)
        
        with tabs[2]:
            st.header("🛠 تعديل وإدارة البيانات")

            if sheets_edit is None:
                st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
            else:
                tab1, tab2 = st.tabs([
                    "➕ إضافة حدث جديد",
                    "✏ تعديل الحدث"
                ])

                with tab1:
                    add_new_event(sheets_edit)

                with tab2:
                    edit_events_and_corrections(sheets_edit)
    
    else:
        tabs = st.tabs([
            "📊 فحص السيرفيس", 
            "📋 فحص الإيفينت والكوريكشن"
        ])
        
        with tabs[0]:
            st.header("📊 فحص السيرفيس")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
                with col2:
                    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")

                if st.button("عرض حالة السيرفيس", key="show_service"):
                    st.session_state["show_service_results"] = True

                if st.session_state.get("show_service_results", False):
                    check_service_status(card_num, current_tons, all_sheets)
        
        with tabs[1]:
            st.header("📋 فحص الإيفينت والكوريكشن")
            
            if all_sheets is None:
                st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
            else:
                check_events_and_corrections(all_sheets)

# تشغيل التطبيق
if __name__ == "__main__":
    main()
