# =========================================================
# 🚀 STREAMLIT WEB UI VERSION - PDF TO EXCEL EXTRACTOR
# =========================================================
import streamlit as st
# =========================
# 🔐 SIMPLE LOGIN SYSTEM
# =========================
def login():
   st.title("🔐 Login")
   username = st.text_input("Username")
   password = st.text_input("Password", type="password")
   if st.button("Login"):
       if username == "Rohith" and password == "Rohith@1234":
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
import re
import os
import tempfile
from io import BytesIO

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="SAP PDF Extractor",
    page_icon="📄",
    layout="wide"
)

# =========================================================
# CUSTOM CSS
# =========================================================
st.markdown("""
<style>
.main {
    padding-top: 1rem;
}

.stButton>button {
    width: 100%;
    background-color: #0066cc;
    color: white;
    border-radius: 10px;
    height: 3em;
    font-size: 16px;
}

.upload-box {
    border: 2px dashed #999;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
}

.success-box {
    padding: 15px;
    background-color: #d4edda;
    border-radius: 10px;
    color: #155724;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# TITLE
# =========================================================
st.title("📄 SAP DC Data Extractor")
st.markdown("### Upload PDF files and extract DC data into Excel")

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def extract_between(text: str, start: str, end: str) -> str:
    pattern = re.escape(start) + r'\s*(.*?)\s*' + re.escape(end)
    match = re.search(pattern, text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_pincode(text):
    matches = re.findall(r'\b\d{6}\b', text or "")
    return matches[-1] if matches else ""


# =========================================================
# CLEAN TABLE
# =========================================================
def clean_table(df):

    df = df.dropna(how='all').reset_index(drop=True)

    if df.shape[0] > 1:
        first_row = df.iloc[0].astype(str).str.lower()

        if any(x in ' '.join(first_row) for x in ['sl', 'desc', 'hsn', 'qty']):
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)

    df.columns = (
        pd.Series(df.columns)
        .astype(str)
        .str.replace("\n", " ")
        .str.replace("\r", " ")
        .str.strip()
    )

    df = df.loc[:, ~df.columns.str.contains('^Unnamed', case=False)]

    df = df.applymap(lambda x: str(x).strip() if pd.notnull(x) else "")

    return df


# =========================================================
# HEADER EXTRACTION
# =========================================================
def extract_header_data(pdf_path, file_name):

    with pdfplumber.open(pdf_path) as pdf:

        page = pdf.pages[0]

        width, height = page.width, page.height
        split_ratio = 0.48

        left_text = page.within_bbox(
            (0, 0, width * split_ratio, height)
        ).extract_text() or ""

        right_text = page.within_bbox(
            (width * split_ratio, 0, width, height)
        ).extract_text() or ""

    return {
        "File Name": file_name,
        "Shipped From": extract_between(right_text, "Shipped From:", "GSTIN:"),
        "Ship From Pincode": extract_pincode(right_text),
        "Shipped To": extract_between(right_text, "Shipped To:", "GSTIN:"),
        "Ship To Pincode": extract_pincode(right_text),
        "Billed From": extract_between(left_text, "Billed From:", "GSTIN:"),
        "Bill From Pincode": extract_pincode(left_text),
        "Billed To": extract_between(left_text, "Billed To:", "GSTIN:"),
        "Bill To Pincode": extract_pincode(left_text),
        "Invoice Num": extract_between(left_text, "Invoice No:", "Date:"),
        "Invoice Date": extract_between(left_text, "Date:", "P.O No"),
        "PO Number": extract_between(left_text, "P.O No.", "IRN No.")
    }


# =========================================================
# TABLE EXTRACTION
# =========================================================
def extract_table_data(pdf_path):

    all_data = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            tables = page.extract_tables()

            for table in tables:

                if not table or len(table) < 2:
                    continue

                df = pd.DataFrame(table)
                df = clean_table(df)

                # Normalize columns
                col_map = {}

                for col in df.columns:

                    c = col.lower()

                    if 'sl' in c:
                        col_map[col] = 'Sl.No'

                    elif 'desc' in c:
                        col_map[col] = 'Description'

                    elif 'hsn' in c:
                        col_map[col] = 'HSN'

                    elif 'qty' in c:
                        col_map[col] = 'Qty'

                df = df.rename(columns=col_map)

                # =========================================================
                # DIRECT EXTRACTION
                # =========================================================
                if 'Description' in df.columns:

                    for col in ['Sl.No', 'HSN', 'Qty']:
                        if col not in df.columns:
                            df[col] = ""

                    # Fix Sl.No
                    df['Sl.No'] = df['Sl.No'].astype(str)

                    df.loc[
                        df['Sl.No'].str.strip() == "",
                        'Sl.No'
                    ] = df['Description'].str.extract(r'^(\d+)')[0]

                    # Remove blank serial numbers
                    df = df[
                        df['Sl.No'].notna() &
                        (df['Sl.No'].astype(str).str.strip() != "")
                    ]

                    # Cleaning
                    df['Description'] = (
                        df['Description']
                        .str.replace(r'\s+', ' ', regex=True)
                        .str.strip()
                    )

                    df['Qty'] = (
                        df['Qty']
                        .astype(str)
                        .str.extract(r'(\d+)')[0]
                        .fillna("")
                    )

                    df['HSN'] = (
                        df['HSN']
                        .astype(str)
                        .str.extract(r'(\d{6,8})')[0]
                        .fillna("")
                    )

                    # Remove total/gst rows
                    df = df[
                        ~df['Description'].str.contains(
                            'total|gst|cgst|sgst|igst',
                            case=False,
                            na=False
                        )
                    ]

                    all_data.append(
                        df[['Sl.No', 'Description', 'HSN', 'Qty']]
                    )

                    continue

                # =========================================================
                # FALLBACK EXTRACTION
                # =========================================================
                df['merged'] = df.apply(
                    lambda row: ' '.join(
                        [str(x) for x in row if pd.notnull(x)]
                    ),
                    axis=1
                )

                for row in df['merged']:

                    if not re.match(r'^\d+', row):
                        continue

                    slno = re.match(r'^(\d+)', row).group(1)

                    hsn = re.search(r'\b\d{6,8}\b', row)
                    hsn = hsn.group() if hsn else ""

                    qty = re.search(r'\b\d+\b$', row)
                    qty = qty.group() if qty else ""

                    desc = row
                    desc = re.sub(r'^\d+\s*', '', desc)
                    desc = desc.replace(hsn, "").replace(qty, "").strip()
                    desc = re.sub(r'\s+', ' ', desc)

                    all_data.append(pd.DataFrame([{
                        'Sl.No': slno,
                        'Description': desc,
                        'HSN': hsn,
                        'Qty': qty
                    }]))

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


# =========================================================
# PROCESS PDFs
# =========================================================
def process_pdfs(uploaded_files):

    final_output = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, uploaded_file in enumerate(uploaded_files):

        status_text.text(f"Processing: {uploaded_file.name}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            pdf_path = tmp.name

        try:
            header = extract_header_data(pdf_path, uploaded_file.name)
            table = extract_table_data(pdf_path)

            if table.empty:
                table = pd.DataFrame([{}])

            for key, value in header.items():
                table[key] = value

            final_output.append(table)

        except Exception as e:
            st.error(f"Error in {uploaded_file.name}: {e}")

        progress_bar.progress((idx + 1) / len(uploaded_files))

    status_text.text("✅ Processing Complete")

    return final_output


# =========================================================
# SAVE OUTPUT
# =========================================================
def generate_excel(final_output):

    df = pd.concat(final_output, ignore_index=True)

    cols = [
        'File Name',
        'Invoice Num',
        'Invoice Date',
        'PO Number',
        'Shipped From',
        'Ship From Pincode',
        'Shipped To',
        'Ship To Pincode',
        'Billed From',
        'Bill From Pincode',
        'Billed To',
        'Bill To Pincode',
        'Sl.No',
        'Description',
        'HSN',
        'Qty'
    ]

    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extracted_Data')

    output.seek(0)

    return output, df


# =========================================================
# FILE UPLOADER
# =========================================================
uploaded_files = st.file_uploader(
    "📂 Upload PDF Files",
    type=["pdf"],
    accept_multiple_files=True
)

# =========================================================
# PROCESS BUTTON
# =========================================================
if uploaded_files:

    st.success(f"✅ {len(uploaded_files)} PDF files uploaded")

    if st.button("🚀 Extract Data"):

        final_output = process_pdfs(uploaded_files)

        if final_output:

            excel_file, preview_df = generate_excel(final_output)

            st.markdown("""
            <div class="success-box">
            ✅ Extraction Completed Successfully
            </div>
            """, unsafe_allow_html=True)

            # =========================================================
            # PREVIEW
            # =========================================================
            st.subheader("📊 Extracted Data Preview")

            st.dataframe(
                preview_df,
                use_container_width=True,
                height=500
            )

            # =========================================================
            # DOWNLOAD BUTTON
            # =========================================================
            st.download_button(
                label="📥 Download Excel File",
                data=excel_file,
                file_name="SAP_DC_EXTRACTION.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("📌 Upload one or more PDF files to begin extraction")


# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.caption("Developed using Streamlit 🚀")
