import streamlit as st
# =========================
# 🔐 SIMPLE LOGIN SYSTEM
# =========================
def login():
   st.title("🔐 Login")
   username = st.text_input("Username")
   password = st.text_input("Password", type="password")
   if st.button("Login"):
       if username == "admin" and password == "1234":
           st.session_state["logged_in"] = True
       else:
           st.error("Invalid credentials")
# Session check
if "logged_in" not in st.session_state:
   st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
   login()
   st.stop()


import streamlit as st
import pdfplumber
import pandas as pd
import tabula
import re
import tempfile
import os

# =========================
# 🔹 HELPER FUNCTIONS
# =========================
def extract_between(text: str, start: str, end: str) -> str:
   pattern = re.escape(start) + r'\s*(.*?)\s*' + re.escape(end)
   m = re.search(pattern, text, flags=re.DOTALL)
   return m.group(1).strip() if m else ""
def extract_pincode(text):
   if not text:
       return ""
   matches = re.findall(r'\b\d{6}\b', text)
   return matches[-1] if matches else ""
# =========================
# 🔹 PDF PROCESS FUNCTION
# =========================
def process_pdf(pdf_file):
   final_output = []
   # Save temp file
   with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
       tmp.write(pdf_file.read())
       pdf_path = tmp.name
   try:
       # -------- TEXT EXTRACTION --------
       with pdfplumber.open(pdf_path) as pdf:
           page = pdf.pages[0]
           width = page.width
           height = page.height
           split_ratio = 0.48
           left_text = page.within_bbox((0, 0, width * split_ratio, height)).extract_text() or ""
           right_text = page.within_bbox((width * split_ratio, 0, width, height)).extract_text() or ""
       # -------- HEADER --------
       shipped_from = extract_between(right_text, "Shipped From:", "Shipped To:")
       shipped_to = extract_between(right_text, "Shipped To:", "GSTIN:")
       billed_from = extract_between(left_text, "Billed From:", "Billed To:")
       billed_to = extract_between(left_text, "Billed To:", "GSTIN:")
       header_data = {
           "File Name": pdf_file.name,
           "Shipped From": shipped_from,
           "Ship From Pincode": extract_pincode(shipped_from),
           "Shipped To": shipped_to,
           "Ship To Pincode": extract_pincode(shipped_to),
           "Billed From": billed_from,
           "Bill From Pincode": extract_pincode(billed_from),
           "Billed To": billed_to,
           "Bill To Pincode": extract_pincode(billed_to)
       }
       # -------- TABLE --------
       tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
       all_data = []
       for df in tables:
           if df is None or df.empty:
               continue
           df = df.dropna(how='all').reset_index(drop=True)
           if df.shape[0] < 2:
               continue
           df.columns = df.columns.astype(str).str.replace("\r", " ").str.strip()
           df = df.applymap(lambda x: str(x).strip() if pd.notnull(x) else x)
           df = df[~df.apply(lambda row: row.astype(str).str.contains(
               'Total|GST|Amount', case=False, na=False
           ).any(), axis=1)]
           if not df.empty:
               all_data.append(df)
       if all_data:
           final_df = pd.concat(all_data, ignore_index=True)
       else:
           final_df = pd.DataFrame()
       for key, value in header_data.items():
           final_df[key] = value
       return final_df
   except Exception as e:
       st.error(f"Error processing {pdf_file.name}: {e}")
       return None
   finally:
       os.remove(pdf_path)
# =========================
# 🔹 STREAMLIT UI
# =========================
st.set_page_config(page_title="PDF Extractor", layout="wide")
st.title("📄 PDF to Excel Extractor")
uploaded_files = st.file_uploader(
   "Upload PDF files",
   type=["pdf"],
   accept_multiple_files=True
)
if uploaded_files:
   st.write(f"📂 {len(uploaded_files)} file(s) uploaded")
   if st.button("🚀 Extract Data"):
       progress_bar = st.progress(0)
       all_results = []
       for i, file in enumerate(uploaded_files):
           st.write(f"Processing: {file.name}")
           df = process_pdf(file)
           if df is not None and not df.empty:
               all_results.append(df)
           progress_bar.progress((i + 1) / len(uploaded_files))
       if all_results:
           final_df = pd.concat(all_results, ignore_index=True)
           st.success("✅ Extraction Completed!")
           # Preview
           st.dataframe(final_df)
           # Download
           excel_file = "output.xlsx"
           final_df.to_excel(excel_file, index=False)
           with open(excel_file, "rb") as f:
               st.download_button(
                   label="📥 Download Excel",
                   data=f,
                   file_name="FINAL_OUTPUT.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
               )
       else:
           st.error("❌ No data extracted")