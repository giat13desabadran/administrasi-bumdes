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

# Fungsi styling tabel agar mirip Excel
def style_excel(df):
    styled = df.style.set_table_styles([
        {"selector": "thead th",
         "props": [("background-color", "#b7e1cd"),
                   ("color", "black"),
                   ("border", "1px solid black"),
                   ("text-align", "center"),
                   ("font-weight", "bold")]},
        {"selector": "td",
         "props": [("border", "1px solid black"),
                   ("text-align", "center"),
                   ("padding", "4px")]}
    ]).format(
        {"Debit (Rp)": format_rupiah, "Kredit (Rp)": format_rupiah}
    )
    return styled

tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# ================= TAB 1 =====================
with tab1:
    st.header("🧾 Jurnal Umum (Editable Table)")

    st.info("✏️ Klik langsung di tabel untuk menambah atau mengubah data.")
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
        }
    )

    # Simpan perubahan
    st.session_state.data = edited_df

    # Hapus baris kosong (opsional)
    df_clean = edited_df.dropna(subset=["Keterangan"], how="all")
    df_clean = df_clean[df_clean["Keterangan"] != ""]

    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()
        st.markdown(f"**Total Debit:** {format_rupiah(total_debit)}")
        st.markdown(f"**Total Kredit:** {format_rupiah(total_kredit)}")
    else:
        st.warning("Belum ada data valid di tabel.")

# ================= TAB 2 =====================
with tab2:
    st.header("📚 Buku Besar (Otomatis dari Jurnal Umum)")

    df = st.session_state.data.copy()
    df = df.dropna(subset=["Ref"])
    df = df[df["Ref"] != ""]

    if not df.empty:
        grouped = df.groupby("Ref")
        for ref, group in grouped:
            st.subheader(f"Nama Akun (Ref): {ref}")
            st.write(style_excel(group).to_html(), unsafe_allow_html=True)

            total_debit = group["Debit (Rp)"].sum()
            total_kredit = group["Kredit (Rp)"].sum()
            saldo = total_debit - total_kredit

            col1, col2, col3 = st.columns(3)
            col2.markdown(
                f"<div style='text-align:center; font-weight:bold; background:#e0f7fa; padding:5px; border:1px solid black;'>"
                f"Saldo Akhir: {format_rupiah(saldo)}</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("Isi data terlebih dahulu di tab **Jurnal Umum**.")
