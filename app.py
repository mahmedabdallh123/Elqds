import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import requests
import shutil
import re
from datetime import datetime, timedelta
from base64 import b64decode
import uuid
import io
from PIL import Image

# ------------------------ باقي الكود كما هو (دوال المستخدمين، الملفات، الصور، الأحداث، العرض) ------------------------
# ... (نفس الكود السابق حتى دوال البحث) ...

# ------------------------------- دوال البحث المتقدم -------------------------------
def search_in_all_sheets(all_sheets, search_text, machine_number, section, start_date, end_date, use_date_filter):
    """
    البحث في جميع الشيتات:
    - search_text: بحث عام في جميع الأعمدة النصية (اختياري)
    - machine_number: بحث دقيق في عمود 'رقم الماكينة' (اختياري)
    - section: بحث دقيق في عمود 'القسم' (اختياري)
    - start_date, end_date: فلترة التاريخ (اختياري)
    """
    if not all_sheets:
        return pd.DataFrame()
    
    all_results = []
    
    for sheet_name, df in all_sheets.items():
        if df.empty:
            continue
        
        df_filtered = df.copy()
        
        # 1. تطبيق البحث العام (نص) - يبحث في كل الأعمدة النصية
        if search_text and search_text.strip() != "":
            mask = pd.Series([False] * len(df_filtered))
            for col in df_filtered.columns:
                if df_filtered[col].dtype == 'object':  # أعمدة نصية
                    try:
                        mask = mask | df_filtered[col].astype(str).str.contains(search_text, case=False, na=False)
                    except:
                        pass
            df_filtered = df_filtered[mask]
        
        # 2. فلتر دقيق برقم الماكينة (إذا تم إدخاله)
        if machine_number and machine_number.strip() != "":
            if "رقم الماكينة" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["رقم الماكينة"].astype(str).str.contains(machine_number, case=False, na=False)]
        
        # 3. فلتر دقيق بالقسم (إذا تم إدخاله)
        if section and section.strip() != "":
            if "القسم" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["القسم"].astype(str).str.contains(section, case=False, na=False)]
        
        # 4. فلتر التاريخ (إذا تم تفعيله)
        if use_date_filter and start_date and end_date:
            if "التاريخ" in df_filtered.columns:
                try:
                    df_filtered["التاريخ_temp"] = pd.to_datetime(df_filtered["التاريخ"], errors='coerce')
                    mask = (df_filtered["التاريخ_temp"].dt.date >= start_date) & (df_filtered["التاريخ_temp"].dt.date <= end_date)
                    df_filtered = df_filtered[mask]
                    df_filtered = df_filtered.drop(columns=["التاريخ_temp"])
                except Exception:
                    pass
        
        if not df_filtered.empty:
            df_filtered["الماكينة (الشيت)"] = sheet_name
            all_results.append(df_filtered)
    
    if all_results:
        return pd.concat(all_results, ignore_index=True)
    return pd.DataFrame()

def show_advanced_search(all_sheets):
    """تبويب البحث المتقدم - مع فصل البحث العام عن البحث الدقيق"""
    st.header("🔍 بحث متقدم")
    
    if not all_sheets:
        st.warning("لا توجد بيانات للبحث")
        return
    
    total_sheets = len(all_sheets)
    total_records = sum(len(df) for df in all_sheets.values())
    st.info(f"📊 إجمالي الماكينات: {total_sheets} | إجمالي الأحداث المسجلة: {total_records}")
    
    st.markdown("---")
    
    search_results = None
    
    with st.form(key="search_form"):
        st.subheader("🔎 بحث عام (نصي)")
        search_text = st.text_input("", placeholder="ابحث في أي نص (حدث، إجراء، ملاحظات، رقم ماكينة، قسم...)")
        
        st.markdown("---")
        st.subheader("🎯 بحث دقيق")
        col1, col2 = st.columns(2)
        with col1:
            machine_number = st.text_input("🔢 رقم الماكينة", placeholder="أدخل رقم الماكينة كاملاً أو جزء منه")
        with col2:
            section = st.text_input("🏢 القسم", placeholder="أدخل اسم القسم كاملاً أو جزء منه")
        
        st.markdown("---")
        st.subheader("📅 فلتر التاريخ")
        use_date_filter = st.checkbox("تفعيل الفلتر بالتاريخ")
        if use_date_filter:
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("من تاريخ", value=datetime.now() - timedelta(days=30))
            with col_date2:
                end_date = st.date_input("إلى تاريخ", value=datetime.now())
        else:
            start_date = None
            end_date = None
        
        st.caption("💡 يمكنك استخدام البحث العام مع البحث الدقيق معاً. اترك الحقول الفارغة إذا لم ترد استخدامها.")
        
        submitted = st.form_submit_button("🔍 بحث", type="primary", use_container_width=True)
        
        if submitted:
            with st.spinner("جاري البحث في جميع الماكينات..."):
                search_results = search_in_all_sheets(
                    all_sheets,
                    search_text,
                    machine_number,
                    section,
                    start_date,
                    end_date,
                    use_date_filter
                )
    
    # عرض النتائج خارج النموذج
    if search_results is not None:
        if not search_results.empty:
            st.success(f"✅ تم العثور على {len(search_results)} نتيجة")
            machines_found = search_results["الماكينة (الشيت)"].nunique()
            st.info(f"📊 موزعة على {machines_found} ماكينة/ماكينات")
            
            csv = search_results.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل النتائج (CSV)", csv, f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
            
            st.markdown("---")
            for idx, row in search_results.iterrows():
                with st.expander(f"📋 {row.get('التاريخ', '')} | {row.get('رقم الماكينة', '')} | {row.get('الماكينة (الشيت)', '')} | {row.get('الحدث/العطل', '')[:50]}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**🏭 الماكينة (الشيت):** {row.get('الماكينة (الشيت)', '')}")
                        st.markdown(f"**📅 التاريخ:** {row.get('التاريخ', '')}")
                        st.markdown(f"**🔢 رقم الماكينة:** {row.get('رقم الماكينة', '')}")
                        st.markdown(f"**⚙️ الحدث/العطل:** {row.get('الحدث/العطل', '')}")
                        st.markdown(f"**🔧 الإجراء التصحيحي:** {row.get('الإجراء التصحيحي', '')}")
                    with col2:
                        st.markdown(f"**👨‍🔧 تم بواسطة:** {row.get('تم بواسطة', '')}")
                        st.markdown(f"**⚖️ الطن:** {row.get('الطن', '')}")
                        st.markdown(f"**🏢 القسم:** {row.get('القسم', '')}")
                        st.markdown(f"**📝 ملاحظات:** {row.get('ملاحظات', '')}")
                        images_str = row.get('الصور', '')
                        if images_str and isinstance(images_str, str):
                            st.markdown("**🖼️ الصور:**")
                            for img in images_str.split(", "):
                                img_path = os.path.join(IMAGES_FOLDER, img)
                                if os.path.exists(img_path):
                                    st.image(img_path, width=150)
        else:
            st.warning("❌ لا توجد نتائج مطابقة لبحثك")

# ------------------------ باقي الكود (الواجهة الرئيسية) بدون تغيير ------------------------
