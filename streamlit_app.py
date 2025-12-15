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

DATA_PATH = "data/EPS_14122025.xlsx"
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
    Carga y prepara los datos desde Excel (nueva estructura EPS_14122025)
    Hoja "Entrevista" contiene los datos principales
    """
    try:
        # ---------- LEER EXCEL PRINCIPAL (HOJA "Entrevista") ----------
        xls = pd.ExcelFile(path_data)
        
        # Verificar que existe la hoja "Entrevista"
        if 'Entrevista' not in xls.sheet_names:
            st.error(f"❌ No se encontró la hoja 'Entrevista' en {path_data}")
            st.info(f"Hojas disponibles: {xls.sheet_names}")
            st.stop()
        
        df = pd.read_excel(xls, 'Entrevista')
        
        print(f"✅ Excel cargado (Hoja 'Entrevista'): {len(df)} registros")
        print(f"Columnas: {list(df.columns[:15])}")
        
        # Renombrar columnas para consistencia
        rename_dict = {}
        
        # Mapeo de columnas
        if 'Region' in df.columns:
            rename_dict['Region'] = 'region_key'
        if 'Comuna' in df.columns:
            rename_dict['Comuna'] = 'comuna'
        if 'Encuestador' in df.columns:
            rename_dict['Encuestador'] = 'encuestador'
        if 'folio_enc' in df.columns:
            rename_dict['folio_enc'] = 'folio'
        if 'status' in df.columns:
            rename_dict['status'] = 'status'
        if 'completedAt' in df.columns:
            rename_dict['completedAt'] = 'completedAt_cl'
        
        df = df.rename(columns=rename_dict)
        
        # Limpiar folio
        if 'folio' in df.columns:
            df["folio"] = df["folio"].astype(str).str.strip()
        else:
            st.error("❌ No se encontró columna de folio")
            st.stop()
        
        # Convertir fecha
        if 'completedAt_cl' in df.columns:
            df["completedAt_cl"] = pd.to_datetime(df["completedAt_cl"], errors="coerce")
            df["fecha"] = df["completedAt_cl"].dt.date
        elif 'createdAt' in df.columns:
            df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce")
            df["fecha"] = df["createdAt"].dt.date
        else:
            df["fecha"] = date.today()
        
        df.loc[df["fecha"].isna(), "fecha"] = date.today()
        
        # ELIMINAR DUPLICADOS - MANTENER SOLO EL ÚLTIMO REGISTRO POR FOLIO
        df_antes = len(df)
        if 'completedAt_cl' in df.columns:
            df = df.sort_values('completedAt_cl', ascending=False)
        df = df.drop_duplicates(subset=['folio'], keep='first')
        df_despues = len(df)
        duplicados_eliminados = df_antes - df_despues
        
        limpieza_info = {
            "total_folios": df_antes,
            "folios_validos": df_despues,
            "folios_filtrados": duplicados_eliminados,
        }
        
        print(f"🔄 Duplicados eliminados: {duplicados_eliminados}")
        print(f"✅ Registros únicos: {df_despues}")
        
        # CLASIFICAR REGISTROS
        df["tipo_registro"] = "Otro"
        df["es_reemplazo"] = False
        
        # 1. COMPLETED = Realizada
        if 'status' in df.columns:
            mascara_completed = df['status'] == 'COMPLETED'
            df.loc[mascara_completed, "tipo_registro"] = "Realizada"
        
        # 2. Si tiene P1.1 con valor = Rechazo
        if 'P1.1' in df.columns:
            mascara_rechazo = (df['P1.1'].notna()) & (df['P1.1'] != "")
            df.loc[mascara_rechazo, "tipo_registro"] = "Rechazo"
        
        # 3. Si tiene P1.2 con valor = Reemplazo
        if 'P1.2' in df.columns:
            mascara_reemplazo = (df['P1.2'].notna()) & (df['P1.2'] != "")
            df.loc[mascara_reemplazo, "es_reemplazo"] = True
        
        # Limpiar región
        if 'region_key' in df.columns:
            df["region_key"] = (
                df["region_key"]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace({"#N/D": np.nan, "NAN": np.nan})
            )
            df = df.dropna(subset=["region_key"]).copy()
        else:
            st.error("❌ No se encontró columna de región")
            st.stop()
        
        # Limpiar encuestador y comuna
        df["encuestador"] = df["encuestador"].fillna("Sin encuestador")
        df["comuna"] = df["comuna"].fillna("Sin comuna")
        
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
    2. Coloca tus archivos en esa carpeta:
       - `EPS_14122025.xlsx` (con hoja "Entrevista")
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

st.sidebar.info(f"Datos disponibles: {fecha_min} a {fecha_max}")

# ===============================
# CABECERA
# ===============================

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

st.title("📊 Dashboard de avance de encuesta por región")
st.caption(f"Fuente: {os.path.basename(DATA_PATH)} (Hoja: Entrevista) y {os.path.basename(TOTAL_PATH)}")

with st.expander("ℹ️ Información de registros"):
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de registros originales", limpieza_info['total_folios'])
    col2.metric("Folios únicos (sin duplicados)", limpieza_info['folios_validos'])
    col3.metric("Duplicados eliminados", limpieza_info['folios_filtrados'])
    
    if limpieza_info['folios_filtrados'] > 0:
        st.info(f"ℹ️ Se eliminaron {limpieza_info['folios_filtrados']} registros duplicados (mismo folio)")

# ===============================
# SIDEBAR
# ===============================

st.sidebar.header("⚙️ Filtros y parámetros")

fecha_corte = st.sidebar.date_input(
    "Fecha de corte",
    value=fecha_max,
    min_value=fecha_min,
    max_value=date.today(),
)

meta_diaria = st.sidebar.number_input(
    "Meta diaria por encuestador",
    min_value=1.0,
    value=3.0,
    step=1.0,
)

regiones_disponibles = (
    tot_regiones[["region_key", "region_label", "region_num"]]
    .drop_duplicates()
    .sort_values("region_num")
)

regiones_seleccionadas = st.sidebar.multiselect(
    "Regiones a mostrar",
    options=list(regiones_disponibles["region_key"]),
    default=list(regiones_disponibles["region_key"]),
    format_func=lambda k: regiones_disponibles[regiones_disponibles["region_key"] == k]["region_label"].iloc[0] if len(regiones_disponibles[regiones_disponibles["region_key"] == k]) > 0 else k,
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
    st.warning("⚠️ No hay registros hasta la fecha de corte seleccionada.")
    st.stop()

dias_transcurridos = (fecha_corte - fecha_min).days + 1

if fecha_corte > fecha_max:
    dias_transcurridos = (fecha_max - fecha_min).days + 1

# ===============================
# RESUMEN POR REGIÓN
# ===============================

resumen_tipo = (
    df_corte.groupby(["region_key", "tipo_registro"])["folio"]
    .nunique()
    .reset_index()
    .pivot(index="region_key", columns="tipo_registro", values="folio")
    .fillna(0)
)

for col in ["Realizada", "Rechazo", "Otro"]:
    if col not in resumen_tipo.columns:
        resumen_tipo[col] = 0

reemplazos_region = (
    df_corte[df_corte["es_reemplazo"] == True]
    .groupby("region_key")["folio"]
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

resumen_region = resumen_region.replace([np.inf, -np.inf], 0)
resumen_region = resumen_region.fillna(0)

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

st.plotly_chart(fig, use_container_width=True)

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

tabla_region["% Avance"] = tabla_region["% Avance"].apply(lambda x: f"{x:.1f}%")
tabla_region["% Rechazo"] = tabla_region["% Rechazo"].apply(lambda x: f"{x:.1f}%")
tabla_region["% Reemplazo"] = tabla_region["% Reemplazo"].apply(lambda x: f"{x:.1f}%")

st.dataframe(
    tabla_region,
    use_container_width=True,
    hide_index=True,
)

# ===============================
# DETALLE POR ENCUESTADOR
# ===============================

with st.expander("👥 Ver detalle por encuestador"):
    resumen_encuestador = (
        df_corte.groupby(["region_key", "encuestador"])["folio"]
        .nunique()
        .reset_index()
        .rename(columns={"folio": "realizadas"})
    )
    
    resumen_encuestador["meta"] = meta_diaria * dias_transcurridos
    resumen_encuestador["avance_pct"] = (
        100 * resumen_encuestador["realizadas"] / resumen_encuestador["meta"]
    ).round(1)
    
    resumen_encuestador = resumen_encuestador.merge(
        tot_regiones[["region_key", "region_label", "region_num"]], 
        on="region_key", 
        how="left"
    )
    
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
        use_container_width=True,
        hide_index=True,
    )

# ===============================
# ANÁLISIS DE RAZONES DE RECHAZO Y REEMPLAZO
# ===============================

st.markdown("---")
st.header("🔍 Análisis Detallado de Razones")

# Mapeos de etiquetas
etiquetas_p1_1 = {
    1: 'Falta de confianza',
    2: 'Falta de tiempo',
    3: 'No encuentra beneficio',
    4: 'Falta de interés',
    5: 'Respondió encuestas recientemente',
    6: 'Otro'
}

etiquetas_p1_2 = {
    1: 'Imposibilidad por enfermedad crónica',
    2: 'Usuario no habita/abandonó agricultura',
    3: 'Usuario no se dedica últimos 3 años'
}

# Crear tabs
tab1, tab2 = st.tabs(["❌ Razones de Rechazo (P1.1)", "🔄 Razones de Reemplazo (P1.2)"])

with tab1:
    st.subheader("P1.1: ¿Por qué no quiso participar en la entrevista?")
    
    if 'P1.1' in df_corte.columns:
        df_p1_1 = df_corte[df_corte['P1.1'].notna()].copy()
        
        if len(df_p1_1) > 0:
            # Función para extraer el valor numérico o detectar "OTRO"
            def procesar_p1_1(valor):
                if pd.isna(valor):
                    return None
                valor_str = str(valor).strip()
                if valor_str.upper().startswith('OTRO') or 'OTRO:' in valor_str.upper():
                    return 6
                try:
                    return int(float(valor_str))
                except:
                    import re
                    match = re.search(r'^\d+', valor_str)
                    if match:
                        return int(match.group())
                    return None
            
            df_p1_1['p1_1_valor'] = df_p1_1['P1.1'].apply(procesar_p1_1)
            df_p1_1 = df_p1_1[df_p1_1['p1_1_valor'].notna()].copy()
            df_p1_1['p1_1_etiqueta'] = df_p1_1['p1_1_valor'].map(etiquetas_p1_1)
            
            col1, col2, col3 = st.columns(3)
            
            total_rechazos_p1_1 = len(df_p1_1)
            casos_otro = (df_p1_1['p1_1_valor'] == 6).sum()
            razon_principal = df_p1_1['p1_1_etiqueta'].value_counts().idxmax() if len(df_p1_1) > 0 else "N/A"
            
            col1.metric("Total Rechazos con Razón", total_rechazos_p1_1)
            col2.metric("Razón Principal", razon_principal)
            col3.metric("Casos 'Otro'", casos_otro)
            
            st.markdown("---")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Distribución de Razones")
                
                conteo_agrupado = df_p1_1['p1_1_etiqueta'].value_counts().sort_values(ascending=True)
                
                fig_p1_1_agrupado = go.Figure()
                
                fig_p1_1_agrupado.add_trace(go.Bar(
                    y=conteo_agrupado.index,
                    x=conteo_agrupado.values,
                    orientation='h',
                    marker_color=COLORS["rojo"],
                    text=[f"{v} ({v/total_rechazos_p1_1*100:.1f}%)" for v in conteo_agrupado.values],
                    textposition='outside'
                ))
                
                fig_p1_1_agrupado.update_layout(
                    xaxis_title="Número de casos",
                    yaxis_title="",
                    height=max(300, len(conteo_agrupado) * 50),
                    showlegend=False
                )
                
                st.plotly_chart(fig_p1_1_agrupado, use_container_width=True)
            
            with col2:
                st.markdown("#### Proporción")
                
                fig_pie_p1_1 = go.Figure()
                
                fig_pie_p1_1.add_trace(go.Pie(
                    labels=conteo_agrupado.index,
                    values=conteo_agrupado.values,
                    hole=0.4,
                    marker=dict(colors=['#e74c3c', '#c0392b', '#e67e22', '#d35400', '#95a5a6', '#7f8c8d'])
                ))
                
                fig_pie_p1_1.update_layout(
                    height=400,
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5)
                )
                
                st.plotly_chart(fig_pie_p1_1, use_container_width=True)
            
        else:
            st.info("ℹ️ No hay registros con razones de rechazo especificadas en P1.1")
    else:
        st.warning("⚠️ No se encontró la columna P1.1 en los datos")

with tab2:
    st.subheader("P1.2: ¿Por qué proponen entrevistar a otra persona?")
    
    if 'P1.2' in df_corte.columns:
        df_p1_2 = df_corte[df_corte['P1.2'].notna()].copy()
        
        if len(df_p1_2) > 0:
            df_p1_2['p1_2_valor'] = pd.to_numeric(df_p1_2['P1.2'], errors='coerce').astype('Int64')
            df_p1_2['p1_2_etiqueta'] = df_p1_2['p1_2_valor'].map(etiquetas_p1_2)
            
            col1, col2, col3 = st.columns(3)
            
            total_reemplazos_p1_2 = len(df_p1_2)
            razon_principal_p1_2 = df_p1_2['p1_2_etiqueta'].value_counts().idxmax() if len(df_p1_2) > 0 else "N/A"
            
            col1.metric("Total Reemplazos con Razón", total_reemplazos_p1_2)
            col2.metric("Razón Principal", razon_principal_p1_2)
            col3.metric("% del Total Realizadas", f"{(total_reemplazos_p1_2/total_realizadas_global*100):.1f}%")
            
            st.markdown("---")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Distribución de Razones de Reemplazo")
                
                conteo_p1_2 = df_p1_2['p1_2_etiqueta'].value_counts().sort_values(ascending=True)
                
                fig_p1_2 = go.Figure()
                
                fig_p1_2.add_trace(go.Bar(
                    y=conteo_p1_2.index,
                    x=conteo_p1_2.values,
                    orientation='h',
                    marker_color=COLORS["naranjo"],
                    text=[f"{v} ({v/total_reemplazos_p1_2*100:.1f}%)" for v in conteo_p1_2.values],
                    textposition='outside'
                ))
                
                fig_p1_2.update_layout(
                    xaxis_title="Número de casos",
                    yaxis_title="",
                    height=max(300, len(conteo_p1_2) * 60),
                    showlegend=False
                )
                
                st.plotly_chart(fig_p1_2, use_container_width=True)
            
            with col2:
                st.markdown("#### Proporción")
                
                fig_pie_p1_2 = go.Figure()
                
                fig_pie_p1_2.add_trace(go.Pie(
                    labels=conteo_p1_2.index,
                    values=conteo_p1_2.values,
                    hole=0.4,
                    marker=dict(colors=[COLORS["naranjo"], COLORS["verde_claro"], COLORS["verde_medio"]])
                ))
                
                fig_pie_p1_2.update_layout(
                    height=400,
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5)
                )
                
                st.plotly_chart(fig_pie_p1_2, use_container_width=True)
            
        else:
            st.info("ℹ️ No hay registros con razones de reemplazo especificadas en P1.2")
    else:
        st.warning("⚠️ No se encontró la columna P1.2 en los datos")

# ===============================
# FOOTER
# ===============================

st.markdown("---")
st.caption("Dashboard creado con Streamlit | Datos actualizados al " + fecha_max.strftime('%d/%m/%Y'))