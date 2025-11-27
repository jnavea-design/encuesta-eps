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

DATA_PATH = "data/data_27112025.xlsx"
TOTAL_PATH = "data/totalmuestra.xlsx"

# Colores Rimisp
COLORS = {
    "verde_oscuro": "#578D7B",
    "verde_medio": "#8AB366",
    "verde_claro": "#7BB191",
    "verde_palido": "#C5DFB7",
    "naranjo": "#E97E3F",
}

# ===============================
# FUNCIONES DE VALIDACIÓN
# ===============================

def verificar_archivos():
    """Verifica que los archivos existan"""
    errores = []
    if not os.path.exists(DATA_PATH):
        errores.append(f"❌ No se encuentra el archivo: {DATA_PATH}")
    if not os.path.exists(TOTAL_PATH):
        errores.append(f"❌ No se encuentra el archivo: {TOTAL_PATH}")
    return errores

# ===============================
# CARGA Y PREPARACIÓN DE DATOS
# ===============================

def cargar_y_preparar_datos(path_data: str, path_total: str):
    """
    Carga y prepara los datos de las encuestas
    """
    try:
        # ---------- FOLIO SURVEY ----------
        xls = pd.ExcelFile(path_data)
        
        # Verificar que exista la hoja
        if "folio_survey" not in xls.sheet_names:
            st.error(f"❌ La hoja 'folio_survey' no existe en {path_data}")
            st.write(f"Hojas disponibles: {xls.sheet_names}")
            st.stop()
        
        folio = pd.read_excel(xls, "folio_survey")
        
        st.write("**Columnas en folio_survey:**", list(folio.columns))
        
        # Mapeo flexible de columnas
        columnas_mapeo = {
            "Region (Agregada)": "region_key",
            "Region(Agregada)": "region_key",
            "Region": "region_key",
            "region": "region_key",
            "Comuna (Agregada)": "comuna",
            "Comuna(Agregada)": "comuna",
            "Comuna": "comuna",
            "comuna": "comuna",
            "surveyor_full_name": "encuestador",
            "Encuestador": "encuestador",
            "encuestador": "encuestador",
            "subject_folio": "folio",
            "Folio": "folio",
            "folio": "folio",
        }
        
        # Renombrar solo las columnas que existen
        rename_dict = {}
        for col_original, col_nueva in columnas_mapeo.items():
            if col_original in folio.columns:
                rename_dict[col_original] = col_nueva
        
        folio = folio.rename(columns=rename_dict)
        
        # Verificar columnas críticas
        columnas_requeridas = ["region_key", "folio"]
        columnas_faltantes = [col for col in columnas_requeridas if col not in folio.columns]
        
        if columnas_faltantes:
            st.error(f"❌ Faltan columnas requeridas: {columnas_faltantes}")
            st.write("Columnas disponibles:", list(folio.columns))
            st.stop()
        
        # Asegurar columnas opcionales
        if "encuestador" not in folio.columns:
            folio["encuestador"] = "Sin encuestador"
        if "comuna" not in folio.columns:
            folio["comuna"] = "Sin comuna"
        
        # Limpiar folio
        folio["folio"] = folio["folio"].astype(str)
        patron_folio_valido = r"^\d{5}-[0-9Kk]$"
        
        total_folios = len(folio)
        folio = folio[folio["folio"].str.match(patron_folio_valido, na=False)].copy()
        folios_validos = len(folio)
        folios_filtrados = total_folios - folios_validos
        
        # Limpiar región en folio
        folio["region_key"] = (
            folio["region_key"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"#N/D": np.nan, "NAN": np.nan})
        )
        folio = folio.dropna(subset=["region_key"]).copy()
        
        limpieza_info = {
            "total_folios": total_folios,
            "folios_validos": folios_validos,
            "folios_filtrados": folios_filtrados,
        }
        
        # ---------- ENTREVISTA SURVEY ----------
        if "entrevista_survey" not in xls.sheet_names:
            st.error(f"❌ La hoja 'entrevista_survey' no existe en {path_data}")
            st.write(f"Hojas disponibles: {xls.sheet_names}")
            st.stop()
        
        entrevista = pd.read_excel(xls, "entrevista_survey")
        
        st.write("**Columnas en entrevista_survey:**", list(entrevista.columns))
        
        # Flexibilidad en nombres de columnas
        if "assignmentId" in entrevista.columns:
            entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})
        elif "assignment_id" in entrevista.columns:
            entrevista = entrevista.rename(columns={"assignment_id": "campaign_assigned_id"})
        
        # Verificar columnas necesarias
        if "campaign_assigned_id" not in entrevista.columns:
            st.error("❌ No se encuentra la columna de ID de asignación")
            st.write("Columnas disponibles:", list(entrevista.columns))
            st.stop()
        
        # DIAGNÓSTICO: Ver qué hay en entrevista
        st.write("**🔍 DIAGNÓSTICO - entrevista_survey:**")
        st.write(f"- Total de registros: {len(entrevista)}")
        if "status" in entrevista.columns:
            st.write(f"- Estados disponibles: {entrevista['status'].value_counts().to_dict()}")
        st.write(f"- Primeras 3 filas:")
        st.dataframe(entrevista.head(3))
        
        columnas_entrevista = ["campaign_assigned_id"]
        if "status" in entrevista.columns:
            columnas_entrevista.append("status")
        if "completedAt_cl" in entrevista.columns:
            columnas_entrevista.append("completedAt_cl")
        elif "completed_at" in entrevista.columns:
            entrevista = entrevista.rename(columns={"completed_at": "completedAt_cl"})
            columnas_entrevista.append("completedAt_cl")
        
        entrevista_subset = entrevista[columnas_entrevista].copy()
        
        # MERGE
        st.write("**🔍 DIAGNÓSTICO - Antes del merge:**")
        st.write(f"- Registros en folio: {len(folio)}")
        st.write(f"- Registros en entrevista: {len(entrevista_subset)}")
        
        df = folio.merge(entrevista_subset, on="campaign_assigned_id", how="left")
        
        st.write(f"- Registros después del merge: {len(df)}")
        st.write(f"- Registros con status null: {df['status'].isna().sum() if 'status' in df.columns else 'N/A'}")
        
        # Filtrar por status si existe
        if "status" in df.columns:
            antes_filtro = len(df)
            df = df[df["status"] == "COMPLETED"].copy()
            st.write(f"- Registros COMPLETED: {len(df)} (filtrados: {antes_filtro - len(df)})")
        
        # Procesar fechas
        if "completedAt_cl" in df.columns:
            df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
            df["fecha"] = df["completedAt_cl"].dt.date
            antes_fecha = len(df)
            df = df[~df["fecha"].isna()].copy()
            st.write(f"- Registros con fecha válida: {len(df)} (sin fecha: {antes_fecha - len(df)})")
        else:
            # Si no hay fecha, usar fecha actual
            df["fecha"] = date.today()
            st.warning("⚠️ No hay columna de fecha, usando fecha actual")
        
        df["comuna"] = df["comuna"].fillna("Sin comuna")
        df["encuestador"] = df["encuestador"].fillna("Sin encuestador")
        
        # Normalizar region_key
        df["region_key"] = df["region_key"].astype(str).str.strip().str.upper()
        
        # ---------- TOTALMUESTRA ----------
        tot = pd.read_excel(path_total)
        
        st.write("**Columnas en totalmuestra:**", list(tot.columns))
        
        # Mapeo flexible para totalmuestra
        mapeo_total = {
            "Región": "region_key",
            "Region": "region_key",
            "región": "region_key",
            "region": "region_key",
            "N° de usuarios(as)": "total_muestra",
            "Total muestra": "total_muestra",
            "total_muestra": "total_muestra",
            "Muestra": "total_muestra",
        }
        
        rename_total = {}
        for col_orig, col_nueva in mapeo_total.items():
            if col_orig in tot.columns:
                rename_total[col_orig] = col_nueva
        
        tot_regiones = tot.rename(columns=rename_total)
        
        # Limpiar
        tot_regiones["region_key"] = (
            tot_regiones["region_key"]
            .astype(str)
            .str.strip()
            .str.upper()
        )
        
        tot_regiones = tot_regiones.replace({"region_key": {"NAN": np.nan}})
        tot_regiones = tot_regiones.dropna(subset=["region_key"]).copy()
        
        # Crear etiqueta
        tot_regiones["region_label"] = (
            tot_regiones["region_key"]
            .str.split("-", n=1)
            .str[-1]
            .str.strip()
            .str.title()
        )
        
        return df, limpieza_info, tot_regiones
        
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

@st.cache_data
def load_data(path_data: str, path_total: str):
    return cargar_y_preparar_datos(path_data, path_total)

# ===============================
# VERIFICAR ARCHIVOS
# ===============================

errores = verificar_archivos()
if errores:
    st.error("### Errores encontrados:")
    for error in errores:
        st.write(error)
    st.info("""
    **Instrucciones:**
    1. Crea una carpeta llamada `data` en el mismo directorio que este script
    2. Coloca tus archivos Excel en esa carpeta:
       - `data_27112025.xlsx`
       - `totalmuestra.xlsx`
    """)
    st.stop()

# ===============================
# CARGAR DATOS
# ===============================

with st.spinner("Cargando datos..."):
    df, limpieza_info, tot_regiones = load_data(DATA_PATH, TOTAL_PATH)

if df.empty:
    st.error("No se encontraron entrevistas COMPLETED.")
    st.stop()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()

# ===============================
# CABECERA
# ===============================

st.title("📊 Dashboard de avance de encuesta por región")
st.caption(f"Fuente: {os.path.basename(DATA_PATH)} y {os.path.basename(TOTAL_PATH)}")

with st.expander("ℹ️ Detalle de limpieza de folios"):
    col1, col2, col3 = st.columns(3)
    col1.metric("Folios totales", limpieza_info['total_folios'])
    col2.metric("Folios válidos", limpieza_info['folios_validos'])
    col3.metric("Folios filtrados", limpieza_info['folios_filtrados'])

# ===============================
# SIDEBAR
# ===============================

st.sidebar.header("⚙️ Filtros y parámetros")

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

# Lista de regiones
regiones_disponibles = (
    tot_regiones[["region_key", "region_label"]]
    .drop_duplicates()
    .sort_values("region_key")
)

regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar",
    options=list(regiones_disponibles["region_key"]),
    default=list(regiones_disponibles["region_key"]),
    format_func=lambda k: f"{k}",
)

if not regiones_seleccionadas:
    st.warning("⚠️ Selecciona al menos una región para mostrar resultados.")
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
        "⚠️ No hay entrevistas completadas hasta la fecha de corte seleccionada."
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

st.subheader("📈 Métricas Globales")

total_muestra_global = float(tot_regiones["total_muestra"].sum())
df_corte_global = df[df["fecha"] <= fecha_corte].copy()
total_realizadas_global = int(df_corte_global["campaign_assigned_id"].nunique())
avance_global = (
    100 * total_realizadas_global / total_muestra_global
    if total_muestra_global > 0
    else 0
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ Realizadas", f"{total_realizadas_global:,}")
col2.metric("🎯 Meta Total", f"{int(total_muestra_global):,}")
col3.metric("📊 Avance", f"{avance_global:.1f}%")
col4.metric("📅 Días", dias_transcurridos)

st.markdown(f"**Fecha de corte:** {fecha_corte.strftime('%d/%m/%Y')}")

# ===============================
# GRÁFICO: AVANCE POR REGIÓN
# ===============================

st.subheader("📊 Avance por región")

resumen_region = resumen_region.sort_values("avance_pct", ascending=True)

fig = go.Figure()

fig.add_bar(
    y=resumen_region["region_label"],
    x=resumen_region["total_muestra"],
    name="Meta Total",
    marker_color=COLORS["verde_palido"],
    orientation='h',
)

fig.add_bar(
    y=resumen_region["region_label"],
    x=resumen_region["realizadas"],
    name="Realizadas",
    marker_color=COLORS["verde_oscuro"],
    orientation='h',
)

fig.update_layout(
    barmode="overlay",
    xaxis_title="Número de encuestas",
    yaxis_title="",
    legend_title="",
    height=max(400, len(resumen_region) * 40),
    margin=dict(l=0, r=0, t=40, b=40),
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# TABLA DETALLE POR REGIÓN
# ===============================

st.subheader("📋 Detalle por región")

tabla_region = resumen_region[
    [
        "region_label",
        "realizadas",
        "total_muestra",
        "pendientes",
        "avance_pct",
        "n_encuestadores",
    ]
].rename(
    columns={
        "region_label": "Región",
        "realizadas": "Realizadas",
        "total_muestra": "Meta",
        "pendientes": "Pendientes",
        "avance_pct": "% Avance",
        "n_encuestadores": "Encuestadores",
    }
)

# Formatear la tabla
tabla_region["% Avance"] = tabla_region["% Avance"].apply(lambda x: f"{x:.1f}%")

st.dataframe(
    tabla_region.sort_values("% Avance", ascending=False),
    use_container_width=True,
    hide_index=True,
)

# ===============================
# DETALLE POR ENCUESTADOR
# ===============================

with st.expander("👥 Ver detalle por encuestador"):
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
    
    # Merge con region_label
    resumen_encuestador = resumen_encuestador.merge(
        tot_regiones[["region_key", "region_label"]], 
        on="region_key", 
        how="left"
    )
    
    tabla_encuestador = resumen_encuestador[
        ["region_label", "encuestador", "realizadas", "meta", "avance_pct"]
    ].rename(columns={
        "region_label": "Región",
        "encuestador": "Encuestador",
        "realizadas": "Realizadas",
        "meta": "Meta",
        "avance_pct": "% Avance"
    })
    
    tabla_encuestador["% Avance"] = tabla_encuestador["% Avance"].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(
        tabla_encuestador.sort_values(["Región", "Encuestador"]),
        use_container_width=True,
        hide_index=True,
    )

# ===============================
# FOOTER
# ===============================

st.markdown("---")
st.caption("Dashboard creado con Streamlit | Datos actualizados al " + fecha_max.strftime('%d/%m/%Y'))