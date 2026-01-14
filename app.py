import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, timedelta
import os
from dotenv import load_dotenv

# LOAD ENV
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# DB ENGINE
engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# PAGE CONFIG

st.set_page_config(
    page_title="Movement Daily Dashboard",
    layout="wide")

st.title("Movement Daily Dashboard")

# DEFAULT DATE
yesterday = date.today() - timedelta(days=3)

# SIDEBAR FILTER
st.sidebar.header("Filter")

date_range = st.sidebar.date_input(
    "Tanggal",
    value=(yesterday, yesterday)
)

if isinstance(date_range, tuple):
    start_date, end_date = date_range
else:
    start_date = end_date = date_range


@st.cache_data
def load_filter_options():
    query = """
        SELECT DISTINCT outlet, item
        FROM public.mv_movement_daily
        ORDER BY outlet, item
    """
    return pd.read_sql(query, engine)

filter_df = load_filter_options()

outlet_selected = st.sidebar.multiselect(
    "Outlet",
    options=filter_df["outlet"].dropna().unique()
)

item_selected = st.sidebar.multiselect(
    "Item",
    options=filter_df["item"].dropna().unique()
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
    """

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    if outlet_selected:
        query += " AND outlet = ANY(:outlet)"
        params["outlet"] = outlet_selected

    if item_selected:
        query += " AND item = ANY(:item)"
        params["item"] = item_selected

    query += " ORDER BY tanggal, outlet, item"

    return pd.read_sql(text(query), engine, params=params)

df = load_data(start_date, end_date, outlet_selected, item_selected)

# INFO PERIODE
st.caption(f"📅 Periode: {start_date} s/d {end_date}")

if df.empty:
    st.warning("⚠️ Tidak ada data untuk filter yang dipilih")
    st.stop()

tidak_sesuai = (df["so_flag"] == "Tidak Sesuai").sum()
st.warning(f"❗ Jumlah Data **Tidak Sesuai**: **{tidak_sesuai}**")

st.divider()

df = df.rename(columns={
    "tanggal": "Tanggal",
    "outlet": "Outlet",
    "spv": "SPV",
    "kota": "Kota",
    "item": "Nama Produk",
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

# HIGHLIGHT TIDAK SESUAI
highlight_cols = [
    "Tanggal",
    "Outlet",
    "SPV",
    "Kota",
    "Nama Produk",
    "Status Stok"
]

def highlight_tidak_sesuai(row):
    styles = []
    for col in row.index:
        if row["Status Stok"] == "Tidak Sesuai" and col in highlight_cols:
            styles.append("background-color: #ffcccc; font-weight: bold;")
        else:
            styles.append("")
    return styles

styled_df = df.style.apply(highlight_tidak_sesuai, axis=1)

# TABLE
st.dataframe(
    styled_df,
    use_container_width=True,
    height=600
)

# DESKRIPSI KOLOM
st.markdown("""
<small>

**Keterangan Kolom:**
- **Stok Awal Hari**: Sisa stok dari hari sebelumnya  
- **Barang Masuk (DC)**: Barang kiriman dari gudang / DC  
- **Terpakai / Terjual**: Barang yang digunakan / terjual  
- **Barang Retur**: Barang yang dikembalikan ke gudang / DC  
- **Sisa Stok Akhir**: Stok fisik terakhir  
- **Pemakaian Seharusnya**: Standar pemakaian (dari DRetail)  
- **Sisa Seharusnya**: Sisa stok sesuai standar  
- **Status Stok**: **Sesuai** / **Tidak Sesuai**

</small>
""", unsafe_allow_html=True)

# DOWNLOAD
st.download_button(
    "⬇️ Download CSV",
    df.to_csv(index=False),
    file_name="movement_daily.csv",
    mime="text/csv"
)
