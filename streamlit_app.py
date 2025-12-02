# ... (todo el código anterior se mantiene igual hasta antes del FOOTER)

# ===============================
# NUEVA SECCIÓN: ANÁLISIS DE RAZONES DE RECHAZO Y REEMPLAZO
# ===============================

st.markdown("---")
st.header("🔍 Análisis Detallado de Razones")

# Preparar datos de P1.1 y P1.2
# Identificar columnas
p1_1_col = None
p1_1_otro_col = None
p1_2_col = None

for col in df.columns:
    col_lower = col.lower()
    if 'p1_1' in col_lower and 'otro' in col_lower:
        p1_1_otro_col = col
    elif 'p1_1' in col_lower and 'otro' not in col_lower:
        p1_1_col = col
    elif 'p1_2' in col_lower and 'otro' not in col_lower:
        p1_2_col = col

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

# Crear tabs para organizar
tab1, tab2 = st.tabs(["❌ Razones de Rechazo (P1.1)", "🔄 Razones de Reemplazo (P1.2)"])

with tab1:
    st.subheader("P1.1: ¿Por qué no quiso participar en la entrevista?")
    
    if p1_1_col and p1_1_col in df_corte.columns:
        # Preparar datos
        df_p1_1 = df_corte[df_corte[p1_1_col].notna()].copy()
        
        if len(df_p1_1) > 0:
            # Convertir a entero
            df_p1_1['p1_1_valor'] = pd.to_numeric(df_p1_1[p1_1_col], errors='coerce').astype('Int64')
            df_p1_1['p1_1_etiqueta'] = df_p1_1['p1_1_valor'].map(etiquetas_p1_1)
            
            # Si existe columna de "Otro", agregarla
            if p1_1_otro_col and p1_1_otro_col in df_p1_1.columns:
                df_p1_1['p1_1_otro_texto'] = df_p1_1[p1_1_otro_col]
                
                # Crear etiqueta completa
                def crear_etiqueta_otro(row):
                    if row['p1_1_valor'] == 6 and pd.notna(row['p1_1_otro_texto']) and str(row['p1_1_otro_texto']).strip() != '':
                        texto = str(row['p1_1_otro_texto']).strip()
                        if len(texto) > 50:
                            texto = texto[:47] + '...'
                        return f"Otro: {texto}"
                    return row['p1_1_etiqueta']
                
                df_p1_1['p1_1_etiqueta_completa'] = df_p1_1.apply(crear_etiqueta_otro, axis=1)
            else:
                df_p1_1['p1_1_etiqueta_completa'] = df_p1_1['p1_1_etiqueta']
            
            # Métricas generales
            col1, col2, col3 = st.columns(3)
            
            total_rechazos_p1_1 = len(df_p1_1)
            casos_otro = (df_p1_1['p1_1_valor'] == 6).sum()
            razon_principal = df_p1_1['p1_1_etiqueta'].value_counts().idxmax() if len(df_p1_1) > 0 else "N/A"
            
            col1.metric("Total Rechazos con Razón", total_rechazos_p1_1)
            col2.metric("Casos 'Otro' especificados", casos_otro)
            col3.metric("Razón Principal", razon_principal)
            
            st.markdown("---")
            
            # Gráficos
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Distribución de Razones (Agrupadas)")
                
                # Gráfico de barras agrupado
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
                
                st.caption("💡 Nota: Las respuestas 'Otro' están agrupadas en una sola categoría")
            
            with col2:
                st.markdown("#### Proporción")
                
                # Pie chart
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
            
            # Desglose de "Otro"
            if casos_otro > 0:
                st.markdown("---")
                st.markdown("#### 📝 Desglose de Respuestas 'Otro'")
                
                df_otros = df_p1_1[df_p1_1['p1_1_valor'] == 6].copy()
                
                # Gráfico detallado de "Otro"
                conteo_otros = df_otros['p1_1_etiqueta_completa'].value_counts().sort_values(ascending=True).head(10)
                
                if len(conteo_otros) > 0:
                    fig_otros = go.Figure()
                    
                    fig_otros.add_trace(go.Bar(
                        y=conteo_otros.index,
                        x=conteo_otros.values,
                        orientation='h',
                        marker_color=COLORS["naranjo"],
                        text=[f"{v}" for v in conteo_otros.values],
                        textposition='outside'
                    ))
                    
                    fig_otros.update_layout(
                        title="Top 10 Razones Específicas (Categoría 'Otro')",
                        xaxis_title="Número de casos",
                        yaxis_title="",
                        height=max(300, len(conteo_otros) * 40),
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig_otros, use_container_width=True)
                    
                    st.caption(f"📊 Mostrando {min(10, len(conteo_otros))} de {casos_otro} respuestas 'Otro'")
                
                # Tabla con todas las respuestas "Otro"
                with st.expander("Ver todas las respuestas 'Otro' (texto completo)"):
                    df_otros_tabla = df_otros[['folio', 'p1_1_otro_texto']].copy()
                    df_otros_tabla.columns = ['Folio', 'Razón Especificada']
                    df_otros_tabla = df_otros_tabla.sort_values('Folio')
                    st.dataframe(df_otros_tabla, use_container_width=True, hide_index=True)
            
            # Análisis por región
            st.markdown("---")
            st.markdown("#### 🗺️ Razones de Rechazo por Región")
            
            # Merge con región
            df_p1_1_region = df_p1_1.merge(
                df_corte[['folio', 'region_key']], 
                on='folio', 
                how='left'
            )
            
            df_p1_1_region = df_p1_1_region.merge(
                tot_regiones[['region_key', 'region_label']], 
                on='region_key', 
                how='left'
            )
            
            # Crear tabla cruzada
            tabla_cruzada = pd.crosstab(
                df_p1_1_region['region_label'], 
                df_p1_1_region['p1_1_etiqueta'],
                margins=True
            )
            
            st.dataframe(tabla_cruzada, use_container_width=True)
            
        else:
            st.info("ℹ️ No hay registros con razones de rechazo especificadas en P1.1")
    else:
        st.warning("⚠️ No se encontró la columna P1.1 en los datos")

with tab2:
    st.subheader("P1.2: ¿Por qué proponen entrevistar a otra persona?")
    
    if p1_2_col and p1_2_col in df_corte.columns:
        # Preparar datos
        df_p1_2 = df_corte[df_corte[p1_2_col].notna()].copy()
        
        if len(df_p1_2) > 0:
            # Convertir a entero
            df_p1_2['p1_2_valor'] = pd.to_numeric(df_p1_2[p1_2_col], errors='coerce').astype('Int64')
            df_p1_2['p1_2_etiqueta'] = df_p1_2['p1_2_valor'].map(etiquetas_p1_2)
            
            # Métricas generales
            col1, col2, col3 = st.columns(3)
            
            total_reemplazos_p1_2 = len(df_p1_2)
            razon_principal_p1_2 = df_p1_2['p1_2_etiqueta'].value_counts().idxmax() if len(df_p1_2) > 0 else "N/A"
            
            col1.metric("Total Reemplazos con Razón", total_reemplazos_p1_2)
            col2.metric("Razón Principal", razon_principal_p1_2)
            col3.metric("% del Total Realizadas", f"{(total_reemplazos_p1_2/total_realizadas_global*100):.1f}%")
            
            st.markdown("---")
            
            # Gráficos
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Distribución de Razones de Reemplazo")
                
                # Gráfico de barras
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
                
                # Pie chart
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
            
            # Análisis por región
            st.markdown("---")
            st.markdown("#### 🗺️ Razones de Reemplazo por Región")
            
            # Merge con región
            df_p1_2_region = df_p1_2.merge(
                df_corte[['folio', 'region_key']], 
                on='folio', 
                how='left'
            )
            
            df_p1_2_region = df_p1_2_region.merge(
                tot_regiones[['region_key', 'region_label']], 
                on='region_key', 
                how='left'
            )
            
            # Crear tabla cruzada
            tabla_cruzada_p1_2 = pd.crosstab(
                df_p1_2_region['region_label'], 
                df_p1_2_region['p1_2_etiqueta'],
                margins=True
            )
            
            st.dataframe(tabla_cruzada_p1_2, use_container_width=True)
            
            # Gráfico apilado por región
            st.markdown("#### Distribución por Región")
            
            # Preparar datos para gráfico apilado
            region_razon = df_p1_2_region.groupby(['region_label', 'p1_2_etiqueta']).size().reset_index(name='count')
            
            fig_region_stack = go.Figure()
            
            for razon in region_razon['p1_2_etiqueta'].unique():
                data_razon = region_razon[region_razon['p1_2_etiqueta'] == razon]
                fig_region_stack.add_trace(go.Bar(
                    y=data_razon['region_label'],
                    x=data_razon['count'],
                    name=razon,
                    orientation='h'
                ))
            
            fig_region_stack.update_layout(
                barmode='stack',
                xaxis_title="Número de casos",
                yaxis_title="",
                height=max(400, len(region_razon['region_label'].unique()) * 40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig_region_stack, use_container_width=True)
            
        else:
            st.info("ℹ️ No hay registros con razones de reemplazo especificadas en P1.2")
    else:
        st.warning("⚠️ No se encontró la columna P1.2 en los datos")

# ===============================
# FOOTER
# ===============================

st.markdown("---")
st.caption("Dashboard creado con Streamlit | Datos actualizados al " + fecha_max.strftime('%d/%m/%Y'))