import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Matchmaker Pro: TURBO", layout="wide", page_icon="⚡")

st.title("⚡ Buscador de Clientes (Optimizado + Imputación Robusta)")
st.markdown("version 3"")

# ==========================================
# 🧠 CONFIGURACIÓN Y MAPEOS
# ==========================================
MAPEO_PARAMETROS = {
    'hojuelas quemadas': ['quemadas', "quemada"],
    'hojuelas gelatinizadas': ['gelatinas', 'gelatina', 'gelatinizadas'],
    'materias extrañas': ['mat extraña', 'materia extraña', 'impurezas'],
    'materia extraña': ['mat extraña', 'materia extraña', 'impurezas'],
    'granos dañados': ['dañados', 'grano dañado'],
    'densidad aparente': ['densidad', 'peso hectolitrico', 'peso especifico'],
    'peroxidos': ['ind perioxido', 'peroxido', 'indice de peroxido'],
    'acidez': ['acidez', 'indice de acidez']
}

SINONIMOS_TIPOS = {
    'instantanea': ['quick', 'instant', 'instantanea', 'instantánea', 'inst'],
    'tradicional': ['rolled', 'traditional', 'tradicional', 'regular', 'old fashioned'],
    'integral': ['whole', 'wholegrain', 'integral', 'grano entero'],
    'laminada': ['rolled', 'flake', 'laminada'],
    'fina': ['fine', 'fina', 'baby'],
    'ultra fina': ['super fine', 'ultra', 'dust'],
    'avena pelada': ['groat', 'kernel', 'pelada'],
    'estabilizada': ['stabilized', 'estabilizada']
}

# --- FUNCIONES OPTIMIZADAS ---
@st.cache_data
def normalizar_texto(texto):
    if not isinstance(texto, str): return str(texto)
    texto = texto.lower().strip()
    texto = texto.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    texto = texto.replace('n°', '').replace('no.', '').replace('num', '')
    for char in ['.', ',', '-', '/', '_', '%']:
        texto = texto.replace(char, ' ')
    return " ".join(texto.split())

def detectar_familia_hoja(nombre_hoja):
    h = normalizar_texto(nombre_hoja)
    if 'groat' in h or 'pelada' in h: return 'groat'
    if 'harina' in h: return 'harina'
    if 'pillow' in h: return 'pillow'
    if 'hojuela' in h: return 'hojuela'
    return 'otros'

def es_texto_gf(texto):
    t = normalizar_texto(texto)
    if 'gf' in t: return True
    if 'gluten' in t and any(x in t for x in ['free', 'sin', 'libre', 'no']): return True
    return False

def check_tipo_producto_score(lote_tipo_norm, ficha_producto_norm):
    if not lote_tipo_norm or lote_tipo_norm == 'nan': return 0
    
    if lote_tipo_norm in ficha_producto_norm: return 1
    for clave, variaciones in SINONIMOS_TIPOS.items():
        if clave in lote_tipo_norm:
            for var in variaciones:
                if var in ficha_producto_norm: return 1
    return 0

# --- CARGA DE DATOS CON CACHÉ ---
@st.cache_data(ttl=3600)
def cargar_fichas_tecnicas(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    
    cols_map = {normalizar_texto(c): c for c in df.columns}
    
    def get_col(keywords):
        for k in keywords:
            kn = normalizar_texto(k)
            for cn, cr in cols_map.items():
                if kn in cn: return cr
        return None

    c_cod = get_col(['codigo ft', 'cod'])
    c_cli = get_col(['cliente'])
    c_fam = get_col(['familia', 'family'])
    c_prod = get_col(['producto', 'descripción'])
    c_tipo = get_col(['tipo'])
    c_param = get_col(['analisis', 'parametro'])
    c_min = get_col(['min', 'mínimo'])
    c_max = get_col(['max', 'máximo'])

    if not all([c_cod, c_cli, c_prod, c_tipo, c_param, c_min, c_max]):
        return None, "Faltan columnas clave en Fichas"

    df['min_val'] = pd.to_numeric(df[c_min], errors='coerce').fillna(0)
    df['max_val'] = pd.to_numeric(df[c_max], errors='coerce').fillna(float('inf'))

    db_fichas = {}
    for cod, grupo in df.groupby(c_cod):
        first = grupo.iloc[0]
        cliente = str(first[c_cli])
        if "_Cliente de PruebaX" in cliente or "NO BORRAR" in cliente: continue

        familia_txt = str(first[c_fam]) if c_fam else ""
        prod_txt = str(first[c_prod])
        es_ficha_gf = es_texto_gf(familia_txt) or es_texto_gf(prod_txt)
        
        fam_norm = detectar_familia_hoja(familia_txt)
        prod_norm = normalizar_texto(prod_txt)
        
        if 'harina' in prod_norm: fam_norm = 'harina'
        elif 'avena pelada' in prod_norm: fam_norm = 'groat'
        elif 'pillow' in prod_norm: fam_norm = 'pillow'
        elif 'hojuela' in prod_norm or 'laminada' in prod_norm: fam_norm = 'hojuela'

        params = []
        for _, row in grupo.iterrows():
            if str(row[c_tipo]).lower().strip() == 'analisis':
                p_norm = normalizar_texto(row[c_param])
                tipo_param = 'otro'
                if 'espesor' in p_norm: tipo_param = 'espesor'
                elif any(x in p_norm for x in ['malla', 'ret', 'bajo', 'a traves']): tipo_param = 'malla'
                
                params.append({
                    'nombre': row[c_param],
                    'nombre_norm': p_norm,
                    'min': row['min_val'],
                    'max': row['max_val'],
                    'tipo_param': tipo_param
                })
        
        if params:
            db_fichas[cod] = {
                'cliente': cliente,
                'familia_norm': fam_norm,
                'producto': prod_txt,
                'producto_norm': prod_norm,
                'es_gf': es_ficha_gf,
                'params': params
            }
    return db_fichas, None

@st.cache_data(ttl=600)
def cargar_planta_completa(file, hoja):
    return pd.read_excel(file, sheet_name=hoja, header=1)

# --- UTILIDAD DE BÚSQUEDA ---
def encontrar_columna_opt(cols_norm_dict, keywords):
    for key in keywords:
        key_norm = normalizar_texto(key)
        for col_norm, col_real in cols_norm_dict.items():
            if key_norm in col_norm: return col_real
    return None

def es_match_granulometria(header_ficha_norm, header_planta_norm):
    nums_f = re.search(r'\d+', header_ficha_norm)
    nums_p = re.search(r'\d+', header_planta_norm)
    
    if not nums_f or not nums_p: return False
    if nums_f.group() != nums_p.group(): return False

    vocab_bajo = {'a traves', 'bajo', 'pasa', 'menor', '<', 'fondo', 'base', 'minus'}
    vocab_sobre = {'retencion', 'retenido', 'sobre', 'arriba', 'mayor', '>', 'encima', 'ret'}

    dir_f = 'bajo' if any(k in header_ficha_norm for k in vocab_bajo) else ('sobre' if any(k in header_ficha_norm for k in vocab_sobre) else 'u')
    dir_p = 'bajo' if any(k in header_planta_norm for k in vocab_bajo) else ('sobre' if any(k in header_planta_norm for k in vocab_sobre) else 'u')

    return dir_f != 'u' and dir_p != 'u' and dir_f == dir_p

# --- UI PRINCIPAL ---
col1, col2 = st.columns(2)
file_prod = col1.file_uploader("1. Excel Planta (Control)", type=['xlsx', 'xls'])
file_fichas = col2.file_uploader("2. Fichas Técnicas", type=['xlsx', 'xls', 'csv'])

if file_prod and file_fichas:
    # 1. CARGAR FICHAS
    db_fichas, error = cargar_fichas_tecnicas(file_fichas)
    if error:
        st.error(error)
        st.stop()

    # 2. SELECCIONAR HOJA
    xls = pd.ExcelFile(file_prod)
    hoja_sel = st.selectbox("Selecciona Hoja de Planta:", xls.sheet_names)
    
    # 3. CARGAR PLANTA
    df_planta = cargar_planta_completa(file_prod, hoja_sel)
    
    cols_planta_norm = {normalizar_texto(c): c for c in df_planta.columns}
    
    c_status = encontrar_columna_opt(cols_planta_norm, ['estado', 'status'])
    c_lote = encontrar_columna_opt(cols_planta_norm, ['lote', 'batch', 'n° lote'])
    c_folio = encontrar_columna_opt(cols_planta_norm, ['folio', 'id muestra'])
    c_cond = encontrar_columna_opt(cols_planta_norm, ['condición', 'condicion', 'gf'])
    c_tipo = encontrar_columna_opt(cols_planta_norm, ['tipo de producto', 'variedad'])
    c_cli_orig = encontrar_columna_opt(cols_planta_norm, ['cliente', 'customer'])
    c_motivo = encontrar_columna_opt(cols_planta_norm, ['motivo', 'razon'])
    c_fecha = encontrar_columna_opt(cols_planta_norm, ['fecha etiqueta', 'fecha producción', 'date'])

    col_agrupacion = c_lote if c_lote else c_folio

    if not c_status:
        st.error("❌ Falta columna ESTADO")
        st.stop()

    # --- FILTRO FECHA ---
    if c_fecha:
        df_planta[c_fecha] = pd.to_datetime(df_planta[c_fecha], errors='coerce')
        hoy = datetime.now().date()
        date1, date2 = st.columns(2)
        with date1:
            rango = st.date_input("Filtrar Fecha:", (hoy - timedelta(days=30), hoy), format="DD/MM/YYYY")
        
        if isinstance(rango, tuple) and len(rango) == 2:
            mask = (df_planta[c_fecha].dt.date >= rango[0]) & (df_planta[c_fecha].dt.date <= rango[1])
            df_planta_filtrada = df_planta[mask].copy()
        else:
            df_planta_filtrada = df_planta.copy()
    else:
        df_planta_filtrada = df_planta.copy()

    # =========================================================
    # 🚨 IMPUTACIÓN DE DATOS REFORZADA 🚨
    # =========================================================
    
    # 1. FORZAR CONVERSIÓN NUMÉRICA
    # Identificamos columnas que NO son metadatos y tratamos de convertirlas a números.
    # Esto es crucial para que "Promedio Espesor" no se quede como 'object' si tiene NaNs o texto vacío.
    cols_meta = [c_status, c_lote, c_folio, c_cond, c_tipo, c_cli_orig, c_motivo, c_fecha]
    cols_potenciales = [c for c in df_planta_filtrada.columns if c not in cols_meta and c is not None]
    
    for col in cols_potenciales:
        # errors='coerce' convierte texto no válido en NaN, permitiendo el cálculo de promedios
        df_planta_filtrada[col] = pd.to_numeric(df_planta_filtrada[col], errors='coerce')

    # 2. Selección de columnas numéricas (ahora sí incluye todas)
    cols_num = df_planta_filtrada.select_dtypes(include=[np.number]).columns
    
    # 3. Crear máscara booleana de dónde faltan datos ANTES de rellenar
    # (Para mostrar visualmente después)
    mask_imputados = df_planta_filtrada[cols_num].isna()
    
    # 4. Calcular promedio global como respaldo
    global_means = df_planta_filtrada[cols_num].mean() 
    
    # 5. Rellenar con promedio del LOTE (Prioridad 1)
    if col_agrupacion:
        df_planta_filtrada[cols_num] = df_planta_filtrada.groupby(col_agrupacion)[cols_num].transform(lambda x: x.fillna(x.mean()))
    
    # 6. Rellenar vacíos restantes con promedio GLOBAL (Prioridad 2)
    df_planta_filtrada[cols_num] = df_planta_filtrada[cols_num].fillna(global_means)

    # Filtrar Retenidos
    mask_ret = df_planta_filtrada[c_status].astype(str).apply(normalizar_texto).str.contains('retenido', na=False)
    df_retenidos = df_planta_filtrada[mask_ret]
    
    # Filtrar también la máscara de imputados para alinear índices
    mask_imputados_ret = mask_imputados[mask_ret]

    st.info(f"Procesando {len(df_retenidos)} lotes.")

    # --- PRE-MAPEO COLUMNAS ---
    mapa_columnas_fichas = {} 

    for cod_ft, ficha in db_fichas.items():
        mapa_columnas_fichas[cod_ft] = {}
        for p in ficha['params']:
            p_norm = p['nombre_norm']
            col_match = None
            
            # 1. Exacta
            if p_norm in cols_planta_norm:
                col_match = cols_planta_norm[p_norm]
            
            # 2. Diccionario
            if not col_match:
                for key, aliases in MAPEO_PARAMETROS.items():
                    if key in p_norm:
                        for alias in aliases:
                            alias_norm = normalizar_texto(alias)
                            matches = [v for k,v in cols_planta_norm.items() if alias_norm in k]
                            if matches:
                                col_match = matches[0]
                                break
                    if col_match: break
            
            # 3. Espesor
            if not col_match and p['tipo_param'] == 'espesor':
                matches = [v for k,v in cols_planta_norm.items() if 'promedio' in k and 'espesor' in k]
                if matches: col_match = matches[0]

            # 4. Granulometría
            if not col_match and p['tipo_param'] == 'malla':
                for k, v in cols_planta_norm.items():
                    if es_match_granulometria(p_norm, k):
                        col_match = v
                        break
            
            # 5. Difusa
            if not col_match and p_norm != 'humedad':
                best_r = 0
                best_c = None
                for k, v in cols_planta_norm.items():
                    r = SequenceMatcher(None, p_norm, k).ratio()
                    if r > best_r:
                        best_r = r
                        best_c = v
                if best_r > 0.8: col_match = best_c

            mapa_columnas_fichas[cod_ft][p['nombre']] = col_match

    # --- BUCLE PRINCIPAL ---
    fam_lote = detecting_fam = detectar_familia_hoja(hoja_sel)
    es_hoja_gf = es_texto_gf(hoja_sel)

    keys_tech = ['humedad', 'espesor', 'malla', 'ret', 'bajo', 'sobre', 'densidad', 'gelatina', 'quemada', 'peroxido', 'acidez', 'materia']

    for idx, row in df_retenidos.iterrows():
        folio_txt = str(row[c_folio]) if c_folio else f"{idx}"
        lote_txt = str(row[c_lote]) if c_lote else "N/A"
        cond_val = str(row[c_cond]) if c_cond else ""
        es_lote_gf = es_hoja_gf or es_texto_gf(cond_val)
        tipo_esp = str(row[c_tipo]) if c_tipo else ""
        tipo_esp_norm = normalizar_texto(tipo_esp)
        
        datos_resumen = {}
        for col in df_planta.columns:
            cn = normalizar_texto(col)
            if any(k in cn for k in keys_tech):
                val = row[col]
                
                # Verificar imputación
                es_imputado = False
                if col in mask_imputados_ret.columns:
                    if mask_imputados_ret.loc[idx, col]:
                        es_imputado = True

                if isinstance(val, (int, float, np.number)):
                     try: 
                         fmt_val = f"{float(val):.2f}"
                         if es_imputado: fmt_val += " (Auto)"
                         datos_resumen[col[:20]] = fmt_val
                     except: pass

        candidatos = []

        for cod_ft, ficha in db_fichas.items():
            
            if es_lote_gf:
                if not ficha['es_gf']: continue
            else:
                if fam_lote in ['harina', 'hojuela', 'pillow'] and ficha['es_gf']: continue

            if fam_lote != 'otros':
                if fam_lote == 'hojuela' and ficha['familia_norm'] == 'harina': continue
                if fam_lote == 'harina' and ficha['familia_norm'] == 'hojuela': continue
                if ficha['familia_norm'] != fam_lote and ficha['familia_norm'] != 'otros':
                     if not (fam_lote in ['hojuela', 'pillow'] and ficha['familia_norm'] in ['hojuela', 'pillow']):
                         continue

            score_txt = 0
            if check_tipo_producto_score(tipo_esp_norm, ficha['producto_norm']): score_txt = 2

            aciertos = 0
            encontrados = 0
            detalles = []
            compatible = True

            for p in ficha['params']:
                col_real = mapa_columnas_fichas[cod_ft].get(p['nombre'])
                
                estado = "⚪"
                val_str = "---"
                
                if col_real:
                    encontrados += 1
                    val_num = row[col_real] # Valor numérico REAL para el cálculo
                    
                    # Verificación de imputación para este parámetro específico
                    es_imputado_param = False
                    if col_real in mask_imputados_ret.columns:
                        if mask_imputados_ret.loc[idx, col_real]:
                            es_imputado_param = True

                    if isinstance(val_num, (int, float, np.number)) and not np.isnan(val_num):
                        val_str = f"{val_num:.2f}"
                        
                        # Marca visual SOLO en el string de visualización
                        if es_imputado_param:
                            val_str += " 🔄"
                        
                        # CÁLCULO MATEMÁTICO PURO (Sin afectar por la marca)
                        if p['min'] <= val_num <= p['max']:
                            aciertos += 1
                            estado = "✅ Cumple"
                        else:
                            compatible = False
                            estado = "❌ Fuera"
                    else:
                        compatible = False
                        estado = "⚠️ Error"
                        val_str = str(val_num)
                
                detalles.append({
                    "Parámetro": p['nombre'],
                    "Rango": f"{p['min']} - {p['max']}",
                    "Columna": col_real if col_real else "No encontrada",
                    "Valor": val_str,
                    "Estado": estado
                })

            if compatible and encontrados > 0:
                pct = (aciertos / encontrados) * 100
                candidatos.append({
                    'Cliente': ficha['cliente'],
                    'Producto': ficha['producto'],
                    'Score': pct,
                    'Txt': score_txt,
                    'Match': f"{aciertos}/{encontrados}",
                    'Detalle': detalles,
                    'N': encontrados
                })

        candidatos.sort(key=lambda x: (x['Txt'], x['Score'], x['N']), reverse=True)
        
        gf_lbl = " (GF)" if es_lote_gf else ""
        motivo = str(row[c_motivo]) if c_motivo else ""
        orig = str(row[c_cli_orig]) if c_cli_orig else ""
        mejor = candidatos[0]['Cliente'] if candidatos else "Ninguno"
        if candidatos and candidatos[0]['Txt']>0: mejor += " ⭐"

        head = f"📦 Folio: {folio_txt} | Lote: {lote_txt} | Prod: {tipo_esp}{gf_lbl} | {motivo} ➡️ {mejor}"
        
        with st.expander(head):
            if datos_resumen:
                st.dataframe(pd.DataFrame([datos_resumen]), use_container_width=True, hide_index=True)
            
            if candidatos:
                for c in candidatos:
                    icon = "⭐" if c['Txt'] > 0 else "📄"
                    sub_head = f"{icon} {c['Cliente']} | {c['Producto']} | {c['Score']:.0f}% ({c['Match']})"
                    with st.expander(sub_head):
                        st.dataframe(pd.DataFrame(c['Detalle']), use_container_width=True, hide_index=True)
            else:
                st.warning("Sin candidatos compatibles.")
