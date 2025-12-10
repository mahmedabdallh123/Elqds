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
    "APP_TITLE": "CMMS - bel",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني", "⏰ نظام التتبع"]
}

# إعدادات الصيانة الوقائية
MAINTENANCE_CONFIG = {
    "LUBRICATION_HOURS": 4320,      # ساعات التشحيم
    "FILTERS_OIL_HOURS": 13000,     # ساعات زيت الفلاتر
    "FEED_ROLL_OIL_HOURS": 40000,   # ساعات زيت الفيدرول
    "CHECK_INTERVAL_HOURS": 168     # ساعات التحقق (أسبوع)
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
MAINTENANCE_FILE = "maintenance_tracking.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON - نسخة محسنة"""
    if not os.path.exists(USERS_FILE):
        # إنشاء مستخدمين افتراضيين مع الصلاحيات المطلوبة
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
        
        # التأكد من أن الملف يحتوي على المستخدم admin الأساسي
        if "admin" not in users:
            users["admin"] = {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
            # حفظ الإضافة مباشرة
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
        
        # التأكد من وجود جميع الحقول المطلوبة لكل مستخدم
        for username, user_data in users.items():
            if "role" not in user_data:
                if username == "admin":
                    user_data["role"] = "admin"
                    user_data["permissions"] = ["all"]
                else:
                    user_data["role"] = "viewer"
                    user_data["permissions"] = ["view"]
            
            if "permissions" not in user_data:
                if user_data.get("role") == "admin":
                    user_data["permissions"] = ["all"]
                elif user_data.get("role") == "editor":
                    user_data["permissions"] = ["view", "edit"]
                else:
                    user_data["permissions"] = ["view"]
                    
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.now().isoformat()
        
        # حفظ أي تحديثات
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        
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

def load_maintenance_data():
    """تحميل بيانات تتبع الصيانة من ملف JSON"""
    if not os.path.exists(MAINTENANCE_FILE):
        default_data = {
            "machines": {},
            "maintenance_history": [],
            "settings": MAINTENANCE_CONFIG,
            "last_updated": datetime.now().isoformat()
        }
        with open(MAINTENANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4, ensure_ascii=False)
        return default_data
    
    try:
        with open(MAINTENANCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # التأكد من وجود جميع الحقول المطلوبة
        if "machines" not in data:
            data["machines"] = {}
        if "maintenance_history" not in data:
            data["maintenance_history"] = []
        if "settings" not in data:
            data["settings"] = MAINTENANCE_CONFIG
        if "last_updated" not in data:
            data["last_updated"] = datetime.now().isoformat()
        
        return data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل ملف تتبع الصيانة: {e}")
        return {
            "machines": {},
            "maintenance_history": [],
            "settings": MAINTENANCE_CONFIG,
            "last_updated": datetime.now().isoformat()
        }

def save_maintenance_data(data):
    """حفظ بيانات تتبع الصيانة إلى ملف JSON"""
    try:
        data["last_updated"] = datetime.now().isoformat()
        with open(MAINTENANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف تتبع الصيانة: {e}")
        return False

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

    # تحميل قائمة المستخدمين مباشرة من الملف
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            current_users = json.load(f)
        user_list = list(current_users.keys())
    except:
        user_list = list(users.keys())

    # اختيار المستخدم
    username_input = st.selectbox("👤 اختر المستخدم", user_list)
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            # تحميل المستخدمين من جديد للتأكد من أحدث بيانات
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
    # إذا كان الدور admin، يعطى جميع الصلاحيات
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True,
            "can_see_maintenance": True
        }
    
    # إذا كان الدور editor
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False,
            "can_see_maintenance": True
        }
    
    # إذا كان الدور viewer أو أي دور آخر
    else:
        # التحقق من الصلاحيات الفردية
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions,
            "can_see_maintenance": "maintenance" in user_permissions or "all" in user_permissions
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
# ⏰ نظام تتبع الصيانة الوقائية
# -------------------------------
def maintenance_tracking_system():
    """نظام تتبع ميعاد تغيير الزيت والتشحيم"""
    st.header("⏰ نظام تتبع الصيانة الوقائية")
    
    # تحميل بيانات الصيانة
    maintenance_data = load_maintenance_data()
    
    # تبويبات النظام
    maint_tabs = st.tabs(["📊 لوحة التحكم", "➕ تسجيل صيانة", "📋 سجل الصيانة", "⚙ الإعدادات"])
    
    with maint_tabs[0]:
        show_maintenance_dashboard(maintenance_data)
    
    with maint_tabs[1]:
        record_maintenance(maintenance_data)
    
    with maint_tabs[2]:
        show_maintenance_history(maintenance_data)
    
    with maint_tabs[3]:
        update_maintenance_settings(maintenance_data)

def show_maintenance_dashboard(maintenance_data):
    """عرض لوحة تحكم الصيانة"""
    st.subheader("📊 لوحة التحكم - حالة الماكينات")
    
    # تحميل بيانات الماكينات من ملف Excel
    all_sheets = load_all_sheets()
    if not all_sheets:
        st.warning("❗ لم يتم تحميل بيانات الماكينات.")
        return
    
    # استخراج أرقام الماكينات
    machine_numbers = []
    for sheet_name in all_sheets.keys():
        if sheet_name.startswith("Card") and not sheet_name.endswith("_Services"):
            match = re.search(r'Card(\d+)', sheet_name)
            if match:
                machine_numbers.append(int(match.group(1)))
    
    if not machine_numbers:
        st.warning("❗ لم يتم العثور على ماكينات.")
        return
    
    # فلترة حسب الحالة
    filter_option = st.selectbox(
        "🔍 فلترة حسب الحالة:",
        ["جميع الماكينات", "تتطلب صيانة", "قريباً تحتاج صيانة", "بحالة جيدة"]
    )
    
    # حساب إحصائيات
    total_machines = len(machine_numbers)
    machines_needing_maintenance = 0
    machines_warning = 0
    machines_good = 0
    
    # عرض حالة كل ماكينة
    st.markdown("### 🔧 حالة الماكينات")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, machine_num in enumerate(sorted(machine_numbers)):
        progress_bar.progress((idx + 1) / total_machines)
        status_text.text(f"🔍 جاري تحليل الماكينة {machine_num}...")
        
        # الحصول على حالة الصيانة
        machine_status = get_machine_maintenance_status(machine_num, maintenance_data, all_sheets)
        
        # تحديث الإحصائيات
        if machine_status["status"] == "danger":
            machines_needing_maintenance += 1
        elif machine_status["status"] == "warning":
            machines_warning += 1
        else:
            machines_good += 1
        
        # تطبيق الفلتر
        if filter_option == "جميع الماكينات" or \
           (filter_option == "تتطلب صيانة" and machine_status["status"] == "danger") or \
           (filter_option == "قريباً تحتاج صيانة" and machine_status["status"] == "warning") or \
           (filter_option == "بحالة جيدة" and machine_status["status"] == "good"):
            
            with st.expander(f"🔧 الماكينة {machine_num} - {machine_status['overall_status']}", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # عرض تفاصيل الحالة
                    for maint_type, details in machine_status["details"].items():
                        if maint_type == "lubrication":
                            label = "التشحيم"
                        elif maint_type == "filters_oil":
                            label = "زيت الفلاتر"
                        elif maint_type == "feed_roll_oil":
                            label = "زيت الفيدرول"
                        else:
                            continue
                        
                        # تحديد اللون حسب الحالة
                        if details["status"] == "danger":
                            color = "🔴"
                        elif details["status"] == "warning":
                            color = "🟡"
                        else:
                            color = "🟢"
                        
                        st.write(f"{color} **{label}:**")
                        st.write(f"   - الساعات المنقضية: {details['hours_elapsed']} ساعة")
                        st.write(f"   - الساعات المتبقية: {details['hours_remaining']} ساعة")
                        st.write(f"   - آخر تغيير: {details['last_change']}")
                
                with col2:
                    # عرض إجراءات سريعة
                    st.write("**🛠 إجراءات سريعة:**")
                    
                    if machine_status["status"] == "danger":
                        st.error("تتطلب صيانة عاجلة!")
                        if st.button(f"📝 تسجيل صيانة", key=f"quick_record_{machine_num}"):
                            st.session_state["quick_record_machine"] = machine_num
                            st.rerun()
                    
                    # زر عرض السجل
                    if st.button(f"📋 عرض السجل", key=f"view_history_{machine_num}"):
                        show_machine_history(machine_num, maintenance_data)
    
    # إخفاء شريط التقدم
    progress_bar.empty()
    status_text.empty()
    
    # عرض الإحصائيات
    st.markdown("---")
    st.subheader("📈 إحصائيات الصيانة")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔢 عدد الماكينات", total_machines)
    
    with col2:
        st.metric("🔴 تتطلب صيانة", machines_needing_maintenance, 
                 delta=f"{(machines_needing_maintenance/total_machines*100):.1f}%" if total_machines > 0 else "0%")
    
    with col3:
        st.metric("🟡 قريباً تحتاج", machines_warning,
                 delta=f"{(machines_warning/total_machines*100):.1f}%" if total_machines > 0 else "0%")
    
    with col4:
        st.metric("🟢 بحالة جيدة", machines_good,
                 delta=f"{(machines_good/total_machines*100):.1f}%" if total_machines > 0 else "0%")
    
    # عرض الرسم البياني
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure(data=[
            go.Pie(
                labels=['تتطلب صيانة', 'قريباً تحتاج', 'بحالة جيدة'],
                values=[machines_needing_maintenance, machines_warning, machines_good],
                hole=.3,
                marker_colors=['#FF6B6B', '#FFD166', '#06D6A0']
            )
        ])
        
        fig.update_layout(
            title="توزيع حالة الماكينات",
            showlegend=True,
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    except:
        pass

def get_machine_maintenance_status(machine_num, maintenance_data, all_sheets):
    """الحصول على حالة الصيانة لماكينة معينة"""
    machine_id = str(machine_num)
    current_time = datetime.now()
    
    # البيانات الافتراضية
    default_status = {
        "machine_number": machine_num,
        "overall_status": "غير معروفة",
        "status": "unknown",  # good, warning, danger
        "details": {}
    }
    
    # البحث في بيانات الماكينة
    machine_info = maintenance_data["machines"].get(machine_id, {})
    
    # الحصول على ساعات التشغيل الحالية
    current_hours = get_machine_current_hours(machine_num, all_sheets)
    
    if current_hours is None:
        default_status["overall_status"] = "لا توجد بيانات تشغيل"
        return default_status
    
    # التحقق من كل نوع صيانة
    statuses = []
    
    for maint_type in ["lubrication", "filters_oil", "feed_roll_oil"]:
        maint_info = machine_info.get(maint_type, {})
        last_change_hours = maint_info.get("last_change_hours", 0)
        last_change_date = maint_info.get("last_change_date", "")
        
        # حساب الساعات المنقضية
        if last_change_hours > 0:
            hours_elapsed = current_hours - last_change_hours
        else:
            hours_elapsed = current_hours
        
        # الحصول على الحد الأقصى للساعات
        max_hours = MAINTENANCE_CONFIG.get(
            f"{maint_type.upper()}_HOURS" if maint_type != "lubrication" else "LUBRICATION_HOURS",
            MAINTENANCE_CONFIG["LUBRICATION_HOURS"]
        )
        
        # حساب النسبة المئوية
        percentage = (hours_elapsed / max_hours) * 100 if max_hours > 0 else 0
        
        # تحديد الحالة
        if percentage >= 100:
            status = "danger"
            status_text = "تتطلب صيانة"
        elif percentage >= 80:
            status = "warning"
            status_text = "قريباً تحتاج"
        else:
            status = "good"
            status_text = "بحالة جيدة"
        
        statuses.append(status)
        
        # تخزين التفاصيل
        if maint_type == "lubrication":
            label = "التشحيم"
        elif maint_type == "filters_oil":
            label = "زيت الفلاتر"
        else:
            label = "زيت الفيدرول"
        
        default_status["details"][maint_type] = {
            "label": label,
            "status": status,
            "status_text": status_text,
            "hours_elapsed": int(hours_elapsed),
            "hours_remaining": int(max(0, max_hours - hours_elapsed)),
            "percentage": round(percentage, 1),
            "last_change": last_change_date if last_change_date else "لم يتم التسجيل",
            "last_change_hours": last_change_hours
        }
    
    # تحديد الحالة العامة
    if "danger" in statuses:
        default_status["overall_status"] = "تتطلب صيانة عاجلة"
        default_status["status"] = "danger"
    elif "warning" in statuses:
        default_status["overall_status"] = "قريباً تحتاج صيانة"
        default_status["status"] = "warning"
    else:
        default_status["overall_status"] = "بحالة جيدة"
        default_status["status"] = "good"
    
    return default_status

def get_machine_current_hours(machine_num, all_sheets):
    """الحصول على ساعات التشغيل الحالية للماكينة"""
    sheet_name = f"Card{machine_num}"
    if sheet_name not in all_sheets:
        return None
    
    df = all_sheets[sheet_name]
    
    # البحث عن عمود الساعات
    hours_columns = [col for col in df.columns if normalize_name(col) in ["hours", "ساعات", "runninghours", "تشغيل"]]
    
    if hours_columns:
        # أخذ آخر قيمة
        last_row = df.iloc[-1] if len(df) > 0 else pd.Series()
        for col in hours_columns:
            if col in last_row and pd.notna(last_row[col]):
                try:
                    return float(last_row[col])
                except:
                    continue
    
    # محاولة الحصول من Tones إذا كانت تعني ساعات
    if "Tones" in df.columns:
        last_tones = df["Tones"].iloc[-1] if len(df) > 0 else None
        if pd.notna(last_tones):
            try:
                return float(last_tones)
            except:
                pass
    
    return 0

def record_maintenance(maintenance_data):
    """تسجيل صيانة جديدة"""
    st.subheader("➕ تسجيل صيانة جديدة")
    
    # تحميل بيانات الماكينات
    all_sheets = load_all_sheets()
    if not all_sheets:
        st.warning("❗ لم يتم تحميل بيانات الماكينات.")
        return
    
    # استخراج أرقام الماكينات
    machine_numbers = []
    for sheet_name in all_sheets.keys():
        if sheet_name.startswith("Card") and not sheet_name.endswith("_Services"):
            match = re.search(r'Card(\d+)', sheet_name)
            if match:
                machine_numbers.append(int(match.group(1)))
    
    if not machine_numbers:
        st.warning("❗ لم يتم العثور على ماكينات.")
        return
    
    # اختيار الماكينة
    if "quick_record_machine" in st.session_state:
        default_machine = st.session_state["quick_record_machine"]
        del st.session_state["quick_record_machine"]
    else:
        default_machine = sorted(machine_numbers)[0] if machine_numbers else None
    
    machine_num = st.selectbox(
        "اختر رقم الماكينة:",
        sorted(machine_numbers),
        index=sorted(machine_numbers).index(default_machine) if default_machine in machine_numbers else 0,
        key="record_maintenance_machine"
    )
    
    # الحصول على ساعات التشغيل الحالية
    current_hours = get_machine_current_hours(machine_num, all_sheets)
    
    if current_hours is not None:
        st.info(f"⏱️ ساعات التشغيل الحالية للماكينة {machine_num}: **{current_hours:.0f}** ساعة")
    else:
        st.warning("⚠ لم يتم العثور على بيانات ساعات التشغيل لهذه الماكينة.")
        current_hours = 0
    
    # اختيار نوع الصيانة
    maintenance_type = st.radio(
        "اختر نوع الصيانة:",
        ["التشحيم", "زيت الفلاتر", "زيت الفيدرول"],
        key="record_maintenance_type"
    )
    
    # تحويل النوع
    if maintenance_type == "التشحيم":
        maint_key = "lubrication"
        max_hours = MAINTENANCE_CONFIG["LUBRICATION_HOURS"]
    elif maintenance_type == "زيت الفلاتر":
        maint_key = "filters_oil"
        max_hours = MAINTENANCE_CONFIG["FILTERS_OIL_HOURS"]
    else:
        maint_key = "feed_roll_oil"
        max_hours = MAINTENANCE_CONFIG["FEED_ROLL_OIL_HOURS"]
    
    # عرض معلومات التتبع
    machine_id = str(machine_num)
    machine_info = maintenance_data["machines"].get(machine_id, {})
    maint_info = machine_info.get(maint_key, {})
    
    last_change_hours = maint_info.get("last_change_hours", 0)
    last_change_date = maint_info.get("last_change_date", "")
    
    if last_change_hours > 0:
        hours_since_last = current_hours - last_change_hours
        st.write(f"**🕐 آخر {maintenance_type}:** {last_change_date}")
        st.write(f"**⏳ الساعات منذ آخر تغيير:** {hours_since_last:.0f} ساعة")
        st.write(f"**🎯 الحد الأقصى:** {max_hours} ساعة")
        
        # حساب النسبة
        percentage = (hours_since_last / max_hours) * 100
        st.progress(min(percentage / 100, 1))
        st.write(f"**📊 نسبة الاستهلاك:** {percentage:.1f}%")
    
    # تفاصيل التسجيل
    st.markdown("### 📝 تفاصيل التسجيل")
    
    col1, col2 = st.columns(2)
    with col1:
        maintenance_date = st.date_input("تاريخ الصيانة:", value=datetime.now())
        technician = st.text_input("اسم الفني:", placeholder="أدخل اسم الفني")
    
    with col2:
        notes = st.text_area("ملاحظات إضافية:", placeholder="أي ملاحظات حول الصيانة...")
    
    # زر التسجيل
    if st.button("💾 تسجيل الصيانة", type="primary", key="save_maintenance_record"):
        if not technician.strip():
            st.warning("⚠ الرجاء إدخال اسم الفني.")
            return
        
        # تحديث بيانات الماكينة
        machine_id = str(machine_num)
        if machine_id not in maintenance_data["machines"]:
            maintenance_data["machines"][machine_id] = {}
        
        maintenance_data["machines"][machine_id][maint_key] = {
            "last_change_hours": current_hours,
            "last_change_date": maintenance_date.strftime("%Y-%m-%d"),
            "technician": technician,
            "notes": notes
        }
        
        # إضافة إلى سجل التاريخ
        maintenance_data["maintenance_history"].append({
            "machine_number": machine_num,
            "maintenance_type": maintenance_type,
            "maintenance_key": maint_key,
            "hours": current_hours,
            "date": maintenance_date.strftime("%Y-%m-%d"),
            "technician": technician,
            "notes": notes,
            "recorded_by": st.session_state.get("username", "unknown"),
            "recorded_at": datetime.now().isoformat()
        })
        
        # حفظ البيانات
        if save_maintenance_data(maintenance_data):
            st.success(f"✅ تم تسجيل {maintenance_type} للماكينة {machine_num} بنجاح!")
            
            # إضافة إلى ملف Excel
            add_maintenance_to_excel(machine_num, maintenance_type, maintenance_date, technician, current_hours, notes)
            
            st.rerun()
        else:
            st.error("❌ حدث خطأ أثناء حفظ البيانات.")

def add_maintenance_to_excel(machine_num, maintenance_type, date, technician, hours, notes):
    """إضافة سجل الصيانة إلى ملف Excel"""
    try:
        # تحميل الشيتات للتحرير
        sheets_edit = load_sheets_for_edit()
        if not sheets_edit:
            return
        
        sheet_name = f"Card{machine_num}"
        if sheet_name not in sheets_edit:
            return
        
        df = sheets_edit[sheet_name].astype(str)
        
        # إنشاء سجل جديد
        new_record = {
            "Date": date.strftime("%Y-%m-%d"),
            "Event": f"{maintenance_type} - {technician}",
            "Correction": notes if notes else f"تم {maintenance_type} عند {hours:.0f} ساعة",
            "Servised by": technician,
            "Tones": str(hours),
            "card": str(machine_num)
        }
        
        # إضافة السجل الجديد
        new_row_df = pd.DataFrame([new_record])
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        sheets_edit[sheet_name] = df_new.astype(object)
        
        # حفظ في GitHub
        auto_save_to_github(
            sheets_edit,
            f"إضافة سجل {maintenance_type} للماكينة {machine_num}"
        )
        
    except Exception as e:
        st.error(f"⚠ خطأ في إضافة السجل إلى Excel: {e}")

def show_maintenance_history(maintenance_data):
    """عرض سجل الصيانة"""
    st.subheader("📋 سجل الصيانة")
    
    history = maintenance_data.get("maintenance_history", [])
    
    if not history:
        st.info("ℹ️ لا توجد سجلات صيانة مسجلة بعد.")
        return
    
    # تحويل إلى DataFrame
    history_df = pd.DataFrame(history)
    
    # فلترة البيانات
    st.markdown("#### 🔍 فلترة السجلات")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        machine_filter = st.multiselect(
            "🔢 أرقام الماكينات:",
            options=sorted(history_df["machine_number"].unique()),
            default=[]
        )
    
    with col2:
        type_filter = st.multiselect(
            "🛠 نوع الصيانة:",
            options=sorted(history_df["maintenance_type"].unique()),
            default=[]
        )
    
    with col3:
        # فلترة حسب التاريخ
        date_range = st.date_input(
            "📅 نطاق التاريخ:",
            value=[datetime.now() - timedelta(days=30), datetime.now()],
            max_value=datetime.now()
        )
    
    # تطبيق الفلاتر
    filtered_df = history_df.copy()
    
    if machine_filter:
        filtered_df = filtered_df[filtered_df["machine_number"].isin(machine_filter)]
    
    if type_filter:
        filtered_df = filtered_df[filtered_df["maintenance_type"].isin(type_filter)]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df["date"] = pd.to_datetime(filtered_df["date"])
        filtered_df = filtered_df[(filtered_df["date"] >= pd.Timestamp(start_date)) & 
                                 (filtered_df["date"] <= pd.Timestamp(end_date))]
    
    # عرض البيانات
    if not filtered_df.empty:
        # إعادة ترتيب الأعمدة
        display_columns = ["machine_number", "maintenance_type", "date", "technician", "hours", "notes", "recorded_by", "recorded_at"]
        display_columns = [col for col in display_columns if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[display_columns].sort_values("date", ascending=False),
            use_container_width=True,
            height=400
        )
        
        # خيارات التصدير
        st.markdown("---")
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            # تصدير Excel
            buffer_excel = io.BytesIO()
            filtered_df.to_excel(buffer_excel, index=False, engine="openpyxl")
            st.download_button(
                label="📊 تصدير إلى Excel",
                data=buffer_excel.getvalue(),
                file_name=f"سجل_الصيانة_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col_exp2:
            # تصدير CSV
            buffer_csv = io.BytesIO()
            filtered_df.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
            st.download_button(
                label="📄 تصدير إلى CSV",
                data=buffer_csv.getvalue(),
                file_name=f"سجل_الصيانة_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.warning("⚠ لا توجد سجلات تطابق معايير الفلترة.")

def show_machine_history(machine_num, maintenance_data):
    """عرض سجل صيانة ماكينة معينة"""
    st.subheader(f"📋 سجل صيانة الماكينة {machine_num}")
    
    history = maintenance_data.get("maintenance_history", [])
    machine_history = [record for record in history if record["machine_number"] == machine_num]
    
    if not machine_history:
        st.info(f"ℹ️ لا توجد سجلات صيانة للماكينة {machine_num}.")
        return
    
    # تحويل إلى DataFrame
    history_df = pd.DataFrame(machine_history)
    
    # عرض حسب نوع الصيانة
    maintenance_types = history_df["maintenance_type"].unique()
    
    for maint_type in maintenance_types:
        with st.expander(f"{maint_type}", expanded=True):
            type_df = history_df[history_df["maintenance_type"] == maint_type].sort_values("date", ascending=False)
            
            for _, record in type_df.iterrows():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**📅 التاريخ:** {record['date']}")
                    st.write(f"**👨‍🔧 الفني:** {record.get('technician', 'غير معروف')}")
                    st.write(f"**⏱️ الساعات:** {record.get('hours', 'غير معروف')}")
                    
                    if record.get('notes'):
                        st.write(f"**📝 الملاحظات:** {record['notes']}")
                
                with col2:
                    st.write(f"**📊 المسجل:** {record.get('recorded_by', 'غير معروف')}")
                    if record.get('recorded_at'):
                        try:
                            recorded_time = datetime.fromisoformat(record['recorded_at']).strftime("%Y-%m-%d %H:%M")
                            st.write(f"**🕐 وقت التسجيل:** {recorded_time}")
                        except:
                            pass

def update_maintenance_settings(maintenance_data):
    """تحديث إعدادات الصيانة"""
    st.subheader("⚙ إعدادات نظام التتبع")
    
    st.info("**⚙ الإعدادات الحالية:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        current_lube = st.number_input(
            "ساعات التشحيم:",
            min_value=100,
            max_value=10000,
            value=maintenance_data["settings"].get("LUBRICATION_HOURS", MAINTENANCE_CONFIG["LUBRICATION_HOURS"]),
            step=100,
            key="set_lube_hours"
        )
    
    with col2:
        current_filters = st.number_input(
            "ساعات زيت الفلاتر:",
            min_value=1000,
            max_value=50000,
            value=maintenance_data["settings"].get("FILTERS_OIL_HOURS", MAINTENANCE_CONFIG["FILTERS_OIL_HOURS"]),
            step=500,
            key="set_filters_hours"
        )
    
    with col3:
        current_feedroll = st.number_input(
            "ساعات زيت الفيدرول:",
            min_value=5000,
            max_value=100000,
            value=maintenance_data["settings"].get("FEED_ROLL_OIL_HOURS", MAINTENANCE_CONFIG["FEED_ROLL_OIL_HOURS"]),
            step=1000,
            key="set_feedroll_hours"
        )
    
    # التحقق من الصلاحيات
    current_user = st.session_state.get("username")
    if current_user != "admin":
        st.warning("⚠ فقط المسؤول (admin) يمكنه تعديل الإعدادات.")
        return
    
    if st.button("💾 حفظ الإعدادات", type="primary", key="save_maintenance_settings"):
        maintenance_data["settings"] = {
            "LUBRICATION_HOURS": current_lube,
            "FILTERS_OIL_HOURS": current_filters,
            "FEED_ROLL_OIL_HOURS": current_feedroll,
            "CHECK_INTERVAL_HOURS": maintenance_data["settings"].get("CHECK_INTERVAL_HOURS", MAINTENANCE_CONFIG["CHECK_INTERVAL_HOURS"])
        }
        
        # تحديث الإعدادات العالمية
        global MAINTENANCE_CONFIG
        MAINTENANCE_CONFIG.update(maintenance_data["settings"])
        
        if save_maintenance_data(maintenance_data):
            st.success("✅ تم حفظ الإعدادات بنجاح!")
            st.rerun()
        else:
            st.error("❌ حدث خطأ أثناء حفظ الإعدادات.")

# ... (استمرار باقي الكود كما هو مع إضافة تبويب الصيانة في الواجهة الرئيسية) ...

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
    
    # زر تحديث الجلسة
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        # تحميل أحدث بيانات المستخدم
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    
    # زر لحفظ جميع التغييرات غير المحفوظة
    if st.session_state.get("unsaved_changes", {}):
        unsaved_count = sum(1 for v in st.session_state.unsaved_changes.values() if v)
        if unsaved_count > 0:
            st.markdown("---")
            st.warning(f"⚠ لديك {unsaved_count} شيت به تغييرات غير محفوظة")
            if st.button("💾 حفظ جميع التغييرات", key="save_all_changes", type="primary"):
                # سيتم التعامل مع هذا في الواجهة الرئيسية
                st.session_state["save_all_requested"] = True
                st.rerun()
    
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
    
    # Tab: إدارة المستخدمين (للمسؤولين فقط)
    with tabs[3]:
        manage_users()
    
    # Tab: الدعم الفني (للمسؤولين فقط أو إذا كان الإعداد يسمح للجميع)
    if APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"] or permissions["can_manage_users"]:
        with tabs[4]:
            tech_support()
    
    # Tab: نظام التتبع
    with tabs[5]:
        maintenance_tracking_system()
    
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "⏰ نظام التتبع"])
    with tabs[3]:
        maintenance_tracking_system()
else:  # viewer
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "⏰ نظام التتبع"])
    with tabs[2]:
        maintenance_tracking_system()

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
        # واجهة بحث متعدد المعايير
        check_events_and_corrections(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 3:
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

            # Tab 1: تعديل بيانات وعرض
            with tab1:
                # التحقق من طلب حفظ جميع التغييرات
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    # هنا يمكنك إضافة منطق لحفظ جميع التغييرات
                    st.session_state["save_all_requested"] = False
                
                # استخدام دالة التعديل مع زر الحفظ
                sheets_edit = edit_sheet_with_save_button(sheets_edit)

            # Tab 2: إضافة صف جديد
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

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}", type="primary"):
                        new_row_df = pd.DataFrame([new_data]).astype(str)
                        df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                        
                        sheets_edit[sheet_name_add] = df_new.astype(object)

                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إضافة صف جديد في {sheet_name_add}"
                        )
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success("✅ تم إضافة الصف الجديد بنجاح!")
                            st.rerun()
                
                with col_btn2:
                    if st.button("🗑 مسح الحقول", key=f"clear_{sheet_name_add}"):
                        st.rerun()

            # Tab 3: إضافة عمود جديد
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                
                new_col_name = st.text_input("اسم العمود الجديد:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "", key="default_value")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}", type="primary"):
                        if new_col_name:
                            df_col[new_col_name] = default_value
                            sheets_edit[sheet_name_col] = df_col.astype(object)
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}"
                            )
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success("✅ تم إضافة العمود الجديد بنجاح!")
                                st.rerun()
                        else:
                            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
                
                with col_btn2:
                    if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
                        st.rerun()

            # Tab 4: إضافة إيفينت جديد
            with tab4:
                add_new_event(sheets_edit)

            # Tab 5: تعديل الإيفينت والكوريكشن
            with tab5:
                edit_events_and_corrections(sheets_edit)
