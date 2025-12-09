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
# 🖥 دالة فحص الإيفينت والكوريكشن - الواجهة البسيطة
# -------------------------------
# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن - الواجهة البسيطة
# -------------------------------
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن بواجهة بسيطة ومباشرة"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    st.markdown("### 🔍 اختر طريقة البحث")
    
    # أربع خيارات بسيطة
    search_mode = st.radio(
        "اختر طريقة البحث:",
        ["🔎 بحث متعدد المعايير", "📅 عرض تسلسلي", "📊 احصائيات عامة", "🔧 تحليل مشاكل محددة"],
        horizontal=True,
        key="simple_events_mode"
    )
    
    if search_mode == "🔎 بحث متعدد المعايير":
        simple_multi_criteria_search(all_sheets)
    elif search_mode == "📅 عرض تسلسلي":
        simple_sequential_display(all_sheets)
    elif search_mode == "📊 احصائيات عامة":
        simple_statistics_display(all_sheets)
    else:
        analyze_specific_problems(all_sheets)

def simple_multi_criteria_search(all_sheets):
    """بحث متعدد المعايير بشكل بسيط"""
    st.markdown("### 🔍 معايير البحث")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # نطاق الماكينات
        st.markdown("**🔢 نطاق الماكينات:**")
        card_start = st.number_input("من:", min_value=1, max_value=50, value=1, step=1, key="card_start")
        card_end = st.number_input("إلى:", min_value=1, max_value=50, value=24, step=1, key="card_end")
        
        # فني الخدمة
        st.markdown("**👨‍🔧 فني الخدمة:**")
        tech_names = extract_available_techs(all_sheets)
        selected_tech = st.selectbox(
            "اختر فني الخدمة:",
            ["كل الفنيين"] + tech_names,
            key="simple_tech"
        )
    
    with col2:
        # التاريخ
        st.markdown("**📅 التاريخ:**")
        date_search = st.text_input(
            "ابحث بتاريخ (مثال: 2024 أو 1/2024):",
            placeholder="اتركه فارغاً للبحث في كل التواريخ",
            key="simple_date"
        )
        
        # نص البحث
        st.markdown("**📝 نص البحث:**")
        search_text = st.text_input(
            "ابحث في نص الحدث أو التصحيح:",
            placeholder="مثال: سير، محور، صيانة",
            key="simple_text"
        )
        
        # خيار البحث النصي
        exact_match = st.checkbox("🔍 مطابقة كاملة للنص", False, key="simple_exact")
    
    # زر البحث
    if st.button("🔍 بدء البحث", type="primary", key="simple_search_btn"):
        # جمع معايير البحث
        search_params = {
            "card_start": card_start,
            "card_end": card_end,
            "tech": selected_tech if selected_tech != "كل الفنيين" else "",
            "date": date_search,
            "text": search_text,
            "exact": exact_match
        }
        
        # تنفيذ البحث
        simple_execute_search(search_params, all_sheets)

def simple_execute_search(params, all_sheets):
    """تنفيذ البحث البسيط"""
    st.markdown("### 📋 نتائج البحث")
    
    with st.spinner("🔍 جاري البحث..."):
        results = []
        
        # جمع النتائج
        for card_num in range(params["card_start"], params["card_end"] + 1):
            sheet_name = f"Card{card_num}"
            if sheet_name in all_sheets:
                df = all_sheets[sheet_name]
                
                for _, row in df.iterrows():
                    # تطبيق معايير البحث
                    if not simple_check_row(row, df, card_num, params):
                        continue
                    
                    # استخراج البيانات
                    result = simple_extract_row_data(row, df, card_num)
                    if result:
                        results.append(result)
        
        # عرض النتائج
        if results:
            simple_display_results(results, params)
        else:
            st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")

def simple_check_row(row, df, card_num, params):
    """التحقق من مطابقة الصف لمعايير البحث البسيطة"""
    
    # التحقق من فني الخدمة
    if params["tech"]:
        row_tech = get_servised_by_value(row).strip()
        if not row_tech or row_tech == "-":
            return False
        if params["tech"].lower() not in row_tech.lower():
            return False
    
    # التحقق من التاريخ
    if params["date"]:
        row_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else ""
        if not row_date:
            return False
        if params["date"] not in row_date:
            return False
    
    # التحقق من نص البحث
    if params["text"]:
        event, correction = extract_event_correction(row, df)
        combined_text = f"{event} {correction}"
        
        if params["exact"]:
            # مطابقة كاملة
            if params["text"].lower() not in [event.lower(), correction.lower()]:
                return False
        else:
            # بحث جزئي
            if params["text"].lower() not in combined_text.lower():
                return False
    
    return True

def simple_extract_row_data(row, df, card_num):
    """استخراج بيانات الصف بشكل بسيط"""
    date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    
    event, correction = extract_event_correction(row, df)
    servised_by = get_servised_by_value(row)
    
    # إذا كانت كل الحقول فارغة، نتجاهل الصف
    if event == "-" and correction == "-" and date == "-" and tones == "-":
        return None
    
    return {
        "رقم الماكينة": card_num,
        "التاريخ": date,
        "الأطنان": tones,
        "الحدث": event,
        "التصحيح": correction,
        "فني الخدمة": servised_by
    }

def simple_display_results(results, params):
    """عرض نتائج البحث بشكل بسيط"""
    # تحويل النتائج إلى DataFrame
    result_df = pd.DataFrame(results)
    
    # ترتيب النتائج
    result_df = result_df.sort_values(["رقم الماكينة", "التاريخ"])
    
    # عرض إحصائيات
    st.markdown("#### 📊 إحصائيات النتائج")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🔢 عدد الماكينات", result_df["رقم الماكينة"].nunique())
    
    with col2:
        st.metric("📋 عدد النتائج", len(result_df))
    
    with col3:
        with_correction = result_df[result_df["التصحيح"] != "-"].shape[0]
        st.metric("✏ بها تصحيح", with_correction)
    
    # فلترة النتائج
    st.markdown("#### 🔍 فلترة النتائج")
    
    filter_col1, filter_col2 = st.columns(2)
    
    with filter_col1:
        show_only_with_events = st.checkbox("عرض الصفوف بها أحداث فقط", False, key="filter_events_only")
        show_only_with_corrections = st.checkbox("عرض الصفوف بها تصحيحات فقط", False, key="filter_corrections_only")
    
    with filter_col2:
        sort_by = st.selectbox(
            "ترتيب النتائج:",
            ["رقم الماكينة", "التاريخ", "فني الخدمة"],
            key="simple_sort_by"
        )
    
    # تطبيق الفلاتر
    filtered_df = result_df.copy()
    
    if show_only_with_events:
        filtered_df = filtered_df[filtered_df["الحدث"] != "-"]
    
    if show_only_with_corrections:
        filtered_df = filtered_df[filtered_df["التصحيح"] != "-"]
    
    # الترتيب
    if sort_by == "التاريخ":
        filtered_df = filtered_df.sort_values("التاريخ", ascending=False)
    elif sort_by == "فني الخدمة":
        filtered_df = filtered_df.sort_values("فني الخدمة")
    else:
        filtered_df = filtered_df.sort_values("رقم الماكينة")
    
    # عرض الجدول
    st.markdown(f"#### 📋 النتائج ({len(filtered_df)} صف)")
    
    # تنسيق الجدول
    def color_simple_row(row):
        styles = []
        for col in row.index:
            value = row[col]
            if col == "رقم الماكينة":
                styles.append("background-color: #e3f2fd; font-weight: bold;")
            elif col == "التاريخ" and value != "-":
                styles.append("background-color: #fff3cd;")
            elif col == "الحدث" and value != "-":
                styles.append("background-color: #d4edda;")
            elif col == "التصحيح" and value != "-":
                styles.append("background-color: #f8d7da;")
            else:
                styles.append("")
        return styles
    
    styled_df = filtered_df.style.apply(color_simple_row, axis=1)
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=500
    )
    
    # تحليل إضافي إذا كان البحث عن "سير"
    if params.get("text", "").lower() in ["سير", "حزام", "belt"]:
        st.markdown("#### 📈 تحليل مشاكل السير")
        analyze_belt_problems(filtered_df)
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        # تصدير Excel
        buffer = io.BytesIO()
        filtered_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="📊 حفظ كملف Excel",
            data=buffer.getvalue(),
            file_name=f"بحث_نتائج_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col_exp2:
        # تصدير CSV
        buffer = io.BytesIO()
        filtered_df.to_csv(buffer, index=False, encoding='utf-8-sig')
        st.download_button(
            label="📄 حفظ كملف CSV",
            data=buffer.getvalue(),
            file_name=f"بحث_نتائج_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

def analyze_belt_problems(df):
    """تحليل مشاكل السير في الماكينات"""
    st.markdown("##### 🔧 تحليل مشاكل السير")
    
    # تحليل التكرار
    belt_issues = df[df["الحدث"].str.contains("سير", case=False, na=False) | 
                     df["التصحيح"].str.contains("سير", case=False, na=False)]
    
    if not belt_issues.empty:
        # تحليل حسب الماكينة
        machine_analysis = belt_issues.groupby("رقم الماكينة").agg({
            "التاريخ": "count",
            "الحدث": lambda x: ", ".join(x[x != "-"].unique()),
            "التصحيح": lambda x: ", ".join(x[x != "-"].unique())
        }).rename(columns={"التاريخ": "عدد مرات المشكلة"})
        
        st.dataframe(machine_analysis, use_container_width=True)
        
        # تحليل زمني
        belt_issues["التاريخ_مفهرس"] = pd.to_datetime(belt_issues["التاريخ"], errors='coerce')
        monthly_issues = belt_issues.groupby(belt_issues["التاريخ_مفهرس"].dt.to_period("M")).size()
        
        if not monthly_issues.empty:
            st.markdown("##### 📅 توزيع المشاكل حسب الشهر")
            monthly_df = pd.DataFrame({
                "الشهر": monthly_issues.index.astype(str),
                "عدد المشاكل": monthly_issues.values
            })
            st.bar_chart(monthly_df.set_index("الشهر"))

def simple_sequential_display(all_sheets):
    """عرض تسلسلي بسيط حسب الماكينة والتاريخ"""
    st.markdown("### 📅 العرض التسلسلي")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # نطاق الماكينات
        st.markdown("**🔢 نطاق الماكينات:**")
        seq_start = st.number_input("من الماكينة:", min_value=1, max_value=50, value=1, step=1, key="seq_start")
        seq_end = st.number_input("إلى الماكينة:", min_value=1, max_value=50, value=24, step=1, key="seq_end")
        
        # نوع العرض
        st.markdown("**📊 نوع العرض:**")
        display_type = st.selectbox(
            "اختر طريقة العرض:",
            ["تسلسل حسب الماكينة", "تسلسل حسب التاريخ", "ملخص شهري"],
            key="display_type"
        )
    
    with col2:
        # تصفية
        st.markdown("**🔍 خيارات التصفية:**")
        show_empty = st.checkbox("عرض الصفوف الفارغة", False, key="seq_show_empty")
        
        # خيارات إضافية
        if display_type == "ملخص شهري":
            selected_year = st.selectbox(
                "السنة:",
                list(range(2020, 2031)),
                index=5,  # 2025
                key="seq_year"
            )
    
    if st.button("📋 عرض البيانات", type="primary", key="seq_display_btn"):
        # جمع البيانات
        all_data = []
        
        for card_num in range(seq_start, seq_end + 1):
            sheet_name = f"Card{card_num}"
            if sheet_name in all_sheets:
                df = all_sheets[sheet_name]
                
                for _, row in df.iterrows():
                    date_str = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else ""
                    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                    event, correction = extract_event_correction(row, df)
                    servised_by = get_servised_by_value(row)
                    
                    # إذا كانت كل الحقول فارغة وكان التصفية نشطة، نتجاوز
                    if not show_empty and event == "-" and correction == "-" and not date_str and tones == "-":
                        continue
                    
                    all_data.append({
                        "رقم الماكينة": card_num,
                        "التاريخ": date_str,
                        "الأطنان": tones,
                        "الحدث": event,
                        "التصحيح": correction,
                        "فني الخدمة": servised_by
                    })
        
        if all_data:
            seq_df = pd.DataFrame(all_data)
            
            if display_type == "تسلسل حسب الماكينة":
                seq_df = seq_df.sort_values(["رقم الماكينة", "التاريخ"])
                simple_display_sequential_by_machine(seq_df)
            elif display_type == "تسلسل حسب التاريخ":
                seq_df = seq_df.sort_values(["التاريخ", "رقم الماكينة"])
                simple_display_sequential_by_date(seq_df)
            else:
                simple_display_monthly_summary(seq_df, selected_year)
        else:
            st.warning("⚠ لا توجد بيانات للعرض")

def simple_display_sequential_by_machine(df):
    """عرض تسلسلي حسب الماكينة"""
    st.markdown(f"#### 📋 العرض حسب الماكينة ({len(df)} حدث)")
    
    # إحصائيات
    col1, col2, col3 = st.columns(3)
    
    with col1:
        machines_count = df["رقم الماكينة"].nunique()
        st.metric("🔢 عدد الماكينات", machines_count)
    
    with col2:
        events_count = df[df["الحدث"] != "-"].shape[0]
        st.metric("📝 عدد الأحداث", events_count)
    
    with col3:
        if df["التاريخ"].notna().any() and df["التاريخ"].str.strip().ne("").any():
            first_date = df[df["التاريخ"] != ""]["التاريخ"].min()
            last_date = df[df["التاريخ"] != ""]["التاريخ"].max()
            st.metric("📅 النطاق الزمني", f"{first_date} - {last_date}")
        else:
            st.metric("📅 النطاق الزمني", "-")
    
    # عرض البيانات
    st.dataframe(
        df.style.apply(
            lambda row: ["background-color: #e3f2fd; font-weight: bold;" if col == "رقم الماكينة" else "" for col in row.index], 
            axis=1
        ),
        use_container_width=True,
        height=500
    )

def simple_display_sequential_by_date(df):
    """عرض تسلسلي حسب التاريخ"""
    st.markdown(f"#### 📅 العرض حسب التاريخ ({len(df)} حدث)")
    
    # تحليل زمني بسيط
    if df["التاريخ"].notna().any() and df["التاريخ"].str.strip().ne("").any():
        try:
            df["التاريخ_مفهرس"] = pd.to_datetime(df["التاريخ"], errors='coerce')
            
            # عرض حسب الشهر
            if df["التاريخ_مفهرس"].notna().any():
                monthly_counts = df[df["التاريخ_مفهرس"].notna()].groupby(
                    df["التاريخ_مفهرس"].dt.to_period("M")
                ).size()
                
                if not monthly_counts.empty:
                    st.markdown("##### 📊 توزيع الأحداث حسب الشهر")
                    monthly_df = pd.DataFrame({
                        "الشهر": monthly_counts.index.astype(str),
                        "عدد الأحداث": monthly_counts.values
                    })
                    st.bar_chart(monthly_df.set_index("الشهر"))
        except:
            pass
    
    # عرض البيانات
    display_df = df.drop(columns=["التاريخ_مفهرس"]) if "التاريخ_مفهرس" in df.columns else df
    
    st.dataframe(
        display_df.style.apply(
            lambda row: ["background-color: #fff3cd;" if col == "التاريخ" else "" for col in row.index], 
            axis=1
        ),
        use_container_width=True,
        height=400
    )

def simple_display_monthly_summary(df, year):
    """عرض ملخص شهري"""
    st.markdown(f"#### 📊 ملخص شهري لعام {year}")
    
    # تحليل الشهور
    if df["التاريخ"].notna().any() and df["التاريخ"].str.strip().ne("").any():
        try:
            df["التاريخ_مفهرس"] = pd.to_datetime(df["التاريخ"], errors='coerce')
        except:
            df["التاريخ_مفهرس"] = pd.NaT
    
    # فلترة بالسنة
    if year and "التاريخ_مفهرس" in df.columns:
        df = df[df["التاريخ_مفهرس"].dt.year == year]
    
    if df.empty:
        st.warning(f"⚠ لا توجد بيانات لعام {year}")
        return
    
    # إنشاء ملخص شهري
    months = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]
    
    summary_data = []
    
    for month_num, month_name in enumerate(months, 1):
        if "التاريخ_مفهرس" in df.columns:
            month_events = df[df["التاريخ_مفهرس"].dt.month == month_num]
        else:
            month_events = df
        
        if not month_events.empty:
            machines_with_events = month_events["رقم الماكينة"].nunique()
            total_events = month_events[month_events["الحدث"] != "-"].shape[0]
            total_corrections = month_events[month_events["التصحيح"] != "-"].shape[0]
            
            # تحليل المشاكل الشائعة
            if not month_events[month_events["الحدث"] != "-"].empty:
                common_events = month_events[month_events["الحدث"] != "-"]["الحدث"].value_counts().head(3)
                common_problems = ", ".join([f"{prob[:20]}..." for prob in common_events.index]) if not common_events.empty else "-"
            else:
                common_problems = "-"
            
            summary_data.append({
                "الشهر": month_name,
                "عدد الماكينات": machines_with_events,
                "عدد الأحداث": total_events,
                "عدد التصحيحات": total_corrections,
                "المشاكل الشائعة": common_problems
            })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        
        # عرض الملخص
        def color_monthly_row(row):
            styles = []
            for col in row.index:
                if col == "عدد الأحداث" and row[col] > 5:
                    styles.append("background-color: #e8f5e9;")
                elif col == "عدد الأحداث" and row[col] > 0:
                    styles.append("background-color: #fff3cd;")
                else:
                    styles.append("")
            return styles
        
        styled_df = summary_df.style.apply(color_monthly_row, axis=1)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=400
        )
    else:
        st.info(f"ℹ️ لا توجد أحداث مسجلة لعام {year}")

def simple_statistics_display(all_sheets):
    """عرض إحصائيات عامة"""
    st.markdown("### 📊 إحصائيات عامة")
    
    # نطاق الماكينات
    col1, col2 = st.columns(2)
    
    with col1:
        stat_start = st.number_input("من الماكينة:", min_value=1, max_value=50, value=1, step=1, key="stat_start")
        stat_end = st.number_input("إلى الماكينة:", min_value=1, max_value=50, value=24, step=1, key="stat_end")
    
    with col2:
        stat_year = st.selectbox(
            "السنة (اختياري):",
            ["كل السنوات"] + list(range(2020, 2031)),
            key="stat_year"
        )
    
    if st.button("📈 عرض الإحصائيات", type="primary", key="stat_btn"):
        with st.spinner("📊 جاري تحليل البيانات..."):
            # جمع البيانات
            all_data = []
            
            for card_num in range(stat_start, stat_end + 1):
                sheet_name = f"Card{card_num}"
                if sheet_name in all_sheets:
                    df = all_sheets[sheet_name]
                    
                    for _, row in df.iterrows():
                        date_str = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else ""
                        event, correction = extract_event_correction(row, df)
                        servised_by = get_servised_by_value(row)
                        
                        # تحليل التاريخ
                        year_num = 0
                        if date_str:
                            date_parts = re.split(r'[/\-\\\. ]', date_str)
                            if len(date_parts) >= 3:
                                try:
                                    year_num = int(date_parts[2]) if date_parts[2].isdigit() else 0
                                except:
                                    pass
                        
                        # فلترة بالسنة إذا تم تحديدها
                        if stat_year != "كل السنوات" and year_num != 0 and year_num != stat_year:
                            continue
                        
                        all_data.append({
                            "رقم الماكينة": card_num,
                            "التاريخ": date_str,
                            "السنة": year_num,
                            "الحدث": event,
                            "التصحيح": correction,
                            "فني الخدمة": servised_by
                        })
            
            if all_data:
                stat_df = pd.DataFrame(all_data)
                display_simple_statistics(stat_df)
            else:
                st.warning("⚠ لا توجد بيانات للتحليل")

def display_simple_statistics(df):
    """عرض إحصائيات بسيطة"""
    st.markdown("#### 📈 الإحصائيات العامة")
    
    # الإحصائيات الأساسية
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_machines = df["رقم الماكينة"].nunique()
        st.metric("🔢 عدد الماكينات", total_machines)
    
    with col2:
        total_events = df[df["الحدث"] != "-"].shape[0]
        st.metric("📝 إجمالي الأحداث", total_events)
    
    with col3:
        total_corrections = df[df["التصحيح"] != "-"].shape[0]
        st.metric("✏ إجمالي التصحيحات", total_corrections)
    
    with col4:
        unique_techs = df[df["فني الخدمة"] != "-"]["فني الخدمة"].nunique()
        st.metric("👨‍🔧 عدد الفنيين", unique_techs)
    
    st.markdown("---")
    
    # تحليل الماكينات
    st.markdown("#### 🔢 تحليل الماكينات")
    
    machine_stats = df.groupby("رقم الماكينة").agg({
        "الحدث": lambda x: x[x != "-"].count(),
        "التصحيح": lambda x: x[x != "-"].count(),
        "فني الخدمة": lambda x: x[x != "-"].nunique()
    }).rename(columns={
        "الحدث": "عدد الأحداث",
        "التصحيح": "عدد التصحيحات",
        "فني الخدمة": "عدد الفنيين"
    })
    
    # ترتيب حسب عدد الأحداث
    machine_stats = machine_stats.sort_values("عدد الأحداث", ascending=False)
    
    st.dataframe(
        machine_stats.style.background_gradient(subset=["عدد الأحداث"], cmap="Reds"),
        use_container_width=True,
        height=300
    )
    
    st.markdown("---")
    
    # تحليل الفنيين
    if not df[df["فني الخدمة"] != "-"].empty:
        st.markdown("#### 👨‍🔧 تحليل الفنيين")
        
        tech_stats = df[df["فني الخدمة"] != "-"].groupby("فني الخدمة").agg({
            "رقم الماكينة": "nunique",
            "الحدث": lambda x: x[x != "-"].count(),
            "التصحيح": lambda x: x[x != "-"].count()
        }).rename(columns={
            "رقم الماكينة": "عدد الماكينات",
            "الحدث": "عدد الأحداث",
            "التصحيح": "عدد التصحيحات"
        })
        
        # ترتيب حسب عدد الماكينات
        tech_stats = tech_stats.sort_values("عدد الماكينات", ascending=False)
        
        st.dataframe(
            tech_stats.style.background_gradient(subset=["عدد الماكينات"], cmap="Blues"),
            use_container_width=True,
            height=300
        )
    
    st.markdown("---")
    
    # تحليل المشاكل الشائعة
    st.markdown("#### 🔧 المشاكل الشائعة")
    
    # تحليل الأحداث
    if not df[df["الحدث"] != "-"].empty:
        common_events = df[df["الحدث"] != "-"]["الحدث"].value_counts().head(10)
        events_df = pd.DataFrame({
            "المشكلة": common_events.index,
            "التكرار": common_events.values,
            "النسبة %": (common_events.values / len(df[df["الحدث"] != "-"]) * 100).round(1)
        })
        
        st.dataframe(
            events_df.style.background_gradient(subset=["التكرار"], cmap="Greens"),
            use_container_width=True,
            height=300
        )

def analyze_specific_problems(all_sheets):
    """تحليل مشاكل محددة"""
    st.markdown("### 🔧 تحليل مشاكل محددة")
    
    st.markdown("#### 🔍 اختر نوع المشكلة للتحليل")
    
    problem_types = {
        "سير": ["سير", "حزام", "belt"],
        "محور": ["محور", "عمود", "شفت"],
        "ماتور": ["ماتور", "موتور", "محرك"],
        "كهرباء": ["كهرباء", "كابلات", "أسلاك", "فيوز"],
        "تزييت": ["زيت", "تزييت", "شحم", "لبركة"],
        "تنظيف": ["تنظيف", "غسيل", "نظافة"]
    }
    
    selected_problem = st.selectbox(
        "اختر نوع المشكلة:",
        list(problem_types.keys()),
        key="problem_type"
    )
    
    # نطاق الماكينات
    col1, col2 = st.columns(2)
    
    with col1:
        problem_start = st.number_input("من الماكينة:", min_value=1, max_value=50, value=1, step=1, key="problem_start")
        problem_end = st.number_input("إلى الماكينة:", min_value=1, max_value=50, value=24, step=1, key="problem_end")
    
    with col2:
        problem_year = st.selectbox(
            "السنة (اختياري):",
            ["كل السنوات"] + list(range(2020, 2031)),
            key="problem_year"
        )
        show_details = st.checkbox("عرض التفاصيل", True, key="problem_details")
    
    if st.button("🔧 تحليل المشكلة", type="primary", key="analyze_btn"):
        # جمع البيانات
        all_data = []
        
        for card_num in range(problem_start, problem_end + 1):
            sheet_name = f"Card{card_num}"
            if sheet_name in all_sheets:
                df = all_sheets[sheet_name]
                
                for _, row in df.iterrows():
                    date_str = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else ""
                    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                    event, correction = extract_event_correction(row, df)
                    servised_by = get_servised_by_value(row)
                    
                    # تحليل التاريخ
                    year_num = 0
                    if date_str:
                        date_parts = re.split(r'[/\-\\\. ]', date_str)
                        if len(date_parts) >= 3:
                            try:
                                year_num = int(date_parts[2]) if date_parts[2].isdigit() else 0
                            except:
                                pass
                    
                    # فلترة بالسنة إذا تم تحديدها
                    if problem_year != "كل السنوات" and year_num != 0 and year_num != problem_year:
                        continue
                    
                    # البحث عن المشكلة في النص
                    search_terms = problem_types[selected_problem]
                    problem_found = False
                    
                    for term in search_terms:
                        if term.lower() in str(event).lower() or term.lower() in str(correction).lower():
                            problem_found = True
                            break
                    
                    if problem_found:
                        all_data.append({
                            "رقم الماكينة": card_num,
                            "التاريخ": date_str,
                            "السنة": year_num,
                            "الأطنان": tones,
                            "الحدث": event,
                            "التصحيح": correction,
                            "فني الخدمة": servised_by
                        })
        
        if all_data:
            problem_df = pd.DataFrame(all_data)
            display_problem_analysis(problem_df, selected_problem, show_details)
        else:
            st.warning(f"⚠ لم يتم العثور على مشاكل {selected_problem} في النطاق المحدد")

def display_problem_analysis(df, problem_type, show_details):
    """عرض تحليل المشكلة"""
    st.markdown(f"#### 🔧 تحليل مشاكل {problem_type}")
    
    # الإحصائيات
    col1, col2, col3 = st.columns(3)
    
    with col1:
        affected_machines = df["رقم الماكينة"].nunique()
        st.metric("🔢 عدد الماكينات المتأثرة", affected_machines)
    
    with col2:
        total_occurrences = len(df)
        st.metric("📋 عدد مرات الحدوث", total_occurrences)
    
    with col3:
        if df["التاريخ"].notna().any() and df["التاريخ"].str.strip().ne("").any():
            first_occurrence = df[df["التاريخ"] != ""]["التاريخ"].min()
            last_occurrence = df[df["التاريخ"] != ""]["التاريخ"].max()
            st.metric("📅 النطاق الزمني", f"{first_occurrence} - {last_occurrence}")
        else:
            st.metric("📅 النطاق الزمني", "-")
    
    st.markdown("---")
    
    # تحليل الماكينات الأكثر تعرضاً للمشكلة
    st.markdown("##### 🔢 الماكينات الأكثر تعرضاً للمشكلة")
    
    machine_counts = df.groupby("رقم الماكينة").size().sort_values(ascending=False)
    
    if not machine_counts.empty:
        machine_df = pd.DataFrame({
            "رقم الماكينة": machine_counts.index,
            "عدد مرات المشكلة": machine_counts.values
        })
        
        st.dataframe(
            machine_df.style.background_gradient(subset=["عدد مرات المشكلة"], cmap="Reds"),
            use_container_width=True,
            height=300
        )
    
    # تحليل زمني
    if df["التاريخ"].notna().any() and df["التاريخ"].str.strip().ne("").any():
        try:
            df["التاريخ_مفهرس"] = pd.to_datetime(df["التاريخ"], errors='coerce')
            
            if df["التاريخ_مفهرس"].notna().any():
                st.markdown("##### 📅 توزيع المشاكل حسب الوقت")
                
                monthly_counts = df[df["التاريخ_مفهرس"].notna()].groupby(
                    df["التاريخ_مفهرس"].dt.to_period("M")
                ).size()
                
                if not monthly_counts.empty:
                    monthly_df = pd.DataFrame({
                        "الشهر": monthly_counts.index.astype(str),
                        "عدد المشاكل": monthly_counts.values
                    })
                    
                    st.bar_chart(monthly_df.set_index("الشهر"))
        except:
            pass
    
    # عرض التفاصيل إذا طلب المستخدم
    if show_details and not df.empty:
        st.markdown("##### 📋 التفاصيل الكاملة")
        
        # ترتيب حسب الماكينة ثم التاريخ
        df = df.sort_values(["رقم الماكينة", "التاريخ"])
        
        # إزالة العمود المؤقت إذا كان موجوداً
        display_df = df.drop(columns=["التاريخ_مفهرس"]) if "التاريخ_مفهرس" in df.columns else df
        
        st.dataframe(
            display_df.style.apply(
                lambda row: ["background-color: #f8d7da;" for _ in row], 
                axis=1
            ),
            use_container_width=True,
            height=400
        )
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

# -------------------------------
# 👥 إدارة المستخدمين (للمسؤولين فقط)
# -------------------------------
def manage_users():
    """إدارة المستخدمين والصلاحيات"""
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    
    # عرض المستخدمين الحاليين
    st.markdown("### 📋 المستخدمون الحاليون")
    
    if users:
        # إنشاء DataFrame للمستخدمين
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
    
    # تبويبات لإدارة المستخدمين
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
            
            # اختيار الصلاحيات بناءً على الدور
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
            
            if new_username in users:
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
            
            # إضافة المستخدم الجديد
            users[new_username] = {
                "password": new_password,
                "role": user_role,
                "permissions": selected_permissions if selected_permissions else default_permissions,
                "created_at": datetime.now().isoformat()
            }
            
            if save_users(users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح!")
                st.rerun()
            else:
                st.error("❌ حدث خطأ أثناء حفظ المستخدم.")
    
    with user_tabs[1]:
        st.markdown("#### ✏ تعديل مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لتعديلهم.")
        else:
            user_to_edit = st.selectbox(
                "اختر المستخدم للتعديل:",
                list(users.keys()),
                key="select_user_to_edit"
            )
            
            if user_to_edit:
                user_info = users[user_to_edit]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**المستخدم:** {user_to_edit}")
                    st.info(f"**الدور الحالي:** {user_info.get('role', 'viewer')}")
                    
                    # تغيير كلمة المرور
                    st.markdown("##### 🔐 تغيير كلمة المرور")
                    new_password_edit = st.text_input("كلمة المرور الجديدة:", type="password", key="edit_password")
                    confirm_password_edit = st.text_input("تأكيد كلمة المرور:", type="password", key="edit_confirm_password")
                
                with col2:
                    # تغيير الدور
                    new_role = st.selectbox(
                        "تغيير الدور:",
                        ["admin", "editor", "viewer"],
                        index=["admin", "editor", "viewer"].index(user_info.get("role", "viewer")),
                        key="edit_user_role"
                    )
                    
                    # تغيير الصلاحيات بناءً على الدور الجديد
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
                
                # أزرار التعديل
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 حفظ التعديلات", key="save_user_edit"):
                        updated = False
                        
                        # تحديث الدور والصلاحيات
                        if user_info.get("role") != new_role or user_info.get("permissions") != new_permissions:
                            users[user_to_edit]["role"] = new_role
                            users[user_to_edit]["permissions"] = new_permissions if new_permissions else default_permissions
                            updated = True
                        
                        # تحديث كلمة المرور إذا تم إدخالها
                        if new_password_edit:
                            if new_password_edit != confirm_password_edit:
                                st.error("❌ كلمة المرور غير مطابقة.")
                                return
                            if len(new_password_edit) < 6:
                                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                                return
                            
                            users[user_to_edit]["password"] = new_password_edit
                            updated = True
                        
                        if updated:
                            if save_users(users):
                                st.success(f"✅ تم تحديث المستخدم '{user_to_edit}' بنجاح!")
                                
                                # إذا كان المستخدم الحالي هو الذي تم تعديله، قم بتحديث session state
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
                    # زر إعادة تعيين كلمة المرور
                    if st.button("🔄 إعادة تعيين كلمة المرور", key="reset_password"):
                        # كلمة مرور افتراضية
                        default_password = "user123"
                        users[user_to_edit]["password"] = default_password
                        
                        if save_users(users):
                            st.warning(f"⚠ تم إعادة تعيين كلمة مرور '{user_to_edit}' إلى: {default_password}")
                            st.info("📋 يجب على المستخدم تغيير كلمة المرور عند أول تسجيل دخول.")
                            st.rerun()
    
    with user_tabs[2]:
        st.markdown("#### 🗑 حذف مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لحذفهم.")
        else:
            # قائمة المستخدمين المتاحة للحذف (لا يمكن حذف المسؤول الرئيسي)
            deletable_users = [u for u in users.keys() if u != "admin"]
            
            if not deletable_users:
                st.warning("⚠ لا يمكن حذف أي مستخدمين (يوجد المسؤول الرئيسي فقط).")
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
                    
                    # تأكيد الحذف
                    confirm_delete = st.checkbox(f"أؤكد أنني أريد حذف المستخدم '{user_to_delete}'", key="confirm_delete")
                    
                    if confirm_delete:
                        if st.button("🗑️ حذف المستخدم نهائياً", type="primary", key="delete_user_final"):
                            # التحقق من أن المستخدم ليس مسجلاً دخولاً حالياً
                            state = load_state()
                            if user_to_delete in state and state[user_to_delete].get("active"):
                                st.error("❌ لا يمكن حذف المستخدم أثناء تسجيل دخوله.")
                                return
                            
                            # حذف المستخدم
                            del users[user_to_delete]
                            
                            if save_users(users):
                                st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح!")
                                st.rerun()
                            else:
                                st.error("❌ حدث خطأ أثناء حذف المستخدم.")

# -------------------------------
# 📞 الدعم الفني
# -------------------------------
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
    
    # عرض إحصائيات النظام
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # عدد المستخدمين
        users = load_users()
        st.metric("👥 عدد المستخدمين", len(users))
    
    with col2:
        # عدد الجلسات النشطة
        state = load_state()
        active_sessions = sum(1 for u in state.values() if u.get("active"))
        st.metric("🔒 جلسات نشطة", f"{active_sessions}/{MAX_ACTIVE_USERS}")
    
    with col3:
        # حجم الملف المحلي
        if os.path.exists(APP_CONFIG["LOCAL_FILE"]):
            file_size = os.path.getsize(APP_CONFIG["LOCAL_FILE"]) / (1024 * 1024)  # بالميجابايت
            st.metric("💾 حجم الملف", f"{file_size:.2f} MB")
        else:
            st.metric("💾 حجم الملف", "غير موجود")
    
    st.markdown("---")
    
    # معلومات الجلسة الحالية
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
    
    # زر إعادة التشغيل
    st.markdown("---")
    if st.button("🔄 إعادة تشغيل التطبيق", key="restart_app"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في إعادة التشغيل: {e}")

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
        # واجهة بحث متعدد المعايير
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

            # Tab 1: تعديل بيانات وعرض
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

            # Tab 3: إضافة عمود جديد
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

            # Tab 4: إضافة إيفينت جديد
            with tab4:
                add_new_event(sheets_edit)

            # Tab 5: تعديل الإيفينت والكوريكشن
            with tab5:
                edit_events_and_corrections(sheets_edit)
