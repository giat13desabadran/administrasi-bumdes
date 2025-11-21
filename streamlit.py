import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.title("📘 Jurnal Umum BUMDes")

# --------------------------------------------------------
# INPUT BULAN DARI USER
# --------------------------------------------------------
bulan = st.text_input("Masukkan Bulan dan Tahun (contoh: Januari 2025)", "")

if bulan:
    st.write(f"### Periode: **{bulan}**")

# --------------------------------------------------------
# SESSION STATE untuk menyimpan tabel
# --------------------------------------------------------
if "jurnal_df" not in st.session_state:
    st.session_state.jurnal_df = pd.DataFrame({
        "Tanggal": [],
        "Keterangan": [],
        "Debit (Rp)": [],
        "Kredit (Rp)": []
    })


# --------------------------------------------------------
# TOMBOL TAMBAH & HAPUS BARIS
# --------------------------------------------------------
colA, colB = st.columns(2)

with colA:
    if st.button("➕ Tambah Baris"):
        st.session_state.jurnal_df.loc[len(st.session_state.jurnal_df)] = ["", "", 0, 0]

with colB:
    if st.button("🗑 Hapus Baris Terpilih"):
        if "selected" in st.session_state:
            st.session_state.jurnal_df = st.session_state.jurnal_df.drop(
                index=st.session_state.selected
            ).reset_index(drop=True)
        else:
            st.warning("Pilih baris dahulu untuk menghapus.")


# --------------------------------------------------------
# AGGRID CONFIG
# --------------------------------------------------------
gb = GridOptionsBuilder.from_dataframe(st.session_state.jurnal_df)
gb.configure_default_column(editable=True)
gb.configure_selection(selection_mode="multiple", use_checkbox=True)
gb.configure_pagination(enabled=True)
grid_options = gb.build()

# --------------------------------------------------------
# TABEL AGGRID
# --------------------------------------------------------
grid = AgGrid(
    st.session_state.jurnal_df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED,
    fit_columns_on_grid_load=True,
    theme="balham"
)

# Ambil hasil edit user
updated_df = pd.DataFrame(grid["data"])
selected_rows = grid["selected_rows"]

# Simpan row selection
st.session_state.selected = [r["_selectedRowNodeInfo"]["nodeRowIndex"] for r in selected_rows] if selected_rows else []


# --------------------------------------------------------
# VALIDASI OTOMATIS
# --------------------------------------------------------
errors = []

# Konversi ke numeric
updated_df["Debit (Rp)"] = pd.to_numeric(updated_df["Debit (Rp)"], errors="coerce").fillna(0)
updated_df["Kredit (Rp)"] = pd.to_numeric(updated_df["Kredit (Rp)"], errors="coerce").fillna(0)

# Cek validasi debit & kredit
for idx, row in updated_df.iterrows():
    if row["Debit (Rp)"] > 0 and row["Kredit (Rp)"] > 0:
        errors.append(f"Baris {idx+1}: Debit & Kredit tidak boleh terisi bersamaan.")

if errors:
    st.error("⚠️ Validasi Gagal:\n" + "\n".join(errors))
else:
    # Jika valid, update session state
    st.session_state.jurnal_df = updated_df


# --------------------------------------------------------
# HITUNG TOTAL jika valid
# --------------------------------------------------------
if not errors and not updated_df.empty:
    total_debit = updated_df["Debit (Rp)"].sum()
    total_kredit = updated_df["Kredit (Rp)"].sum()

    st.markdown("### **Total Akhir**")
    col1, col2 = st.columns(2)
    col1.metric("Total Debit", f"Rp {total_debit:,.0f}")
    col2.metric("Total Kredit", f"Rp {total_kredit:,.0f}")
else:
    st.info("Masukkan data dan pastikan validasi terpenuhi.")
