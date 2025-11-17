import streamlit as st
import pandas as pd
from datetime import date
import calendar
import tempfile

# PDF (fpdf2)
try:
    from fpdf import FPDF  # pip install fpdf2
    FPDF_AVAILABLE = True
except Exception:
    FPDF_AVAILABLE = False

# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Styling (opsional) ===
st.markdown("""
<style>
.ag-theme-streamlit {
    --ag-background-color: #F9FAFB;
    --ag-odd-row-background-color: #FFFFFF;
    --ag-header-background-color: #E9ECEF;
    --ag-border-color: #DDDDDD;
    --ag-header-foreground-color: #000000;
    --ag-font-family: "Inter", system-ui, sans-serif;
    --ag-font-size: 14px;
    --ag-row-hover-color: #EEF6ED;
    --ag-selected-row-background-color: #DDF0DC;
    --ag-cell-horizontal-padding: 10px;
    --ag-cell-vertical-padding: 6px;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# === Nama bulan Indonesia ===
MONTH_NAMES_ID = [
    None, "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

# === Helper formatting ===
def fmt_tgl(v):
    try:
        return pd.to_datetime(v).strftime("%d-%m-%Y")
    except Exception:
        return v

def format_rupiah(x):
    try:
        if x < 0:
            return f"({abs(x):,.0f})".replace(",", ".")
        return f"{x:,.0f}".replace(",", ".")
    except Exception:
        return x

def style_table(df: pd.DataFrame, add_total: bool = True):
    # Salinan untuk tampilan
    df_disp = df.copy()

    # Penomoran baris mulai 1
    df_disp.index = range(1, len(df_disp) + 1)

    # Tambahkan baris TOTAL (untuk Debit & Kredit)
    if add_total and not df_disp.empty:
        totals = {}
        for col in ["Debit", "Kredit"]:
            if col in df_disp.columns:
                totals[col] = pd.to_numeric(df_disp[col], errors="coerce").fillna(0.0).sum()
        total_row = {c: "" for c in df_disp.columns}
        if "Keterangan" in total_row:
            total_row["Keterangan"] = "TOTAL"
        total_row.update(totals)
        df_disp = pd.concat([df_disp, pd.DataFrame([total_row])], ignore_index=False)

    # Peta format
    format_map = {}
    if "Tanggal" in df_disp.columns:
        format_map["Tanggal"] = fmt_tgl
    for col in ["Debit", "Kredit", "Saldo Debit", "Saldo Kredit"]:
        if col in df_disp.columns:
            format_map[col] = "Rp {:,.0f}".format

    return df_disp.style.format(format_map).set_properties(**{"text-align": "center"})

# === Helper form tambah transaksi (seragam) ===
def form_transaksi(form_key: str, akun_options=None):
    """
    Render form tambah transaksi dengan desain seragam.
    - form_key: key unik untuk hindari bentrok widget
    - akun_options: list akun; jika None, dropdown akun disembunyikan (untuk Jurnal Umum)
    Return: dict {submitted, tgl, ket, tipe, jumlah, akun (opsional)}
    """
    with st.form(form_key):
        c1, c2, c3 = st.columns([2, 2, 1])

        with c1:
            tgl = st.date_input("Tanggal", value=date.today(), key=f"{form_key}_tgl")
            ket = st.text_input("Keterangan", placeholder="Deskripsi transaksi", key=f"{form_key}_ket")

        with c2:
            akun_val = None
            if akun_options is not None:
                akun_val = st.selectbox("Pilih Akun", akun_options, key=f"{form_key}_akun")
            tipe = st.radio("Tipe", ["Debit", "Kredit"], horizontal=True, key=f"{form_key}_tipe")

        with c3:
            jumlah = st.number_input(
                "Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f", key=f"{form_key}_jml"
            )
            submitted = st.form_submit_button("Tambah Transaksi")

    return {
        "submitted": submitted,
        "tgl": tgl,
        "ket": ket,
        "tipe": tipe,
        "jumlah": jumlah,
        "akun": akun_val,
    }

# === Periode helper ===
def pilih_periode(prefix: str):
    c1, c2 = st.columns(2)
    with c1:
        tahun = st.number_input(
            "Tahun",
            min_value=2000, max_value=2100,
            value=date.today().year, step=1,
            key=f"{prefix}_tahun"
        )
    with c2:
        bulan = st.selectbox(
            "Bulan",
            options=list(range(1, 13)),
            index=date.today().month - 1,
            format_func=lambda m: MONTH_NAMES_ID[m],
            key=f"{prefix}_bulan"
        )
    start = date(int(tahun), int(bulan), 1)
    end = date(int(tahun), int(bulan), calendar.monthrange(int(tahun), int(bulan))[1])
    period_text = f"{MONTH_NAMES_ID[bulan]} {tahun}"
    return start, end, period_text, int(tahun), int(bulan)

def filter_periode(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    dfx = df.copy()
    dfx["Tanggal"] = pd.to_datetime(dfx["Tanggal"], errors="coerce").dt.date
    mask = (dfx["Tanggal"] >= start) & (dfx["Tanggal"] <= end)
    return dfx.loc[mask].copy()

# === Hitung saldo berjalan (all-time) ===
def hitung_saldo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tambahkan kolom Saldo (Debit - Kredit) dan Saldo Berjalan (cumsum).
    """
    if df.empty or not {"Debit", "Kredit"}.issubset(df.columns):
        return df.copy()
    dfx = df.copy()
    dfx["Debit"] = pd.to_numeric(dfx["Debit"], errors="coerce").fillna(0.0)
    dfx["Kredit"] = pd.to_numeric(dfx["Kredit"], errors="coerce").fillna(0.0)
    dfx["Saldo"] = dfx["Debit"] - dfx["Kredit"]
    dfx["Saldo Berjalan"] = dfx["Saldo"].cumsum()
    return dfx

# === Fungsi PDF (adaptasi dari kode teman) ===
def buat_pdf(df: pd.DataFrame, judul: str = "Jurnal Umum BUMDes", periode: str = "") -> bytes:
    """
    Generate PDF dari DataFrame dengan header judul dan periode.
    Return: bytes siap diumpankan ke st.download_button
    """
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 belum terpasang. Install dengan: pip install fpdf2")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 10, txt=judul, ln=True, align="C")
    if periode:
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, txt=f"Periode: {periode}", ln=True, align="C")
    pdf.ln(5)

    # Tabel header
    cols = list(df.columns)
    page_width = 190  # lebar efektif A4 (210 - 2*10 margin)
    col_width = page_width / max(len(cols), 1)

    pdf.set_font("Arial", size=11)
    for col in cols:
        pdf.cell(col_width, 9, str(col), border=1, align="C")
    pdf.ln()

    # Tabel isi
    pdf.set_font("Arial", size=10)
    for _, row in df.iterrows():
        for col in cols:
            pdf.cell(col_width, 8, str(row[col]), border=1, align="C")
        pdf.ln()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        return tmp.read()

# =========================
# Halaman: Jurnal Umum
# =========================
st.header("🧾 Jurnal Umum")

# 1) Inisialisasi storage session (perbaikan KeyError)
if "df_jurnal" not in st.session_state:
    st.session_state["df_jurnal"] = pd.DataFrame(
        columns=["Tanggal", "Keterangan", "Debit", "Kredit"]
    )

# 2) Form tambah transaksi
with st.expander("Tambah Transaksi"):
    res = form_transaksi("form_jurnal", akun_options=None)
    if res["submitted"]:
        if not res["ket"]:
            st.warning("Keterangan wajib diisi.")
        else:
            debit = float(res["jumlah"]) if res["tipe"] == "Debit" else 0.0
            kredit = float(res["jumlah"]) if res["tipe"] == "Kredit" else 0.0
            new_row = pd.DataFrame([{
                "Tanggal": pd.to_datetime(res["tgl"]).date(),
                "Keterangan": res["ket"],
                "Debit": debit,
                "Kredit": kredit
            }])
            st.session_state["df_jurnal"] = pd.concat(
                [st.session_state["df_jurnal"], new_row], ignore_index=True
            )
            st.success("Transaksi ditambahkan.")

# 3) Pilih periode (bulan-tahun)
start, end, periode_text, tahun, bulan = pilih_periode("jurnal")

# 4) Filter data sesuai periode & urutkan tanggal
df_show = filter_periode(st.session_state["df_jurnal"], start, end)
if not df_show.empty:
    df_show = df_show.sort_values(by="Tanggal")

# 5) Tabel tampilan dengan total
st.subheader(f"Daftar Transaksi - {periode_text}")
st.dataframe(style_table(df_show), use_container_width=True)

# 6) Tombol unduh: CSV & PDF
c1, c2 = st.columns(2)

with c1:
    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"jurnal_umum_{tahun}_{bulan:02d}.csv",
        mime="text/csv",
        use_container_width=True
    )

with c2:
    if not df_show.empty:
        if FPDF_AVAILABLE:
            # Siapkan DataFrame untuk PDF: format tanggal & rupiah
            df_pdf = df_show.copy()
            df_pdf["Tanggal"] = df_pdf["Tanggal"].apply(fmt_tgl)
            df_pdf["Debit"] = pd.to_numeric(df_pdf["Debit"], errors="coerce").fillna(0).map(
                lambda x: f"Rp {x:,.0f}".replace(",", ".")
            )
            df_pdf["Kredit"] = pd.to_numeric(df_pdf["Kredit"], errors="coerce").fillna(0).map(
                lambda x: f"Rp {x:,.0f}".replace(",", ".")
            )

            try:
                pdf_bytes = buat_pdf(df_pdf, judul="Jurnal Umum BUMDes", periode=periode_text)
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"jurnal_umum_{tahun}_{bulan:02d}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Gagal membuat PDF: {e}")
        else:
            st.info("Fitur PDF membutuhkan fpdf2. Install: pip install fpdf2")
    else:
        st.info("Tidak ada data pada periode ini.")
