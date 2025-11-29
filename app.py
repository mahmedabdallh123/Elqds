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

# محاولة استيراد PyGithub
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق
# ===============================
APP_CONFIG = {
    "APP_TITLE": "CMMS - Elqds",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "elquds.xlsx",
    "LOCAL_FILE": "elquds.xlsx",
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم", "🛠 تعديل البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# ===============================
# 🧩 الدوال الأساسية
# ===============================
def load_users():
    """تحميل بيانات المستخدمين"""
    if not os.path.exists(USERS_FILE):
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
            return json.load(f)
    except Exception as e:
        st.error(f"❌ خطأ في تحميل المستخدمين: {e}")
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "permissions": ["all"]
            }
        }

def save_users(users):
    """حفظ بيانات المستخدمين"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ المستخدمين: {e}")
        return False

def load_state():
    """تحميل حالة الجلسات"""
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
    """حفظ حالة الجلسات"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    """تنظيف الجلسات المنتهية"""
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
    """الوقت المتبقي للجلسة"""
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
    """تسجيل الخروج"""
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
    """واجهة تسجيل الدخول"""
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

def fetch_from_github_requests():
    """تحميل الملف من GitHub باستخدام requests"""
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
    """تحميل الملف من GitHub باستخدام API"""
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

@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات"""
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
    """تحميل الشيتات للتحرير"""
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
    """حفظ الملف محلياً ورفعه إلى GitHub"""
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

    # حاول الرفع إلى GitHub
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
            result = repo.update_file(
                path=APP_CONFIG["FILE_PATH"], 
                message=commit_message, 
                content=content, 
                sha=contents.sha, 
                branch=APP_CONFIG["BRANCH"]
            )
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح: {commit_message}")
            return load_sheets_for_edit()
        except Exception as e:
            # حاول رفع كملف جديد
            try:
                result = repo.create_file(
                    path=APP_CONFIG["FILE_PATH"], 
                    message=commit_message, 
                    content=content, 
                    branch=APP_CONFIG["BRANCH"]
                )
                st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                return load_sheets_for_edit()
            except Exception as create_error:
                st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                return None

    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    """حفظ تلقائي إلى GitHub"""
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات تلقائياً في GitHub")
        return result
    else:
        st.error("❌ فشل الحفظ التلقائي")
        return sheets_dict

def normalize_name(s):
    """تطبيع الأسماء"""
    if s is None: return ""
    s = str(s).replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    """تقسيم الخدمات المطلوبة"""
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم"""
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
        return {
            "can_view": True,
            "can_edit": False,
            "can_manage_users": False,
            "can_see_tech_support": False
        }

# ===============================
# 🖥 واجهة فحص السيرفيس
# ===============================
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return
    
    card_df = all_sheets[card_sheet_name]

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح"),
        horizontal=True,
        key=f"service_view_{card_num}"
    )

    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[
            (service_plan_df["Min_Tones"] <= current_tons) & 
            (service_plan_df["Max_Tones"] >= current_tons)
        ]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة")
        return

    all_results = []
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)

        # البحث عن الصفوف المطابقة
        mask = (
            (card_df.get("Min_Tones", 0).fillna(0) <= slice_max) & 
            (card_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        )
        matching_rows = card_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                # تحديد الخدمات المنجزة
                done_services = []
                for col in card_df.columns:
                    if col.lower() in ["min_tones", "max_tones", "tones", "date", "event", "correction", "servised by", "card"]:
                        continue
                    val = str(row.get(col, "")).strip()
                    if val and val not in ["", "nan", "none", "0", "no", "false"]:
                        if val.lower() not in ["x", "-"]:
                            done_services.append(col)

                # مقارنة الخدمات
                not_done = [p for p in needed_parts if p not in done_services]
                
                all_results.append({
                    "Card Number": card_num,
                    "Min_Tons": slice_min,
                    "Max_Tons": slice_max,
                    "Service Needed": " + ".join(needed_parts),
                    "Service Done": ", ".join(done_services),
                    "Service Didn't Done": ", ".join(not_done),
                    "Tones": row.get("Tones", "-"),
                    "Date": row.get("Date", "-")
                })
        else:
            all_results.append({
                "Card Number": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts),
                "Service Done": "-",
                "Service Didn't Done": ", ".join(needed_parts),
                "Tones": "-",
                "Date": "-"
            })

    result_df = pd.DataFrame(all_results)
    st.markdown("### 📋 نتائج فحص السيرفيس")
    st.dataframe(result_df, use_container_width=True)

# ===============================
# 🖥 واجهة فحص الإيفينت والكوريكشن (منفصلة عن الـ Tons)
# ===============================
def check_events_and_corrections(card_num, all_sheets):
    """فحص الإيفينت والكوريكشن - منفصلة عن الـ Tons"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    card_sheet_name = f"Card{card_num}"
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return
    
    card_df = all_sheets[card_sheet_name]

    st.subheader("🔍 خيارات البحث")
    
    col1, col2 = st.columns(2)
    with col1:
        search_date = st.text_input("البحث بالتاريخ:", "", key=f"date_events_{card_num}")
    with col2:
        search_event = st.text_input("البحث بالإيفينت:", "", key=f"event_events_{card_num}")
    
    col3, col4 = st.columns(2)
    with col3:
        search_correction = st.text_input("البحث بالكوريكشن:", "", key=f"correction_events_{card_num}")
    with col4:
        search_technician = st.text_input("البحث بفني الخدمة:", "", key=f"tech_events_{card_num}")

    # فلترة البيانات
    filtered_df = card_df.copy()
    
    # البحث في التاريخ
    if search_date:
        filtered_df = filtered_df[filtered_df.astype(str).apply(
            lambda row: row.str.contains(search_date, case=False, na=False).any(), axis=1
        )]
    
    # البحث في الإيفينت
    if search_event:
        event_cols = [col for col in filtered_df.columns if "event" in col.lower()]
        if event_cols:
            mask = filtered_df[event_cols[0]].astype(str).str.contains(search_event, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    # البحث في الكوريكشن
    if search_correction:
        correction_cols = [col for col in filtered_df.columns if "correction" in col.lower()]
        if correction_cols:
            mask = filtered_df[correction_cols[0]].astype(str).str.contains(search_correction, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    # البحث في فني الخدمة
    if search_technician:
        tech_cols = [col for col in filtered_df.columns if any(x in col.lower() for x in ["servised", "serviced", "فني", "خدمة"])]
        if tech_cols:
            mask = filtered_df[tech_cols[0]].astype(str).str.contains(search_technician, case=False, na=False)
            filtered_df = filtered_df[mask]

    # استخراج النتائج (منفصلة عن الـ Tons)
    events_results = []
    for _, row in filtered_df.iterrows():
        # الحصول على البيانات
        card = row.get("card", "-")
        date = row.get("Date", "-")
        
        # البحث عن الإيفينت
        event_value = "-"
        event_cols = [col for col in card_df.columns if "event" in col.lower()]
        if event_cols:
            event_val = row.get(event_cols[0])
            if pd.notna(event_val) and str(event_val).strip():
                event_value = str(event_val)
        
        # البحث عن الكوريكشن
        correction_value = "-"
        correction_cols = [col for col in card_df.columns if "correction" in col.lower()]
        if correction_cols:
            correction_val = row.get(correction_cols[0])
            if pd.notna(correction_val) and str(correction_val).strip():
                correction_value = str(correction_val)
        
        # البحث عن فني الخدمة
        technician_value = "-"
        tech_cols = [col for col in card_df.columns if any(x in col.lower() for x in ["servised", "serviced", "فني", "خدمة"])]
        if tech_cols:
            tech_val = row.get(tech_cols[0])
            if pd.notna(tech_val) and str(tech_val).strip():
                technician_value = str(tech_val)

        # إضافة النتيجة إذا كان هناك بيانات
        if any(x != "-" and x not in ["", "nan", "None"] for x in [event_value, correction_value, technician_value]):
            events_results.append({
                "Card Number": card,
                "Event": event_value,
                "Correction": correction_value,
                "Servised by": technician_value,
                "Date": date
            })

    events_df = pd.DataFrame(events_results)
    
    if events_df.empty:
        st.info("ℹ️ لا توجد أحداث أو تصحيحات مطابقة لمعايير البحث.")
    else:
        st.markdown("### 📋 نتائج فحص الإيفينت والكوريكشن")
        st.dataframe(events_df, use_container_width=True)

        # تنزيل النتائج
        buffer = io.BytesIO()
        events_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Events_Corrections_Card{card_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ===============================
# 🖥 واجهة تعديل البيانات
# ===============================
def edit_data_interface(sheets_edit):
    """واجهة تعديل البيانات"""
    st.header("🛠 تعديل البيانات")
    
    if sheets_edit is None:
        st.warning("❗ الملف غير موجود. استخدم زر التحديث أولاً.")
        return
    
    # تبويبات التعديل
    tab1, tab2, tab3, tab4 = st.tabs(["✏ تعديل مباشر", "➕ إضافة إيفينت", "➕ إضافة صف كامل", "🗑 حذف بيانات"])
    
    with tab1:
        st.subheader("تعديل مباشر للشيتات")
        sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet_select")
        
        if sheet_name:
            df = sheets_edit[sheet_name].fillna("")
            st.write(f"### تعديل شيت: {sheet_name}")
            
            # عرض البيانات الحالية للتحرير
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{sheet_name}")
            
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}"):
                sheets_edit[sheet_name] = edited_df
                new_sheets = auto_save_to_github(sheets_edit, f"تعديل شيت {sheet_name}")
                if new_sheets is not None:
                    st.success("✅ تم حفظ التغييرات بنجاح!")
                    st.rerun()
    
    with tab2:
        st.subheader("إضافة إيفينت جديد")
        
        sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
        if sheet_name:
            df = sheets_edit[sheet_name]
            
            col1, col2 = st.columns(2)
            with col1:
                card_num = st.text_input("رقم الماكينة:", key="new_card")
                event_text = st.text_area("نص الإيفينت:", key="new_event")
            with col2:
                correction_text = st.text_area("نص الكوريكشن:", key="new_correction")
                technician = st.text_input("فني الخدمة:", key="new_tech")
            
            event_date = st.text_input("التاريخ:", key="new_date")
            
            if st.button("➕ إضافة الإيفينت", key="add_event_btn"):
                if not card_num.strip():
                    st.warning("⚠ الرجاء إدخال رقم الماكينة")
                    return
                
                # إنشاء صف جديد
                new_row = {"card": card_num.strip()}
                
                if event_date.strip():
                    new_row["Date"] = event_date.strip()
                
                # إضافة الإيفينت
                event_cols = [col for col in df.columns if "event" in col.lower()]
                if event_cols and event_text.strip():
                    new_row[event_cols[0]] = event_text.strip()
                
                # إضافة الكوريكشن
                correction_cols = [col for col in df.columns if "correction" in col.lower()]
                if correction_cols and correction_text.strip():
                    new_row[correction_cols[0]] = correction_text.strip()
                
                # إضافة فني الخدمة
                tech_cols = [col for col in df.columns if any(x in col.lower() for x in ["servised", "serviced", "فني", "خدمة"])]
                if tech_cols and technician.strip():
                    new_row[tech_cols[0]] = technician.strip()
                
                # إضافة الصف الجديد
                new_row_df = pd.DataFrame([new_row])
                df_new = pd.concat([df, new_row_df], ignore_index=True)
                sheets_edit[sheet_name] = df_new
                
                new_sheets = auto_save_to_github(sheets_edit, f"إضافة إيفينت جديد في {sheet_name}")
                if new_sheets is not None:
                    st.success("✅ تم إضافة الإيفينت بنجاح!")
                    st.rerun()
    
    with tab3:
        st.subheader("إضافة صف كامل")
        sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_row_sheet")
        
        if sheet_name:
            df = sheets_edit[sheet_name]
            st.info("أدخل بيانات الصف الجديد:")
            
            new_data = {}
            cols = st.columns(3)
            for i, col in enumerate(df.columns):
                with cols[i % 3]:
                    new_data[col] = st.text_input(f"{col}:", key=f"new_{sheet_name}_{col}")
            
            if st.button("➕ إضافة الصف", key="add_row_btn"):
                new_row_df = pd.DataFrame([new_data])
                df_new = pd.concat([df, new_row_df], ignore_index=True)
                sheets_edit[sheet_name] = df_new
                
                new_sheets = auto_save_to_github(sheets_edit, f"إضافة صف جديد في {sheet_name}")
                if new_sheets is not None:
                    st.success("✅ تم إضافة الصف بنجاح!")
                    st.rerun()
    
    with tab4:
        st.subheader("حذف بيانات")
        sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="delete_sheet")
        
        if sheet_name:
            df = sheets_edit[sheet_name]
            st.dataframe(df, use_container_width=True)
            
            row_num = st.number_input("رقم الصف للحذف (ابدأ من 0):", min_value=0, max_value=len(df)-1, key="delete_row")
            
            if st.button("🗑 حذف الصف", key="delete_btn"):
                df_new = df.drop(row_num).reset_index(drop=True)
                sheets_edit[sheet_name] = df_new
                
                new_sheets = auto_save_to_github(sheets_edit, f"حذف صف {row_num} من {sheet_name}")
                if new_sheets is not None:
                    st.success("✅ تم حذف الصف بنجاح!")
                    st.rerun()

# ===============================
# 🖥 واجهة البحث المتقدم
# ===============================
def advanced_search_interface(all_sheets):
    """واجهة البحث المتقدم"""
    st.header("🔍 بحث متقدم")
    
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        search_card = st.number_input("رقم الماكينة (اختياري):", min_value=1, value=None, key="adv_card")
        search_text = st.text_input("نص البحث:", key="adv_text")
    with col2:
        search_date = st.text_input("البحث بالتاريخ:", key="adv_date")
        search_technician = st.text_input("البحث بفني الخدمة:", key="adv_tech")
    
    search_type = st.radio("نوع البحث:", ["الخدمات", "الأحداث والتصحيحات", "الك"], horizontal=True, key="adv_type")
    
    if st.button("🔍 بدء البحث", key="adv_search_btn"):
        all_results = []
        
        # تحديد الشيتات للبحث
        if search_card:
            sheet_names = [f"Card{search_card}"]
        else:
            sheet_names = [name for name in all_sheets.keys() if name.startswith("Card")]
        
        for sheet_name in sheet_names:
            if sheet_name not in all_sheets:
                continue
                
            df = all_sheets[sheet_name]
            card_num = sheet_name.replace("Card", "")
            
            if search_type == "الخدمات":
                # البحث في الخدمات
                for _, row in df.iterrows():
                    if search_text and not any(search_text.lower() in str(val).lower() for val in row.values if pd.notna(val)):
                        continue
                    
                    if search_date and search_date not in str(row.get("Date", "")):
                        continue
                    
                    if search_technician:
                        tech_cols = [col for col in df.columns if any(x in col.lower() for x in ["servised", "serviced", "فني", "خدمة"])]
                        if tech_cols and search_technician not in str(row.get(tech_cols[0], "")):
                            continue
                    
                    # استخراج بيانات السيرفيس
                    all_results.append({
                        "Card": card_num,
                        "Min_Tons": row.get("Min_Tones", "-"),
                        "Max_Tons": row.get("Max_Tones", "-"),
                        "Tones": row.get("Tones", "-"),
                        "Date": row.get("Date", "-"),
                        "Type": "Service"
                    })
            
            elif search_type == "الأحداث والتصحيحات":
                # البحث في الأحداث والتصحيحات
                for _, row in df.iterrows():
                    has_event = any(pd.notna(row.get(col, "")) and str(row.get(col, "")).strip() for col in df.columns if "event" in col.lower())
                    has_correction = any(pd.notna(row.get(col, "")) and str(row.get(col, "")).strip() for col in df.columns if "correction" in col.lower())
                    
                    if has_event or has_correction:
                        if search_text and not any(search_text.lower() in str(val).lower() for val in row.values if pd.notna(val)):
                            continue
                        
                        if search_date and search_date not in str(row.get("Date", "")):
                            continue
                        
                        if search_technician:
                            tech_cols = [col for col in df.columns if any(x in col.lower() for x in ["servised", "serviced", "فني", "خدمة"])]
                            if tech_cols and search_technician not in str(row.get(tech_cols[0], "")):
                                continue
                        
                        # استخراج بيانات الإيفينت والكوريكشن
                        event_value = "-"
                        event_cols = [col for col in df.columns if "event" in col.lower()]
                        if event_cols:
                            event_val = row.get(event_cols[0])
                            if pd.notna(event_val):
                                event_value = str(event_val)
                        
                        correction_value = "-"
                        correction_cols = [col for col in df.columns if "correction" in col.lower()]
                        if correction_cols:
                            correction_val = row.get(correction_cols[0])
                            if pd.notna(correction_val):
                                correction_value = str(correction_val)
                        
                        all_results.append({
                            "Card": card_num,
                            "Date": row.get("Date", "-"),
                            "Event": event_value,
                            "Correction": correction_value,
                            "Type": "Event/Correction"
                        })
        
        if all_results:
            results_df = pd.DataFrame(all_results)
            st.markdown("### 📋 نتائج البحث")
            st.dataframe(results_df, use_container_width=True)
            
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

# ===============================
# 🖥 واجهة إدارة المستخدمين
# ===============================
def users_management_interface():
    """واجهة إدارة المستخدمين"""
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    
    # عرض المستخدمين الحاليين
    st.subheader("📋 المستخدمون الحاليون")
    if users:
        user_data = []
        for username, info in users.items():
            user_data.append({
                "اسم المستخدم": username,
                "الدور": info.get("role", "user"),
                "الصلاحيات": ", ".join(info.get("permissions", [])),
                "تاريخ الإنشاء": info.get("created_at", "غير معروف")
            })
        
        users_df = pd.DataFrame(user_data)
        st.dataframe(users_df, use_container_width=True)
    else:
        st.info("لا يوجد مستخدمين مسجلين بعد.")
    
    # إضافة مستخدم جديد
    st.subheader("➕ إضافة مستخدم جديد")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        new_username = st.text_input("اسم المستخدم الجديد:", key="new_username")
    with col2:
        new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
    with col3:
        user_role = st.selectbox("الدور:", ["admin", "editor", "viewer"], key="user_role")
    
    if st.button("إضافة مستخدم", key="add_user"):
        if not new_username.strip() or not new_password.strip():
            st.warning("⚠ الرجاء إدخال اسم المستخدم وكلمة المرور.")
        elif new_username in users:
            st.warning("⚠ هذا المستخدم موجود بالفعل.")
        else:
            # تحديد الصلاحيات بناءً على الدور
            if user_role == "admin":
                permissions_list = ["all"]
            elif user_role == "editor":
                permissions_list = ["view", "edit"]
            else:  # viewer
                permissions_list = ["view"]
            
            users[new_username] = {
                "password": new_password,
                "role": user_role,
                "permissions": permissions_list,
                "created_at": datetime.now().isoformat()
            }
            if save_users(users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح.")
                st.rerun()
            else:
                st.error("❌ حدث خطأ أثناء حفظ بيانات المستخدم.")
    
    # حذف مستخدم
    st.subheader("🗑 حذف مستخدم")
    
    if len(users) > 1:
        user_to_delete = st.selectbox(
            "اختر مستخدم للحذف:",
            [u for u in users.keys() if u != "admin"],
            key="delete_user_select"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            confirm_delete = st.checkbox("✅ تأكيد الحذف", key="confirm_user_delete")
        with col2:
            if st.button("حذف المستخدم", key="delete_user_btn"):
                if not confirm_delete:
                    st.warning("⚠ يرجى تأكيد الحذف أولاً.")
                elif user_to_delete == "admin":
                    st.error("❌ لا يمكن حذف المستخدم admin.")
                elif user_to_delete == st.session_state.get("username"):
                    st.error("❌ لا يمكن حذف حسابك أثناء تسجيل الدخول.")
                else:
                    if user_to_delete in users:
                        del users[user_to_delete]
                        if save_users(users):
                            st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح.")
                            st.rerun()
                        else:
                            st.error("❌ حدث خطأ أثناء حفظ التغييرات.")
    else:
        st.info("لا يمكن حذف جميع المستخدمين. يجب أن يبقى مستخدم واحد على الأقل.")

# ===============================
# 🖥 واجهة الدعم الفني
# ===============================
def tech_support_interface():
    """واجهة الدعم الفني"""
    st.header("📞 الدعم الفني")
    
    st.markdown("## 🛠 معلومات التطوير والدعم")
    st.markdown("تم تطوير هذا التطبيق بواسطة:")
    st.markdown("### م. محمد عبدالله")
    st.markdown("### رئيس قسم الكرد والمحطات")
    st.markdown("### مصنع بيل يارن للغزل")
    st.markdown("---")
    st.markdown("### معلومات الاتصال:")
    st.markdown("- 📧 البريد الإلكتروني: medotatch124@gmail.com")
    st.markdown("- 📞 هاتف: 01274424062")
    st.markdown("- 🏢 الموقع: مصنع بيل يارن للغزل")
    st.markdown("---")
    st.markdown("### خدمات الدعم الفني:")
    st.markdown("- 🔧 صيانة وتحديث النظام")
    st.markdown("- 📊 تطوير تقارير إضافية")
    st.markdown("- 🐛 إصلاح الأخطاء والمشكلات")
    st.markdown("- 💡 استشارات فنية وتقنية")
    st.markdown("---")
    st.markdown("### إصدار النظام:")
    st.markdown("- الإصدار: 1.0")
    st.markdown("- آخر تحديث: 2025")
    st.markdown("- النظام: نظام سيرفيس كرد ترتشلر")
    
    st.info("ملاحظة: في حالة مواجهة أي مشاكل تقنية أو تحتاج إلى إضافة ميزات جديدة، يرجى التواصل مع قسم الدعم الفني.")

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
def main():
    st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
    
    # الشريط الجانبي
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

    # المحتوى الرئيسي
    st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

    # التحقق من الصلاحيات
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    user_permissions = st.session_state.get("user_permissions", ["view"])
    permissions = get_user_permissions(user_role, user_permissions)

    # تحميل البيانات
    all_sheets = load_all_sheets()
    sheets_edit = load_sheets_for_edit()

    # تحديد التبويبات بناءً على الصلاحيات
    if permissions["can_manage_users"]:
        tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
    elif permissions["can_edit"]:
        tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم", "🛠 تعديل البيانات"])
    else:
        tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🔍 بحث متقدم"])

    # تبويب فحص السيرفيس
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

    # تبويب فحص الإيفينت والكوريكشن
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

    # تبويب البحث المتقدم
    with tabs[2]:
        advanced_search_interface(all_sheets)

    # تبويب تعديل البيانات
    if permissions["can_edit"] and len(tabs) > 3:
        with tabs[3]:
            edit_data_interface(sheets_edit)

    # تبويب إدارة المستخدمين
    if permissions["can_manage_users"] and len(tabs) > 4:
        with tabs[4]:
            users_management_interface()

    # تبويب الدعم الفني
    if permissions["can_manage_users"] and len(tabs) > 5:
        with tabs[5]:
            tech_support_interface()

if __name__ == "__main__":
    main()
