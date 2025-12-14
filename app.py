# ... (بقية الكود كما هو حتى دالة فحص الإيفينت والكوريكشن)

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن - مع مدة زمنية بين الأحداث
# -------------------------------
def check_events_and_corrections_with_time(all_sheets):
    """فحص الإيفينت والكوريكشن مع إضافة مدة زمنية بين الأحداث"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تهيئة session state إذا لزم الأمر
    if "search_params_time" not in st.session_state:
        st.session_state.search_params_time = {
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "sort_by": "رقم الماكينة",
            "time_filter_enabled": False,
            "min_days": 0,
            "max_days": 365,
            "show_time_diff": True
        }
    
    if "search_triggered_time" not in st.session_state:
        st.session_state.search_triggered_time = False
    
    # قسم البحث - واجهة محسنة مع إضافة المدة الزمنية
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير مع المدة الزمنية")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك تفعيل فلترة المدة الزمنية بين الأحداث.")
        
        # تقسيم الشاشة إلى أعمدة
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # قسم أرقام الماكينات
            with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                st.caption("أدخل أرقام الماكينات (مفصولة بفواصل أو نطاقات)")
                card_numbers = st.text_input(
                    "مثال: 1,3,5 أو 1-5 أو 2,4,7-10",
                    value=st.session_state.search_params_time.get("card_numbers", ""),
                    key="input_cards_time",
                    placeholder="اتركه فارغاً للبحث في كل الماكينات"
                )
                
                # أزرار سريعة لأرقام الماكينات
                st.caption("أو اختر من:")
                quick_cards_col1, quick_cards_col2, quick_cards_col3 = st.columns(3)
                with quick_cards_col1:
                    if st.button("🔟 أول 10 ماكينات", key="quick_10_time"):
                        st.session_state.search_params_time["card_numbers"] = "1-10"
                        st.session_state.search_triggered_time = True
                        st.rerun()
                with quick_cards_col2:
                    if st.button("🔟 ماكينات 11-20", key="quick_20_time"):
                        st.session_state.search_params_time["card_numbers"] = "11-20"
                        st.session_state.search_triggered_time = True
                        st.rerun()
                with quick_cards_col3:
                    if st.button("🗑 مسح", key="clear_cards_time"):
                        st.session_state.search_params_time["card_numbers"] = ""
                        st.rerun()
            
            # قسم التواريخ
            with st.expander("📅 **التواريخ**", expanded=True):
                st.caption("ابحث بالتاريخ (سنة، شهر/سنة)")
                date_input = st.text_input(
                    "مثال: 2024 أو 1/2024 أو 2024,2025",
                    value=st.session_state.search_params_time.get("date_range", ""),
                    key="input_date_time",
                    placeholder="اتركه فارغاً للبحث في كل التواريخ"
                )
        
        with col2:
            # قسم فنيي الخدمة
            with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                st.caption("ابحث بأسماء فنيي الخدمة")
                tech_names = st.text_input(
                    "مثال: أحمد, محمد, علي",
                    value=st.session_state.search_params_time.get("tech_names", ""),
                    key="input_techs_time",
                    placeholder="اتركه فارغاً للبحث في كل الفنيين"
                )
            
            # قسم نص البحث
            with st.expander("📝 **نص البحث**", expanded=True):
                st.caption("ابحث في وصف الحدث أو التصحيح")
                search_text = st.text_input(
                    "مثال: صيانة, إصلاح, تغيير",
                    value=st.session_state.search_params_time.get("search_text", ""),
                    key="input_text_time",
                    placeholder="اتركه فارغاً للبحث في كل النصوص"
                )
        
        # قسم فلترة المدة الزمنية
        with st.expander("⏰ **فلترة المدة الزمنية بين الأحداث**", expanded=False):
            col_time1, col_time2, col_time3 = st.columns(3)
            
            with col_time1:
                time_filter_enabled = st.checkbox(
                    "تفعيل فلترة المدة الزمنية",
                    value=st.session_state.search_params_time.get("time_filter_enabled", False),
                    key="time_filter_checkbox",
                    help="تفعيل البحث عن الأحداث حسب المدة الزمنية بينها"
                )
            
            with col_time2:
                if time_filter_enabled:
                    min_days = st.number_input(
                        "الحد الأدنى للأيام بين الأحداث",
                        min_value=0,
                        max_value=3650,
                        value=st.session_state.search_params_time.get("min_days", 0),
                        key="min_days_input",
                        help="الحد الأدنى للأيام بين حدثين متتاليين"
                    )
                else:
                    min_days = st.session_state.search_params_time.get("min_days", 0)
            
            with col_time3:
                if time_filter_enabled:
                    max_days = st.number_input(
                        "الحد الأقصى للأيام بين الأحداث",
                        min_value=0,
                        max_value=3650,
                        value=st.session_state.search_params_time.get("max_days", 365),
                        key="max_days_input",
                        help="الحد الأقصى للأيام بين حدثين متتاليين"
                    )
                else:
                    max_days = st.session_state.search_params_time.get("max_days", 365)
            
            # خيار إظهار الفروق الزمنية
            show_time_diff = st.checkbox(
                "إظهار الفروق الزمنية بين الأحداث",
                value=st.session_state.search_params_time.get("show_time_diff", True),
                key="show_time_diff_checkbox",
                help="إظهار عدد الأيام بين كل حدث والحدث الذي يسبقه"
            )
        
        # قسم خيارات البحث المتقدمة
        with st.expander("⚙ **خيارات متقدمة**", expanded=False):
            col_adv1, col_adv2, col_adv3 = st.columns(3)
            with col_adv1:
                search_mode = st.radio(
                    "🔍 طريقة البحث:",
                    ["بحث جزئي", "مطابقة كاملة"],
                    index=0 if not st.session_state.search_params_time.get("exact_match") else 1,
                    key="radio_search_mode_time",
                    help="بحث جزئي: يبحث عن النص في أي مكان. مطابقة كاملة: يبحث عن النص مطابق تماماً"
                )
            with col_adv2:
                include_empty = st.checkbox(
                    "🔍 تضمين الحقول الفارغة",
                    value=st.session_state.search_params_time.get("include_empty", True),
                    key="checkbox_include_empty_time",
                    help="تضمين النتائج التي تحتوي على حقول فارغة"
                )
            with col_adv3:
                sort_by = st.selectbox(
                    "📊 ترتيب النتائج:",
                    ["رقم الماكينة", "التاريخ", "فني الخدمة"],
                    index=["رقم الماكينة", "التاريخ", "فني الخدمة"].index(
                        st.session_state.search_params_time.get("sort_by", "رقم الماكينة")
                    ),
                    key="select_sort_by_time"
                )
        
        # زر البحث الرئيسي
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        with col_btn1:
            search_clicked = st.button(
                "🔍 **بدء البحث مع المدة الزمنية**",
                type="primary",
                use_container_width=True,
                key="main_search_btn_time"
            )
        with col_btn2:
            if st.button("🗑 **مسح الحقول**", use_container_width=True, key="clear_fields_time"):
                st.session_state.search_params_time = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة",
                    "time_filter_enabled": False,
                    "min_days": 0,
                    "max_days": 365,
                    "show_time_diff": True
                }
                st.session_state.search_triggered_time = False
                st.rerun()
        with col_btn3:
            if st.button("📊 **عرض كل البيانات**", use_container_width=True, key="show_all_time"):
                st.session_state.search_params_time = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة",
                    "time_filter_enabled": False,
                    "min_days": 0,
                    "max_days": 365,
                    "show_time_diff": True
                }
                st.session_state.search_triggered_time = True
                st.rerun()
    
    # تحديث معايير البحث عند تغيير الحقول
    if card_numbers != st.session_state.search_params_time.get("card_numbers", ""):
        st.session_state.search_params_time["card_numbers"] = card_numbers
    
    if date_input != st.session_state.search_params_time.get("date_range", ""):
        st.session_state.search_params_time["date_range"] = date_input
    
    if tech_names != st.session_state.search_params_time.get("tech_names", ""):
        st.session_state.search_params_time["tech_names"] = tech_names
    
    if search_text != st.session_state.search_params_time.get("search_text", ""):
        st.session_state.search_params_time["search_text"] = search_text
    
    st.session_state.search_params_time["exact_match"] = (search_mode == "مطابقة كاملة")
    st.session_state.search_params_time["include_empty"] = include_empty
    st.session_state.search_params_time["sort_by"] = sort_by
    st.session_state.search_params_time["time_filter_enabled"] = time_filter_enabled
    st.session_state.search_params_time["min_days"] = min_days
    st.session_state.search_params_time["max_days"] = max_days
    st.session_state.search_params_time["show_time_diff"] = show_time_diff
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered_time:
        st.session_state.search_triggered_time = True
        
        # جمع معايير البحث
        search_params = st.session_state.search_params_time.copy()
        
        # عرض معايير البحث
        show_search_params_with_time(search_params)
        
        # تنفيذ البحث
        show_advanced_search_results_with_time(search_params, all_sheets)

def show_search_params_with_time(search_params):
    """عرض معايير البحث المستخدمة مع المدة الزمنية"""
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
        
        if search_params["time_filter_enabled"]:
            params_display.append(f"**⏰ المدة الزمنية:** {search_params['min_days']} - {search_params['max_days']} يوم")
        
        if params_display:
            st.info(" | ".join(params_display))
        else:
            st.info("🔍 **بحث في كل البيانات**")

def show_advanced_search_results_with_time(search_params, all_sheets):
    """عرض نتائج البحث المتقدم مع المدة الزمنية"""
    st.markdown("### 📊 نتائج البحث مع المدة الزمنية")
    
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
    
    # تطبيق فلترة المدة الزمنية إذا كانت مفعلة
    if search_params["time_filter_enabled"] and all_results:
        all_results = filter_events_by_time(all_results, search_params)
    
    # عرض النتائج
    if all_results:
        display_search_results_with_time(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def parse_date_string(date_str):
    """محاولة تحويل نص التاريخ إلى كائن datetime"""
    if not date_str or date_str == "-" or pd.isna(date_str):
        return None
    
    date_formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
        "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
        "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except:
            continue
    
    # محاولة تحليل باستخدام regex
    try:
        # البحث عن نمط dd/mm/yyyy أو yyyy-mm-dd
        match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})', str(date_str))
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = "20" + year if int(year) < 50 else "19" + year
            
            day = int(day)
            month = int(month)
            year = int(year)
            
            if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
                return datetime(year, month, day)
    except:
        pass
    
    return None

def calculate_time_difference(date1_str, date2_str):
    """حساب الفرق الزمني بالايام بين تاريخين"""
    date1 = parse_date_string(date1_str)
    date2 = parse_date_string(date2_str)
    
    if date1 is None or date2 is None:
        return None
    
    # حساب الفرق بالأيام (قيمة مطلقة)
    return abs((date2 - date1).days)

def filter_events_by_time(events, search_params):
    """تصفية الأحداث بناءً على المدة الزمنية بينها"""
    if not events:
        return []
    
    # تجميع الأحداث حسب الماكينة
    events_by_machine = {}
    for event in events:
        machine = event.get("Card Number")
        if machine not in events_by_machine:
            events_by_machine[machine] = []
        events_by_machine[machine].append(event)
    
    # تصفية الأحداث لكل ماكينة
    filtered_events = []
    min_days = search_params.get("min_days", 0)
    max_days = search_params.get("max_days", 365)
    
    for machine, machine_events in events_by_machine.items():
        # ترتيب الأحداث حسب التاريخ (من الأقدم للأحدث)
        sorted_events = sorted(machine_events, 
                             key=lambda x: parse_date_string(x.get("Date")) or datetime.min)
        
        if len(sorted_events) >= 2:
            for i in range(len(sorted_events)):
                current_event = sorted_events[i]
                current_date = current_event.get("Date")
                
                if i == 0:
                    # الحدث الأول - حساب الفرق مع الحدث الثاني
                    next_event = sorted_events[i + 1]
                    next_date = next_event.get("Date")
                    
                    time_diff = calculate_time_difference(current_date, next_date)
                    
                    if time_diff is not None and min_days <= time_diff <= max_days:
                        current_event["Time_Diff_Next"] = time_diff
                        current_event["Time_Diff_Prev"] = None
                        filtered_events.append(current_event)
                
                elif i == len(sorted_events) - 1:
                    # الحدث الأخير - حساب الفرق مع الحدث السابق
                    prev_event = sorted_events[i - 1]
                    prev_date = prev_event.get("Date")
                    
                    time_diff = calculate_time_difference(current_date, prev_date)
                    
                    if time_diff is not None and min_days <= time_diff <= max_days:
                        current_event["Time_Diff_Next"] = None
                        current_event["Time_Diff_Prev"] = time_diff
                        filtered_events.append(current_event)
                
                else:
                    # حدث في المنتصف - حساب الفرق مع الحدثين السابق والتالي
                    prev_event = sorted_events[i - 1]
                    next_event = sorted_events[i + 1]
                    
                    prev_date = prev_event.get("Date")
                    next_date = next_event.get("Date")
                    
                    time_diff_prev = calculate_time_difference(current_date, prev_date)
                    time_diff_next = calculate_time_difference(current_date, next_date)
                    
                    # التحقق إذا كان أي من الفروق ضمن النطاق المحدد
                    within_range = False
                    if time_diff_prev is not None and min_days <= time_diff_prev <= max_days:
                        within_range = True
                    if time_diff_next is not None and min_days <= time_diff_next <= max_days:
                        within_range = True
                    
                    if within_range:
                        current_event["Time_Diff_Prev"] = time_diff_prev
                        current_event["Time_Diff_Next"] = time_diff_next
                        filtered_events.append(current_event)
        else:
            # إذا كان هناك حدث واحد فقط، نضيفه إذا كانت الفلترة تسمح بذلك
            if len(sorted_events) == 1:
                single_event = sorted_events[0]
                single_event["Time_Diff_Prev"] = None
                single_event["Time_Diff_Next"] = None
                filtered_events.append(single_event)
    
    return filtered_events

def display_search_results_with_time(results, search_params):
    """عرض نتائج البحث بشكل احترافي مع المدة الزمنية"""
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
    st.markdown("### 📈 إحصائيات النتائج مع المدة الزمنية")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(display_df))
    
    with col2:
        unique_machines = display_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        # حساب متوسط الفروق الزمنية إذا كانت موجودة
        if 'Time_Diff_Prev' in display_df.columns or 'Time_Diff_Next' in display_df.columns:
            # جمع الفروق الزمنية
            time_diffs = []
            if 'Time_Diff_Prev' in display_df.columns:
                time_diffs.extend(display_df['Time_Diff_Prev'].dropna().tolist())
            if 'Time_Diff_Next' in display_df.columns:
                time_diffs.extend(display_df['Time_Diff_Next'].dropna().tolist())
            
            if time_diffs:
                avg_diff = sum(time_diffs) / len(time_diffs)
                st.metric("⏰ متوسط الفرق الزمني (يوم)", f"{avg_diff:.1f}")
            else:
                st.metric("⏰ متوسط الفرق الزمني", "غير متاح")
        else:
            st.metric("⏰ متوسط الفرق الزمني", "غير مفعل")
    
    with col4:
        # حساب الماكينات ذات الفروق الزمنية العالية/المنخفضة
        if 'Time_Diff_Prev' in display_df.columns or 'Time_Diff_Next' in display_df.columns:
            # حساب عدد الماكينات التي لديها فروق زمنية ضمن نطاق معين
            machines_with_data = set()
            for _, row in display_df.iterrows():
                if (pd.notna(row.get('Time_Diff_Prev')) or 
                    pd.notna(row.get('Time_Diff_Next'))):
                    machines_with_data.add(row['Card Number'])
            
            st.metric("🔢 مكن مع فروق زمنية", len(machines_with_data))
        else:
            st.metric("🔢 مكن مع فروق زمنية", 0)
    
    st.markdown("---")
    
    # عرض الفروق الزمنية إذا كان الخيار مفعلاً
    if search_params.get("show_time_diff", False):
        st.markdown("### ⏰ الفروق الزمنية بين الأحداث")
        
        # إضافة عمود يوضح الفروق الزمنية
        if 'Time_Diff_Prev' in display_df.columns or 'Time_Diff_Next' in display_df.columns:
            # إنشاء عمود مدمج للفروق الزمنية
            time_diff_display = []
            for _, row in display_df.iterrows():
                prev_diff = row.get('Time_Diff_Prev')
                next_diff = row.get('Time_Diff_Next')
                
                if pd.notna(prev_diff) and pd.notna(next_diff):
                    time_diff_display.append(f"← {int(prev_diff)} يوم → {int(next_diff)} يوم")
                elif pd.notna(prev_diff):
                    time_diff_display.append(f"← {int(prev_diff)} يوم")
                elif pd.notna(next_diff):
                    time_diff_display.append(f"→ {int(next_diff)} يوم")
                else:
                    time_diff_display.append("-")
            
            display_df['الفرق الزمني (يوم)'] = time_diff_display
            
            # إضافة تصنيف للفروق الزمنية
            def classify_time_diff(row):
                prev_diff = row.get('Time_Diff_Prev')
                next_diff = row.get('Time_Diff_Next')
                
                if pd.notna(prev_diff):
                    diff_to_check = prev_diff
                elif pd.notna(next_diff):
                    diff_to_check = next_diff
                else:
                    return "غير محدد"
                
                if diff_to_check < 7:
                    return "قريب جداً"
                elif diff_to_check < 30:
                    return "قريب"
                elif diff_to_check < 90:
                    return "متوسط"
                elif diff_to_check < 180:
                    return "بعيد"
                else:
                    return "بعيد جداً"
            
            if 'Time_Diff_Prev' in display_df.columns or 'Time_Diff_Next' in display_df.columns:
                display_df['تصنيف الفرق الزمني'] = display_df.apply(classify_time_diff, axis=1)
    
    # فلترة النتائج
    st.markdown("#### 🔍 فلترة النتائج")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    
    with filter_col1:
        show_with_event = st.checkbox("📝 مع حدث", True, key="filter_event_time")
    with filter_col2:
        show_with_correction = st.checkbox("✏ مع تصحيح", True, key="filter_correction_time")
    with filter_col3:
        show_with_tech = st.checkbox("👨‍🔧 مع فني خدمة", True, key="filter_tech_time")
    with filter_col4:
        if search_params.get("show_time_diff", False) and 'تصنيف الفرق الزمني' in display_df.columns:
            time_categories = sorted(display_df['تصنيف الفرق الزمني'].unique())
            selected_time_cat = st.multiselect(
                "⏰ تصنيف الفرق الزمني",
                options=time_categories,
                default=time_categories,
                key="filter_time_cat"
            )
    
    # تطبيق الفلاتر
    filtered_df = display_df.copy()
    
    if not show_with_event and 'Event' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Event"] != "-"]
    if not show_with_correction and 'Correction' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Correction"] != "-"]
    if not show_with_tech and 'Servised by' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Servised by"] != "-"]
    
    if search_params.get("show_time_diff", False) and 'تصنيف الفرق الزمني' in filtered_df.columns and selected_time_cat:
        filtered_df = filtered_df[filtered_df['تصنيف الفرق الزمني'].isin(selected_time_cat)]
    
    # عرض النتائج
    if not filtered_df.empty:
        # تحديد الأعمدة المراد عرضها
        columns_to_show = ['Card Number', 'Event', 'Correction', 'Servised by', 
                          'Tones', 'Date', 'Event_Order', 'Total_Events']
        
        # إضافة أعمدة المدة الزمنية إذا كانت موجودة
        if search_params.get("show_time_diff", False):
            if 'الفرق الزمني (يوم)' in filtered_df.columns:
                columns_to_show.append('الفرق الزمني (يوم)')
            if 'تصنيف الفرق الزمني' in filtered_df.columns:
                columns_to_show.append('تصنيف الفرق الزمني')
        
        # عرض البيانات في جدول
        st.dataframe(
            filtered_df[columns_to_show].style.apply(style_table, axis=1),
            use_container_width=True,
            height=500
        )
        
        # عرض تحليل الفروق الزمنية
        if search_params.get("show_time_diff", False) and ('Time_Diff_Prev' in filtered_df.columns or 'Time_Diff_Next' in filtered_df.columns):
            show_time_difference_analysis(filtered_df, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير الفلترة")
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        # تصدير Excel
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
                file_name=f"بحث_أحداث_مع_زمن_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
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
                file_name=f"بحث_أحداث_مع_زمن_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("⚠ لا توجد بيانات للتصدير")

def show_time_difference_analysis(df, search_params):
    """عرض تحليل الفروق الزمنية بين الأحداث"""
    if not search_params.get("show_time_diff", False):
        return
    
    st.markdown("### 📊 تحليل الفروق الزمنية بين الأحداث")
    
    # إنشاء تبويبات للتحليل
    time_tabs = st.tabs(["📈 إحصائيات الفروق", "📊 توزيع الفروق", "🔍 الأكثر تكراراً"])
    
    with time_tabs[0]:
        st.markdown("#### 📈 إحصائيات الفروق الزمنية")
        
        # جمع جميع الفروق الزمنية
        all_diffs = []
        if 'Time_Diff_Prev' in df.columns:
            all_diffs.extend(df['Time_Diff_Prev'].dropna().tolist())
        if 'Time_Diff_Next' in df.columns:
            all_diffs.extend(df['Time_Diff_Next'].dropna().tolist())
        
        if all_diffs:
            # حساب الإحصائيات
            stats_data = {
                "إجمالي الفروق": len(all_diffs),
                "متوسط الفرق (يوم)": f"{sum(all_diffs) / len(all_diffs):.1f}",
                "أقل فرق (يوم)": min(all_diffs),
                "أعلى فرق (يوم)": max(all_diffs),
                "الفرق المتوسط (يوم)": f"{pd.Series(all_diffs).median():.1f}",
                "الانحراف المعياري (يوم)": f"{pd.Series(all_diffs).std():.1f}"
            }
            
            # عرض الإحصائيات
            for key, value in stats_data.items():
                st.info(f"**{key}:** {value}")
            
            # عرض الماكينات ذات الفروق المتطرفة
            st.markdown("##### 📋 الماكينات ذات الفروق المتطرفة")
            
            # البحث عن الماكينات ذات أعلى وأقل فروق
            machine_diffs = {}
            for _, row in df.iterrows():
                machine = row['Card Number']
                prev_diff = row.get('Time_Diff_Prev')
                next_diff = row.get('Time_Diff_Next')
                
                if pd.notna(prev_diff):
                    if machine not in machine_diffs:
                        machine_diffs[machine] = []
                    machine_diffs[machine].append(prev_diff)
                
                if pd.notna(next_diff):
                    if machine not in machine_diffs:
                        machine_diffs[machine] = []
                    machine_diffs[machine].append(next_diff)
            
            # حساب المتوسط لكل ماكينة
            machine_avg = {}
            for machine, diffs in machine_diffs.items():
                if diffs:
                    machine_avg[machine] = sum(diffs) / len(diffs)
            
            # عرض أعلى 5 وأقل 5
            if machine_avg:
                sorted_machines = sorted(machine_avg.items(), key=lambda x: x[1])
                
                col_ext1, col_ext2 = st.columns(2)
                
                with col_ext1:
                    st.markdown("**أقل 5 فروق (أكثر تكراراً):**")
                    for machine, avg in sorted_machines[:5]:
                        st.write(f"- الماكينة {machine}: {avg:.1f} يوم")
                
                with col_ext2:
                    st.markdown("**أعلى 5 فروق (أقل تكراراً):**")
                    for machine, avg in sorted_machines[-5:]:
                        st.write(f"- الماكينة {machine}: {avg:.1f} يوم")
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض الإحصائيات")
    
    with time_tabs[1]:
        st.markdown("#### 📊 توزيع الفروق الزمنية")
        
        # جمع جميع الفروق الزمنية
        all_diffs = []
        if 'Time_Diff_Prev' in df.columns:
            all_diffs.extend(df['Time_Diff_Prev'].dropna().tolist())
        if 'Time_Diff_Next' in df.columns:
            all_diffs.extend(df['Time_Diff_Next'].dropna().tolist())
        
        if all_diffs:
            # إنشاء DataFrame للفروق
            diffs_df = pd.DataFrame({'الفرق_بالأيام': all_diffs})
            
            # محاولة عرض مخطط باستخدام plotly
            try:
                import plotly.express as px
                import plotly.graph_objects as go
                
                # مخطط توزيع الفروق
                fig1 = px.histogram(
                    diffs_df, 
                    x='الفرق_بالأيام',
                    nbins=20,
                    title='توزيع الفروق الزمنية بين الأحداث',
                    labels={'الفرق_بالأيام': 'الفرق بالأيام'},
                    color_discrete_sequence=['#4ECDC4']
                )
                fig1.update_layout(
                    xaxis_title="الفرق بالأيام",
                    yaxis_title="التكرار",
                    height=400
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                # مخطط المدرج التكراري مع متوسط الفرق
                avg_diff = diffs_df['الفرق_بالأيام'].mean()
                fig2 = go.Figure()
                fig2.add_trace(go.Histogram(
                    x=diffs_df['الفرق_بالأيام'],
                    name='الفروق',
                    marker_color='#FF6B6B'
                ))
                fig2.add_vline(
                    x=avg_diff,
                    line_dash="dash",
                    line_color="green",
                    annotation_text=f"المتوسط: {avg_diff:.1f} يوم"
                )
                fig2.update_layout(
                    title='توزيع الفروق مع خط المتوسط',
                    xaxis_title="الفرق بالأيام",
                    yaxis_title="التكرار",
                    height=400
                )
                st.plotly_chart(fig2, use_container_width=True)
                
            except ImportError:
                # استخدام streamlit charts بدلاً من plotly
                st.markdown("**📊 توزيع الفروق الزمنية:**")
                
                # إنشاء فئات للفروق
                bins = [0, 7, 30, 90, 180, 365, float('inf')]
                labels = ['أقل من أسبوع', 'أسبوع - شهر', 'شهر - 3 شهور', 
                         '3 - 6 شهور', '6 - 12 شهر', 'أكثر من سنة']
                
                diffs_series = pd.Series(all_diffs)
                binned_diffs = pd.cut(diffs_series, bins=bins, labels=labels, right=False)
                binned_counts = binned_diffs.value_counts().sort_index()
                
                # عرض البيانات في جدول
                dist_table = pd.DataFrame({
                    'الفئة الزمنية': binned_counts.index,
                    'عدد الأحداث': binned_counts.values,
                    'النسبة': (binned_counts.values / len(all_diffs) * 100).round(1)
                })
                st.dataframe(dist_table, use_container_width=True)
                
                # مخطط شريطي بسيط
                st.bar_chart(binned_counts, height=400)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض المخططات")
    
    with time_tabs[2]:
        st.markdown("#### 🔍 الأحداث الأكثر تكراراً والأقل تكراراً")
        
        # تحليل تكرار الأحداث
        if 'Time_Diff_Prev' in df.columns or 'Time_Diff_Next' in df.columns:
            # حساب تكرار الأحداث لكل ماكينة
            event_counts = df.groupby('Card Number').size().reset_index(name='عدد الأحداث')
            
            if not event_counts.empty:
                # ترتيب حسب عدد الأحداث
                event_counts_sorted = event_counts.sort_values('عدد الأحداث', ascending=False)
                
                col_freq1, col_freq2 = st.columns(2)
                
                with col_freq1:
                    st.markdown("**🔝 أعلى 5 ماكينات في عدد الأحداث:**")
                    top_machines = event_counts_sorted.head()
                    for _, row in top_machines.iterrows():
                        st.write(f"- الماكينة {row['Card Number']}: {row['عدد الأحداث']} حدث")
                
                with col_freq2:
                    st.markdown("**📉 أقل 5 ماكينات في عدد الأحداث:**")
                    bottom_machines = event_counts_sorted.tail()
                    for _, row in bottom_machines.iterrows():
                        st.write(f"- الماكينة {row['Card Number']}: {row['عدد الأحداث']} حدث")
                
                # تحليل الفروق الزمنية لكل ماكينة
                st.markdown("##### 📊 متوسط الفروق الزمنية لكل ماكينة")
                
                machine_stats = []
                for machine in event_counts['Card Number'].unique():
                    machine_data = df[df['Card Number'] == machine]
                    
                    # جمع الفروق الزمنية
                    machine_diffs = []
                    if 'Time_Diff_Prev' in machine_data.columns:
                        machine_diffs.extend(machine_data['Time_Diff_Prev'].dropna().tolist())
                    if 'Time_Diff_Next' in machine_data.columns:
                        machine_diffs.extend(machine_data['Time_Diff_Next'].dropna().tolist())
                    
                    if machine_diffs:
                        avg_diff = sum(machine_diffs) / len(machine_diffs)
                        machine_stats.append({
                            'الماكينة': machine,
                            'عدد الأحداث': len(machine_data),
                            'متوسط الفرق الزمني': f"{avg_diff:.1f} يوم",
                            'تصنيف التكرار': 'عالية' if len(machine_data) > event_counts['عدد الأحداث'].mean() else 'منخفضة'
                        })
                
                if machine_stats:
                    stats_df = pd.DataFrame(machine_stats)
                    st.dataframe(stats_df, use_container_width=True, height=300)
            else:
                st.info("ℹ️ لا توجد بيانات كافية لعرض تحليل التكرار")
        else:
            st.info("ℹ️ لم يتم تفعيل خيار عرض الفروق الزمنية")

# ... (بقية الكود كما هو، وفي الواجهة الرئيسية):

# في الواجهة الرئيسية، عند التبويبات:
# Tab: فحص الإيفينت والكوريكشن (لجميع المستخدمين)
with tabs[1]:
    # إنشاء تبويبات داخلية للاختيار بين البحث العادي والبحث مع المدة الزمنية
    search_type_tabs = st.tabs(["🔍 بحث عادي", "⏰ بحث مع المدة الزمنية"])
    
    # البحث العادي
    with search_type_tabs[0]:
        st.header("📋 فحص الإيفينت والكوريكشن (عادي)")
        
        if all_sheets is None:
            st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
        else:
            # استدعاء الدالة العادية
            check_events_and_corrections(all_sheets)
    
    # البحث مع المدة الزمنية
    with search_type_tabs[1]:
        st.header("📋 فحص الإيفينت والكوريكشن مع المدة الزمنية")
        
        if all_sheets is None:
            st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
        else:
            # استدعاء الدالة الجديدة مع المدة الزمنية
            check_events_and_corrections_with_time(all_sheets)

# ... (بقية الكود كما هو)
