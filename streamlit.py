import streamlit as st
import pandas as pd
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import tempfile

st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# Inisialisasi data awal
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Ref": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

def format_rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# ================= TAB 1 =====================
with tab1:
    st.header("🧾 Jurnal Umum")
    st.caption("💡 Langsung ketik di tabel dan tekan Enter — perubahan otomatis tersimpan!")

    # --- Setup AgGrid ---
    gb = GridOptionsBuilder.from_dataframe(st.session_state.data)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_column("Tanggal", header_name="Tanggal (YYYY-MM-DD)", editable=True)
    gb.configure_column("Keterangan", editable=True)
    gb.configure_column("Ref", editable=True)
    gb.configure_column("Debit (Rp)", editable=True, type=["numericColumn"])
    gb.configure_column("Kredit (Rp)", editable=True, type=["numericColumn"])
    gb.configure_grid_options(domLayout='normal')

    grid_options = gb.build()

    grid_response = AgGrid(
        st.session_state.data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        theme="alpine",  # Bisa diganti: "streamlit", "material"
        fit_columns_on_grid_load=True,
        height=300,
    )

    df_ag = grid_response["data"]
    st.session_state.data = pd.DataFrame(df_ag)

    # Hapus baris kosong hanya jika semua kolomnya kosong
    df_clean = st.session_state.data.dropna(how="all")
    df_clean = df_clean[df_clean["Keterangan"] != ""]

    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()

        # Tambah baris total ke bawah tabel
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Ref": [""],
            "Debit (Rp)": [total_debit],
            "Kredit (Rp)": [total_kredit],
        })

        df_final = pd.concat([df_clean, total_row], ignore_index=True)

        st.write("### 💰 Rekapitulasi Jurnal")
        st.dataframe(df_final.style.format({
            "Debit (Rp)": format_rupiah,
            "Kredit (Rp)": format_rupiah
        }))

        # Fungsi PDF
        def buat_pdf(df):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Jurnal Umum BUMDes", ln=True, align="C")
            pdf.ln(8)
            for col in df.columns:
                pdf.cell(38, 10, col, border=1)
            pdf.ln()
            for _, row in df.iterrows():
                for item in row:
                    pdf.cell(38, 10, str(item), border=1)
                pdf.ln()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                pdf_bytes = tmp.read()
            return pdf_bytes

        pdf_data = buat_pdf(df_final)

        st.download_button(
            "📥 Download PDF",
            data=pdf_data,
            file_name="jurnal_umum.pdf",
            mime="application/pdf",
        )

    else:
        st.warning("Belum ada data valid di tabel.")
