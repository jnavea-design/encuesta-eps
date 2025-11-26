import os
import re
import unicodedata
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ===============================
# CONFIGURACIÓN BÁSICA STREAMLIT
# ===============================

st.set_page_config(
    page_title="Avance encuesta por región",
    layout="wide"
)

# ===============================
# RUTAS
# ===============================

DATA_PATH = "data/data_26112025.xlsx"
TOTAL_PATH = "data/totalmuestra.xlsx"

# ===============================
# COLORES RIMISP
# ===============================

COLORS = {
    "verde_oscuro": "#578D7B",
    "verde_medio":  "#8AB366",
    "verde_claro":  "#7BB191",
    "verde_palido": "#C5DFB7",
    "naranjo":      "#E97E3F",
}

# ===============================
# NORMALIZACIÓN DE REGIONES
# ===============================

def normalizar_region(nombre):
    if pd.isna(nombre):
        return None
    s = str(nombre).upper().strip()
    s = re.sub(r"^\d+-", "", s)  # quitar "01-" si viene
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s.strip()

# ===============================
# CARGA Y PREPARACIÓN DE DATOS
# ===============================

def cargar_y_preparar_datos(path_data, path_total):

    # ---------- (1) FOLIO SURVEY ----------
    xls = pd.ExcelFile(path_data)
    folio = pd.read_excel(xls, "folio_survey")

    folio = folio.rename(columns={
        "Region (Agregada)": "region",
        "Comuna (Agregada)": "comuna",
        "surveyor_full_name": "encuestador",
        "subject_folio": "folio",
        "campaign_assigned_id": "campaign_assigned_id"
    })

    folio["folio"] = folio["folio"].astype(str)
    patron = r"^\d{5}-[0-9Kk]$"

    total_folios = len(folio)
    folio = folio[folio["folio"].str.match(patron, na=False)].copy()
    validos = len(folio)

    limpieza_info = {
        "total_folios": total_folios,
        "folios_validos": validos,
        "folios_filtrados": total_folios - validos,
    }

    # ---------- (2) ENTREVISTA SURVEY ----------
    entrevista = pd.read_excel(xls, "entrevista_survey")
    entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})

    entrevista = entrevista[["campaign_assigned_id", "status", "completedAt_cl"]]

    df = folio.merge(entrevista, on="campaign_assigned_id", how="left")
    df = df[df["status"] == "COMPLETED"].copy()

    df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
    df["fecha"] = df["completedAt_cl"].dt.date

    df = df.dropna(subset=["fecha"]).copy()

    df["region"] = df["region"].fillna("Sin región")
    df["comuna"] = df["comuna"].fillna("Sin comuna")
    df["encuestador"] = df["encuestador"].fillna("Sin encuestador")

    df["region_norm"] = df["region"].apply(normalizar_region)

    # ---------- (3) TOTALMUESTRA ----------
    tot = pd.read_excel(path_total, "Hoja1")

    # Arreglar códigos de región → formato 01–16 siempre string
    if "Código región" in tot.columns:
        tot["region_code"] = (
            tot["Código región"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(2)
        )

    tot_regiones = tot[tot["Nivel"] == "Región (total)"].copy()

    tot_regiones = tot_regiones.rename(columns={
        "Región": "region_name",
        "N° de usuarios(as)": "total_muestra"
    })

    tot_regiones["region_norm"] = tot_regiones["region_name"].apply(normalizar_region)

    return df, limpieza_info, tot_regiones


@st.cache_data
def load_data(path1, path2):
    return cargar_y_preparar_datos(path1, path2)

# ===============================
# CARGAR DATOS
# ===============================

df, limpieza_info, tot_regiones = load_data(DATA_PATH, TOTAL_PATH)

if df.empty:
    st.error("No hay entrevistas COMPLETED en la base.")
    st.stop()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()

# ===============================
# LOGOS (opcionales)
# ===============================

st.title("Dashboard de avance de encuesta por región")
st.caption("Fuente: data_26112025.xlsx y totalmuestra.xlsx")

# ===============================
# SIDEBAR
# ===============================

fecha_corte = st.sidebar.date_input(
    "Fecha de corte",
    value=fecha_max,
    min_value=fecha_min,
    max_value=fecha_max
)

regiones_disponibles = sorted(tot_regiones["region_norm"].unique())

regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar",
    options=regiones_disponibles,
    default=regiones_disponibles
)

meta_diaria = st.sidebar.number_input(
    "Meta diaria por encuestador",
    value=3.0,
    min_value=1.0,
    step=1.0
)

# ===============================
# FILTROS
# ===============================

df_corte = df[(df["fecha"] <= fecha_corte) & (df["region_norm"].isin(regiones_seleccionadas))]

df_total_filtro = df[df["region_norm"].isin(regiones_seleccionadas)]

dias_transcurridos = (fecha_corte - fecha_min).days + 1

# ===============================
# RESUMEN POR REGIÓN
# ===============================

realizadas_region = (
    df_corte.groupby("region_norm")["campaign_assigned_id"].nunique()
)

encuestadores_region = (
    df_total_filtro.groupby("region_norm")["encuestador"].nunique()
)

resumen = tot_regiones[tot_regiones["region_norm"].isin(regiones_seleccionadas)].copy()
resumen = resumen.merge(realizadas_region, on="region_norm", how="left")
resumen = resumen.merge(encuestadores_region, on="region_norm", how="left")

resumen["realizadas"] = resumen["campaign_assigned_id"].fillna(0).astype(int)
resumen["n_encuestadores"] = resumen["encuestador"].fillna(0).astype(int)

resumen["pendientes"] = resumen["total_muestra"] - resumen["realizadas"]
resumen["pendientes"] = resumen["pendientes"].clip(lower=0)

resumen["avance_pct"] = (100 * resumen["realizadas"] / resumen["total_muestra"]).round(1)

# ===============================
# MÉTRICAS GLOBALES
# ===============================

total_muestra_global = tot_regiones["total_muestra"].sum()
total_realizadas_global = df[df["fecha"] <= fecha_corte]["campaign_assigned_id"].nunique()

avance_global = (100 * total_realizadas_global / total_muestra_global)

col1, col2, col3 = st.columns(3)
col1.metric("Entrevistas realizadas (global)", total_realizadas_global)
col2.metric("Total muestra global", int(total_muestra_global))
col3.metric("Avance global (%)", f"{avance_global:.1f}%")

# ===============================
# GRÁFICO
# ===============================

st.subheader("Avance por región")

resumen = resumen.sort_values("region_name")

fig = go.Figure()

fig.add_bar(
    x=resumen["region_name"],
    y=resumen["total_muestra"],
    name="Total muestra",
    marker_color=COLORS["verde_medio"]
)

fig.add_bar(
    x=resumen["region_name"],
    y=resumen["realizadas"],
    name="Realizadas",
    marker_color=COLORS["verde_oscuro"]
)

fig.update_layout(
    barmode="relative",
    yaxis_title="Encuestas",
    xaxis_title="Región",
    margin=dict(l=0, r=0, t=40, b=80)
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# TABLA DETALLE
# ===============================

st.subheader("Detalle por región")

mostrar = resumen[[
    "region_name", "realizadas", "n_encuestadores",
    "total_muestra", "pendientes", "avance_pct"
]]

st.dataframe(
    mostrar.rename(columns={
        "region_name": "Región",
        "realizadas": "Realizadas",
        "n_encuestadores": "Encuestadores",
        "total_muestra": "Muestra total",
        "pendientes": "Pendientes",
        "avance_pct": "% avance"
    }),
    use_container_width=True
)

# ===============================
# DETALLE POR ENCUESTADOR
# ===============================

with st.expander("Ver detalle por encuestador"):
    res_enc = (
        df_corte.groupby(["region", "encuestador"])["campaign_assigned_id"]
        .nunique()
        .reset_index()
        .rename(columns={"campaign_assigned_id": "realizadas"})
    )

    res_enc["meta"] = dias_transcurridos * meta_diaria
    res_enc["avance_pct"] = (100 * res_enc["realizadas"] / res_enc["meta"]).round(1)

    st.dataframe(res_enc, use_container_width=True)
