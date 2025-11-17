import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO

# Optional: ReportLab untuk PDF
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    _RPT_OK = True
    _RPT_ERR = None
except Exception as e:
    _RPT_OK = False
    _RPT_ERR = e

# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

if not _RPT_OK:
    st.warning(
        "Fitur Download PDF membutuhkan paket 'reportlab'. "
        "Tambahkan ke requirements.txt: reportlab. "
        f"Detail error: {str(_RPT_ERR)}"
    )

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

# === Helper formatting ===
def fmt_tgl(v):
    try:
        return pd.to_datetime(v).strftime("%d-%m-%Y")
    except Exception:
        return v

def rupiah(v, empty_zero=False):
    try:
        n = float(v)
        if empty_zero and abs(n) < 1e-9:
            return ""
        # Format ribuan pakai titik (Indonesia)
        return ("Rp {:,.0f}").format(n).replace(",", ".")
    except Exception:
        return v

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
                totals[col] = pd.to_numeric(df_disp[col], errors="coerce").fillna(0).sum()
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

# === Helper saldo berjalan (dipakai UI dan PDF) ===
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

# === Helper PDF ===
def _pdf_make_table(data, col_widths):
    """Buat Table ReportLab dengan style bawaan."""
    tbl = Table(data, colWidths=[w * cm for w in col_widths])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),

        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),  # kolom angka rata kanan
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),

        # Baris TOTAL (jika ada) diberi background sedikit berbeda
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F5F7FA")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    return tbl

def build_pdf_jurnal(df: pd.DataFrame, org_name: str = "BUMDes") -> BytesIO:
    """Bangun PDF Jurnal Umum dari DataFrame."""
    if not _RPT_OK:
        return None

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.2*cm
    )
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f"<b>Jurnal Umum - {org_name}</b>", styles["Title"])
    subtitle = Paragraph(datetime.now().strftime("Dicetak: %d-%m-%Y %H:%M"), styles["Normal"])
    story += [title, subtitle, Spacer(1, 0.4*cm)]

    dfx = df.copy()
    if dfx.empty:
        story.append(Paragraph("Tidak ada data.", styles["Normal"]))
        doc.build(story)
        buf.seek(0)
        return buf

    # Siapkan data tabel
    # Header
    data = [["Tanggal", "Keterangan", "Debit", "Kredit"]]
    # Body
    for _, r in dfx.iterrows():
        data.append([
            fmt_tgl(r.get("Tanggal", "")),
            str(r.get("Keterangan", "")),
            rupiah(r.get("Debit", 0.0), empty_zero=True),
            rupiah(r.get("Kredit", 0.0), empty_zero=True),
        ])
    # Baris total
    total_debit = pd.to_numeric(dfx.get("Debit", pd.Series()), errors="coerce").fillna(0).sum()
    total_kredit = pd.to_numeric(dfx.get("Kredit", pd.Series()), errors="coerce").fillna(0).sum()
    data.append(["", "TOTAL", rupiah(total_debit), rupiah(total_kredit)])

    # Lebar kolom (dalam cm) agar muat di A4 landscape
    col_widths = [3.2, 12.0, 5.0, 5.0]
    tbl = _pdf_make_table(data, col_widths)
    # Keterangan kolom dirata kiri
    tbl.setStyle(TableStyle([("ALIGN", (1, 1), (1, -2), "LEFT")]))

    story.append(tbl)
    doc.build(story)
    buf.seek(0)
    return buf

def build_pdf_buku_besar_per_akun(akun: str, df: pd.DataFrame, org_name: str = "BUMDes") -> BytesIO:
    """Bangun PDF Buku Besar untuk satu akun."""
    if not _RPT_OK:
        return None

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=
