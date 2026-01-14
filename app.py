import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, bindparam
from datetime import date, timedelta
import os
from urllib.parse import quote_plus

# LOAD ENV / SECRETS
DB_HOST = st.secrets.get("DB_HOST", os.getenv("DB_HOST"))
DB_PORT = st.secrets.get("DB_PORT", os.getenv("DB_PORT"))
DB_NAME = st.secrets.get("DB_NAME", os.getenv("DB_NAME"))
DB_USER = st.secrets.get("DB_USER", os.getenv("DB_USER"))
DB_PASSWORD = st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD"))

missing = [k for k, v in {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD
}.items() if not v]

if missing:
    st.error(f"❌ Missing environment variables: {', '.join(missing)}")
    st.stop()

DB_PASSWORD = quote_plus(DB_PASSWORD)

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}",
    pool_pre_ping=True
)

# PAGE CONFIG
st.set_page_config(
    page_title="Movement Daily",
    layout="wide"
)

st.title("Movement Daily")

# DEFAULT DATE
yesterday = date.today() - timedelta(days=3)

st.sidebar.header("Filter")

selected_date = st.sidebar.date_input(
    "Tanggal",
    value=yesterday
)

start_date = end_date = selected_date

# LOAD FILTER OPTIONS
@st.cache_data
def load_filter_options():
    query = """
        SELECT DISTINCT outlet, item
        FROM public.mv_movement_daily
        WHERE lower(item) NOT ILIKE '%frozen%'
        ORDER BY outlet, item
    """
    return pd.read_sql(query, engine)

filter_df = load_filter_options()

outlet_options = filter_df["outlet"].dropna().unique().tolist()

default_index = (
    outlet_options.index("Alfamart Kopo")
    if "Alfamart Kopo" in outlet_options
    else 0
)

outlet_selected = st.sidebar.selectbox(
    "Outlet",
    options=outlet_options,
    index=default_index
)

item_options = (
    filter_df[filter_df["outlet"] == outlet_selected]["item"]
    .dropna()
    .unique()
    .tolist()
)

item_selected = st.sidebar.multiselect(
    "Item",
    options=item_options
)

# LOAD DATA
@st.cache_data
def load_data(start_date, end_date, outlet_selected, item_selected):

    query = """
        SELECT
            tanggal,
            outlet,
            spv,
            kota,
            item,
            stock_awal,
            stock_masuk,
            qty_terpakai,
            qty_sisa,
            ideal_usage_qty,
            retur_qty,
            qty_sisa_seharusnya,
            gap_qty_sisa,
            so_flag
        FROM public.mv_movement_daily
        WHERE tanggal BETWEEN :start_date AND :end_date
          AND lower(item) NOT ILIKE '%frozen%'
          AND outlet = :outlet
    """

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "outlet": outlet_selected
    }

    if item_selected:
        query += " AND item IN :items"

    query += " ORDER BY tanggal, outlet, item"

    stmt = text(query)

    if item_selected:
        stmt = stmt.bindparams(bindparam("items", expanding=True))
        params["items"] = tuple(item_selected)

    return pd.read_sql(stmt, engine, params=params)

df = load_data(start_date, end_date, outlet_selected, item_selected)

# INFO
st.caption(f"📅 Periode Data: {start_date}")

if df.empty:
    st.warning("⚠️ Tidak ada data untuk filter yang dipilih")
    st.stop()

tidak_sesuai = (df["so_flag"] == "Tidak Sesuai").sum()
st.warning(f"❗ Jumlah Data **Tidak Sesuai**: **{tidak_sesuai}**")

st.divider()

# RENAME KOLOM
df = df.rename(columns={
    "tanggal": "Tanggal",
    "outlet": "Outlet",
    "spv": "SPV",
    "kota": "Kota",
    "item": "Item",
    "stock_awal": "Stok Awal Hari",
    "stock_masuk": "Barang Masuk (DC)",
    "qty_terpakai": "Terpakai / Terjual",
    "qty_sisa": "Sisa Stok Akhir",
    "ideal_usage_qty": "Pemakaian Seharusnya",
    "retur_qty": "Barang Retur",
    "qty_sisa_seharusnya": "Sisa Seharusnya",
    "gap_qty_sisa": "Selisih Sisa",
    "so_flag": "Status Stok"
})

# FORMAT NUMERIC
numeric_cols = [
    "Stok Awal Hari",
    "Barang Masuk (DC)",
    "Terpakai / Terjual",
    "Sisa Stok Akhir",
    "Pemakaian Seharusnya",
    "Barang Retur",
    "Sisa Seharusnya",
    "Selisih Sisa"
]

for col in numeric_cols:
    df[col] = df[col].fillna(0).round(0).astype("int64")

# HIGHLIGHT TIDAK SESUAI
highlight_cols = [
    "Tanggal",
    "Outlet",
    "SPV",
    "Kota",
    "Item",
    "Status Stok"
]

def highlight_tidak_sesuai(row):
    return [
        "background-color: #ffcccc; font-weight: bold;"
        if row["Status Stok"] == "Tidak Sesuai" and col in highlight_cols
        else ""
        for col in row.index
    ]

styled_df = df.style.apply(highlight_tidak_sesuai, axis=1)

st.dataframe(
    styled_df,
    use_container_width=True,
    height=600
)

st.markdown("""
<small>

**Keterangan Kolom:**
* **Stok Awal Hari**: Sisa stok dari hari sebelumnya **(sudah dikurangi retur)**
* **Barang Masuk (DC)**: Barang kiriman dari gudang / DC  
* **Terpakai / Terjual**: Barang yang digunakan / terjual **(Stok Awal Hari + Barang Masuk (DC) - SO)**
* **Barang Retur**: Barang yang dikembalikan ke gudang / DC  
* **Sisa Stok Akhir**: Stok fisik terakhir **(sudah dikurangi retur)** 
* **Pemakaian Seharusnya**: Standar pemakaian **(data DRetail)**  
* **Sisa Seharusnya**: Sisa stok sesuai standar **(data DRetail)**  
* **Status Stok**: **Sesuai** / **Tidak Sesuai**, sesuai jika **Terpakai / Terjual = Pemakaian Seharusnya**

</small>
""", unsafe_allow_html=True)

# DOWNLOAD
st.download_button(
    label="⬇️ Download CSV",
    data=df.to_csv(index=False),
    file_name="movement_daily.csv",
    mime="text/csv"
)
