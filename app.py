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
            "can_see_tech_support": True
        }
    
    # إذا كان الدور editor
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    
    # إذا كان الدور viewer أو أي دور آخر
    else:
        # التحقق من الصلاحيات الفردية
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions
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
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

        # عرض الإحصائيات والنسب
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
    """عرض الإحصائيات والنسب المئوية لفحص السيرفيس"""
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
            
            # محاولة استخدام plotly للمخططات التفاعلية
            try:
                import plotly.graph_objects as go
                
                # تحليل نطاقات الشرائح
                slice_ranges = []
                completion_rates = []
                
                for slice_item in slice_stats_data:
                    slice_key = slice_item["الشريحة"]
                    slice_range = slice_key.split("-")
                    if len(slice_range) == 2:
                        try:
                            mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                            slice_ranges.append(mid_point)
                            
                            # استخراج النسبة من النص
                            rate_text = slice_item["نسبة الإنجاز"]
                            rate_value = float(rate_text.replace("%", "").strip())
                            completion_rates.append(rate_value)
                        except:
                            continue
                
                if slice_ranges and completion_rates:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(
                        x=slice_ranges,
                        y=completion_rates,
                        mode='lines+markers',
                        name='نسبة الإنجاز',
                        line=dict(color='#4ECDC4', width=3),
                        marker=dict(size=10, color='#FF6B6B')
                    ))
                    
                    fig3.update_layout(
                        title="نسبة الإنجاز حسب نطاق الأطنان",
                        xaxis_title="نطاق الأطنان (منتصف الشريحة)",
                        yaxis_title="نسبة الإنجاز (%)",
                        height=400,
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
                    
            except ImportError:
                # استخدام streamlit line chart بديل
                if slice_stats_data:
                    # تحضير البيانات للرسم البياني
                    chart_data = []
                    for slice_item in slice_stats_data:
                        slice_key = slice_item["الشريحة"]
                        slice_range = slice_key.split("-")
                        if len(slice_range) == 2:
                            try:
                                mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                                rate_text = slice_item["نسبة الإنجاز"]
                                rate_value = float(rate_text.replace("%", "").strip())
                                
                                chart_data.append({
                                    "نطاق الأطنان": mid_point,
                                    "نسبة الإنجاز": rate_value
                                })
                            except:
                                continue
                    
                    if chart_data:
                        chart_df = pd.DataFrame(chart_data).sort_values("نطاق الأطنان")
                        st.line_chart(chart_df.set_index("نطاق الأطنان"), height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للشرائح.")

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن - واجهة مبسطة واحترافية
# -------------------------------
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن بواجهة مبسطة واحترافية"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تهيئة session state إذا لزم الأمر
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
    
    # قسم البحث - واجهة احترافية
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك ملء واحد أو أكثر من الحقول.")
        
        # تقسيم الشاشة إلى أعمدة
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # قسم أرقام الماكينات
            with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                st.caption("أدخل أرقام الماكينات (مفصولة بفواصل أو نطاقات)")
                card_numbers = st.text_input(
                    "مثال: 1,3,5 أو 1-5 أو 2,4,7-10",
                    value=st.session_state.search_params.get("card_numbers", ""),
                    key="input_cards",
                    placeholder="اتركه فارغاً للبحث في كل الماكينات"
                )
                
                # أزرار سريعة لأرقام الماكينات
                st.caption("أو اختر من:")
                quick_cards_col1, quick_cards_col2, quick_cards_col3 = st.columns(3)
                with quick_cards_col1:
                    if st.button("🔟 أول 10 ماكينات", key="quick_10"):
                        st.session_state.search_params["card_numbers"] = "1-10"
                        st.session_state.search_triggered = True
                        st.rerun()
                with quick_cards_col2:
                    if st.button("🔟 ماكينات 11-20", key="quick_20"):
                        st.session_state.search_params["card_numbers"] = "11-20"
                        st.session_state.search_triggered = True
                        st.rerun()
                with quick_cards_col3:
                    if st.button("🗑 مسح", key="clear_cards"):
                        st.session_state.search_params["card_numbers"] = ""
                        st.rerun()
            
            # قسم التواريخ
            with st.expander("📅 **التواريخ**", expanded=True):
                st.caption("ابحث بالتاريخ (سنة، شهر/سنة)")
                date_input = st.text_input(
                    "مثال: 2024 أو 1/2024 أو 2024,2025",
                    value=st.session_state.search_params.get("date_range", ""),
                    key="input_date",
                    placeholder="اتركه فارغاً للبحث في كل التواريخ"
                )
        
        with col2:
            # قسم فنيي الخدمة
            with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                st.caption("ابحث بأسماء فنيي الخدمة")
                tech_names = st.text_input(
                    "مثال: أحمد, محمد, علي",
                    value=st.session_state.search_params.get("tech_names", ""),
                    key="input_techs",
                    placeholder="اتركه فارغاً للبحث في كل الفنيين"
                )
            
            # قسم نص البحث
            with st.expander("📝 **نص البحث**", expanded=True):
                st.caption("ابحث في وصف الحدث أو التصحيح")
                search_text = st.text_input(
                    "مثال: صيانة, إصلاح, تغيير",
                    value=st.session_state.search_params.get("search_text", ""),
                    key="input_text",
                    placeholder="اتركه فارغاً للبحث في كل النصوص"
                )
        
        # قسم خيارات البحث المتقدمة
        with st.expander("⚙ **خيارات متقدمة**", expanded=False):
            col_adv1, col_adv2, col_adv3 = st.columns(3)
            with col_adv1:
                search_mode = st.radio(
                    "🔍 طريقة البحث:",
                    ["بحث جزئي", "مطابقة كاملة"],
                    index=0 if not st.session_state.search_params.get("exact_match") else 1,
                    key="radio_search_mode",
                    help="بحث جزئي: يبحث عن النص في أي مكان. مطابقة كاملة: يبحث عن النص مطابق تماماً"
                )
            with col_adv2:
                include_empty = st.checkbox(
                    "🔍 تضمين الحقول الفارغة",
                    value=st.session_state.search_params.get("include_empty", True),
                    key="checkbox_include_empty",
                    help="تضمين النتائج التي تحتوي على حقول فارغة"
                )
            with col_adv3:
                sort_by = st.selectbox(
                    "📊 ترتيب النتائج:",
                    ["رقم الماكينة", "التاريخ", "فني الخدمة"],
                    index=["رقم الماكينة", "التاريخ", "فني الخدمة"].index(
                        st.session_state.search_params.get("sort_by", "رقم الماكينة")
                    ),
                    key="select_sort_by"
                )
        
        # زر البحث الرئيسي
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
    
    # تحديث معايير البحث عند تغيير الحقول
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
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        # جمع معايير البحث
        search_params = st.session_state.search_params.copy()
        
        # عرض معايير البحث
        show_search_params(search_params)
        
        # تنفيذ البحث
        show_advanced_search_results(search_params, all_sheets)

def extract_available_techs(all_sheets):
    """استخراج أسماء فنيي الخدمة المتاحة في البيانات"""
    techs_set = set()
    
    for sheet_name, df in all_sheets.items():
        if sheet_name == "ServicePlan":
            continue
            
        for _, row in df.iterrows():
            tech = get_servised_by_value(row)
            if tech != "-":
                techs_set.add(tech)
    
    return sorted(list(techs_set))

def show_search_params(search_params):
    """عرض معايير البحث المستخدمة"""
    with st.container():
        st.markdown("### ⚙ معايير البحث المستخدمة")
        
        params_display = []
        if search_params["card_numbers"]:
            params_display.append(f"**🔢 أرقام الماكينات:** {search_params['card_numbers']}")
        if search_params["date_range"]:
            params_display.append(f"**📅 التواريخ:** {search_params['date_range']}")
        if search_params["tech_names"]:
            params_display.append(f"**👨‍🔧 فنيو الخدمة:** {search_params['tech_names']}")
        if search_params["search_text"]:
            params_display.append(f"**📝 نص البحث:** {search_params['search_text']}")
        
        if params_display:
            st.info(" | ".join(params_display))
        else:
            st.info("🔍 **بحث في كل البيانات**")

def parse_card_numbers(card_numbers_str):
    """تحليل سلسلة أرقام الماكينات إلى قائمة أرقام"""
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

def extract_event_correction(row, df):
    """استخراج الحدث والتصحيح من الصف"""
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
    
    return event_value, correction_value

def extract_row_data(row, df, card_num):
    """استخراج بيانات الصف مع تحليل التاريخ"""
    card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
    date_str = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    
    event_value, correction_value = extract_event_correction(row, df)
    
    # إذا كانت كل الحقول فارغة، نتجاهل الصف
    if (event_value == "-" and correction_value == "-" and 
        date_str == "-" and tones == "-"):
        return None
    
    servised_by_value = get_servised_by_value(row)
    
    # تحليل التاريخ إلى كائن datetime (بشكل آمن)
    date_parsed = None
    if date_str != "-":
        # محاولة تحليل التاريخ بأشكال مختلفة
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
            '%m/%d/%Y', '%m-%d-%Y', '%m.%d.%Y',
            '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d'
        ]
        
        for fmt in date_formats:
            try:
                date_parsed = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        
        # إذا فشلت جميع المحاولات، تحاول pandas
        if date_parsed is None:
            try:
                date_parsed = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                if pd.isna(date_parsed):
                    date_parsed = None
            except:
                date_parsed = None
    
    return {
        "Card Number": card_num_value,
        "Event": event_value,
        "Correction": correction_value,
        "Servised by": servised_by_value,
        "Tones": tones,
        "Date": date_str,
        "Date_parsed": date_parsed
    }

def format_time_interval(days):
    """تنسيق الفترة الزمنية بشكل مقروء"""
    if days < 1:
        return "أقل من يوم"
    elif days < 7:
        return f"{days} يوم"
    elif days < 30:
        weeks = days // 7
        remaining_days = days % 7
        if remaining_days > 0:
            return f"{weeks} أسبوع و {remaining_days} يوم"
        return f"{weeks} أسبوع"
    elif days < 365:
        months = days // 30
        remaining_days = days % 30
        if remaining_days > 0:
            return f"{months} شهر و {remaining_days} يوم"
        return f"{months} شهر"
    else:
        years = days // 365
        remaining_days = days % 365
        if remaining_days > 0:
            months = remaining_days // 30
            return f"{years} سنة و {months} شهر"
        return f"{years} سنة"

def analyze_time_intervals(events_data):
    """تحليل الفترات الزمنية بين الأحداث"""
    analysis = {
        "time_intervals": [],
        "stats": {
            "avg_interval_days": None,
            "min_interval_days": None,
            "max_interval_days": None,
            "total_events": 0,
            "covered_period_days": None
        },
        "by_technician": {},
        "recent_activity": []
    }
    
    if not events_data:
        return analysis
    
    # ترتيب الأحداث حسب التاريخ
    events_sorted = sorted(
        [e for e in events_data if e.get("Date_parsed")], 
        key=lambda x: x["Date_parsed"]
    )
    
    analysis["stats"]["total_events"] = len(events_sorted)
    
    if len(events_sorted) < 2:
        return analysis
    
    # حساب الفترات الزمنية
    intervals = []
    for i in range(1, len(events_sorted)):
        prev_date = events_sorted[i-1]["Date_parsed"]
        curr_date = events_sorted[i]["Date_parsed"]
        
        if prev_date and curr_date:
            delta = curr_date - prev_date
            days = delta.days
            
            intervals.append({
                "from_event": events_sorted[i-1].get("Event", "غير معروف"),
                "to_event": events_sorted[i].get("Event", "غير معروف"),
                "from_date": prev_date,
                "to_date": curr_date,
                "days": days,
                "formatted": format_time_interval(days)
            })
    
    analysis["time_intervals"] = intervals
    
    # حساب الإحصائيات
    if intervals:
        days_list = [interval["days"] for interval in intervals]
        analysis["stats"]["avg_interval_days"] = sum(days_list) / len(days_list)
        analysis["stats"]["min_interval_days"] = min(days_list)
        analysis["stats"]["max_interval_days"] = max(days_list)
        
        # الفترة الزمنية الكلية
        first_date = events_sorted[0]["Date_parsed"]
        last_date = events_sorted[-1]["Date_parsed"]
        total_days = (last_date - first_date).days
        analysis["stats"]["covered_period_days"] = total_days
    
    # تحليل حسب فني الخدمة
    technician_events = {}
    for event in events_sorted:
        tech = event.get("Servised by", "غير معروف")
        if tech not in technician_events:
            technician_events[tech] = []
        technician_events[tech].append(event)
    
    for tech, tech_events in technician_events.items():
        if len(tech_events) > 1:
            tech_events_sorted = sorted(tech_events, key=lambda x: x["Date_parsed"])
            tech_intervals = []
            
            for i in range(1, len(tech_events_sorted)):
                delta = tech_events_sorted[i]["Date_parsed"] - tech_events_sorted[i-1]["Date_parsed"]
                tech_intervals.append(delta.days)
            
            analysis["by_technician"][tech] = {
                "event_count": len(tech_events),
                "avg_interval": sum(tech_intervals) / len(tech_intervals) if tech_intervals else None,
                "intervals": tech_intervals
            }
    
    # تحليل النشاط الأخير
    recent_limit = min(5, len(events_sorted))
    for i in range(recent_limit):
        event = events_sorted[-(i+1)]
        days_ago = (datetime.now() - event["Date_parsed"]).days
        analysis["recent_activity"].append({
            "event": event.get("Event", "غير معروف"),
            "date": event["Date_parsed"],
            "days_ago": days_ago,
            "technician": event.get("Servised by", "غير معروف")
        })
    
    return analysis

def check_row_criteria(row, df, card_num, target_techs, target_dates, 
                      search_terms, search_params):
    """التحقق من مطابقة الصف لمعايير البحث"""
    
    # 1. التحقق من فني الخدمة
    if target_techs:
        row_tech = get_servised_by_value(row).lower()
        if row_tech == "-" and not search_params["include_empty"]:
            return False
        
        tech_match = False
        if row_tech != "-":
            for tech in target_techs:
                if search_params["exact_match"]:
                    if tech == row_tech:
                        tech_match = True
                        break
                else:
                    if tech in row_tech:
                        tech_match = True
                        break
        
        if not tech_match:
            return False
    
    # 2. التحقق من التاريخ
    if target_dates:
        row_date = str(row.get("Date", "")).strip().lower() if pd.notna(row.get("Date")) else ""
        if not row_date and not search_params["include_empty"]:
            return False
        
        date_match = False
        if row_date:
            for date_term in target_dates:
                if search_params["exact_match"]:
                    if date_term == row_date:
                        date_match = True
                        break
                else:
                    if date_term in row_date:
                        date_match = True
                        break
        
        if not date_match:
            return False
    
    # 3. التحقق من نص البحث
    if search_terms:
        row_event, row_correction = extract_event_correction(row, df)
        row_event_lower = row_event.lower()
        row_correction_lower = row_correction.lower()
        
        if not row_event and not row_correction and not search_params["include_empty"]:
            return False
        
        text_match = False
        combined_text = f"{row_event_lower} {row_correction_lower}"
        
        for term in search_terms:
            if search_params["exact_match"]:
                if term == row_event_lower or term == row_correction_lower:
                    text_match = True
                    break
            else:
                if term in combined_text:
                    text_match = True
                    break
        
        if not text_match:
            return False
    
    return True

def show_advanced_search_results(search_params, all_sheets):
    """عرض نتائج البحث المتقدم مع التحليل الزمني"""
    st.markdown("### 📊 نتائج البحث")
    
    # شريط التقدم
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # البحث في البيانات
    all_results = []
    total_machines = 0
    processed_machines = 0
    
    # حساب إجمالي عدد الماكينات
    for sheet_name in all_sheets.keys():
        if sheet_name != "ServicePlan" and sheet_name.startswith("Card"):
            total_machines += 1
    
    # معالجة أرقام الماكينات المطلوبة
    target_card_numbers = parse_card_numbers(search_params["card_numbers"])
    
    # معالجة أسماء الفنيين
    target_techs = []
    if search_params["tech_names"]:
        techs = search_params["tech_names"].split(',')
        target_techs = [tech.strip().lower() for tech in techs if tech.strip()]
    
    # معالجة التواريخ
    target_dates = []
    if search_params["date_range"]:
        dates = search_params["date_range"].split(',')
        target_dates = [date.strip().lower() for date in dates if date.strip()]
    
    # معالجة نص البحث
    search_terms = []
    if search_params["search_text"]:
        terms = search_params["search_text"].split(',')
        search_terms = [term.strip().lower() for term in terms if term.strip()]
    
    # البحث في جميع الشيتات
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        # استخراج رقم الماكينة
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
            
        card_num = int(card_num_match.group(1))
        
        # التحقق من رقم الماكينة إذا كان هناك تحديد
        if target_card_numbers and card_num not in target_card_numbers:
            continue
        
        processed_machines += 1
        if total_machines > 0:
            progress_bar.progress(processed_machines / total_machines)
        status_text.text(f"🔍 جاري معالجة الماكينة {card_num}...")
        
        df = all_sheets[sheet_name].copy()
        
        # البحث في الصفوف
        for _, row in df.iterrows():
            # تطبيق معايير البحث
            if not check_row_criteria(row, df, card_num, target_techs, target_dates, 
                                     search_terms, search_params):
                continue
            
            # استخراج البيانات
            result = extract_row_data(row, df, card_num)
            if result:
                all_results.append(result)
    
    # إخفاء شريط التقدم
    progress_bar.empty()
    status_text.empty()
    
    # عرض النتائج
    if all_results:
        display_search_results(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def display_search_results(results, search_params):
    """عرض نتائج البحث بشكل احترافي مع ترتيب متسلسل والتحليل الزمني"""
    # تحويل النتائج إلى DataFrame
    if not results:
        st.warning("⚠ لا توجد نتائج لعرضها")
        return
    
    result_df = pd.DataFrame(results)
    
    # التأكد من وجود البيانات
    if result_df.empty:
        st.warning("⚠ لا توجد بيانات لعرضها")
        return
    
    # إنشاء نسخة للعرض مع معالجة الترتيب
    display_df = result_df.copy()
    
    # تحويل رقم الماكينة إلى رقم صحيح للترتيب (بشكل آمن)
    display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    
    # تحويل التواريخ لترتيب زمني (بشكل آمن)
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    
    # ترتيب النتائج حسب رقم الماكينة ثم التاريخ
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Card_Number_Clean'], 
                                          ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, True, False], na_position='last')
    else:  # رقم الماكينة (الافتراضي)
        display_df = display_df.sort_values(by=['Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, False], na_position='last')
    
    # إضافة ترتيب الأحداث لكل ماكينة
    display_df['Event_Order'] = display_df.groupby('Card Number').cumcount() + 1
    display_df['Total_Events'] = display_df.groupby('Card Number')['Card Number'].transform('count')
    
    # عرض الإحصائيات
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    
    with col2:
        unique_machines = display_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        # عدد الماكينات التي لديها أكثر من حدث
        if not display_df.empty:
            machine_counts = display_df.groupby('Card Number').size()
            multi_event_machines = (machine_counts > 1).sum()
            st.metric("🔢 مكن متعددة الأحداث", multi_event_machines)
        else:
            st.metric("🔢 مكن متعددة الأحداث", 0)
    
    with col4:
        if 'Correction' in display_df.columns:
            with_correction = display_df[display_df["Correction"] != "-"].shape[0]
            st.metric("✏ تحتوي على تصحيح", with_correction)
        else:
            st.metric("✏ تحتوي على تصحيح", 0)
    
    # عرض النتائج بشكل متسلسل
    st.markdown("### 📋 النتائج التفصيلية (مرتبة)")
    
    # تبويبات العرض
    display_tabs = st.tabs(["📊 جدول النتائج", "📋 حسب الماكينة", "⏱ التحليل الزمني", "📈 إحصائيات زمنية"])
    
    with display_tabs[0]:
        # العرض الجدولي التقليدي
        # فلترة النتائج
        st.markdown("#### 🔍 فلترة النتائج")
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            show_with_event = st.checkbox("📝 مع حدث", True, key="filter_event_1")
        with filter_col2:
            show_with_correction = st.checkbox("✏ مع تصحيح", True, key="filter_correction_1")
        with filter_col3:
            show_with_tech = st.checkbox("👨‍🔧 مع فني خدمة", True, key="filter_tech_1")
        
        # تطبيق الفلاتر
        filtered_df = display_df.copy()
        
        if not show_with_event and 'Event' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Event"] != "-"]
        if not show_with_correction and 'Correction' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Correction"] != "-"]
        if not show_with_tech and 'Servised by' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Servised by"] != "-"]
        
        # تحديد الأعمدة المراد عرضها
        columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date', 'Event_Order', 'Total_Events']
        columns_to_show = [col for col in columns_to_show if col in filtered_df.columns]
        
        if not filtered_df.empty:
            st.dataframe(
                filtered_df[columns_to_show].style.apply(style_table, axis=1),
                use_container_width=True,
                height=500
            )
        else:
            st.warning("⚠ لم يتم العثور على نتائج تطابق معايير الفلترة")
    
    with display_tabs[1]:
        # عرض تفصيلي لكل ماكينة بشكل منفصل
        # تجميع الماكينات الفريدة
        unique_machines = sorted(filtered_df['Card Number'].unique(), 
                               key=lambda x: pd.to_numeric(x, errors='coerce') if str(x).isdigit() else float('inf'))
        
        for machine in unique_machines:
            machine_data = filtered_df[filtered_df['Card Number'] == machine].copy()
            machine_data = machine_data.sort_values('Event_Order')
            
            with st.expander(f"🔧 الماكينة {machine} - عدد الأحداث: {len(machine_data)}", expanded=len(unique_machines) <= 5):
                
                # عرض إحصائيات الماكينة
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        st.metric("📅 أول حدث", machine_data['Date'].iloc[0] if machine_data['Date'].iloc[0] != "-" else "غير محدد")
                    else:
                        st.metric("📅 أول حدث", "-")
                with col_stats2:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        st.metric("📅 آخر حدث", machine_data['Date'].iloc[-1] if machine_data['Date'].iloc[-1] != "-" else "غير محدد")
                    else:
                        st.metric("📅 آخر حدث", "-")
                with col_stats3:
                    if not machine_data.empty and 'Servised by' in machine_data.columns:
                        tech_count = machine_data['Servised by'].nunique()
                        st.metric("👨‍🔧 فنيين مختلفين", tech_count)
                    else:
                        st.metric("👨‍🔧 فنيين مختلفين", 0)
                
                # عرض أحداث الماكينة
                for idx, row in machine_data.iterrows():
                    st.markdown("---")
                    col_event1, col_event2 = st.columns([3, 2])
                    
                    with col_event1:
                        event_order = row.get('Event_Order', '?')
                        total_events = row.get('Total_Events', '?')
                        st.markdown(f"**الحدث #{event_order} من {total_events}**")
                        if 'Date' in row:
                            st.markdown(f"**📅 التاريخ:** {row['Date']}")
                        if 'Event' in row and row['Event'] != '-':
                            st.markdown(f"**📝 الحدث:** {row['Event']}")
                        if 'Correction' in row and row['Correction'] != '-':
                            st.markdown(f"**✏ التصحيح:** {row['Correction']}")
                    
                    with col_event2:
                        if 'Servised by' in row and row['Servised by'] != '-':
                            st.markdown(f"**👨‍🔧 فني الخدمة:** {row['Servised by']}")
                        if 'Tones' in row and row['Tones'] != '-':
                            st.markdown(f"**⚖️ الأطنان:** {row['Tones']}")
    
    with display_tabs[2]:
        # تحليل زمني شامل لكل الماكينات
        st.markdown("### ⏱ التحليل الزمني الشامل")
        
        # جمع أحداث جميع الماكينات المختارة
        all_machine_events = []
        unique_machines = sorted(filtered_df['Card Number'].unique(), 
                               key=lambda x: pd.to_numeric(x, errors='coerce') if str(x).isdigit() else float('inf'))
        
        for machine in unique_machines:
            machine_data = filtered_df[filtered_df['Card Number'] == machine].copy()
            for _, row in machine_data.iterrows():
                event_data = {
                    "Card Number": machine,
                    "Event": row.get("Event", "-"),
                    "Date": row.get("Date", "-"),
                    "Date_parsed": row.get("Date_parsed"),
                    "Servised by": row.get("Servised by", "-"),
                    "Tones": row.get("Tones", "-")
                }
                if event_data["Date_parsed"]:
                    all_machine_events.append(event_data)
        
        if len(all_machine_events) < 2:
            st.info("ℹ️ لا يوجد ما يكفي من الأحداث للتحليل الزمني (تحتاج إلى حدثين على الأقل).")
        else:
            # تحليل زمني شامل
            time_analysis_all = analyze_time_intervals(all_machine_events)
            
            # إحصائيات عامة
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🔢 إجمالي الأحداث", time_analysis_all["stats"]["total_events"])
            
            with col2:
                if time_analysis_all["stats"]["avg_interval_days"]:
                    st.metric("⏱ متوسط المدة العامة", 
                             f"{time_analysis_all['stats']['avg_interval_days']:.1f} يوم")
                else:
                    st.metric("⏱ متوسط المدة العامة", "-")
            
            with col3:
                if time_analysis_all["stats"]["min_interval_days"]:
                    st.metric("⏱ أقصر مدة", 
                             f"{time_analysis_all['stats']['min_interval_days']} يوم")
                else:
                    st.metric("⏱ أقصر مدة", "-")
            
            with col4:
                if time_analysis_all["stats"]["max_interval_days"]:
                    st.metric("⏱ أطول مدة", 
                             f"{time_analysis_all['stats']['max_interval_days']} يوم")
                else:
                    st.metric("⏱ أطول مدة", "-")
            
            # تحليل حسب فني الخدمة
            st.markdown("#### 👨‍🔧 التحليل حسب فني الخدمة")
            
            if time_analysis_all["by_technician"]:
                tech_data = []
                for tech, stats in time_analysis_all["by_technician"].items():
                    tech_data.append({
                        "فني الخدمة": tech,
                        "عدد الأحداث": stats["event_count"],
                        "متوسط المدة (يوم)": f"{stats['avg_interval']:.1f}" if stats["avg_interval"] else "-",
                        "نشاط": "نشط" if stats["event_count"] > 1 else "مرة واحدة"
                    })
                
                tech_df = pd.DataFrame(tech_data)
                st.dataframe(tech_df, use_container_width=True)
            
            # النشاط الأخير
            st.markdown("#### 📅 النشاط الأخير")
            
            recent_activity = []
            for activity in time_analysis_all["recent_activity"][:5]:  # أول 5 أحداث
                recent_activity.append({
                    "الحدث": activity["event"][:50] + "..." if len(activity["event"]) > 50 else activity["event"],
                    "التاريخ": activity["date"].strftime("%Y-%m-%d") if activity["date"] else "-",
                    "قبل (يوم)": activity["days_ago"],
                    "فني الخدمة": activity["technician"]
                })
            
            if recent_activity:
                recent_df = pd.DataFrame(recent_activity)
                st.dataframe(recent_df, use_container_width=True)
            
            # توزيع الفترات الزمنية
            if time_analysis_all["time_intervals"]:
                st.markdown("#### 📊 توزيع الفترات الزمنية")
                
                intervals_data = [interval["days"] for interval in time_analysis_all["time_intervals"]]
                
                # محاولة استخدام plotly للمخططات
                try:
                    import plotly.express as px
                    
                    # توزيع المدد
                    fig_dist = px.histogram(
                        x=intervals_data,
                        title="توزيع المدد الزمنية بين الأحداث",
                        labels={"x": "المدة (أيام)", "y": "التكرار"},
                        nbins=20,
                        color_discrete_sequence=['#4ECDC4']
                    )
                    fig_dist.update_layout(
                        xaxis_title="المدة بين الأحداث (أيام)",
                        yaxis_title="عدد الفترات",
                        height=400
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                    
                except ImportError:
                    # استخدام streamlit charts بديل
                    st.bar_chart(
                        pd.DataFrame({"المدة (أيام)": intervals_data}).value_counts().sort_index(),
                        height=400
                    )
    
    with display_tabs[3]:
        # إحصائيات زمنية مفصلة
        st.markdown("### 📈 إحصائيات زمنية مفصلة")
        
        if len(filtered_df) < 2:
            st.info("ℹ️ لا يوجد ما يكفي من البيانات للإحصائيات الزمنية.")
        else:
            # حساب إحصائيات لكل ماكينة
            machine_stats = []
            
            for machine in unique_machines[:20]:  # أول 20 ماكينة فقط
                machine_data = filtered_df[filtered_df['Card Number'] == machine].copy()
                machine_events = []
                
                for _, row in machine_data.iterrows():
                    if row.get("Date_parsed"):
                        machine_events.append({
                            "Date_parsed": row.get("Date_parsed"),
                            "Event": row.get("Event", "-")
                        })
                
                if len(machine_events) > 1:
                    machine_events_sorted = sorted(machine_events, key=lambda x: x["Date_parsed"])
                    
                    # حساب الفترات
                    intervals = []
                    for i in range(1, len(machine_events_sorted)):
                        delta = machine_events_sorted[i]["Date_parsed"] - machine_events_sorted[i-1]["Date_parsed"]
                        intervals.append(delta.days)
                    
                    if intervals:
                        machine_stats.append({
                            "الماكينة": machine,
                            "عدد الأحداث": len(machine_events),
                            "أول حدث": machine_events_sorted[0]["Date_parsed"].strftime("%Y-%m-%d"),
                            "آخر حدث": machine_events_sorted[-1]["Date_parsed"].strftime("%Y-%m-%d"),
                            "متوسط المدة": sum(intervals) / len(intervals),
                            "أقصر مدة": min(intervals),
                            "أطول مدة": max(intervals),
                            "الفترة الكلية": (machine_events_sorted[-1]["Date_parsed"] - machine_events_sorted[0]["Date_parsed"]).days
                        })
            
            if machine_stats:
                stats_df = pd.DataFrame(machine_stats)
                
                # عرض أفضل 10 ماكينات من حيث النشاط
                st.markdown("#### 🏆 أكثر 10 ماكينات نشاطاً")
                top_active = stats_df.nlargest(10, "عدد الأحداث")
                st.dataframe(top_active, use_container_width=True)
                
                st.markdown("#### ⏱ أكثر 10 ماكينات من حيث المدة بين الأحداث")
                top_intervals = stats_df.nlargest(10, "متوسط المدة")
                st.dataframe(top_intervals, use_container_width=True)
                
                st.markdown("#### ⚡ أكثر 10 ماكينات من حيث التكرار (أقصر مدة بين الأحداث)")
                top_frequent = stats_df.nsmallest(10, "متوسط المدة")
                st.dataframe(top_frequent, use_container_width=True)
            else:
                st.info("ℹ️ لا توجد بيانات كافية للإحصائيات الزمنية.")
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        # تصدير Excel - استخدام البيانات الأصلية وترتيبها بشكل صحيح
        if not result_df.empty:
            buffer_excel = io.BytesIO()
            
            # إنشاء نسخة للتصدير مع ترتيب صحيح
            export_df = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_df['Card_Number_Clean_Export'] = pd.to_numeric(export_df['Card Number'], errors='coerce')
            export_df['Date_Clean_Export'] = pd.to_datetime(export_df['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_df = export_df.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                             ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_df = export_df.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
            # حفظ الملف
            export_df.to_excel(buffer_excel, index=False, engine="openpyxl")
            
            st.download_button(
                label="📊 حفظ كملف Excel",
                data=buffer_excel.getvalue(),
                file_name=f"بحث_أحداث_مرتب_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("⚠ لا توجد بيانات للتصدير")
    
    with export_col2:
        # تصدير CSV
        if not result_df.empty:
            buffer_csv = io.BytesIO()
            
            # إنشاء نسخة للتصدير مع ترتيب صحيح
            export_csv = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_csv['Card_Number_Clean_Export'] = pd.to_numeric(export_csv['Card Number'], errors='coerce')
            export_csv['Date_Clean_Export'] = pd.to_datetime(export_csv['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_csv = export_csv.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                               ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_csv = export_csv.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
            # حفظ الملف
            export_csv.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="📄 حفظ كملف CSV",
                data=buffer_csv.getvalue(),
                file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("⚠ لا توجد بيانات للتصدير")

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
            with col_btn2:
        if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
            st.rerun()

# Tab 4: إضافة إيفينت جديد
with tab4:
    add_new_event(sheets_edit)

# Tab 5: تعديل الإيفينت والكوريكشن
with tab5:
    edit_events_and_corrections(sheets_edit)
