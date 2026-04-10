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

# ------------------------ باقي الكود (دوال المستخدمين، الملفات، الصور، الأحداث، إلخ) كما هو سابق ------------------------
# ... (لم يتغير شيء في الأجزاء السابقة حتى دوال البحث) ...

# ------------------------------- دوال إدارة الماكينات (الشيتات) -------------------------------
def rename_sheet(sheets_edit, old_name, new_name):
    """إعادة تسمية شيت (ماكينة)"""
    if old_name not in sheets_edit:
        return sheets_edit, False, "الماكينة غير موجودة"
    if new_name in sheets_edit:
        return sheets_edit, False, "الاسم الجديد موجود بالفعل"
    clean_name = re.sub(r'[\\/*?:"<>|]', '_', new_name.strip())
    if not clean_name:
        return sheets_edit, False, "اسم غير صالح"
    sheets_edit[clean_name] = sheets_edit.pop(old_name)
    return sheets_edit, True, f"تم تغيير اسم الماكينة من '{old_name}' إلى '{clean_name}'"

def delete_sheet(sheets_edit, sheet_name):
    """حذف شيت (ماكينة) بالكامل مع جميع سجلاتها"""
    if sheet_name not in sheets_edit:
        return sheets_edit, False, "الماكينة غير موجودة"
    # حذف الصور المرتبطة بالسجلات (اختياري، قد تبقى صور بدون مرجع)
    del sheets_edit[sheet_name]
    return sheets_edit, True, f"تم حذف الماكينة '{sheet_name}' وجميع سجلاتها"

# ------------------------------- دوال العرض (معدلة) -------------------------------
def display_sheet_data_with_events(sheet_name, df, unique_id, sheets_edit, can_edit):
    """عرض بيانات الشيت مع إمكانية تعديل وحذف الأحداث، وتعديل/حذف الماكينة نفسها"""
    st.markdown(f"### {sheet_name}")
    
    # أزرار إدارة الماكينة (تعديل الاسم وحذف الماكينة)
    if can_edit:
        col_rename, col_delete = st.columns(2)
        with col_rename:
            if st.button(f"✏️ تعديل اسم الماكينة", key=f"rename_machine_{unique_id}"):
                st.session_state[f"rename_mode_{unique_id}"] = True
        with col_delete:
            if st.button(f"🗑️ حذف الماكينة بالكامل", key=f"delete_machine_{unique_id}"):
                st.session_state[f"confirm_delete_{unique_id}"] = True
        
        # نموذج إعادة التسمية
        if st.session_state.get(f"rename_mode_{unique_id}", False):
            with st.form(key=f"rename_form_{unique_id}"):
                new_name = st.text_input("الاسم الجديد للماكينة:", value=sheet_name)
                submitted = st.form_submit_button("تأكيد التعديل")
                if submitted:
                    new_sheets_edit, success, msg = rename_sheet(sheets_edit, sheet_name, new_name)
                    if success:
                        if save_to_github(new_sheets_edit, f"تعديل اسم الماكينة من {sheet_name} إلى {new_name}"):
                            st.success(msg)
                            st.session_state[f"rename_mode_{unique_id}"] = False
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("فشل الحفظ")
                    else:
                        st.error(msg)
            if st.button("إلغاء", key=f"cancel_rename_{unique_id}"):
                st.session_state[f"rename_mode_{unique_id}"] = False
                st.rerun()
        
        # تأكيد حذف الماكينة
        if st.session_state.get(f"confirm_delete_{unique_id}", False):
            st.warning(f"⚠️ هل أنت متأكد من حذف الماكينة '{sheet_name}' وجميع سجلاتها؟ هذا الإجراء لا يمكن التراجع عنه.")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("نعم، احذف", key=f"confirm_yes_{unique_id}"):
                    new_sheets_edit, success, msg = delete_sheet(sheets_edit, sheet_name)
                    if success:
                        if save_to_github(new_sheets_edit, f"حذف الماكينة {sheet_name}"):
                            st.success(msg)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("فشل الحفظ")
                    else:
                        st.error(msg)
            with col_no:
                if st.button("لا، إلغاء", key=f"confirm_no_{unique_id}"):
                    st.session_state[f"confirm_delete_{unique_id}"] = False
                    st.rerun()
    
    st.info(f"عدد السجلات: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    # فلتر حسب رقم الماكينة والقسم (كما هو)
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        if "رقم الماكينة" in df.columns:
            machines = ["الكل"] + sorted(df["رقم الماكينة"].dropna().unique().astype(str).tolist())
            selected_machine = st.selectbox("فلتر حسب رقم الماكينة:", machines, key=f"machine_filter_{unique_id}")
            if selected_machine != "الكل":
                df = df[df["رقم الماكينة"].astype(str) == selected_machine]
    with col_filter2:
        if "القسم" in df.columns:
            sections = ["الكل"] + sorted(df["القسم"].dropna().unique().tolist())
            selected_section = st.selectbox("فلتر حسب القسم:", sections, key=f"section_filter_{unique_id}")
            if selected_section != "الكل":
                df = df[df["القسم"].astype(str) == selected_section]
    
    st.markdown("---")
    
    # عرض الأحداث (مع إمكانية تعديل وحذف كل حدث) - كما هو موجود سابقاً
    if not df.empty:
        for idx, row in df.iterrows():
            with st.expander(f"📋 {row.get('التاريخ', 'تاريخ غير محدد')} - {row.get('رقم الماكينة', 'رقم غير محدد')} - {row.get('الحدث/العطل', 'حدث غير محدد')[:50]}"):
                # ... (نفس الكود السابق لعرض تفاصيل الحدث وأزرار تعديل/حذف الحدث) ...
                # (لم يتغير شيء في هذا الجزء)
                pass
    else:
        st.info("لا توجد سجلات")

# ------------------------ باقي الكود (الواجهة الرئيسية) كما هو ------------------------
