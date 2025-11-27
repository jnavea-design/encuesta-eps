import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ===============================
# CONFIGURACIÓN BÁSICA STREAMLIT
# ===============================

st.set_page_config(
    page_title="Avance encuesta por región",
    layout="wide",
)

# ===============================
# RUTAS DE ARCHIVOS
# ===============================

DATA_PATH = "data/data_26112025.xlsx"   # folio_survey + entrevista_survey
TOTAL_PATH = "data/totalmuestra.xlsx"   # tabla simple Región / N° de usuarios(as)

# ===============================
# COLORES
# ===============================

COLORS = {
    "verde_oscuro": "#578D7B",
    "verde_medio": "#8AB366",
    "verde_claro": "#7BB191",
    "verde_palido": "#C5DFB7",
    "naranjo": "#E97E3F",
}

# ===============================
# CARGA Y PREPARACIÓN DE DATOS
# ===============================


def cargar_y_preparar_datos(path_data: str, path_total: str):
    """
    Carga:
      - data_26112025.xlsx (folio_survey + entrevista_survey)
      - totalmuestra.xlsx  (Hoja1 con columnas:
            'Región', 'N° de usuarios(as)')
    Devuelve:
      - df: entrevistas COMPLETED con metadatos y region_key tipo '08-BIOBIO'
      - limpieza_info: stats de folios filtrados
      - tot_regiones: muestra total por región + region_key y region_label
    """

    # ---------- FOLIO SURVEY ----------
    xls = pd.ExcelFile(path_data)
    folio = pd.read_excel(xls, "folio_survey")

    folio = folio.rename(
        columns={
            "Region (Agregada)": "region_key",
            "Comuna (Agregada)": "comuna",
            "surveyor_full_name": "encuestador",
            "subject_folio": "folio",
            "campaign_assigned_id": "campaign_assigned_id",
        }
    )

    # limpiar folio
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

    # asegurar que region_key tenga el formato correcto como texto
    folio["region_key"] = folio["region_key"].astype(str).str.strip()

    # ---------- ENTREVISTA SURVEY ----------
    entrevista = pd.read_excel(xls, "entrevista_survey")
    entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})

    entrevista_subset = entrevista[
        ["campaign_assigned_id", "status", "completedAt_cl"]
    ].copy()

    # MERGE
    df = folio.merge(entrevista_subset, on="campaign_assigned_id", how="left")

    # sólo COMPLETED
    df = df[df["status"] == "COMPLETED"].copy()

    df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
    df["fecha"] = df["completedAt_cl"].dt.date
    df = df[~df["fecha"].isna()].copy()

    df["comuna"] = df["comuna"].fillna("Sin comuna")
    df["encuestador"] = df["encuestador"].fillna("Sin encuestador")

    # ---------- TOTAL MUESTRA POR REGIÓN ----------
    # Nuevo archivo sencillo:
    # Región | N° de usuarios(as)
    tot_regiones = pd.read_excel(path_total, "Hoja1")

    tot_regiones = tot_regiones.rename(
        columns={
            "Región": "region_key",
            "N° de usuarios(as)": "total_muestra",
        }
    )

    # asegurar formato idéntico al de folio_survey
    tot_regiones["region_key"] = (
        tot_regiones["region_key"].astype(str).str.strip()
    )

    # etiqueta sin código (solo el nombre después del guion)
    tot_regiones["region_label"] = (
        tot_regiones["region_key"].str.split("-", n=1).str[-1]
    )

    return df, limpieza_info, tot_regiones


@st.cache_data
def load_data(path_data: str, path_total: str):
    return cargar_y_preparar_datos(path_data, path_total)


# ===============================
# CARGAR DATOS
# ===============================

df, limpieza_info, tot_regiones = load_data(DATA_PATH, TOTAL_PATH)

if df.empty:
    st.error("No se encontraron entrevistas COMPLETED.")
    st.stop()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()

# ===============================
# CABECERA
# ===============================

st.title("Dashboard de avance de encuesta por región")
st.caption("Fuente: data_26112025.xlsx y totalmuestra.xlsx")

with st.expander("Detalle de limpieza de folios"):
    st.write(f"Folios totales en folio_survey: **{limpieza_info['total_folios']}**")
    st.write(f"Folios válidos usados en el análisis: **{limpieza_info['folios_validos']}**")
    st.write(
        f"Folios filtrados (dummy, como 301-8, 302-6, etc.): **{limpieza_info['folios_filtrados']}**"
    )

# ===============================
# SIDEBAR
# ===============================

st.sidebar.header("Filtros y parámetros")

fecha_corte = st.sidebar.date_input(
    "Fecha de corte",
    value=fecha_max,
    min_value=fecha_min,
    max_value=fecha_max,
)

meta_diaria = st.sidebar.number_input(
    "Meta diaria por encuestador",
    min_value=1.0,
    value=3.0,
    step=1.0,
)

# Lista de regiones a partir de tot_regiones (clave oficial igual a Region (Agregada))
regiones_disponibles = (
    tot_regiones[["region_key", "region_label"]]
    .drop_duplicates()
    .sort_values("region_key")
)

regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar (código + nombre)",
    options=list(regiones_disponibles["region_key"]),
    default=list(regiones_disponibles["region_key"]),
    format_func=lambda k: f"{k}",
)

if not regiones_seleccionadas:
    st.warning("Selecciona al menos una región para mostrar resultados.")
    st.stop()

# ===============================
# FILTRADO PRINCIPAL
# ===============================

df_corte = df[
    (df["fecha"] <= fecha_corte) & (df["region_key"].isin(regiones_seleccionadas))
].copy()

df_filtrado_total = df[df["region_key"].isin(regiones_seleccionadas)].copy()

if df_corte.empty:
    st.warning(
        "No hay entrevistas completadas hasta la fecha de corte seleccionada con los filtros actuales."
    )
    st.stop()

dias_transcurridos = (fecha_corte - fecha_min).days + 1

# ===============================
# RESUMEN POR REGIÓN
# ===============================

realizadas_region = (
    df_corte.groupby("region_key")["campaign_assigned_id"]
    .nunique()
    .rename("realizadas")
)

encuestadores_region = (
    df_filtrado_total.groupby("region_key")["encuestador"]
    .nunique()
    .rename("n_encuestadores")
)

resumen_region = tot_regiones[
    tot_regiones["region_key"].isin(regiones_seleccionadas)
].copy()

resumen_region = resumen_region.merge(realizadas_region, on="region_key", how="left")
resumen_region = resumen_region.merge(encuestadores_region, on="region_key", how="left")

resumen_region[["realizadas", "n_encuestadores"]] = resumen_region[
    ["realizadas", "n_encuestadores"]
].fillna(0)

resumen_region["pendientes"] = (
    resumen_region["total_muestra"] - resumen_region["realizadas"]
).clip(lower=0)

resumen_region["avance_pct"] = (
    100 * resumen_region["realizadas"] / resumen_region["total_muestra"]
).round(1)

# ===============================
# MÉTRICAS GLOBALES
# ===============================

total_muestra_global = float(tot_regiones["total_muestra"].sum())
df_corte_global = df[df["fecha"] <= fecha_corte].copy()
total_realizadas_global = int(df_corte_global["campaign_assigned_id"].nunique())
avance_global = (
    100 * total_realizadas_global / total_muestra_global
    if total_muestra_global > 0
    else np.nan
)

col1, col2, col3 = st.columns(3)
col1.metric("Entrevistas realizadas (global)", f"{total_realizadas_global}")
col2.metric("Total muestra global", f"{int(total_muestra_global)}")
col3.metric("Avance global (%)", f"{avance_global:.1f} %")

st.markdown(
    f"**Fecha de corte:** {fecha_corte.strftime('%Y-%m-%d')}  ·  "
    f"**Días transcurridos (desde {fecha_min}):** {dias_transcurridos}"
)

# ===============================
# GRÁFICO: AVANCE POR REGIÓN
# ===============================

st.subheader("Avance por región (realizadas vs total muestra)")

resumen_region = resumen_region.sort_values("region_key")

fig = go.Figure()

fig.add_bar(
    x=resumen_region["region_label"],
    y=resumen_region["total_muestra"],
    name="Total muestra región",
    marker_color=COLORS["verde_medio"],
)

fig.add_bar(
    x=resumen_region["region_label"],
    y=resumen_region["realizadas"],
    name="Realizadas",
    marker_color=COLORS["verde_oscuro"],
)

fig.update_layout(
    barmode="relative",
    xaxis_title="Región",
    yaxis_title="Número de encuestas",
    legend_title="",
    margin=dict(l=0, r=0, t=40, b=80),
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# TABLA DETALLE POR REGIÓN
# ===============================

st.subheader("Detalle por región")

tabla_region = resumen_region[
    [
        "region_key",
        "region_label",
        "realizadas",
        "n_encuestadores",
        "total_muestra",
        "pendientes",
        "avance_pct",
    ]
].rename(
    columns={
        "region_key": "Código–Región",
        "region_label": "Región",
        "realizadas": "Realizadas",
        "n_encuestadores": "N encuestadores",
        "total_muestra": "Total muestra región",
        "pendientes": "Pendientes",
        "avance_pct": "% avance",
    }
)

st.dataframe(tabla_region, use_container_width=True)

# ===============================
# DETALLE POR ENCUESTADOR
# ===============================

with st.expander("Ver detalle por encuestador (meta diaria x días)"):

    resumen_encuestador = (
        df_corte.groupby(["region_key", "encuestador"])["campaign_assigned_id"]
        .nunique()
        .reset_index()
        .rename(columns={"campaign_assigned_id": "realizadas"})
    )

    resumen_encuestador["meta"] = meta_diaria * dias_transcurridos
    resumen_encuestador["avance_pct"] = (
        100 * resumen_encuestador["realizadas"] / resumen_encuestador["meta"]
    ).round(1)

    st.dataframe(
        resumen_encuestador.sort_values(["region_key", "encuestador"]),
        use_container_width=True,
    )
