import streamlit as st
import pandas as pd
from datetime import date

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

# === Helper formatting ===
def fmt_tgl(v):
    try:
        return pd.to_datetime(v).strftime("%d-%m-%Y")
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
                totals[col] = df_disp[col].sum()
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

# === Tabs utama ===
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# =========================
#         JURNAL UMUM
# =========================
with tab1:
    st.header("🧾 Jurnal Umum")
    st.subheader("Input Transaksi Baru")

    # Inisialisasi / migrasi struktur DataFrame jurnal (tanpa Ref)
    jurnal_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]
    if "jurnal" not in st.session_state:
        st.session_state.jurnal = pd.DataFrame(columns=jurnal_cols)
    else:
        if "Ref" in st.session_state.jurnal.columns:
            st.session_state.jurnal = st.session_state.jurnal.drop(columns=["Ref"])
        for c in jurnal_cols:
            if c not in st.session_state.jurnal.columns:
                st.session_state.jurnal[c] = []
        st.session_state.jurnal = st.session_state.jurnal[jurnal_cols]

    # Form transaksi Jurnal (tanpa akun)
    f = form_transaksi("form_input_jurnal", akun_options=None)
    if f["submitted"]:
        if f["ket"].strip() == "":
            st.error("Mohon isi kolom keterangan!")
        elif f["jumlah"] <= 0:
            st.error("Jumlah harus lebih dari nol!")
        else:
            debit = float(f["jumlah"]) if f["tipe"] == "Debit" else 0.0
            kredit = float(f["jumlah"]) if f["tipe"] == "Kredit" else 0.0
            new_row = {
                "Tanggal": f["tgl"],
                "Keterangan": f["ket"].strip(),
                "Debit": debit,
                "Kredit": kredit,
            }
            st.session_state.jurnal = pd.concat(
                [st.session_state.jurnal, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success("Transaksi berhasil ditambahkan ke Jurnal Umum!")

    st.divider()

    # Tabel Jurnal + aksi hapus
    df_jurnal = st.session_state.jurnal.copy()

    if not df_jurnal.empty:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=True), use_container_width=True)

        cdel1, cdel2, cdel3 = st.columns([2, 1, 1])
        with cdel1:
            del_idx = st.number_input(
                "Hapus baris nomor",
                min_value=1,
                max_value=len(df_jurnal),
                step=1,
                value=1,
                help="Pilih nomor baris (bukan baris TOTAL)"
            )
        with cdel2:
            if st.button("Hapus Baris"):
                st.session_state.jurnal = st.session_state.jurnal.drop(
                    st.session_state.jurnal.index[int(del_idx) - 1]
                ).reset_index(drop=True)
                st.success(f"Baris {int(del_idx)} berhasil dihapus!")
                st.rerun()
        with cdel3:
            if st.button("Hapus Semua"):
                st.session_state.jurnal = st.session_state.jurnal.iloc[0:0].copy()
                st.success("Semua baris jurnal berhasil dihapus!")
                st.rerun()
    else:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=False), use_container_width=True)
        st.info("Belum ada data transaksi di Jurnal Umum.")

# =========================
#        BUKU BESAR
# =========================
with tab2:
    st.header("📚 Buku Besar")

    # Inisialisasi akun dan data jika belum ada (tanpa 'Ref')
    akun_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]
    if "accounts" not in st.session_state:
        st.session_state.accounts = {
            "Kas": pd.DataFrame(columns=akun_cols),
            "Peralatan": pd.DataFrame(columns=akun_cols),
            "Perlengkapan": pd.DataFrame(columns=akun_cols),
            "Modal": pd.DataFrame(columns=akun_cols),
            "Pendapatan": pd.DataFrame(columns=akun_cols),
            "Beban sewa": pd.DataFrame(columns=akun_cols),
            "Beban BBM": pd.DataFrame(columns=akun_cols),
            "Beban gaji": pd.DataFrame(columns=akun_cols),
            "Beban listrik": pd.DataFrame(columns=akun_cols),
            "Beban perawatan": pd.DataFrame(columns=akun_cols),
            "Beban prive": pd.DataFrame(columns=akun_cols)
        }
    else:
        for k, df in st.session_state.accounts.items():
            if "Ref" in df.columns:
                st.session_state.accounts[k] = df.drop(columns=["Ref"])
            for c in akun_cols:
                if c not in st.session_state.accounts[k].columns:
                    st.session_state.accounts[k][c] = []
            st.session_state.accounts[k] = st.session_state.accounts[k][akun_cols]

    # Fungsi hitung saldo berjalan
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

    # Form transaksi Buku Besar (desain sama, dengan dropdown Akun)
    st.subheader("Input Transaksi Baru")
    akun_list = list(st.session_state.accounts.keys())
    fbb = form_transaksi("form_input_tb", akun_options=akun_list)

    if fbb["submitted"]:
        if fbb["ket"].strip() == "":
            st.error("Mohon isi kolom keterangan!")
        elif fbb["jumlah"] <= 0:
            st.error("Jumlah harus lebih dari nol!")
        elif not fbb["akun"]:
            st.error("Mohon pilih akun!")
        else:
            debit = float(fbb["jumlah"]) if fbb["tipe"] == "Debit" else 0.0
            kredit = float(fbb["jumlah"]) if fbb["tipe"] == "Kredit" else 0.0
            baris = pd.DataFrame({
                "Tanggal": [fbb["tgl"]],
                "Keterangan": [fbb["ket"].strip()],
                "Debit": [debit],
                "Kredit": [kredit],
            })
            st.session_state.accounts[fbb["akun"]] = pd.concat(
                [st.session_state.accounts[fbb["akun"]], baris], ignore_index=True
            )
            st.success(f"Transaksi berhasil ditambahkan di akun {fbb['akun']}!")

    st.divider()

    # Tampilkan tabel buku besar per akun dengan saldo berjalan, di Tabs
    tabs_akun = st.tabs(akun_list)
    for i, akun in enumerate(akun_list):
        with tabs_akun[i]:
            st.markdown(f"Nama Akun : {akun}  \n")
            df = st.session_state.accounts[akun]
            df_show = hitung_saldo(df) if not df.empty else df.copy()
            st.dataframe(style_table(df_show, add_total=True), use_container_width=True)


