import streamlit as st
import pandas as pd
from datetime import date
import json, os  # Persistensi

# === Persistensi: Konfigurasi & fungsi simpan/muat ===
DATA_FILE = "data_bumdes.json"
AKUN_COLS = ["Tanggal", "Keterangan", "Debit", "Kredit"]

def save_data():
    """
    Simpan Jurnal dan Buku Besar ke file JSON.
    Panggil setiap selesai mengubah data.
    """
    data = {
        "jurnal": st.session_state.get("jurnal", pd.DataFrame(columns=AKUN_COLS)).to_dict(orient="records"),
        "accounts": {
            k: df.to_dict(orient="records")
            for k, df in st.session_state.get("accounts", {}).items()
        }
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)  # default=str agar tipe tanggal aman

def load_data() -> bool:
    """
    Muat data dari file JSON ke st.session_state.
    Return True jika file ada & berhasil dimuat, else False.
    """
    if not os.path.exists(DATA_FILE):
        return False

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Muat Jurnal
    j = pd.DataFrame(raw.get("jurnal", []))
    for c in AKUN_COLS:
        if c not in j.columns:
            j[c] = []
    if not j.empty and "Tanggal" in j.columns:
        j["Tanggal"] = pd.to_datetime(j["Tanggal"], errors="coerce").dt.date
    st.session_state.jurnal = j[AKUN_COLS]

    # Muat Buku Besar
    st.session_state.accounts = {}
    for nama, recs in raw.get("accounts", {}).items():
        df = pd.DataFrame(recs)
        for c in AKUN_COLS:
            if c not in df.columns:
                df[c] = []
        if not df.empty and "Tanggal" in df.columns:
            df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors="coerce").dt.date
        st.session_state.accounts[nama] = df[AKUN_COLS]
    return True


# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Inisialisasi dari file (sekali saat app pertama jalan) ===
if "initialized" not in st.session_state:
    loaded = load_data()
    if not loaded:
        st.session_state.jurnal = pd.DataFrame(columns=AKUN_COLS)
        st.session_state.accounts = {
            "Kas": pd.DataFrame(columns=AKUN_COLS),
            "Peralatan": pd.DataFrame(columns=AKUN_COLS),
            "Perlengkapan": pd.DataFrame(columns=AKUN_COLS),
            "Modal": pd.DataFrame(columns=AKUN_COLS),
            "Pendapatan": pd.DataFrame(columns=AKUN_COLS),
            "Beban sewa": pd.DataFrame(columns=AKUN_COLS),
            "Beban BBM": pd.DataFrame(columns=AKUN_COLS),
            "Beban gaji": pd.DataFrame(columns=AKUN_COLS),
            "Beban listrik": pd.DataFrame(columns=AKUN_COLS),
            "Beban perawatan": pd.DataFrame(columns=AKUN_COLS),
            "Beban prive": pd.DataFrame(columns=AKUN_COLS),
        }
    st.session_state.initialized = True

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
    df_disp = df.copy()

    # Penomoran index tampil (1..n)
    df_disp.index = range(1, len(df_disp) + 1)

    # Tambah baris TOTAL (hanya untuk tampilan)
    if add_total and not df_disp.empty:
        total_row = {}
        for c in df_disp.columns:
            if c == "Keterangan":
                total_row[c] = "TOTAL"
            elif c in ["Debit", "Kredit", "Saldo Debit", "Saldo Kredit"]:
                total_row[c] = df_disp[c].sum()
            else:
                total_row[c] = None
        df_disp.loc[len(df_disp) + 1] = total_row

    # Format style
    fmt = {}
    if "Tanggal" in df_disp.columns:
        fmt["Tanggal"] = fmt_tgl
    for col in ["Debit", "Kredit", "Saldo Debit", "Saldo Kredit"]:
        if col in df_disp.columns:
            fmt[col] = lambda x: f"Rp {x:,.0f}" if pd.notnull(x) else ""

    return df_disp.style.format(fmt).set_properties(**{"text-align": "center"})

# === Helper form tambah transaksi (seragam) ===
def form_transaksi(form_key: str, akun_options=None):
    """
    Render form tambah transaksi dengan desain seragam.
    - akun_options None => tanpa dropdown akun (untuk Jurnal Umum)
    """
    with st.form(form_key):
        c1, c2, c3 = st.columns([2, 2, 1])

        with c1:
            tgl = st.date_input("Tanggal", value=date.today(), key=f"{form_key}_tgl")
            ket = st.text_input("Keterangan", placeholder="Deskripsi transaksi", key=f"{form_key}_ket")

        with c2:
            akun_val = None
            if akun_options is not None and len(akun_options) > 0:
                akun_val = st.selectbox("Pilih Akun", akun_options, key=f"{form_key}_akun")
            tipe = st.radio("Tipe", ["Debit", "Kredit"], horizontal=True, key=f"{form_key}_tipe")

        with c3:
            jumlah = st.number_input(
                "Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f", key=f"{form_key}_jml"
            )
            submitted = st.form_submit_button("Tambah Transaksi")

    return {"submitted": submitted, "tgl": tgl, "ket": ket, "tipe": tipe, "jumlah": jumlah, "akun": akun_val}

# === Tabs utama ===
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# =========================
#         JURNAL UMUM
# =========================
with tab1:
    st.header("🧾 Jurnal Umum")
    st.subheader("Input Transaksi Baru")

    # Migrasi struktur DataFrame jurnal (jaga konsistensi kolom)
    jurnal_cols = AKUN_COLS
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
            save_data()  # simpan setelah tambah
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
                save_data()  # simpan setelah hapus
                st.success(f"Baris {int(del_idx)} berhasil dihapus!")
                st.rerun()
        with cdel3:
            if st.button("Hapus Semua"):
                st.session_state.jurnal = st.session_state.jurnal.iloc[0:0].copy()
                save_data()  # simpan setelah hapus semua
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

    # Inisialisasi/migrasi akun (drop 'Ref' jika ada)
    if "accounts" not in st.session_state:
        st.session_state.accounts = {}
    for k, df in list(st.session_state.accounts.items()):
        if "Ref" in df.columns:
            st.session_state.accounts[k] = df.drop(columns=["Ref"])
        for c in AKUN_COLS:
            if c not in st.session_state.accounts[k].columns:
                st.session_state.accounts[k][c] = []
        st.session_state.accounts[k] = st.session_state.accounts[k][AKUN_COLS]

    # Kelola Akun (opsional: tambah/ubah/hapus akun)
    with st.expander("⚙️ Kelola Akun Buku Besar"):
        def _sanitize_name(n: str) -> str:
            return " ".join((n or "").split()).strip()

        c1, c2 = st.columns([3, 1])
        with c1:
            akun_baru = st.text_input("Nama akun baru", placeholder="contoh: Piutang Usaha", key="akun_baru")
        with c2:
            if st.button("Tambah Akun"):
                nama = _sanitize_name(akun_baru)
                if not nama:
                    st.warning("Nama akun tidak boleh kosong.")
                elif any(nama.lower() == k.lower() for k in st.session_state.accounts.keys()):
                   
