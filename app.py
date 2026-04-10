def manage_data_edit(sheets_edit):
    if sheets_edit is None:
        st.warning("الملف غير موجود. استخدم زر 'تحديث من GitHub' في الشريط الجانبي أولاً")
        return sheets_edit
    
    tab_names = ["📋 عرض الأقسام", "📝 إضافة بيانات", "🔧 إدارة الماكينات", "➕ إضافة قسم جديد", "🔍 فحص البيانات"]
    tabs_edit = st.tabs(tab_names)
    
    with tabs_edit[0]:
        st.subheader("جميع الأقسام")
        if sheets_edit:
            dept_tabs = st.tabs(list(sheets_edit.keys()))
            for i, (dept_name, df) in enumerate(sheets_edit.items()):
                with dept_tabs[i]:
                    display_sheet_data(dept_name, df, f"view_{dept_name}", sheets_edit)
                    with st.expander("✏️ تعديل مباشر للبيانات", expanded=False):
                        edited_df = st.data_editor(df.astype(str), num_rows="dynamic", use_container_width=True, key=f"editor_{dept_name}")
                        if st.button(f"💾 حفظ", key=f"save_{dept_name}"):
                            sheets_edit[dept_name] = edited_df.astype(object)
                            if save_and_push_to_github(sheets_edit, f"تعديل بيانات في قسم {dept_name}"):
                                st.cache_data.clear()
                                st.success("تم الحفظ والرفع إلى GitHub!")
                                st.rerun()
    
    with tabs_edit[1]:
        if sheets_edit:
            sheet_name = st.selectbox("اختر القسم:", list(sheets_edit.keys()), key="add_data_sheet")
            sheets_edit = add_new_data_entry(sheets_edit, sheet_name)
    
    with tabs_edit[2]:
        if sheets_edit:
            sheet_name = st.selectbox("اختر القسم:", list(sheets_edit.keys()), key="manage_machines_sheet")
            manage_machines(sheets_edit, sheet_name)
    
    with tabs_edit[3]:
        sheets_edit = add_new_department(sheets_edit)
    
    with tabs_edit[4]:
        # تبويب فحص البيانات - يساعد في معرفة ما إذا كانت البيانات موجودة
        all_sheets_temp = load_all_sheets()
        show_section_contents(all_sheets_temp)
    
    return sheets_edit
