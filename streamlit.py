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

# === Tabs utama ===
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# =========================
#         JURNAL UMUM
# =========================
with tab1:
    st.header("🧾 Jurnal Umum (Input Transaksi)")

    # Inisialisasi / migrasi struktur DataFrame jurnal
    jurnal_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]
    if "jurnal" not in st.session_state:
        st.session_state.jurnal = pd.DataFrame(columns=jurnal_cols)
    else:
        # Drop kolom 'Ref' jika masih ada (migrasi data lama)
        if "Ref" in st.session_state.jurnal.columns:
            st.session_state.jurnal = st.session_state.jurnal.drop(columns=["Ref"])

        # Pastikan urutan dan kelengkapan kolom sesuai
        for c in jurnal_cols:
            if c not in st.session_state.jurnal.columns:
                st.session_state.jurnal[c] = []  # tambahkan kolom kosong
        st.session_state.jurnal = st.session_state.jurnal[jurnal_cols]

    # Form input transaksi (tanpa 'Ref')
    with st.form("form_input_jurnal"):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            tgl = st.date_input("Tanggal", value=date.today())
            ket = st.text_input("Keterangan", placeholder="Deskripsi transaksi")
        with c2:
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
            debit = float(jumlah) if tipe == "Debit" else 0.0
            kredit = float(jumlah) if tipe == "Kredit" else 0.0

            new_row = {
                "Tanggal": tgl,
                "Keterangan": ket.strip(),
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

    if not df_jurnal.empty:
        st.subheader("Data Jurnal Umum")

        # Nomori baris mulai dari 1 (untuk tampilan)
        df_display = df_jurnal.copy()
        df_display.index = range(1, len(df_display) + 1)

        # Hitung total debit dan kredit
        total_debit = df_jurnal["Debit"].sum()
        total_kredit = df_jurnal["Kredit"].sum()

        # Tambah baris total (untuk tampilan)
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Debit": [total_debit],
            "Kredit": [total_kredit],
        })
        # gunakan ignore_index=False agar index penomoran tidak berubah
        df_final = pd.concat([df_display, total_row], ignore_index=False)

        # Format tampilan
        def fmt_tgl(v):
            try:
                return pd.to_datetime(v).strftime("%d-%m-%Y")
            except Exception:
                return v

        styler = df_final.style.format({
            "Tanggal": fmt_tgl,
            "Debit": "Rp {:,.0f}".format,
            "Kredit": "Rp {:,.0f}".format
        }).set_properties(**{"text-align": "center"})

        st.dataframe(styler, use_container_width=True)

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
                # Map nomor tampilan (1..N) ke index asli (0..N-1)
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
            "101 - Kas": pd.DataFrame(columns=akun_cols),
            "102 - Peralatan": pd.DataFrame(columns=akun_cols),
            "103 - Perlengkapan": pd.DataFrame(columns=akun_cols),
            "301 - Modal": pd.DataFrame(columns=akun_cols),
        }
    else:
        # Migrasi data lama: drop 'Ref' jika ada di tiap akun
        for k, df in st.session_state.accounts.items():
            if "Ref" in df.columns:
                st.session_state.accounts[k] = df.drop(columns=["Ref"])
            # Pastikan kolom lengkap & berurutan
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

        # Urutkan berdasarkan tanggal (stable sort)
        dfx = dfx.sort_values(["Tanggal"], kind="mergesort").reset_index(drop=True)

        # Hitung saldo berjalan (Debit - Kredit)
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

        # Kembalikan tanggal ke date untuk tampilan
        dfx["Tanggal"] = dfx["Tanggal"].dt.date
        return dfx

    # Form input transaksi baru ke Buku Besar (tanpa 'Ref')
    st.subheader("Input Transaksi Baru")
    with st.form("form_input_tb"):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            akun_pil = st.selectbox("Pilih Akun", list(st.session_state.accounts.keys()))
            ket_bb = st.text_input("Keterangan", placeholder="contoh: Membeli peralatan")
        with c2:
            tgl_bb = st.date_input("Tanggal", value=date.today())
        with c3:
            tipe_bb = st.radio("Tipe", ["Debit", "Kredit"], horizontal=True, key="tipe_bb")
            jumlah_bb = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f", key="jumlah_bb")
        tambah = st.form_submit_button("Tambah Transaksi")

    if tambah:
        if ket_bb.strip() == "":
            st.error("Mohon isi kolom keterangan!")
        elif jumlah_bb <= 0:
            st.error("Jumlah harus lebih dari nol!")
        else:
            debit = float(jumlah_bb) if tipe_bb == "Debit" else 0.0
            kredit = float(jumlah_bb) if tipe_bb == "Kredit" else 0.0
            baris = pd.DataFrame({
                "Tanggal": [tgl_bb],
                "Keterangan": [ket_bb.strip()],
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
            st.markdown(f"Nama Akun : {akun.split(' - ',1)[1]}  \nNo Akun : {akun.split(' - ',1)[0]}")
            df = st.session_state.accounts[akun]
            df_show = hitung_saldo(df) if not df.empty else df.copy()

            st.dataframe(
                df_show.style.format({
                    "Debit": "Rp {:,.0f}".format,
                    "Kredit": "Rp {:,.0f}".format,
                    "Saldo Debit": "Rp {:,.0f}".format,
                    "Saldo Kredit": "Rp {:,.0f}".format,
                }).set_properties(**{"text-align": "center"}),
                use_container_width=True
            )
