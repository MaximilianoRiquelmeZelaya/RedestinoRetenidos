import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Redestinación Inteligente", layout="wide", page_icon="🎯")

# Título
st.title("🎯 Buscador de Redestinación de Productos")
st.markdown("Encuentra clientes que acepten tu producto basándose en sus especificaciones técnicas.")

# 1. Carga de Archivo
st.sidebar.header("1. Cargar Datos")
uploaded_file = st.sidebar.file_uploader("Sube Fichas Técnicas (Excel/CSV)", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # Lectura de datos
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Limpieza y conversión de tipos (CRUCIAL para filtrar números)
        # Convertimos 'Minimo' y 'Maximo' a numérico, errores se vuelven NaN
        df['Minimo_num'] = pd.to_numeric(df['Minimo'], errors='coerce')
        df['Maximo_num'] = pd.to_numeric(df['Maximo'], errors='coerce')

        st.success("✅ Datos cargados correctamente")

        # ---------------------------------------------------------
        # 2. SELECCIÓN DE PRODUCTO
        # ---------------------------------------------------------
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.header("2. Producto")
            productos_disponibles = sorted(df['Producto'].dropna().unique())
            producto_sel = st.selectbox("Producto en Contenedor:", productos_disponibles)
        
        # Filtrar DF base por producto
        df_prod = df[df['Producto'] == producto_sel].copy()

        # ---------------------------------------------------------
        # 3. FILTROS AVANZADOS (Lo que pediste)
        # ---------------------------------------------------------
        st.header("3. Filtrar por Análisis de Calidad")
        
        with st.container():
            col_f1, col_f2, col_f3 = st.columns(3)
            
            # A. Lista Desplegable de Análisis disponibles para este producto
            analisis_disponibles = sorted(df_prod['Analisis'].astype(str).unique())
            
            with col_f1:
                analisis_sel = st.selectbox("Selecciona el Análisis Crítico:", analisis_disponibles)
                
            # B. Inputs para filtrar
            with col_f2:
                # Opción 1: Simular el valor de TU producto (Caso de uso: Redestinar)
                valor_producto = st.number_input(
                    "Valor de TU Producto (Redestinación):", 
                    value=0.0, 
                    help="Escribe el valor que tiene tu lote. Se buscarán clientes que acepten este valor."
                )
                usar_valor_producto = st.checkbox("Filtrar usando este valor", value=False)
            
            with col_f3:
                # Opción 2: Filtrar requisitos del cliente
                st.markdown("**O filtrar por rango de exigencia:**")
                min_req = st.number_input("Exigencia Mínima >=", value=0.0)
                max_req = st.number_input("Exigencia Máxima <=", value=100.0)
                usar_rango_manual = st.checkbox("Filtrar por este rango manual", value=False)

        st.markdown("---")

        # ---------------------------------------------------------
        # 4. LÓGICA DE FILTRADO
        # ---------------------------------------------------------
        
        # Empezamos con el DF del producto y el análisis seleccionado
        df_filtrado = df_prod[df_prod['Analisis'] == analisis_sel]

        # Aplicar filtros si están activados
        if usar_valor_producto:
            # Lógica: El cliente sirve si Min_Cliente <= Valor_Producto <= Max_Cliente
            # Usamos fillna para no perder filas donde no haya limite (ej. Min=0 implicito)
            mask = (df_filtrado['Minimo_num'].fillna(0) <= valor_producto) & \
                   (df_filtrado['Maximo_num'].fillna(999999) >= valor_producto)
            df_filtrado = df_filtrado[mask]
            st.info(f"🔍 Buscando clientes que acepten un valor de **{valor_producto}** para **{analisis_sel}**.")

        if usar_rango_manual:
            # Lógica: Mostrar clientes cuyo rango exigido esté dentro de lo que escribí
            # O simplemente filtrar las columnas
            df_filtrado = df_filtrado[
                (df_filtrado['Minimo_num'].fillna(0) >= min_req) & 
                (df_filtrado['Maximo_num'].fillna(999999) <= max_req)
            ]
            st.info(f"🔍 Buscando clientes que pidan entre **{min_req}** y **{max_req}**.")

        # ---------------------------------------------------------
        # 5. MOSTRAR RESULTADOS
        # ---------------------------------------------------------
        
        if df_filtrado.empty:
            st.warning("⚠️ No hay clientes que cumplan con estos criterios de filtro.")
        else:
            clientes_match = df_filtrado['Cliente'].unique()
            st.success(f"🎉 ¡Encontramos {len(clientes_match)} clientes potenciales!")
            
            # Mostrar tabla resumen limpia
            st.subheader("Resumen de Coincidencias")
            cols_ver = ['Cliente', 'Analisis', 'Minimo', 'Maximo']
            st.dataframe(df_filtrado[cols_ver], use_container_width=True, hide_index=True)

            # Detalle expandible (ver la ficha completa de esos clientes)
            with st.expander("Ver Fichas Completas de estos Clientes"):
                # Filtramos el DF original completo para estos clientes
                df_completo_match = df_prod[df_prod['Cliente'].isin(clientes_match)]
                st.dataframe(df_completo_match, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        st.write("Detalle técnico:", e)

else:
    st.info("👋 Sube tu archivo en el menú lateral para comenzar.")
