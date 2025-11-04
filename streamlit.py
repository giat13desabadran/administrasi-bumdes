import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="Administrasi BUMDes", layout="wide")

# ============ SIDEBAR NAVIGASI ============ #
with st.sidebar:
    selected = option_menu(
        "📘 Administrasi BUMDes",
        ["🧾 Jurnal Umum", "📚 Buku Besar"],
        icons=["journal-text", "book"],
        menu_icon="building",
        default_index=0,
        styles={
            "container": {"padding": "5px", "background-color": "#f0f2f6"},
            "icon": {"color": "#2b7a78", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"2px"},
            "nav-link-selected": {"background-color": "#def2f1"},
        },
    )

# ============ DATA AWAL ============ #
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Ref": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

def format_rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

# ============ JURNAL UMUM ============ #
if selected == "🧾 Jurnal Umum":
    st.header("🧾 Jurnal Umum (Editable Table)")
    st.caption("💡 Setelah mengetik, tekan Enter atau klik di luar sel agar tersimpan.")

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
    st.session_state.data = edited_df.copy()

    if "Keterangan" in edited_df.columns:
        if edited_df["Keterangan"].replace("", pd.NA).notna().any():
            df_clean = edited_df[edited_df["Keterangan"] != ""]
        else:
            df_clean = pd.DataFrame(columns=edited_df.columns)
    else:
        df_clean = pd.DataFrame(columns=edited_df.columns)

    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()

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

# ============ BUKU BESAR ============ #
elif selected == "📚 Buku Besar":
    st.header("📚 Buku Besar")
    st.info("Halaman ini akan menampilkan rekap akun berdasarkan jurnal.")
