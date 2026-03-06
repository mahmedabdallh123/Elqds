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
import uuid

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
    "APP_TITLE": "CMMS - نظام إدارة الصيانة الشامل",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l6.xlsx",
    "LOCAL_FILE": "l6.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "📊 تحليلات متقدمة"],
    
    # إعدادات الصور
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    
    # إعدادات الأعمدة الافتراضية
    "DEFAULT_COLUMNS": [
        "card", "Date", "Event", "Correction", "Servised by", "Tones", "Images"
    ],
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"
GITHUB_USERS_URL = "https://raw.githubusercontent.com/mahmedabdallh123/Elqds/refs/heads/main/users.json"
GITHUB_REPO_USERS = "mahmedabdallh123/Elqds"

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    """إنشاء وإعداد مجلد الصور"""
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        # إنشاء ملف .gitkeep لجعل المجلد فارغاً في GitHub
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def save_uploaded_images(uploaded_files):
    """حفظ الصور المرفوعة وإرجاع أسماء الملفات"""
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        # التحقق من نوع الملف
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن نوعه غير مدعوم")
            continue
        
        # التحقق من حجم الملف
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن حجمه ({file_size_mb:.2f}MB) يتجاوز الحد المسموح ({APP_CONFIG['MAX_IMAGE_SIZE_MB']}MB)")
            continue
        
        # إنشاء اسم فريد للملف
        unique_id = str(uuid.uuid4())[:8]
        original_name = uploaded_file.name.split('.')[0]
        safe_name = re.sub(r'[^\w\-_]', '_', original_name)
        new_filename = f"{safe_name}_{unique_id}.{file_extension}"
        
        # حفظ الملف
        file_path = os.path.join(IMAGES_FOLDER, new_filename)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        saved_files.append(new_filename)
    
    return saved_files

def delete_image_file(image_filename):
    """حذف ملف صورة"""
    try:
        file_path = os.path.join(IMAGES_FOLDER, image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        st.error(f"❌ خطأ في حذف الصورة {image_filename}: {e}")
    return False

def get_image_url(image_filename):
    """الحصول على رابط الصورة للعرض"""
    if not image_filename:
        return None
    
    file_path = os.path.join(IMAGES_FOLDER, image_filename)
    if os.path.exists(file_path):
        return file_path
    return None

def display_images(image_filenames, caption="الصور المرفقة"):
    """عرض الصور في واجهة المستخدم"""
    if not image_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    
    # تقسيم الصور إلى أعمدة
    images_per_row = 3
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    
    for i in range(0, len(images), images_per_row):
        cols = st.columns(images_per_row)
        for j in range(images_per_row):
            idx = i + j
            if idx < len(images):
                image_filename = images[idx].strip()
                with cols[j]:
                    image_path = get_image_url(image_filename)
                    if image_path and os.path.exists(image_path):
                        try:
                            st.image(image_path, caption=image_filename, use_column_width=True)
                        except:
                            st.write(f"📷 {image_filename}")
                    else:
                        st.write(f"📷 {image_filename} (غير موجود)")

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def download_users_from_github():
    """تحميل ملف المستخدمين من GitHub"""
    try:
        response = requests.get(GITHUB_USERS_URL, timeout=10)
        response.raise_for_status()
        users_data = response.json()
        
        # حفظ نسخة محلية
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل ملف المستخدمين من GitHub: {e}")
        
        # محاولة استخدام النسخة المحلية إذا كانت موجودة
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    users_data = json.load(f)
                return users_data
            except:
                pass
        
        # إرجاع بيانات افتراضية
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
        }

def upload_users_to_github(users_data):
    """رفع ملف المستخدمين إلى GitHub"""
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.error("❌ لم يتم العثور على GitHub token")
            return False
        
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO_USERS)
        
        # تحويل البيانات إلى JSON
        users_json = json.dumps(users_data, indent=4, ensure_ascii=False, sort_keys=True)
        
        # محاولة تحديث الملف إذا كان موجوداً
        try:
            contents = repo.get_contents("users.json", ref="main")
            result = repo.update_file(
                path="users.json",
                message=f"تحديث ملف المستخدمين بواسطة {st.session_state.get('username', 'admin')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                content=users_json,
                sha=contents.sha,
                branch="main"
            )
            return True
        except Exception as e:
            # إذا كان الخطأ أن الملف غير موجود (404) أو SHA غير موجود
            error_msg = str(e)
            if "404" in error_msg or "sha" in error_msg.lower() or "not found" in error_msg.lower():
                # إنشاء ملف جديد إذا لم يكن موجوداً
                try:
                    result = repo.create_file(
                        path="users.json",
                        message=f"إنشاء ملف المستخدمين بواسطة {st.session_state.get('username', 'admin')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        content=users_json,
                        branch="main"
                    )
                    return True
                except Exception as create_error:
                    st.error(f"❌ خطأ في إنشاء ملف المستخدمين على GitHub: {create_error}")
                    return False
            else:
                st.error(f"❌ خطأ في تحديث ملف المستخدمين على GitHub: {e}")
                return False
                
    except Exception as e:
        st.error(f"❌ خطأ في رفع ملف المستخدمين إلى GitHub: {e}")
        return False

def load_users():
    """تحميل بيانات المستخدمين من GitHub"""
    try:
        # أولاً: تحميل من GitHub
        users_data = download_users_from_github()
        
        # التحقق من وجود المستخدم admin
        if "admin" not in users_data:
            users_data["admin"] = {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
            # حفظ التحديث في GitHub
            upload_users_to_github(users_data)
        
        # التأكد من وجود جميع الحقول لكل مستخدم
        for username, user_data in users_data.items():
            required_fields = ["password", "role", "created_at", "permissions", "active"]
            for field in required_fields:
                if field not in user_data:
                    if field == "password" and username == "admin":
                        user_data[field] = "admin123"
                    elif field == "role" and username == "admin":
                        user_data[field] = "admin"
                    elif field == "role":
                        user_data[field] = "viewer"
                    elif field == "permissions" and username == "admin":
                        user_data[field] = ["all"]
                    elif field == "permissions" and user_data.get("role") == "editor":
                        user_data[field] = ["view", "edit"]
                    elif field == "permissions":
                        user_data[field] = ["view"]
                    elif field == "created_at":
                        user_data[field] = datetime.now().isoformat()
                    elif field == "active":
                        user_data[field] = False
        
        # حفظ أي تحديثات في GitHub
        upload_users_to_github(users_data)
        
        return users_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل بيانات المستخدمين: {e}")
        # إرجاع المستخدم الافتراضي في حالة الخطأ
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "active": False
            }
        }

def save_users_to_github(users_data):
    """حفظ بيانات المستخدمين إلى GitHub"""
    return upload_users_to_github(users_data)

def update_user_in_github(username, user_data):
    """تحديث بيانات مستخدم محدد في GitHub"""
    try:
        users = load_users()
        users[username] = user_data
        return save_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في تحديث المستخدم {username}: {e}")
        return False

def add_user_to_github(username, user_data):
    """إضافة مستخدم جديد إلى GitHub"""
    try:
        users = load_users()
        if username in users:
            st.warning(f"⚠ المستخدم '{username}' موجود بالفعل")
            return False
        users[username] = user_data
        return save_users_to_github(users)
    except Exception as e:
        st.error(f"❌ خطأ في إضافة المستخدم {username}: {e}")
        return False

def delete_user_from_github(username):
    """حذف مستخدم من GitHub"""
    try:
        users = load_users()
        if username in users:
            del users[username]
            return save_users_to_github(users)
        return False
    except Exception as e:
        st.error(f"❌ خطأ في حذف المستخدم {username}: {e}")
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

    # تحميل قائمة المستخدمين من GitHub
    try:
        user_list = list(users.keys())
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
            # تحميل المستخدمين من GitHub
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
# 📂 تحميل الشيتات (مخبأ) - معدل لقراءة جميع الشيتات بشكل ديناميكي
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel بشكل ديناميكي"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            if df.empty:
                continue
            df.columns = df.columns.astype(str).str.strip()
            # تعبئة القيم NaN لتجنب الأخطاء
            df = df.fillna('')
            sheets[name] = df
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الشيتات: {e}")
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
            # تعبئة القيم NaN
            df = df.fillna('')
            sheets[name] = df
        
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الشيتات للتحرير: {e}")
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
            # إذا كان الملف غير موجود أو هناك مشكلة في SHA
            error_msg = str(e)
            if "404" in error_msg or "sha" in error_msg.lower():
                try:
                    # حاول إنشاء ملف جديد
                    result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                    st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                    return load_sheets_for_edit()
                except Exception as create_error:
                    st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                    return None
            else:
                st.error(f"❌ فشل الرفع إلى GitHub: {e}")
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
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;",
        "Images": "background-color: #d6eaf8; color:#1b4f72; font-weight:bold;"
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
            "can_manage_sheets": True
        }
    
    # إذا كان الدور editor
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False,
            "can_manage_sheets": True
        }
    
    # إذا كان الدور viewer أو أي دور آخر
    else:
        # التحقق من الصلاحيات الفردية
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions,
            "can_manage_sheets": "manage_sheets" in user_permissions or "all" in user_permissions
        }

# ===============================
# 🔧 دوال استخراج البيانات الديناميكية
# ===============================
def extract_sheet_data(df, sheet_name):
    """استخراج البيانات من أي شيت بشكل ديناميكي"""
    if df.empty:
        return []
    
    results = []
    
    # تحديد أسماء الأعمدة الهامة
    card_column = None
    date_column = None
    event_column = None
    correction_column = None
    tech_column = None
    images_column = None
    tones_column = None
    
    # البحث عن الأعمدة المختلفة
    for col in df.columns:
        col_lower = str(col).lower().strip()
        
        # البحث عن عمود رقم الماكينة
        if card_column is None and any(keyword in col_lower for keyword in ['card', 'machine', 'رقم', 'ماكينة', 'جهاز']):
            card_column = col
        
        # البحث عن عمود التاريخ
        elif date_column is None and any(keyword in col_lower for keyword in ['date', 'تاريخ', 'time']):
            date_column = col
        
        # البحث عن عمود الحدث
        elif event_column is None and any(keyword in col_lower for keyword in ['event', 'حدث', 'issue', 'مشكلة']):
            event_column = col
        
        # البحث عن عمود التصحيح
        elif correction_column is None and any(keyword in col_lower for keyword in ['correction', 'تصحيح', 'solution', 'حل']):
            correction_column = col
        
        # البحث عن عمود الفني
        elif tech_column is None and any(keyword in col_lower for keyword in ['servised', 'serviced', 'service', 'technician', 'فني', 'خدم', 'تم بواسطة']):
            tech_column = col
        
        # البحث عن عمود الصور
        elif images_column is None and any(keyword in col_lower for keyword in ['images', 'pictures', 'صور', 'مرفقات']):
            images_column = col
        
        # البحث عن عمود الأطنان
        elif tones_column is None and any(keyword in col_lower for keyword in ['tones', 'طن', 'أطنان', 'ton', 'tone']):
            tones_column = col
    
    # إذا لم يتم العثور على أعمدة معينة، نستخدم الأعمدة الأولى المتاحة
    if not card_column and len(df.columns) > 0:
        card_column = df.columns[0]
    
    # استخراج البيانات من كل صف
    for idx, row in df.iterrows():
        try:
            result = {
                "Sheet Name": sheet_name,
                "Row Index": idx,
                "Card Number": str(row[card_column]) if card_column and card_column in row and pd.notna(row[card_column]) else sheet_name,
                "Date": str(row[date_column]) if date_column and date_column in row and pd.notna(row[date_column]) else "-",
                "Event": str(row[event_column]) if event_column and event_column in row and pd.notna(row[event_column]) else "-",
                "Correction": str(row[correction_column]) if correction_column and correction_column in row and pd.notna(row[correction_column]) else "-",
                "Servised by": str(row[tech_column]) if tech_column and tech_column in row and pd.notna(row[tech_column]) else "-",
                "Tones": str(row[tones_column]) if tones_column and tones_column in row and pd.notna(row[tones_column]) else "-",
                "Images": str(row[images_column]) if images_column and images_column in row and pd.notna(row[images_column]) else ""
            }
            
            # إضافة الصف إذا كان يحتوي على بيانات
            if result["Event"] != "-" or result["Correction"] != "-" or result["Date"] != "-":
                results.append(result)
        except Exception as e:
            # تجاهل الصفوف التي بها أخطاء
            continue
    
    return results

def check_dynamic_row_criteria(result, target_techs, target_dates, 
                              search_terms, search_params):
    """التحقق من مطابقة النتيجة لمعايير البحث"""
    
    # 1. التحقق من فني الخدمة
    if target_techs:
        row_tech = result.get("Servised by", "").lower()
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
        row_date = str(result.get("Date", "")).lower()
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
        row_event = result.get("Event", "").lower()
        row_correction = result.get("Correction", "").lower()
        
        if not row_event and not row_correction and not search_params["include_empty"]:
            return False
        
        text_match = False
        combined_text = f"{row_event} {row_correction}"
        
        for term in search_terms:
            if search_params["exact_match"]:
                if term == row_event or term == row_correction:
                    text_match = True
                    break
            else:
                if term in combined_text:
                    text_match = True
                    break
        
        if not text_match:
            return False
    
    return True

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

def calculate_durations_between_events(events_data, duration_type="أيام", group_by_type=False):
    """حساب المدة بين الأحداث لنفس الماكينة"""
    if not events_data:
        return events_data
    
    # تحويل إلى DataFrame
    df = pd.DataFrame(events_data)
    
    # تحويل التواريخ إلى تنسيق datetime
    def parse_date(date_str):
        try:
            # محاولة تحليل تنسيقات مختلفة
            date_str = str(date_str).strip()
            if not date_str or date_str.lower() in ["nan", "none", "-", ""]:
                return None
            
            # تجربة تنسيقات مختلفة
            formats = [
                "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
                "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            
            # إذا فشلت جميع المحاولات
            return None
        except:
            return None
    
    df['Date_Parsed'] = df['Date'].apply(parse_date)
    
    # فرز البيانات حسب الماكينة ثم التاريخ
    df = df.sort_values(['Card Number', 'Date_Parsed'])
    
    # إضافة أعمدة المدة
    df['Previous_Date'] = None
    df['Duration'] = None
    df['Duration_Unit'] = None
    df['Event_Type'] = None
    
    # تحديد نوع الحدث (حدث أو تصحيح)
    def determine_event_type(event, correction):
        event_str = str(event).strip().lower()
        correction_str = str(correction).strip().lower()
        
        if event_str not in ['-', 'nan', 'none', ''] and correction_str not in ['-', 'nan', 'none', '']:
            return "تصحيح"
        elif event_str not in ['-', 'nan', 'none', '']:
            return "حدث"
        elif correction_str not in ['-', 'nan', 'none', '']:
            return "تصحيح"
        else:
            return "غير محدد"
    
    df['Event_Type'] = df.apply(lambda row: determine_event_type(row.get('Event', '-'), row.get('Correction', '-')), axis=1)
    
    # حساب المدة بين الأحداث لكل ماكينة
    durations_data = []
    
    for card_num in df['Card Number'].unique():
        card_events = df[df['Card Number'] == card_num].copy()
        
        if len(card_events) > 1:
            for i in range(1, len(card_events)):
                current_event = card_events.iloc[i]
                previous_event = card_events.iloc[i-1]
                
                current_date = current_event['Date_Parsed']
                previous_date = previous_event['Date_Parsed']
                
                if current_date and previous_date:
                    # حساب المدة بالأيام
                    duration_days = (current_date - previous_date).days
                    
                    # تحويل إلى الوحدة المطلوبة
                    if duration_type == "أسابيع":
                        duration_value = duration_days / 7
                        duration_unit = "أسبوع"
                    elif duration_type == "أشهر":
                        duration_value = duration_days / 30.44  # متوسط أيام الشهر
                        duration_unit = "شهر"
                    else:  # أيام
                        duration_value = duration_days
                        duration_unit = "يوم"
                    
                    # التحقق من تجميع حسب النوع
                    if group_by_type:
                        current_type = current_event['Event_Type']
                        previous_type = previous_event['Event_Type']
                        
                        if current_type == previous_type:
                            duration_info = {
                                'Card Number': card_num,
                                'Current_Event_Date': current_event['Date'],
                                'Previous_Event_Date': previous_event['Date'],
                                'Duration': round(duration_value, 1),
                                'Duration_Unit': duration_unit,
                                'Event_Type': current_type,
                                'Current_Event': current_event.get('Event', '-'),
                                'Previous_Event': previous_event.get('Event', '-'),
                                'Current_Correction': current_event.get('Correction', '-'),
                                'Previous_Correction': previous_event.get('Correction', '-'),
                                'Technician': current_event.get('Servised by', '-')
                            }
                            durations_data.append(duration_info)
                    else:
                        duration_info = {
                            'Card Number': card_num,
                            'Current_Event_Date': current_event['Date'],
                            'Previous_Event_Date': previous_event['Date'],
                            'Duration': round(duration_value, 1),
                            'Duration_Unit': duration_unit,
                            'Event_Type': f"{previous_event['Event_Type']} → {current_event['Event_Type']}",
                            'Current_Event': current_event.get('Event', '-'),
                            'Previous_Event': previous_event.get('Event', '-'),
                            'Current_Correction': current_event.get('Correction', '-'),
                            'Previous_Correction': previous_event.get('Correction', '-'),
                            'Technician': current_event.get('Servised by', '-')
                        }
                        durations_data.append(duration_info)
    
    return durations_data

# ===============================
# 🖥 دالة فحص الإيفينت والكوريكشن - ديناميكية
# ===============================
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن مع خاصية حساب المدة بين الأحداث"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تهيئة session state
    if "search_params" not in st.session_state:
        st.session_state.search_params = {
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "sort_by": "الشيت",
            "calculate_duration": False,
            "duration_type": "أيام",
            "duration_filter_min": 0,
            "duration_filter_max": 365,
            "group_by_type": False,
            "show_images": True
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    # قسم البحث - مع إضافة خيارات حساب المدة
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك ملء واحد أو أكثر من الحقول.")
        
        # تبويبات للبحث وخيارات المدة
        main_tabs = st.tabs(["🔍 معايير البحث", "⏱️ خيارات المدة", "📊 تحليل زمني"])
        
        with main_tabs[0]:
            col1, col2 = st.columns(2)
            
            with col1:
                # قسم أرقام الماكينات
                with st.expander("🔢 **أرقام الماكينات/الشيتات**", expanded=True):
                    st.caption("أدخل أرقام الماكينات أو أسماء الشيتات (مفصولة بفواصل)")
                    card_numbers = st.text_input(
                        "مثال: 1,3,5 أو Card1,Card3 أو Machine,Service",
                        value=st.session_state.search_params.get("card_numbers", ""),
                        key="input_cards",
                        placeholder="اتركه فارغاً للبحث في كل الشيتات"
                    )
                    
                    # أزرار سريعة لأرقام الماكينات
                    st.caption("أو اختر من:")
                    quick_cards_col1, quick_cards_col2, quick_cards_col3 = st.columns(3)
                    with quick_cards_col1:
                        if st.button("🔟 شيتات Card", key="quick_cards"):
                            st.session_state.search_params["card_numbers"] = "Card"
                            st.session_state.search_triggered = True
                            st.rerun()
                    with quick_cards_col2:
                        if st.button("📋 كل الشيتات", key="quick_all"):
                            st.session_state.search_params["card_numbers"] = ""
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
                        ["الشيت", "التاريخ", "فني الخدمة", "مدة الحدث"],
                        index=["الشيت", "التاريخ", "فني الخدمة", "مدة الحدث"].index(
                            st.session_state.search_params.get("sort_by", "الشيت")
                        ),
                        key="select_sort_by"
                    )
        
        with main_tabs[1]:
            st.markdown("#### ⏱️ خيارات حساب المدة بين الأحداث")
            
            col_dur1, col_dur2 = st.columns(2)
            
            with col_dur1:
                calculate_duration = st.checkbox(
                    "📅 حساب المدة بين الأحداث",
                    value=st.session_state.search_params.get("calculate_duration", False),
                    key="checkbox_calculate_duration",
                    help="حساب المدة بين الأحداث لنفس الماكينة"
                )
                
                if calculate_duration:
                    duration_type = st.selectbox(
                        "وحدة حساب المدة:",
                        ["أيام", "أسابيع", "أشهر"],
                        index=["أيام", "أسابيع", "أشهر"].index(
                            st.session_state.search_params.get("duration_type", "أيام")
                        ),
                        key="select_duration_type"
                    )
                    
                    group_by_type = st.checkbox(
                        "📊 تجميع حسب نوع الحدث",
                        value=st.session_state.search_params.get("group_by_type", False),
                        key="checkbox_group_by_type",
                        help="فصل حساب المدة حسب نوع الحدث (حدث/تصحيح)"
                    )
            
            with col_dur2:
                if calculate_duration:
                    st.markdown("#### 🔍 فلترة حسب المدة")
                    
                    duration_filter_min = st.number_input(
                        "الحد الأدنى للمدة:",
                        min_value=0,
                        value=st.session_state.search_params.get("duration_filter_min", 0),
                        step=1,
                        key="input_duration_min"
                    )
                    
                    duration_filter_max = st.number_input(
                        "الحد الأقصى للمدة:",
                        min_value=duration_filter_min,
                        value=st.session_state.search_params.get("duration_filter_max", 365),
                        step=1,
                        key="input_duration_max"
                    )
                    
                    st.caption(f"سيتم عرض الأحداث التي تتراوح مدتها بين {duration_filter_min} و {duration_filter_max} {duration_type}")
        
        with main_tabs[2]:
            st.markdown("#### 📊 تحليل زمني متقدم")
            
            analysis_options = st.multiselect(
                "اختر نوع التحليل:",
                ["معدل تكرار الأحداث", "مقارنة المدة حسب الفني", "توزيع الأحداث زمنياً", "مقارنة بين الحدث والتصحيح"],
                default=[],
                key="select_analysis_options"
            )
            
            if "معدل تكرار الأحداث" in analysis_options:
                st.info("📈 سيتم حساب متوسط المدة بين الأحداث لكل ماكينة")
            
            if "مقارنة المدة حسب الفني" in analysis_options:
                st.info("👨‍🔧 سيتم مقارنة متوسط المدة التي يستغرقها كل فني")
            
            if "توزيع الأحداث زمنياً" in analysis_options:
                st.info("📅 سيتم تحليل توزيع الأحداث على مدار السنة")
            
            if "مقارنة بين الحدث والتصحيح" in analysis_options:
                st.info("⚖️ سيتم مقارنة المدة بين الأحداث العادية والتصحيحات")
        
        # تحديث معايير البحث
        st.session_state.search_params.update({
            "card_numbers": card_numbers,
            "date_range": date_input,
            "tech_names": tech_names,
            "search_text": search_text,
            "exact_match": search_mode == "مطابقة كاملة",
            "include_empty": include_empty,
            "sort_by": sort_by,
            "calculate_duration": calculate_duration,
            "duration_type": duration_type if calculate_duration else "أيام",
            "duration_filter_min": duration_filter_min if calculate_duration else 0,
            "duration_filter_max": duration_filter_max if calculate_duration else 365,
            "group_by_type": group_by_type if calculate_duration else False,
            "analysis_options": analysis_options,
            "show_images": True
        })
        
        # زر البحث الرئيسي
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        with col_btn1:
            search_clicked = st.button(
                "🔍 **بدء البحث والتحليل**",
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
                    "sort_by": "الشيت",
                    "calculate_duration": False,
                    "duration_type": "أيام",
                    "duration_filter_min": 0,
                    "duration_filter_max": 365,
                    "group_by_type": False,
                    "analysis_options": [],
                    "show_images": True
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
                    "sort_by": "الشيت",
                    "calculate_duration": True,
                    "duration_type": "أيام",
                    "duration_filter_min": 0,
                    "duration_filter_max": 365,
                    "group_by_type": True,
                    "analysis_options": ["معدل تكرار الأحداث", "توزيع الأحداث زمنياً"],
                    "show_images": True
                }
                st.session_state.search_triggered = True
                st.rerun()
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        # جمع معايير البحث
        search_params = st.session_state.search_params.copy()
        
        # عرض معايير البحث
        show_search_params(search_params)
        
        # تنفيذ البحث
        show_advanced_search_results_with_duration(search_params, all_sheets)

def show_search_params(search_params):
    """عرض معايير البحث المستخدمة"""
    with st.container():
        st.markdown("### ⚙ معايير البحث المستخدمة")
        
        params_display = []
        if search_params["card_numbers"]:
            params_display.append(f"**🔢 أرقام الماكينات/الشيتات:** {search_params['card_numbers']}")
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

def show_advanced_search_results_with_duration(search_params, all_sheets):
    """عرض نتائج البحث مع حساب المدة"""
    st.markdown("### 📊 نتائج البحث")
    
    # شريط التقدم
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # البحث في البيانات
    all_results = []
    total_sheets = len(all_sheets)
    processed_sheets = 0
    
    # معالجة أرقام الماكينات/الشيتات المطلوبة
    target_sheets = []
    if search_params["card_numbers"]:
        target_text = search_params["card_numbers"].lower()
        target_sheets = [sheet_name for sheet_name in all_sheets.keys() if target_text in sheet_name.lower()]
    
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
    for sheet_name, df in all_sheets.items():
        # التحقق من اسم الشيت إذا كان هناك تحديد
        if target_sheets and sheet_name not in target_sheets:
            continue
        
        processed_sheets += 1
        if total_sheets > 0:
            progress_bar.progress(processed_sheets / total_sheets)
        
        status_text.text(f"🔍 جاري معالجة الشيت: {sheet_name}...")
        
        # استخراج البيانات من الشيت
        sheet_results = extract_sheet_data(df, sheet_name)
        
        # فلترة النتائج حسب معايير البحث
        for result in sheet_results:
            # تطبيق معايير البحث
            if not check_dynamic_row_criteria(result, target_techs, target_dates, 
                                             search_terms, search_params):
                continue
            
            # إضافة النتائج المطابقة
            all_results.append(result)
    
    # إخفاء شريط التقدم
    progress_bar.empty()
    status_text.empty()
    
    # عرض النتائج مع حساب المدة
    if all_results:
        display_search_results_with_duration(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def display_search_results_with_duration(results, search_params):
    """عرض نتائج البحث مع خاصية حساب المدة"""
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
    
    # محاولة تحويل رقم الماكينة إلى رقم صحيح للترتيب
    try:
        display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    except:
        display_df['Card_Number_Clean'] = display_df['Card Number']
    
    # تحويل التواريخ لترتيب زمني
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    
    # ترتيب النتائج حسب الشيت ثم التاريخ
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Sheet Name'], 
                                          ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Sheet Name', 'Date_Clean'], 
                                          ascending=[True, True, False], na_position='last')
    elif search_params["sort_by"] == "مدة الحدث":
        # سنحتاج إلى حساب المدة أولاً
        pass
    else:  # الشيت (الافتراضي)
        display_df = display_df.sort_values(by=['Sheet Name', 'Date_Clean'], 
                                          ascending=[True, False], na_position='last')
    
    # إضافة ترتيب الأحداث لكل شيت
    display_df['Event_Order'] = display_df.groupby('Sheet Name').cumcount() + 1
    display_df['Total_Events'] = display_df.groupby('Sheet Name')['Sheet Name'].transform('count')
    
    # عرض الإحصائيات
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    
    with col2:
        unique_sheets = display_df["Sheet Name"].nunique()
        st.metric("📂 عدد الشيتات", unique_sheets)
    
    with col3:
        # عدد الشيتات التي لديها أكثر من حدث
        if not display_df.empty:
            sheet_counts = display_df.groupby('Sheet Name').size()
            multi_event_sheets = (sheet_counts > 1).sum()
            st.metric("📊 شيتات متعددة الأحداث", multi_event_sheets)
        else:
            st.metric("📊 شيتات متعددة الأحداث", 0)
    
    with col4:
        # التحقق من وجود عمود الصور في display_df
        has_images_column = 'Images' in display_df.columns
        if has_images_column:
            with_images = display_df[display_df["Images"].notna() & (display_df["Images"] != "") & (display_df["Images"] != "-")].shape[0]
            st.metric("📷 تحتوي على صور", with_images)
        else:
            st.metric("📷 تحتوي على صور", 0)
    
    # حساب المدة بين الأحداث إذا كان مطلوباً
    if search_params.get("calculate_duration", False):
        st.markdown("---")
        st.markdown("### ⏱️ تحليل المدة بين الأحداث")
        
        # حساب المدة
        durations_data = calculate_durations_between_events(
            results,
            search_params.get("duration_type", "أيام"),
            search_params.get("group_by_type", False)
        )
        
        if durations_data:
            # تحويل إلى DataFrame
            durations_df = pd.DataFrame(durations_data)
            
            # فلترة حسب نطاق المدة
            duration_min = search_params.get("duration_filter_min", 0)
            duration_max = search_params.get("duration_filter_max", 365)
            
            filtered_durations = durations_df[
                (durations_df['Duration'] >= duration_min) & 
                (durations_df['Duration'] <= duration_max)
            ]
            
            # عرض إحصائيات المدة
            st.markdown("#### 📊 إحصائيات المدة")
            
            col_dur1, col_dur2, col_dur3, col_dur4 = st.columns(4)
            
            with col_dur1:
                avg_duration = filtered_durations['Duration'].mean() if not filtered_durations.empty else 0
                st.metric(f"⏳ متوسط المدة", f"{avg_duration:.1f} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur2:
                min_duration = filtered_durations['Duration'].min() if not filtered_durations.empty else 0
                st.metric(f"⚡ أقصر مدة", f"{min_duration} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur3:
                max_duration = filtered_durations['Duration'].max() if not filtered_durations.empty else 0
                st.metric(f"🐌 أطول مدة", f"{max_duration} {search_params.get('duration_type', 'أيام')}")
            
            with col_dur4:
                total_durations = len(filtered_durations)
                st.metric("🔢 عدد الفترات", total_durations)
            
            # عرض جدول المدة
            st.markdown("#### 📋 جدول المدة بين الأحداث")
            
            # تنسيق الأعمدة للعرض
            display_columns = [
                'Card Number', 'Previous_Event_Date', 'Current_Event_Date',
                'Duration', 'Duration_Unit', 'Event_Type', 'Technician'
            ]
            
            available_columns = [col for col in display_columns if col in filtered_durations.columns]
            
            st.dataframe(
                filtered_durations[available_columns],
                use_container_width=True,
                height=400
            )
            
            # تحليلات إضافية
            analysis_options = search_params.get("analysis_options", [])
            if analysis_options:
                st.markdown("---")
                st.markdown("### 📈 تحليلات متقدمة")
                
                for analysis in analysis_options:
                    if analysis == "معدل تكرار الأحداث":
                        show_event_frequency_analysis(filtered_durations, search_params.get("duration_type", "أيام"))
                    
                    elif analysis == "مقارنة المدة حسب الفني":
                        show_technician_comparison_analysis(filtered_durations)
                    
                    elif analysis == "توزيع الأحداث زمنياً":
                        show_temporal_distribution_analysis(durations_df)
                    
                    elif analysis == "مقارنة بين الحدث والتصحيح":
                        show_event_correction_comparison(filtered_durations)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لحساب المدة بين الأحداث (تحتاج إلى حدثين على الأقل لكل ماكينة)")
    
    # عرض النتائج الأصلية
    st.markdown("---")
    st.markdown("### 📋 النتائج التفصيلية")
    
    # استخدام تبويبات لعرض النتائج
    display_tabs = st.tabs(["📊 عرض جدولي", "📋 عرض تفصيلي حسب الشيت", "📷 عرض الصور"])
    
    with display_tabs[0]:
        # العرض الجدولي التقليدي
        columns_to_show = ['Sheet Name', 'Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date', 'Event_Order', 'Total_Events']
        
        # إضافة عمود الصور إذا كان موجوداً في النتائج
        has_images_in_results = any('Images' in result for result in results)
        if has_images_in_results and 'Images' not in columns_to_show:
            columns_to_show.append('Images')
        
        columns_to_show = [col for col in columns_to_show if col in display_df.columns]
        
        st.dataframe(
            display_df[columns_to_show].style.apply(style_table, axis=1),
            use_container_width=True,
            height=500
        )
    
    with display_tabs[1]:
        # عرض تفصيلي لكل شيت بشكل منفصل
        unique_sheets = sorted(display_df['Sheet Name'].unique())
        
        for sheet_name in unique_sheets:
            sheet_data = display_df[display_df['Sheet Name'] == sheet_name].copy()
            sheet_data = sheet_data.sort_values('Event_Order')
            
            with st.expander(f"📂 {sheet_name} - عدد الأحداث: {len(sheet_data)}", expanded=len(unique_sheets) <= 5):
                
                # عرض إحصائيات الشيت
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    if not sheet_data.empty and 'Date' in sheet_data.columns:
                        first_date = sheet_data['Date'].iloc[0]
                        st.metric("📅 أول حدث", first_date if first_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 أول حدث", "-")
                with col_stats2:
                    if not sheet_data.empty and 'Date' in sheet_data.columns:
                        last_date = sheet_data['Date'].iloc[-1]
                        st.metric("📅 آخر حدث", last_date if last_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 آخر حدث", "-")
                with col_stats3:
                    if not sheet_data.empty and 'Servised by' in sheet_data.columns:
                        tech_count = sheet_data['Servised by'].nunique()
                        st.metric("👨‍🔧 فنيين مختلفين", tech_count)
                    else:
                        st.metric("👨‍🔧 فنيين مختلفين", 0)
                
                # عرض أحداث الشيت
                for idx, row in sheet_data.iterrows():
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
                        
                        # عرض معلومات الصور إذا كانت موجودة
                        if 'Images' in row and row['Images'] not in ['-', '', None, 'nan']:
                            images_str = str(row['Images'])
                            if images_str.strip():
                                images_count = len(images_str.split(',')) if images_str else 0
                                st.markdown(f"**📷 عدد الصور:** {images_count}")
    
    with display_tabs[2]:
        # عرض الصور للأحداث التي تحتوي على صور
        # جمع الصور من النتائج
        events_with_images = []
        
        for result in results:
            # التحقق من وجود الصور في كل نتيجة
            if 'Images' in result and result['Images'] and result['Images'] != "-" and result['Images'] != "":
                # نسخ النتيجة وإضافة المعلومات اللازمة
                event_with_images = result.copy()
                event_with_images['has_images'] = True
                events_with_images.append(event_with_images)
        
        if events_with_images:
            st.markdown("### 📷 الصور المرفقة بالأحداث")
            
            # تحويل إلى DataFrame للعرض المنظم
            images_df = pd.DataFrame(events_with_images)
            
            for idx, row in images_df.iterrows():
                sheet_name = row.get('Sheet Name', 'غير معروف')
                card_num = row.get('Card Number', 'غير معروف')
                event_date = row.get('Date', 'غير معروف')
                event_text = row.get('Event', 'لا يوجد')
                
                with st.expander(f"📸 صور للحدث - {sheet_name} - {card_num} - {event_date}", expanded=False):
                    # عرض تفاصيل الحدث
                    col_img1, col_img2 = st.columns([2, 3])
                    
                    with col_img1:
                        st.markdown("**تفاصيل الحدث:**")
                        st.markdown(f"**الشيت:** {sheet_name}")
                        st.markdown(f"**رقم الماكينة:** {card_num}")
                        st.markdown(f"**التاريخ:** {event_date}")
                        st.markdown(f"**الحدث:** {event_text[:50]}{'...' if len(event_text) > 50 else ''}")
                        st.markdown(f"**التصحيح:** {row.get('Correction', '-')}")
                        st.markdown(f"**فني الخدمة:** {row.get('Servised by', '-')}")
                    
                    with col_img2:
                        # عرض الصور
                        images_value = row.get('Images', '')
                        if images_value:
                            display_images(images_value, "الصور المرفقة")
        else:
            st.info("ℹ️ لا توجد أحداث تحتوي على صور في نتائج البحث")
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        # تصدير Excel
        if not result_df.empty:
            buffer_excel = io.BytesIO()
            
            export_df = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_df['Sheet_Name_Clean'] = export_df['Sheet Name']
            export_df['Date_Clean_Export'] = pd.to_datetime(export_df['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_df = export_df.sort_values(by=['Sheet_Name_Clean', 'Date_Clean_Export'], 
                                             ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_df = export_df.drop(['Sheet_Name_Clean', 'Date_Clean_Export'], axis=1, errors='ignore')
            
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
            
            export_csv = result_df.copy()
            
            # إضافة أعمدة التنظيف للترتيب
            export_csv['Sheet_Name_Clean'] = export_csv['Sheet Name']
            export_csv['Date_Clean_Export'] = pd.to_datetime(export_csv['Date'], errors='coerce', dayfirst=True)
            
            # ترتيب البيانات
            export_csv = export_csv.sort_values(by=['Sheet_Name_Clean', 'Date_Clean_Export'], 
                                               ascending=[True, False], na_position='last')
            
            # إزالة الأعمدة المؤقتة
            export_csv = export_csv.drop(['Sheet_Name_Clean', 'Date_Clean_Export'], axis=1, errors='ignore')
            
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
    
    with export_col3:
        # تصدير تقرير المدة
        if search_params.get("calculate_duration", False) and 'durations_data' in locals():
            if durations_data:
                buffer_duration = io.BytesIO()
                
                duration_export_df = pd.DataFrame(durations_data)
                
                with pd.ExcelWriter(buffer_duration, engine='openpyxl') as writer:
                    duration_export_df.to_excel(writer, sheet_name='المدة_بين_الأحداث', index=False)
                    
                    # إضافة ملخص إحصائي
                    summary_data = []
                    for event_type in duration_export_df['Event_Type'].unique():
                        type_data = duration_export_df[duration_export_df['Event_Type'] == event_type]
                        summary_data.append({
                            'نوع الحدث': event_type,
                            'عدد الفترات': len(type_data),
                            f'متوسط المدة ({search_params.get("duration_type", "أيام")})': type_data['Duration'].mean(),
                            'أقل مدة': type_data['Duration'].min(),
                            'أعلى مدة': type_data['Duration'].max()
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='ملخص_إحصائي', index=False)
                
                st.download_button(
                    label="⏱️ حفظ تقرير المدة",
                    data=buffer_duration.getvalue(),
                    file_name=f"تقرير_المدة_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("⚠ لا توجد بيانات مدة للتصدير")

def show_event_frequency_analysis(durations_df, duration_unit):
    """تحليل معدل تكرار الأحداث"""
    st.markdown("#### 📈 معدل تكرار الأحداث")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات لتحليل التكرار")
        return
    
    # تجميع حسب الماكينة
    machine_stats = durations_df.groupby('Card Number').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max']
    }).round(2)
    
    machine_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة']
    machine_stats = machine_stats.reset_index()
    
    # عرض أفضل 10 ماكينات من حيث التكرار
    st.markdown("##### 🥇 أفضل 10 ماكينات من حيث تكرار الصيانة")
    top_10_frequent = machine_stats.sort_values('عدد_الفترات', ascending=False).head(10)
    st.dataframe(top_10_frequent, use_container_width=True)
    
    # عرض ماكينات بأطول مدة بين الأحداث
    st.markdown("##### 🐌 ماكينات بأطول مدة بين الأحداث")
    top_10_longest = machine_stats.sort_values('متوسط_المدة', ascending=False).head(10)
    st.dataframe(top_10_longest, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط توزيع المدة
        fig1 = px.histogram(durations_df, x='Duration', 
                           title=f'توزيع المدة بين الأحداث (بوحدة {duration_unit})',
                           labels={'Duration': f'المدة ({duration_unit})'},
                           nbins=20)
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط العلاقة بين عدد الفترات والمتوسط
        fig2 = px.scatter(machine_stats, x='عدد_الفترات', y='متوسط_المدة',
                         title='العلاقة بين عدد الفترات ومتوسط المدة',
                         hover_data=['Card Number'])
        fig2.update_layout(xaxis_title="عدد الفترات", yaxis_title=f"متوسط المدة ({duration_unit})")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_technician_comparison_analysis(durations_df):
    """مقارنة المدة حسب الفني"""
    st.markdown("#### 👨‍🔧 مقارنة أداء الفنيين")
    
    if durations_df.empty or 'Technician' not in durations_df.columns:
        st.info("ℹ️ لا توجد بيانات فنيين للمقارنة")
        return
    
    # فلترة الفنيين غير المعروفين
    filtered_df = durations_df[durations_df['Technician'] != '-'].copy()
    
    if filtered_df.empty:
        st.info("ℹ️ لا توجد بيانات كافية للمقارنة")
        return
    
    # تجميع حسب الفني
    tech_stats = filtered_df.groupby('Technician').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max'],
        'Card Number': 'nunique'
    }).round(2)
    
    tech_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة', 'عدد_الماكينات']
    tech_stats = tech_stats.reset_index()
    
    # ترتيب حسب متوسط المدة (الأسرع أولاً)
    tech_stats = tech_stats.sort_values('متوسط_المدة')
    
    st.dataframe(tech_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط شريطي لمتوسط المدة حسب الفني
        fig = px.bar(tech_stats, x='Technician', y='متوسط_المدة',
                    title='متوسط المدة بين الأحداث حسب الفني',
                    color='عدد_الماكينات',
                    hover_data=['عدد_الفترات', 'أقل_مدة', 'أعلى_مدة'])
        fig.update_layout(xaxis_title="الفني", yaxis_title="متوسط المدة")
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_temporal_distribution_analysis(durations_df):
    """تحليل التوزيع الزمني"""
    st.markdown("#### 📅 تحليل التوزيع الزمني")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات للتحليل الزمني")
        return
    
    # استخراج الشهر والسنة من التواريخ
    def extract_month_year(date_str):
        try:
            date_obj = datetime.strptime(str(date_str), "%d/%m/%Y")
            return date_obj.strftime("%Y-%m")
        except:
            return "غير معروف"
    
    durations_df['Month_Year'] = durations_df['Current_Event_Date'].apply(extract_month_year)
    
    # تجميع حسب الشهر
    monthly_stats = durations_df[durations_df['Month_Year'] != 'غير معروف'].groupby('Month_Year').agg({
        'Duration': ['count', 'mean'],
        'Card Number': 'nunique'
    }).round(2)
    
    monthly_stats.columns = ['عدد_الأحداث', 'متوسط_المدة', 'عدد_الماكينات']
    monthly_stats = monthly_stats.reset_index()
    
    if monthly_stats.empty:
        st.info("ℹ️ لا توجد بيانات تاريخية صالحة")
        return
    
    st.dataframe(monthly_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط خطي لتطور عدد الأحداث مع الوقت
        fig1 = px.line(monthly_stats, x='Month_Year', y='عدد_الأحداث',
                      title='تطور عدد الأحداث الشهري',
                      markers=True)
        fig1.update_layout(xaxis_title="الشهر", yaxis_title="عدد الأحداث")
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط خطي لمتوسط المدة مع الوقت
        fig2 = px.line(monthly_stats, x='Month_Year', y='متوسط_المدة',
                      title='تطور متوسط المدة بين الأحداث',
                      markers=True)
        fig2.update_layout(xaxis_title="الشهر", yaxis_title="متوسط المدة")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

def show_event_correction_comparison(durations_df):
    """مقارنة بين الحدث العادي والتصحيح"""
    st.markdown("#### ⚖️ مقارنة بين الحدث والتصحيح")
    
    if durations_df.empty:
        st.info("ℹ️ لا توجد بيانات للمقارنة")
        return
    
    # تحليل حسب نوع الحدث
    event_type_stats = durations_df.groupby('Event_Type').agg({
        'Duration': ['count', 'mean', 'std', 'min', 'max'],
        'Card Number': 'nunique'
    }).round(2)
    
    event_type_stats.columns = ['عدد_الفترات', 'متوسط_المدة', 'انحراف_معياري', 'أقل_مدة', 'أعلى_مدة', 'عدد_الماكينات']
    event_type_stats = event_type_stats.reset_index()
    
    st.dataframe(event_type_stats, use_container_width=True)
    
    try:
        import plotly.express as px
        
        # مخطط دائري لتوزيع أنواع الأحداث
        fig1 = px.pie(event_type_stats, values='عدد_الفترات', names='Event_Type',
                     title='توزيع أنواع الأحداث')
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط شريطي لمتوسط المدة حسب النوع
        fig2 = px.bar(event_type_stats, x='Event_Type', y='متوسط_المدة',
                     title='متوسط المدة حسب نوع الحدث',
                     color='عدد_الماكينات',
                     hover_data=['عدد_الفترات', 'أقل_مدة', 'أعلى_مدة'])
        fig2.update_layout(xaxis_title="نوع الحدث", yaxis_title="متوسط المدة")
        st.plotly_chart(fig2, use_container_width=True)
        
    except ImportError:
        st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")

# ===============================
# 🖥 دوال العرض والتعديل الديناميكية
# ===============================
def display_dynamic_sheets(sheets_edit):
    """عرض جميع الشيتات بشكل ديناميكي"""
    st.subheader("📂 جميع الشيتات")
    
    if not sheets_edit:
        st.warning("⚠ لا توجد شيتات متاحة")
        return
    
    # إنشاء تبويبات لكل شيت
    sheet_tabs = st.tabs(list(sheets_edit.keys()))
    
    for i, (sheet_name, df) in enumerate(sheets_edit.items()):
        with sheet_tabs[i]:
            st.markdown(f"### 📋 {sheet_name}")
            st.info(f"الصفوف: {len(df)} | الأعمدة: {len(df.columns)}")
            
            # عرض جميع الأعمدة
            if st.checkbox(f"عرض جميع الأعمدة", key=f"show_all_{sheet_name}"):
                st.dataframe(df, use_container_width=True)
            else:
                # عرض الأعمدة الرئيسية فقط
                display_cols = []
                for col in df.columns:
                    col_lower = str(col).lower()
                    if any(keyword in col_lower for keyword in ['card', 'date', 'event', 'correction', 'servised', 'serviced', 'images', 'صور', 'technician', 'فني']):
                        display_cols.append(col)
                
                if display_cols:
                    st.dataframe(df[display_cols], use_container_width=True)
                else:
                    st.dataframe(df.head(10), use_container_width=True)
            
            # عرض إحصائيات
            with st.expander("📊 إحصائيات الشيت", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("عدد الصفوف", len(df))
                with col2:
                    st.metric("عدد الأعمدة", len(df.columns))
                with col3:
                    non_empty = df.notna().sum().sum()
                    total_cells = len(df) * len(df.columns)
                    st.metric("خلايا غير فارغة", f"{non_empty}/{total_cells}")

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد - مع خاصية رفع الصور
# -------------------------------
def add_new_event(sheets_edit):
    """إضافة إيفينت جديد في شيت منفصل مع خاصية رفع الصور"""
    st.subheader("➕ إضافة حدث جديد مع صور")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    st.markdown("أدخل بيانات الحدث الجديد:")
    
    col1, col2 = st.columns(2)
    with col1:
        card_num = st.text_input("رقم الماكينة/المعرف:", key="new_event_card")
        event_text = st.text_area("الحدث:", key="new_event_text")
    with col2:
        correction_text = st.text_area("التصحيح:", key="new_correction_text")
        serviced_by = st.text_input("فني الخدمة:", key="new_serviced_by")
    
    event_date = st.text_input("التاريخ (مثال: 20/5/2025):", key="new_event_date")
    
    # قسم رفع الصور
    st.markdown("---")
    st.markdown("### 📷 رفع صور للحدث (اختياري)")
    
    # خيارات رفع الصور
    uploaded_files = st.file_uploader(
        "اختر الصور المرفقة للحدث:",
        type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
        accept_multiple_files=True,
        key="event_images_uploader"
    )
    
    if uploaded_files:
        st.info(f"📁 تم اختيار {len(uploaded_files)} صورة")
        # عرض معاينة للصور المختارة
        preview_cols = st.columns(min(3, len(uploaded_files)))
        for idx, uploaded_file in enumerate(uploaded_files):
            with preview_cols[idx % 3]:
                try:
                    st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)
                except:
                    st.write(f"📷 {uploaded_file.name}")
    
    if st.button("💾 إضافة الحدث الجديد مع الصور", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        
        # حفظ الصور المرفوعة
        saved_images = []
        if uploaded_files:
            saved_images = save_uploaded_images(uploaded_files)
            if saved_images:
                st.success(f"✅ تم حفظ {len(saved_images)} صورة بنجاح")
        
        # إنشاء صف جديد
        new_row = {}
        
        # إضافة البيانات الأساسية
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
        # البحث عن أعمدة الحدث والتصحيح والفني
        for col in df.columns:
            col_lower = str(col).lower()
            if "event" in col_lower or "حدث" in col_lower:
                if event_text.strip():
                    new_row[col] = event_text.strip()
            elif "correction" in col_lower or "تصحيح" in col_lower:
                if correction_text.strip():
                    new_row[col] = correction_text.strip()
            elif "servis" in col_lower or "service" in col_lower or "فني" in col_lower:
                if serviced_by.strip():
                    new_row[col] = serviced_by.strip()
            elif "images" in col_lower or "صور" in col_lower:
                if saved_images:
                    new_row[col] = ", ".join(saved_images)
        
        # إضافة الصف الجديد
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new.astype(object)
        
        # حفظ تلقائي في GitHub
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}" + (f" مع {len(saved_images)} صورة" if saved_images else "")
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            
            # عرض ملخص
            with st.expander("📋 ملخص الحدث المضافة", expanded=True):
                st.markdown(f"**رقم الماكينة:** {card_num}")
                st.markdown(f"**الحدث:** {event_text[:100]}{'...' if len(event_text) > 100 else ''}")
                if saved_images:
                    st.markdown(f"**عدد الصور المرفقة:** {len(saved_images)}")
                    display_images(saved_images, "الصور المحفوظة")
            
            st.rerun()

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن - مع خاصية إدارة الصور
# -------------------------------
def edit_events_and_corrections(sheets_edit):
    """تعديل الحدث والتصحيح والصور"""
    st.subheader("✏ تعديل الحدث والتصحيح والصور")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    # عرض البيانات الحالية
    st.markdown("### 📋 البيانات الحالية")
    
    # استخراج الأعمدة المطلوبة
    display_columns = []
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['card', 'date', 'event', 'correction', 'servis', 'service', 'فني', 'images', 'صور']):
            display_columns.append(col)
    
    # إذا لم نجد أعمدة واضحة، نعرض أول 5 أعمدة
    if not display_columns and len(df.columns) > 0:
        display_columns = list(df.columns[:5])
    
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
        
        # البحث عن الأعمدة الرئيسية
        card_col = None
        date_col = None
        event_col = None
        correction_col = None
        tech_col = None
        images_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if "card" in col_lower or "رقم" in col_lower:
                card_col = col
            elif "date" in col_lower or "تاريخ" in col_lower:
                date_col = col
            elif "event" in col_lower or "حدث" in col_lower:
                event_col = col
            elif "correction" in col_lower or "تصحيح" in col_lower:
                correction_col = col
            elif "servis" in col_lower or "service" in col_lower or "فني" in col_lower:
                tech_col = col
            elif "images" in col_lower or "صور" in col_lower:
                images_col = col
        
        col1, col2 = st.columns(2)
        with col1:
            if card_col:
                new_card = st.text_input("رقم الماكينة:", value=editing_data.get(card_col, ""), key="edit_card")
            if date_col:
                new_date = st.text_input("التاريخ:", value=editing_data.get(date_col, ""), key="edit_date")
        with col2:
            if tech_col:
                new_serviced_by = st.text_input("فني الخدمة:", value=editing_data.get(tech_col, ""), key="edit_serviced_by")
        
        # حقول الإيفينت والكوريكشن
        if event_col:
            new_event = st.text_area("الحدث:", value=editing_data.get(event_col, ""), key="edit_event")
        if correction_col:
            new_correction = st.text_area("التصحيح:", value=editing_data.get(correction_col, ""), key="edit_correction")
        
        # قسم إدارة الصور
        st.markdown("---")
        st.markdown("### 📷 إدارة صور الحدث")
        
        existing_images = []
        if images_col and images_col in editing_data:
            existing_images_str = editing_data.get(images_col, "")
            if existing_images_str and existing_images_str != "-":
                existing_images = [img.strip() for img in existing_images_str.split(",") if img.strip()]
        
        # عرض الصور الحالية
        if existing_images:
            st.markdown("**الصور الحالية:**")
            display_images(existing_images, "")
            
            # خيار حذف الصور
            if st.checkbox("🗑️ حذف كل الصور الحالية", key="delete_existing_images"):
                existing_images = []
        
        # إضافة صور جديدة
        st.markdown("**إضافة صور جديدة:**")
        new_uploaded_files = st.file_uploader(
            "اختر صور جديدة لإضافتها:",
            type=APP_CONFIG["ALLOWED_IMAGE_TYPES"],
            accept_multiple_files=True,
            key="edit_images_uploader"
        )
        
        all_images = existing_images.copy()
        
        if new_uploaded_files:
            st.info(f"📁 تم اختيار {len(new_uploaded_files)} صورة جديدة")
            # حفظ الصور الجديدة
            new_saved_images = save_uploaded_images(new_uploaded_files)
            if new_saved_images:
                all_images.extend(new_saved_images)
                st.success(f"✅ تم حفظ {len(new_saved_images)} صورة جديدة")
        
        if st.button("💾 حفظ التعديلات والصور", key="save_edits_btn"):
            # تحديث البيانات
            if card_col:
                df.at[row_index, card_col] = new_card
            if date_col:
                df.at[row_index, date_col] = new_date
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            if tech_col:
                df.at[row_index, tech_col] = new_serviced_by.strip()
            
            # تحديث الصور
            if images_col:
                if all_images:
                    df.at[row_index, images_col] = ", ".join(all_images)
                else:
                    df.at[row_index, images_col] = ""
            
            sheets_edit[sheet_name] = df.astype(object)
            
            # حفظ تلقائي في GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"تعديل حدث في {sheet_name} - الصف {row_index}" + (f" مع تحديث الصور" if all_images else "")
            )
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                
                # عرض ملخص
                if all_images:
                    st.info(f"📷 العدد النهائي للصور: {len(all_images)}")
                    display_images(all_images, "الصور المحفوظة")
                
                # مسح بيانات الجلسة
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# -------------------------------
# 🖥 دالة إدارة الشيتات والأعمدة
# -------------------------------
def manage_sheets_and_columns(sheets_edit):
    """إدارة الشيتات والأعمدة"""
    st.subheader("🗂 إدارة الشيتات والأعمدة")
    
    if not sheets_edit:
        st.warning("⚠ لا توجد بيانات متاحة")
        return sheets_edit
    
    # تبويبات للإدارة
    manage_tabs = st.tabs(["➕ إنشاء شيت جديد", "✏ إدارة أعمدة شيت", "🗑 حذف شيت"])
    
    with manage_tabs[0]:
        st.markdown("### ➕ إنشاء شيت جديد")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_sheet_name = st.text_input("اسم الشيت الجديد:", placeholder="مثال: Card10 أو ServiceLog", key="new_sheet_name")
            
            # اختيار نموذج الأعمدة
            column_template = st.selectbox(
                "نموذج الأعمدة:",
                ["استخدام الأعمدة الافتراضية", "نسخ أعمدة من شيت موجود", "تحديد أعمدة مخصصة"],
                key="column_template"
            )
        
        with col2:
            if column_template == "نسخ أعمدة من شيت موجود":
                source_sheet = st.selectbox(
                    "اختر الشيت لنسخ أعمدة منه:",
                    list(sheets_edit.keys()),
                    key="source_sheet_for_columns"
                )
            elif column_template == "تحديد أعمدة مخصصة":
                custom_columns = st.text_area(
                    "أدخل أسماء الأعمدة (مفصولة بفواصل):",
                    placeholder="مثال: card, Date, Event, Correction, Servised by",
                    key="custom_columns"
                )
        
        # خيارات إضافية
        initial_rows = st.number_input("عدد الصفوف الأولية:", min_value=0, max_value=100, value=0, step=1, key="initial_rows")
        
        if st.button("🚀 إنشاء الشيت الجديد", key="create_new_sheet_btn", type="primary"):
            if not new_sheet_name.strip():
                st.warning("⚠ الرجاء إدخال اسم للشيت الجديد")
                return sheets_edit
            
            if new_sheet_name in sheets_edit:
                st.warning(f"⚠ الشيت '{new_sheet_name}' موجود بالفعل!")
                return sheets_edit
            
            # تحديد الأعمدة
            columns_to_use = APP_CONFIG["DEFAULT_COLUMNS"]
            
            if column_template == "نسخ أعمدة من شيت موجود" and source_sheet in sheets_edit:
                columns_to_use = list(sheets_edit[source_sheet].columns)
            
            elif column_template == "تحديد أعمدة مخصصة" and custom_columns.strip():
                columns_to_use = [col.strip() for col in custom_columns.split(',') if col.strip()]
            
            # إنشاء الشيت الجديد
            new_df = pd.DataFrame(columns=columns_to_use)
            sheets_edit[new_sheet_name] = new_df
            
            # إضافة الصفوف الأولية إذا طلب
            if initial_rows > 0:
                empty_data = {col: [""] * initial_rows for col in columns_to_use}
                sheets_edit[new_sheet_name] = pd.DataFrame(empty_data)
            
            # حفظ في GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"إنشاء شيت جديد '{new_sheet_name}' مع {len(columns_to_use)} أعمدة"
            )
            
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' بنجاح!")
                st.info(f"الأعمدة: {', '.join(columns_to_use[:5])}{'...' if len(columns_to_use) > 5 else ''}")
                st.rerun()
    
    with manage_tabs[1]:
        st.markdown("### ✏ إدارة أعمدة شيت")
        
        # اختيار الشيت
        selected_sheet = st.selectbox(
            "اختر الشيت:",
            list(sheets_edit.keys()),
            key="selected_sheet_for_columns"
        )
        
        if selected_sheet:
            df = sheets_edit[selected_sheet]
            columns = list(df.columns)
            
            st.markdown(f"**الأعمدة الحالية في '{selected_sheet}':**")
            st.info(f"عدد الأعمدة: {len(columns)}")
            
            # عرض الأعمدة الحالية
            columns_df = pd.DataFrame({
                "الرقم": range(1, len(columns) + 1),
                "اسم العمود": columns,
                "نوع البيانات": [str(df[col].dtype) for col in columns]
            })
            
            st.dataframe(columns_df, use_container_width=True)
            
            # تبويبات العمليات
            column_ops_tabs = st.tabs(["إعادة تسمية عمود", "إضافة عمود", "حذف عمود", "إعادة ترتيب الأعمدة"])
            
            with column_ops_tabs[0]:
                st.markdown("#### إعادة تسمية عمود")
                
                col_rename1, col_rename2 = st.columns(2)
                
                with col_rename1:
                    old_column_name = st.selectbox(
                        "اختر العمود لإعادة التسمية:",
                        columns,
                        key="old_column_name"
                    )
                
                with col_rename2:
                    new_column_name = st.text_input(
                        "الاسم الجديد للعمود:",
                        value=old_column_name if 'old_column_name' in locals() else "",
                        key="new_column_name_input"
                    )
                
                if st.button("✏️ إعادة تسمية", key="rename_column_btn"):
                    if old_column_name and new_column_name and old_column_name != new_column_name:
                        df.rename(columns={old_column_name: new_column_name}, inplace=True)
                        sheets_edit[selected_sheet] = df
                        
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إعادة تسمية عمود '{old_column_name}' إلى '{new_column_name}' في شيت '{selected_sheet}'"
                        )
                        
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success(f"✅ تم إعادة تسمية العمود '{old_column_name}' إلى '{new_column_name}'")
                            st.rerun()
                    else:
                        st.warning("⚠ الرجاء اختيار عمود وإدخال اسم جديد مختلف")
            
            with column_ops_tabs[1]:
                st.markdown("#### إضافة عمود جديد")
                
                new_column_name_add = st.text_input("اسم العمود الجديد:", key="new_column_to_add")
                default_value_add = st.text_input("القيمة الافتراضية (اختياري):", key="default_value_for_new_column")
                
                if st.button("➕ إضافة العمود", key="add_new_column_btn"):
                    if new_column_name_add:
                        if new_column_name_add not in df.columns:
                            df[new_column_name_add] = default_value_add if default_value_add else ""
                            sheets_edit[selected_sheet] = df
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"إضافة عمود جديد '{new_column_name_add}' إلى شيت '{selected_sheet}'"
                            )
                            
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success(f"✅ تم إضافة العمود '{new_column_name_add}'")
                                st.rerun()
                        else:
                            st.warning(f"⚠ العمود '{new_column_name_add}' موجود بالفعل!")
                    else:
                        st.warning("⚠ الرجاء إدخال اسم للعمود الجديد")
            
            with column_ops_tabs[2]:
                st.markdown("#### حذف عمود")
                
                column_to_delete = st.selectbox(
                    "اختر العمود للحذف:",
                    columns,
                    key="column_to_delete"
                )
                
                if st.button("🗑 حذف العمود", key="delete_column_btn", type="secondary"):
                    if column_to_delete:
                        confirm = st.checkbox(f"هل أنت متأكد من حذف العمود '{column_to_delete}'؟")
                        
                        if confirm:
                            df.drop(columns=[column_to_delete], inplace=True)
                            sheets_edit[selected_sheet] = df
                            
                            new_sheets = auto_save_to_github(
                                sheets_edit,
                                f"حذف عمود '{column_to_delete}' من شيت '{selected_sheet}'"
                            )
                            
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success(f"✅ تم حذف العمود '{column_to_delete}'")
                                st.rerun()
            
            with column_ops_tabs[3]:
                st.markdown("#### إعادة ترتيب الأعمدة")
                
                st.info("اسحب الأعمدة لإعادة ترتيبها:")
                
                # استخدام multiselect لتمثيل الترتيب
                column_order = st.multiselect(
                    "ترتيب الأعمدة:",
                    columns,
                    default=columns,
                    key="column_order_multiselect"
                )
                
                if st.button("🔄 تطبيق الترتيب الجديد", key="apply_column_order_btn"):
                    if len(column_order) == len(columns):
                        df = df[column_order]
                        sheets_edit[selected_sheet] = df
                        
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إعادة ترتيب أعمدة شيت '{selected_sheet}'"
                        )
                        
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success("✅ تم إعادة ترتيب الأعمدة بنجاح!")
                            st.rerun()
                    else:
                        st.warning("⚠ يجب اختيار جميع الأعمدة للترتيب")
    
    with manage_tabs[2]:
        st.markdown("### 🗑 حذف شيت")
        
        sheet_to_delete = st.selectbox(
            "اختر الشيت للحذف:",
            list(sheets_edit.keys()),
            key="sheet_to_delete"
        )
        
        if sheet_to_delete:
            st.warning(f"⚠ تحذير: سيتم حذف الشيت '{sheet_to_delete}' بشكل دائم!")
            
            # عرض معلومات الشيت
            if sheet_to_delete in sheets_edit:
                df_to_delete = sheets_edit[sheet_to_delete]
                st.info(f"الشيت يحتوي على: {len(df_to_delete)} صف و {len(df_to_delete.columns)} عمود")
            
            confirm_delete = st.checkbox(f"أنا أدرك أن حذف الشيت '{sheet_to_delete}' لا يمكن التراجع عنه", key="confirm_sheet_delete")
            
            if st.button("🗑️ حذف الشيت نهائياً", key="delete_sheet_btn", disabled=not confirm_delete, type="secondary"):
                if confirm_delete:
                    # حذف الشيت
                    del sheets_edit[sheet_to_delete]
                    
                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"حذف شيت '{sheet_to_delete}'"
                    )
                    
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.success(f"✅ تم حذف الشيت '{sheet_to_delete}' بنجاح!")
                        st.rerun()
    
    return sheets_edit

# -------------------------------
# 🖥 دالة تعديل الشيت مع زر حفظ يدوي
# -------------------------------
def edit_sheet_with_save_button(sheets_edit):
    """تعديل بيانات الشيت مع زر حفظ يدوي"""
    st.subheader("✏ تعديل البيانات")
    
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    
    df = sheets_edit[sheet_name].astype(str).copy()
    
    # عرض البيانات للتحرير
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # محرر البيانات
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )
    
    # التحقق من وجود تغييرات
    has_changes = not edited_df.equals(df)
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        
        # عرض إشعار بالتغييرات غير المحفوظة
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        
        # أزرار الإدارة
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                # حفظ التغييرات
                sheets_edit[sheet_name] = edited_df.astype(object)
                
                # حفظ تلقائي في GitHub
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل يدوي في شيت {sheet_name}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    
                    # تحديث البيانات الأصلية
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    
                    # إعادة التحميل بعد ثانية
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                # استعادة البيانات الأصلية
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info(f"↩️ تم التراجع عن التغييرات في شيت {sheet_name}")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
        
        with col3:
            # عرض ملخص التغييرات
            with st.expander("📊 ملخص التغييرات", expanded=False):
                # حساب الاختلافات
                changes_count = 0
                
                # التحقق من الصفوف المضافة
                if len(edited_df) > len(df):
                    added_rows = len(edited_df) - len(df)
                    st.write(f"➕ **صفوف مضافة:** {added_rows}")
                    changes_count += added_rows
                
                # التحقق من الصفوف المحذوفة
                elif len(edited_df) < len(df):
                    deleted_rows = len(df) - len(edited_df)
                    st.write(f"🗑️ **صفوف محذوفة:** {deleted_rows}")
                    changes_count += deleted_rows
                
                # التحقق من التغييرات في القيم
                changed_cells = 0
                if len(edited_df) == len(df) and edited_df.columns.equals(df.columns):
                    for col in df.columns:
                        if not edited_df[col].equals(df[col]):
                            col_changes = (edited_df[col] != df[col]).sum()
                            changed_cells += col_changes
                
                if changed_cells > 0:
                    st.write(f"✏️ **خلايا معدلة:** {changed_cells}")
                    changes_count += changed_cells
                
                if changes_count == 0:
                    st.write("🔄 **لا توجد تغييرات**")
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
            st.session_state.unsaved_changes[sheet_name] = False
        
        # زر لإعادة تحميل البيانات
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
# إعداد الصفحة
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# إعداد مجلد الصور
setup_images_folder()

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
        # تحميل أحدث بيانات المستخدم من GitHub
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
    
    # زر إدارة الصور
    st.markdown("---")
    st.markdown("**📷 إدارة الصور:**")
    if os.path.exists(IMAGES_FOLDER):
        image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
        st.caption(f"عدد الصور: {len(image_files)}")
    
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

# عرض جميع الشيتات المتاحة
if all_sheets:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 الشيتات المتاحة")
    
    sheet_list = list(all_sheets.keys())
    selected_sheet_info = st.sidebar.selectbox("عرض معلومات شيت:", sheet_list)
    
    if selected_sheet_info in all_sheets:
        df_info = all_sheets[selected_sheet_info]
        st.sidebar.info(f"**{selected_sheet_info}:** {len(df_info)} صف × {len(df_info.columns)} عمود")
        
        # عرض عينة من البيانات
        if st.sidebar.checkbox("عرض عينة من البيانات"):
            st.sidebar.dataframe(df_info.head(3), use_container_width=True)

# تحديد التبويبات بناءً على الصلاحيات
if permissions["can_manage_users"]:  # admin
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
    
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"])
else:  # viewer
    tabs = st.tabs(["📋 فحص الإيفينت والكوريكشن"])

# -------------------------------
# Tab: فحص الإيفينت والكوريكشن (لجميع المستخدمين)
# -------------------------------
with tabs[0]:
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        # واجهة بحث متعدد المعايير
        check_events_and_corrections(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 1:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")

        # تحقق صلاحية الرفع
        token_exists = bool(st.secrets.get("github", {}).get("token", None))
        can_push = token_exists and GITHUB_AVAILABLE

        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            # عرض جميع الشيتات أولاً
            display_dynamic_sheets(sheets_edit)
            
            # تبويبات متعددة للإدارة
            tab_names = [
                "عرض وتعديل شيت",
                "إضافة صف جديد", 
                "إضافة عمود جديد",
                "➕ إضافة حدث جديد مع صور",
                "✏ تعديل الحدث والصور",
                "🗂 إدارة الشيتات والأعمدة",
                "📷 إدارة الصور"
            ]
            
            tabs_edit = st.tabs(tab_names)

            # Tab 1: تعديل بيانات وعرض
            with tabs_edit[0]:
                # التحقق من طلب حفظ جميع التغييرات
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    # هنا يمكنك إضافة منطق لحفظ جميع التغييرات
                    st.session_state["save_all_requested"] = False
                
                # استخدام دالة التعديل مع زر الحفظ
                sheets_edit = edit_sheet_with_save_button(sheets_edit)

            # Tab 2: إضافة صف جديد
            with tabs_edit[1]:
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
            with tabs_edit[2]:
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

            # Tab 4: إضافة إيفينت جديد مع صور
            with tabs_edit[3]:
                add_new_event(sheets_edit)

            # Tab 5: تعديل الإيفينت والكوريكشن والصور
            with tabs_edit[4]:
                edit_events_and_corrections(sheets_edit)
            
            # Tab 6: إدارة الشيتات والأعمدة
            with tabs_edit[5]:
                sheets_edit = manage_sheets_and_columns(sheets_edit)
            
            # Tab 7: إدارة الصور
            with tabs_edit[6]:
                st.subheader("📷 إدارة الصور المخزنة")
                
                if os.path.exists(IMAGES_FOLDER):
                    image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
                    
                    if image_files:
                        st.info(f"عدد الصور المخزنة: {len(image_files)}")
                        
                        # فلترة الصور
                        search_term = st.text_input("🔍 بحث عن صور:", placeholder="ابحث باسم الصورة")
                        
                        filtered_images = image_files
                        if search_term:
                            filtered_images = [img for img in image_files if search_term.lower() in img.lower()]
                            st.caption(f"تم العثور على {len(filtered_images)} صورة")
                        
                        # عرض الصور
                        images_per_page = 9
                        if "image_page" not in st.session_state:
                            st.session_state.image_page = 0
                        
                        total_pages = (len(filtered_images) + images_per_page - 1) // images_per_page
                        
                        if filtered_images:
                            # أزرار التنقل بين الصفحات
                            col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
                            with col_nav1:
                                if st.button("⏪ السابق", disabled=st.session_state.image_page == 0):
                                    st.session_state.image_page = max(0, st.session_state.image_page - 1)
                                    st.rerun()
                            
                            with col_nav2:
                                st.caption(f"الصفحة {st.session_state.image_page + 1} من {total_pages}")
                            
                            with col_nav3:
                                if st.button("التالي ⏩", disabled=st.session_state.image_page == total_pages - 1):
                                    st.session_state.image_page = min(total_pages - 1, st.session_state.image_page + 1)
                                    st.rerun()
                            
                            # عرض الصور
                            start_idx = st.session_state.image_page * images_per_page
                            end_idx = min(start_idx + images_per_page, len(filtered_images))
                            
                            for i in range(start_idx, end_idx, 3):
                                cols = st.columns(3)
                                for j in range(3):
                                    idx = i + j
                                    if idx < end_idx:
                                        with cols[j]:
                                            img_file = filtered_images[idx]
                                            img_path = os.path.join(IMAGES_FOLDER, img_file)
                                            
                                            try:
                                                st.image(img_path, caption=img_file, use_column_width=True)
                                                
                                                # زر حذف الصورة
                                                if st.button(f"🗑 حذف", key=f"delete_{img_file}"):
                                                    if delete_image_file(img_file):
                                                        st.success(f"✅ تم حذف {img_file}")
                                                        st.rerun()
                                                    else:
                                                        st.error(f"❌ فشل حذف {img_file}")
                                            except:
                                                st.write(f"📷 {img_file}")
                                                st.caption("⚠ لا يمكن عرض الصورة")
                    else:
                        st.info("ℹ️ لا توجد صور مخزنة بعد")
                else:
                    st.warning(f"⚠ مجلد الصور {IMAGES_FOLDER} غير موجود")

# -------------------------------
# Tab: تحليلات متقدمة - للمسؤولين فقط
# -------------------------------
if permissions["can_manage_users"] and len(tabs) > 2:
    with tabs[2]:
        st.header("📊 تحليلات متقدمة")
        
        if all_sheets is None:
            st.warning("❗ الملف المحلي غير موجود.")
        else:
            st.markdown("### 📈 تحليلات شاملة")
            
            # إحصائيات عامة
            total_sheets = len(all_sheets)
            total_rows = sum(len(df) for df in all_sheets.values())
            total_columns = sum(len(df.columns) for df in all_sheets.values())
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("📂 عدد الشيتات", total_sheets)
            with col_stat2:
                st.metric("📊 عدد الصفوف", total_rows)
            with col_stat3:
                st.metric("📋 عدد الأعمدة", total_columns)
            
            # تحليل الشيتات
            st.markdown("### 📊 تحليل الشيتات")
            
            sheets_analysis = []
            for sheet_name, df in all_sheets.items():
                non_empty = df.notna().sum().sum()
                total_cells = len(df) * len(df.columns)
                fill_rate = (non_empty / total_cells * 100) if total_cells > 0 else 0
                
                sheets_analysis.append({
                    "اسم الشيت": sheet_name,
                    "عدد الصفوف": len(df),
                    "عدد الأعمدة": len(df.columns),
                    "معدل التعبئة %": round(fill_rate, 2),
                    "الأعمدة الفريدة": ", ".join(df.columns[:3]) + ("..." if len(df.columns) > 3 else "")
                })
            
            analysis_df = pd.DataFrame(sheets_analysis)
            st.dataframe(analysis_df, use_container_width=True)
            
            # توزيع البيانات حسب الشيتات
            st.markdown("### 📈 توزيع البيانات")
            
            chart_data = pd.DataFrame({
                "الشيت": list(all_sheets.keys()),
                "عدد الصفوف": [len(df) for df in all_sheets.values()],
                "عدد الأعمدة": [len(df.columns) for df in all_sheets.values()]
            })
            
            try:
                import plotly.express as px
                
                fig1 = px.bar(chart_data, x='الشيت', y='عدد الصفوف', 
                            title='توزيع عدد الصفوف حسب الشيت')
                st.plotly_chart(fig1, use_container_width=True)
                
                fig2 = px.bar(chart_data, x='الشيت', y='عدد الأعمدة',
                            title='توزيع عدد الأعمدة حسب الشيت')
                st.plotly_chart(fig2, use_container_width=True)
                
            except ImportError:
                st.info("📊 لرؤية المخططات التفاعلية، قم بتثبيت مكتبة plotly")
