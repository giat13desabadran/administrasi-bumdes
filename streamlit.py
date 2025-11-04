import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, ColumnsAutoSizeMode

st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Inisialisasi data awal ===
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Ref": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

# === Fungsi format rupiah (untuk tampilan tabel di bawah & PDF) ===
def format_rupiah(x):
    try:
        return f"Rp {x:,.0f}".replace(",", ".")
    except Exception:
        return x

# === CSS tampilan grid (tema alpine, terang, card-like) ===
st.markdown("""
<style>
.ag-theme-alpine {
  --ag-background-color: #ffffff !important;
  --ag-odd-row-background-color: #fbfbfd !important;
  --ag-header-background-color: #f6f7fb !important;
  --ag-border-color: #e5e7eb !important;
  --ag-row-hover-color: #eef4ff !important;
  --ag-selected-row-background-color: #e6f0ff !important;
  --ag-font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  --ag-font-size: 13px !important;
}
.ag-theme-alpine .ag-root-wrapper {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 6px 16px rgba(0,0,0,0.06);
}
.ag-theme-alpine .ag-header-cell-label { font-weight: 600; color: #111827; }
.ag-theme-alpine .ag-cell { padding: 8px 12px; }
.ag-theme-alpine .ag-floating-bottom .ag-cell,
.ag-theme-alpine .ag-pinned-bottom .ag-cell {
  font-weight: 700;
  background: #fafafa;
  border-top: 2px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

# === Tabs ===
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

with tab1:
    st.header("🧾 Jurnal Umum")
    st.info("💡 Tekan Enter sekali untuk menyimpan perubahan otomatis, seperti di tabel Streamlit.")

    # Hitung total saat ini (untuk pinned bottom)
    df_now = st.session_state.data.copy()
    df_clean_now = df_now[df_now["Keterangan"].astype(str).strip() != ""]
    total_debit_now = int(df_clean_now["Debit (Rp)"].sum()) if not df_clean_now.empty else 0
    total_kredit_now = int(df_clean_now["Kredit (Rp)"].sum()) if not df_clean_now.empty else 0

    # === Setup Grid AgGrid (tema alpine) ===
    gb = GridOptionsBuilder.from_dataframe(st.session_state.data)
    gb.configure_default_column(
        editable=True, resizable=True, sortable=True, filter=True,
        floatingFilter=True, wrapText=True, autoHeight=True
    )
    gb.configure_grid_options(
        rowHeight=36, headerHeight=40, animateRows=True,
        stopEditingWhenCellsLoseFocus=False, suppressScrollOnNewData=True,
        pinnedBottomRowData=[{
            "Tanggal": "", "Keterangan": "TOTAL", "Ref": "",
            "Debit (Rp)": total_debit_now, "Kredit (Rp)": total_kredit_now
        }]
    )

    # Tipe & formatter kolom
    gb.configure_column("Tanggal", header_name="Tanggal (YYYY-MM-DD)",
                        type=["dateColumnFilter","customDateTimeFormat"], custom_format_string="yyyy-MM-dd")
    gb.configure_column("Ref", header_name="Ref (contoh: 101)", type=["numericColumn"])
    rupiahFmt = "(params.value==null || params.value==='') ? '' : 'Rp ' + Intl.NumberFormat('id-ID').format(params.value)"
    gb.configure_column("Debit (Rp)", type=["numericColumn","rightAligned"], valueFormatter=rupiahFmt)
    gb.configure_column("Kredit (Rp)", type=["numericColumn","rightAligned"], valueFormatter=rupiahFmt)

    grid_response = AgGrid(
        st.session_state.data,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="alpine",            # ← pakai tema alpine agar tidak abu-abu gelap
        height=420,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        key="aggrid_table"
    )

    # === Sinkronisasi otomatis ===
    new_df = pd.DataFrame(grid_response["data"])
    if not new_df.equals(st.session_state.data):
        st.session_state.data = new_df.copy()
        st.toast("💾 Perubahan tersimpan otomatis!", icon="💾")

    # === Bersihkan data kosong + total + tampilan hasil + PDF ===
    df_clean = new_df[new_df["Keterangan"].astype(str).str.strip() != ""]

    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()
        total_row = pd.DataFrame({
            "Tanggal": [""], "Keterangan": ["TOTAL"], "Ref": [""],
            "Debit (Rp)": [total_debit], "Kredit (Rp)": [total_kredit],
        })
        df_final = pd.concat([df_clean, total_row], ignore_index=True)

        st.write("### 📊 Hasil Jurnal")
        df_final_display = df_final.copy()
        df_final_display.index = range(1, len(df_final_display) + 1)
        df_final_display.index.name = "No"

        st.dataframe(df_final_display.style.format({
            "Debit (Rp)": format_rupiah,
            "Kredit (Rp)": format_rupiah
        }), use_container_width=True)

        # === PDF ===
        def buat_pdf(df):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Jurnal Umum BUMDes", ln=True, align="C")
            pdf.ln(8)

            col_width = 190 / len(df.columns)
            for col in df.columns:
                pdf.cell(col_width, 10, col, border=1, align="C")
            pdf.ln()

            pdf.set_font("Arial", size=10)
            for _, row in df.iterrows():
                for item in row:
                    pdf.cell(col_width, 8, str(item), border=1, align="C")
                pdf.ln()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                return tmp.read()

        pdf_data = buat_pdf(df_final)
        st.download_button(
            "📥 Download PDF",
            data=pdf_data,
            file_name="jurnal_umum.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.warning("Belum ada data valid di tabel.")

with tab2:
    st.header("📚 Buku Besar")
    st.info("Fitur ini sedang dalam pengembangan 🚧")
