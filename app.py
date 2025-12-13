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
# 🎨 إعدادات الألوان المحسنة
# ===============================
COLOR_CONFIG = {
    "service_done": "#d4edda",  # أخضر فاتح
    "service_not_done": "#f8d7da",  # أحمر فاتح
    "service_partial": "#fff3cd",  # أصفر فاتح
    "row_added": "#e3f2fd",  # أزرق فاتح
    "row_deleted": "#ffebee",  # أحمر شفاف
    "row_modified": "#e8f5e8",  # أخضر شفاف
    "header": "#4f8bf9",  # أزرق للرأس
    "even_row": "#ffffff",  # أبيض
    "odd_row": "#f9f9f9",  # رمادي فاتح جداً
    "highlight": "#e1f5fe",  # أزرق فاتح للتمييز
    "success": "#c8e6c9",  # أخضر ناعم
    "warning": "#ffecb3",  # أصفر ناعم
    "error": "#ffcdd2",  # أحمر ناعم
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
# 🧠 وظائف المصادقة (مختصرة)
# ===============================
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"]}}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"admin": {"password": "admin123", "role": "admin", "created_at": datetime.now().isoformat(), "permissions": ["all"]}}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

def login_ui():
    users = load_users()
    
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            if username_input in users and users[username_input]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = users[username_input].get("role", "viewer")
                st.session_state.user_permissions = users[username_input].get("permissions", ["view"])
                st.success(f"✅ تم تسجيل الدخول: {username_input}")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        st.success(f"✅ مسجل الدخول كـ: {st.session_state.username}")
        if st.button("🚪 تسجيل الخروج"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
        return True

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_users": True, "can_see_tech_support": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_users": False, "can_see_tech_support": False}
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions
        }

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
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف للتحرير: {e}")
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
    if not token or not GITHUB_AVAILABLE:
        st.warning("⚠ سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()

    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            result = repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح")
            return load_sheets_for_edit()
        except:
            try:
                result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                st.success(f"✅ تم إنشاء ملف جديد على GitHub")
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
        st.success("✅ تم حفظ التغييرات تلقائياً")
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
# 🎨 وظائف التلوين المحسنة
# ===============================
def apply_service_coloring(df):
    """تطبيق التلوين على جدول السيرفيس"""
    def color_row(row):
        service_done = row.get("Service Done", "-")
        service_not_done = row.get("Service Didn't Done", "-")
        
        if service_done == "-":
            return [f"background-color: {COLOR_CONFIG['service_not_done']}"] * len(row)
        elif service_not_done == "-":
            return [f"background-color: {COLOR_CONFIG['service_done']}"] * len(row)
        else:
            return [f"background-color: {COLOR_CONFIG['service_partial']}"] * len(row)
    
    styled_df = df.style.apply(color_row, axis=1)
    
    # تلوين الرأس
    styled_df = styled_df.set_properties(**{
        'background-color': COLOR_CONFIG['header'],
        'color': 'white',
        'font-weight': 'bold',
        'border': '1px solid #ddd',
        'text-align': 'center'
    }, subset=pd.IndexSlice[0:0, :])
    
    # تلوين الصفوف الفردية والزوجية
    for i in range(len(df)):
        if i % 2 == 0:
            styled_df = styled_df.set_properties(**{
                'background-color': COLOR_CONFIG['even_row']
            }, subset=pd.IndexSlice[i:i, :])
        else:
            styled_df = styled_df.set_properties(**{
                'background-color': COLOR_CONFIG['odd_row']
            }, subset=pd.IndexSlice[i:i, :])
    
    return styled_df

def apply_edit_coloring(df, added_rows=None, modified_rows=None):
    """تطبيق التلوين على جدول التعديل"""
    added_rows = added_rows or []
    modified_rows = modified_rows or []
    
    def color_row(row):
        idx = row.name
        if idx in added_rows:
            return [f"background-color: {COLOR_CONFIG['row_added']}"] * len(row)
        elif idx in modified_rows:
            return [f"background-color: {COLOR_CONFIG['row_modified']}"] * len(row)
        elif idx % 2 == 0:
            return [f"background-color: {COLOR_CONFIG['even_row']}"] * len(row)
        else:
            return [f"background-color: {COLOR_CONFIG['odd_row']}"] * len(row)
    
    styled_df = df.style.apply(color_row, axis=1)
    
    # تلوين الرأس
    styled_df = styled_df.set_properties(**{
        'background-color': COLOR_CONFIG['header'],
        'color': 'white',
        'font-weight': 'bold',
        'border': '1px solid #ddd'
    }, subset=pd.IndexSlice[0:0, :])
    
    return styled_df

# ===============================
# 📊 فحص السيرفيس مع تلوين
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
    card_services_sheet_name = f"Card{card_num}_Services"
    
    if card_services_sheet_name not in all_sheets:
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            services_df = all_sheets[card_old_sheet_name].copy()
        else:
            st.warning(f"⚠ لا يوجد شيت لهذه الماكينة")
            return
    else:
        services_df = all_sheets[card_services_sheet_name].copy()

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True
    )

    min_range = max(0, current_tons - 500)
    max_range = current_tons + 500
    
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range)
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range)

    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[
            (service_plan_df["Min_Tones"] <= current_tons) & 
            (service_plan_df["Max_Tones"] >= current_tons)
        ]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[
            (service_plan_df["Min_Tones"] >= min_range) & 
            (service_plan_df["Max_Tones"] <= max_range)
        ]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة")
        return

    all_results = []
    service_stats = {
        "service_counts": {},
        "service_done_counts": {},
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {},
        "by_service_type": {}
    }
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        
        service_stats["by_slice"][slice_key] = {
            "needed": needed_parts,
            "done": [],
            "not_done": [],
            "total_needed": len(needed_parts),
            "total_done": 0
        }
        
        for service in needed_parts:
            service_stats["service_counts"][service] = service_stats["service_counts"].get(service, 0) + 1
            if service not in service_stats["by_service_type"]:
                service_stats["by_service_type"][service] = {
                    "required": 0,
                    "done": 0,
                    "remaining": 0
                }
            service_stats["by_service_type"][service]["required"] += 1
        
        service_stats["total_needed_services"] += len(needed_parts)

        try:
            mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
            matching_rows = services_df[mask]
        except:
            matching_rows = services_df

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                for col in services_df.columns:
                    col_normalized = normalize_name(col)
                    if any(keyword in col_normalized for keyword in ["card", "tones", "date", "min", "max", "servised", "event", "correction", "other"]):
                        continue
                    
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", "", "null", "0", "no", "false", "not done", "لم تتم", "x", "-"]:
                        done_services_set.add(col)
                        
                        service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                        service_stats["total_done_services"] += 1
                        
                        for service_type in service_stats["by_service_type"]:
                            if service_type.lower() in col.lower() or col.lower() in service_type.lower():
                                service_stats["by_service_type"][service_type]["done"] += 1

                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                servised_by_value = get_servised_by_value(row)
                
                done_services = sorted(list(done_services_set))
                
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
                not_done = []
                for needed_part in needed_parts:
                    found = False
                    for done_service in done_services:
                        if needed_part.lower() in done_service.lower() or done_service.lower() in needed_part.lower():
                            found = True
                            break
                    if not found:
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
            
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    # حساب المتبقي لأنواع الخدمات
    for service_type in service_stats["by_service_type"]:
        service_data = service_stats["by_service_type"][service_type]
        service_data["remaining"] = service_data["required"] - service_data["done"]

    if all_results:
        result_df = pd.DataFrame(all_results)
        
        st.markdown("### 📋 نتائج فحص السيرفيس")
        
        # تطبيق التلوين
        styled_result_df = apply_service_coloring(result_df)
        
        st.dataframe(styled_result_df, use_container_width=True, height=400)
        
        if service_stats["total_needed_services"] > 0:
            completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100
            
            st.markdown("### 📊 الإحصائيات العامة")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📈 نسبة الإنجاز", f"{completion_rate:.1f}%")
            with col2:
                st.metric("🔢 الخدمات المطلوبة", service_stats["total_needed_services"])
            with col3:
                st.metric("✅ الخدمات المنفذة", service_stats["total_done_services"])
            with col4:
                remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
                st.metric("⏳ الخدمات المتبقية", remaining)
        
        # عرض إحصائيات كل رنج
        st.markdown("### 📊 إحصائيات كل رنج")
        
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            completion_rate = (slice_data["total_done"] / slice_data["total_needed"] * 100) if slice_data["total_needed"] > 0 else 0
            slice_stats_data.append({
                "الرنج": slice_key,
                "الخدمات المطلوبة": slice_data["total_needed"],
                "الخدمات المنفذة": slice_data["total_done"],
                "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                "نسبة الإنجاز": f"{completion_rate:.1f}%"
            })
        
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            
            def color_completion(val):
                try:
                    percent = float(val.replace('%', ''))
                    if percent >= 80:
                        return f"background-color: {COLOR_CONFIG['service_done']}"
                    elif percent >= 50:
                        return f"background-color: {COLOR_CONFIG['service_partial']}"
                    else:
                        return f"background-color: {COLOR_CONFIG['service_not_done']}"
                except:
                    return ""
            
            styled_slice_df = slice_stats_df.style.applymap(
                color_completion, 
                subset=['نسبة الإنجاز']
            )
            st.dataframe(styled_slice_df, use_container_width=True)
        
        # عرض إحصائيات كل نوع سيرفيس
        st.markdown("### 📊 إحصائيات كل نوع سيرفيس")
        
        service_type_data = []
        for service_type, service_data in service_stats["by_service_type"].items():
            completion_rate = (service_data["done"] / service_data["required"] * 100) if service_data["required"] > 0 else 0
            service_type_data.append({
                "نوع الخدمة": service_type,
                "مطلوب في": service_data["required"],
                "تم تنفيذه": service_data["done"],
                "متبقي": service_data["remaining"],
                "نسبة الإنجاز": f"{completion_rate:.1f}%"
            })
        
        if service_type_data:
            service_type_df = pd.DataFrame(service_type_data)
            styled_service_df = service_type_df.style.applymap(
                color_completion,
                subset=['نسبة الإنجاز']
            )
            st.dataframe(styled_service_df, use_container_width=True)
    else:
        st.info("ℹ️ لا توجد خدمات مسجلة لهذه الماكينة.")

# ===============================
# 🛠 إدارة وتعديل البيانات مع إضافة صفوف متكاملة
# ===============================
def edit_sheet_with_save_button(sheets_edit):
    """تعديل بيانات الشيت مع إضافة صفوف ضمن رنج محدد"""
    st.subheader("✏ تعديل البيانات")
    
    # تهيئة session state
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    
    if "added_rows" not in st.session_state:
        st.session_state.added_rows = {}
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    
    df = sheets_edit[sheet_name].astype(str).copy()
    
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # قسم إضافة صف جديد
    st.markdown("---")
    st.markdown("### ➕ إضافة صف جديد ضمن رنج محدد")
    
    with st.expander("🎯 تحديد الرنج والخوادم", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            new_min_tones = st.number_input("من (طن):", min_value=0, value=0, step=100, key="new_min_tones")
        with col2:
            new_max_tones = st.number_input("إلى (طن):", min_value=new_min_tones, value=1000, step=100, key="new_max_tones")
        
        # الحصول على أنواع الخدمات من ServicePlan
        if "ServicePlan" in sheets_edit:
            service_plan_df = sheets_edit["ServicePlan"]
            # البحث عن الرنج المناسب
            matching_service = service_plan_df[
                (service_plan_df["Min_Tones"] <= new_max_tones) & 
                (service_plan_df["Max_Tones"] >= new_min_tones)
            ]
            
            if not matching_service.empty:
                service_needed = matching_service.iloc[0].get("Service", "")
                needed_services = split_needed_services(service_needed)
                
                st.markdown(f"**📋 أنواع السيرفيس المطلوبة في هذا الرنج:**")
                if needed_services:
                    for service in needed_services:
                        st.write(f"• {service}")
                    
                    # خيارات لكل نوع سيرفيس
                    st.markdown("**✅ تحديد حالة كل سيرفيس:**")
                    for service in needed_services:
                        col_s1, col_s2 = st.columns([3, 1])
                        with col_s1:
                            st.write(f"{service}")
                        with col_s2:
                            service_status = st.selectbox(
                                f"حالة {service}",
                                ["Done", "Not Done"],
                                key=f"service_status_{service}"
                            )
                else:
                    st.warning("⚠ لا توجد خدمات محددة لهذا الرنج في ServicePlan")
            else:
                st.info("ℹ️ لا يوجد رنج مطابق في ServicePlan، يمكنك إضافة الخدمات يدوياً")
                
        # بيانات إضافية للصف الجديد
        st.markdown("**📝 بيانات إضافية:**")
        col3, col4 = st.columns(2)
        with col3:
            new_date = st.text_input("التاريخ:", placeholder="يوم/شهر/سنة", key="new_row_date")
            new_tones = st.number_input("التونز:", min_value=0, value=new_min_tones, key="new_row_tones")
        with col4:
            new_servised_by = st.text_input("فني الخدمة:", placeholder="اسم الفني", key="new_row_servised_by")
            new_card = st.text_input("رقم الكارد:", value="", placeholder="رقم الكارد", key="new_row_card")
    
    # زر إضافة الصف الجديد
    if st.button("➕ إضافة الصف الجديد", type="primary", key="add_new_row_btn"):
        if new_min_tones > new_max_tones:
            st.error("❌ الحد الأدنى يجب أن يكون أقل من الحد الأقصى")
            return
        
        # إنشاء الصف الجديد
        new_row = {}
        
        # إضافة البيانات الأساسية
        new_row["Min_Tones"] = str(new_min_tones)
        new_row["Max_Tones"] = str(new_max_tones)
        
        if new_card:
            new_row["card"] = new_card
        if new_date:
            new_row["Date"] = new_date
        if new_tones:
            new_row["Tones"] = str(new_tones)
        if new_servised_by:
            new_row["Servised by"] = new_servised_by
        
        # إضافة بيانات الخدمات
        if "ServicePlan" in sheets_edit and not matching_service.empty and needed_services:
            for service in needed_services:
                service_key = f"service_status_{service}"
                if service_key in st.session_state:
                    status = st.session_state[service_key]
                    if status == "Done":
                        new_row[service] = "✓"
                    else:
                        new_row[service] = ""
        
        # إضافة الصف إلى DataFrame
        new_row_df = pd.DataFrame([new_row])
        
        # إيجاد المكان المناسب لإضافة الصف (بناءً على Min_Tones)
        insert_position = len(df)
        if "Min_Tones" in df.columns:
            for i in range(len(df)):
                try:
                    current_min = float(df.iloc[i]["Min_Tones"]) if df.iloc[i]["Min_Tones"] not in ["", "nan", "NaN"] else 0
                    if new_min_tones < current_min:
                        insert_position = i
                        break
                except:
                    continue
        
        # إضافة الصف في الموقع المناسب
        df = pd.concat([df.iloc[:insert_position], new_row_df, df.iloc[insert_position:]]).reset_index(drop=True)
        
        # تحديث session state
        st.session_state.unsaved_changes[sheet_name] = True
        
        if sheet_name not in st.session_state.added_rows:
            st.session_state.added_rows[sheet_name] = []
        st.session_state.added_rows[sheet_name].append(insert_position)
        
        st.success(f"✅ تم إضافة صف جديد في الرنج {new_min_tones}-{new_max_tones}")
        st.info("💡 الصف المضاف سيكون بلون أزرق فاتح")
    
    st.markdown("---")
    st.markdown("### 🛠 محرر البيانات")
    
    # عرض الصفوف المضاف حديثاً
    if sheet_name in st.session_state.added_rows and st.session_state.added_rows[sheet_name]:
        st.markdown(f"#### 📌 الصفوف المضاف حديثاً ({len(st.session_state.added_rows[sheet_name])})")
        added_indices = st.session_state.added_rows[sheet_name]
        added_df = df.iloc[added_indices].copy()
        
        if not added_df.empty:
            # تلوين الصفوف المضاف
            def color_added_rows(row):
                return [f"background-color: {COLOR_CONFIG['row_added']}"] * len(row)
            
            styled_added_df = added_df.style.apply(color_added_rows, axis=1)
            st.dataframe(styled_added_df, use_container_width=True, height=200)
    
    # محرر البيانات الرئيسي
    st.markdown("#### ✏ تعديل البيانات الحالية")
    
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )
    
    # التحقق من التغييرات
    has_changes = not edited_df.equals(df)
    
    # كشف الصفوف المعدلة
    modified_rows = []
    if len(edited_df) == len(df):
        for i in range(len(df)):
            if not df.iloc[i].equals(edited_df.iloc[i]):
                modified_rows.append(i)
                has_changes = True
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        
        # حساب التغييرات
        changes_summary = calculate_changes_summary(df, edited_df, sheet_name)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                
                new_sheets = auto_save_to_github(
                    sheets_edit,
                    f"تعديل في شيت {sheet_name}"
                )
                
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.session_state.added_rows[sheet_name] = []
                    
                    st.success(f"✅ تم حفظ التغييرات بنجاح!")
                    st.rerun()
        
        with col2:
            if st.button("↩️ تراجع", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.session_state.added_rows[sheet_name] = []
                    st.info("↩️ تم التراجع عن التغييرات")
                    st.rerun()
        
        with col3:
            with st.expander("📊 ملخص التغييرات"):
                st.write(f"**🔄 تغييرات في:** {sheet_name}")
                st.write(f"**➕ صفوف مضافة:** {changes_summary.get('added', 0)}")
                st.write(f"**✏️ صفوف معدلة:** {len(modified_rows)}")
                st.write(f"**🔢 إجمالي التغييرات:** {changes_summary.get('total', 0)}")
    
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
        
        if st.button("🔄 تحديث", key=f"refresh_{sheet_name}"):
            st.rerun()
    
    return sheets_edit

def calculate_changes_summary(original_df, edited_df, sheet_name):
    """حساب ملخص التغييرات"""
    summary = {
        "added": 0,
        "deleted": 0,
        "modified": 0,
        "total": 0
    }
    
    if len(edited_df) > len(original_df):
        summary["added"] = len(edited_df) - len(original_df)
    elif len(edited_df) < len(original_df):
        summary["deleted"] = len(original_df) - len(edited_df)
    
    if sheet_name in st.session_state.added_rows:
        summary["added"] = len(st.session_state.added_rows[sheet_name])
    
    summary["total"] = summary["added"] + summary["deleted"]
    
    return summary

# ===============================
# 👥 إدارة المستخدمين (مختصرة)
# ===============================
def manage_users():
    """إدارة المستخدمين والصلاحيات"""
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    current_user = st.session_state.get("username")
    
    if current_user != "admin":
        st.error("❌ الصلاحية مقتصرة على المسؤول فقط.")
        return
    
    st.dataframe(pd.DataFrame([
        {
            "اسم المستخدم": username,
            "الدور": info.get("role", "viewer"),
            "الصلاحيات": ", ".join(info.get("permissions", [])),
            "تاريخ الإنشاء": info.get("created_at", "")
        }
        for username, info in users.items()
    ]), use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("➕ إضافة مستخدم جديد"):
        new_user = st.text_input("اسم المستخدم الجديد")
        new_pass = st.text_input("كلمة المرور", type="password")
        new_role = st.selectbox("الدور", ["admin", "editor", "viewer"])
        
        if st.button("إضافة مستخدم"):
            if new_user and new_pass:
                users[new_user] = {
                    "password": new_pass,
                    "role": new_role,
                    "permissions": ["all"] if new_role == "admin" else ["view", "edit"] if new_role == "editor" else ["view"],
                    "created_at": datetime.now().isoformat()
                }
                if save_users(users):
                    st.success("✅ تم إضافة المستخدم")
                    st.rerun()

# ===============================
# 📞 الدعم الفني (مختصرة)
# ===============================
def tech_support():
    """قسم الدعم الفني"""
    st.header("📞 الدعم الفني")
    
    st.markdown("""
    ### 🔧 استكشاف الأخطاء وإصلاحها
    
    1. **المشكلة:** لا يمكن تحميل الملف من GitHub
       **الحل:** اضغط على زر "🔄 تحديث الملف من GitHub" في الشريط الجانبي
    
    2. **المشكلة:** لا يمكن حفظ التعديلات
       **الحل:** تأكد من وجود token GitHub في الإعدادات
    
    3. **المشكلة:** التطبيق يعمل ببطء
       **الحل:** اضغط على زر "🗑 مسح الكاش"
    
    ### 📊 إحصائيات النظام
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        users = load_users()
        st.metric("👥 عدد المستخدمين", len(users))
    with col2:
        if os.path.exists(APP_CONFIG["LOCAL_FILE"]):
            size = os.path.getsize(APP_CONFIG["LOCAL_FILE"]) / (1024 * 1024)
            st.metric("💾 حجم الملف", f"{size:.2f} MB")
    
    if st.button("🔄 إعادة تشغيل التطبيق"):
        st.cache_data.clear()
        st.rerun()

# ===============================
# 🏠 الواجهة الرئيسية
# ===============================
def main():
    """الدالة الرئيسية للتطبيق"""
    st.set_page_config(
        page_title=APP_CONFIG["APP_TITLE"],
        page_icon="🏭",
        layout="wide"
    )
    
    # الشريط الجانبي
    with st.sidebar:
        st.header(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
        
        if not login_ui():
            st.stop()
        
        st.markdown("---")
        st.write("🔧 أدوات النظام:")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 تحديث الملف", use_container_width=True):
                if fetch_from_github_requests():
                    st.rerun()
        with col2:
            if st.button("🗑 مسح الكاش", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        if st.session_state.get("logged_in"):
            st.markdown("---")
            if st.button("🚪 تسجيل الخروج", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.rerun()
    
    # الواجهة الرئيسية
    st.title(f"{APP_CONFIG['APP_ICON']} نظام إدارة الصيانة CMMS")
    
    # تحميل البيانات
    all_sheets = load_all_sheets()
    sheets_edit = load_sheets_for_edit()
    
    # التحقق من الصلاحيات
    username = st.session_state.get("username")
    user_role = st.session_state.get("user_role", "viewer")
    permissions = get_user_permissions(user_role, st.session_state.get("user_permissions", []))
    
    # عرض التبويبات حسب الصلاحية
    if permissions["can_manage_users"]:  # Admin
        tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
        
        with tabs[0]:  # فحص السيرفيس
            st.header("📊 فحص السيرفيس")
            if all_sheets:
                col1, col2 = st.columns(2)
                with col1:
                    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
                with col2:
                    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
                
                if st.button("🔍 فحص السيرفيس", type="primary"):
                    check_service_status(card_num, current_tons, all_sheets)
            else:
                st.warning("❗ لم يتم تحميل الملف")
        
        with tabs[1]:  # فحص الإيفينت
            st.header("📋 فحص الإيفينت والكوريكشن")
            st.info("قيد التطوير...")
        
        with tabs[2]:  # تعديل البيانات
            st.header("🛠 تعديل وإدارة البيانات")
            if sheets_edit:
                edit_sheet_with_save_button(sheets_edit)
            else:
                st.warning("❗ لم يتم تحميل الملف للتحرير")
        
        with tabs[3]:  # إدارة المستخدمين
            manage_users()
        
        with tabs[4]:  # الدعم الفني
            tech_support()
    
    elif permissions["can_edit"]:  # Editor
        tabs = st.tabs([
            "📊 فحص السيرفيس",
            "🛠 تعديل وإدارة البيانات"
        ])
        
        with tabs[0]:
            st.header("📊 فحص السيرفيس")
            if all_sheets:
                col1, col2 = st.columns(2)
                with col1:
                    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="editor_card")
                with col2:
                    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="editor_tons")
                
                if st.button("🔍 فحص السيرفيس", type="primary"):
                    check_service_status(card_num, current_tons, all_sheets)
        
        with tabs[1]:
            st.header("🛠 تعديل وإدارة البيانات")
            if sheets_edit:
                edit_sheet_with_save_button(sheets_edit)
    
    else:  # Viewer
        st.header("📊 فحص السيرفيس")
        if all_sheets:
            col1, col2 = st.columns(2)
            with col1:
                card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="viewer_card")
            with col2:
                current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="viewer_tons")
            
            if st.button("🔍 فحص السيرفيس", type="primary"):
                check_service_status(card_num, current_tons, all_sheets)

# تشغيل التطبيق
if __name__ == "__main__":
    main()
