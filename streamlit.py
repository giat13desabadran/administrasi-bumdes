# streamlit.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import os
import base64
import requests

# -----------------------
# Config dasar
# -----------------------
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# -----------------------
# Default / fallback repo info (parsed from URL user provided)
# -----------------------
DEFAULT_REPO = "puanbening/administrasi-bumdes"
DEFAULT_BRANCH = "main"
DEFAULT_BACKUP_FOLDER = "backup"
LOCAL_FALLBACK_DIR = "backup_local"

os.makedirs(LOCAL_FALLBACK_DIR, exist_ok=True)

# -----------------------
# GitHub helper (uses Streamlit secrets if available)
# -----------------------
def get_github_settings():
    # Prefer secrets set in Streamlit Cloud; otherwise use defaults
    repo = st.secrets.get("GITHUB_REPO", DEFAULT_REPO) if hasattr(st, "secrets") else DEFAULT_REPO
    token = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, "secrets") else None
    branch = st.secrets.get("GITHUB_BRANCH", DEFAULT_BRANCH) if hasattr(st, "secrets") else DEFAULT_BRANCH
    folder = st.secrets.get("BACKUP_FOLDER", DEFAULT_BACKUP_FOLDER) if hasattr(st, "secrets") else DEFAULT_BACKUP_FOLDER
    return repo, token, branch, folder

def github_get_file_sha(repo, token, branch, path):
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def save_json_to_github(data: dict, filename: str) -> bool:
    """
    Save `data` (dict) to repo: {backup_folder}/{filename} via GitHub API.
    Returns True on success, False on failure.
    """
    repo, token, branch, folder = get_github_settings()
    if not token:
        return False

    url = f"https://api.github.com/repos/{repo}/contents/{folder}/{filename}"
    headers = {"Authorization": f"Bearer {token}"}
    content_b64 = base64.b64encode(json.dumps(data, indent=2, default=str).encode()).decode()

    # Check existing to get sha
    get_resp = requests.get(url + f"?ref={branch}", headers=headers)
    payload = {
        "message": f"Auto-backup {filename} ({datetime.utcnow().isoformat()})",
        "content": content_b64,
        "branch": branch,
    }
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")
        payload["sha"] = sha

    put_resp = requests.put(url, headers=headers, json=payload)
    return put_resp.status_code in (200, 201)

def load_json_from_github(filename: str):
    """
    Load and return parsed JSON from repo backup folder. Returns None if not found or error.
    """
    repo, token, branch, folder = get_github_settings()
    if not token:
        return None
    url = f"https://api.github.com/repos/{repo}/contents/{folder}/{filename}?ref={branch}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_b64 = r.json().get("content", "")
        try:
            raw = base64.b64decode(content_b64).decode()
            return json.loads(raw)
        except Exception:
            return None
    return None

# -----------------------
# Local fallback save/load (when GitHub not configured or failing)
# -----------------------
def save_json_local(data: dict, filename: str):
    path = os.path.join(LOCAL_FALLBACK_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def load_json_local(filename: str):
    path = os.path.join(LOCAL_FALLBACK_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# -----------------------
# Wrapper save/load that tries GitHub first, falls back to local
# -----------------------
def save_backup_auto(name: str, data_dict: dict):
    """
    name: filename (eg. 'jurnal.json', 'accounts.json')
    data_dict: serializable dict
    """
    ok = False
    try:
        ok = save_json_to_github(data_dict, name)
    except Exception:
        ok = False

    if not ok:
        # fallback to local
        try:
            save_json_local(data_dict, name)
            st.warning(f"Backup disimpan secara lokal ({LOCAL_FALLBACK_DIR}/{name}). (GitHub tidak tersedia)")
        except Exception as e:
            st.error(f"Gagal menyimpan backup lokal: {e}")
    else:
        st.info(f"Backup tersimpan di GitHub: {name}")

def load_backup_auto(name: str):
    """
    Try loading from GitHub, then fallback to local.
    Returns parsed dict or None.
    """
    data = None
    try:
        data = load_json_from_github(name)
    except Exception:
        data = None

    if data is None:
        data = load_json_local(name)
    return data

# -----------------------
# Styling & helper functions (sama seperti sebelumnya)
# -----------------------
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

def fmt_tgl(v):
    try:
        return pd.to_datetime(v).strftime("%d-%m-%Y")
    except Exception:
        return v

def style_table(df: pd.DataFrame, add_total: bool = True):
    df_disp = df.copy()
    df_disp.index = range(1, len(df_disp) + 1)
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

    format_map = {}
    if "Tanggal" in df_disp.columns:
        format_map["Tanggal"] = fmt_tgl
    for col in ["Debit", "Kredit", "Saldo Debit", "Saldo Kredit"]:
        if col in df_disp.columns:
            format_map[col] = "Rp {:,.0f}".format
    return df_disp.style.format(format_map).set_properties(**{"text-align": "center"})

def form_transaksi(form_key: str, akun_options=None):
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
            jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.0f", key=f"{form_key}_jml")
            submitted = st.form_submit_button("Tambah Transaksi")
    return {
        "submitted": submitted,
        "tgl": tgl,
        "ket": ket,
        "tipe": tipe,
        "jumlah": jumlah,
        "akun": akun_val,
    }

# -----------------------
# Load backup on startup (auto-load)
# -----------------------
JURNAL_FILE = "jurnal.json"
ACCOUNTS_FILE = "accounts.json"

if "data_loaded" not in st.session_state:
    # Try load jurnal
    loaded = load_backup_auto(JURNAL_FILE)
    if loaded:
        try:
            # Expecting list of records
            st.session_state.jurnal = pd.DataFrame.from_records(loaded)
        except Exception:
            st.session_state.jurnal = pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
    else:
        st.session_state.jurnal = pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])

    # Try load accounts (expecting dict: account_name -> list of records)
    loaded_acc = load_backup_auto(ACCOUNTS_FILE)
    if loaded_acc and isinstance(loaded_acc, dict):
        # ensure all accounts present (fallback to defaults if missing)
        default_accounts = ["Kas", "Peralatan", "Perlengkapan", "Modal", "Pendapatan",
                            "Beban sewa", "Beban BBM", "Beban gaji", "Beban listrik",
                            "Beban perawatan", "Beban prive"]
        accounts = {}
        for k in default_accounts:
            recs = loaded_acc.get(k, [])
            accounts[k] = pd.DataFrame.from_records(recs) if recs else pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
        # include any extra accounts from loaded_acc
        for k, recs in loaded_acc.items():
            if k not in accounts:
                accounts[k] = pd.DataFrame.from_records(recs)
        st.session_state.accounts = accounts
    else:
        st.session_state.accounts = {
            "Kas": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Peralatan": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Perlengkapan": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Modal": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Pendapatan": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban sewa": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban BBM": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban gaji": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban listrik": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban perawatan": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]),
            "Beban prive": pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
        }

    st.session_state.data_loaded = True

# -----------------------
# UI (tabs) - logika tetap sama, tapi kita panggil save_backup_auto(...) saat ada perubahan
# -----------------------
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

with tab1:
    st.header("🧾 Jurnal Umum")
    st.subheader("Input Transaksi Baru")

    jurnal_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]

    # ensure columns exist
    if "jurnal" not in st.session_state:
        st.session_state.jurnal = pd.DataFrame(columns=jurnal_cols)
    else:
        for c in jurnal_cols:
            if c not in st.session_state.jurnal.columns:
                st.session_state.jurnal[c] = []

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
                "Tanggal": f["tgl"].isoformat() if isinstance(f["tgl"], date) else str(f["tgl"]),
                "Keterangan": f["ket"].strip(),
                "Debit": debit,
                "Kredit": kredit,
            }
            st.session_state.jurnal = pd.concat([st.session_state.jurnal, pd.DataFrame([new_row])], ignore_index=True)
            st.success("Transaksi berhasil ditambahkan ke Jurnal Umum!")

            # Save backup: jurnal + accounts (keep both in sync)
            save_backup_auto(JURNAL_FILE, st.session_state.jurnal.to_dict(orient="records"))
            # also save accounts snapshot
            accounts_serial = {k: v.to_dict(orient="records") for k, v in st.session_state.accounts.items()}
            save_backup_auto(ACCOUNTS_FILE, accounts_serial)

    st.divider()
    df_jurnal = st.session_state.jurnal.copy()

    if not df_jurnal.empty:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=True), use_container_width=True)

        cdel1, cdel2, cdel3 = st.columns([2, 1, 1])
        with cdel1:
            del_idx = st.number_input("Hapus baris nomor", min_value=1, max_value=len(df_jurnal), step=1, value=1)
        with cdel2:
            if st.button("Hapus Baris"):
                st.session_state.jurnal = st.session_state.jurnal.drop(st.session_state.jurnal.index[int(del_idx)-1]).reset_index(drop=True)
                # save after deletion
                save_backup_auto(JURNAL_FILE, st.session_state.jurnal.to_dict(orient="records"))
                st.success(f"Baris {int(del_idx)} berhasil dihapus!")
                st.experimental_rerun()
        with cdel3:
            if st.button("Hapus Semua"):
                st.session_state.jurnal = st.session_state.jurnal.iloc[0:0].copy()
                save_backup_auto(JURNAL_FILE, st.session_state.jurnal.to_dict(orient="records"))
                st.success("Semua baris jurnal berhasil dihapus!")
                st.experimental_rerun()
    else:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=False), use_container_width=True)
        st.info("Belum ada data transaksi di Jurnal Umum.")

with tab2:
    st.header("📚 Buku Besar")
    akun_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]

    # ensure accounts exist
    if "accounts" not in st.session_state:
        st.session_state.accounts = {}
    for k, df in list(st.session_state.accounts.items()):
        if not isinstance(df, pd.DataFrame):
            st.session_state.accounts[k] = pd.DataFrame.from_records(df)
        for c in akun_cols:
            if c not in st.session_state.accounts[k].columns:
                st.session_state.accounts[k][c] = []

    # helper saldo berjalan
    def hitung_saldo(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        dfx = df.copy()
        dfx["Tanggal"] = pd.to_datetime(dfx["Tanggal"], errors='coerce')
        for c in ["Debit", "Kredit"]:
            dfx[c] = pd.to_numeric(dfx[c], errors="coerce").fillna(0.0)
        dfx = dfx.sort_values(["Tanggal"], kind="mergesort").reset_index(drop=True)
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

    st.subheader("Input Transaksi Baru")
    akun_list = list(st.session_state.accounts.keys())
    # if no accounts defined (edge-case), define defaults
    if not akun_list:
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
                "Tanggal": [fbb["tgl"].isoformat() if isinstance(fbb["tgl"], date) else str(fbb["tgl"])],
                "Keterangan": [fbb["ket"].strip()],
                "Debit": [debit],
                "Kredit": [kredit],
            })
            st.session_state.accounts[fbb["akun"]] = pd.concat([st.session_state.accounts[fbb["akun"]], baris], ignore_index=True)
            st.success(f"Transaksi ditambahkan ke akun {fbb['akun']}!")

            # Save both jurnal and accounts snapshots
            save_backup_auto(JURNAL_FILE, st.session_state.jurnal.to_dict(orient="records"))
            accounts_serial = {k: v.to_dict(orient="records") for k, v in st.session_state.accounts.items()}
            save_backup_auto(ACCOUNTS_FILE, accounts_serial)

    st.divider()

    # display per account in tabs
    tabs_akun = st.tabs(list(st.session_state.accounts.keys()))
    for i, akun in enumerate(list(st.session_state.accounts.keys())):
        with tabs_akun[i]:
            st.markdown(f"Nama Akun: **{akun}**")
            df = st.session_state.accounts[akun]
            df_show = hitung_saldo(df) if not df.empty else df.copy()
            st.dataframe(style_table(df_show, add_total=True), use_container_width=True)

# -----------------------
# Optional manual actions for debugging / restore
# -----------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔁 Force Load Backup dari GitHub"):
        # force reload
        loaded = load_backup_auto(JURNAL_FILE)
        if loaded:
            st.session_state.jurnal = pd.DataFrame.from_records(loaded)
        loaded_acc = load_backup_auto(ACCOUNTS_FILE)
        if loaded_acc and isinstance(loaded_acc, dict):
            st.session_state.accounts = {k: pd.DataFrame.from_records(v) for k, v in loaded_acc.items()}
        st.experimental_rerun()

with col2:
    if st.button("💾 Force Save Snapshot ke GitHub/Local"):
        save_backup_auto(JURNAL_FILE, st.session_state.jurnal.to_dict(orient="records"))
        accounts_serial = {k: v.to_dict(orient="records") for k, v in st.session_state.accounts.items()}
        save_backup_auto(ACCOUNTS_FILE, accounts_serial)

with col3:
    if st.button("📁 Show Local Backup Files"):
        files = os.listdir(LOCAL_FALLBACK_DIR)
        st.write(files if files else "Tidak ada file backup lokal.")
