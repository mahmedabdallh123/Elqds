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
from typing import List, Dict, Any, Optional

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

# ===============================
# 🧠 وظائف المصادقة وإدارة المستخدمين
# ===============================
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
# 📁 وظائف إدارة الملفات وGitHub
# ===============================
def fetch_from_github_requests():
    """تحميل بإستخدام رابط RAW (requests)"""
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

@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel"""
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
    """تحميل جميع الشيتات للتحرير"""
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
    """دالة محسنة للحفظ التلقائي المحلي والرفع إلى GitHub"""
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

# ===============================
# 🛠 وظائف مساعدة للمعالجة
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

def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم بناءً على الدور والصلاحيات"""
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
    """استخراج قيمة فني الخدمة من الصف"""
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
# 📊 التحليل الزمني والإحصائي للأحداث
# ===============================
class EventTimeAnalyzer:
    """محلل الفترات الزمنية للأحداث"""
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """تحويل سلسلة التاريخ إلى كائن datetime"""
        if not date_str or str(date_str).lower() in ["nan", "none", "null", "", "-"]:
            return None
        
        date_str = str(date_str).strip()
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d',
            '%d/%m/%y', '%d-%m-%y', '%Y/%m/%d',
            '%d.%m.%Y', '%d.%m.%y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        try:
            return pd.to_datetime(date_str, dayfirst=True)
        except:
            return None
    
    @staticmethod
    def analyze_event_time_intervals(results_df: pd.DataFrame, event_name: str) -> Dict[str, Any]:
        """
        تحليل الفترات الزمنية بين تكرارات حدث معين
        """
        if results_df.empty or 'Date' not in results_df.columns:
            return {}
        
        event_mask = results_df['Event'].str.contains(event_name, case=False, na=False)
        filtered_df = results_df[event_mask].copy()
        
        if filtered_df.empty:
            return {}
        
        # تحليل التواريخ
        filtered_df['Parsed_Date'] = filtered_df['Date'].apply(EventTimeAnalyzer.parse_date)
        filtered_df = filtered_df[filtered_df['Parsed_Date'].notna()]
        
        if filtered_df.empty:
            return {}
        
        filtered_df = filtered_df.sort_values('Parsed_Date')
        
        # حساب الفترات الزمنية
        time_intervals = EventTimeAnalyzer.calculate_time_intervals(filtered_df)
        
        return {
            'event_name': event_name,
            'total_occurrences': len(filtered_df),
            'machines_count': filtered_df['Card Number'].nunique(),
            'time_intervals': time_intervals,
            'filtered_df': filtered_df,
            'statistics': EventTimeAnalyzer.calculate_statistics(time_intervals) if time_intervals else {}
        }
    
    @staticmethod
    def calculate_time_intervals(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """حساب الفترات الزمنية بين الأحداث"""
        intervals = []
        
        machines = df['Card Number'].unique()
        
        for machine in machines:
            machine_events = df[df['Card Number'] == machine].sort_values('Parsed_Date')
            
            if len(machine_events) > 1:
                for i in range(len(machine_events) - 1):
                    current_event = machine_events.iloc[i]
                    next_event = machine_events.iloc[i + 1]
                    
                    current_date = current_event['Parsed_Date']
                    next_date = next_event['Parsed_Date']
                    
                    if current_date and next_date:
                        time_diff = next_date - current_date
                        days_between = time_diff.days
                        
                        intervals.append({
                            'machine': str(machine),
                            'current_event': EventTimeAnalyzer.truncate_text(str(current_event['Event']), 50),
                            'next_event': EventTimeAnalyzer.truncate_text(str(next_event['Event']), 50),
                            'current_date': current_event['Date'],
                            'next_date': next_event['Date'],
                            'current_parsed_date': current_date,
                            'next_parsed_date': next_date,
                            'days_between': days_between,
                            'weeks_between': days_between / 7,
                            'months_between': days_between / 30,
                            'current_tones': current_event.get('Tones', '-'),
                            'next_tones': next_event.get('Tones', '-'),
                            'current_tech': current_event.get('Servised by', '-'),
                            'next_tech': next_event.get('Servised by', '-')
                        })
        
        return intervals
    
    @staticmethod
    def calculate_statistics(intervals: List[Dict[str, Any]]) -> Dict[str, float]:
        """حساب الإحصائيات"""
        if not intervals:
            return {}
        
        days_list = [interval['days_between'] for interval in intervals]
        
        return {
            'min_days': min(days_list),
            'max_days': max(days_list),
            'mean_days': np.mean(days_list),
            'median_days': np.median(days_list),
            'std_days': np.std(days_list),
            'total_intervals': len(days_list),
            'machines_count': len(set([interval['machine'] for interval in intervals]))
        }
    
    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """قص النص إذا كان طويلاً"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    @staticmethod
    def analyze_multiple_events(results_df: pd.DataFrame, event_names: List[str]) -> Dict[str, Any]:
        """تحليل مقارن لعدة أحداث"""
        if results_df.empty:
            return {}
        
        comparison_data = []
        
        for event_name in event_names:
            analysis = EventTimeAnalyzer.analyze_event_time_intervals(results_df, event_name)
            if analysis and analysis.get('statistics'):
                stats = analysis['statistics']
                comparison_data.append({
                    'الحدث': event_name,
                    'التكرارات': analysis['total_occurrences'],
                    'الماكينات': analysis['machines_count'],
                    'متوسط الأيام': stats['mean_days'],
                    'الوسيط': stats['median_days'],
                    'أقصر فترة': stats['min_days'],
                    'أطول فترة': stats['max_days'],
                    'الانحراف المعياري': stats['std_days']
                })
        
        return {
            'comparison_data': comparison_data,
            'total_events_analyzed': len(comparison_data)
        }

# ===============================
# 🖥 واجهة التحليل الزمني للأحداث
# ===============================
def display_time_analysis(analysis_result: Dict[str, Any]):
    """عرض نتائج التحليل الزمني"""
    if not analysis_result:
        return
    
    event_name = analysis_result['event_name']
    stats = analysis_result['statistics']
    intervals = analysis_result['time_intervals']
    filtered_df = analysis_result['filtered_df']
    
    st.markdown(f"### ⏱️ التحليل الزمني لحدث: **{event_name}**")
    
    # عرض الإحصائيات الأساسية
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔄 عدد التكرارات", analysis_result['total_occurrences'])
    
    with col2:
        st.metric("🔢 عدد الماكينات", analysis_result['machines_count'])
    
    with col3:
        if stats:
            st.metric("📊 متوسط الأيام", f"{stats['mean_days']:.1f}")
    
    with col4:
        if stats:
            st.metric("📈 عدد الفترات", stats['total_intervals'])
    
    st.markdown("---")
    
    if not intervals:
        st.info(f"ℹ️ حدث '{event_name}' وُجد في {analysis_result['total_occurrences']} مناسبات، لكن لا يمكن حساب الفترات الزمنية.")
        display_events_table(filtered_df)
        return
    
    # تبويبات لعرض التفاصيل
    tabs = st.tabs(["📊 الإحصائيات التفصيلية", "📈 المخططات الزمنية", "📋 الفترات الزمنية", "🎯 التوصيات"])
    
    with tabs[0]:
        display_detailed_statistics(stats, intervals)
    
    with tabs[1]:
        display_time_charts(intervals, event_name)
    
    with tabs[2]:
        display_intervals_table(intervals)
    
    with tabs[3]:
        display_recommendations(analysis_result)

def display_detailed_statistics(stats: Dict[str, float], intervals: List[Dict[str, Any]]):
    """عرض الإحصائيات التفصيلية"""
    if not stats:
        return
    
    st.markdown("#### 📊 الإحصائيات الزمنية")
    
    stat_data = {
        "المقياس": [
            "أقصر فترة (أيام)",
            "أطول فترة (أيام)",
            "المتوسط الحسابي (أيام)",
            "الوسيط (أيام)",
            "الانحراف المعياري (أيام)",
            "متوسط الأسابيع",
            "متوسط الأشهر"
        ],
        "القيمة": [
            f"{stats['min_days']:.1f}",
            f"{stats['max_days']:.1f}",
            f"{stats['mean_days']:.1f}",
            f"{stats['median_days']:.1f}",
            f"{stats['std_days']:.1f}",
            f"{stats['mean_days'] / 7:.1f}",
            f"{stats['mean_days'] / 30:.1f}"
        ]
    }
    
    stat_df = pd.DataFrame(stat_data)
    st.dataframe(stat_df, use_container_width=True)
    
    # تحليل التوزيع
    st.markdown("#### 📈 تحليل التوزيع")
    
    days_list = [interval['days_between'] for interval in intervals]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        short_intervals = len([d for d in days_list if d < 30])
        st.metric("⏳ فترات قصيرة (<30 يوم)", short_intervals)
    
    with col2:
        medium_intervals = len([d for d in days_list if 30 <= d <= 90])
        st.metric("🕐 فترات متوسطة (30-90 يوم)", medium_intervals)
    
    with col3:
        long_intervals = len([d for d in days_list if d > 90])
        st.metric("⏰ فترات طويلة (>90 يوم)", long_intervals)

def display_time_charts(intervals: List[Dict[str, Any]], event_name: str):
    """عرض المخططات الزمنية"""
    if not intervals:
        return
    
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        
        intervals_df = pd.DataFrame(intervals)
        
        # مخطط توزيع الفترات
        st.markdown("#### 📊 توزيع الفترات الزمنية")
        
        fig1 = px.histogram(
            intervals_df,
            x='days_between',
            nbins=20,
            title=f'توزيع الفترات الزمنية بين تكرارات حدث "{event_name}"',
            labels={'days_between': 'عدد الأيام بين التكرارات'},
            color_discrete_sequence=['#4ECDC4']
        )
        fig1.update_layout(
            xaxis_title="الأيام",
            yaxis_title="عدد الفترات",
            showlegend=False
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # مخطط مربعات (Box Plot)
        st.markdown("#### 📦 مخطط المربعات لتوزيع الفترات")
        
        fig2 = px.box(
            intervals_df,
            y='days_between',
            title='توزيع الفترات الزمنية (مخطط المربعات)',
            labels={'days_between': 'عدد الأيام'}
        )
        fig2.update_layout(
            yaxis_title="الأيام بين التكرارات",
            showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        # مخطط شريطي حسب الماكينة
        if len(intervals_df['machine'].unique()) <= 20:
            st.markdown("#### 🏭 متوسط الفترات حسب الماكينة")
            
            machine_avg = intervals_df.groupby('machine')['days_between'].mean().reset_index()
            machine_avg = machine_avg.sort_values('days_between', ascending=True)
            
            fig3 = px.bar(
                machine_avg,
                x='days_between',
                y='machine',
                orientation='h',
                title='متوسط الفترات الزمنية حسب الماكينة',
                labels={'days_between': 'متوسط الأيام', 'machine': 'رقم الماكينة'},
                color='days_between',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig3, use_container_width=True)
        
    except ImportError:
        st.info("⚠ لم يتم العثور على مكتبة plotly. يمكنك تثبيتها باستخدام: pip install plotly")
        
        # عرض بديل باستخدام streamlit charts
        intervals_df = pd.DataFrame(intervals)
        
        st.markdown("#### 📊 توزيع الفترات الزمنية (بديل)")
        st.bar_chart(intervals_df['days_between'].value_counts().sort_index())
        
        st.markdown("#### 📈 إحصائيات الفترات حسب الماكينة")
        if 'machine' in intervals_df.columns and 'days_between' in intervals_df.columns:
            machine_stats = intervals_df.groupby('machine')['days_between'].agg(['mean', 'min', 'max']).round(1)
            st.dataframe(machine_stats, use_container_width=True)

def display_intervals_table(intervals: List[Dict[str, Any]]):
    """عرض جدول الفترات الزمنية"""
    if not intervals:
        return
    
    st.markdown("#### 📋 جدول الفترات الزمنية المفصلة")
    
    display_data = []
    for interval in intervals:
        display_data.append({
            'الماكينة': interval['machine'],
            'التاريخ الأول': interval['current_date'],
            'الحدث الأول': interval['current_event'],
            'التاريخ التالي': interval['next_date'],
            'الحدث التالي': interval['next_event'],
            'الأيام بينهما': interval['days_between'],
            'الأسابيع بينهما': f"{interval['weeks_between']:.1f}",
            'الأشهر بينهما': f"{interval['months_between']:.1f}",
            'فني الخدمة (الأول)': interval.get('current_tech', '-'),
            'فني الخدمة (التالي)': interval.get('next_tech', '-')
        })
    
    intervals_df = pd.DataFrame(display_data)
    
    # إضافة فلترة
    st.markdown("##### 🔍 فلترة النتائج")
    col1, col2 = st.columns(2)
    
    with col1:
        min_days = st.number_input("الحد الأدنى للأيام:", min_value=0, value=0, step=1)
    
    with col2:
        max_days = st.number_input("الحد الأقصى للأيام:", min_value=min_days, value=365, step=1)
    
    filtered_df = intervals_df[
        (intervals_df['الأيام بينهما'] >= min_days) & 
        (intervals_df['الأيام بينهما'] <= max_days)
    ]
    
    st.dataframe(
        filtered_df.sort_values('الأيام بينهما'),
        use_container_width=True,
        height=400
    )
    
    # خيارات التصدير
    st.markdown("---")
    buffer = io.BytesIO()
    filtered_df.to_excel(buffer, index=False, engine='openpyxl')
    
    st.download_button(
        label="📊 حفظ الفترات الزمنية كـ Excel",
        data=buffer.getvalue(),
        file_name=f"فترات_زمنية_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def display_recommendations(analysis_result: Dict[str, Any]):
    """عرض التوصيات بناءً على التحليل"""
    if not analysis_result or not analysis_result.get('statistics'):
        return
    
    stats = analysis_result['statistics']
    event_name = analysis_result['event_name']
    total_occurrences = analysis_result['total_occurrences']
    
    st.markdown("#### 🎯 التوصيات والتحليلات")
    
    recommendations = []
    
    # تحليل الفترات الزمنية
    mean_days = stats['mean_days']
    std_days = stats['std_days']
    
    if mean_days < 30:
        recommendations.append({
            "التصنيف": "🔄 تكرار سريع",
            "الوصف": f"حدث '{event_name}' يتكرر كل {mean_days:.1f} يوم في المتوسط",
            "التوصية": f"""• مراجعة جدولة الصيانة الوقائية كل {mean_days:.0f} يوم
• فحص جودة التنفيذ
• تقليل الفترات إذا أمكن"""
        })
    elif mean_days < 90:
        recommendations.append({
            "التصنيف": "⚖️ تكرار متوسط",
            "الوصف": f"حدث '{event_name}' يتكرر كل {mean_days:.1f} يوم في المتوسط",
            "التوصية": f"""• مراقبة المؤشرات الدورية كل {mean_days/7:.1f} أسابيع
• تحسين الجدولة الشهرية
• مراجعة قطع الغيار"""
        })
    else:
        recommendations.append({
            "التصنيف": "⏰ تكرار طويل",
            "الوصف": f"حدث '{event_name}' يتكرر كل {mean_days:.1f} يوم في المتوسط",
            "التوصية": f"""• مراجعة سياسة الصيانة كل {mean_days/30:.1f} أشهر
• تحليل أسباب التكرار الطويل
• تخطيط ميزانية الصيانة السنوية"""
        })
    
    # تحليل التباين
    if std_days > mean_days * 0.5:
        recommendations.append({
            "التصنيف": "📊 تباين كبير",
            "الوصف": f"الانحراف المعياري ({std_days:.1f} يوم) يشير إلى تباين كبير في الفترات",
            "التوصية": """• توحيد إجراءات الصيانة
• تدريب الفنيين
• تطوير معايير موحدة"""
        })
    
    # عدد التكرارات
    if total_occurrences > 10:
        recommendations.append({
            "التصنيف": "🔢 تكرارات عالية",
            "الوصف": f"الحدث تكرر {total_occurrences} مرة",
            "التوصية": """• تحليل أسباب التكرار العالي
• دراسة جدوى التحسينات
• تقييم كفاءة المعدات"""
        })
    
    # عرض التوصيات
    for i, rec in enumerate(recommendations, 1):
        with st.expander(f"{rec['التصنيف']} - {rec['الوصف']}", expanded=True):
            st.markdown(f"**التوصية:**")
            st.write(rec['التوصية'])
    
    # إضافة تحليل تنبؤي
    st.markdown("#### 🔮 تحليل تنبؤي")
    
    col1, col2 = st.columns(2)
    
    with col1:
        next_occurrence = st.number_input(
            "عدد الأيام القادمة للتنبؤ:",
            min_value=30,
            max_value=365,
            value=90,
            step=30
        )
    
    with col2:
        machines_count = analysis_result['machines_count']
        expected_occurrences = (next_occurrence / mean_days) * machines_count if mean_days > 0 else 0
        
        st.metric(
            "📈 التكرارات المتوقعة",
            f"{expected_occurrences:.1f}",
            f"خلال {next_occurrence} يوم"
        )

def display_events_table(filtered_df: pd.DataFrame):
    """عرض جدول الأحداث مباشرة"""
    if filtered_df.empty:
        return
    
    display_cols = ['Card Number', 'Event', 'Date', 'Servised by', 'Tones']
    display_cols = [col for col in display_cols if col in filtered_df.columns]
    
    st.dataframe(
        filtered_df[display_cols].sort_values('Date'),
        use_container_width=True,
        height=300
    )

# ===============================
# 🔍 فحص الإيفينت والكوريكشن مع التحليل الزمني
# ===============================
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن بواجهة مبسطة واحترافية مع التحليل الزمني"""
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
    
    # قسم البحث الرئيسي
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                card_numbers = st.text_input(
                    "مثال: 1,3,5 أو 1-5 أو 2,4,7-10",
                    value=st.session_state.search_params.get("card_numbers", ""),
                    key="input_cards",
                    placeholder="اتركه فارغاً للبحث في كل الماكينات"
                )
            
            with st.expander("📅 **التواريخ**", expanded=True):
                date_input = st.text_input(
                    "مثال: 2024 أو 1/2024 أو 2024,2025",
                    value=st.session_state.search_params.get("date_range", ""),
                    key="input_date",
                    placeholder="اتركه فارغاً للبحث في كل التواريخ"
                )
        
        with col2:
            with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                tech_names = st.text_input(
                    "مثال: أحمد, محمد, علي",
                    value=st.session_state.search_params.get("tech_names", ""),
                    key="input_techs",
                    placeholder="اتركه فارغاً للبحث في كل الفنيين"
                )
            
            with st.expander("📝 **نص البحث**", expanded=True):
                search_text = st.text_input(
                    "مثال: صيانة, إصلاح, تغيير",
                    value=st.session_state.search_params.get("search_text", ""),
                    key="input_text",
                    placeholder="اتركه فارغاً للبحث في كل النصوص"
                )
        
        # خيارات متقدمة
        with st.expander("⚙ **خيارات متقدمة**", expanded=False):
            col_adv1, col_adv2, col_adv3 = st.columns(3)
            with col_adv1:
                search_mode = st.radio(
                    "🔍 طريقة البحث:",
                    ["بحث جزئي", "مطابقة كاملة"],
                    index=0 if not st.session_state.search_params.get("exact_match") else 1,
                    key="radio_search_mode"
                )
            with col_adv2:
                include_empty = st.checkbox(
                    "🔍 تضمين الحقول الفارغة",
                    value=st.session_state.search_params.get("include_empty", True),
                    key="checkbox_include_empty"
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
        search_results = perform_advanced_search(search_params, all_sheets)
        
        if search_results is not None and not search_results.empty:
            display_search_results(search_results, search_params)
            
            # إضافة قسم التحليل الزمني
            add_time_analysis_section(search_results)
        else:
            st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")

def perform_advanced_search(search_params, all_sheets):
    """تنفيذ البحث المتقدم"""
    all_results = []
    
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
            
        card_num = int(card_num_match.group(1))
        
        target_card_numbers = parse_card_numbers(search_params["card_numbers"])
        if target_card_numbers and card_num not in target_card_numbers:
            continue
        
        df = all_sheets[sheet_name].copy()
        
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
        
        for _, row in df.iterrows():
            if not check_row_criteria(row, df, card_num, target_techs, target_dates, search_terms, search_params):
                continue
            
            result = extract_row_data(row, df, card_num)
            if result:
                all_results.append(result)
    
    if all_results:
        result_df = pd.DataFrame(all_results)
        return result_df
    return pd.DataFrame()

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

def check_row_criteria(row, df, card_num, target_techs, target_dates, search_terms, search_params):
    """التحقق من مطابقة الصف لمعايير البحث"""
    
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
    """استخراج بيانات الصف"""
    card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
    date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    
    event_value, correction_value = extract_event_correction(row, df)
    
    if (event_value == "-" and correction_value == "-" and date == "-" and tones == "-"):
        return None
    
    servised_by_value = get_servised_by_value(row)
    
    return {
        "Card Number": card_num_value,
        "Event": event_value,
        "Correction": correction_value,
        "Servised by": servised_by_value,
        "Tones": tones,
        "Date": date
    }

def display_search_results(results, search_params):
    """عرض نتائج البحث بشكل احترافي مع ترتيب متسلسل"""
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
    
    # عرض النتائج
    st.markdown("### 📋 النتائج التفصيلية (مرتبة)")
    
    if not display_df.empty:
        display_tabs = st.tabs(["📊 عرض جدولي", "📋 عرض تفصيلي حسب الماكينة"])
        
        with display_tabs[0]:
            columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 'Tones', 'Date', 'Event_Order', 'Total_Events']
            columns_to_show = [col for col in columns_to_show if col in display_df.columns]
            
            st.dataframe(
                display_df[columns_to_show].style.apply(style_table, axis=1),
                use_container_width=True,
                height=500
            )
        
        with display_tabs[1]:
            unique_machines = sorted(display_df['Card Number'].unique(), 
                                   key=lambda x: pd.to_numeric(x, errors='coerce') if str(x).isdigit() else float('inf'))
            
            for machine in unique_machines:
                machine_data = display_df[display_df['Card Number'] == machine].copy()
                machine_data = machine_data.sort_values('Event_Order')
                
                with st.expander(f"🔧 الماكينة {machine} - عدد الأحداث: {len(machine_data)}", expanded=len(unique_machines) <= 5):
                    
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
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        if not results.empty:
            buffer_excel = io.BytesIO()
            export_df = results.copy()
            
            export_df['Card_Number_Clean_Export'] = pd.to_numeric(export_df['Card Number'], errors='coerce')
            export_df['Date_Clean_Export'] = pd.to_datetime(export_df['Date'], errors='coerce', dayfirst=True)
            
            export_df = export_df.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                             ascending=[True, False], na_position='last')
            
            export_df = export_df.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
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
        if not results.empty:
            buffer_csv = io.BytesIO()
            export_csv = results.copy()
            
            export_csv['Card_Number_Clean_Export'] = pd.to_numeric(export_csv['Card Number'], errors='coerce')
            export_csv['Date_Clean_Export'] = pd.to_datetime(export_csv['Date'], errors='coerce', dayfirst=True)
            
            export_csv = export_csv.sort_values(by=['Card_Number_Clean_Export', 'Date_Clean_Export'], 
                                               ascending=[True, False], na_position='last')
            
            export_csv = export_csv.drop(['Card_Number_Clean_Export', 'Date_Clean_Export'], axis=1, errors='ignore')
            
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

def add_time_analysis_section(results_df: pd.DataFrame):
    """إضافة قسم التحليل الزمني"""
    st.markdown("---")
    st.markdown("## ⏱️ التحليل الزمني والإحصائي للأحداث")
    
    analysis_tabs = st.tabs([
        "🔍 تحليل حدث محدد",
        "📊 مقارنة عدة أحداث",
        "📈 إحصائيات عامة"
    ])
    
    with analysis_tabs[0]:
        analyze_single_event(results_df)
    
    with analysis_tabs[1]:
        compare_multiple_events(results_df)
    
    with analysis_tabs[2]:
        show_general_statistics(results_df)

def analyze_single_event(results_df: pd.DataFrame):
    """تحليل حدث معين"""
    st.markdown("#### 🔍 تحليل الفترات الزمنية لحدث معين")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        event_name = st.text_input(
            "اسم الحدث للتحليل:",
            placeholder="أدخل كلمة أو جزء من الحدث (مثال: سير، محرك، صيانة)",
            key="event_name_input"
        )
    
    with col2:
        if st.button("🔍 استخراج الأحداث الشائعة", key="extract_common_events"):
            common_events = extract_common_events(results_df)
            if common_events:
                st.session_state.common_events = common_events
                st.rerun()
    
    if 'common_events' in st.session_state:
        st.markdown("##### 📋 الأحداث الشائعة:")
        common_cols = st.columns(3)
        for idx, (event, count) in enumerate(st.session_state.common_events[:6]):
            with common_cols[idx % 3]:
                if st.button(f"{event} ({count})", key=f"common_{idx}"):
                    st.session_state.event_name_input = event
                    st.rerun()
    
    if event_name and st.button("🔬 تحليل الفترات الزمنية", type="primary"):
        with st.spinner("🔄 جاري تحليل الفترات الزمنية..."):
            analysis_result = EventTimeAnalyzer.analyze_event_time_intervals(results_df, event_name)
            st.session_state.event_analysis = analysis_result
    
    if st.session_state.get("event_analysis"):
        display_time_analysis(st.session_state.event_analysis)

def extract_common_events(results_df: pd.DataFrame, top_n: int = 10) -> List[tuple]:
    """استخراج الأحداث الأكثر شيوعاً"""
    if results_df.empty or 'Event' not in results_df.columns:
        return []
    
    all_events = results_df['Event'].dropna().astype(str)
    word_counts = {}
    
    for event in all_events:
        words = re.findall(r'[\u0600-\u06FFa-zA-Z]+', event)
        for word in words:
            if len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_words[:top_n]

def compare_multiple_events(results_df: pd.DataFrame):
    """مقارنة عدة أحداث"""
    st.markdown("#### 📊 مقارنة الفترات الزمنية لعدة أحداث")
    
    events_input = st.text_area(
        "أدخل الأحداث للمقارنة (مفصولة بفاصلة):",
        placeholder="مثال: سير, محرك, صيانة, تغيير زيت",
        height=100,
        key="multiple_events_input"
    )
    
    if events_input and st.button("📈 مقارنة الأحداث", type="primary"):
        event_list = [e.strip() for e in events_input.split(',') if e.strip()]
        
        if len(event_list) >= 2:
            with st.spinner("🔄 جاري تحليل ومقارنة الأحداث..."):
                comparison_result = EventTimeAnalyzer.analyze_multiple_events(results_df, event_list)
                
                if comparison_result and comparison_result.get('comparison_data'):
                    display_comparison_results(comparison_result, results_df)
                else:
                    st.warning("⚠ لم يتم العثور على بيانات كافية للمقارنة")
        else:
            st.warning("⚠ الرجاء إدخال حدثين على الأقل للمقارنة")

def display_comparison_results(comparison_result: Dict[str, Any], results_df: pd.DataFrame):
    """عرض نتائج المقارنة"""
    comparison_data = comparison_result['comparison_data']
    
    st.markdown(f"##### 📋 نتائج مقارنة {len(comparison_data)} حدث")
    
    comp_df = pd.DataFrame(comparison_data)
    st.dataframe(
        comp_df.sort_values('متوسط الأيام'),
        use_container_width=True
    )
    
    # مخططات المقارنة
    try:
        import plotly.express as px
        
        fig = px.bar(
            comp_df,
            x='الحدث',
            y='متوسط الأيام',
            color='التكرارات',
            title='مقارنة متوسط الفترات الزمنية للأحداث',
            labels={'متوسط الأيام': 'متوسط الأيام بين التكرارات', 'الحدث': 'الحدث'},
            hover_data=['أقصر فترة', 'أطول فترة', 'الانحراف المعياري']
        )
        fig.update_layout(
            xaxis_title="الحدث",
            yaxis_title="متوسط الأيام",
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        st.info("⚠ لم يتم العثور على مكتبة plotly. يمكنك تثبيتها باستخدام: pip install plotly")

def show_general_statistics(results_df: pd.DataFrame):
    """عرض إحصائيات عامة"""
    st.markdown("#### 📈 إحصائيات عامة للأحداث")
    
    if results_df.empty:
        st.info("ℹ️ لا توجد بيانات لعرض الإحصائيات")
        return
    
    total_events = len(results_df)
    unique_machines = results_df['Card Number'].nunique()
    events_with_dates = results_df['Date'].notna().sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 إجمالي الأحداث", total_events)
    
    with col2:
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        events_per_machine = total_events / unique_machines if unique_machines > 0 else 0
        st.metric("📊 متوسط الأحداث/ماكينة", f"{events_per_machine:.1f}")
    
    with col4:
        st.metric("📅 أحداث بتاريخ", events_with_dates)
    
    # تحليل الأحداث الأكثر تكراراً
    st.markdown("##### 🔄 الأحداث الأكثر تكراراً")
    
    if 'Event' in results_df.columns:
        top_events = results_df['Event'].value_counts().head(10).reset_index()
        top_events.columns = ['الحدث', 'عدد التكرارات']
        
        st.dataframe(top_events, use_container_width=True)

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
def main():
    """الدالة الرئيسية للتطبيق"""
    # إعداد الصفحة
    st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
    
    # الشريط الجانبي
    with st.sidebar:
        render_sidebar()
    
    # تحميل البيانات
    all_sheets = load_all_sheets()
    sheets_edit = load_sheets_for_edit()
    
    # عنوان التطبيق
    st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
    
    # التحقق من الصلاحيات
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    user_permissions = st.session_state.get("user_permissions", ["view"])
    permissions = get_user_permissions(user_role, user_permissions)
    
    # تحديد التبويبات
    render_tabs_based_on_permissions(all_sheets, sheets_edit, permissions)

def render_sidebar():
    """عرض الشريط الجانبي"""
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
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

def render_tabs_based_on_permissions(all_sheets, sheets_edit, permissions):
    """عرض التبويبات بناءً على الصلاحيات"""
    if permissions["can_manage_users"]:  # admin
        tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
        
        # Tab 1: فحص السيرفيس
        with tabs[0]:
            render_service_check_tab(all_sheets)
        
        # Tab 2: فحص الإيفينت والكوريكشن
        with tabs[1]:
            render_event_check_tab(all_sheets)
        
        # Tab 3: تعديل البيانات
        with tabs[2]:
            render_data_management_tab(sheets_edit, permissions)
        
        # Tab 4: إدارة المستخدمين
        with tabs[3]:
            render_user_management_tab()
        
        # Tab 5: الدعم الفني
        if APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"] or permissions["can_manage_users"]:
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

def render_service_check_tab(all_sheets):
    """عرض تبويب فحص السيرفيس"""
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

def render_event_check_tab(all_sheets):
    """عرض تبويب فحص الإيفينت والكوريكشن"""
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        check_events_and_corrections(all_sheets)

def render_data_management_tab(sheets_edit, permissions):
    """عرض تبويب إدارة البيانات"""
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

        with tab4:
            add_new_event(sheets_edit)

        with tab5:
            edit_events_and_corrections(sheets_edit)
    
    return sheets_edit

def render_user_management_tab():
    """عرض تبويب إدارة المستخدمين"""
    st.header("👥 إدارة المستخدمين")
    manage_users()

def render_tech_support_tab():
    """عرض تبويب الدعم الفني"""
    st.header("📞 الدعم الفني")
    tech_support()

# تشغيل التطبيق
if __name__ == "__main__":
    main()
