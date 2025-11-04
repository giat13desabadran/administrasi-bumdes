import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="Jurnal & Buku Besar BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi Sederhana BUMDes - Januari 2025")

# State untuk simpan data
if "data" not in st.session_state:
    st.session_state.data = []

# Tabs utama
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# ============ TAB 1: JURNAL UMUM ============
with tab1:
    st.header("🧾 Jurnal Umum")

    with st.form("input_form"):
        tanggal = st.date_input("Tanggal")
        keterangan = st.text_input("Keterangan")
        ref = st.text_input("Ref (misal: 101 untuk Kas)")
        debit = st.number_input("Debit (Rp)", min_value=0, step=1000)
        kredit = st.number_input("Kredit (Rp)", min_value=0, step=1000)
        submitted = st.form_submit_button("Tambah Data")

        if submitted:
            st.session_state.data.append({
                "Tanggal": tanggal,
                "Keterangan": keterangan,
                "Ref": ref,
                "Debit (Rp)": debit,
                "Kredit (Rp)": kredit
            })
            st.success("✅ Data berhasil ditambahkan!")

    if st.session_state.data:
        df = pd.DataFrame(st.session_state.data)
        st.dataframe(df, use_container_width=True)

        total_debit = df["Debit (Rp)"].sum()
        total_kredit = df["Kredit (Rp)"].sum()
        st.write(f"**Total Debit:** Rp {total_debit:,.0f}")
        st.write(f"**Total Kredit:** Rp {total_kredit:,.0f}")

        if st.button("📄 Download PDF Jurnal Umum"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(200, 10, "Jurnal Umum BUMDes - Januari 2025", ln=True, align="C")
            pdf.ln(10)

            headers = ["Tanggal", "Keterangan", "Ref", "Debit (Rp)", "Kredit (Rp)"]
            widths = [25, 70, 20, 35, 35]

            pdf.set_font("Arial", "B", 10)
            for h, w in zip(headers, widths):
                pdf.cell(w, 10, h, 1, 0, "C")
            pdf.ln()

            pdf.set_font("Arial", "", 9)
            for _, row in df.iterrows():
                pdf.cell(25, 10, str(row["Tanggal"]), 1)
                pdf.cell(70, 10, str(row["Keterangan"]), 1)
                pdf.cell(20, 10, str(row["Ref"]), 1)
                pdf.cell(35, 10, f"{int(row['Debit (Rp)']):,}", 1, 0, "R")
                pdf.cell(35, 10, f"{int(row['Kredit (Rp)']):,}", 1, 0, "R")
                pdf.ln()

            pdf.cell(115, 10, "Jumlah", 1)
            pdf.cell(35, 10, f"{int(total_debit):,}", 1, 0, "R")
            pdf.cell(35, 10, f"{int(total_kredit):,}", 1, 0, "R")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(temp_file.name)

            with open(temp_file.name, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Jurnal Umum",
                    data=f,
                    file_name="Jurnal_BUMDes_Januari2025.pdf",
                    mime="application/pdf"
                )

# ============ TAB 2: BUKU BESAR ============
with tab2:
    st.header("📚 Buku Besar")

    if st.session_state.data:
        df = pd.DataFrame(st.session_state.data)

        grouped = df.groupby("Ref")
        for ref, group in grouped:
            st.subheader(f"Nama Akun (Ref): {ref}")
            st.dataframe(group, use_container_width=True)

            total_debit = group["Debit (Rp)"].sum()
            total_kredit = group["Kredit (Rp)"].sum()

            saldo = total_debit - total_kredit
            saldo_text = f"Saldo Akhir: Rp {saldo:,.0f}"
            if saldo >= 0:
                st.success(saldo_text)
            else:
                st.error(saldo_text)

        # Download PDF Buku Besar
        if st.button("📘 Download PDF Buku Besar"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(200, 10, "Buku Besar BUMDes - Januari 2025", ln=True, align="C")
            pdf.ln(10)

            for ref, group in grouped:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"Akun No: {ref}", ln=True)
                pdf.set_font("Arial", "B", 10)
                headers = ["Tanggal", "Keterangan", "Ref", "Debit (Rp)", "Kredit (Rp)"]
                widths = [25, 70, 20, 35, 35]
                for h, w in zip(headers, widths):
                    pdf.cell(w, 8, h, 1, 0, "C")
                pdf.ln()

                pdf.set_font("Arial", "", 9)
                for _, row in group.iterrows():
                    pdf.cell(25, 8, str(row["Tanggal"]), 1)
                    pdf.cell(70, 8, str(row["Keterangan"]), 1)
                    pdf.cell(20, 8, str(row["Ref"]), 1)
                    pdf.cell(35, 8, f"{int(row['Debit (Rp)']):,}", 1, 0, "R")
                    pdf.cell(35, 8, f"{int(row['Kredit (Rp)']):,}", 1, 0, "R")
                    pdf.ln()

                total_debit = group["Debit (Rp)"].sum()
                total_kredit = group["Kredit (Rp)"].sum()
                saldo = total_debit - total_kredit
                pdf.set_font("Arial", "B", 10)
                pdf.cell(115, 8, "Saldo", 1)
                pdf.cell(35, 8, f"{int(total_debit):,}", 1, 0, "R")
                pdf.cell(35, 8, f"{int(total_kredit):,}", 1, 0, "R")
                pdf.ln(12)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(temp_file.name)

            with open(temp_file.name, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Buku Besar",
                    data=f,
                    file_name="Buku_Besar_BUMDes_Januari2025.pdf",
                    mime="application/pdf"
                )
    else:
        st.info("Masukkan data terlebih dahulu di tab **Jurnal Umum**.")
