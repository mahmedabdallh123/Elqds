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
    "APP_TITLE": "CMMS - Elqds",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l3.xlsx",
    "LOCAL_FILE": "l3.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON"""
    if not os.path.exists(USERS_FILE):
        # إنشاء مستخدمين افتراضيين مع الصلاحيات المطلوبة
        default_users = {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            },
            "user1": {
                "password": "user1123", 
                "role": "editor", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["view", "edit"]
            },
            "user2": {
                "password": "user2123", 
                "role": "viewer", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["view"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            # التأكد من وجود جميع الحقول المطلوبة لكل مستخدم
            for username, user_data in users.items():
                if "role" not in user_data:
                    # تحديد الدور بناءً على اسم المستخدم إذا لم يكن موجوداً
                    if username == "admin":
                        user_data["role"] = "admin"
                        user_data["permissions"] = ["all"]
                    else:
                        user_data["role"] = "viewer"
                        user_data["permissions"] = ["view"]
                
                if "permissions" not in user_data:
                    # تعيين الصلاحيات الافتراضية بناءً على الدور
                    if user_data["role"] == "admin":
                        user_data["permissions"] = ["all"]
                    elif user_data["role"] == "editor":
                        user_data["permissions"] = ["view", "edit"]
                    else:
                        user_data["permissions"] = ["view"]
                        
                if "created_at" not in user_data:
                    user_data["created_at"] = datetime.now().isoformat()
                    
            return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        # إرجاع المستخدمين الافتراضيين في حالة الخطأ
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }

def save_users(users):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
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

    # اختيار المستخدم
    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            if username_input in users and users[username_input]["password"] == password:
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
                st.session_state.user_role = users[username_input].get("role", "viewer")
                st.session_state.user_permissions = users[username_input].get("permissions", ["view"])
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
        # امسح الكاش
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
# 📂 تحميل الشيتات (مخبأ) - معدل لقراءة جميع الشيتات
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# نسخة مع dtype=object لواجهة التحرير
@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    """تحميل جميع الشيتات للتحرير"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات مع dtype=object للحفاظ على تنسيق البيانات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub + مسح الكاش + إعادة تحميل
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    """دالة محسنة للحفظ التلقائي المحلي والرفع إلى GitHub"""
    # احفظ محلياً
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

    # امسح الكاش
    try:
        st.cache_data.clear()
    except:
        pass

    # حاول الرفع عبر PyGithub token في secrets
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
            # حاول رفع كملف جديد أو إنشاء
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
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;"
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم بناءً على الدور والصلاحيات"""
    if "all" in user_permissions:
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    elif "edit" in user_permissions:
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    elif "view" in user_permissions:
        return {
            "can_view": True,
            "can_edit": False,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    else:
        # صلاحيات افتراضية للعرض فقط
        return {
            "can_view": True,
            "can_edit": False,
            "can_manage_users": False,
            "can_see_tech_support": False
        }

def get_servised_by_value(row):
    """استخراج قيمة فني الخدمة من الصف"""
    # قائمة بالأعمدة المحتملة لفني الخدمة
    servised_columns = [
        "Servised by", "SERVISED BY", "servised by", "Servised By",
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    ]
    
    # البحث في الأعمدة المعروفة
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    # البحث في جميع الأعمدة التي قد تحتوي على فني الخدمة
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    return "-"

# -------------------------------
# 🖥 دالة فحص السيرفيس فقط - من الشيتات الجديدة
# -------------------------------
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس فقط"""
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
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]

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

                # جمع بيانات السيرفيس فقط
                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                # البحث عن فني الخدمة
                servised_by_value = get_servised_by_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                # مقارنة الخدمات المنجزة مع المطلوبة
                not_done = []
                for needed_part, needed_norm_part in zip(needed_parts, needed_norm):
                    if needed_norm_part not in done_norm:
                        not_done.append(needed_part)

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

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

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

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن فقط - مبسطة
# -------------------------------
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن بطريقة مبسطة"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    st.subheader("🔍 اختر طريقة البحث")
    
    # خياران للبحث
    search_option = st.radio(
        "طريقة البحث:",
        ["🔢 البحث برقم الماكينة", "🔍 بحث عام (فني خدمة/تاريخ/نص)"],
        horizontal=True
    )
    
    if search_option == "🔢 البحث برقم الماكينة":
        card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="search_card_simple")
        
        if st.button("🔍 عرض كل بيانات الماكينة", key="show_all_machine_data"):
            st.session_state["show_simple_search"] = True
            st.session_state["search_card_num"] = card_num
            st.session_state["search_type"] = "by_card"
    
    else:  # بحث عام
        st.markdown("### 🔍 بحث عام")
        search_query = st.text_input("ابحث بأي من: (فني الخدمة / التاريخ / نص في الحدث / نص في التصحيح):", 
                                    placeholder="مثال: أحمد، 2024، صيانة، إصلاح...")
        
        if st.button("🔍 بحث شامل", key="search_general"):
            if search_query.strip():
                st.session_state["show_simple_search"] = True
                st.session_state["search_query"] = search_query.strip()
                st.session_state["search_type"] = "general"
            else:
                st.warning("⚠ الرجاء إدخال نص للبحث")
    
    # عرض النتائج
    if st.session_state.get("show_simple_search", False):
        if st.session_state["search_type"] == "by_card":
            card_num = st.session_state.get("search_card_num", 1)
            show_machine_events(card_num, all_sheets)
        else:
            search_query = st.session_state.get("search_query", "")
            show_general_search(search_query, all_sheets)

def show_machine_events(card_num, all_sheets):
    """عرض كل أحداث ماكينة محددة"""
    st.markdown(f"### 📋 جميع أحداث الماكينة رقم {card_num}")
    
    # البحث عن شيت الماكينة
    machine_data = []
    
    # 1. البحث في شيت الأحداث المخصص
    card_events_sheet_name = f"Card{card_num}_Events"
    if card_events_sheet_name in all_sheets:
        df = all_sheets[card_events_sheet_name].copy()
        machine_data.extend(extract_events_from_df(df, card_num))
    
    # 2. البحث في الشيت القديم
    card_old_sheet_name = f"Card{card_num}"
    if card_old_sheet_name in all_sheets:
        df = all_sheets[card_old_sheet_name].copy()
        # فلترة الأحداث فقط (التي ليس لها Min_Tones و Max_Tones)
        events_df = df[
            (df.get("Min_Tones", pd.NA).isna()) | 
            (df.get("Max_Tones", pd.NA).isna()) |
            ((df.get("Min_Tones", "") == "") & (df.get("Max_Tones", "") == ""))
        ].copy()
        machine_data.extend(extract_events_from_df(events_df, card_num))
    
    # 3. البحث في شيت الخدمات (إذا كان يحتوي على أحداث)
    card_services_sheet_name = f"Card{card_num}_Services"
    if card_services_sheet_name in all_sheets:
        df = all_sheets[card_services_sheet_name].copy()
        # البحث عن الصفوف التي تحتوي على Event أو Correction
        event_mask = df.astype(str).apply(
            lambda row: any("event" in col.lower() or "correction" in col.lower() 
                          for col in row.index if pd.notna(row[col]) and str(row[col]).strip() != ""), 
            axis=1
        )
        events_df = df[event_mask].copy()
        machine_data.extend(extract_events_from_df(events_df, card_num))
    
    # عرض النتائج
    if machine_data:
        result_df = pd.DataFrame(machine_data)
        
        # عرض إحصائيات
        st.markdown(f"**📊 الإحصائيات:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("عدد الأحداث", len(result_df))
        with col2:
            events_with_date = result_df[result_df["Date"] != "-"].shape[0]
            st.metric("أحداث بتاريخ", events_with_date)
        with col3:
            unique_techs = result_df["Servised by"].nunique()
            st.metric("فنيين مختلفين", unique_techs)
        with col4:
            events_with_correction = result_df[result_df["Correction"] != "-"].shape[0]
            st.metric("تحتوي على تصحيح", events_with_correction)
        
        # عرض النتائج
        st.markdown("### 📋 النتائج")
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True, height=400)
        
        # خيارات التصدير
        buffer = io.BytesIO()
        result_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Machine_{card_num}_Events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info(f"ℹ️ لا توجد أحداث مسجلة للماكينة رقم {card_num}")

def show_general_search(search_query, all_sheets):
    """بحث عام في جميع الماكينات"""
    st.markdown(f"### 🔍 نتائج البحث عن: '{search_query}'")
    
    all_results = []
    machine_count = 0
    
    # البحث في جميع شيتات الماكينات
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        df = all_sheets[sheet_name].copy()
        
        # استخراج رقم الماكينة من اسم الشيت
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        card_num = card_num_match.group(1) if card_num_match else "0"
        
        # البحث في جميع الصفوف
        for idx, row in df.iterrows():
            # تحقق مما إذا كان الصف يحتوي على نص البحث
            row_contains_query = False
            
            # تحقق في كل عمود
            for col in df.columns:
                cell_value = str(row[col]) if pd.notna(row[col]) else ""
                if search_query.lower() in cell_value.lower():
                    row_contains_query = True
                    break
            
            if row_contains_query:
                # استخراج البيانات
                card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else card_num
                date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                # البحث عن الحدث
                event_value = "-"
                for col in df.columns:
                    col_normalized = normalize_name(col)
                    if "event" in col_normalized or "الحدث" in col_normalized:
                        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                            event_value = str(row[col]).strip()
                            break
                
                # البحث عن التصحيح
                correction_value = "-"
                for col in df.columns:
                    col_normalized = normalize_name(col)
                    if "correction" in col_normalized or "تصحيح" in col_normalized:
                        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                            correction_value = str(row[col]).strip()
                            break
                
                # البحث عن فني الخدمة
                servised_by_value = get_servised_by_value(row)
                
                # إضافة النتيجة إذا كان هناك بيانات
                if (event_value != "-" or correction_value != "-" or servised_by_value != "-" or 
                    search_query.lower() in date.lower() or search_query.lower() in tones.lower()):
                    all_results.append({
                        "Card Number": card_num_value,
                        "Event": event_value,
                        "Correction": correction_value,
                        "Servised by": servised_by_value,
                        "Tones": tones,
                        "Date": date,
                        "Sheet": sheet_name
                    })
    
    if all_results:
        result_df = pd.DataFrame(all_results)
        
        # إزالة التكرارات
        result_df = result_df.drop_duplicates().reset_index(drop=True)
        
        # عرض إحصائيات
        st.markdown("### 📊 إحصائيات البحث")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("عدد النتائج", len(result_df))
        with col2:
            unique_machines = result_df["Card Number"].nunique()
            st.metric("عدد الماكينات", unique_machines)
        with col3:
            if "Servised by" in result_df.columns:
                techs_with_results = result_df[result_df["Servised by"] != "-"]["Servised by"].nunique()
                st.metric("فنيين مختلفين", techs_with_results)
        
        # توزيع النتائج حسب الماكينة
        if not result_df.empty:
            st.markdown("#### 📈 توزيع النتائج حسب الماكينة")
            machine_dist = result_df["Card Number"].value_counts().head(10)
            dist_df = pd.DataFrame({
                "رقم الماكينة": machine_dist.index,
                "عدد الأحداث": machine_dist.values
            })
            st.dataframe(dist_df, use_container_width=True)
        
        # عرض النتائج
        st.markdown("### 📋 النتائج")
        # إزالة عمود Sheet للعرض فقط
        display_df = result_df.drop(columns=['Sheet'], errors='ignore')
        st.dataframe(display_df.style.apply(style_table, axis=1), use_container_width=True, height=400)
        
        # خيارات التصدير
        buffer = io.BytesIO()
        result_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ جميع النتائج",
            data=buffer.getvalue(),
            file_name=f"General_Search_{search_query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info(f"ℹ️ لا توجد نتائج للبحث عن: '{search_query}'")

def extract_events_from_df(df, card_num):
    """استخراج الأحداث من DataFrame"""
    events_list = []
    
    for _, row in df.iterrows():
        card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
        date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
        tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
        
        # البحث عن الحدث
        event_value = "-"
        for col in df.columns:
            col_normalized = normalize_name(col)
            if "event" in col_normalized or "الحدث" in col_normalized:
                if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                    event_value = str(row[col]).strip()
                    break
        
        # البحث عن التصحيح
        correction_value = "-"
        for col in df.columns:
            col_normalized = normalize_name(col)
            if "correction" in col_normalized or "تصحيح" in col_normalized:
                if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                    correction_value = str(row[col]).strip()
                    break
        
        # البحث عن فني الخدمة
        servised_by_value = get_servised_by_value(row)
        
        # إضافة الحدث إذا كان يحتوي على بيانات
        if event_value != "-" or correction_value != "-" or servised_by_value != "-":
            events_list.append({
                "Card Number": card_num_value,
                "Event": event_value,
                "Correction": correction_value,
                "Servised by": servised_by_value,
                "Tones": tones,
                "Date": date
            })
    
    return events_list

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد - في الشيت المنفصل
# -------------------------------
def add_new_event(sheets_edit):
    """إضافة إيفينت جديد في شيت منفصل"""
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
    
    if st.button("💾 إضافة الحدث الجديد", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        
        # إنشاء صف جديد
        new_row = {}
        
        # إضافة البيانات الأساسية للأحداث
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
        # إضافة بيانات الإيفينت والكوريكشن
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
        
        # البحث عن عمود Servised by
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
        
        # إضافة الصف الجديد
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new.astype(object)
        
        # حفظ تلقائي في GitHub
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}"
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            st.rerun()

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن
# -------------------------------
def edit_events_and_corrections(sheets_edit):
    """تعديل الإيفينت والكوريكشن"""
    st.subheader("✏ تعديل الحدث والتصحيح")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    # عرض البيانات الحالية
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح)")
    
    # استخراج الأعمدة المطلوبة
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
    
    # عرض البيانات
    display_df = df[display_columns].copy()
    st.dataframe(display_df, use_container_width=True)
    
    # اختيار الصف للتعديل
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
        
        # حقول الإيفينت والكوريكشن
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
            # تحديث البيانات
            df.at[row_index, "card"] = new_card
            df.at[row_index, "Date"] = new_date
            
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            
            # البحث عن عمود Servised by
            servised_col = None
            for col in df.columns:
                if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]:
                    servised_col = col
                    break
            
            if servised_col and new_serviced_by.strip():
                df.at[row_index, servised_col] = new_serviced_by.strip()
            
            sheets_edit[sheet_name] = df.astype(object)
            
            # حفظ تلقائي في GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"تعديل حدث في {sheet_name} - الصف {row_index}"
            )
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                # مسح بيانات الجلسة
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
# إعداد الصفحة
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# شريط تسجيل الدخول / معلومات الجلسة في الشريط الجانبي
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
    
    # زر مسح الكاش
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    st.markdown("---")
    # زر لإعادة تسجيل الخروج
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

# تحميل الشيتات (عرض وتحليل)
all_sheets = load_all_sheets()

# تحميل الشيتات للتحرير (dtype=object)
sheets_edit = load_sheets_for_edit()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# التحقق من الصلاحيات - استخدم .get() لمنع الأخطاء
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# تحديد التبويبات بناءً على الصلاحيات
if permissions["can_manage_users"]:  # admin
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"])
else:  # viewer
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن"])

# -------------------------------
# Tab: فحص السيرفيس (لجميع المستخدمين)
# -------------------------------
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

# -------------------------------
# Tab: فحص الإيفينت والكوريكشن (لجميع المستخدمين)
# -------------------------------
with tabs[1]:
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        # واجهة مبسطة مع خيارين فقط
        st.info("🔍 اختر طريقة البحث المناسبة:")
        
        # استدعاء دالة البحث المبسطة
        check_events_and_corrections(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        st.header("🛠 تعديل وإدارة البيانات")

        # تحقق صلاحية الرفع
        token_exists = bool(st.secrets.get("github", {}).get("token", None))
        can_push = token_exists and GITHUB_AVAILABLE

        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "عرض وتعديل شيت",
                "إضافة صف جديد", 
                "إضافة عمود جديد",
                "➕ إضافة حدث جديد",
                "✏ تعديل الحدث"
            ])

            # -------------------------------
            # Tab 1: تعديل بيانات وعرض
            # -------------------------------
            with tab1:
                st.subheader("✏ تعديل البيانات")
                sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
                df = sheets_edit[sheet_name].astype(str)

                edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, 
                                         key=f"editor_{sheet_name}")
                
                if not edited_df.equals(df):
                    st.info("🔄 يتم حفظ التغييرات تلقائياً...")
                    sheets_edit[sheet_name] = edited_df.astype(object)
                    new_sheets = auto_save_to_github(
                        sheets_edit, 
                        f"تعديل تلقائي في شيت {sheet_name}"
                    )
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.rerun()

            # -------------------------------
            # Tab 2: إضافة صف جديد
            # -------------------------------
            with tab2:
                st.subheader("➕ إضافة صف جديد")
                sheet_name_add = st.selectbox("اختر الشيت لإضافة صف:", list(sheets_edit.keys()), key="add_sheet")
                df_add = sheets_edit[sheet_name_add].astype(str).reset_index(drop=True)
                
                st.markdown("أدخل بيانات الصف الجديد:")

                new_data = {}
                cols = st.columns(3)
                for i, col in enumerate(df_add.columns):
                    with cols[i % 3]:
                        new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")

                if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}"):
                    new_row_df = pd.DataFrame([new_data]).astype(str)
                    df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                    
                    sheets_edit[sheet_name_add] = df_new.astype(object)

                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"إضافة صف جديد في {sheet_name_add}"
                    )
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.rerun()

            # -------------------------------
            # Tab 3: إضافة عمود جديد
            # -------------------------------
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                
                new_col_name = st.text_input("اسم العمود الجديد:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "", key="default_value")

                if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}"):
                    if new_col_name:
                        df_col[new_col_name] = default_value
                        sheets_edit[sheet_name_col] = df_col.astype(object)
                        
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}"
                        )
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.rerun()
                    else:
                        st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")

            # -------------------------------
            # Tab 4: إضافة إيفينت جديد
            # -------------------------------
            with tab4:
                add_new_event(sheets_edit)

            # -------------------------------
            # Tab 5: تعديل الإيفينت والكوريكشن
            # -------------------------------
            with tab5:
                edit_events_and_corrections(sheets_edit)
