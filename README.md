import os
import re
import unicodedata
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ===============================
# CONFIGURACIÓN BÁSICA
# ===============================

st.set_page_config(
    page_title="Avance encuesta por región",
    layout="wide"
)

# Rutas
DATA_PATH = "data/data_25112025.xlsx"
TOTAL_PATH = "data/totalmuestra.xlsx"

LOGO_RIMISP = "logos/logo_rimisp.png"
LOGO_INDAP = "logos/logo_indap.png"
LOGO_BID = "logos/logo_bid.png"

META_DIARIA_DEFAULT = 3.0

# Colores Rimisp
COLORS = {
    "verde_oscuro": "#578D7B",
    "verde_medio": "#8AB366",
    "verde_palido": "#C5DFB7",
    "naranjo": "#E97E3F",
}


# ===============================
# FUNCIONES AUXILIARES
# ===============================

def normalizar_region(nombre):
    if pd.isna(nombre):
        return None
    s = str(nombre).strip().upper()
    s = re.sub(r"^\d+-", "", s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s


def cargar_y_preparar_datos(path_data: str, path_total: str):
    xls = pd.ExcelFile(path_data)

    # ========== folio_survey ==========
    folio = pd.read_excel(xls, "folio_survey")
    folio = folio.rename(columns={
        "Region (Agregada)": "region",
        "Comuna (Agregada)": "comuna",
        "surveyor_full_name": "encuestador",
        "subject_folio": "folio",
        "campaign_assigned_id": "campaign_assigned_id",
    })
    folio["folio"] = folio["folio"].astype(str)

    patron_folio_valido = r"^\d{5}-[0-9Kk]$"
    total_folios = len(folio)
    folio = folio[folio["folio"].str.match(patron_folio_valido, na=False)].copy()
    folios_validos = len(folio)
    folios_filtrados = total_folios - folios_validos

    limpieza_info = {
        "total_folios": total_folios,
        "folios_validos": folios_validos,
        "folios_filtrados": folios_filtrados,
    }

    # ========== entrevista_survey ==========
    entrevista = pd.read_excel(xls, "entrevista_survey")
    entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})
    entrevista_subset = entrevista[["campaign_assigned_id", "status", "completedAt_cl"]].copy()

    # ========== merge ==========
    df = folio.merge(entrevista_subset, on="campaign_assigned_id", how="left")
    df = df[df["status"] == "COMPLETED"].copy()

    df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
    df["fecha"] = df["completedAt_cl"].dt.date
    df = df[~df["fecha"].isna()].copy()

    df["region"] = df["region"].fillna("Sin región")
    df["comuna"] = df["comuna"].fillna("Sin comuna")
    df["encuestador"] = df["encuestador"].fillna("Sin encuestador")
    df["region_norm"] = df["region"].apply(normalizar_region)

    # ========== totalmuestra ==========
    tot = pd.read_excel(path_total, "Hoja1")
    tot_regiones = tot[tot["Nivel"] == "Región (total)"].copy()
    tot_regiones = tot_regiones.rename(columns={
        "Región": "region_name",
        "N° de usuarios(as)": "total_muestra",
    })
    tot_regiones["region_norm"] = tot_regiones["region_name"].apply(normalizar_region)
    return df, limpieza_info, tot_regiones


@st.cache_data
def load_data(path_data: str, path_total: str):
    return cargar_y_preparar_datos(path_data, path_total)


# ===============================
# CARGA DE DATOS
# ===============================

df, limpieza_info, tot_regiones = load_data(DATA_PATH, TOTAL_PATH)

if df.empty:
    st.error("No se encontraron datos COMPLETED en las hojas especificadas.")
    st.stop()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()


# ===============================
# LOGOS
# ===============================

col1, col2, col3 = st.columns(3)
with col1:
    st.image(LOGO_RIMISP, width=220)
with col2:
    st.image(LOGO_INDAP, width=220)
with col3:
    st.image(LOGO_BID, width=220)

st.markdown("---")
st.title("Dashboard de avance de encuesta por región")
st.caption("Fuente: data_25112025.xlsx y totalmuestra.xlsx")


# ===============================
# LIMPIEZA DE FOLIOS
# ===============================

with st.expander("Detalle de limpieza de folios"):
    st.write(f"Folios totales en folio_survey: **{limpieza_info['total_folios']}**")
    st.write(f"Folios válidos usados en el análisis: **{limpieza_info['folios_validos']}**")
    st.write(f"Folios filtrados (dummy): **{limpieza_info['folios_filtrados']}**")


# ===============================
# SIDEBAR
# ===============================

st.sidebar.header("Filtros y parámetros")

fecha_corte = st.sidebar.date_input(
    "Fecha de corte",
    value=fecha_max,
    min_value=fecha_min,
    max_value=fecha_max
)

meta_diaria = st.sidebar.number_input(
    "Meta diaria por encuestador",
    min_value=1.0,
    value=META_DIARIA_DEFAULT,
    step=1.0
)

regiones_disponibles = sorted(tot_regiones["region_name"].unique())
regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar",
    options=regiones_disponibles,
    default=regiones_disponibles
)

selected_norms = tot_regiones[
    tot_regiones["region_name"].isin(regiones_seleccionadas)
]["region_norm"].unique()


# ===============================
# RESÚMENES
# ===============================

df_corte = df[(df["fecha"] <= fecha_corte) & (df["region_norm"].isin(selected_norms))].copy()
df_filtrado = df[df["region_norm"].isin(selected_norms)].copy()

if df_corte.empty:
    st.warning("No hay entrevistas completadas en la fecha seleccionada.")
    st.stop()

dias_transcurridos = (fecha_corte - fecha_min).days + 1

realizadas_region_norm = (
    df_corte
    .groupby("region_norm")["campaign_assigned_id"]
    .nunique()
    .rename("realizadas")
)

encuestadores_region_norm = (
    df_filtrado
    .groupby("region_norm")["encuestador"]
    .nunique()
    .rename("n_encuestadores")
)

resumen_region = tot_regiones[
    tot_regiones["region_norm"].isin(selected_norms)
].copy()

resumen_region = resumen_region.merge(realizadas_region_norm, on="region_norm", how="left")
resumen_region = resumen_region.merge(encuestadores_region_norm, on="region_norm", how="left")

resumen_region[["realizadas", "n_encuestadores"]] = resumen_region[["realizadas", "n_encuestadores"]].fillna(0)
resumen_region["pendientes"] = resumen_region["total_muestra"] - resumen_region["realizadas"]
resumen_region["pendientes"] = resumen_region["pendientes"].clip(lower=0)

resumen_region["avance_pct"] = (
    100 * resumen_region["realizadas"] / resumen_region["total_muestra"]
).round(1)


# ===============================
# MÉTRICAS GLOBALES (2199 MUESTRA TOTAL)
# ===============================

total_muestra_global = float(tot_regiones["total_muestra"].sum())
df_corte_global = df[df["fecha"] <= fecha_corte].copy()
total_realizadas_global = int(df_corte_global["campaign_assigned_id"].nunique())
avance_global = 100 * total_realizadas_global / total_muestra_global

c1, c2, c3 = st.columns(3)
c1.metric("Entrevistas realizadas (global)", total_realizadas_global)
c2.metric("Total muestra global", int(total_muestra_global))
c3.metric("Avance global (%)", f"{avance_global:.1f} %")


st.markdown(
    f"**Fecha de corte:** {fecha_corte} · "
    f"**Días transcurridos (desde {fecha_min}):** {dias_transcurridos}"
)


# ===============================
# GRÁFICO DE BARRAS APILADAS
# ===============================

st.subheader("Avance acumulado por región (realizadas vs pendientes)")

resumen_region = resumen_region.sort_values("region_name")

fig = go.Figure()

fig.add_bar(
    x=resumen_region["region_name"],
    y=resumen_region["realizadas"],
    name="Realizadas",
    marker_color=COLORS["verde_oscuro"]
)

fig.add_bar(
    x=resumen_region["region_name"],
    y=resumen_region["pendientes"],
    name="Pendientes",
    marker_color=COLORS["verde_palido"]
)

fig.update_layout(
    barmode="stack",
    xaxis_title="Región",
    yaxis_title="Número de encuestas",
    legend_title="",
    margin=dict(l=0, r=0, t=40, b=80),
)

st.plotly_chart(fig, use_container_width=True)


# ===============================
# TABLA POR REGIÓN
# ===============================

st.subheader("Detalle por región")

tabla_region = resumen_region.rename(columns={
    "region_name": "Región",
    "realizadas": "Realizadas",
    "n_encuestadores": "N encuestadores",
    "total_muestra": "Total muestra región",
    "avance_pct": "% avance"
})

st.dataframe(
    tabla_region[
        ["Región", "Realizadas", "N encuestadores", "Total muestra región", "% avance"]
    ],
    use_container_width=True
)


# ===============================
# DETALLE POR ENCUESTADOR
# ===============================

with st.expander("Detalle por encuestador"):
    resumen_encuestador = (
        df_corte
        .groupby(["region", "encuestador"])["campaign_assigned_id"]
        .nunique()
        .reset_index()
        .rename(columns={"campaign_assigned_id": "realizadas"})
    )

    resumen_encuestador["meta"] = META_DIARIA_DEFAULT * dias_transcurridos
    resumen_encuestador["avance_pct"] = (
        100 * resumen_encuestador["realizadas"] / resumen_encuestador["meta"]
    ).round(1)

    st.dataframe(
        resumen_encuestador.sort_values(["region", "encuestador"]),
        use_container_width=True
    )