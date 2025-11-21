import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# === Konfigurasi dasar ===
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# === Inisialisasi data awal ===
def init_dataframe(columns):
    return pd.DataFrame([{col: 0 if "(Rp)" in col or col == "Jumlah (Rp)" else "" for col in columns}])

if "data" not in st.session_state:
    st.session_state.data = init_dataframe(["Tanggal", "Keterangan", "Ref", "Akun", "Debit (Rp)", "Kredit (Rp)"])

if "neraca_saldo" not in st.session_state:
    st.session_state.neraca_saldo = pd.DataFrame([
        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}  # ← UBAH INI!
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

if "buku_besar" not in st.session_state:
    st.session_state.buku_besar = {}

if "neraca_refresh_counter" not in st.session_state:
    st.session_state.neraca_refresh_counter = 0

# === Fungsi format rupiah aman ===
def format_rupiah(x):
    try:
        x = float(x)
        if x < 0:
            return f"({abs(x):,.0f})".replace(",", ".")
        return f"{x:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return ""

# === Fungsi AgGrid ===
def create_aggrid(df, key_suffix, height=400):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=True)
    
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
    
    # Konversi kolom numerik ke float
    for col in df.columns:
        if "(Rp)" in col:
            grid_response["data"][col] = pd.to_numeric(grid_response["data"][col], errors="coerce").fillna(0)
    # Konversi tanggal aman
    if "Tanggal" in grid_response["data"]:
        grid_response["data"]["Tanggal"] = grid_response["data"]["Tanggal"].apply(lambda x: "" if pd.isna(x) else str(x))
    
    return pd.DataFrame(grid_response["data"])

# === Fungsi untuk membuat buku besar ===
def buat_buku_besar():
    df = st.session_state.data.copy()
    for col in ["Debit (Rp)", "Kredit (Rp)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    buku_besar = {}
    for _, row in df.iterrows():
        ref = str(row.get("Ref", "")).strip()
        nama_akun_jurnal = str(row.get("Akun", "")).strip()

        # Gunakan Ref sebagai kunci; jika kosong, fallback ke nama akun
        key = ref if ref else nama_akun_jurnal
        if not key:
            continue

        if key not in buku_besar:
            buku_besar[key] = {
                "nama_akun": nama_akun_jurnal if nama_akun_jurnal else f"Akun {key}",
                "debit": 0.0,
                "kredit": 0.0,
                "transaksi": []
            }

        debit_val = float(row.get("Debit (Rp)", 0) or 0)
        kredit_val = float(row.get("Kredit (Rp)", 0) or 0)
        tanggal = "" if pd.isna(row.get("Tanggal", "")) else str(row.get("Tanggal", ""))
        keterangan = str(row.get("Keterangan", "")).strip()

        if debit_val > 0:
            buku_besar[key]["transaksi"].append({"tanggal": tanggal, "keterangan": keterangan, "debit": debit_val, "kredit": 0.0})
            buku_besar[key]["debit"] += debit_val
        if kredit_val > 0:
            buku_besar[key]["transaksi"].append({"tanggal": tanggal, "keterangan": keterangan, "debit": 0.0, "kredit": kredit_val})
            buku_besar[key]["kredit"] += kredit_val

    # Update nama akun dari Neraca Saldo (pakai kolom benar: Ref & Akun)
    ns = st.session_state.get("neraca_saldo", pd.DataFrame())
    if not ns.empty:
        for _, row in ns.iterrows():
            ref_ns = str(row.get("Ref", "")).strip()
            nama_ns = str(row.get("Akun", "")).strip()
            if ref_ns and ref_ns in buku_besar and nama_ns:
                buku_besar[ref_ns]["nama_akun"] = nama_ns

    return buku_besar

import json

def _signature_buku_besar(bb: dict) -> str:
    # Buat tanda tangan sederhana untuk deteksi perubahan
    items = []
    for ref, data in (bb or {}).items():
        items.append({
            "ref": str(ref),
            "nama": data.get("nama_akun", ""),
            "debit": round(float(data.get("debit", 0) or 0), 2),
            "kredit": round(float(data.get("kredit", 0) or 0), 2),
        })
    items.sort(key=lambda x: x["ref"])
    return json.dumps(items, sort_keys=True)

def sync_neraca_from_bukubesar(non_destructive: bool = True):
    bb = st.session_state.get("buku_besar", {})
    if not bb:
        return

    ns = st.session_state.get("neraca_saldo")
    if ns is None or ns.empty:
        ns = pd.DataFrame(columns=["Ref", "Akun", "Debit (Rp)", "Kredit (Rp)"])

    # Normalisasi nilai
    ns["Ref"] = ns["Ref"].astype(str).str.strip()
    ns["Akun"] = ns["Akun"].astype(str).str.strip()
    ns["Debit (Rp)"] = pd.to_numeric(ns.get("Debit (Rp)", 0), errors="coerce").fillna(0)
    ns["Kredit (Rp)"] = pd.to_numeric(ns.get("Kredit (Rp)", 0), errors="coerce").fillna(0)

    ns_idx = {ns.loc[i, "Ref"]: i for i in ns.index if str(ns.loc[i, "Ref"]).strip() != ""}

    rows_to_add = []
    for ref, data in bb.items():
        ref_str = str(ref).strip()
        nama = data.get("nama_akun", f"Akun {ref_str}")
        debit = float(data.get("debit", 0) or 0)
        kredit = float(data.get("kredit", 0) or 0)
        net_debit = max(debit - kredit, 0)
        net_kredit = max(kredit - debit, 0)

        if ref_str in ns_idx:
            idx = ns_idx[ref_str]
            ns.at[idx, "Akun"] = nama or ns.at[idx, "Akun"]
            ns.at[idx, "Debit (Rp)"] = net_debit
            ns.at[idx, "Kredit (Rp)"] = net_kredit
        else:
            rows_to_add.append({
                "Ref": ref_str,
                "Akun": nama,
                "Debit (Rp)": net_debit,
                "Kredit (Rp)": net_kredit
            })

    if rows_to_add:
        ns = pd.concat([ns, pd.DataFrame(rows_to_add)], ignore_index=True)

    if not non_destructive:
        # Overwrite penuh: hapus baris yang Ref-nya tidak ada di Buku Besar
        refs_bb = set(str(k).strip() for k in bb.keys())
        ns = ns[ns["Ref"].astype(str).str.strip().isin(refs_bb)]

    st.session_state.neraca_saldo = ns.reset_index(drop=True)

from calendar import monthrange

def _parse_tanggal_series(s: pd.Series) -> pd.Series:
    # Robust parse: terima variasi format tanggal, kosong -> NaT
    return pd.to_datetime(s.astype(str).str.strip().replace({"": None, "nan": None}), errors="coerce", dayfirst=True)

def buat_buku_besar_periode(bulan: str, tahun: int) -> dict:
    """
    Bangun buku besar hanya untuk transaksi pada bulan/tahun terpilih.
    Kunci tetap pakai Ref (fallback ke nama_akun jika Ref kosong).
    """
    df = st.session_state.data.copy()

    # Parse tanggal dan filter periode
    df["__tgl"] = _parse_tanggal_series(df.get("Tanggal", pd.Series(dtype=str)))
    bln = int(bulan)
    thn = int(tahun)
    start = pd.Timestamp(thn, bln, 1)
    end = pd.Timestamp(thn, bln, monthrange(thn, bln)[1])  # hari terakhir bulan
    df = df[(df["__tgl"].notna()) & (df["__tgl"] >= start) & (df["__tgl"] <= end)]

    # Normalisasi angka
    for col in ["Debit (Rp)", "Kredit (Rp)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    buku_besar = {}
    for _, row in df.iterrows():
        ref = str(row.get("Ref", "")).strip()
        nama_akun_jurnal = str(row.get("Akun", "")).strip()
        key = ref if ref else nama_akun_jurnal
        if not key:
            continue

        if key not in buku_besar:
            buku_besar[key] = {
                "nama_akun": nama_akun_jurnal if nama_akun_jurnal else f"Akun {key}",
                "debit": 0.0,
                "kredit": 0.0,
                "transaksi": []
            }

        debit_val = float(row.get("Debit (Rp)", 0) or 0)
        kredit_val = float(row.get("Kredit (Rp)", 0) or 0)
        tanggal = "" if pd.isna(row.get("__tgl", "")) else str(row.get("__tgl", "").date())
        keterangan = str(row.get("Keterangan", "")).strip()

        if debit_val > 0:
            buku_besar[key]["transaksi"].append({"tanggal": tanggal, "keterangan": keterangan, "debit": debit_val, "kredit": 0.0})
            buku_besar[key]["debit"] += debit_val
        if kredit_val > 0:
            buku_besar[key]["transaksi"].append({"tanggal": tanggal, "keterangan": keterangan, "debit": 0.0, "kredit": kredit_val})
            buku_besar[key]["kredit"] += kredit_val

    return buku_besar

def sync_neraca_from_bb(bb: dict, non_destructive: bool = True):
    """
    Sinkronkan Neraca Saldo dari buku besar yang diberikan (bb),
    bukan dari st.session_state.buku_besar global. Aman untuk sinkron per-periode.
    """
    if not bb:
        return

    ns = st.session_state.get("neraca_saldo")
    if ns is None or ns.empty:
        ns = pd.DataFrame(columns=["Ref", "Akun", "Debit (Rp)", "Kredit (Rp)"])

    ns["Ref"] = ns["Ref"].astype(str).str.strip()
    ns["Akun"] = ns["Akun"].astype(str).str.strip()
    ns["Debit (Rp)"] = pd.to_numeric(ns.get("Debit (Rp)", 0), errors="coerce").fillna(0.0)
    ns["Kredit (Rp)"] = pd.to_numeric(ns.get("Kredit (Rp)", 0), errors="coerce").fillna(0.0)

    idx_by_ref = {ns.loc[i, "Ref"]: i for i in ns.index if ns.loc[i, "Ref"]}

    to_add = []
    for ref, data in bb.items():
        ref_str = str(ref).strip()
        nama = data.get("nama_akun", f"Akun {ref_str}")
        debit = float(data.get("debit", 0) or 0)
        kredit = float(data.get("kredit", 0) or 0)
        net_debit = max(debit - kredit, 0)
        net_kredit = max(kredit - debit, 0)

        if ref_str in idx_by_ref:
            idx = idx_by_ref[ref_str]
            ns.at[idx, "Akun"] = nama or ns.at[idx, "Akun"]
            ns.at[idx, "Debit (Rp)"] = net_debit
            ns.at[idx, "Kredit (Rp)"] = net_kredit
        else:
            to_add.append({"Ref": ref_str, "Akun": nama, "Debit (Rp)": net_debit, "Kredit (Rp)": net_kredit})

    if to_add:
        ns = pd.concat([ns, pd.DataFrame(to_add)], ignore_index=True)

    if not non_destructive:
        refs_bb = set(str(k).strip() for k in bb.keys())
        ns = ns[ns["Ref"].astype(str).str.strip().isin(refs_bb)]

    st.session_state.neraca_saldo = ns.reset_index(drop=True)


# === Styling AgGrid ===
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
tab1, tab2, tab3, tab4 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar", "💵 Neraca Saldo", "📊 Laporan Keuangan"])

# ========================================
# TAB 1: JURNAL UMUM
# ========================================
with tab1:
    st.header("🧾 Jurnal Umum")
    st.info("💡 Tekan Enter sekali untuk menyimpan perubahan otomatis.")

    if "grid_key" not in st.session_state:
        st.session_state.grid_key = 0

    # --- Input bulan dan tahun ---
    col1, col2 = st.columns(2)
    with col1:
        bulan_selected = st.selectbox(
            "Pilih Bulan", 
            options=[("01", "Januari"), ("02", "Februari"), ("03", "Maret"),
                     ("04", "April"), ("05", "Mei"), ("06", "Juni"),
                     ("07", "Juli"), ("08", "Agustus"), ("09", "September"),
                     ("10", "Oktober"), ("11", "November"), ("12", "Desember")],
            format_func=lambda x: x[1]
        )[0]
    with col2:
        tahun_selected = st.number_input("Tahun", min_value=2000, max_value=2100, value=pd.Timestamp.now().year, step=1)

    st.session_state['bulan'] = bulan_selected
    st.session_state['tahun'] = tahun_selected

    
    # Fungsi untuk menambah baris
    def add_journal_row():
        new_row = pd.DataFrame({
            "Tanggal": [""], 
            "Keterangan": [""], 
            "Ref": [""],
            "Akun": [""], 
            "Debit (Rp)": [0], 
            "Kredit (Rp)": [0]
        })
        # Simpan data yang ada dulu dari AgGrid
        #if 'grid_response' in st.session_state:
            #st.session_state.data = st.session_state.grid_response['data']
        # Tambah baris baru
        st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
        st.session_state.grid_key += 1
    
    # Tombol tambah baris
    st.button("➕ Tambah Baris Jurnal", key="tambah_jurnal", on_click=add_journal_row)
    
    # Setup AgGrid
    gb = GridOptionsBuilder.from_dataframe(st.session_state.data)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=True)
    
    for col in st.session_state.data.columns:
        if "(Rp)" in col:
            gb.configure_column(col, type=["numericColumn"], valueFormatter="value ? value.toLocaleString() : ''")
    
    grid_options = gb.build()
    
    # Render AgGrid
    grid_response = AgGrid(
        st.session_state.data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=320,
        key=f"jurnal_grid_{st.session_state.grid_key}",
        reload_data=True
    )
    
    # Simpan data dari grid ke session state
    st.session_state.data = grid_response['data']
    
    # Tampilkan data yang sudah difilter
    df_clean = st.session_state.data[st.session_state.data["Keterangan"].astype(str).str.strip() != ""]
    
    if not df_clean.empty:
        total_debit = df_clean["Debit (Rp)"].sum()
        total_kredit = df_clean["Kredit (Rp)"].sum()
        total_row = pd.DataFrame({
            "Tanggal": [""],
            "Keterangan": ["TOTAL"],
            "Ref": [""],
            "Akun": [""],
            "Debit (Rp)": [total_debit],
            "Kredit (Rp)": [total_kredit],
        })
        df_final = pd.concat([df_clean, total_row], ignore_index=True)

        st.write("### 📊 Hasil Jurnal")
        df_final_display = df_final.copy()
        df_final_display.index = range(1, len(df_final_display)+1)
        df_final_display.index.name = "No"
        st.dataframe(df_final_display.style.format({
            "Debit (Rp)": format_rupiah,
            "Kredit (Rp)": format_rupiah
        }))

        # --- PDF ---
        def buat_pdf(df, bulan, tahun):
            import calendar
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            bulan_dict = {
                1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei",
                6: "Juni", 7: "Juli", 8: "Agustus", 9: "September",
                10: "Oktober", 11: "November", 12: "Desember"
            }
            try:
                bulan_nama = bulan_dict.get(int(bulan), calendar.month_name[int(bulan)])
            except:
                bulan_nama = "Unknown"
            
            pdf.cell(200, 10, txt=f"Jurnal Umum BUMDes - {bulan_nama} {tahun}", ln=True, align="C")
            pdf.ln(8)
        
            col_width = 190 / len(df.columns)
            pdf.set_font("Arial", size=10, style="B")
            for col in df.columns:
                pdf.cell(col_width, 10, col, border=1, align="C")
            pdf.ln()
        
            pdf.set_font("Arial", size=9)
            for _, row in df.iterrows():
                for item in row:
                    if isinstance(item, (int, float)):
                        item = f"{item:,.0f}".replace(",", ".")
                    pdf.cell(col_width, 8, str(item), border=1, align="C")
                pdf.ln()
        
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                return tmp.read()
        
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

    # Perbarui buku besar penuh dari jurnal
    st.session_state.buku_besar = buat_buku_besar()
    # Ambil periode dari Tab 1 (yang sudah di-set ke session_state)
    bulan_bukubesar = st.session_state.get('bulan')
    tahun_bukubesar = st.session_state.get('tahun')
    if not bulan_bukubesar or not tahun_bukubesar:
        st.warning("Periode belum dipilih di Tab 1.")
    else:
        # Hanya TAMPILKAN periode yang dipilih di Tab 1
        bulan_dict = {
            "01": "Januari", "02": "Februari", "03": "Maret",
            "04": "April",   "05": "Mei",      "06": "Juni",
            "07": "Juli",    "08": "Agustus",  "09": "September",
            "10": "Oktober", "11": "November", "12": "Desember"
        }
        st.subheader(f"Periode: {bulan_dict[bulan_bukubesar]} {tahun_bukubesar}")
        # Ambil buku besar TERFILTER periode
        bb_periode = buat_buku_besar_periode(bulan_bukubesar, tahun_bukubesar)

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


        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Debit", format_rupiah(akun_data["debit"]))
        with col2:
            st.metric("Total Kredit", format_rupiah(akun_data["kredit"]))

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
            
#if "neraca_saldo" not in st.session_state:
#       st.session_state.neraca_saldo = pd.DataFrame([
#       {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
#    ])
# sync_neraca_from_bukubesar(non_destructive=True)
# ========================================
# TAB 3: NERACA SALDO (REVISI LENGKAP)
# ========================================
with tab3:
    st.header("💵 Neraca Saldo BUMDes")
    # Ambil periode dari Tab 1
    bulan_neraca = st.session_state.get('bulan')
    tahun_neraca = st.session_state.get('tahun')

    if not bulan_neraca or not tahun_neraca:
        st.warning("Periode belum dipilih di Tab 1.")
    else:
        bulan_dict = {
            "01": "Januari", "02": "Februari", "03": "Maret",
            "04": "April",   "05": "Mei",      "06": "Juni",
            "07": "Juli",    "08": "Agustus",  "09": "September",
            "10": "Oktober", "11": "November", "12": "Desember"
        }
        st.subheader(f"Periode: {bulan_dict[bulan_neraca]} {tahun_neraca}")

        # Ambil buku besar TERFILTER periode
        bb_periode = buat_buku_besar_periode(bulan_neraca, tahun_neraca)

        # Jika Buku Besar kosong → tampilkan info dan jangan lanjut
        if not bb_periode:
            st.info("ℹ️ Belum ada data untuk Neraca Saldo pada periode ini. Silakan isi Jurnal Umum terlebih dahulu.")
        else:
            # HANYA JALAN SAAT bb_periode ADA
            sync_neraca_from_bb(bb_periode, non_destructive=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("➕ Tambah 1 Baris", key="tambah_neraca_1", use_container_width=True):
                    new_row = pd.DataFrame([{"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                    st.session_state.neraca_saldo = pd.concat([st.session_state.neraca_saldo, new_row], ignore_index=True)
                    st.session_state.neraca_refresh_counter += 1
                    st.rerun()

            with col2:
                if st.button("➕➕ Tambah 5 Baris", key="tambah_neraca_5", use_container_width=True):
                    new_rows = pd.DataFrame([
                        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0},
                        {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
                    ])
                    st.session_state.neraca_saldo = pd.concat([st.session_state.neraca_saldo, new_rows], ignore_index=True)
                    st.session_state.neraca_refresh_counter += 1
                    st.rerun()

            with col3:
                if st.button("🗑️ Hapus Kosong", key="hapus_neraca_kosong", use_container_width=True):
                    st.session_state.neraca_saldo = st.session_state.neraca_saldo[
                        st.session_state.neraca_saldo["Akun"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.neraca_saldo) == 0:
                        st.session_state.neraca_saldo = pd.DataFrame([
                            {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
                        ])
                    st.session_state.neraca_refresh_counter += 1
                    st.rerun()

            # Normalisasi aman untuk st.session_state.neraca_saldo
            ns = st.session_state.get("neraca_saldo")
            if not isinstance(ns, pd.DataFrame):
                st.warning("Session state neraca_saldo bukan DataFrame — memperbaiki otomatis.")
                ns = pd.DataFrame([{"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])

            rename_map = {}
            for col in ns.columns:
                col_clean = col.lower().replace(" ", "").replace(".", "")
                if col_clean in ["ref"]:
                    rename_map[col] = "Ref"
                elif col_clean in ["akun", "account", "namaakun"]:
                    rename_map[col] = "Akun"
                elif col_clean in ["debit(rp)", "debitrp", "debit"]:
                    rename_map[col] = "Debit (Rp)"
                elif col_clean in ["kredit(rp)", "kreditrp", "kredit"]:
                    rename_map[col] = "Kredit (Rp)"
            ns = ns.rename(columns=rename_map)

            required_cols = ["Ref", "Akun", "Debit (Rp)", "Kredit (Rp)"]
            for c in required_cols:
                if c not in ns.columns:
                    ns[c] = "" if c in ["Ref", "Akun"] else 0

            ns["Debit (Rp)"] = pd.to_numeric(ns["Debit (Rp)"], errors="coerce").fillna(0)
            ns["Kredit (Rp)"] = pd.to_numeric(ns["Kredit (Rp)"], errors="coerce").fillna(0)

            st.session_state.neraca_saldo = ns.reset_index(drop=True)

            # --- Sistem Penghapusan dengan Checkbox ---
            df_terisi = st.session_state.neraca_saldo[
                st.session_state.neraca_saldo["Akun"].astype(str).str.strip() != ""
            ]
            if len(df_terisi) > 0:
                with st.expander("🗑️ Hapus Baris Tertentu", expanded=False):
                    st.write("**Pilih baris yang ingin dihapus:**")
                    rows_to_delete = []
                    for idx in df_terisi.index:
                        row = df_terisi.loc[idx]
                        col_check, col_info = st.columns([1, 9])
                        with col_check:
                            if st.checkbox("", key=f"check_del_{idx}_{st.session_state.neraca_refresh_counter}"):
                                rows_to_delete.append(idx)
                        with col_info:
                            st.text(f"Ref: {row['Ref']} | {row['Akun']} | Debit: {format_rupiah(row['Debit (Rp)'])} | Kredit: {format_rupiah(row['Kredit (Rp)'])}")
                    if rows_to_delete:
                        if st.button(f"🗑️ Hapus {len(rows_to_delete)} Baris", key=f"confirm_delete_{st.session_state.neraca_refresh_counter}", use_container_width=True):
                            st.session_state.neraca_saldo = st.session_state.neraca_saldo.drop(rows_to_delete).reset_index(drop=True)
                            if len(st.session_state.neraca_saldo) == 0:
                                st.session_state.neraca_saldo = pd.DataFrame([
                                    {"Ref": "", "Akun": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}
                                ])
                            st.session_state.neraca_refresh_counter += 1
                            st.success("✅ Baris berhasil dihapus!")
                            st.rerun()

            st.markdown("---")

            # --- AgGrid dengan Dropdown Akun dari Buku Besar (PER PERIODE) ---
            aggrid_key = f"neraca_{st.session_state.neraca_refresh_counter}"

            daftar_akun_values = sorted({
                v["nama_akun"] for v in bb_periode.values()
                if isinstance(v, dict) and "nama_akun" in v
            })

            gb = GridOptionsBuilder.from_dataframe(st.session_state.neraca_saldo)
            gb.configure_default_column(editable=True, resizable=True)
            gb.configure_grid_options(stopEditingWhenCellsLoseFocus=False)

            if daftar_akun_values:
                gb.configure_column(
                    "Akun",
                    editable=True,
                    cellEditor="agSelectCellEditor",
                    cellEditorParams={"values": daftar_akun_values}
                )

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

            # Filter data valid
            df_neraca_clean = st.session_state.neraca_saldo[
                st.session_state.neraca_saldo["Akun"].astype(str).str.strip() != ""
            ]

            if not df_neraca_clean.empty:
                total_debit = df_neraca_clean["Debit (Rp)"].sum()
                total_kredit = df_neraca_clean["Kredit (Rp)"].sum()

                total_row = pd.DataFrame({
                    "Ref": [""],
                    "Akun": ["Jumlah"],
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
                # PDF Export
                def buat_pdf_neraca(df, bulan, tahun):
                    pdf = FPDF()
                    pdf.add_page()
                    
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, txt="Neraca Saldo BUMDes", ln=True, align="C")
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(0, 8, txt=f"Periode: {bulan_dict[bulan]} {tahun}", ln=True, align="C")
                    pdf.ln(5)
        
                    pdf.set_font("Arial", 'B', 10)
                    col_widths = [15, 25, 70, 40, 40]
                    headers = ["No", "Ref", "Akun", "Debit (Rp)", "Kredit (Rp)"]
                    
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 10, header, border=1, align="C")
                    pdf.ln()
        
                    pdf.set_font("Arial", '', 9)
                    for idx, row in df.iterrows():
                        pdf.cell(col_widths[0], 8, str(idx), border=1, align="C")
                        pdf.cell(col_widths[1], 8, str(row["Ref"]), border=1, align="C")
                        
                        akun = str(row["Akun"])
                        if len(akun) > 35:
                            akun = akun[:32] + "..."
                        pdf.cell(col_widths[2], 8, akun, border=1, align="L")
                        
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
        
                pdf_neraca = buat_pdf_neraca(df_neraca_final, bulan_neraca, tahun_neraca)
                st.download_button(
                    "📥 Download PDF Neraca Saldo",
                    data=pdf_neraca,
                    file_name=f"neraca_saldo_{bulan_neraca}_{tahun_neraca}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Belum ada data valid di tabel Neraca Saldo.")
# ========================================
# TAB 4: LAPORAN KEUANGAN
# ========================================
with tab4:
    st.header("📊 Laporan Keuangan BUMDes")
    
    # --- Selector Periode ---
    col1, col2 = st.columns(2)
    
    bulan_dict = {
        "01": "Januari", "02": "Februari", "03": "Maret",
        "04": "April", "05": "Mei", "06": "Juni",
        "07": "Juli", "08": "Agustus", "09": "September",
        "10": "Oktober", "11": "November", "12": "Desember"
    }
    
    with col1:
        bulan_laporan = st.selectbox(
            "Pilih Bulan", 
            options=[
                ("01", "Januari"), ("02", "Februari"), ("03", "Maret"),
                ("04", "April"), ("05", "Mei"), ("06", "Juni"),
                ("07", "Juli"), ("08", "Agustus"), ("09", "September"),
                ("10", "Oktober"), ("11", "November"), ("12", "Desember")
            ],
            format_func=lambda x: x[1],
            key="bulan_laporan"
        )[0]
    
    with col2:
        tahun_laporan = st.number_input(
            "Tahun", 
            min_value=2000, 
            max_value=2100, 
            value=2025,
            step=1,
            key="tahun_laporan"
        )
    
    st.subheader(f"Periode: {bulan_dict[bulan_laporan]} {tahun_laporan}")
    
    #st.info("💡 Data otomatis diambil dari Neraca Saldo, namun Anda tetap bisa mengedit manual di tabel yang tersedia.")

    # Counter refresh
    if "laporan_refresh" not in st.session_state:
        st.session_state.laporan_refresh = 0
    
    # Inisialisasi laba_bersih di session_state
    if "laba_bersih" not in st.session_state:
        st.session_state.laba_bersih = 0

    # ========================================
    # AUTO-LOAD DARI NERACA SALDO (SEKALI SAJA)
    # ========================================
    if "pendapatan_loaded" not in st.session_state:
        st.session_state.pendapatan_loaded = False
    
    if not st.session_state.pendapatan_loaded:
        df_neraca = st.session_state.neraca_saldo[
            st.session_state.neraca_saldo["Akun"].astype(str).str.strip() != ""
        ]
        
        # Clear data lama
        st.session_state.pendapatan = pd.DataFrame([{"Jenis Pendapatan": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
        st.session_state.beban = pd.DataFrame([{"Jenis Beban": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
        st.session_state.aktiva_lancar = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
        st.session_state.aktiva_tetap = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
        st.session_state.kewajiban = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
        st.session_state.modal_data = {"modal_awal": 0}
        
        # Auto-populate dari Neraca Saldo
        for _, row in df_neraca.iterrows():
            nama_akun = str(row["Akun"]).lower()
            debit = row["Debit (Rp)"] if pd.notna(row["Debit (Rp)"]) else 0
            kredit = row["Kredit (Rp)"] if pd.notna(row["Kredit (Rp)"]) else 0
            
            if "pendapatan" in nama_akun or "penjualan" in nama_akun:
                new_row = pd.DataFrame([{"Jenis Pendapatan": row["Akun"], "Debit (Rp)": 0, "Kredit (Rp)": kredit}])
                st.session_state.pendapatan = pd.concat([st.session_state.pendapatan, new_row], ignore_index=True)
            
            elif "beban" in nama_akun or "biaya" in nama_akun:
                new_row = pd.DataFrame([{"Jenis Beban": row["Akun"], "Debit (Rp)": debit, "Kredit (Rp)": 0}])
                st.session_state.beban = pd.concat([st.session_state.beban, new_row], ignore_index=True)
            
            elif "kas" in nama_akun or "perlengkapan" in nama_akun or "piutang" in nama_akun:
                new_row = pd.DataFrame([{"Item": row["Akun"], "Jumlah (Rp)": debit}])
                st.session_state.aktiva_lancar = pd.concat([st.session_state.aktiva_lancar, new_row], ignore_index=True)
            
            elif "peralatan" in nama_akun or "gedung" in nama_akun or "kendaraan" in nama_akun:
                new_row = pd.DataFrame([{"Item": row["Akun"], "Jumlah (Rp)": debit}])
                st.session_state.aktiva_tetap = pd.concat([st.session_state.aktiva_tetap, new_row], ignore_index=True)
            
            elif "modal" in nama_akun:
                st.session_state.modal_data["modal_awal"] = kredit
            
            elif "hutang" in nama_akun or "utang" in nama_akun:
                new_row = pd.DataFrame([{"Item": row["Akun"], "Jumlah (Rp)": kredit}])
                st.session_state.kewajiban = pd.concat([st.session_state.kewajiban, new_row], ignore_index=True)
        
        st.session_state.pendapatan_loaded = True

    # === SUB-TABS ===
    subtab1, subtab2, subtab3 = st.tabs([
        "📈 Laba/Rugi",
        "🏦 Neraca", 
        "💸 Arus Kas"
    ])
    
    # ========================================
    # SUB-TAB 1: LAPORAN LABA/RUGI
    # ========================================
    with subtab1:
        st.markdown("### 📈 Laporan Laba/Rugi")
        st.markdown(f"**BUMDes - {bulan_dict[bulan_laporan]} {tahun_laporan}**")
        st.markdown("---")
        
        # Tombol reload
        if st.button("🔄 Reload dari Neraca Saldo", key="reload_labarugi"):
            st.session_state.pendapatan_loaded = False
            st.session_state.laporan_refresh += 1
            st.rerun()
        
        # Input Hybrid
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Input Pendapatan (Kredit):")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="tambah_pendapatan", use_container_width=True):
                    new_row = pd.DataFrame([{"Jenis Pendapatan": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                    st.session_state.pendapatan = pd.concat([st.session_state.pendapatan, new_row], ignore_index=True)
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="hapus_pendapatan_kosong", use_container_width=True):
                    st.session_state.pendapatan = st.session_state.pendapatan[
                        st.session_state.pendapatan["Jenis Pendapatan"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.pendapatan) == 0:
                        st.session_state.pendapatan = pd.DataFrame([{"Jenis Pendapatan": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            new_pendapatan = create_aggrid(st.session_state.pendapatan, f"pendapatan_{st.session_state.laporan_refresh}", height=250)
            if not new_pendapatan.equals(st.session_state.pendapatan):
                st.session_state.pendapatan = new_pendapatan.copy()
            
            # Hapus Tertentu
            df_pend_terisi = st.session_state.pendapatan[
                st.session_state.pendapatan["Jenis Pendapatan"].astype(str).str.strip() != ""
            ]
            
            if len(df_pend_terisi) > 0:
                with st.expander("🗑️ Hapus Pendapatan Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_pend_terisi.index:
                        row = df_pend_terisi.loc[idx]
                        col_chk, col_txt = st.columns([1, 9])
                        with col_chk:
                            if st.checkbox("", key=f"chk_p_{idx}_{st.session_state.laporan_refresh}"):
                                rows_del.append(idx)
                        with col_txt:
                            st.text(f"{row['Jenis Pendapatan']}: D: {format_rupiah(row['Debit (Rp)'])} | K: {format_rupiah(row['Kredit (Rp)'])}")
                    
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_pend"):
                        st.session_state.pendapatan = st.session_state.pendapatan.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.pendapatan) == 0:
                            st.session_state.pendapatan = pd.DataFrame([{"Jenis Pendapatan": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                        st.session_state.laporan_refresh += 1
                        st.rerun()

        with col2:
            st.write("#### Input Beban-Beban (Debit):")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="tambah_beban", use_container_width=True):
                    new_row = pd.DataFrame([{"Jenis Beban": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                    st.session_state.beban = pd.concat([st.session_state.beban, new_row], ignore_index=True)
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="hapus_beban_kosong", use_container_width=True):
                    st.session_state.beban = st.session_state.beban[
                        st.session_state.beban["Jenis Beban"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.beban) == 0:
                        st.session_state.beban = pd.DataFrame([{"Jenis Beban": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            new_beban = create_aggrid(st.session_state.beban, f"beban_{st.session_state.laporan_refresh}", height=250)
            if not new_beban.equals(st.session_state.beban):
                st.session_state.beban = new_beban.copy()
            
            # Hapus Tertentu
            df_beban_terisi = st.session_state.beban[
                st.session_state.beban["Jenis Beban"].astype(str).str.strip() != ""
            ]
            
            if len(df_beban_terisi) > 0:
                with st.expander("🗑️ Hapus Beban Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_beban_terisi.index:
                        row = df_beban_terisi.loc[idx]
                        col_chk, col_txt = st.columns([1, 9])
                        with col_chk:
                            if st.checkbox("", key=f"chk_b_{idx}_{st.session_state.laporan_refresh}"):
                                rows_del.append(idx)
                        with col_txt:
                            st.text(f"{row['Jenis Beban']}: D: {format_rupiah(row['Debit (Rp)'])} | K: {format_rupiah(row['Kredit (Rp)'])}")
                    
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_beban"):
                        st.session_state.beban = st.session_state.beban.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.beban) == 0:
                            st.session_state.beban = pd.DataFrame([{"Jenis Beban": "", "Debit (Rp)": 0, "Kredit (Rp)": 0}])
                        st.session_state.laporan_refresh += 1
                        st.rerun()

        st.markdown("---")

        # Hitung dan SIMPAN laba_bersih di session_state
        df_pendapatan_clean = new_pendapatan[new_pendapatan["Jenis Pendapatan"].astype(str).str.strip() != ""]
        df_beban_clean = new_beban[new_beban["Jenis Beban"].astype(str).str.strip() != ""]

        # Pendapatan = Kredit, Beban = Debit
        total_pendapatan = df_pendapatan_clean["Kredit (Rp)"].sum() if not df_pendapatan_clean.empty else 0
        total_beban = df_beban_clean["Debit (Rp)"].sum() if not df_beban_clean.empty else 0
        
        # SIMPAN di session_state agar bisa diakses sub-tab lain!
        st.session_state.laba_bersih = total_pendapatan - total_beban

        if not df_pendapatan_clean.empty or not df_beban_clean.empty:
            st.write("### 📊 Hasil Laporan Laba/Rugi")
            
            result_data = []
            result_data.append({"Keterangan": "Pendapatan:", "Debit": "", "Kredit": ""})
            
            for idx, row in df_pendapatan_clean.iterrows():
                result_data.append({
                    "Keterangan": f"  {idx+1}. {row['Jenis Pendapatan']}", 
                    "Debit": row["Debit (Rp)"] if row["Debit (Rp)"] != 0 else "",
                    "Kredit": row["Kredit (Rp)"]
                })
            
            result_data.append({"Keterangan": "", "Debit": "", "Kredit": ""})
            result_data.append({"Keterangan": "Total Pendapatan", "Debit": "", "Kredit": total_pendapatan})
            result_data.append({"Keterangan": "", "Debit": "", "Kredit": ""})
            result_data.append({"Keterangan": "Beban-Beban:", "Debit": "", "Kredit": ""})
            
            for idx, row in df_beban_clean.iterrows():
                result_data.append({
                    "Keterangan": f"  {idx+1}. {row['Jenis Beban']}", 
                    "Debit": row["Debit (Rp)"],
                    "Kredit": row["Kredit (Rp)"] if row["Kredit (Rp)"] != 0 else ""
                })
            
            result_data.append({"Keterangan": "", "Debit": "", "Kredit": ""})
            result_data.append({"Keterangan": "Total Beban", "Debit": total_beban, "Kredit": ""})
            result_data.append({"Keterangan": "", "Debit": "", "Kredit": ""})
            
            # Laba Bersih = Kredit - Debit
            if st.session_state.laba_bersih >= 0:
                result_data.append({"Keterangan": "Laba Bersih", "Debit": "", "Kredit": st.session_state.laba_bersih})
            else:
                result_data.append({"Keterangan": "Rugi Bersih", "Debit": abs(st.session_state.laba_bersih), "Kredit": ""})

            df_labarugi = pd.DataFrame(result_data)
            
            st.dataframe(
                df_labarugi.style.format({
                    "Debit": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x,
                    "Kredit": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x
                })
                .apply(lambda x: ['font-weight: bold' if i < len(df_labarugi) and ('Total' in str(df_labarugi.iloc[i]['Keterangan']) or 'Laba' in str(df_labarugi.iloc[i]['Keterangan']) or 'Rugi' in str(df_labarugi.iloc[i]['Keterangan'])) else '' for i in range(len(x))], axis=0)
                .set_properties(**{'text-align': 'left'}, subset=['Keterangan'])
                .set_properties(**{'text-align': 'right'}, subset=['Debit', 'Kredit']),
                use_container_width=True,
                hide_index=True
            )
            
            # PDF Export
            def buat_pdf_labarugi(df, bulan, tahun):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, txt="Laporan Laba/Rugi", ln=True, align="C")
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 8, txt="BUMDes", ln=True, align="C")
                pdf.cell(0, 8, txt=f"Periode: {bulan_dict[bulan]} {tahun}", ln=True, align="C")
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(90, 10, "Keterangan", border=1, align="C")
                pdf.cell(45, 10, "Debit (Rp)", border=1, align="C")
                pdf.cell(45, 10, "Kredit (Rp)", border=1, align="C")
                pdf.ln()
                pdf.set_font("Arial", '', 9)
                for idx in range(len(df)):
                    row = df.iloc[idx]
                    is_bold = 'Total' in str(row['Keterangan']) or 'Laba' in str(row['Keterangan']) or 'Rugi' in str(row['Keterangan'])
                    if is_bold:
                        pdf.set_font("Arial", 'B', 9)
                    ket = str(row["Keterangan"])[:40] + "..." if len(str(row["Keterangan"])) > 43 else str(row["Keterangan"])
                    pdf.cell(90, 8, ket, border=1, align="L")
                    debit_text = format_rupiah(row["Debit"]) if isinstance(row["Debit"], (int, float)) else ""
                    pdf.cell(45, 8, debit_text, border=1, align="R")
                    kredit_text = format_rupiah(row["Kredit"]) if isinstance(row["Kredit"], (int, float)) else ""
                    pdf.cell(45, 8, kredit_text, border=1, align="R")
                    pdf.ln()
                    if is_bold:
                        pdf.set_font("Arial", '', 9)
                pdf.ln(5)
                pdf.set_font("Arial", 'I', 8)
                pdf.cell(0, 5, txt="Dicetak dari Sistem Akuntansi BUMDes", ln=True, align="C")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    pdf.output(tmp.name)
                    tmp.seek(0)
                    return tmp.read()

            pdf_labarugi = buat_pdf_labarugi(df_labarugi, bulan_laporan, tahun_laporan)
            st.download_button(
                "📥 Download PDF Laba/Rugi",
                data=pdf_labarugi,
                file_name=f"laporan_labarugi_{bulan_laporan}_{tahun_laporan}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    
    # ========================================
    # SUB-TAB 2: LAPORAN NERACA
    # ========================================
    with subtab2:
        st.markdown("### 🏦 Laporan Neraca")
        st.markdown(f"**BUMDes - {bulan_dict[bulan_laporan]} {tahun_laporan}**")
        st.markdown("---")
        
        # Tombol reload
        if st.button("🔄 Reload dari Neraca Saldo", key="reload_neraca"):
            st.session_state.pendapatan_loaded = False
            st.session_state.laporan_refresh += 1
            st.rerun()
        
        # Input Modal
        modal_awal = st.number_input(
            "Modal Awal (Rp)", 
            value=st.session_state.modal_data.get("modal_awal", 0), 
            step=100000,
            key="modal_awal_input"
        )
        st.session_state.modal_data["modal_awal"] = modal_awal
        
        st.markdown("---")
        
        # Input untuk Aktiva & Kewajiban
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Aktiva Lancar:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="tambah_aktiva_lancar", use_container_width=True):
                    new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.aktiva_lancar = pd.concat([st.session_state.aktiva_lancar, new_row], ignore_index=True)
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="hapus_lancar_kosong", use_container_width=True):
                    st.session_state.aktiva_lancar = st.session_state.aktiva_lancar[
                        st.session_state.aktiva_lancar["Item"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.aktiva_lancar) == 0:
                        st.session_state.aktiva_lancar = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            new_aktiva_lancar = create_aggrid(st.session_state.aktiva_lancar, f"lancar_{st.session_state.laporan_refresh}", height=180)
            if not new_aktiva_lancar.equals(st.session_state.aktiva_lancar):
                st.session_state.aktiva_lancar = new_aktiva_lancar.copy()
            
            # Hapus Tertentu Aktiva Lancar
            df_lancar_terisi = st.session_state.aktiva_lancar[
                st.session_state.aktiva_lancar["Item"].astype(str).str.strip() != ""
            ]
            if len(df_lancar_terisi) > 0:
                with st.expander("🗑️ Hapus Aktiva Lancar Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_lancar_terisi.index:
                        row = df_lancar_terisi.loc[idx]
                        col_chk, col_txt = st.columns([1, 9])
                        with col_chk:
                            if st.checkbox("", key=f"chk_al_{idx}_{st.session_state.laporan_refresh}"):
                                rows_del.append(idx)
                        with col_txt:
                            st.text(f"{row['Item']}: {format_rupiah(row['Jumlah (Rp)'])}")
                    
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_lancar"):
                        st.session_state.aktiva_lancar = st.session_state.aktiva_lancar.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.aktiva_lancar) == 0:
                            st.session_state.aktiva_lancar = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                        st.session_state.laporan_refresh += 1
                        st.rerun()

            st.write("#### Aktiva Tetap:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="tambah_aktiva_tetap", use_container_width=True):
                    new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.aktiva_tetap = pd.concat([st.session_state.aktiva_tetap, new_row], ignore_index=True)
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="hapus_tetap_kosong", use_container_width=True):
                    st.session_state.aktiva_tetap = st.session_state.aktiva_tetap[
                        st.session_state.aktiva_tetap["Item"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.aktiva_tetap) == 0:
                        st.session_state.aktiva_tetap = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            new_aktiva_tetap = create_aggrid(st.session_state.aktiva_tetap, f"tetap_{st.session_state.laporan_refresh}", height=180)
            if not new_aktiva_tetap.equals(st.session_state.aktiva_tetap):
                st.session_state.aktiva_tetap = new_aktiva_tetap.copy()
            
            # Hapus Tertentu Aktiva Tetap
            df_tetap_terisi = st.session_state.aktiva_tetap[
                st.session_state.aktiva_tetap["Item"].astype(str).str.strip() != ""
            ]
            if len(df_tetap_terisi) > 0:
                with st.expander("🗑️ Hapus Aktiva Tetap Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_tetap_terisi.index:
                        row = df_tetap_terisi.loc[idx]
                        col_chk, col_txt = st.columns([1, 9])
                        with col_chk:
                            if st.checkbox("", key=f"chk_at_{idx}_{st.session_state.laporan_refresh}"):
                                rows_del.append(idx)
                        with col_txt:
                            st.text(f"{row['Item']}: {format_rupiah(row['Jumlah (Rp)'])}")
                    
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_tetap"):
                        st.session_state.aktiva_tetap = st.session_state.aktiva_tetap.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.aktiva_tetap) == 0:
                            st.session_state.aktiva_tetap = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                        st.session_state.laporan_refresh += 1
                        st.rerun()

        with col2:
            st.write("#### Kewajiban:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="tambah_kewajiban", use_container_width=True):
                    new_row = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.kewajiban = pd.concat([st.session_state.kewajiban, new_row], ignore_index=True)
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="hapus_kewajiban_kosong", use_container_width=True):
                    st.session_state.kewajiban = st.session_state.kewajiban[
                        st.session_state.kewajiban["Item"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.kewajiban) == 0:
                        st.session_state.kewajiban = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                    st.session_state.laporan_refresh += 1
                    st.rerun()
            
            new_kewajiban = create_aggrid(st.session_state.kewajiban, f"kewajiban_{st.session_state.laporan_refresh}", height=180)
            if not new_kewajiban.equals(st.session_state.kewajiban):
                st.session_state.kewajiban = new_kewajiban.copy()
            
            # Hapus Tertentu Kewajiban
            df_kewajiban_terisi = st.session_state.kewajiban[
                st.session_state.kewajiban["Item"].astype(str).str.strip() != ""
            ]
            if len(df_kewajiban_terisi) > 0:
                with st.expander("🗑️ Hapus Kewajiban Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_kewajiban_terisi.index:
                        row = df_kewajiban_terisi.loc[idx]
                        col_chk, col_txt = st.columns([1, 9])
                        with col_chk:
                            if st.checkbox("", key=f"chk_k_{idx}_{st.session_state.laporan_refresh}"):
                                rows_del.append(idx)
                        with col_txt:
                            st.text(f"{row['Item']}: {format_rupiah(row['Jumlah (Rp)'])}")
                    
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_kewajiban"):
                        st.session_state.kewajiban = st.session_state.kewajiban.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.kewajiban) == 0:
                            st.session_state.kewajiban = pd.DataFrame([{"Item": "", "Jumlah (Rp)": 0}])
                        st.session_state.laporan_refresh += 1
                        st.rerun()

        st.markdown("---")

        # Hitung totals
        df_aktiva_lancar_clean = new_aktiva_lancar[new_aktiva_lancar["Item"].astype(str).str.strip() != ""]
        df_aktiva_tetap_clean = new_aktiva_tetap[new_aktiva_tetap["Item"].astype(str).str.strip() != ""]
        df_kewajiban_clean = new_kewajiban[new_kewajiban["Item"].astype(str).str.strip() != ""]

        total_aktiva_lancar = df_aktiva_lancar_clean["Jumlah (Rp)"].sum() if not df_aktiva_lancar_clean.empty else 0
        total_aktiva_tetap = df_aktiva_tetap_clean["Jumlah (Rp)"].sum() if not df_aktiva_tetap_clean.empty else 0
        total_aktiva = total_aktiva_lancar + total_aktiva_tetap
        
        total_kewajiban = df_kewajiban_clean["Jumlah (Rp)"].sum() if not df_kewajiban_clean.empty else 0
        
        # GUNAKAN laba_bersih dari session_state
        modal_akhir = modal_awal + st.session_state.laba_bersih
        total_passiva = total_kewajiban + modal_akhir
        
        # Pastikan numeric
        total_aktiva = 0 if pd.isna(total_aktiva) else float(total_aktiva)
        total_passiva = 0 if pd.isna(total_passiva) else float(total_passiva)

        # Hasil Neraca
        st.write("### 📊 Hasil Laporan Neraca")
        
        neraca_data = []
        neraca_data.append({"Aktiva": "Aktiva", "Jumlah1": "", "Passiva": "Passiva", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Aktiva Lancar:", "Jumlah1": "", "Passiva": "Kewajiban:", "Jumlah2": ""})
        
        max_rows = max(len(df_aktiva_lancar_clean), len(df_kewajiban_clean)) if not df_aktiva_lancar_clean.empty or not df_kewajiban_clean.empty else 0
        for i in range(max_rows):
            aktiva_item = df_aktiva_lancar_clean.iloc[i]["Item"] if i < len(df_aktiva_lancar_clean) else ""
            aktiva_val = df_aktiva_lancar_clean.iloc[i]["Jumlah (Rp)"] if i < len(df_aktiva_lancar_clean) else ""
            kewajiban_item = df_kewajiban_clean.iloc[i]["Item"] if i < len(df_kewajiban_clean) else ""
            kewajiban_val = df_kewajiban_clean.iloc[i]["Jumlah (Rp)"] if i < len(df_kewajiban_clean) else ""
            
            neraca_data.append({
                "Aktiva": f"  {aktiva_item}",
                "Jumlah1": aktiva_val,
                "Passiva": f"  {kewajiban_item}",
                "Jumlah2": kewajiban_val
            })
        
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Jml aktiva lancar", "Jumlah1": total_aktiva_lancar, "Passiva": "Ekuitas:", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "  Modal", "Jumlah2": modal_awal})
        neraca_data.append({"Aktiva": "Aktiva Tetap:", "Jumlah1": "", "Passiva": "  Laba", "Jumlah2": st.session_state.laba_bersih})
        
        for idx, row in df_aktiva_tetap_clean.iterrows():
            neraca_data.append({
                "Aktiva": f"  {row['Item']}",
                "Jumlah1": row["Jumlah (Rp)"],
                "Passiva": "",
                "Jumlah2": ""
            })
        
        neraca_data.append({"Aktiva": "", "Jumlah1": "", "Passiva": "", "Jumlah2": ""})
        neraca_data.append({"Aktiva": "Jml Aktiva", "Jumlah1": total_aktiva, "Passiva": "Jml Kewajiban & Ekuitas", "Jumlah2": total_passiva})
        
        df_neraca_lap = pd.DataFrame(neraca_data)
        
        st.dataframe(
            df_neraca_lap.style.format({
                "Jumlah1": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x,
                "Jumlah2": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x
            })
            .apply(lambda x: ['font-weight: bold' if i < len(df_neraca_lap) and ('Jml' in str(df_neraca_lap.iloc[i].get('Aktiva', '')) or 'Jml' in str(df_neraca_lap.iloc[i].get('Passiva', ''))) else '' for i in range(len(x))], axis=0)
            .set_properties(**{'text-align': 'left'}, subset=['Aktiva', 'Passiva'])
            .set_properties(**{'text-align': 'right'}, subset=['Jumlah1', 'Jumlah2']),
            use_container_width=True,
            hide_index=True
        )
        
        # PDF Export
        def buat_pdf_neraca_lap(df, bulan, tahun):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, txt="Laporan Neraca", ln=True, align="C")
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 8, txt="BUMDes", ln=True, align="C")
            pdf.cell(0, 8, txt=f"Periode: {bulan_dict[bulan]} {tahun}", ln=True, align="C")
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            col_widths = [60, 30, 60, 30]
            for h in ["Aktiva", "Jumlah (Rp)", "Passiva", "Jumlah (Rp)"]:
                pdf.cell(col_widths[0] if h == "Aktiva" else (col_widths[2] if h == "Passiva" else col_widths[1]), 10, h, border=1, align="C")
            pdf.ln()
            pdf.set_font("Arial", '', 9)
            for idx in range(len(df)):
                row = df.iloc[idx]
                is_bold = 'Jml' in str(row.get('Aktiva', '')) or 'Jml' in str(row.get('Passiva', ''))
                if is_bold:
                    pdf.set_font("Arial", 'B', 9)
                pdf.cell(col_widths[0], 8, str(row["Aktiva"]), border=1, align="L")
                pdf.cell(col_widths[1], 8, format_rupiah(row["Jumlah1"]) if isinstance(row["Jumlah1"], (int, float)) else "", border=1, align="R")
                pdf.cell(col_widths[2], 8, str(row["Passiva"]), border=1, align="L")
                pdf.cell(col_widths[3], 8, format_rupiah(row["Jumlah2"]) if isinstance(row["Jumlah2"], (int, float)) else "", border=1, align="R")
                pdf.ln()
                if is_bold:
                    pdf.set_font("Arial", '', 9)
            pdf.ln(5)
            pdf.set_font("Arial", 'I', 8)
            pdf.cell(0, 5, txt="Dicetak dari Sistem Akuntansi BUMDes", ln=True, align="C")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                tmp.seek(0)
                return tmp.read()

        pdf_neraca = buat_pdf_neraca_lap(df_neraca_lap, bulan_laporan, tahun_laporan)
        st.download_button(
            "📥 Download PDF Neraca",
            data=pdf_neraca,
            file_name=f"laporan_neraca_{bulan_laporan}_{tahun_laporan}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    
    # ========================================
    # SUB-TAB 3: ARUS KAS
    # ========================================
    with subtab3:
        st.markdown("### 💸 Laporan Arus Kas")
        st.markdown(f"**BUMDes - {bulan_dict[bulan_laporan]} {tahun_laporan}**")
        st.markdown("---")
        
        st.info("💡 Input manual untuk aktivitas arus kas.")
        
        if "arus_kas_refresh" not in st.session_state:
            st.session_state.arus_kas_refresh = 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("#### Operasi:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="add_op", use_container_width=True):
                    st.session_state.arus_kas_operasi = pd.concat([st.session_state.arus_kas_operasi, pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])], ignore_index=True)
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="del_op_empty", use_container_width=True):
                    st.session_state.arus_kas_operasi = st.session_state.arus_kas_operasi[
                        st.session_state.arus_kas_operasi["Aktivitas"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.arus_kas_operasi) == 0:
                        st.session_state.arus_kas_operasi = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            
            new_arus_operasi = create_aggrid(st.session_state.arus_kas_operasi, f"op_{st.session_state.arus_kas_refresh}", height=200)
            if not new_arus_operasi.equals(st.session_state.arus_kas_operasi):
                st.session_state.arus_kas_operasi = new_arus_operasi.copy()
            
            # Hapus Tertentu Operasi
            df_op_terisi = st.session_state.arus_kas_operasi[
                st.session_state.arus_kas_operasi["Aktivitas"].astype(str).str.strip() != ""
            ]
            if len(df_op_terisi) > 0:
                with st.expander("🗑️ Hapus Item Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_op_terisi.index:
                        row = df_op_terisi.loc[idx]
                        if st.checkbox(f"{row['Aktivitas']}: {format_rupiah(row['Jumlah (Rp)'])}", key=f"chk_op_{idx}_{st.session_state.arus_kas_refresh}"):
                            rows_del.append(idx)
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_op"):
                        st.session_state.arus_kas_operasi = st.session_state.arus_kas_operasi.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.arus_kas_operasi) == 0:
                            st.session_state.arus_kas_operasi = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                        st.session_state.arus_kas_refresh += 1
                        st.rerun()

        with col2:
            st.write("#### Investasi:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="add_inv", use_container_width=True):
                    st.session_state.arus_kas_investasi = pd.concat([st.session_state.arus_kas_investasi, pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])], ignore_index=True)
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="del_inv_empty", use_container_width=True):
                    st.session_state.arus_kas_investasi = st.session_state.arus_kas_investasi[
                        st.session_state.arus_kas_investasi["Aktivitas"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.arus_kas_investasi) == 0:
                        st.session_state.arus_kas_investasi = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            
            new_arus_investasi = create_aggrid(st.session_state.arus_kas_investasi, f"inv_{st.session_state.arus_kas_refresh}", height=200)
            if not new_arus_investasi.equals(st.session_state.arus_kas_investasi):
                st.session_state.arus_kas_investasi = new_arus_investasi.copy()
            
            # Hapus Tertentu Investasi
            df_inv_terisi = st.session_state.arus_kas_investasi[
                st.session_state.arus_kas_investasi["Aktivitas"].astype(str).str.strip() != ""
            ]
            if len(df_inv_terisi) > 0:
                with st.expander("🗑️ Hapus Item Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_inv_terisi.index:
                        row = df_inv_terisi.loc[idx]
                        if st.checkbox(f"{row['Aktivitas']}: {format_rupiah(row['Jumlah (Rp)'])}", key=f"chk_inv_{idx}_{st.session_state.arus_kas_refresh}"):
                            rows_del.append(idx)
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_inv"):
                        st.session_state.arus_kas_investasi = st.session_state.arus_kas_investasi.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.arus_kas_investasi) == 0:
                            st.session_state.arus_kas_investasi = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                        st.session_state.arus_kas_refresh += 1
                        st.rerun()

        with col3:
            st.write("#### Pendanaan:")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ Tambah", key="add_pend", use_container_width=True):
                    st.session_state.arus_kas_pendanaan = pd.concat([st.session_state.arus_kas_pendanaan, pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])], ignore_index=True)
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ Hapus Kosong", key="del_pend_empty", use_container_width=True):
                    st.session_state.arus_kas_pendanaan = st.session_state.arus_kas_pendanaan[
                        st.session_state.arus_kas_pendanaan["Aktivitas"].astype(str).str.strip() != ""
                    ].reset_index(drop=True)
                    if len(st.session_state.arus_kas_pendanaan) == 0:
                        st.session_state.arus_kas_pendanaan = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                    st.session_state.arus_kas_refresh += 1
                    st.rerun()
            
            new_arus_pendanaan = create_aggrid(st.session_state.arus_kas_pendanaan, f"pend_{st.session_state.arus_kas_refresh}", height=200)
            if not new_arus_pendanaan.equals(st.session_state.arus_kas_pendanaan):
                st.session_state.arus_kas_pendanaan = new_arus_pendanaan.copy()
            
            # Hapus Tertentu Pendanaan
            df_pend_terisi = st.session_state.arus_kas_pendanaan[
                st.session_state.arus_kas_pendanaan["Aktivitas"].astype(str).str.strip() != ""
            ]
            if len(df_pend_terisi) > 0:
                with st.expander("🗑️ Hapus Item Tertentu", expanded=False):
                    rows_del = []
                    for idx in df_pend_terisi.index:
                        row = df_pend_terisi.loc[idx]
                        if st.checkbox(f"{row['Aktivitas']}: {format_rupiah(row['Jumlah (Rp)'])}", key=f"chk_pend_{idx}_{st.session_state.arus_kas_refresh}"):
                            rows_del.append(idx)
                    if rows_del and st.button(f"🗑️ Hapus {len(rows_del)} Item", key="del_pend"):
                        st.session_state.arus_kas_pendanaan = st.session_state.arus_kas_pendanaan.drop(rows_del).reset_index(drop=True)
                        if len(st.session_state.arus_kas_pendanaan) == 0:
                            st.session_state.arus_kas_pendanaan = pd.DataFrame([{"Aktivitas": "", "Jumlah (Rp)": 0}])
                        st.session_state.arus_kas_refresh += 1
                        st.rerun()

        st.markdown("---")

        # Hasil Arus Kas
        df_op = new_arus_operasi[new_arus_operasi["Aktivitas"].astype(str).str.strip() != ""]
        df_inv = new_arus_investasi[new_arus_investasi["Aktivitas"].astype(str).str.strip() != ""]
        df_pend = new_arus_pendanaan[new_arus_pendanaan["Aktivitas"].astype(str).str.strip() != ""]

        if not df_op.empty or not df_inv.empty or not df_pend.empty:
            st.write("### 📊 Hasil Arus Kas")
            arus_data = []
            arus_data.append({"Aktivitas": "Arus Kas Operasi:", "Jumlah": ""})
            for _, r in df_op.iterrows():
                arus_data.append({"Aktivitas": f"  {r['Aktivitas']}", "Jumlah": r["Jumlah (Rp)"]})
            arus_data.append({"Aktivitas": "", "Jumlah": ""})
            arus_data.append({"Aktivitas": "Arus Kas Investasi:", "Jumlah": ""})
            for _, r in df_inv.iterrows():
                arus_data.append({"Aktivitas": f"  {r['Aktivitas']}", "Jumlah": r["Jumlah (Rp)"]})
            arus_data.append({"Aktivitas": "", "Jumlah": ""})
            arus_data.append({"Aktivitas": "Arus Kas Pendanaan:", "Jumlah": ""})
            for _, r in df_pend.iterrows():
                arus_data.append({"Aktivitas": f"  {r['Aktivitas']}", "Jumlah": r["Jumlah (Rp)"]})
            
            df_ak = pd.DataFrame(arus_data)
            st.dataframe(
                df_ak.style.format({"Jumlah": lambda x: format_rupiah(x) if isinstance(x, (int, float)) else x})
                .apply(lambda x: ['font-weight: bold' if i < len(df_ak) and 'Arus Kas' in str(df_ak.iloc[i]['Aktivitas']) else '' for i in range(len(x))], axis=0)
                .set_properties(**{'text-align': 'left'}, subset=['Aktivitas'])
                .set_properties(**{'text-align': 'right'}, subset=['Jumlah']),
                use_container_width=True,
                hide_index=True
            )
            
            # PDF
            def buat_pdf_ak(df, b, t):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, "Laporan Arus Kas", ln=True, align="C")
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 8, "BUMDes", ln=True, align="C")
                pdf.cell(0, 8, f"Periode: {bulan_dict[b]} {t}", ln=True, align="C")
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(120, 10, "Aktivitas", border=1, align="C")
                pdf.cell(60, 10, "Jumlah (Rp)", border=1, align="C")
                pdf.ln()
                pdf.set_font("Arial", '', 9)
                for i in range(len(df)):
                    r = df.iloc[i]
                    is_bold = 'Arus Kas' in str(r['Aktivitas'])
                    if is_bold:
                        pdf.set_font("Arial", 'B', 9)
                    pdf.cell(120, 8, str(r["Aktivitas"])[:47], border=1, align="L")
                    pdf.cell(60, 8, format_rupiah(r["Jumlah"]) if isinstance(r["Jumlah"], (int, float)) else "", border=1, align="R")
                    pdf.ln()
                    if is_bold:
                        pdf.set_font("Arial", '', 9)
                pdf.ln(5)
                pdf.set_font("Arial", 'I', 8)
                pdf.cell(0, 5, "Dicetak dari Sistem Akuntansi BUMDes", ln=True, align="C")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    pdf.output(tmp.name)
                    tmp.seek(0)
                    return tmp.read()
            
            st.download_button("📥 Download PDF Arus Kas", buat_pdf_ak(df_ak, bulan_laporan, tahun_laporan), f"arus_kas_{bulan_laporan}_{tahun_laporan}.pdf", "application/pdf", use_container_width=True)
