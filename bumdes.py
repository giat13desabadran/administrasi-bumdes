import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Inisialisasi data awal ===
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Tanggal": "", "Keterangan": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

if "neraca_saldo" not in st.session_state:
    st.session_state.neraca_saldo = pd.DataFrame([
        {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
    ])

if "pendapatan" not in st.session_state:
    st.session_state.pendapatan = pd.DataFrame([
        {"Jenis Pendapatan": "", "Jumlah (Rp)": 0}
    ])

if "beban" not in st.session_state:
    st.session_state.beban = pd.DataFrame([
        {"Jenis Beban": "", "Jumlah (Rp)": 0}
    ])

if "modal_data" not in st.session_state:
    st.session_state.modal_data = {
        "modal_awal": 0,
        "prive": 0
    }

if "aktiva_lancar" not in st.session_state:
    st.session_state.aktiva_lancar = pd.DataFrame([
        {"Item": "", "Jumlah (Rp)": 0}
    ])

if "aktiva_tetap" not in st.session_state:
    st.session_state.aktiva_tetap = pd.DataFrame([
        {"Item": "", "Jumlah (Rp)": 0}
    ])

if "kewajiban" not in st.session_state:
    st.session_state.kewajiban = pd.DataFrame([
        {"Item": "", "Jumlah (Rp)": 0}
    ])

if "arus_kas_operasi" not in st.session_state:
    st.session_state.arus_kas_operasi = pd.DataFrame([
        {"Aktivitas": "", "Jumlah (Rp)": 0}
    ])

if "arus_kas_investasi" not in st.session_state:
    st.session_state.arus_kas_investasi = pd.DataFrame([
        {"Aktivitas": "", "Jumlah (Rp)": 0}
    ])

if "arus_kas_pendanaan" not in st.session_state:
    st.session_state.arus_kas_pendanaan = pd.DataFrame([
        {"Aktivitas": "", "Jumlah (Rp)": 0}
    ])

# Data untuk Buku Besar
if "buku_besar" not in st.session_state:
    st.session_state.buku_besar = {}

# === Fungsi format rupiah ===
def format_rupiah(x):
    try:
        if x < 0:
            return f"({abs(x):,.0f})".replace(",", ".")
        return f"{x:,.0f}".replace(",", ".")
    except Exception:
        return x

# Fungsi format tanggal
def parse_date_safe(s):
    try:
        return pd.to_datetime(s, format="%Y-%m-%d", errors="raise").date()
    except:
        return None
        
# === Fungsi AgGrid ===
def create_aggrid(df, key_suffix, height=400):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=False)
    
    for col in df.columns:
        if "(Rp)" in col:
            gb.configure_column(col, type=["numericColumn"], valueFormatter="value ? value.toLocaleString() : ''")
    
    grid_options = gb.build()
    
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=height,
        key=f"aggrid_{key_suffix}",
        reload_data=False
    )
    
    return pd.DataFrame(grid_response["data"])

# === Fungsi untuk membuat buku besar ===
# === Fungsi untuk membuat buku besar ===
def buat_buku_besar():
    df = st.session_state.data.copy()

    # Pastikan kolom numeric adalah float
    df["Debit (Rp)"] = pd.to_numeric(df["Debit (Rp)"], errors="coerce").fillna(0).astype(float)
    df["Kredit (Rp)"] = pd.to_numeric(df["Kredit (Rp)"], errors="coerce").fillna(0).astype(float)

    buku_besar = {}

    for _, row in df.iterrows():
        akun = str(row.get("Akun", "")).strip()
        if not akun:
            continue

        if akun not in buku_besar:
            buku_besar[akun] = {
                "nama_akun": f"Akun {akun}",
                "debit": 0.0,
                "kredit": 0.0,
                "transaksi": []
            }

        # Konversi nilai ke float dengan aman
        try:
            debit = float(row.get("Debit (Rp)", 0) or 0)
        except:
            debit = 0.0
        
        try:
            kredit = float(row.get("Kredit (Rp)", 0) or 0)
        except:
            kredit = 0.0

        # Tambahkan transaksi jika ada nilai
        if debit > 0:
            buku_besar[akun]["transaksi"].append({
                "tanggal": row.get("Tanggal", ""),
                "keterangan": row.get("Keterangan", ""),
                "debit": debit,
                "kredit": 0.0
            })
            buku_besar[akun]["debit"] += debit

        if kredit > 0:
            buku_besar[akun]["transaksi"].append({
                "tanggal": row.get("Tanggal", ""),
                "keterangan": row.get("Keterangan", ""),
                "debit": 0.0,
                "kredit": kredit
            })
            buku_besar[akun]["kredit"] += kredit

    # Update nama akun dari neraca saldo
    for _, row in st.session_state.neraca_saldo.iterrows():
        akun_no = str(row.get("No Akun", "")).strip()
        nama_akun = str(row.get("Nama Akun", "")).strip()
        if akun_no in buku_besar and nama_akun:
            buku_besar[akun_no]["nama_akun"] = nama_akun

    return buku_besar

# === Styling ===
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

# === Tabs ===
tab1, tab2, tab3, tab4 = st.tabs([
    "🧾 Jurnal Umum", 
    "📚 Buku Besar", 
    "💵 Neraca Saldo",
    "📊 Laporan Keuangan"
])

# ========================================
# TAB 1: JURNAL UMUM
# ========================================
with tab1:
    st.header("🧾 Jurnal Umum")
    st.info("💡 Tekan Enter sekali untuk menyimpan perubahan otomatis.")

    # --- Input bulan dan tahun ---
    col1, col2 = st.columns(2)
    with col1:
        bulan_selected = st.selectbox(
            "Pilih Bulan", 
            options=[
                ("01", "Januari"), ("02", "Februari"), ("03", "Maret"),
                ("04", "April"), ("05", "Mei"), ("06", "Juni"),
                ("07", "Juli"), ("08", "Agustus"), ("09", "September"),
                ("10", "Oktober"), ("11", "November"), ("12", "Desember")
            ],
            format_func=lambda x: x[1]
        )[0]  # ambil kode bulan "01"-"12"
    with col2:
        tahun_selected = st.number_input("Tahun", min_value=2000, max_value=2100, value=pd.Timestamp.now().year, step=1)
        
    # Tombol tambah baris untuk Jurnal Umum
    if st.button("➕ Tambah Baris Jurnal", key="tambah_jurnal"):
        new_row = pd.DataFrame([{"Tanggal": "", "Keterangan": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
        st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
        st.rerun()

    # Konfigurasi Grid 
    gb = GridOptionsBuilder.from_dataframe(st.session_state.data)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=False)
    gb.configure_column(
    "Tanggal",
    editable=True,
    cellEditor="agDateCellEditor",
    valueFormatter="value ? new Date(value).toLocaleDateString('en-CA') : ''",
    valueParser="""
        function(params){
            if (!params.newValue) return '';
            // Konversi ke tanggal ISO
            const d = new Date(params.newValue);
            if (isNaN(d)) return '';
            return d.toISOString().split('T')[0]; // "YYYY-MM-DD"
        }
    """
    )
    gb.configure_column("Keterangan", header_name="Keterangan")
    gb.configure_column("Akun", header_name="Akun (contoh: Perlengkapan)")
    gb.configure_column("Debit (Rp)", type=["numericColumn"], valueFormatter="value ? value.toLocaleString() : ''")
    gb.configure_column("Kredit (Rp)", type=["numericColumn"], valueFormatter="value ? value.toLocaleString() : ''")

    grid_options = gb.build()

    grid_response = AgGrid(
        st.session_state.data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=320,
        key="aggrid_jurnal",
        reload_data=False
    )

    new_df = pd.DataFrame(grid_response["data"])
    for col in ["Debit (Rp)", "Kredit (Rp)"]:
        if col in new_df.columns:
            new_df[col] = pd.to_numeric(new_df[col], errors="coerce").fillna(0)
    if "Tanggal" in new_df.columns:
        # ubah semua jadi string dulu, strip whitespace
        new_df["Tanggal"] = new_df["Tanggal"].astype(str).str.strip()
        
        # ubah string kosong atau "None"/"nan" menjadi NaN
        new_df["Tanggal"] = new_df["Tanggal"].replace({"": pd.NA, "None": pd.NA, "nan": pd.NA})
        
        # konversi ke datetime, invalid jadi NaT
        new_df["Tanggal"] = pd.to_datetime(new_df["Tanggal"], errors="coerce")
        
        # ubah NaT menjadi string kosong agar tampil di st.dataframe
        new_df["Tanggal"] = new_df["Tanggal"].dt.strftime('%Y-%m-%d').fillna('')

    if not new_df.equals(st.session_state.data):
        st.session_state.data = new_df.copy()

    df_clean = new_df[new_df["Keterangan"].astype(str).str.strip() != ""]

    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Akun": [""],
            "Debit (Rp)": [total_debit],
            "Kredit (Rp)": [total_kredit],
        })
        df_final = pd.concat([df_clean, total_row], ignore_index=True)

        st.write("### 📊 Hasil Jurnal")
        df_final_display = df_final.copy()
        df_final_display.index = range(1, len(df_final_display) + 1)
        df_final_display.index.name = "No"
    
        
        st.dataframe(df_final_display.style.format({
            "Debit (Rp)": format_rupiah,
            "Kredit (Rp)": format_rupiah
        }))

        def buat_pdf(df, bulan, tahun):
            import calendar
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            # Konversi angka bulan ke nama bulan Indonesia
            bulan_dict = {
                1: "Januari",
                2: "Februari",
                3: "Maret",
                4: "April",
                5: "Mei",
                6: "Juni",
                7: "Juli",
                8: "Agustus",
                9: "September",
                10: "Oktober",
                11: "November",
                12: "Desember"
            }
            
            bulan_nama = bulan_dict.get(int(bulan), calendar.month_name[int(bulan)])
            pdf.cell(200, 10, txt=f"Jurnal Umum BUMDes - {bulan_nama} {tahun}", ln=True, align="C")
            pdf.ln(8)
        
            col_width = 190 / len(df.columns)
            # Header tabel
            pdf.set_font("Arial", size=10, style="B")  # Bold untuk header
            for col in df.columns:
                pdf.cell(col_width, 10, col, border=1, align="C")
            pdf.ln()
        
            pdf.set_font("Arial", size=9)  # Ukuran font lebih kecil untuk konten
            for _, row in df.iterrows():
                for item in row:
                    # Format angka jika nilai numerik
                    if isinstance(item, (int, float)):
                        item = f"{item:,.0f}".replace(",", ".")
                    pdf.cell(col_width, 8, str(item), border=1, align="C")
                pdf.ln()
        
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                return tmp.read()
        
        # Pastikan bulan_selected adalah angka (bukan nama bulan)
        pdf_data = buat_pdf(df_final, bulan_selected, tahun_selected)
        st.download_button(
            "📥 Download PDF",
            data=pdf_data,
            file_name=f"jurnal_umum_{bulan_selected}_{tahun_selected}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.warning("Belum ada data valid di tabel.")
        
# ========================================
# TAB 2: BUKU BESAR
# ========================================
with tab2:
    st.header("📚 Buku Besar")
    
    # Perbarui buku besar berdasarkan jurnal
    st.session_state.buku_besar = buat_buku_besar()
    
    if not st.session_state.buku_besar:
        st.info("ℹ️ Belum ada data untuk buku besar. Silakan isi Jurnal Umum terlebih dahulu.")
    
    else:
        # Buat pilihan berdasarkan nama akun asli
        akun_labels = {k: v["nama_akun"] for k, v in st.session_state.buku_besar.items()}
        
        # Selectbox menampilkan hanya nama akun
        selected_label = st.selectbox("Pilih Akun:", akun_labels.values())
        
        # Cari key berdasarkan label
        akun_no = [k for k, v in akun_labels.items() if v == selected_label][0]
        akun_data = st.session_state.buku_besar[akun_no]

        # Hitung saldo
        saldo = akun_data["debit"] - akun_data["kredit"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Debit", format_rupiah(akun_data["debit"]))
        with col2:
            st.metric("Total Kredit", format_rupiah(akun_data["kredit"]))
        with col3:
            st.metric("Saldo Akhir", format_rupiah(saldo))

        # Tabel transaksi
        if akun_data["transaksi"]:
            df_transaksi = pd.DataFrame(akun_data["transaksi"])
            st.write(f"### Transaksi Akun: {akun_data['nama_akun']}")

            df_transaksi_display = df_transaksi.copy()
            df_transaksi_display.index = range(1, len(df_transaksi_display) + 1)
            df_transaksi_display.index.name = "No"

            st.dataframe(df_transaksi_display.style.format({
                "debit": format_rupiah,
                "kredit": format_rupiah
            }))

            # === PDF Buku Besar ===
            def buat_pdf_buku_besar(akun_no, akun_data):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, txt=f"Buku Besar", ln=True, align="C")
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 8, txt=f"Akun: {akun_data['nama_akun']}", ln=True, align="C")
                pdf.ln(5)

                pdf.set_font("Arial", '', 10)
                pdf.cell(0, 8, txt=f"Total Debit  : {format_rupiah(akun_data['debit'])}", ln=True)
                pdf.cell(0, 8, txt=f"Total Kredit : {format_rupiah(akun_data['kredit'])}", ln=True)
                saldo = akun_data["debit"] - akun_data["kredit"]
                pdf.cell(0, 8, txt=f"Saldo Akhir  : {format_rupiah(saldo)}", ln=True)
                pdf.ln(5)

                # Header tabel
                pdf.set_font("Arial", 'B', 10)
                col_widths = [25, 60, 50, 50]
                headers = ["Tanggal", "Keterangan", "Debit (Rp)", "Kredit (Rp)"]
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header, border=1, align="C")
                pdf.ln()

                # Isi tabel
                pdf.set_font("Arial", '', 9)
                for trx in akun_data["transaksi"]:
                    pdf.cell(col_widths[0], 8, str(trx["tanggal"]), border=1, align="C")

                    ket = str(trx["keterangan"])
                    if len(ket) > 30:
                        ket = ket[:27] + "..."
                    pdf.cell(col_widths[1], 8, ket, border=1, align="L")

                    pdf.cell(col_widths[2], 8, format_rupiah(trx["debit"]), border=1, align="R")
                    pdf.cell(col_widths[3], 8, format_rupiah(trx["kredit"]), border=1, align="R")
                    pdf.ln()

                pdf.ln(5)
                pdf.set_font("Arial", 'I', 8)
                pdf.cell(0, 5, txt="Dicetak dari Sistem Akuntansi BUMDes", ln=True, align="C")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    pdf.output(tmp.name)
                    tmp.seek(0)
                    return tmp.read()

            pdf_buku_besar = buat_pdf_buku_besar(akun_no, akun_data)
            st.download_button(
                "📥 Download PDF Buku Besar",
                data=pdf_buku_besar,
                file_name=f"buku_besar_{akun_data['nama_akun']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.info("Tidak ada transaksi untuk akun ini.")

# ========================================
# TAB 3: NERACA SALDO (OPTIMIZED FOR STREAMLIT CLOUD)
# ========================================
with tab3:
    st.header("💵 Neraca Saldo BUMDes")
    st.subheader("Periode: Januari 2025")
    st.info("💡 Masukkan data saldo akhir dari setiap akun di Buku Besar. Klik 'Tambah Baris' untuk menambah data baru.")

    if "neraca_refresh_counter" not in st.session_state:
        st.session_state.neraca_refresh_counter = 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Tambah 1 Baris", key="tambah_neraca_1", use_container_width=True):
            new_row = pd.DataFrame([{"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
            st.session_state.neraca_saldo = pd.concat([st.session_state.neraca_saldo, new_row], ignore_index=True)
            st.session_state.neraca_refresh_counter += 1
            st.rerun()
    
    with col2:
        if st.button("➕➕ Tambah 5 Baris", key="tambah_neraca_5", use_container_width=True):
            new_rows = pd.DataFrame([
                {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
            ])
            st.session_state.neraca_saldo = pd.concat([st.session_state.neraca_saldo, new_rows], ignore_index=True)
            st.session_state.neraca_refresh_counter += 1
            st.rerun()
    
    with col3:
        if st.button("🗑️ Hapus Kosong", key="hapus_neraca_kosong", use_container_width=True):
            st.session_state.neraca_saldo = st.session_state.neraca_saldo[
                st.session_state.neraca_saldo["Nama Akun"].astype(str).str.strip() != ""
            ].reset_index(drop=True)
            
            if len(st.session_state.neraca_saldo) == 0:
                st.session_state.neraca_saldo = pd.DataFrame([
                    {"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
                ])
            st.session_state.neraca_refresh_counter += 1
            st.rerun()

    total_rows = len(st.session_state.neraca_saldo)
    filled_rows = len(st.session_state.neraca_saldo[st.session_state.neraca_saldo["Nama Akun"].astype(str).str.strip() != ""])
    st.caption(f"📊 Total Baris: {total_rows} | Terisi: {filled_rows} | Kosong: {total_rows - filled_rows}")

    # EXPANDER HAPUS BARIS (INI HARUS MUNCUL!)
    df_terisi = st.session_state.neraca_saldo[st.session_state.neraca_saldo["Nama Akun"].astype(str).str.strip() != ""]
    
    if len(df_terisi) > 0:
        with st.expander("🗑️ Hapus Baris Tertentu (Klik untuk buka)", expanded=False):
            st.write("**Cara menggunakan:**")
            st.write("1. Lihat nomor baris di tabel preview")
            st.write("2. Ketik nomor yang ingin dihapus (contoh: 1 atau 1,2,3)")
            st.write("3. Klik tombol Hapus")
            
            preview_df = df_terisi.copy().reset_index(drop=True)
            preview_df.index = preview_df.index + 1
            preview_df.index.name = "No"
            
            st.dataframe(
                preview_df.style.format({
                    "Debit (Rp)": format_rupiah,
                    "Kredit (Rp)": format_rupiah,
                }),
                use_container_width=True,
                height=150
            )
            
            nomor_hapus = st.text_input(
                "Nomor baris yang akan dihapus:",
                placeholder="1 atau 1,2,3",
                key="input_nomor_hapus"
            )
            
            col_btn = st.columns([1, 1, 2])
            
            with col_btn[0]:
                if st.button("🗑️ Hapus", key="btn_hapus", use_container_width=True):
                    if nomor_hapus.strip():
                        try:
                            nomor_list = [int(x.strip()) for x in nomor_hapus.split(",")]
                            valid_nomor = [n for n in nomor_list if 1 <= n <= len(df_terisi)]
                            
                            if valid_nomor:
                                indices = [df_terisi.index[n-1] for n in valid_nomor]
                                st.session_state.neraca_saldo = st.session_state.neraca_saldo.drop(indices).reset_index(drop=True)
                                
                                if len(st.session_state.neraca_saldo) == 0:
                                    st.session_state.neraca_saldo = pd.DataFrame([{"No Akun": "", "Nama Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                                
                                st.session_state.neraca_refresh_counter += 1
                                st.success(f"✅ {len(valid_nomor)} baris dihapus!")
                                st.rerun()
                        except:
                            st.error("❌ Format salah!")

    st.markdown("---")
    
    aggrid_key = f"neraca_{st.session_state.neraca_refresh_counter}"
    
    gb = GridOptionsBuilder.from_dataframe(st.session_state.neraca_saldo)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=False)
    
    for col in st.session_state.neraca_saldo.columns:
        if "(Rp)" in col:
            gb.configure_column(col, type=["numericColumn"], valueFormatter="value ? value.toLocaleString() : ''")
    
    grid_options = gb.build()
    
    grid_response = AgGrid(
        st.session_state.neraca_saldo,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=300,
        key=aggrid_key,
        reload_data=True
    )
    
    new_neraca = pd.DataFrame(grid_response["data"])
    if not new_neraca.equals(st.session_state.neraca_saldo):
        st.session_state.neraca_saldo = new_neraca.copy()

    df_neraca_clean = new_neraca[new_neraca["Nama Akun"].astype(str).str.strip() != ""]

    if not df_neraca_clean.empty:
        total_debit = df_neraca_clean["Debit (Rp)"].sum()
        total_kredit = df_neraca_clean["Kredit (Rp)"].sum()

        total_row = pd.DataFrame({
            "No Akun": [""],
            "Nama Akun": ["Jumlah"],
            "Debit (Rp)": [total_debit],
            "Kredit (Rp)": [total_kredit]
        })

        df_neraca_final = pd.concat([df_neraca_clean, total_row], ignore_index=True)
        df_neraca_final.index = range(1, len(df_neraca_final) + 1)
        df_neraca_final.index.name = "No"

        st.write("### 📊 Hasil Neraca Saldo")
        st.dataframe(
            df_neraca_final.style.format({
                "Debit (Rp)": format_rupiah,
                "Kredit (Rp)": format_rupiah,
            }).apply(lambda x: ['font-weight: bold' if i == len(df_neraca_final) else '' for i in range(len(x))], axis=0),
            use_container_width=True
        )

        def buat_pdf_neraca(df):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, txt="Neraca Saldo BUMDes", ln=True, align="C")
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 8, txt="Periode: Januari 2025", ln=True, align="C")
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            col_widths = [15, 25, 70, 40, 40]
            headers = ["No", "No Akun", "Nama Akun", "Debit (Rp)", "Kredit (Rp)"]
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 10, header, border=1, align="C")
            pdf.ln()
            pdf.set_font("Arial", '', 9)
            for idx, row in df.iterrows():
                pdf.cell(col_widths[0], 8, str(idx), border=1, align="C")
                pdf.cell(col_widths[1], 8, str(row["No Akun"]), border=1, align="C")
                nama_akun = str(row["Nama Akun"])
                if len(nama_akun) > 35:
                    nama_akun = nama_akun[:32] + "..."
                pdf.cell(col_widths[2], 8, nama_akun, border=1, align="L")
                debit_val = row["Debit (Rp)"]
                debit_text = format_rupiah(debit_val) if isinstance(debit_val, (int, float)) and debit_val != 0 else "-"
                pdf.cell(col_widths[3], 8, debit_text, border=1, align="R")
                kredit_val = row["Kredit (Rp)"]
                kredit_text = format_rupiah(kredit_val) if isinstance(kredit_val, (int, float)) and kredit_val != 0 else "-"
                pdf.cell(col_widths[4], 8, kredit_text, border=1, align="R")
                pdf.ln()
            pdf.ln(5)
            pdf.set_font("Arial", 'I', 8)
            pdf.cell(0, 5, txt="Dicetak dari Sistem Akuntansi BUMDes", ln=True, align="C")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                return tmp.read()

        pdf_neraca = buat_pdf_neraca(df_neraca_final)
        st.download_button(
            "📥 Download PDF Neraca Saldo",
            data=pdf_neraca,
            file_name="neraca_saldo.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ========================================
# TAB 4: LAPORAN KEUANGAN (SESUAI SCREENSHOT)
# ========================================
with tab4:
    st.header("📊 Laporan Keuangan BUMDes")
    st.subheader("Periode: Januari 2025")

    # ========================================
    # 1. LAPORAN LABA/RUGI
    # ========================================
    st.markdown("---")
    st.markdown("### 📈 Laporan Laba/Rugi")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.write("#### Input Pendapatan:")
        if st.button("➕ Tambah Pendapatan", key="tambah_pendapatan"):
            new_row = pd.DataFrame([{"Jenis Pendapatan": "", "Jumlah (Rp)": 0}])
            st.session_state.pendapatan = pd.concat([st.session_state.pendapatan, new_row], ignore_index=True)
            st.rerun()
        
        new_pendapatan = create_aggrid(st.session_state.pendapatan, "pendapatan", height=250)
        if not new_pendapatan.equals(st.session_state.pendapatan):
            st.session_state.pendapatan = new_pendapatan.copy()

    with col2:
        st.write("#### Input Beban-Beban:")
        if st.button("➕ Tambah Beban", key="tambah_beban"):
            new_row = pd.DataFrame([{"Jenis Beban": "", "Jumlah (Rp)": 0}])
            st.session_state.beban = pd.concat([st.session_state.beban, new_row], ignore_index=True)
            st.rerun()
        
        new_beban = create_aggrid(st.session_state.beban, "beban", height=250)
        if not new_beban.equals(st.session_state.beban):
            st.session_state.beban = new_beban.copy()

    df_pendapatan_clean = new_pendapatan[new_pendapatan["Jenis Pendapatan"].astype(str).str.strip() != ""]
    df_beban_clean = new_beban[new_beban["Jenis Beban"].astype(str).str.strip() != ""]

    if not df_pendapatan_clean.empty or not df_beban_clean.empty:
        total_pendapatan = df_pendapatan_clean["Jumlah (Rp)"].sum()
        total_beban = df_beban_clean["Jumlah (Rp)"].sum()
        laba_bersih = total_pendapatan - total_beban

        st.write("### 📊 Hasil Laporan Laba/Rugi")
        
        # Format sesuai screenshot Excel (3 kolom)
        result_data = []
        result_data.append({"": "Laporan Laba/Rugi", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "BUMDes", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "Pendapatan:", "Kolom2": "", "Jumlah": ""})
        
        for idx, row in df_pendapatan_clean.iterrows():
            result_data.append({"": f"{idx+1}. {row['Jenis Pendapatan']}", "Kolom2": "", "Jumlah": row["Jumlah (Rp)"]})
        
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "Total Pendapatan", "Kolom2": "", "Jumlah": total_pendapatan})
        result_data.append({"": "Beban-Beban:", "Kolom2": "", "Jumlah": ""})
        
        for idx, row in df_beban_clean.iterrows():
            result_data.append({"": f"{idx+1}. {row['Jenis Beban']}", "Kolom2": "", "Jumlah": row["Jumlah (Rp)"]})
        
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "Total Beban", "Kolom2": "", "Jumlah": total_beban})
        result_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        result_data.append({"": "Laba Bersih", "Kolom2": "", "Jumlah": laba_bersih})

        df_labarugi = pd.DataFrame(result_data)
        
        st.dataframe(
            df_labarugi.style.format({"Jumlah": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x})
            .set_properties(**{'text-align': 'left'}, subset=[''])
            .set_properties(**{'text-align': 'right'}, subset=['Jumlah']),
            use_container_width=True,
            hide_index=True
        )

    # ========================================
    # 2. LAPORAN PERUBAHAN MODAL
    # ========================================
    st.markdown("---")
    st.markdown("### 💰 Laporan Perubahan Modal")
    
    col1, col2 = st.columns(2)
    with col1:
        modal_awal = st.number_input("Modal Awal (Rp)", value=st.session_state.modal_data["modal_awal"], step=100000, key="modal_awal_input")
    with col2:
        prive = st.number_input("Prive (Rp)", value=st.session_state.modal_data["prive"], step=100000, key="prive_input")
    
    if modal_awal != st.session_state.modal_data["modal_awal"] or prive != st.session_state.modal_data["prive"]:
        st.session_state.modal_data["modal_awal"] = modal_awal
        st.session_state.modal_data["prive"] = prive

    if not df_pendapatan_clean.empty or not df_beban_clean.empty:
        modal_akhir = modal_awal + laba_bersih - prive

        st.write("### 📊 Hasil Laporan Perubahan Modal")
        
        # Format sesuai screenshot (Prive di kolom TENGAH!)
        modal_data = []
        modal_data.append({"": "Laporan Perubahan Modal", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "BUMDes", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "Modal Awal", "Kolom2": "", "Jumlah": modal_awal})
        modal_data.append({"": "", "Kolom2": "", "Jumlah": ""})
        modal_data.append({"": "Laba Bersih", "Kolom2": "", "Jumlah": laba_bersih})
        modal_data.append({"": "Prive", "Kolom2": prive, "Jumlah": ""})  # Prive di kolom tengah!
        modal_data.append({"": "Modal Akhir", "Kolom2": "", "Jumlah": modal_akhir})

        df_modal = pd.DataFrame(modal_data)

        st.dataframe(
            df_modal.style.format({
                "Kolom2": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x,
                "Jumlah": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x
            })
            .set_properties(**{'text-align': 'left'}, subset=[''])
            .set_properties(**{'text-align': 'right'}, subset=['Kolom2', 'Jumlah']),
            use_container_width=True,
            hide_index=True
        )

        # ========================================
        # 3. LAPORAN NERACA
        # ========================================
        st.markdown("---")
        st.markdown("### 🏦 Laporan Neraca")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Aktiva Lancar:")
            if st.button("➕ Tambah Aktiva Lancar", key="tambah_aktiva_lancar"):
                new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                st.session_state.aktiva_lancar = pd.concat([st.session_state.aktiva_lancar, new_row], ignore_index=True)
                st.rerun()
            
            new_aktiva_lancar = create_aggrid(st.session_state.aktiva_lancar, "aktiva_lancar", height=200)
            if not new_aktiva_lancar.equals(st.session_state.aktiva_lancar):
                st.session_state.aktiva_lancar = new_aktiva_lancar.copy()

            st.write("#### Aktiva Tetap:")
            if st.button("➕ Tambah Aktiva Tetap", key="tambah_aktiva_tetap"):
                new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                st.session_state.aktiva_tetap = pd.concat([st.session_state.aktiva_tetap, new_row], ignore_index=True)
                st.rerun()
            
            new_aktiva_tetap = create_aggrid(st.session_state.aktiva_tetap, "aktiva_tetap", height=200)
            if not new_aktiva_tetap.equals(st.session_state.aktiva_tetap):
                st.session_state.aktiva_tetap = new_aktiva_tetap.copy()

        with col2:
            st.write("#### Kewajiban:")
            if st.button("➕ Tambah Kewajiban", key="tambah_kewajiban"):
                new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                st.session_state.kewajiban = pd.concat([st.session_state.kewajiban, new_row], ignore_index=True)
                st.rerun()
            
            new_kewajiban = create_aggrid(st.session_state.kewajiban, "kewajiban", height=200)
            if not new_kewajiban.equals(st.session_state.kewajiban):
                st.session_state.kewajiban = new_kewajiban.copy()

        df_aktiva_lancar_clean = new_aktiva_lancar[new_aktiva_lancar["Item"].astype(str).str.strip() != ""]
        df_aktiva_tetap_clean = new_aktiva_tetap[new_aktiva_tetap["Item"].astype(str).str.strip() != ""]
        df_kewajiban_clean = new_kewajiban[new_kewajiban["Item"].astype(str).str.strip() != ""]

        jml_aktiva_lancar = df_aktiva_lancar_clean["Jumlah (Rp)"].sum()
        jml_aktiva_tetap = df_aktiva_tetap_clean["Jumlah (Rp)"].sum()
        jml_aktiva = jml_aktiva_lancar + jml_aktiva_tetap
        
        jml_kewajiban = df_kewajiban_clean["Jumlah (Rp)"].sum()
        jml_ekuitas = modal_akhir
        jml_kewajiban_ekuitas = jml_kewajiban + jml_ekuitas

        st.write("### 📊 Hasil Laporan Neraca")
        
        # Format sesuai screenshot (4 kolom)
        neraca_data = []
        neraca_data.append({"Aktiva": "Laporan Neraca", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "BUMDes", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Aktiva", "Jumlah1": "", "Passiva": "Passiva", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Aktiva Lancar:", "Jumlah1": "", "Passiva": "Kewajiban:", "Jumlah2": ""})
        
        max_rows = max(len(df_aktiva_lancar_clean), len(df_kewajiban_clean))
        for i in range(max_rows):
            aktiva_item = df_aktiva_lancar_clean.iloc[i]["Item"] if i < len(df_aktiva_lancar_clean) else ""
            aktiva_val = df_aktiva_lancar_clean.iloc[i]["Jumlah (Rp)"] if i < len(df_aktiva_lancar_clean) else ""
            kewajiban_item = df_kewajiban_clean.iloc[i]["Item"] if i < len(df_kewajiban_clean) else ""
            kewajiban_val = df_kewajiban_clean.iloc[i]["Jumlah (Rp)"] if i < len(df_kewajiban_clean) else ""
            
            neraca_data.append({
                "Aktiva": aktiva_item,
                "Jumlah1": aktiva_val,
                "Passiva": kewajiban_item,
                "Jumlah2": kewajiban_val
            })
        
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Jml aktiva lancar", "Jumlah1": jml_aktiva_lancar, "Passiva": "Ekuitas:", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "Modal", "Jumlah2": modal_awal})
        neraca_data.append({"Aktiva": "Aktiva Tetap:", "Jumlah1": "", "Passiva": "Laba", "Jumlah2": laba_bersih})
        
        for idx, row in df_aktiva_tetap_clean.iterrows():
            neraca_data.append({
                "Aktiva": row['Item'],
                "Jumlah1": row["Jumlah (Rp)"],
                "Passiva": "Prive" if idx == df_aktiva_tetap_clean.index[0] else "",
                "Jumlah2": f"({format_rupiah(prive)})" if idx == df_aktiva_tetap_clean.index[0] else ""  # Kurung!
            })
        
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Jml Aktiva", "Jumlah1": jml_aktiva, "Passiva": "Jml Kewajiban&Ekuitas", "Jumlah2": jml_kewajiban_ekuitas})

        df_neraca_lap = pd.DataFrame(neraca_data)

        st.dataframe(
            df_neraca_lap.style.format({
                "Jumlah1": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x,
                "Jumlah2": lambda x: x if isinstance(x, str) and "(" in x else (format_rupiah(x) if isinstance(x, (int, float)) else x)
            })
            .set_properties(**{'text-align': 'left'}, subset=['Aktiva', 'Passiva'])
            .set_properties(**{'text-align': 'right'}, subset=['Jumlah1', 'Jumlah2']),
            use_container_width=True,
            hide_index=True
        )

        # ========================================
        # 4. LAPORAN ARUS KAS
        # ========================================
        st.markdown("---")
        st.markdown("### 💸 Laporan Arus Kas")

        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("#### Arus Kas Operasi:")
            if st.button("➕ Tambah Operasi", key="tambah_operasi"):
                new_row = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                st.session_state.arus_kas_operasi = pd.concat([st.session_state.arus_kas_operasi, new_row], ignore_index=True)
                st.rerun()
            
            new_arus_operasi = create_aggrid(st.session_state.arus_kas_operasi, "operasi", height=250)
            if not new_arus_operasi.equals(st.session_state.arus_kas_operasi):
                st.session_state.arus_kas_operasi = new_arus_operasi.copy()

        with col2:
            st.write("#### Arus Kas Investasi:")
            if st.button("➕ Tambah Investasi", key="tambah_investasi"):
                new_row = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                st.session_state.arus_kas_investasi = pd.concat([st.session_state.arus_kas_investasi, new_row], ignore_index=True)
                st.rerun()
            
            new_arus_investasi = create_aggrid(st.session_state.arus_kas_investasi, "investasi", height=250)
            if not new_arus_investasi.equals(st.session_state.arus_kas_investasi):
                st.session_state.arus_kas_investasi = new_arus_investasi.copy()

        with col3:
            st.write("#### Arus Kas Pendanaan:")
            if st.button("➕ Tambah Pendanaan", key="tambah_pendanaan"):
                new_row = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                st.session_state.arus_kas_pendanaan = pd.concat([st.session_state.arus_kas_pendanaan, new_row], ignore_index=True)
                st.rerun()
            
            new_arus_pendanaan = create_aggrid(st.session_state.arus_kas_pendanaan, "pendanaan", height=250)
            if not new_arus_pendanaan.equals(st.session_state.arus_kas_pendanaan):
                st.session_state.arus_kas_pendanaan = new_arus_pendanaan.copy()

        df_operasi_clean = new_arus_operasi[new_arus_operasi["Aktivitas"].astype(str).str.strip() != ""]
        df_investasi_clean = new_arus_investasi[new_arus_investasi["Aktivitas"].astype(str).str.strip() != ""]
        df_pendanaan_clean = new_arus_pendanaan[new_arus_pendanaan["Aktivitas"].astype(str).str.strip() != ""]

        if not df_operasi_clean.empty or not df_investasi_clean.empty or not df_pendanaan_clean.empty:
            st.write("### 📊 Hasil Laporan Arus Kas")
            
            # Format sesuai screenshot (3 kolom)
            arus_kas_data = []
            arus_kas_data.append({"": "Laporan Arus Kas", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "BUMDes", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "Arus Kas Operasi:", "Kolom2": "", "Jumlah": ""})
            
            for _, row in df_operasi_clean.iterrows():
                arus_kas_data.append({"": row['Aktivitas'], "Kolom2": "", "Jumlah": row["Jumlah (Rp)"]})
            
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "Arus Kas Investasi:", "Kolom2": "", "Jumlah": ""})
            
            for _, row in df_investasi_clean.iterrows():
                arus_kas_data.append({"": row['Aktivitas'], "Kolom2": "", "Jumlah": row["Jumlah (Rp)"]})
            
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "", "Kolom2": "", "Jumlah": ""})
            arus_kas_data.append({"": "Arus Kas Pendanaan:", "Kolom2": "", "Jumlah": ""})
            
            for _, row in df_pendanaan_clean.iterrows():
                arus_kas_data.append({"": row['Aktivitas'], "Kolom2": "", "Jumlah": row["Jumlah (Rp)"]})

            df_arus_kas = pd.DataFrame(arus_kas_data)

            st.dataframe(
                df_arus_kas.style.format({
                    "Jumlah": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x
                })
                .set_properties(**{'text-align': 'left'}, subset=[''])
                .set_properties(**{'text-align': 'right'}, subset=['Jumlah']),
                use_container_width=True,
                hide_index=True
            )
