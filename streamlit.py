import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# Inisialisasi data awal
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Ref": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

# Fungsi format rupiah
def format_rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# ================= TAB 1 =====================
with tab1:
    st.header("🧾 Jurnal Umum (Editable Table)")
    st.caption("💡 Setelah mengetik, tekan Enter atau klik di luar sel agar tersimpan.")

    # --- Tabel input ---
    edited_df = st.data_editor(
        st.session_state.data,
        num_rows="dynamic",
        use_container_width=True,
        key="editable_table",
        column_config={
            "Tanggal": st.column_config.TextColumn("Tanggal (misal: 2025-01-01)"),
            "Keterangan": st.column_config.TextColumn("Keterangan"),
            "Ref": st.column_config.TextColumn("Ref (contoh: 101)"),
            "Debit (Rp)": st.column_config.NumberColumn("Debit (Rp)", step=1000),
            "Kredit (Rp)": st.column_config.NumberColumn("Kredit (Rp)", step=1000),
        },
    )

    # Simpan hasil edit ke session
    st.session_state.data = edited_df.copy()

    # Hindari hapus baris kosong terlalu cepat
    if "Keterangan" in edited_df.columns:
        if edited_df["Keterangan"].replace("", pd.NA).notna().any():
            df_clean = edited_df[edited_df["Keterangan"] != ""]
        else:
            df_clean = pd.DataFrame(columns=edited_df.columns)
    else:
        df_clean = pd.DataFrame(columns=edited_df.columns)

    # Kalau sudah ada data valid
    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()

        # Tambahkan baris total
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Ref": [""],
            "Debit (Rp)": [total_debit],
            "Kredit (Rp)": [total_kredit],
        })

        df_final = pd.concat([df_clean, total_row], ignore_index=True)

        st.markdown("### 💰 Rekapitulasi")
        st.dataframe(df_final.style.format({
            "Debit (Rp)": format_rupiah,
            "Kredit (Rp)": format_rupiah
        }))

        # --- Download PDF ---
        def buat_pdf(df):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Jurnal Umum BUMDes", ln=True, align="C")
            pdf.ln(8)

            # Header
            for col in df.columns:
                pdf.cell(38, 10, col, border=1)
            pdf.ln()

            # Isi tabel
            for _, row in df.iterrows():
                for item in row:
                    pdf.cell(38, 10, str(item), border=1)
                pdf.ln()

            # Simpan ke file sementara
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
