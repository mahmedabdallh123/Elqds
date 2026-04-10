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

# محاولة استيراد PyGithub (لرفع التعديلات والصور)
try:
    from github import Github, GithubException
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق - يمكن تعديلها بسهولة
# ===============================
APP_CONFIG = {
    # إعدادات التطبيق العامة
    "APP_TITLE": "CMMS -سيرفيس تحضيرات بيل يارن 1",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/BELYARN",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "IMAGES_FOLDER": "event_images",  # المجلد الذي ستُرفع إليه الصور في GitHub
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"],
    
    # إعدادات الصور
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp"],
    "MAX_IMAGE_SIZE_MB": 5
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
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{APP_CONFIG['REPO_NAME']}/{APP_CONFIG['BRANCH']}/"

# -------------------------------
# 🧩 دوال مساعدة للصور و GitHub
# -------------------------------
def get_github_repo():
    """إرجاع كائن المستودع من GitHub إذا كان التوكن متاحاً"""
    if not GITHUB_AVAILABLE:
        return None
    token = st.secrets.get("github", {}).get("token", None)
    if not token:
        return None
    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        return repo
    except Exception:
        return None

def upload_image_to_github(image_bytes, filename):
    """رفع صورة إلى مجلد event_images في GitHub وإرجاع الرابط المباشر"""
    repo = get_github_repo()
    if not repo:
        st.error("❌ لا يمكن رفع الصور: فشل الاتصال بـ GitHub أو عدم وجود token")
        return None
    
    # مسار الملف في المستودع
    file_path = f"{IMAGES_FOLDER}/{filename}"
    
    try:
        # محاولة الحصول على الملف القديم (إذا كان موجوداً)
        try:
            contents = repo.get_contents(file_path, ref=APP_CONFIG["BRANCH"])
            # تحديث الملف
            repo.update_file(file_path, f"Update image {filename}", image_bytes, contents.sha, branch=APP_CONFIG["BRANCH"])
        except GithubException as e:
            if e.status == 404:
                # الملف غير موجود، إنشاؤه
                repo.create_file(file_path, f"Add image {filename}", image_bytes, branch=APP_CONFIG["BRANCH"])
            else:
                raise e
        
        # إرجاع الرابط المباشر
        raw_url = f"{GITHUB_RAW_BASE}{file_path}"
        return raw_url
    except Exception as e:
        st.error(f"❌ فشل رفع الصورة {filename}: {e}")
        return None

def delete_image_from_github(image_url):
    """حذف صورة من GitHub باستخدام الرابط (إذا كان الرابط يشير إلى المستودع)"""
    repo = get_github_repo()
    if not repo:
        return False
    
    # استخراج المسار النسبي من الرابط
    if image_url.startswith(GITHUB_RAW_BASE):
        relative_path = image_url.replace(GITHUB_RAW_BASE, "")
        try:
            contents = repo.get_contents(relative_path, ref=APP_CONFIG["BRANCH"])
            repo.delete_file(relative_path, f"Delete image {relative_path}", contents.sha, branch=APP_CONFIG["BRANCH"])
            return True
        except Exception as e:
            st.error(f"❌ فشل حذف الصورة {image_url}: {e}")
            return False
    return False

def save_uploaded_images_to_github(uploaded_files):
    """حفظ الصور المرفوعة على GitHub وإرجاع قائمة الروابط المباشرة"""
    if not uploaded_files:
        return []
    
    saved_urls = []
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
        
        # رفع الصورة إلى GitHub
        image_bytes = uploaded_file.getvalue()
        raw_url = upload_image_to_github(image_bytes, new_filename)
        if raw_url:
            saved_urls.append(raw_url)
            st.success(f"✅ تم رفع {uploaded_file.name}")
    
    return saved_urls

def delete_images_from_github(image_urls):
    """حذف قائمة من الصور من GitHub"""
    if not image_urls:
        return
    for url in image_urls:
        delete_image_from_github(url)

def display_images(image_urls_or_filenames, caption="الصور المرفقة"):
    """عرض الصور من الروابط المباشرة أو أسماء الملفات المحلية (للتوافق القديم)"""
    if not image_urls_or_filenames:
        return
    
    st.markdown(f"**{caption}:**")
    
    # إذا كانت السلسلة نصية، نحولها إلى قائمة
    if isinstance(image_urls_or_filenames, str):
        if image_urls_or_filenames.startswith("http"):
            urls = [image_urls_or_filenames]
        else:
            # قد تكون أسماء ملفات قديمة (مخزنة محلياً) - نعرضها كروابط محلية إن وجدت
            urls = [img.strip() for img in image_urls_or_filenames.split(",") if img.strip()]
    else:
        urls = image_urls_or_filenames
    
    images_per_row = 3
    for i in range(0, len(urls), images_per_row):
        cols = st.columns(images_per_row)
        for j in range(images_per_row):
            idx = i + j
            if idx < len(urls):
                url = urls[idx].strip()
                with cols[j]:
                    try:
                        # إذا كان الرابط يبدأ بـ http، نستخدم st.image مباشرة
                        if url.startswith("http"):
                            st.image(url, caption=url.split("/")[-1], use_column_width=True)
                        else:
                            # محاولة عرض الملف المحلي (للتوافق القديم)
                            if os.path.exists(url):
                                st.image(url, caption=os.path.basename(url), use_column_width=True)
                            else:
                                st.write(f"📷 {url} (غير متوفر)")
                    except Exception:
                        st.write(f"📷 {url}")

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة (بدون تغيير)
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON - نسخة محسنة"""
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

# -------------------------------
# 🔄 طرق جلب الملف من GitHub (بدون تغيير)
# -------------------------------
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

def fetch_from_github_api():
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
# 📂 تحميل الشيتات (بدون تغيير)
# -------------------------------
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
        return None

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub (بدون تغيير)
# -------------------------------
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
            repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح: {commit_message}")
            return load_sheets_for_edit()
        except Exception:
            try:
                repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
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

# -------------------------------
# 🧰 دوال مساعدة للمعالجة والنصوص (بدون تغيير)
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
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
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
            "can_manage_users": False,
            "can_see_tech_support": False
        }

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

def get_images_value(row):
    images_columns = [
        "Images", "images", "Pictures", "pictures", "Attachments", "attachments",
        "صور", "الصور", "مرفقات", "المرفقات", "صور الحدث"
    ]
    for col in images_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["images", "pictures", "attachments", "صور", "مرفقات"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    return ""

# -------------------------------
# 🖥 دالة فحص السيرفيس (بدون تغيير كبير، فقط تحديث display_images)
# -------------------------------
def check_service_status(card_num, current_tons, all_sheets):
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_services_sheet_name = f"Card{card_num}_Services"
    
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
        "service_counts": {},
        "service_done_counts": {},
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {}
    }
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
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

        if "Min_Tones" in services_df.columns and "Max_Tones" in services_df.columns:
            mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
        elif "Min_Tones" in services_df.columns:
            mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Min_Tones"].fillna(0) >= slice_min)
        elif "Max_Tones" in services_df.columns:
            mask = (services_df["Max_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
        else:
            if "Tones" in services_df.columns:
                mask = services_df["Tones"].notna()
            else:
                mask = pd.Series([True] * len(services_df), index=services_df.index)
        
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                metadata_columns = {
                    "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
                    "Other", "Servised by", "Event", "Correction", "Images",
                    "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
                    "OTHER", "EVENT", "CORRECTION", "SERVISED BY", "IMAGES",
                    "servised by", "Servised By", 
                    "Serviced by", "Service by", "Serviced By", "Service By",
                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة",
                    "صور", "الصور", "مرفقات", "المرفقات"
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
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1

                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                servised_by_value = get_servised_by_value(row)
                images_value = get_images_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
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
                    "Date": current_date,
                    "Images": images_value if images_value else "-"
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
                "Date": "-",
                "Images": "-"
            })
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)
        show_service_statistics(service_stats, result_df)
        if "Images" in result_df.columns:
            for idx, row in result_df.iterrows():
                images_value = row.get("Images", "")
                if images_value and images_value != "-":
                    display_images(images_value, f"📷 صور للحدث #{idx+1}")
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
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    if service_stats["total_needed_services"] == 0:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100 if service_stats["total_needed_services"] > 0 else 0
    completion_rate = max(0, min(100, completion_rate))
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="📈 نسبة الإنجاز العامة", value=f"{completion_rate:.1f}%", delta=f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}")
    with col2:
        st.metric(label="🔢 عدد الخدمات المطلوبة", value=service_stats["total_needed_services"])
    with col3:
        st.metric(label="✅ الخدمات المنفذة", value=service_stats["total_done_services"])
    with col4:
        remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
        st.metric(label="⏳ الخدمات المتبقية", value=remaining)
    st.markdown("---")
    stat_tabs = st.tabs(["📝 إحصائيات الخدمات", "📋 توزيع الخدمات", "📊 حسب الشريحة"])
    with stat_tabs[0]:
        st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
        stat_data = []
        all_services = set(service_stats["service_counts"].keys()).union(set(service_stats["service_done_counts"].keys()))
        for service in sorted(all_services):
            needed_count = service_stats["service_counts"].get(service, 0)
            done_count = service_stats["service_done_counts"].get(service, 0)
            if needed_count > 0:
                completion_rate_service = (done_count / needed_count) * 100
                completion_rate_service = max(0, min(100, completion_rate_service))
            else:
                completion_rate_service = 0
            stat_data.append({
                "الخدمة": service,
                "مطلوبة": needed_count,
                "منفذة": done_count,
                "متبقية": needed_count - done_count,
                "نسبة الإنجاز": f"{completion_rate_service:.1f}%",
                "حالة": "✅ ممتاز" if completion_rate_service >= 90 else "🟢 جيد" if completion_rate_service >= 70 else "🟡 متوسط" if completion_rate_service >= 50 else "🔴 ضعيف"
            })
        if stat_data:
            stat_df = pd.DataFrame(stat_data)
            st.dataframe(stat_df, use_container_width=True, height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للخدمات.")
    with stat_tabs[1]:
        st.markdown("#### 📋 توزيع الخدمات")
        if service_stats["service_counts"]:
            try:
                import plotly.express as px
                plot_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    plot_data.append({"الخدمة": service, "النوع": "مطلوبة", "العدد": needed_count})
                    plot_data.append({"الخدمة": service, "النوع": "منفذة", "العدد": done_count})
                plot_df = pd.DataFrame(plot_data)
                fig = px.bar(plot_df, x="الخدمة", y="العدد", color="النوع", barmode="group", title="توزيع الخدمات المطلوبة والمنفذة", color_discrete_map={"مطلوبة": "#FF6B6B", "منفذة": "#4ECDC4"})
                fig.update_layout(xaxis_title="الخدمة", yaxis_title="العدد", showlegend=True, height=500)
                st.plotly_chart(fig, use_container_width=True)
                fig2 = px.pie(names=["✅ منفذة", "⏳ غير منفذة"], values=[service_stats["total_done_services"], service_stats["total_needed_services"] - service_stats["total_done_services"]], title="نسبة الإنجاز العامة", color_discrete_sequence=["#4ECDC4", "#FF6B6B"])
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
                st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
                if 0 <= completion_rate <= 100:
                    st.progress(completion_rate / 100)
                else:
                    st.info("ℹ️ لا يمكن عرض شريط التقدم بسبب قيمة النسبة غير الصحيحة")
            except ImportError:
                st.info("📊 عرض البيانات باستخدام الرسوم البيانية المضمنة في Streamlit")
                st.markdown("**📋 توزيع الخدمات:**")
                dist_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    if needed_count > 0:
                        completion_rate_service = (done_count / needed_count) * 100
                        completion_rate_service = max(0, min(100, completion_rate_service))
                    else:
                        completion_rate_service = 0
                    dist_data.append({"الخدمة": service, "مطلوبة": needed_count, "منفذة": done_count, "نسبة": f"{completion_rate_service:.1f}%"})
                if dist_data:
                    dist_df = pd.DataFrame(dist_data).sort_values("نسبة", ascending=False)
                    st.dataframe(dist_df, use_container_width=True, height=300)
                st.markdown("**📊 مخطط الخدمات المطلوبة مقابل المنفذة:**")
                chart_data = pd.DataFrame({"الخدمة": list(service_stats["service_counts"].keys()), "مطلوبة": list(service_stats["service_counts"].values()), "منفذة": [service_stats["service_done_counts"].get(service, 0) for service in service_stats["service_counts"].keys()]})
                if len(chart_data) > 10:
                    chart_data = chart_data.nlargest(10, "مطلوبة")
                st.bar_chart(chart_data.set_index("الخدمة"), height=400)
                st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
                if 0 <= completion_rate <= 100:
                    st.progress(completion_rate / 100)
                else:
                    st.info("ℹ️ لا يمكن عرض شريط التقدم بسبب قيمة النسبة غير الصحيحة")
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض المخططات.")
    with stat_tabs[2]:
        st.markdown("#### 📊 الإحصائيات حسب الشريحة")
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            if slice_data["total_needed"] > 0:
                completion_rate_slice = (slice_data["total_done"] / slice_data["total_needed"]) * 100
                completion_rate_slice = max(0, min(100, completion_rate_slice))
            else:
                completion_rate_slice = 0
            slice_stats_data.append({
                "الشريحة": slice_key,
                "الخدمات المطلوبة": slice_data["total_needed"],
                "الخدمات المنفذة": slice_data["total_done"],
                "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                "نسبة الإنجاز": f"{completion_rate_slice:.1f}%",
                "حالة الشريحة": "✅ ممتازة" if completion_rate_slice >= 90 else "🟢 جيدة" if completion_rate_slice >= 70 else "🟡 متوسطة" if completion_rate_slice >= 50 else "🔴 ضعيفة"
            })
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            st.dataframe(slice_stats_df, use_container_width=True, height=400)
            try:
                import plotly.graph_objects as go
                slice_ranges = []
                completion_rates = []
                for slice_item in slice_stats_data:
                    slice_key = slice_item["الشريحة"]
                    slice_range = slice_key.split("-")
                    if len(slice_range) == 2:
                        try:
                            mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                            slice_ranges.append(mid_point)
                            rate_text = slice_item["نسبة الإنجاز"]
                            rate_value = float(rate_text.replace("%", "").strip())
                            rate_value = max(0, min(100, rate_value))
                            completion_rates.append(rate_value)
                        except:
                            continue
                if slice_ranges and completion_rates:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(x=slice_ranges, y=completion_rates, mode='lines+markers', name='نسبة الإنجاز', line=dict(color='#4ECDC4', width=3), marker=dict(size=10, color='#FF6B6B')))
                    fig3.update_layout(title="نسبة الإنجاز حسب نطاق الأطنان", xaxis_title="نطاق الأطنان (منتصف الشريحة)", yaxis_title="نسبة الإنجاز (%)", height=400, showlegend=True)
                    st.plotly_chart(fig3, use_container_width=True)
            except ImportError:
                if slice_stats_data:
                    chart_data = []
                    for slice_item in slice_stats_data:
                        slice_key = slice_item["الشريحة"]
                        slice_range = slice_key.split("-")
                        if len(slice_range) == 2:
                            try:
                                mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                                rate_text = slice_item["نسبة الإنجاز"]
                                rate_value = float(rate_text.replace("%", "").strip())
                                rate_value = max(0, min(100, rate_value))
                                chart_data.append({"نطاق الأطنان": mid_point, "نسبة الإنجاز": rate_value})
                            except:
                                continue
                    if chart_data:
                        chart_df = pd.DataFrame(chart_data).sort_values("نطاق الأطنان")
                        st.line_chart(chart_df.set_index("نطاق الأطنان"), height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للشرائح.")

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن (بدون تحليل مدة، مع تعديل display_images)
# -------------------------------
def check_events_and_corrections(all_sheets):
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
            "sort_by": "رقم الماكينة",
            "show_images": True
        }
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك ملء واحد أو أكثر من الحقول.")
        col1, col2 = st.columns([1, 1])
        with col1:
            with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                st.caption("أدخل أرقام الماكينات (مفصولة بفواصل أو نطاقات)")
                card_numbers = st.text_input("مثال: 1,3,5 أو 1-5 أو 2,4,7-10", value=st.session_state.search_params.get("card_numbers", ""), key="input_cards", placeholder="اتركه فارغاً للبحث في كل الماكينات")
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
            with st.expander("📅 **التواريخ**", expanded=True):
                st.caption("ابحث بالتاريخ (سنة، شهر/سنة)")
                date_input = st.text_input("مثال: 2024 أو 1/2024 أو 2024,2025", value=st.session_state.search_params.get("date_range", ""), key="input_date", placeholder="اتركه فارغاً للبحث في كل التواريخ")
        with col2:
            with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                st.caption("ابحث بأسماء فنيي الخدمة")
                tech_names = st.text_input("مثال: أحمد, محمد, علي", value=st.session_state.search_params.get("tech_names", ""), key="input_techs", placeholder="اتركه فارغاً للبحث في كل الفنيين")
            with st.expander("📝 **نص البحث**", expanded=True):
                st.caption("ابحث في وصف الحدث أو التصحيح")
                search_text = st.text_input("مثال: صيانة, إصلاح, تغيير", value=st.session_state.search_params.get("search_text", ""), key="input_text", placeholder="اتركه فارغاً للبحث في كل النصوص")
        with st.expander("⚙ **خيارات متقدمة**", expanded=False):
            col_adv1, col_adv2, col_adv3 = st.columns(3)
            with col_adv1:
                search_mode = st.radio("🔍 طريقة البحث:", ["بحث جزئي", "مطابقة كاملة"], index=0 if not st.session_state.search_params.get("exact_match") else 1, key="radio_search_mode")
            with col_adv2:
                include_empty = st.checkbox("🔍 تضمين الحقول الفارغة", value=st.session_state.search_params.get("include_empty", True), key="checkbox_include_empty")
            with col_adv3:
                sort_by = st.selectbox("📊 ترتيب النتائج:", ["رقم الماكينة", "التاريخ", "فني الخدمة"], index=["رقم الماكينة", "التاريخ", "فني الخدمة"].index(st.session_state.search_params.get("sort_by", "رقم الماكينة")), key="select_sort_by")
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        with col_btn1:
            search_clicked = st.button("🔍 **بدء البحث**", type="primary", use_container_width=True, key="main_search_btn")
        with col_btn2:
            if st.button("🗑 **مسح الحقول**", use_container_width=True, key="clear_fields"):
                st.session_state.search_params = {"card_numbers": "", "date_range": "", "tech_names": "", "search_text": "", "exact_match": False, "include_empty": True, "sort_by": "رقم الماكينة", "show_images": True}
                st.session_state.search_triggered = False
                st.rerun()
        with col_btn3:
            if st.button("📊 **عرض كل البيانات**", use_container_width=True, key="show_all"):
                st.session_state.search_params = {"card_numbers": "", "date_range": "", "tech_names": "", "search_text": "", "exact_match": False, "include_empty": True, "sort_by": "رقم الماكينة", "show_images": True}
                st.session_state.search_triggered = True
                st.rerun()
    
    st.session_state.search_params.update({
        "card_numbers": card_numbers,
        "date_range": date_input,
        "tech_names": tech_names,
        "search_text": search_text,
        "exact_match": search_mode == "مطابقة كاملة",
        "include_empty": include_empty,
        "sort_by": sort_by,
        "show_images": True
    })
    
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        search_params = st.session_state.search_params.copy()
        show_search_params(search_params)
        show_advanced_search_results(search_params, all_sheets)

def show_search_params(search_params):
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

def show_advanced_search_results(search_params, all_sheets):
    st.markdown("### 📊 نتائج البحث")
    progress_bar = st.progress(0)
    status_text = st.empty()
    all_results = []
    total_machines = 0
    processed_machines = 0
    for sheet_name in all_sheets.keys():
        if sheet_name != "ServicePlan" and sheet_name.startswith("Card"):
            total_machines += 1
    target_card_numbers = parse_card_numbers(search_params["card_numbers"])
    target_techs = []
    if search_params["tech_names"]:
        techs = search_params["tech_names"].split(',')
        target_techs = [tech.strip().lower() for tech in techs if tech.strip()]
    target_dates = []
    if search_params["date_range"]:
        dates = search_params["date_range"].split(',')
        target_dates = [date.strip().lower() for date in dates if date.strip()]
    search_terms = []
    if search_params["search_text"]:
        terms = search_params["search_text"].split(',')
        search_terms = [term.strip().lower() for term in terms if term.strip()]
    
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
        card_num = int(card_num_match.group(1))
        if target_card_numbers and card_num not in target_card_numbers:
            continue
        processed_machines += 1
        if total_machines > 0:
            progress_bar.progress(processed_machines / total_machines)
        status_text.text(f"🔍 جاري معالجة الماكينة {card_num}...")
        df = all_sheets[sheet_name].copy()
        for _, row in df.iterrows():
            if not check_row_criteria(row, df, card_num, target_techs, target_dates, search_terms, search_params):
                continue
            result = extract_row_data(row, df, card_num)
            if result:
                all_results.append(result)
    progress_bar.empty()
    status_text.empty()
    if all_results:
        display_search_results(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def display_search_results(results, search_params):
    if not results:
        st.warning("⚠ لا توجد نتائج لعرضها")
        return
    result_df = pd.DataFrame(results)
    if result_df.empty:
        st.warning("⚠ لا توجد بيانات لعرضها")
        return
    display_df = result_df.copy()
    display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Card_Number_Clean'], ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Card_Number_Clean', 'Date_Clean'], ascending=[True, True, False], na_position='last')
    else:
        display_df = display_df.sort_values(by=['Card_Number_Clean', 'Date_Clean'], ascending=[True, False], na_position='last')
    display_df['Event_Order'] = display_df.groupby('Card Number').cumcount() + 1
    display_df['Total_Events'] = display_df.groupby('Card Number')['Card Number'].transform('count')
    st.markdown("### 📈 إحصائيات النتائج")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    with col2:
        unique_machines = display_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    with col3:
        if not display_df.empty:
            machine_counts = display_df.groupby('Card Number').size()
            multi_event_machines = (machine_counts > 1).sum()
            st.metric("🔢 مكن متعددة الأحداث", multi_event_machines)
        else:
            st.metric("🔢 مكن متعددة الأحداث", 0)
    with col4:
        has_images_column = 'Images' in display_df.columns
        if has_images_column:
            with_images = display_df[display_df["Images"].notna() & (display_df["Images"] != "-")].shape[0]
            st.metric("📷 تحتوي على صور", with_images)
        else:
            st.metric("📷 تحتوي على صور", 0)
    st.markdown("---")
    st.markdown("### 📋 النتائج التفصيلية")
    display_tabs = st.tabs(["📊 عرض جدولي", "📋 عرض تفصيلي حسب الماكينة", "📷 عرض الصور"])
    with display_tabs[0]:
        columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date', 'Event_Order', 'Total_Events']
        has_images_in_results = any('Images' in result for result in results)
        if has_images_in_results and 'Images' not in columns_to_show:
            columns_to_show.append('Images')
        columns_to_show = [col for col in columns_to_show if col in display_df.columns]
        st.dataframe(display_df[columns_to_show].style.apply(style_table, axis=1), use_container_width=True, height=500)
    with display_tabs[1]:
        unique_machines = sorted(display_df['Card Number'].unique(), key=lambda x: pd.to_numeric(x, errors='coerce') if str(x).isdigit() else float('inf'))
        for machine in unique_machines:
            machine_data = display_df[display_df['Card Number'] == machine].copy()
            machine_data = machine_data.sort_values('Event_Order')
            with st.expander(f"🔧 الماكينة {machine} - عدد الأحداث: {len(machine_data)}", expanded=len(unique_machines) <= 5):
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        first_date = machine_data['Date'].iloc[0]
                        st.metric("📅 أول حدث", first_date if first_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 أول حدث", "-")
                with col_stats2:
                    if not machine_data.empty and 'Date' in machine_data.columns:
                        last_date = machine_data['Date'].iloc[-1]
                        st.metric("📅 آخر حدث", last_date if last_date != "-" else "غير محدد")
                    else:
                        st.metric("📅 آخر حدث", "-")
                with col_stats3:
                    if not machine_data.empty and 'Servised by' in machine_data.columns:
                        tech_count = machine_data['Servised by'].nunique()
                        st.metric("👨‍🔧 فنيين مختلفين", tech_count)
                    else:
                        st.metric("👨‍🔧 فنيين مختلفين", 0)
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
                        if 'Images' in row and row['Images'] not in ['-', '', None, 'nan']:
                            images_str = str(row['Images'])
                            if images_str.strip():
                                images_count = len(images_str.split(',')) if images_str else 0
                                st.markdown(f"**📷 عدد الصور:** {images_count}")
    with display_tabs[2]:
        events_with_images = []
        for result in results:
            if 'Images' in result and result['Images'] and result['Images'] != "-":
                events_with_images.append(result)
        if events_with_images:
            st.markdown("### 📷 الصور المرفقة بالأحداث")
            images_df = pd.DataFrame(events_with_images)
            for idx, row in images_df.iterrows():
                card_num = row.get('Card Number', 'غير معروف')
                event_date = row.get('Date', 'غير معروف')
                event_text = row.get('Event', 'لا يوجد')
                with st.expander(f"📸 صور للحدث - الماكينة {card_num} - {event_date}", expanded=False):
                    col_img1, col_img2 = st.columns([2, 3])
                    with col_img1:
                        st.markdown("**تفاصيل الحدث:**")
                        st.markdown(f"**رقم الماكينة:** {card_num}")
                        st.markdown(f"**التاريخ:** {event_date}")
                        st.markdown(f"**الحدث:** {event_text[:50]}{'...' if len(event_text) > 50 else ''}")
                        st.markdown(f"**التصحيح:** {row.get('Correction', '-')}")
                        st.markdown(f"**فني الخدمة:** {row.get('Servised by', '-')}")
                    with col_img2:
                        images_value = row.get('Images', '')
                        if images_value:
                            display_images(images_value, "الصور المرفقة")
        else:
            st.info("ℹ️ لا توجد أحداث تحتوي على صور في نتائج البحث")
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        if not result_df.empty:
            buffer_excel = io.BytesIO()
            export_df = result_df.copy()
            export_df['Card_Number_Clean_Export'] = pd.to_numeric(export_df['Card Number'], errors='coerce')
            export_df['Date_Clean_Export'] = pd.to_datetime(export_df['Date'], errors='coerce', dayfirst=True)
            export_df = export_df.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], ascending=[True, False], na_position='last')
            export_df = export_df.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            export_df.to_excel(buffer_excel, index=False, engine="openpyxl")
            st.download_button(label="📊 حفظ كملف Excel", data=buffer_excel.getvalue(), file_name=f"بحث_أحداث_مرتب_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.info("⚠ لا توجد بيانات للتصدير")
    with export_col2:
        if not result_df.empty:
            buffer_csv = io.BytesIO()
            export_csv = result_df.copy()
            export_csv['Card_Number_Clean_Export'] = pd.to_numeric(export_csv['Card Number'], errors='coerce')
            export_csv['Date_Clean_Export'] = pd.to_datetime(export_csv['Date'], errors='coerce', dayfirst=True)
            export_csv = export_csv.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], ascending=[True, False], na_position='last')
            export_csv = export_csv.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            export_csv.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
            st.download_button(label="📄 حفظ كملف CSV", data=buffer_csv.getvalue(), file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("⚠ لا توجد بيانات للتصدير")

def check_row_criteria(row, df, card_num, target_techs, target_dates, search_terms, search_params):
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

def extract_event_correction(row, df):
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
    card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
    date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    event_value, correction_value = extract_event_correction(row, df)
    images_value = get_images_value(row)
    if (event_value == "-" and correction_value == "-" and date == "-" and tones == "-" and not images_value):
        return None
    servised_by_value = get_servised_by_value(row)
    result = {"Card Number": card_num_value, "Event": event_value, "Correction": correction_value, "Servised by": servised_by_value, "Tones": tones, "Date": date}
    if images_value and images_value.strip():
        result["Images"] = images_value.strip()
    return result

def parse_card_numbers(card_numbers_str):
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

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد مع رفع الصور إلى GitHub
# -------------------------------
def add_new_event(sheets_edit):
    st.subheader("➕ إضافة حدث جديد مع صور (ترفع إلى GitHub)")
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
    event_date = st.text_input("التاريخ (مثال: 20/5/2025):", key="new_event_date")
    st.markdown("---")
    st.markdown("### 📷 رفع صور للحدث (اختياري) - سيتم رفعها إلى GitHub")
    uploaded_files = st.file_uploader("اختر الصور المرفقة للحدث:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True, key="event_images_uploader")
    if uploaded_files:
        st.info(f"📁 تم اختيار {len(uploaded_files)} صورة")
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
        saved_urls = []
        if uploaded_files:
            with st.spinner("جاري رفع الصور إلى GitHub..."):
                saved_urls = save_uploaded_images_to_github(uploaded_files)
            if saved_urls:
                st.success(f"✅ تم رفع {len(saved_urls)} صورة بنجاح إلى GitHub")
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
        if saved_urls:
            images_col = None
            images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
            if images_columns:
                images_col = images_columns[0]
            else:
                images_col = "Images"
                if images_col not in df.columns:
                    df[images_col] = ""
            new_row[images_col] = ", ".join(saved_urls)
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        sheets_edit[sheet_name] = df_new.astype(object)
        new_sheets = auto_save_to_github(sheets_edit, f"إضافة حدث جديد في {sheet_name}" + (f" مع {len(saved_urls)} صورة" if saved_urls else ""))
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            with st.expander("📋 ملخص الحدث المضافة", expanded=True):
                st.markdown(f"**رقم الماكينة:** {card_num}")
                st.markdown(f"**الحدث:** {event_text[:100]}{'...' if len(event_text) > 100 else ''}")
                if saved_urls:
                    st.markdown(f"**عدد الصور المرفقة:** {len(saved_urls)}")
                    display_images(saved_urls, "الصور المحفوظة")
            st.rerun()

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن مع إدارة الصور على GitHub
# -------------------------------
def edit_events_and_corrections(sheets_edit):
    st.subheader("✏ تعديل الحدث والتصحيح والصور (مع إدارة الصور على GitHub)")
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح والصور)")
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
    images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
    if images_columns:
        display_columns.append(images_columns[0])
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
        st.markdown("---")
        st.markdown("### 📷 إدارة صور الحدث (على GitHub)")
        images_col = None
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["images", "pictures", "attachments", "صور", "مرفقات"]:
                images_col = col
                break
        existing_images = []
        if images_col and images_col in editing_data:
            existing_images_str = editing_data.get(images_col)
            if existing_images_str is not None and pd.notna(existing_images_str):
                existing_images_str = str(existing_images_str).strip()
                if existing_images_str and existing_images_str != "-":
                    existing_images = [img.strip() for img in existing_images_str.split(",") if img.strip()]
        if existing_images:
            st.markdown("**الصور الحالية (روابط GitHub):**")
            display_images(existing_images, "")
            if st.checkbox("🗑️ حذف كل الصور الحالية من GitHub", key="delete_existing_images"):
                with st.spinner("جاري حذف الصور من GitHub..."):
                    delete_images_from_github(existing_images)
                existing_images = []
                st.success("✅ تم حذف الصور الحالية")
        st.markdown("**إضافة صور جديدة (سيتم رفعها إلى GitHub):**")
        new_uploaded_files = st.file_uploader("اختر صور جديدة لإضافتها:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True, key="edit_images_uploader")
        all_images = existing_images.copy()
        if new_uploaded_files:
            st.info(f"📁 تم اختيار {len(new_uploaded_files)} صورة جديدة")
            with st.spinner("جاري رفع الصور الجديدة إلى GitHub..."):
                new_saved_urls = save_uploaded_images_to_github(new_uploaded_files)
            if new_saved_urls:
                all_images.extend(new_saved_urls)
                st.success(f"✅ تم رفع {len(new_saved_urls)} صورة جديدة")
        if st.button("💾 حفظ التعديلات والصور", key="save_edits_btn"):
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
            if images_col:
                if all_images:
                    df.at[row_index, images_col] = ", ".join(all_images)
                else:
                    df.at[row_index, images_col] = ""
            elif all_images:
                images_col = "Images"
                df[images_col] = ""
                df.at[row_index, images_col] = ", ".join(all_images)
            sheets_edit[sheet_name] = df.astype(object)
            new_sheets = auto_save_to_github(sheets_edit, f"تعديل حدث في {sheet_name} - الصف {row_index}" + (f" مع تحديث الصور" if all_images else ""))
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                if all_images:
                    st.info(f"📷 العدد النهائي للصور: {len(all_images)}")
                    display_images(all_images, "الصور المحفوظة")
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# -------------------------------
# 🖥 دالة تعديل الشيت مع زر حفظ يدوي (بدون تغيير)
# -------------------------------
def edit_sheet_with_save_button(sheets_edit):
    st.subheader("✏ تعديل البيانات")
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    df = sheets_edit[sheet_name].astype(str).copy()
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{sheet_name}")
    has_changes = not edited_df.equals(df)
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                new_sheets = auto_save_to_github(sheets_edit, f"تعديل يدوي في شيت {sheet_name}")
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info(f"↩️ تم التراجع عن التغييرات في شيت {sheet_name}")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
        with col3:
            with st.expander("📊 ملخص التغييرات", expanded=False):
                changes_count = 0
                if len(edited_df) > len(df):
                    added_rows = len(edited_df) - len(df)
                    st.write(f"➕ **صفوف مضافة:** {added_rows}")
                    changes_count += added_rows
                elif len(edited_df) < len(df):
                    deleted_rows = len(df) - len(edited_df)
                    st.write(f"🗑️ **صفوف محذوفة:** {deleted_rows}")
                    changes_count += deleted_rows
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
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# لا حاجة لإنشاء مجلد الصور محلياً لأن الصور تُرفع إلى GitHub
# setup_images_folder()  # تم إلغاؤها

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
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    if st.session_state.get("unsaved_changes", {}):
        unsaved_count = sum(1 for v in st.session_state.unsaved_changes.values() if v)
        if unsaved_count > 0:
            st.markdown("---")
            st.warning(f"⚠ لديك {unsaved_count} شيت به تغييرات غير محفوظة")
            if st.button("💾 حفظ جميع التغييرات", key="save_all_changes", type="primary"):
                st.session_state["save_all_requested"] = True
                st.rerun()
    st.markdown("---")
    st.markdown("**📷 إدارة الصور:**")
    st.info("الصور تُرفع إلى GitHub في مجلد `event_images`")
    if st.button("🧹 تنظيف الصور المحلية (اختياري)"):
        if os.path.exists(IMAGES_FOLDER):
            shutil.rmtree(IMAGES_FOLDER)
            st.success("✅ تم حذف المجلد المحلي للصور (إن وجد)")
            st.rerun()
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

if permissions["can_edit"]:
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
else:
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن"])

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

if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        st.header("🛠 تعديل وإدارة البيانات")
        token_exists = bool(st.secrets.get("github", {}).get("token", None))
        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "عرض وتعديل شيت",
                "إضافة صف جديد", 
                "إضافة عمود جديد",
                "➕ إضافة حدث جديد مع صور",
                "✏ تعديل الحدث والصور",
                "📷 إدارة الصور (GitHub)"
            ])
            with tab1:
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    st.session_state["save_all_requested"] = False
                sheets_edit = edit_sheet_with_save_button(sheets_edit)
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
                        new_sheets = auto_save_to_github(sheets_edit, f"إضافة صف جديد في {sheet_name_add}")
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success("✅ تم إضافة الصف الجديد بنجاح!")
                            st.rerun()
                with col_btn2:
                    if st.button("🗑 مسح الحقول", key=f"clear_{sheet_name_add}"):
                        st.rerun()
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
                            new_sheets = auto_save_to_github(sheets_edit, f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}")
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success("✅ تم إضافة العمود الجديد بنجاح!")
                                st.rerun()
                        else:
                            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
                with col_btn2:
                    if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
                        st.rerun()
            with tab4:
                add_new_event(sheets_edit)
            with tab5:
                edit_events_and_corrections(sheets_edit)
            with tab6:
                st.subheader("📷 إدارة الصور على GitHub")
                st.info("يمكنك عرض وحذف الصور المخزنة في مستودع GitHub مباشرة.")
                repo = get_github_repo()
                if repo:
                    try:
                        contents = repo.get_contents(IMAGES_FOLDER, ref=APP_CONFIG["BRANCH"])
                        image_files = [c for c in contents if c.name.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
                        if image_files:
                            st.info(f"عدد الصور في GitHub: {len(image_files)}")
                            search_term = st.text_input("🔍 بحث عن صور:", placeholder="ابحث باسم الصورة")
                            filtered = [c for c in image_files if search_term.lower() in c.name.lower()] if search_term else image_files
                            st.caption(f"تم العثور على {len(filtered)} صورة")
                            images_per_page = 9
                            if "image_page_github" not in st.session_state:
                                st.session_state.image_page_github = 0
                            total_pages = (len(filtered) + images_per_page - 1) // images_per_page
                            if filtered:
                                col_nav1, col_nav2, col_nav3 = st.columns([1,2,1])
                                with col_nav1:
                                    if st.button("⏪ السابق", disabled=st.session_state.image_page_github == 0):
                                        st.session_state.image_page_github = max(0, st.session_state.image_page_github - 1)
                                        st.rerun()
                                with col_nav2:
                                    st.caption(f"الصفحة {st.session_state.image_page_github + 1} من {total_pages}")
                                with col_nav3:
                                    if st.button("التالي ⏩", disabled=st.session_state.image_page_github == total_pages - 1):
                                        st.session_state.image_page_github = min(total_pages - 1, st.session_state.image_page_github + 1)
                                        st.rerun()
                                start_idx = st.session_state.image_page_github * images_per_page
                                end_idx = min(start_idx + images_per_page, len(filtered))
                                for i in range(start_idx, end_idx, 3):
                                    cols = st.columns(3)
                                    for j in range(3):
                                        idx = i + j
                                        if idx < end_idx:
                                            content = filtered[idx]
                                            with cols[j]:
                                                raw_url = f"{GITHUB_RAW_BASE}{content.path}"
                                                st.image(raw_url, caption=content.name, use_column_width=True)
                                                if st.button(f"🗑 حذف", key=f"delete_github_{content.name}"):
                                                    repo.delete_file(content.path, f"Delete image {content.name}", content.sha, branch=APP_CONFIG["BRANCH"])
                                                    st.success(f"✅ تم حذف {content.name}")
                                                    st.rerun()
                        else:
                            st.info("ℹ️ لا توجد صور في مجلد event_images على GitHub")
                    except GithubException as e:
                        if e.status == 404:
                            st.info("ℹ️ مجلد event_images غير موجود بعد. سيتم إنشاؤه عند رفع أول صورة.")
                        else:
                            st.error(f"❌ خطأ في الوصول إلى GitHub: {e}")
                else:
                    st.warning("⚠ لا يمكن الاتصال بـ GitHub. تأكد من توفر token.")
