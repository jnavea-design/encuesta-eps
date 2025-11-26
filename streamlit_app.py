import os
import re
import unicodedata
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
    layout="wide"
)

# ===============================
# RUTAS DE ARCHIVOS
# ===============================

DATA_PATH = "data/data_26112025.xlsx"
TOTAL_PATH = "data/totalmuestra.xlsx"

# carpeta base (para logos)
DATA_DIR = "logos"

LOGO_RIMISP = os.path.join(DATA_DIR, "logo_rimisp.png")
LOGO_INDAP  = os.path.join(DATA_DIR, "logo_indap.png")
LOGO_BID    = os.path.join(DATA_DIR, "logo_bid.png")

META_DIARIA_DEFAULT = 3.0

# ===============================
# FUNCIONES AUXILIARES
# ===============================

def limpiar_region_location(x):
    if pd.isna(x):
        return None
    x = x.upper()
    x = x.replace("REGIÓN DEL ", "").replace("REGION DEL ", "")
    x = x.replace("REGIÓN DE ", "").replace("REGION DE ", "")
    x = x.replace("REGIÓN ", "").replace("REGION ", "")
    x = x.replace(", CHILE", "").strip()

    if "BIOBIO" in x or "BIOBÍO" in x:
        return "BIOBIO"
    if "AYSEN" in x or "AYSÉN" in x:
        return "AYSEN"
    if "ARAUCA" in x:
        return "LA ARAUCANIA"
    if "ÑUBLE" in x or "NUBLE" in x:
        return "ÑUBLE"
    if "LOS LAGOS" in x:
        return "LOS LAGOS"
    if "LOS RIOS" in x or "LOS RÍOS" in x:
        return "LOS RIOS"

    return x


def normalizar_texto(s):
    if pd.isna(s):
        return None
    s = s.upper()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("utf-8")
    s = s.replace("'", "")
    s = s.strip()
    return s


# Diccionario con código oficial Chile
region_map = {
    "ARICA Y PARINACOTA": "15-ARICA Y PARINACOTA",
    "TARAPACA": "01-TARAPACA",
    "ANTOFAGASTA": "02-ANTOFAGASTA",
    "ATACAMA": "03-ATACAMA",
    "COQUIMBO": "04-COQUIMBO",
    "VALPARAISO": "05-VALPARAISO",
    "LIBERTADOR BERNARDO O HIGGINS": "06-LIBERTADOR BERNARDO O'HIGGINS",
    "MAULE": "07-MAULE",
    "BIOBIO": "08-BIOBIO",
    "LA ARAUCANIA": "09-ARAUCANÍA",
    "LOS LAGOS": "10-LOS LAGOS",
    "AYSEN": "11-AYSÉN",
    "MAGALLANES": "12-MAGALLANES",
    "METROPOLITANA": "13-METROPOLITANA",
    "LOS RIOS": "14-LOS RÍOS",
    "ÑUBLE": "16-ÑUBLE"
}

# ===============================
# CARGA DE DATOS
# ===============================

xls = pd.ExcelFile(DATA_PATH)

folio = pd.read_excel(xls, "folio_survey")
entrevista = pd.read_excel(xls, "entrevista_survey")
tot_regiones = pd.read_excel(TOTAL_PATH, "Hoja1")

# Normalizar nombres
folio["location"] = folio["location"].astype(str)
folio["region_clean"] = folio["location"].apply(limpiar_region_location)
folio["region_clean"] = folio["region_clean"].apply(normalizar_texto)

tot_regiones["region_clean"] = tot_regiones["Región"].apply(normalizar_texto)

# Aplicar códigos a ambos DF
folio["region_code"] = folio["region_clean"].map(region_map)
tot_regiones["region_code"] = tot_regiones["region_clean"].map(region_map)

# Conversión de entrevista
entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})
entrevista["completedAt_cl"] = pd.to_datetime(entrevista["completedAt_cl"], errors="coerce")

# MERGE completo
df = folio.merge(
    entrevista[["campaign_assigned_id", "status", "completedAt_cl"]],
    on="campaign_assigned_id",
    how="left"
)

df = df[df["status"] == "COMPLETED"].copy()
df["fecha"] = df["completedAt_cl"].dt.date

df = df[df["region_code"].notna()].copy()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()

# ===============================
# LOGOS
# ===============================

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    if os.path.exists(LOGO_RIMISP):
        st.image(LOGO_RIMISP, width=140)
with c2:
    if os.path.exists(LOGO_INDAP):
        st.image(LOGO_INDAP, width=140)
with c3:
    if os.path.exists(LOGO_BID):
        st.image(LOGO_BID, width=140)

st.markdown("---")
st.title("Dashboard de avance de encuesta por región")
st.caption("Fuente: data_26112025.xlsx y totalmuestra.xlsx")

# ===============================
# SIDEBAR FILTROS
# ===============================

st.sidebar.header("Filtros y parámetros")

fecha_corte = st.sidebar.date_input(
    "Fecha de corte",
    value=fecha_max,
    min_value=fecha_min,
    max_value=fecha_max,
)

regiones_disponibles = sorted(tot_regiones["region_code"].unique())
regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones",
    regiones_disponibles,
    default=regiones_disponibles
)

df_corte = df[(df["fecha"] <= fecha_corte) & (df["region_code"].isin(regiones_seleccionadas))]

# ===============================
# RESUMEN POR REGIÓN
# ===============================

realizadas_region = (
    df_corte.groupby("region_code")["campaign_assigned_id"]
    .nunique()
    .rename("realizadas")
)

encuestadores_region = (
    df.groupby("region_code")["encuestador"]
    .nunique()
    .rename("n_encuestadores")
)

resumen_region = tot_regiones[
    tot_regiones["region_code"].isin(regiones_seleccionadas)
].copy()

resumen_region = resumen_region.merge(realizadas_region, on="region_code", how="left")
resumen_region = resumen_region.merge(encuestadores_region, on="region_code", how="left")

resumen_region[["realizadas", "n_encuestadores"]] = resumen_region[["realizadas", "n_encuestadores"]].fillna(0)

resumen_region = resumen_region.rename(columns={"N° de usuarios(as)": "total_muestra"})

resumen_region["avance_pct"] = (
    100 * resumen_region["realizadas"] / resumen_region["total_muestra"]
).round(1)

# ===============================
# MÉTRICAS GLOBALES
# ===============================

total_muestra_global = resumen_region["total_muestra"].sum()
total_realizadas_global = resumen_region["realizadas"].sum()
avance_global = 100 * total_realizadas_global / total_muestra_global

col1, col2, col3 = st.columns(3)
col1.metric("Realizadas (global)", f"{total_realizadas_global}")
col2.metric("Total muestra global", f"{int(total_muestra_global)}")
col3.metric("Avance global (%)", f"{avance_global:.1f}%")

# ===============================
# GRAFICO
# ===============================

st.subheader("Avance acumulado por región")

fig = go.Figure()

fig.add_bar(
    x=resumen_region["region_code"],
    y=resumen_region["total_muestra"],
    name="Total muestra",
    marker_color="#8AB366",
)

fig.add_bar(
    x=resumen_region["region_code"],
    y=resumen_region["realizadas"],
    name="Realizadas",
    marker_color="#578D7B",
)

fig.update_layout(
    barmode="relative",
    xaxis_title="Región",
    yaxis_title="Encuestas",
    legend_title=""
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# TABLA
# ===============================

st.subheader("Detalle por región")

st.dataframe(
    resumen_region[[
        "region_code", "realizadas", "n_encuestadores", "total_muestra", "avance_pct"
    ]],
    use_container_width=True
)
