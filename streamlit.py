# streamlit.py (FINAL) - Administrasi BUMDes
import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import os
import base64
import requests
from typing import Optional

# -----------------------
# Basic config
# -----------------------
st.set_page_config(page_title="Administrasi BUMDes", layout="wide")
st.title("📘 Sistem Akuntansi BUMDes")

# -----------------------
# GitHub / local backup settings
# -----------------------
DEFAULT_REPO = "puanbening/administrasi-bumdes"
DEFAULT_BRANCH = "main"
DEFAULT_BACKUP_FOLDER = "backup"           # on repo
LOCAL_FALLBACK_DIR = "backup_local"        # local fallback dir
BACKUP_FILENAME = "full_snapshot.json"     # stored as backup/<BACKUP_FILENAME>

os.makedirs(LOCAL_FALLBACK_DIR, exist_ok=True)

# read secrets safely
GITHUB_TOKEN = None
try:
    # st.secrets exists in Streamlit Cloud; use .get to avoid KeyError locally
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, "secrets") else None
except Exception:
    GITHUB_TOKEN = None

GITHUB_REPO = st.secrets.get("GITHUB_REPO", DEFAULT_REPO) if hasattr(st, "secrets") else DEFAULT_REPO
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", DEFAULT_BRANCH) if hasattr(st, "secrets") else DEFAULT_BRANCH
GITHUB_FOLDER = st.secrets.get("BACKUP_FOLDER", DEFAULT_BACKUP_FOLDER) if hasattr(st, "secrets") else DEFAULT_BACKUP_FOLDER

# -----------------------
# Helper: GitHub API operations (with timeout & error handling)
# -----------------------
def _github_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def github_get_file_sha(path: str) -> Optional[str]:
    """Return SHA if file exists, else None."""
    if not GITHUB_TOKEN:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
    try:
        r = requests.get(url, headers=_github_headers(), timeout=10)
        if r.status_code == 200:
            return r.json().get("sha")
    except Exception as e:
        # don't crash app; return None so fallback to local
        st.session_state.setdefault("_backup_warnings", []).append(f"GitHub GET error: {e}")
    return None

def github_put_file(path: str, data_dict: dict, commit_message: str) -> bool:
    """Create or update file at path with data_dict (JSON). Returns True if success."""
    if not GITHUB_TOKEN:
        return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    content_json = json.dumps(data_dict, indent=2, default=str)
    content_b64 = base64.b64encode(content_json.encode()).decode()
    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    sha = github_get_file_sha(path)
    if sha:
        payload["sha"] = sha
    headers = _github_headers()
    headers["Content-Type"] = "application/json"
    try:
        r = requests.put(url, headers=headers, timeout=15, json=payload)
        return r.status_code in (200, 201)
    except Exception as e:
        st.session_state.setdefault("_backup_warnings", []).append(f"GitHub PUT error: {e}")
        return False

def github_load_file(path: str) -> Optional[dict]:
    """Load JSON file content from GitHub; return parsed dict/list or None."""
    if not GITHUB_TOKEN:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
    try:
        r = requests.get(url, headers=_github_headers(), timeout=10)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            raw = base64.b64decode(content_b64).decode()
            return json.loads(raw)
    except Exception as e:
        st.session_state.setdefault("_backup_warnings", []).append(f"GitHub load error: {e}")
    return None

# -----------------------
# Local fallback save/load
# -----------------------
def save_local(filename: str, data: dict):
    path = os.path.join(LOCAL_FALLBACK_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def load_local(filename: str):
    path = os.path.join(LOCAL_FALLBACK_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# -----------------------
# Wrapper for backup: tries GitHub first, then local
# -----------------------
def save_snapshot(snapshot: dict):
    """
    snapshot: dict with keys "jurnal" (list) and "accounts" (dict of lists)
    Will attempt to write to repo at GITHUB_FOLDER/BACKUP_FILENAME; fallback to local.
    """
    path = f"{GITHUB_FOLDER}/{BACKUP_FILENAME}"
    commit_msg = f"Auto-backup full snapshot ({datetime.utcnow().isoformat()})"
    saved_to_github = False
    if GITHUB_TOKEN:
        saved_to_github = github_put_file(path, snapshot, commit_msg)
    if saved_to_github:
        st.info("Backup disimpan ke GitHub.")
    else:
        save_local(BACKUP_FILENAME, snapshot)
        st.warning(f"Backup disimpan secara lokal ({LOCAL_FALLBACK_DIR}/{BACKUP_FILENAME}). (GitHub tidak tersedia)")

def load_snapshot() -> Optional[dict]:
    """Try load from GitHub, then local. Return dict or None."""
    path = f"{GITHUB_FOLDER}/{BACKUP_FILENAME}"
    data = None
    if GITHUB_TOKEN:
        data = github_load_file(path)
    if data is None:
        data = load_local(BACKUP_FILENAME)
    return data

# -----------------------
# Styling & helpers (unchanged semantics)
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
# Load snapshot at startup (once)
# -----------------------
if "data_loaded" not in st.session_state:
    loaded = load_snapshot()
    if loaded and isinstance(loaded, dict):
        # load jurnal
        jurnal_data = loaded.get("jurnal", [])
        try:
            st.session_state.jurnal = pd.DataFrame.from_records(jurnal_data) if jurnal_data else pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
        except Exception:
            st.session_state.jurnal = pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
        # load accounts
        accounts_data = loaded.get("accounts", {})
        if accounts_data and isinstance(accounts_data, dict):
            accounts = {}
            for k, recs in accounts_data.items():
                accounts[k] = pd.DataFrame.from_records(recs) if recs else pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
            # ensure default accounts present
            default_accounts = ["Kas", "Peralatan", "Perlengkapan", "Modal", "Pendapatan",
                                "Beban sewa", "Beban BBM", "Beban gaji", "Beban listrik",
                                "Beban perawatan", "Beban prive"]
            for acc in default_accounts:
                accounts.setdefault(acc, pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"]))
            st.session_state.accounts = accounts
        else:
            # defaults if not present
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
    else:
        # no snapshot found -> initialize empty states
        st.session_state.jurnal = pd.DataFrame(columns=["Tanggal", "Keterangan", "Debit", "Kredit"])
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
# Tabs & main UI
# -----------------------
tab1, tab2 = st.tabs(["🧾 Jurnal Umum", "📚 Buku Besar"])

# Helper to produce consistent snapshot dict
def build_snapshot():
    jurnal_serial = st.session_state.jurnal.to_dict(orient="records") if not st.session_state.jurnal.empty else []
    accounts_serial = {k: v.to_dict(orient="records") for k, v in st.session_state.accounts.items()}
    return {"jurnal": jurnal_serial, "accounts": accounts_serial, "last_update": datetime.utcnow().isoformat()}

# ---------- JURNAL UMUM ----------
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

            # Auto save snapshot (GitHub -> fallback local)
            snapshot = build_snapshot()
            save_snapshot(snapshot)

    st.divider()
    df_jurnal = st.session_state.jurnal.copy()

    if not df_jurnal.empty:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=True), width="stretch")

        cdel1, cdel2, cdel3 = st.columns([2, 1, 1])
        with cdel1:
            del_idx = st.number_input("Hapus baris nomor", min_value=1, max_value=len(df_jurnal), step=1, value=1, help="Pilih nomor baris (bukan baris TOTAL)")
        with cdel2:
            if st.button("Hapus Baris"):
                st.session_state.jurnal = st.session_state.jurnal.drop(st.session_state.jurnal.index[int(del_idx)-1]).reset_index(drop=True)
                # save after deletion
                save_snapshot(build_snapshot())
                st.success(f"Baris {int(del_idx)} berhasil dihapus!")
                st.experimental_rerun()
        with cdel3:
            if st.button("Hapus Semua"):
                st.session_state.jurnal = st.session_state.jurnal.iloc[0:0].copy()
                save_snapshot(build_snapshot())
                st.success("Semua baris jurnal berhasil dihapus!")
                st.experimental_rerun()
    else:
        st.subheader("Data Jurnal Umum")
        st.dataframe(style_table(df_jurnal, add_total=False), width="stretch")
        st.info("Belum ada data transaksi di Jurnal Umum.")

# ---------- BUKU BESAR ----------
with tab2:
    st.header("📚 Buku Besar")
    akun_cols = ["Tanggal", "Keterangan", "Debit", "Kredit"]

    # ensure accounts structure
    if "accounts" not in st.session_state:
        st.session_state.accounts = {}
    # convert any non-dataframe entries
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
    if not akun_list:
        # define defaults if missing
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

            # Save full snapshot after adding to books
            save_snapshot(build_snapshot())

    st.divider()
    tabs_akun = st.tabs(list(st.session_state.accounts.keys()))
    for i, akun in enumerate(list(st.session_state.accounts.keys())):
        with tabs_akun[i]:
            st.markdown(f"Nama Akun: **{akun}**")
            df = st.session_state.accounts[akun]
            df_show = hitung_saldo(df) if not df.empty else df.copy()
            st.dataframe(style_table(df_show, add_total=True), width="stretch")

# -----------------------
# Debug / Manual controls
# -----------------------
st.markdown("---")
col1, col2, col3 = st.columns([1,1,1])
with col1:
    if st.button("🔁 Force Load Snapshot"):
        loaded = load_snapshot()
        if loaded and isinstance(loaded, dict):
            st.session_state.jurnal = pd.DataFrame.from_records(loaded.get("jurnal", [])) if loaded.get("jurnal") else pd.DataFrame(columns=["Tanggal","Keterangan","Debit","Kredit"])
            accounts_loaded = loaded.get("accounts", {})
            if accounts_loaded and isinstance(accounts_loaded, dict):
                st.session_state.accounts = {k: pd.DataFrame.from_records(v) for k, v in accounts_loaded.items()}
            st.success("Snapshot dimuat.")
            st.experimental_rerun()
        else:
            st.warning("Tidak ada snapshot ditemukan (GitHub/local).")

with col2:
    if st.button("💾 Force Save Snapshot"):
        save_snapshot(build_snapshot())
        st.success("Snapshot disimpan (GitHub/local).")

with col3:
    if st.button("📁 Show Local Backup Files"):
        files = os.listdir(LOCAL_FALLBACK_DIR)
        st.write(files if files else "Tidak ada file backup lokal.")

# Show any backup warnings
if st.session_state.get("_backup_warnings"):
    st.warning("Ada peringatan terkait backup:")
    for w in st.session_state["_backup_warnings"]:
        st.write("-", w)
