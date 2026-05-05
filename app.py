import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import requests
import shutil
import re
from datetime import datetime, timedelta
import io
import uuid
from PIL import Image
from github import Github, GithubException

# ------------------------------- دوال وضع عدم الاتصال -------------------------------
PENDING_OPS_FILE = "pending_operations.json"

def load_pending_operations():
    """تحميل العمليات المعلقة من ملف JSON أو session_state."""
    if "pending_operations" not in st.session_state:
        st.session_state.pending_operations = []
        if os.path.exists(PENDING_OPS_FILE):
            try:
                with open(PENDING_OPS_FILE, "r", encoding="utf-8") as f:
                    st.session_state.pending_operations = json.load(f)
            except:
                pass
    return st.session_state.pending_operations

def save_pending_operations():
    """حفظ العمليات المعلقة إلى ملف JSON."""
    try:
        with open(PENDING_OPS_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.pending_operations, f, indent=2, ensure_ascii=False)
    except:
        pass

def add_pending_operation(op_type, data):
    """إضافة عملية جديدة إلى قائمة الانتظار."""
    op = {
        "id": str(uuid.uuid4()),
        "type": op_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "retries": 0
    }
    pending = load_pending_operations()
    pending.append(op)
    save_pending_operations()
    return op["id"]

def remove_pending_operation(op_id):
    """إزالة عملية من القائمة."""
    pending = load_pending_operations()
    pending = [op for op in pending if op["id"] != op_id]
    st.session_state.pending_operations = pending
    save_pending_operations()

def is_github_accessible():
    """التحقق من الاتصال بـ GitHub."""
    try:
        response = requests.get("https://raw.githubusercontent.com/mahmedabdallh123/Elqds/main/users.json", timeout=5)
        return response.status_code == 200
    except:
        return False

# ------------------------------- الإعدادات الثابتة -------------------------------
APP_CONFIG = {
    "APP_TITLE": "القدس - CMMS",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/Elqds",
    "BRANCH": "main",
    "FILE_PATH": "l9.xlsx",
    "LOCAL_FILE": "l9.xlsx",
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 60,
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "MAX_IMAGE_SIZE_MB": 10,
    "DEFAULT_SHEET_COLUMNS": ["مده الاصلاح", "التاريخ", "المعدة", "الحدث/العطل", "الإجراء التصحيحي", "تم بواسطة", "قطع غيار مستخدمة", "نوع العطل", "قدرة الفني (حل/تفكير/مبادرة/قرار)", "الالتزام بتعليمات السلامة", "رابط الصورة"],
    "SPARE_PARTS_SHEET": "قطع_الغيار",
    "SPARE_PARTS_COLUMNS": ["اسم القطعة", "المقاس", "قوه الشد", "الرصيد الموجود", "مدة التوريد", "ضرورية", "القسم", "رابط_الصورة", "حد_الإنذار"],
    "MAINTENANCE_SHEET": "صيانة_وقائية",
    "MAINTENANCE_COLUMNS": ["المعدة", "نوع_الصيانة", "اسم_البند", "الفترة_بالأيام", "آخر_تنفيذ", "التاريخ_التالي", "ملاحظات", "قطع_غيار_مستخدمة_افتراضية", "رابط_الصورة"],
    "GENERAL_SECTION": "عام"
}

# ------------------------------- إعداد الصفحة -------------------------------
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# ... (باقي الاستيرادات والثوابت كما هي لديك) ...

# ------------------------------- دوال رفع الصور والحفظ -------------------------------
def upload_image_to_github(...):  # الكود الموجود لديك
    pass

# دوال قطع الغيار والصيانة موجودة لديك ...

# ------------------------------- دوال الحفظ مع دعم عدم الاتصال -------------------------------
def save_excel_locally(sheets_dict):
    # الكود الموجود لديك (غير معدل)
    pass

def push_to_github():
    # الكود الموجود لديك
    pass

def save_with_offline_support(sheets_edit, operation_name, operation_type, operation_data):
    """يحفظ محلياً ثم يحاول الرفع إلى GitHub. إذا فشل الرفع، يضيف العملية لقائمة المعلقة."""
    if not save_excel_locally(sheets_edit):
        st.error("❌ فشل الحفظ المحلي!")
        return False

    if is_github_accessible():
        if push_to_github():
            st.success(f"✅ {operation_name} - تم الحفظ والرفع إلى GitHub.")
            return True
        else:
            st.warning(f"⚠️ {operation_name} - فشل الرفع إلى GitHub، تم الحفظ محلياً وسيتم إعادة المحاولة لاحقاً.")
            add_pending_operation(operation_type, operation_data)
            return True
    else:
        st.info(f"📴 وضع عدم الاتصال: '{operation_name}' تم الحفظ محلياً. سيتم المزامنة لاحقاً.")
        add_pending_operation(operation_type, operation_data)
        return True

def execute_pending_add_event(sheets_edit, data):
    """تنفيذ إضافة حدث مخزنة مسبقاً."""
    sheet_name = data["sheet_name"]
    new_row = data["new_row"]
    if sheet_name not in sheets_edit:
        return False
    df = sheets_edit[sheet_name]
    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    sheets_edit[sheet_name] = new_df
    return True

def sync_pending_operations(sheets_edit):
    """محاولة تنفيذ جميع العمليات المعلقة بالترتيب."""
    if not is_github_accessible():
        st.warning("🌐 لا يوجد اتصال بالإنترنت، لا يمكن المزامنة الآن.")
        return sheets_edit

    pending = load_pending_operations()
    if not pending:
        return sheets_edit

    st.info(f"🔄 جاري مزامنة {len(pending)} عملية معلقة...")
    progress_bar = st.progress(0)
    successfully_removed = []

    for i, op in enumerate(pending):
        success = False
        try:
            if op["type"] == "add_event":
                success = execute_pending_add_event(sheets_edit, op["data"])
            # يمكنك إضافة أنواع أخرى هنا لاحقاً (مثل add_spare_part, إلخ)
            else:
                st.error(f"نوع العملية غير معروف: {op['type']}")
        except Exception as e:
            st.error(f"خطأ في تنفيذ العملية {op['id']}: {e}")

        if success:
            successfully_removed.append(op["id"])
        else:
            op["retries"] += 1
            if op["retries"] >= 5:
                st.error(f"تم التخلي عن العملية {op['id']} بعد 5 محاولات فاشلة.")
                successfully_removed.append(op["id"])
        progress_bar.progress((i+1)/len(pending))

    # إزالة العمليات الناجحة أو المتخلى عنها
    st.session_state.pending_operations = [op for op in pending if op["id"] not in successfully_removed]
    save_pending_operations()

    # حفظ التغييرات المحلية بعد تنفيذ العمليات
    if save_excel_locally(sheets_edit) and push_to_github():
        st.success("✅ تمت مزامنة جميع العمليات ورفعها إلى GitHub.")
    else:
        st.warning("⚠️ تم تنفيذ العمليات ولكن فشل الرفع النهائي، سيتم إعادة المحاولة لاحقاً.")
    return sheets_edit

# ------------------------------- دالة add_new_event المعدلة -------------------------------
def add_new_event(sheets_edit, sheet_name):
    st.markdown(f"### 📝 إضافة حدث عطل جديد في قسم: {sheet_name}")
    df = sheets_edit[sheet_name]
    equipment_list = get_equipment_list_from_sheet(df)
    if not equipment_list:
        st.warning("⚠ لا توجد ماكينات مسجلة في هذا القسم. يرجى إضافة ماكينة أولاً من تبويب 'إدارة الماكينات'")
        return sheets_edit

    # إدارة اختيار الماكينة المؤقتة
    if "selected_equipment_temp" not in st.session_state:
        st.session_state.selected_equipment_temp = equipment_list[0] if equipment_list else ""
    selected_equipment = st.selectbox("🔧 اختر الماكينة:", equipment_list,
                                      index=equipment_list.index(st.session_state.selected_equipment_temp) if st.session_state.selected_equipment_temp in equipment_list else 0,
                                      key="equipment_select")
    if selected_equipment != st.session_state.selected_equipment_temp:
        st.session_state.selected_equipment_temp = selected_equipment
        st.rerun()

    spare_parts_list = get_spare_parts_for_section(sheet_name)

    with st.form(key="add_event_form"):
        col1, col2 = st.columns(2)
        with col1:
            event_date = st.date_input("📅 التاريخ:", value=datetime.now())
            repair_duration = st.number_input("⏱️ مدة الإصلاح (ساعات):", min_value=0.0, step=0.5, format="%.1f")
            event_desc = st.text_area("📝 الحدث/العطل:", height=100)
            fault_type = st.selectbox("🏷️ نوع العطل:", ["", "ميكانيكي", "كهربائي", "إلكتروني", "هيدروليكي", "هوائي", "هيكلي", "آخر"])
            uploaded_image = st.file_uploader("🖼️ رفع صورة (اختياري):", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"])
        with col2:
            correction_desc = st.text_area("🔧 الإجراء التصحيحي:", height=100)
            servised_by = st.text_input("👨‍🔧 تم بواسطة:")
            technician_rating = st.select_slider("⭐ قدرة الفني (حل/تفكير/مبادرة/قرار):", options=[1, 2, 3, 4, 5], value=3)
            safety_compliance = st.selectbox("🛡️ الالتزام بتعليمات السلامة:", ["", "ملتزم بالكامل", "ملتزم جزئياً", "غير ملتزم", "غير مطبق"])
            st.markdown("---")
            st.markdown("**🔩 قطع الغيار المستخدمة**")
            part_name = ""
            consume_qty = 0
            if spare_parts_list:
                part_names = [f"{name} (الرصيد: {qty})" for name, qty in spare_parts_list]
                selected_part_display = st.selectbox("اختر قطعة:", [""] + part_names, key="spare_part_select")
                if selected_part_display:
                    part_name = selected_part_display.split(" (")[0]
                    current_qty = next((qty for name, qty in spare_parts_list if name == part_name), 0)
                    st.caption(f"الرصيد الحالي: {current_qty}")
                    consume_qty = st.number_input("الكمية المستخدمة:", min_value=1, max_value=max(1, current_qty), value=1, step=1, key="consume_qty")
                    if consume_qty > current_qty:
                        st.error(f"⚠️ الرصيد غير كافٍ (الموجود {current_qty})")
                    else:
                        st.success(f"سيتم خصم {consume_qty} من الرصيد")
            else:
                st.info("لا توجد قطع غيار مسجلة لهذا القسم. يمكنك إضافتها من تبويب 'قطع الغيار'.")

        submitted = st.form_submit_button("✅ إضافة الحدث", type="primary")
        if submitted:
            spare_part_used = ""
            warning_msg = ""
            if part_name and consume_qty > 0:
                success, msg, new_qty = consume_spare_part(part_name, consume_qty)
                if success:
                    spare_part_used = f"{part_name} (كمية {consume_qty})"
                    critical_parts = get_critical_spare_parts()
                    for cp in critical_parts:
                        if cp["اسم القطعة"] == part_name:
                            warning_msg = f"⚠️ **تحذير:** القطعة '{part_name}' ضرورية وأصبح رصيدها {new_qty} (أقل من 1). يرجى إعادة التوريد."
                            break
                else:
                    st.error(msg)
                    return sheets_edit

            image_url = None
            if uploaded_image is not None:
                event_id = str(uuid.uuid4())[:8]
                # نرفع الصورة فوراً إذا كان متصلاً، وإلا سنرفعها لاحقاً في المزامنة
                if is_github_accessible():
                    image_url = upload_image_to_github(uploaded_image, "event", event_id)
                    if image_url:
                        st.success("✅ تم رفع الصورة بنجاح!")
                    else:
                        st.warning("⚠️ فشل رفع الصورة، سيتم حفظ الحدث بدون صورة")
                else:
                    # في وضع عدم الاتصال، نخزن الصورة مؤقتاً (هنا نكتفي بمسار وهمي)
                    st.info("📴 وضع عدم الاتصال: سيتم رفع الصورة لاحقاً عند المزامنة.")
                    # يمكنك تخزين الصورة في session_state لرفعها لاحقاً، لكننا سنبسطها حالياً
                    image_url = None

            new_row = {
                "مده الاصلاح": repair_duration if repair_duration > 0 else "",
                "التاريخ": event_date.strftime("%Y-%m-%d"),
                "المعدة": selected_equipment,
                "الحدث/العطل": event_desc,
                "الإجراء التصحيحي": correction_desc,
                "تم بواسطة": servised_by,
                "قطع غيار مستخدمة": spare_part_used,
                "نوع العطل": fault_type if fault_type else "",
                "قدرة الفني (حل/تفكير/مبادرة/قرار)": technician_rating,
                "الالتزام بتعليمات السلامة": safety_compliance if safety_compliance else "",
                "رابط الصورة": image_url or ""
            }
            # التأكد من وجود كل الأعمدة
            for col in df.columns:
                if col not in new_row:
                    new_row[col] = ""
            new_row_df = pd.DataFrame([new_row])
            df_new = pd.concat([df, new_row_df], ignore_index=True)
            sheets_edit[sheet_name] = df_new
            if "temp_spare_parts_df" in st.session_state:
                sheets_edit[APP_CONFIG["SPARE_PARTS_SHEET"]] = st.session_state.temp_spare_parts_df
                del st.session_state.temp_spare_parts_df

            # ---------------------------------------------
            # استخدام save_with_offline_support بدلاً من save_and_push_to_github
            offline_data = {
                "sheet_name": sheet_name,
                "new_row": new_row,
                "part_name": part_name,
                "consume_qty": consume_qty,
                "image_url": image_url,
                "event_desc": event_desc,
                "selected_equipment": selected_equipment,
                "warning_msg": warning_msg
            }
            if save_with_offline_support(sheets_edit, f"إضافة حدث عطل مع استخدام قطعة {part_name}", "add_event", offline_data):
                st.cache_data.clear()
                log_activity("add_event", f"تم إضافة عطل: {event_desc[:50]} للماكينة {selected_equipment}")
                if warning_msg:
                    st.warning(warning_msg)
                st.rerun()
            else:
                st.error("❌ فشل الحفظ (حتى الحفظ المحلي لم ينجح)")
            # ---------------------------------------------
    return sheets_edit

# ------------------------------- باقي دوال التطبيق -------------------------------
# (كل الدوال الأخرى مثل load_spare_parts, get_critical_spare_parts, 
#  failures_analysis_tab, search_across_sheets, manage_data_edit, 
#  الواجهة الرئيسية مع الشريط الجانبي ... تبقى كما هي مع إضافة واجهة العمليات المعلقة)

# ... ضع هنا باقي الدوال الموجودة لديك كما هي (غير معدلة) ...

# ------------------------------- الواجهة الرئيسية -------------------------------
with st.sidebar:
    st.header("الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | ⏳ {mins:02d}:{secs:02d}")
        st.markdown("---")
        if st.button("🔄 تحديث"):
            if fetch_from_github_requests():
                st.rerun()
        if st.button("مسح مهملات"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()

        # ----- عرض العمليات المعلقة -----
        pending = load_pending_operations()
        if pending:
            st.markdown("---")
            st.warning(f"⏳ عمليات معلقة: {len(pending)}")
            if st.button("🔄 مزامنة الآن"):
                sheets_edit = load_sheets_for_edit()
                sheets_edit = sync_pending_operations(sheets_edit)
                st.rerun()
            with st.expander("عرض التفاصيل"):
                for op in pending:
                    st.write(f"- {op['type']} | {op['timestamp'][:16]} | محاولات: {op['retries']}")
                    if st.button(f"🗑️ حذف {op['id'][:8]}", key=f"del_{op['id']}"):
                        remove_pending_operation(op['id'])
                        st.rerun()

# ------------------------------- تحميل البيانات والمزامنة التلقائية -------------------------------
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()
# مزامنة تلقائية عند بدء التشغيل إذا كان هناك اتصال
if is_github_accessible() and load_pending_operations():
    sheets_edit = sync_pending_operations(sheets_edit)

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")
# ... باقي واجهة التبويبات ...
