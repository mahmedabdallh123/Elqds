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
# ⏱️ التحليل الزمني المبسط للأحداث
# ===============================
def parse_arabic_date(date_str):
    """تحويل التاريخ العربي إلى كائن datetime"""
    if not date_str or pd.isna(date_str) or str(date_str).strip() == "-":
        return None
    
    date_str = str(date_str).strip()
    
    # تحويل الأرقام العربية إلى إنجليزية
    arabic_to_english = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        '/': '/', '-': '-', '.': '.', '\\': '/'
    }
    
    # تحويل الأرقام
    converted_date = ""
    for char in date_str:
        converted_date += arabic_to_english.get(char, char)
    
    # أنماط التاريخ المحتملة
    date_patterns = [
        r'(\d{1,2})[/\-\\](\d{1,2})[/\-\\](\d{2,4})',  # 20/5/2025 أو 20-5-2025
        r'(\d{2,4})[/\-\\](\d{1,2})[/\-\\](\d{1,2})',  # 2025/5/20
        r'(\d{1,2})[/\-\\](\d{1,2})[/\-\\](\d{2})',    # 20/5/25
        r'(\d{4})[/\-\\](\d{2})[/\-\\](\d{2})',        # 2025-05-20
    ]
    
    for pattern in date_patterns:
        match = re.match(pattern, converted_date)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                try:
                    # محاولة تحويل إلى datetime
                    if len(groups[2]) == 4:  # سنة كاملة
                        day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        if day > 31 or month > 12:
                            continue
                        return datetime(year, month, day)
                    else:  # سنة مكونة من رقمين
                        day, month, year_short = int(groups[0]), int(groups[1]), int(groups[2])
                        if day > 31 or month > 12:
                            continue
                        year = 2000 + year_short if year_short < 100 else year_short
                        return datetime(year, month, day)
                except:
                    continue
    
    return None

def analyze_event_time_intervals_simple(results_df, event_keyword):
    """تحليل بسيط للفترات الزمنية بين الأحداث"""
    if results_df.empty or 'Event' not in results_df.columns or 'Date' not in results_df.columns:
        return None
    
    # فلترة الأحداث التي تحتوي على الكلمة المطلوبة
    filtered_events = results_df[results_df['Event'].str.contains(event_keyword, case=False, na=False)].copy()
    
    if filtered_events.empty:
        return None
    
    # تحليل التواريخ
    filtered_events['Parsed_Date'] = filtered_events['Date'].apply(parse_arabic_date)
    filtered_events = filtered_events[filtered_events['Parsed_Date'].notna()]
    
    if filtered_events.empty:
        return None
    
    # ترتيب حسب التاريخ
    filtered_events = filtered_events.sort_values('Parsed_Date')
    
    # تجميع حسب الماكينة
    intervals_data = []
    
    for machine in filtered_events['Card Number'].unique():
        machine_events = filtered_events[filtered_events['Card Number'] == machine]
        machine_events = machine_events.sort_values('Parsed_Date')
        
        if len(machine_events) > 1:
            for i in range(len(machine_events) - 1):
                current = machine_events.iloc[i]
                next_event = machine_events.iloc[i + 1]
                
                days_between = (next_event['Parsed_Date'] - current['Parsed_Date']).days
                
                intervals_data.append({
                    'الماكينة': machine,
                    'الحدث الأول': current['Event'][:50] + '...' if len(str(current['Event'])) > 50 else current['Event'],
                    'التاريخ الأول': current['Date'],
                    'الحدث التالي': next_event['Event'][:50] + '...' if len(str(next_event['Event'])) > 50 else next_event['Event'],
                    'التاريخ التالي': next_event['Date'],
                    'الأيام بينهما': days_between,
                    'الأسابيع بينهما': round(days_between / 7, 1),
                    'الأشهر بينهما': round(days_between / 30, 1)
                })
    
    if not intervals_data:
        return None
    
    intervals_df = pd.DataFrame(intervals_data)
    
    # حساب الإحصائيات
    if len(intervals_df) > 0:
        stats = {
            'عدد الفترات': len(intervals_df),
            'أقصر فترة (يوم)': intervals_df['الأيام بينهما'].min(),
            'أطول فترة (يوم)': intervals_df['الأيام بينهما'].max(),
            'متوسط الفترة (يوم)': round(intervals_df['الأيام بينهما'].mean(), 1),
            'الوسيط (يوم)': intervals_df['الأيام بينهما'].median(),
            'متوسط الأسابيع': round(intervals_df['الأيام بينهما'].mean() / 7, 1),
            'متوسط الأشهر': round(intervals_df['الأيام بينهما'].mean() / 30, 1)
        }
    else:
        stats = None
    
    return {
        'event_keyword': event_keyword,
        'total_events': len(filtered_events),
        'unique_machines': filtered_events['Card Number'].nunique(),
        'intervals_df': intervals_df,
        'stats': stats,
        'filtered_events': filtered_events
    }

def display_time_analysis_simple(analysis_result):
    """عرض نتائج التحليل الزمني المبسط"""
    if not analysis_result:
        return
    
    st.markdown(f"### ⏱️ التحليل الزمني لكلمة: **{analysis_result['event_keyword']}**")
    
    # عرض الإحصائيات الأساسية
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔄 عدد التكرارات", analysis_result['total_events'])
    
    with col2:
        st.metric("🔢 عدد الماكينات", analysis_result['unique_machines'])
    
    with col3:
        if analysis_result['stats']:
            st.metric("📊 متوسط الأيام", analysis_result['stats']['متوسط الفترة (يوم)'])
    
    with col4:
        if analysis_result['stats']:
            st.metric("📈 عدد الفترات", analysis_result['stats']['عدد الفترات'])
    
    st.markdown("---")
    
    if analysis_result['stats']:
        st.markdown("#### 📊 الإحصائيات التفصيلية")
        
        stats_df = pd.DataFrame({
            'المقياس': list(analysis_result['stats'].keys()),
            'القيمة': list(analysis_result['stats'].values())
        })
        
        st.dataframe(stats_df, use_container_width=True)
    
    if not analysis_result['intervals_df'].empty:
        st.markdown("#### 📋 جدول الفترات الزمنية")
        
        # فلترة حسب عدد الأيام
        st.markdown("##### 🔍 فلترة حسب عدد الأيام")
        col1, col2 = st.columns(2)
        with col1:
            min_days = st.number_input("الحد الأدنى للأيام:", min_value=0, value=0, step=1, key="min_days_filter")
        with col2:
            max_days = st.number_input("الحد الأقصى للأيام:", min_value=min_days, value=365, step=1, key="max_days_filter")
        
        filtered_intervals = analysis_result['intervals_df'][
            (analysis_result['intervals_df']['الأيام بينهما'] >= min_days) & 
            (analysis_result['intervals_df']['الأيام بينهما'] <= max_days)
        ]
        
        st.dataframe(
            filtered_intervals.sort_values('الأيام بينهما'),
            use_container_width=True,
            height=400
        )
        
        # خيارات التصدير
        st.markdown("---")
        buffer = io.BytesIO()
        filtered_intervals.to_excel(buffer, index=False, engine='openpyxl')
        
        st.download_button(
            label="📊 حفظ الفترات الزمنية كـ Excel",
            data=buffer.getvalue(),
            file_name=f"فترات_زمنية_{analysis_result['event_keyword']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info(f"⚠ تم العثور على {analysis_result['total_events']} حدث يحتوي على '{analysis_result['event_keyword']}'، لكن لا يمكن حساب الفترات الزمنية (يحتاج إلى حدثين على الأقل لكل ماكينة).")
        
        # عرض الأحداث المباشرة
        st.markdown("#### 📋 قائمة الأحداث:")
        display_events_table_simple(analysis_result['filtered_events'])

def display_events_table_simple(filtered_df):
    """عرض جدول الأحداث مباشرة"""
    if filtered_df.empty:
        return
    
    display_cols = ['Card Number', 'Event', 'Date', 'Servised by']
    display_cols = [col for col in display_cols if col in filtered_df.columns]
    
    st.dataframe(
        filtered_df[display_cols].sort_values('Date'),
        use_container_width=True,
        height=300
    )

# ===============================
# 🔍 فحص الإيفينت والكوريكشن مع التحليل الزمني المبسط
# ===============================
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن مع تحليل زمني مبسط"""
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
            "sort_by": "رقم الماكينة"
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    # قسم البحث
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
    
    # خيارات متقدمة
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
    
    # أزرار البحث
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
    
    # تحديث معايير البحث
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
        
        search_params = st.session_state.search_params.copy()
        
        # تنفيذ البحث
        search_results = perform_search(search_params, all_sheets)
        
        if search_results is not None and not search_results.empty:
            display_search_results(search_results, search_params)
            
            # إضافة قسم التحليل الزمني المبسط
            add_simple_time_analysis_section(search_results)
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
        
        # فلترة أرقام الماكينات
        if search_params["card_numbers"]:
            target_numbers = parse_card_numbers(search_params["card_numbers"])
            if target_numbers and card_num not in target_numbers:
                continue
        
        df = all_sheets[sheet_name].copy()
        
        # فلترة فنيي الخدمة
        target_techs = []
        if search_params["tech_names"]:
            techs = search_params["tech_names"].split(',')
            target_techs = [tech.strip().lower() for tech in techs if tech.strip()]
        
        # فلترة التواريخ
        target_dates = []
        if search_params["date_range"]:
            dates = search_params["date_range"].split(',')
            target_dates = [date.strip().lower() for date in dates if date.strip()]
        
        # فلترة نص البحث
        search_terms = []
        if search_params["search_text"]:
            terms = search_params["search_text"].split(',')
            search_terms = [term.strip().lower() for term in terms if term.strip()]
        
        for _, row in df.iterrows():
            # التحقق من فني الخدمة
            if target_techs:
                row_tech = get_servised_by_value(row).lower()
                if row_tech == "-" and not search_params["include_empty"]:
                    continue
                
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
                    continue
            
            # التحقق من التاريخ
            if target_dates:
                row_date = str(row.get("Date", "")).strip().lower() if pd.notna(row.get("Date")) else ""
                if not row_date and not search_params["include_empty"]:
                    continue
                
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
                    continue
            
            # استخراج الحدث والتصحيح
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
            
            # التحقق من نص البحث في الحدث أو التصحيح
            if search_terms:
                if not event_value and not correction_value and not search_params["include_empty"]:
                    continue
                
                text_match = False
                combined_text = f"{event_value.lower()} {correction_value.lower()}"
                
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
            
            # إذا كانت كل الحقول فارغة، نتجاهل الصف
            if (event_value == "-" and correction_value == "-"):
                continue
            
            # استخراج البيانات
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
    
    # تنظيف البيانات للترتيب
    display_df['Card_Number_Clean'] = pd.to_numeric(display_df['Card Number'], errors='coerce')
    display_df['Date_Clean'] = pd.to_datetime(display_df['Date'], errors='coerce', dayfirst=True)
    
    # ترتيب النتائج
    if search_params["sort_by"] == "التاريخ":
        display_df = display_df.sort_values(by=['Date_Clean', 'Card_Number_Clean'], 
                                          ascending=[False, True], na_position='last')
    elif search_params["sort_by"] == "فني الخدمة":
        display_df = display_df.sort_values(by=['Servised by', 'Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, True, False], na_position='last')
    else:
        display_df = display_df.sort_values(by=['Card_Number_Clean', 'Date_Clean'], 
                                          ascending=[True, False], na_position='last')
    
    # عرض الإحصائيات
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
    
    # عرض النتائج
    st.markdown("### 📋 النتائج التفصيلية")
    
    # تحديد الأعمدة للعرض
    columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date']
    columns_to_show = [col for col in columns_to_show if col in display_df.columns]
    
    st.dataframe(
        display_df[columns_to_show],
        use_container_width=True,
        height=500
    )
    
    # خيارات التصدير
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

def add_simple_time_analysis_section(results_df):
    """إضافة قسم التحليل الزمني المبسط"""
    st.markdown("---")
    st.markdown("## ⏱️ التحليل الزمني للأحداث")
    
    st.markdown("#### 🔍 تحليل الفترات الزمنية بين الأحداث")
    
    # إدخال كلمة للبحث
    event_keyword = st.text_input(
        "الكلمة المطلوبة (مثال: سير، محرك، صيانة):",
        placeholder="أدخل كلمة أو جزء من الحدث للتحليل الزمني",
        key="time_analysis_keyword"
    )
    
    if event_keyword and st.button("🔬 تحليل الفترات الزمنية", type="primary"):
        with st.spinner("🔄 جاري تحليل الفترات الزمنية..."):
            analysis_result = analyze_event_time_intervals_simple(results_df, event_keyword)
            
            if analysis_result:
                display_time_analysis_simple(analysis_result)
            else:
                st.warning(f"⚠ لم يتم العثور على أحداث تحتوي على '{event_keyword}' أو لا يمكن تحليل الفترات الزمنية.")

# ===============================
# 🖥 تبويبات التطبيق
# ===============================
def render_service_check_tab(all_sheets):
    """تبويب فحص السيرفيس"""
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
            # استخدام الدالة الأصلية لفحص السيرفيس
            pass

def render_event_check_tab(all_sheets):
    """تبويب فحص الإيفينت والكوريكشن"""
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        check_events_and_corrections(all_sheets)

def render_data_management_tab(sheets_edit, permissions):
    """تبويب إدارة البيانات"""
    st.header("🛠 تعديل وإدارة البيانات")

    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
    else:
        st.info("ℹ️ قسم تعديل البيانات - سيتم تطويره لاحقاً")

def render_user_management_tab():
    """تبويب إدارة المستخدمين"""
    st.header("👥 إدارة المستخدمين")
    st.info("ℹ️ قسم إدارة المستخدمين - سيتم تطويره لاحقاً")

def render_tech_support_tab():
    """تبويب الدعم الفني"""
    st.header("📞 الدعم الفني")
    st.info("ℹ️ قسم الدعم الفني - سيتم تطويره لاحقاً")

# ===============================
# 🏠 الواجهة الرئيسية
# ===============================
def main():
    """الدالة الرئيسية للتطبيق"""
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
    
    # تحميل البيانات
    all_sheets = load_all_sheets()
    sheets_edit = load_sheets_for_edit()
    
    # عنوان التطبيق
    st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
    
    # التحقق من الصلاحيات
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    user_permissions = st.session_state.get("user_permissions", ["view"])
    
    # الحصول على الصلاحيات
    if user_role == "admin":
        permissions = {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    elif user_role == "editor":
        permissions = {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    else:
        permissions = {
            "can_view": True,
            "can_edit": False,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    
    # تحديد التبويبات
    if permissions["can_manage_users"]:  # admin
        tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
        
        with tabs[0]:
            render_service_check_tab(all_sheets)
        
        with tabs[1]:
            render_event_check_tab(all_sheets)
        
        with tabs[2]:
            render_data_management_tab(sheets_edit, permissions)
        
        with tabs[3]:
            render_user_management_tab()
        
        with tabs[4]:
            render_tech_support_tab()
    
    elif permissions["can_edit"]:  # editor
        tabs = st.tabs([
            "📊 فحص السيرفيس", 
            "📋 فحص الإيفينت والكوريكشن", 
            "🛠 تعديل وإدارة البيانات"
        ])
        
        with tabs[0]:
            render_service_check_tab(all_sheets)
        
        with tabs[1]:
            render_event_check_tab(all_sheets)
        
        with tabs[2]:
            render_data_management_tab(sheets_edit, permissions)
    
    else:  # viewer
        tabs = st.tabs([
            "📊 فحص السيرفيس", 
            "📋 فحص الإيفينت والكوريكشن"
        ])
        
        with tabs[0]:
            render_service_check_tab(all_sheets)
        
        with tabs[1]:
            render_event_check_tab(all_sheets)

# تشغيل التطبيق
if __name__ == "__main__":
    main()
