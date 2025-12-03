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
    "FILE_PATH": "elquds2.xlsx",
    "LOCAL_FILE": "elquds2.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
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
# 🖥 دالة فحص السيرفيس فقط
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
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
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

        mask = (services_df.get("Min_Tones", 0).fillna(0) <= slice_max) & (services_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
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

                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                servised_by_value = get_servised_by_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
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
# 🖥 دالة فحص الإيفينت والكوريكشن فقط
# -------------------------------
def check_events_and_corrections(card_num, all_sheets):
    """فحص الإيفينت والكوريكشن فقط"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    card_events_sheet_name = f"Card{card_num}_Events"
    
    if card_events_sheet_name not in all_sheets:
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
            events_df = card_df[
                (card_df.get("Min_Tones", pd.NA).isna()) | 
                (card_df.get("Max_Tones", pd.NA).isna()) |
                ((card_df.get("Min_Tones", "") == "") & (card_df.get("Max_Tones", "") == ""))
            ].copy()
        else:
            st.warning(f"⚠ لا يوجد شيت باسم {card_events_sheet_name} أو {card_old_sheet_name}")
            return
    else:
        events_df = all_sheets[card_events_sheet_name].copy()

    st.subheader("🔍 خيارات البحث")
    
    col1, col2 = st.columns(2)
    with col1:
        search_date = st.text_input("البحث بالتاريخ (مثال: 2024, 2025, 1\\2025):", "", key=f"search_date_{card_num}")
    with col2:
        search_event = st.text_input("البحث بالحدث:", "", key=f"search_event_{card_num}")
    
    col3, col4 = st.columns(2)
    with col3:
        search_correction = st.text_input("البحث بالتصحيح:", "", key=f"search_correction_{card_num}")
    with col4:
        search_serviced_by = st.text_input("البحث بفني الخدمة:", "", key=f"search_serviced_by_{card_num}")

    filtered_df = events_df.copy()
    
    if search_date:
        filtered_df = filtered_df[filtered_df.astype(str).apply(lambda row: row.str.contains(search_date, case=False, na=False).any(), axis=1)]
    
    if search_event:
        event_columns = [col for col in filtered_df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
        if event_columns:
            mask = filtered_df[event_columns[0]].astype(str).str.contains(search_event, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    if search_correction:
        correction_columns = [col for col in filtered_df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
        if correction_columns:
            mask = filtered_df[correction_columns[0]].astype(str).str.contains(search_correction, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    if search_serviced_by:
        servised_columns = [col for col in filtered_df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
        if servised_columns:
            mask = filtered_df[servised_columns[0]].astype(str).str.contains(search_serviced_by, case=False, na=False)
            filtered_df = filtered_df[mask]

    events_results = []
    for _, row in filtered_df.iterrows():
        card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else "-"
        date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
        tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
        
        event_value = "-"
        event_columns = [col for col in events_df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
        for event_col in event_columns:
            if event_col in row and pd.notna(row[event_col]) and str(row[event_col]).strip() != "":
                event_value = str(row[event_col]).strip()
                break
        
        correction_value = "-"
        correction_columns = [col for col in events_df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
        for correction_col in correction_columns:
            if correction_col in row and pd.notna(row[correction_col]) and str(row[correction_col]).strip() != "":
                correction_value = str(row[correction_col]).strip()
                break
        
        servised_by_value = get_servised_by_value(row)

        if event_value != "-" or correction_value != "-" or servised_by_value != "-":
            events_results.append({
                "Card Number": card_num_value,
                "Event": event_value,
                "Correction": correction_value,
                "Servised by": servised_by_value,
                "Tones": tones,
                "Date": date
            })

    events_df_result = pd.DataFrame(events_results).dropna(how="all").reset_index(drop=True)

    if events_df_result.empty:
        st.info("ℹ️ لا توجد أحداث أو تصحيحات مطابقة لمعايير البحث.")
    else:
        st.markdown("### 📋 نتائج فحص الإيفينت والكوريكشن")
        st.dataframe(events_df_result.style.apply(style_table, axis=1), use_container_width=True)

        buffer = io.BytesIO()
        events_df_result.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Events_Corrections_Card{card_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# -------------------------------
# 🖥 دالة البحث المتقدم مع التخصيص الكامل
# -------------------------------
def advanced_search(all_sheets):
    """بحث متقدم مع تخصيص كامل"""
    st.header("🔍 البحث المتقدم")
    
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # خيارات البحث الرئيسية
    st.subheader("🔎 معايير البحث")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search_type = st.selectbox(
            "نوع البحث:",
            ["الكل", "الخدمات", "الأحداث", "الخدمات والأحداث"],
            key="adv_search_type"
        )
    
    with col2:
        search_card = st.number_input(
            "رقم الماكينة (اختياري):", 
            min_value=1, 
            step=1, 
            value=None,
            key="adv_search_card"
        )
    
    with col3:
        search_text = st.text_input(
            "كلمة البحث (نص):",
            "",
            key="adv_search_text",
            help="ابحث في أي نص (سير، عيار، كوريكشن، إلخ)"
        )
    
    with col4:
        search_technician = st.text_input(
            "فني الخدمة:",
            "",
            key="adv_search_technician",
            help="ابحث باسم فني الخدمة"
        )
    
    # خيارات تخصيص إضافية
    st.subheader("⚙️ خيارات التخصيص")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_date = st.text_input(
            "التاريخ:",
            "",
            key="adv_search_date",
            help="مثال: 2024, 2025, 1\\2025"
        )
    
    with col2:
        specific_service = st.selectbox(
            "خدمة محددة:",
            ["الكل", "سير", "عيار", "كوريكشن", "كورسينج", "فيلينج", "كليننج", "بوليش", "اكستراكت"],
            key="adv_specific_service"
        )
    
    with col3:
        exact_match = st.checkbox("بحث مطابق للنص", key="adv_exact_match")
        show_empty = st.checkbox("عرض البيانات الفارغة", key="adv_show_empty")
    
    if st.button("🔍 بدء البحث", key="adv_search_button", type="primary"):
        all_results = []
        
        # تحديد الشيتات للبحث
        if search_card:
            # البحث في ماكينة محددة
            services_sheet = f"Card{search_card}_Services"
            events_sheet = f"Card{search_card}_Events"
            old_sheet = f"Card{search_card}"
            
            sheets_to_search = []
            if services_sheet in all_sheets:
                sheets_to_search.append((services_sheet, "services"))
            if events_sheet in all_sheets:
                sheets_to_search.append((events_sheet, "events"))
            elif old_sheet in all_sheets:
                sheets_to_search.append((old_sheet, "mixed"))
        else:
            # البحث في جميع الشيتات
            sheets_to_search = []
            for sheet_name in all_sheets.keys():
                if sheet_name == "ServicePlan":
                    continue
                if sheet_name.endswith("_Services"):
                    sheets_to_search.append((sheet_name, "services"))
                elif sheet_name.endswith("_Events"):
                    sheets_to_search.append((sheet_name, "events"))
                elif sheet_name.startswith("Card"):
                    sheets_to_search.append((sheet_name, "mixed"))
        
        for sheet_name, sheet_type in sheets_to_search:
            df = all_sheets[sheet_name]
            card_num = sheet_name.replace("Card", "").replace("_Services", "").replace("_Events", "")
            
            # البحث حسب النوع
            if search_type == "الخدمات" and sheet_type not in ["services", "mixed"]:
                continue
            elif search_type == "الأحداث" and sheet_type not in ["events", "mixed"]:
                continue
            
            # البحث في كل صف
            for idx, row in df.iterrows():
                # تطبيق شروط البحث
                if not matches_search_criteria(row, search_text, search_technician, 
                                              search_date, specific_service, exact_match, 
                                              show_empty, sheet_type):
                    continue
                
                # استخراج النتائج حسب نوع الشيت
                if sheet_type == "services" or (sheet_type == "mixed" and has_services_data(row)):
                    service_results = extract_service_results(row, card_num, specific_service)
                    if service_results:
                        all_results.extend(service_results)
                
                if sheet_type == "events" or (sheet_type == "mixed" and has_events_data(row)):
                    event_results = extract_event_results(row, card_num)
                    if event_results:
                        all_results.extend(event_results)
        
        if all_results:
            results_df = pd.DataFrame(all_results)
            
            # إزالة التكرارات
            results_df = results_df.drop_duplicates()
            
            # ترتيب النتائج
            if "Date" in results_df.columns:
                results_df = results_df.sort_values(by=["Card", "Date"], ascending=[True, False])
            
            st.markdown("### 📋 نتائج البحث")
            st.dataframe(results_df, use_container_width=True, height=400)
            
            # إحصائيات البحث
            st.markdown("### 📊 إحصائيات البحث")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("عدد النتائج", len(results_df))
            
            with col2:
                if "Card" in results_df.columns:
                    unique_cards = results_df["Card"].nunique()
                    st.metric("عدد الماكينات", unique_cards)
                else:
                    st.metric("عدد الماكينات", 0)
            
            with col3:
                if "Servised by" in results_df.columns:
                    unique_techs = results_df["Servised by"][results_df["Servised by"] != "-"].nunique()
                    st.metric("عدد الفنيين", unique_techs)
                else:
                    st.metric("عدد الفنيين", 0)
            
            with col4:
                if "Type" in results_df.columns:
                    service_count = len(results_df[results_df["Type"] == "Service"])
                    event_count = len(results_df[results_df["Type"] == "Event"])
                    st.metric("الخدمات / الأحداث", f"{service_count} / {event_count}")
            
            # تنزيل النتائج
            buffer = io.BytesIO()
            results_df.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(
                label="💾 حفظ نتائج البحث",
                data=buffer.getvalue(),
                file_name="Advanced_Search_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("ℹ️ لم يتم العثور على نتائج مطابقة لمعايير البحث.")

def matches_search_criteria(row, search_text, search_technician, search_date, 
                           specific_service, exact_match, show_empty, sheet_type):
    """التحقق من تطابق الصف مع معايير البحث"""
    # التحقق من النص
    if search_text and not text_matches_row(row, search_text, exact_match):
        return False
    
    # التحقق من فني الخدمة
    if search_technician:
        tech_value = get_servised_by_value(row)
        if not tech_value or search_technician.lower() not in tech_value.lower():
            return False
    
    # التحقق من التاريخ
    if search_date:
        date_match = False
        for col in row.index:
            if "date" in normalize_name(col) and pd.notna(row[col]):
                if search_date.lower() in str(row[col]).lower():
                    date_match = True
                    break
        if not date_match:
            return False
    
    # التحقق من الخدمة المحددة
    if specific_service != "الكل" and sheet_type in ["services", "mixed"]:
        service_match = False
        for col in row.index:
            col_normalized = normalize_name(col)
            if specific_service.lower() in col_normalized:
                val = str(row[col]).strip()
                if val and val.lower() not in ["nan", "none", "", "0"]:
                    service_match = True
                    break
        if not service_match:
            return False
    
    # التحقق من البيانات الفارغة
    if not show_empty and is_empty_row(row, sheet_type):
        return False
    
    return True

def text_matches_row(row, search_text, exact_match):
    """التحقق إذا كان النص موجود في أي عمود"""
    for col in row.index:
        cell_value = str(row[col]).strip()
        if not cell_value or cell_value.lower() in ["nan", "none", ""]:
            continue
        
        if exact_match:
            if search_text.lower() == cell_value.lower():
                return True
        else:
            if search_text.lower() in cell_value.lower():
                return True
    
    return False

def is_empty_row(row, sheet_type):
    """التحقق إذا كان الصف فارغ"""
    for col in row.index:
        val = str(row[col]).strip()
        if val and val.lower() not in ["nan", "none", ""]:
            return False
    return True

def has_services_data(row):
    """التحقق إذا كان الصف يحتوي على بيانات خدمات"""
    return pd.notna(row.get("Min_Tones")) and pd.notna(row.get("Max_Tones"))

def has_events_data(row):
    """التحقق إذا كان الصف يحتوي على بيانات أحداث"""
    event_columns = [col for col in row.index if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
    correction_columns = [col for col in row.index if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
    
    for col in event_columns + correction_columns:
        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
            return True
    
    return False

def extract_service_results(row, card_num, specific_service):
    """استخراج نتائج الخدمات"""
    results = []
    
    metadata_columns = {
        "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
        "Other", "Servised by", "Event", "Correction",
        "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
        "OTHER", "EVENT", "CORRECTION", "SERVISED BY",
        "servised by", "Servised By", 
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    }
    
    all_columns = set(row.index)
    service_columns = all_columns - metadata_columns
    
    for col in service_columns:
        val = str(row.get(col, "")).strip()
        
        # تخطي الخلايا الفارغة
        if not val or val.lower() in ["nan", "none", "", "null", "0"]:
            continue
        
        # فلترة حسب الخدمة المحددة
        if specific_service != "الكل":
            col_normalized = normalize_name(col)
            if specific_service.lower() not in col_normalized:
                continue
        
        servised_by_value = get_servised_by_value(row)
        
        results.append({
            "Card": card_num,
            "Service Type": col,
            "Service Status": val,
            "Servised by": servised_by_value,
            "Date": row.get("Date", "-"),
            "Tones": row.get("Tones", "-"),
            "Min_Tones": row.get("Min_Tones", "-"),
            "Max_Tones": row.get("Max_Tones", "-"),
            "Type": "Service"
        })
    
    return results

def extract_event_results(row, card_num):
    """استخراج نتائج الأحداث"""
    results = []
    
    event_columns = [col for col in row.index if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
    correction_columns = [col for col in row.index if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
    
    has_event = any(pd.notna(row.get(col, "")) and str(row.get(col, "")).strip() != "" for col in event_columns)
    has_correction = any(pd.notna(row.get(col, "")) and str(row.get(col, "")).strip() != "" for col in correction_columns)
    
    if not has_event and not has_correction:
        return results
    
    # استخراج أحداث متعددة
    event_values = []
    for col in event_columns:
        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
            event_values.append(str(row[col]).strip())
    
    correction_values = []
    for col in correction_columns:
        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
            correction_values.append(str(row[col]).strip())
    
    servised_by_value = get_servised_by_value(row)
    
    event_text = "، ".join(event_values) if event_values else "-"
    correction_text = "، ".join(correction_values) if correction_values else "-"
    
    results.append({
        "Card": card_num,
        "Date": row.get("Date", "-"),
        "Event": event_text,
        "Correction": correction_text,
        "Servised by": servised_by_value,
        "Tones": row.get("Tones", "-"),
        "Type": "Event"
    })
    
    return results

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد
# -------------------------------
def add_new_event(sheets_edit):
    """إضافة إيفينت جديد"""
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
        
        new_row = {}
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
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

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن
# -------------------------------
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
    st.dataframe(display_df, use_container_width=True)
    
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
    
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

# تحميل الشيتات (عرض وتحليل)
all_sheets = load_all_sheets()

# تحميل الشيتات للتحرير (dtype=object)
sheets_edit = load_sheets_for_edit()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# التحقق من الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# تحديد التبويبات
if permissions["can_manage_users"]:  # admin
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم", "🛠 تعديل وإدارة البيانات"])
else:  # viewer
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم"])

# -------------------------------
# Tab: فحص السيرفيس
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
# Tab: فحص الإيفينت والكوريكشن
# -------------------------------
with tabs[1]:
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        card_num_events = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_events")

        if st.button("عرض الأحداث والتصحيحات", key="show_events"):
            st.session_state["show_events_results"] = True

        if st.session_state.get("show_events_results", False):
            check_events_and_corrections(card_num_events, all_sheets)

# -------------------------------
# Tab: بحث متقدم
# -------------------------------
with tabs[2]:
    advanced_search(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 3:
    with tabs[3]:
        st.header("🛠 تعديل وإدارة البيانات")

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

            with tab4:
                add_new_event(sheets_edit)

            with tab5:
                edit_events_and_corrections(sheets_edit)
