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

DATA_PATH = "data/data_29112025.xlsx"
TOTAL_PATH = "data/totalmuestra.xlsx"

# Colores Rimisp
COLORS = {
    "verde_oscuro": "#578D7B",
    "verde_medio": "#8AB366",
    "verde_claro": "#7BB191",
    "verde_palido": "#C5DFB7",
    "naranjo": "#E97E3F",
    "rojo": "#DC3545",
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
        
        if "folio_survey" not in xls.sheet_names:
            st.error(f"❌ La hoja 'folio_survey' no existe en {path_data}")
            st.write(f"Hojas disponibles: {xls.sheet_names}")
            st.stop()
        
        folio = pd.read_excel(xls, "folio_survey")
        
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
        
        # Verificar si campaign_status existe en folio
        if "campaign_status" in folio.columns:
            folio = folio.rename(columns={"campaign_status": "status_folio"})
        elif "status" in folio.columns:
            folio = folio.rename(columns={"status": "status_folio"})
        
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
        
        # Flexibilidad en nombres de columnas
        if "assignmentId" in entrevista.columns:
            entrevista = entrevista.rename(columns={"assignmentId": "campaign_assigned_id"})
        elif "assignment_id" in entrevista.columns:
            entrevista = entrevista.rename(columns={"assignment_id": "campaign_assigned_id"})
        
        if "campaign_assigned_id" not in entrevista.columns:
            st.error("❌ No se encuentra la columna de ID de asignación")
            st.write("Columnas disponibles:", list(entrevista.columns))
            st.stop()
        
        # Columnas a extraer (incluyendo p1_0, p1_1, p1_2)
        columnas_entrevista = ["campaign_assigned_id"]
        if "status" in entrevista.columns:
            columnas_entrevista.append("status")
        if "completedAt_cl" in entrevista.columns:
            columnas_entrevista.append("completedAt_cl")
        elif "completed_at" in entrevista.columns:
            entrevista = entrevista.rename(columns={"completed_at": "completedAt_cl"})
            columnas_entrevista.append("completedAt_cl")
        
        # Agregar TODAS las columnas que empiezan con p1_
        for col in entrevista.columns:
            if col.startswith("p1_") or col.startswith("P1_"):
                if col not in columnas_entrevista:
                    columnas_entrevista.append(col)
        
        entrevista_subset = entrevista[columnas_entrevista].copy()
        
        # MERGE
        ids_folio = set(folio['campaign_assigned_id'].dropna())
        ids_entrevista = set(entrevista_subset['campaign_assigned_id'].dropna())
        ids_comunes = ids_folio.intersection(ids_entrevista)
        
        if len(ids_comunes) > 0:
            df = folio.merge(entrevista_subset, on="campaign_assigned_id", how="left")
        else:
            if "folio_encuesta" in entrevista.columns or "subjectId" in entrevista.columns:
                if "folio_encuesta" in entrevista.columns:
                    entrevista["folio_match"] = entrevista["folio_encuesta"].astype(str)
                elif "subjectId" in entrevista.columns:
                    entrevista["folio_match"] = entrevista["subjectId"].astype(str)
                
                folio["folio_match"] = folio["folio"].astype(str)
                entrevista_subset_folio = entrevista[columnas_entrevista + ["folio_match"]].copy()
                df = folio.merge(entrevista_subset_folio, on="folio_match", how="left")
            else:
                st.error("❌ No se puede hacer merge. Revisa la estructura de los archivos.")
                st.stop()
        
        # Clasificar registros
        df["tipo_registro"] = "Otro"
        
        # Buscar columnas p1_1 y p1_2
        p1_1_cols = [col for col in df.columns if col.lower().startswith("p1_1")]
        p1_2_cols = [col for col in df.columns if col.lower().startswith("p1_2")]
        
        p1_1_col = p1_1_cols[0] if p1_1_cols else None
        p1_2_col = p1_2_cols[0] if p1_2_cols else None
        
        # Crear máscaras para cada tipo
        tiene_p1_1 = False
        tiene_p1_2 = False
        
        if p1_1_col:
            # p1_1 tiene valor = rechazo (NO respuesta)
            tiene_p1_1 = (df[p1_1_col].notna()) & (df[p1_1_col] != "")
        
        if p1_2_col:
            # p1_2 tiene valor = reemplazo (pero va en REALIZADAS)
            tiene_p1_2 = (df[p1_2_col].notna()) & (df[p1_2_col] != "")
        
        # Clasificar
        # Primero: marcar todo lo que tiene status COMPLETED o IN_PROGRESS (de folio o entrevista)
        status_a_usar = None
        if "status_folio" in df.columns:
            status_a_usar = "status_folio"
        elif "status" in df.columns:
            status_a_usar = "status"
        
        if status_a_usar:
            mascara_realizada = df[status_a_usar].isin(["COMPLETED"])
            df.loc[mascara_realizada, "tipo_registro"] = "Realizada"
        
        # Segundo: sobrescribir con Rechazo si tiene p1_1 (se negó)
        if isinstance(tiene_p1_1, pd.Series):
            df.loc[tiene_p1_1, "tipo_registro"] = "Rechazo"
        
        # Marcar específicamente los reemplazos (para conteo, pero quedan como realizadas)
        if isinstance(tiene_p1_2, pd.Series):
            df["es_reemplazo"] = tiene_p1_2
        else:
            df["es_reemplazo"] = False
        
        # Procesar fechas
        if "completedAt_cl" in df.columns:
            df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
            df["fecha"] = df["completedAt_cl"].dt.date
            # Para los que no tienen fecha, usar fecha de hoy
            df.loc[df["fecha"].isna(), "fecha"] = date.today()
        else:
            df["fecha"] = date.today()
        
        df["comuna"] = df["comuna"].fillna("Sin comuna")
        df["encuestador"] = df["encuestador"].fillna("Sin encuestador")
        df["region_key"] = df["region_key"].astype(str).str.strip().str.upper()
        
        # ---------- TOTALMUESTRA ----------
        tot = pd.read_excel(path_total)
        
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
        
        tot_regiones["region_key"] = (
            tot_regiones["region_key"]
            .astype(str)
            .str.strip()
            .str.upper()
        )
        
        tot_regiones = tot_regiones.replace({"region_key": {"NAN": np.nan}})
        tot_regiones = tot_regiones.dropna(subset=["region_key"]).copy()
        
        # Extraer número de región para ordenamiento
        tot_regiones["region_num"] = (
            tot_regiones["region_key"]
            .str.extract(r'^(\d+)', expand=False)
            .astype(float)
        )
        
        # Crear etiqueta CON número
        tot_regiones["region_label"] = (
            tot_regiones["region_key"]
            .str.replace("-", " - ")
        )
        
        # Ordenar por número de región
        tot_regiones = tot_regiones.sort_values("region_num").reset_index(drop=True)
        
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
       - `data_29112025.xlsx`
       - `totalmuestra.xlsx`
    """)
    st.stop()

# ===============================
# CARGAR DATOS
# ===============================

with st.spinner("Cargando datos..."):
    df, limpieza_info, tot_regiones = load_data(DATA_PATH, TOTAL_PATH)

if df.empty:
    st.error("No se encontraron registros.")
    st.stop()

fecha_min = df["fecha"].min()
fecha_max = df["fecha"].max()

# Debug: mostrar fechas
st.sidebar.info(f"Datos disponibles: {fecha_min} a {fecha_max}")

# ===============================
# CABECERA
# ===============================

# Logos en la parte superior
col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 2])

with col2:
    if os.path.exists("logos/logo_rimisp.png"):
        st.image("logos/logo_rimisp.png", width=150)

with col3:
    if os.path.exists("logos/logo_bid.png"):
        st.image("logos/logo_bid.png", width=150)

with col4:
    if os.path.exists("logos/logo_indap.png"):
        st.image("logos/logo_indap.png", width=150)

# Título debajo de los logos
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
    value=fecha_max,  # Usa la fecha máxima de los datos, no hoy
    min_value=fecha_min,
    max_value=date.today(),
)

meta_diaria = st.sidebar.number_input(
    "Meta diaria por encuestador",
    min_value=1.0,
    value=3.0,
    step=1.0,
)

# Lista de regiones (ordenadas por número)
regiones_disponibles = (
    tot_regiones[["region_key", "region_label", "region_num"]]
    .drop_duplicates()
    .sort_values("region_num")
)

regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar",
    options=list(regiones_disponibles["region_key"]),
    default=list(regiones_disponibles["region_key"]),
    format_func=lambda k: regiones_disponibles[regiones_disponibles["region_key"] == k]["region_label"].iloc[0],
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
        "⚠️ No hay registros hasta la fecha de corte seleccionada."
    )
    st.stop()

dias_transcurridos = (fecha_corte - fecha_min).days + 1

# Ajustar si la fecha de corte es mayor a la fecha máxima real de datos
if fecha_corte > fecha_max:
    dias_transcurridos = (fecha_max - fecha_min).days + 1

# ===============================
# RESUMEN POR REGIÓN
# ===============================

# Contar por tipo de registro
resumen_tipo = (
    df_corte.groupby(["region_key", "tipo_registro"])["campaign_assigned_id"]
    .nunique()
    .reset_index()
    .pivot(index="region_key", columns="tipo_registro", values="campaign_assigned_id")
    .fillna(0)
)

# Asegurar que existan todas las columnas
for col in ["Realizada", "Rechazo"]:
    if col not in resumen_tipo.columns:
        resumen_tipo[col] = 0

# Contar reemplazos por separado (no van al gráfico pero sí a métricas)
reemplazos_region = (
    df_corte[df_corte["es_reemplazo"] == True]
    .groupby("region_key")["campaign_assigned_id"]
    .nunique()
    .rename("reemplazos")
)

realizadas_region = resumen_tipo["Realizada"].rename("realizadas")
rechazos_region = resumen_tipo["Rechazo"].rename("rechazos")

encuestadores_region = (
    df_filtrado_total.groupby("region_key")["encuestador"]
    .nunique()
    .rename("n_encuestadores")
)

resumen_region = tot_regiones[
    tot_regiones["region_key"].isin(regiones_seleccionadas)
].copy()

resumen_region = resumen_region.merge(realizadas_region, on="region_key", how="left")
resumen_region = resumen_region.merge(rechazos_region, on="region_key", how="left")
resumen_region = resumen_region.merge(reemplazos_region, on="region_key", how="left")
resumen_region = resumen_region.merge(encuestadores_region, on="region_key", how="left")

resumen_region[["realizadas", "rechazos", "reemplazos", "n_encuestadores"]] = resumen_region[
    ["realizadas", "rechazos", "reemplazos", "n_encuestadores"]
].fillna(0)

resumen_region["contactadas"] = (
    resumen_region["realizadas"] + 
    resumen_region["rechazos"]
)

resumen_region["pendientes"] = (
    resumen_region["total_muestra"] - resumen_region["contactadas"]
).clip(lower=0)

resumen_region["avance_pct"] = (
    100 * resumen_region["contactadas"] / resumen_region["total_muestra"]
).round(1)

resumen_region["tasa_rechazo"] = (
    100 * resumen_region["rechazos"] / resumen_region["contactadas"]
).round(1)

resumen_region["tasa_reemplazo"] = (
    100 * resumen_region["reemplazos"] / resumen_region["contactadas"]
).round(1)

# Reemplazar inf y nan
resumen_region = resumen_region.replace([np.inf, -np.inf], 0)
resumen_region = resumen_region.fillna(0)

# Ordenar por número de región
resumen_region = resumen_region.sort_values("region_num").reset_index(drop=True)

# ===============================
# MÉTRICAS GLOBALES
# ===============================

st.subheader("📈 Métricas Globales")

total_muestra_global = float(tot_regiones["total_muestra"].sum())
df_corte_global = df[df["fecha"] <= fecha_corte].copy()

total_realizadas_global = int((df_corte_global["tipo_registro"] == "Realizada").sum())
total_rechazos_global = int((df_corte_global["tipo_registro"] == "Rechazo").sum())
total_reemplazos_global = int(df_corte_global["es_reemplazo"].sum())
total_contactadas_global = total_realizadas_global + total_rechazos_global

# Avance incluye realizadas + rechazos
avance_global = (
    100 * total_contactadas_global / total_muestra_global
    if total_muestra_global > 0
    else 0
)

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("✅ Realizadas", f"{total_realizadas_global:,}")
col2.metric("🎯 Meta Total", f"{int(total_muestra_global):,}")
col3.metric("📊 Avance", f"{avance_global:.1f}%")
col4.metric("📅 Días", dias_transcurridos)
col5.metric("❌ Rechazos", f"{total_rechazos_global:,}")
col6.metric("🔄 Reemplazos", f"{total_reemplazos_global:,}")

st.markdown(f"**Fecha de corte:** {fecha_corte.strftime('%d/%m/%Y')}")

# ===============================
# GRÁFICO: AVANCE POR REGIÓN
# ===============================

st.subheader("📊 Avance por región")

fig = go.Figure()

fig.add_bar(
    y=resumen_region["region_label"],
    x=resumen_region["realizadas"],
    name="Realizadas (incluye reemplazos)",
    marker_color=COLORS["verde_oscuro"],
    orientation='h',
)

fig.add_bar(
    y=resumen_region["region_label"],
    x=resumen_region["rechazos"],
    name="Rechazos",
    marker_color=COLORS["rojo"],
    orientation='h',
)

fig.add_bar(
    y=resumen_region["region_label"],
    x=resumen_region["pendientes"],
    name="Pendientes",
    marker_color=COLORS["verde_palido"],
    orientation='h',
)

fig.update_layout(
    barmode="stack",
    xaxis_title="Número de encuestas",
    yaxis_title="",
    legend_title="Estado",
    height=max(400, len(resumen_region) * 40),
    margin=dict(l=0, r=0, t=40, b=40),
)

st.plotly_chart(fig, width='stretch')

# ===============================
# TABLA DETALLE POR REGIÓN
# ===============================

st.subheader("📋 Detalle por región")

tabla_region = resumen_region[
    [
        "region_label",
        "realizadas",
        "rechazos",
        "reemplazos",
        "contactadas",
        "pendientes",
        "total_muestra",
        "avance_pct",
        "tasa_rechazo",
        "tasa_reemplazo",
        "n_encuestadores",
    ]
].rename(
    columns={
        "region_label": "Región",
        "realizadas": "Realizadas",
        "rechazos": "Rechazos",
        "reemplazos": "Reemplazos",
        "contactadas": "Contactadas",
        "pendientes": "Pendientes",
        "total_muestra": "Meta",
        "avance_pct": "% Avance",
        "tasa_rechazo": "% Rechazo",
        "tasa_reemplazo": "% Reemplazo",
        "n_encuestadores": "Encuestadores",
    }
)

# Formatear porcentajes
tabla_region["% Avance"] = tabla_region["% Avance"].apply(lambda x: f"{x:.1f}%")
tabla_region["% Rechazo"] = tabla_region["% Rechazo"].apply(lambda x: f"{x:.1f}%")
tabla_region["% Reemplazo"] = tabla_region["% Reemplazo"].apply(lambda x: f"{x:.1f}%")

st.dataframe(
    tabla_region,
    width='stretch',
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
    
    # Merge con region_label y region_num
    resumen_encuestador = resumen_encuestador.merge(
        tot_regiones[["region_key", "region_label", "region_num"]], 
        on="region_key", 
        how="left"
    )
    
    # Ordenar por región (número)
    resumen_encuestador = resumen_encuestador.sort_values(["region_num", "encuestador"])
    
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
        tabla_encuestador,
        width='stretch',
        hide_index=True,
    )

# ===============================
# FOOTER
# ===============================

st.markdown("---")
st.caption("Dashboard creado con Streamlit | Datos actualizados al " + fecha_max.strftime('%d/%m/%Y'))