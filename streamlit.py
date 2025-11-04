import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from datetime import date

# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Inisialisasi data awal untuk Jurnal Umum ===
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Ref": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

# === Fungsi format rupiah ===
def format_rupiah(x):
    try:
        return f"Rp {x:,.0f}".replace(",", ".")
    except Exception:
        return x

# === Styling agar mirip Streamlit ===
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

# === Tabs utama ===
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

with tab1:
    st.header("🧾 Jurnal Umum (Input Transaksi)")

    # Inisialisasi DataFrame jurnal di session_state jika belum ada
    if "jurnal" not in st.session_state:
        cols = ["Tanggal", "Keterangan", "Ref", "Debit", "Kredit"]
        st.session_state.jurnal = pd.DataFrame(columns=cols)

    # Form input transaksi
    with st.form("form_input_jurnal"):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            tgl = st.date_input("Tanggal", value=date.today())
            ket = st.text_input("Keterangan", placeholder="Deskripsi transaksi")
        with c2:
            ref = st.text_input("Ref", placeholder="Mis. JU-1")
            tipe = st.radio("Tipe", ["Debit", "Kredit"], horizontal=True)
        with c3:
            jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f")
            submit = st.form_submit_button("Tambah")

    if submit:
        if ket.strip() == "":
            st.error("Mohon isi kolom keterangan!")
        elif jumlah <= 0:
            st.error("Jumlah harus lebih dari nol!")
        else:
            debit = jumlah if tipe == "Debit" else 0.0
            kredit = jumlah if tipe == "Kredit" else 0.0

            new_row = {
                "Tanggal": tgl,
                "Keterangan": ket,
                "Ref": ref,
                "Debit": debit,
                "Kredit": kredit,
            }
            st.session_state.jurnal = pd.concat(
                [st.session_state.jurnal, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success("Transaksi berhasil ditambahkan!")

    st.divider()

    # Tampilkan tabel jurnal dengan total dan opsi hapus baris
    df_jurnal = st.session_state.jurnal.copy()

    # Tombol hapus baris (berbasis index)
    if not df_jurnal.empty:
        st.subheader("Data Jurnal Umum")
        # Reset index no otomatis
        df_jurnal.index = range(1, len(df_jurnal)+1)
        del_idx = st.number_input("Hapus baris nomor", min_value=0, max_value=len(df_jurnal), step=1, value=0, help="Masukkan nomor baris untuk dihapus, 0 untuk batal")

        if st.button("Hapus Baris") and del_idx > 0:
            st.session_state.jurnal = st.session_state.jurnal.drop(st.session_state.jurnal.index[del_idx-1]).reset_index(drop=True)
            st.success(f"Baris {del_idx} berhasil dihapus!")
            st.experimental_rerun()

        # Hitung total debit dan kredit
        total_debit = df_jurnal["Debit"].sum()
        total_kredit = df_jurnal["Kredit"].sum()

        # Tambah baris total
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Ref": [""],
            "Debit": [total_debit],
            "Kredit": [total_kredit],
        })
        df_final = pd.concat([df_jurnal, total_row], ignore_index=True)

        # Tampilkan dataframe dengan format rupiah & indonesian date
        styler = df_final.style.format({
            "Tanggal": lambda d: d.strftime("%d-%m-%Y") if hasattr(d, "strftime") else d,
            "Debit": "Rp {:,.0f}".format,
            "Kredit": "Rp {:,.0f}".format
        }).set_properties(**{"text-align": "center"})

        st.dataframe(styler, use_container_width=True)
    else:
        st.info("Belum ada data transaksi di Jurnal Umum.")

with tab2:
    st.header("📚 Buku Besar")

    # Inisialisasi akun dan data jika belum ada
    if "accounts" not in st.session_state:
        cols = ["Tanggal", "Keterangan", "Ref", "Debit", "Kredit"]
        st.session_state.accounts = {
            "101 - Kas": pd.DataFrame(columns=cols),
            "102 - Peralatan": pd.DataFrame(columns=cols),
            "103 - Perlengkapan": pd.DataFrame(columns=cols),
            "301 - Modal": pd.DataFrame(columns=cols),
        }

    # Fungsi hitung saldo berjalan
    def hitung_saldo(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        dfx = df.copy()
        dfx["Tanggal"] = pd.to_datetime(dfx["Tanggal"], errors='coerce').dt.date
        for c in ["Debit", "Kredit"]:
            dfx[c] = pd.to_numeric(dfx[c], errors="coerce").fillna(0.0)
        dfx = dfx.sort_values(["Tanggal"], kind="mergesort").reset_index(drop=True)

        saldo_debit = []
        saldo_kredit = []
        running = 0.0
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
        return dfx

    # Form input transaksi baru
    st.subheader("Input Transaksi Baru")
    with st.form("form_input_tb"):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            akun_pil = st.selectbox("Pilih Akun", list(st.session_state.accounts.keys()))
            ket = st.text_input("Keterangan", placeholder="contoh: Membeli peralatan")
        with c2:
            tgl = st.date_input("Tanggal", value=date.today())
            ref = st.text_input("Ref", value="JU-1")
        with c3:
            tipe = st.radio("Tipe", ["Debit", "Kredit"], horizontal=True)
            jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f")
        tambah = st.form_submit_button("Tambah Transaksi")

    if tambah:
        debit = jumlah if tipe == "Debit" else 0.0
        kredit = jumlah if tipe == "Kredit" else 0.0
        baris = pd.DataFrame({
            "Tanggal": [tgl],
            "Keterangan": [ket],
            "Ref": [ref],
            "Debit": [debit],
            "Kredit": [kredit],
        })
        st.session_state.accounts[akun_pil] = pd.concat(
            [st.session_state.accounts[akun_pil], baris], ignore_index=True
        )
        st.success(f"Transaksi berhasil ditambahkan di akun {akun_pil}!")

    st.divider()

    # Tampilkan tabel buku besar per akun dengan saldo berjalan, di Tabs
    akun_list = list(st.session_state.accounts.keys())
    tabs_akun = st.tabs(akun_list)

    for i, akun in enumerate(akun_list):
        with tabs_akun[i]:
            st.markdown(f"**Nama Akun : {akun.split(' - ',1)[1]}**  \nNo Akun : {akun.split(' - ',1)[0]}")
            df = st.session_state.accounts[akun]
            df_show = hitung_saldo(df) if not df.empty else df.copy()
            
            st.dataframe(
                df_show.style.format({
                    "Debit": "{:,.0f}",
                    "Kredit": "{:,.0f}",
                    "Saldo Debit": "{:,.0f}",
                    "Saldo Kredit": "{:,.0f}",
                }).set_properties(**{"text-align": "center"}),
                use_container_width=True
            )
