import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Redestinación de Contenedores", layout="wide", page_icon="📦")

# Título y Contexto
st.title("📦 Sistema de Redestinación de Contenedores")
st.markdown("""
Esta herramienta permite identificar clientes potenciales para redestinar productos 
basándose en las especificaciones técnicas de calidad (Análisis).
""")

# 1. Carga de Archivo (Excel o CSV)
st.sidebar.header("1. Cargar Datos")
uploaded_file = st.sidebar.file_uploader("Sube tu archivo de Fichas Técnicas (Excel o CSV)", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # Lógica para leer Excel o CSV
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Validación básica de columnas
        columnas_requeridas = ['Cliente', 'Producto', 'Tipo', 'Analisis', 'Minimo', 'Maximo']
        if not all(col in df.columns for col in columnas_requeridas):
            st.error(f"El archivo debe contener las columnas: {', '.join(columnas_requeridas)}")
        else:
            st.success("✅ Archivo cargado correctamente")

            # 2. Selector de Producto
            st.header("2. Seleccionar Producto a Redestinar")
            
            # Obtener lista única de productos
            productos_disponibles = df['Producto'].dropna().unique()
            producto_seleccionado = st.selectbox(
                "Elija el tipo de producto disponible en el contenedor:",
                options=productos_disponibles
            )

            # 3. Filtrado y Procesamiento
            # Filtramos por el producto seleccionado y por Tipo = 'Analisis' (según requerimiento)
            df_filtrado = df[
                (df['Producto'] == producto_seleccionado) & 
                (df['Tipo'].astype(str).str.lower() == 'analisis')
            ]

            if df_filtrado.empty:
                st.warning(f"No se encontraron especificaciones de tipo 'Analisis' para el producto: {producto_seleccionado}")
            else:
                # Agrupar por Cliente
                clientes_unicos = df_filtrado['Cliente'].unique()
                
                st.markdown(f"### 📋 Clientes potenciales encontrados: {len(clientes_unicos)}")
                st.markdown("---")

                # Mostrar datos agrupados por Cliente
                for cliente in clientes_unicos:
                    with st.expander(f"👤 Cliente: {cliente}", expanded=True):
                        # Sub-dataframe para este cliente
                        datos_cliente = df_filtrado[df_filtrado['Cliente'] == cliente]
                        
                        # Seleccionamos columnas relevantes para la toma de decisión
                        cols_mostrar = ['Analisis', 'Minimo', 'Maximo']
                        if 'Frecuencia' in df.columns:
                            cols_mostrar.append('Frecuencia')
                        
                        # Mostramos la tabla limpia sin índice numérico
                        st.dataframe(
                            datos_cliente[cols_mostrar].reset_index(drop=True),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Métrica rápida (Opcional: ayuda visual para rangos críticos)
                        # Si quisieras destacar algo específico, este es el lugar.

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")

else:
    st.info("👋 Por favor, sube el archivo 'FichasTecnicas.xlsx' en el panel lateral para comenzar.")
