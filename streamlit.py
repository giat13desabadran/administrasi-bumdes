import streamlit as st
import pandas as pd
from datetime import date
import calendar

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
    if df.empty:
        return df.copy()
    dfx = df.copy()
    dfx["Tanggal"] = pd.to_datetime(dfx["Tanggal"], errors='coerce')
    for c in ["Debit", "Kredit"]:
        dfx[c] = pd.to_numeric(dfx[c], errors="coerce").fillna(0.0)

    # Urutkan tanggal stabil
    dfx = dfx.sort_values(["Tanggal"], kind="mergesort").reset_index(drop=True)

    # Running balance (Debit - Kredit)
    running = 0.0
    saldo_debit = []
    saldo_kredit = []
    for _, r in dfx.iterrows():
        running += float(r["Debit"]) - float(r["Kredit"])
        if running >= 0:
            saldo_debit.append(running)
            saldo_kredit.append(0.0)
        else:
            saldo_debit.append(0.0)
            saldo_kredit.append(abs(running))

    dfx["Saldo Debit"] = saldo_debit
    dfx["Saldo Kredit"] = saldo_kredit
    dfx["Tanggal"] = dfx["Tanggal"].dt.date
    return dfx

# === Ledger per periode + Saldo Awal ===
def ledger_periode_with_opening(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    # Ledger periode + baris "Saldo Awal" dan saldo berjalan
    if df.empty:
        return pd.DataFrame([{
            "Tanggal": start, "Keterangan": "Saldo Awal",
            "Debit": 0.0, "Kredit": 0.0, "Saldo Debit": 0.0, "Saldo Kredit": 0.0
        }])

    dfx = df.copy()
    dfx["Tanggal"] = pd.to_datetime(dfx["Tanggal"], errors="coerce")
    for c in ["Debit", "Kredit"]:
        dfx[c] = pd.to_numeric(dfx[c], errors="coerce").fillna(0.0)

    opening = dfx.loc[dfx["Tanggal"] < pd.to_datetime(start), "Debit"].sum() - \
              dfx.loc[dfx["Tanggal"] <
