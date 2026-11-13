import streamlit as st
from pymongo import MongoClient
from thefuzz import process, fuzz
import re
import os

# 1. Configuración de página (SIEMPRE en la primera línea)
st.set_page_config(page_title="TRANSLOGEX ALERT | Sistema de alertas y validación", layout="wide")

# --- ESTILOS CSS CORPORATIVOS (PALETA TRANSLOGEX S.A.S.) ---
st.markdown("""
<style>
    /* Botones con identidad corporativa Translogex */
    div.stButton > button:first-child, div.stFormSubmitButton > button:first-child {
        background-color: #843463;
        color: white;
        border-radius: 6px;
        padding: 10px 24px;
        font-weight: 600;
        border: none;
        letter-spacing: 0.5px;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:first-child:hover, div.stFormSubmitButton > button:first-child:hover {
        background-color: #632549;
        color: white;
    }
    
    /* Encabezado del Login centrado y limpio */
    .login-header {
        text-align: center;
        padding-bottom: 18px;
        margin-bottom: 22px;
        border-bottom: 3px solid #843463;
    }
    .login-brand {
        font-size: 2.1rem;
        font-weight: 800;
        color: #843463;
        letter-spacing: 1.5px;
        margin: 0;
        line-height: 1.2;
        text-transform: uppercase;
    }
    .login-subtitle {
        font-size: 1.05rem;
        font-weight: 600;
        color: #1E1E1E;
        letter-spacing: 0.5px;
        margin-top: 6px;
    }
    .login-caption {
        font-size: 0.88rem;
        color: #64748B;
        margin-top: 8px;
    }

    /* Encabezado del Panel Principal */
    .main-header {
        border-left: 5px solid #843463;
        padding-left: 16px;
        margin-bottom: 16px;
    }
    .main-brand {
        font-size: 2.2rem;
        font-weight: 800;
        color: #843463;
        letter-spacing: 1.2px;
        margin: 0;
        line-height: 1.15;
    }
    .main-subtitle {
        font-size: 1.15rem;
        font-weight: 600;
        color: #1E1E1E;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE CREDENCIALES (4 USUARIOS Y 4 CONTRASEÑAS) ---
USUARIOS_AUTORIZADOS = {
    "admin_aml": "Cumplimiento2026*",
    "analista_senior": "Auditoria#849",
    "gerencia_riesgos": "Directivo$AML99",
    "operaciones_oplg": "Logistica%753"
}

# Inicializar estado de sesión
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = ""

# --- PANTALLA DE INICIO DE SESIÓN ---
if not st.session_state["autenticado"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.3, 1])
    
    with col_l2:
        st.markdown("""
        <div class="login-header">
            <div class="login-brand">TRANSLOGEX ALERT</div>
            <div class="login-subtitle">Sistema de alertas y validación</div>
            <div class="login-caption">Plataforma corporativa de debida diligencia y cumplimiento normativo</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("formulario_login", clear_on_submit=False):
            usuario_input = st.text_input("Usuario", placeholder="Ingrese su usuario")
            clave_input = st.text_input("Contraseña", type="password", placeholder="Ingrese su contraseña")
            st.markdown("<br>", unsafe_allow_html=True)
            btn_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if btn_login:
                usuario_limpio = usuario_input.strip()
                if usuario_limpio in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario_limpio] == clave_input:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = usuario_limpio
                    st.rerun()
                else:
                    st.error("Credenciales inválidas. Verifique su usuario y contraseña.")
                    
    st.stop()

# =====================================================================
# A PARTIR DE AQUÍ SOLO SE EJECUTA SI EL USUARIO INICIÓ SESIÓN CON ÉXITO
# =====================================================================

# --- FUNCIONES DEL MOTOR DE DATOS ---
def traducir_fuentes(fuentes_crudas):
    if "OPENSANCTIONS" in fuentes_crudas:
        traducciones_agencias = {
            "UA_": "Ucrania", "NZ_": "Nueva Zelanda", "EU_": "Unión Europea",
            "FR_": "Francia", "MC_": "Mónaco", "CA_": "Canadá", "GB_": "Reino Unido",
            "AU_": "Australia", "CH_": "Suiza", "BE_": "Bélgica", "JP_": "Japón",
            "US_": "EE. UU.", "UN_": "ONU", "PL_": "Polonia", "IL_": "Israel"
        }
        paises_detectados = set([pais for clave, pais in traducciones_agencias.items() if clave in fuentes_crudas])
        if paises_detectados:
            return "OpenSanctions (Agencias de: " + ", ".join(list(paises_detectados)) + ")"
        return "OpenSanctions (Listas Consolidadas Globales)"
    return fuentes_crudas

def traducir_motivos(programas_crudos):
    if not programas_crudos or programas_crudos == "No especificado": return "Motivo no especificado"
    diccionario_delitos = {
        "SDGT": "Terrorismo Internacional", "SDNTK": "Narcotráfico (Carteles)",
        "SDNT": "Narcotráfico", "VENEZUELA": "Corrupción o Abuso de DD.HH. (Venezuela)",
        "IRAN-CON-ARMS-EO": "Tráfico de Armas (Irán)", "SYRIA": "Conflicto / Violación de DD.HH. (Siria)",
        "CYBER2": "Ciberdelincuencia", "TCO": "Crimen Organizado Transnacional",
        "NPWMD": "Armas de Destrucción Masiva", "RUSSIA-EO14024": "Sanciones (Rusia)",
        "GLOBAL-MAGNITSKY": "Corrupción y Violación de DD.HH.", "FTO": "Organización Terrorista",
        "SANCIONES INTERNACIONALES": "Sanciones Financieras Internacionales"
    }
    texto_limpio = programas_crudos.replace("[", " ").replace("]", " ")
    motivos = [delito for codigo, delito in diccionario_delitos.items() if codigo in texto_limpio]
    return " | ".join(motivos) if motivos else programas_crudos

def generar_resumen_espanol(texto_crudo):
    if not texto_crudo or texto_crudo == "No hay detalles públicos adicionales.":
        return "No hay información adicional registrada."
    texto = texto_crudo
    diccionario_forzado = {
        "DOB": "Fecha de nacimiento:", "POB": "Lugar de nacimiento:", "a.k.a.": "Alias:", "Gender": "Género:", "Male": "Masculino", "Female": "Femenino",
        "Secondary sanctions risk:": "Riesgo de sanciones secundarias:", "Transactions Prohibited For Persons Owned or Controlled By U.S. Financial Institutions:": "Transacciones prohibidas para instituciones financieras de EE. UU.:",
        "North Korea Sanctions Regulations": "Regulaciones de Sanciones a Corea del Norte", "sections": "secciones", "section": "sección", "Executive Order": "Orden Ejecutiva",
        " Jan ": " Ene ", " Feb ": " Feb ", " Mar ": " Mar ", " Apr ": " Abr ", " May ": " May ", " Jun ": " Jun ", " Jul ": " Jul ", " Aug ": " Ago ", " Sep ": " Sep ", " Oct ": " Oct ", " Nov ": " Nov ", " Dec ": " Dic "
    }
    for ingles, espanol in diccionario_forzado.items(): texto = texto.replace(ingles, espanol)
    texto = re.sub(r'(\d{4})-(\d{2})-(\d{2})', r'\3/\2/\1', texto)
    paises_iso = {"ru": "Rusia", "pt": "Portugal", "il": "Israel", "ve": "Venezuela", "ir": "Irán", "kp": "Corea del Norte", "sy": "Siria", "cu": "Cuba", "cn": "China", "af": "Afganistán", "us": "EE. UU.", "gb": "Reino Unido", "co": "Colombia", "mx": "México", "es": "España"}
    partes_finales = []
    for parte in texto.split(";"):
        p = parte.strip()
        if not p: continue
        p = p.replace("Fecha de nacimiento: ", "Fecha de nacimiento: ").replace("Dob ", "Fecha de nacimiento: ")
        if p.lower().startswith("nacionalidad:") or p.lower().startswith("ciudadanía:") or p.lower().startswith("ciudadano "):
            partes_split = p.split(":", 1)
            if len(partes_split) == 2:
                nombres_paises = [paises_iso.get(c.strip().lower(), c.strip()) for c in partes_split[1].split(",")]
                p = f"{partes_split[0]}: " + ", ".join(nombres_paises)
        p = p[0].upper() + p[1:]
        partes_finales.append(f"- {p}")
    return "\n".join(partes_finales)

# --- CONEXIÓN SEGURA A MONGODB ---
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    st.error("Error de Seguridad: No se detectaron las credenciales de la base de datos (Falta Variable de Entorno MONGO_URI).")
    st.stop()

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI)

client = init_connection()
coleccion = client["antecedentes_db"]["sanciones"]

# --- BARRA LATERAL ---
with st.sidebar:
    st.caption(f"Sesión activa: **{st.session_state['usuario_actual']}**")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = ""
        st.rerun()
        
    st.divider()
    
    st.title("Enlaces Oficiales")
    st.markdown("Portales gubernamentales e internacionales para validación manual de debida diligencia.")
    
    st.divider()

    # Sección Internacionales
    st.subheader("Internacionales")
    st.markdown("""
    * 🔗 [OFAC (Sanciones EE.UU.)](https://sanctionssearch.ofac.treas.gov/)
    * 🔗 [ONU (Lista Consolidada)](https://www.un.org/securitycouncil/es/content/un-sc-consolidated-list)
    * 🔗 [Interpol (Notificaciones Rojas)](https://www.interpol.int/es/Como-trabajamos/Notificaciones/Notificaciones-rojas/Ver-las-notificaciones-rojas)
    * 🔗 [Unión Europea (Sanciones)](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=OJ:L:2022:025:TOC)
    * 🔗 [State Dept (FTO Terrorismo)](https://www.state.gov/foreign-terrorist-organizations/)
    """)

    st.divider()
    
    # Sección Colombia
    st.subheader("República de Colombia")
    st.markdown("""
    * 🔗 [Policía Nacional (Penales)](https://antecedentes.policia.gov.co:7005/WebJudicial/)
    * 🔗 [Contraloría (Resp. Fiscal)](https://www.contraloria.gov.co/control-fiscal/responsabilidad-fiscal/certificado-de-antecedentes-fiscales)
    * 🔗 [Procuraduría (Disciplinarios)](https://www.procuraduria.gov.co/Pages/Consulta-de-Antecedentes.aspx)
    * 🔗 [SIMIT (Multas de Tránsito)](https://www.fcm.org.co/simit/#/home-public)
    """)
    
    st.divider()
    
    # Sección Ecuador
    st.subheader("República del Ecuador")
    st.markdown("""
    * 🔗 [Min. del Interior (Penales)](https://certificados.ministeriodelinterior.gob.ec/gestorcertificados/antecedentes/)
    * 🔗 [Función Judicial (Causas / SATJE)](http://consultas.funcionjudicial.gob.ec/informacionjudicial/public/informacion.jsf)
    * 🔗 [ANT (Multas de Tránsito)](https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_criterio_consulta.jsp)
    """)

# --- INTERFAZ VISUAL PRINCIPAL ---
st.markdown("""
<div class="main-header">
    <div class="main-brand">TRANSLOGEX ALERT</div>
    <div class="main-subtitle">Sistema de alertas y validación</div>
</div>
""", unsafe_allow_html=True)

st.markdown("Sistema automatizado de cruce de datos contra listas restrictivas y vinculantes a nivel global: \n**Oficina de Control de Activos Extranjeros (OFAC SDN & Non-SDN), Consejo de Seguridad de las Naciones Unidas (ONU), Organización Internacional de Policía Criminal (Interpol - Notificaciones Rojas), Sanciones Financieras de la Unión Europea (UE), Departamento de Estado de EE.UU. (Organizaciones Terroristas Extranjeras - FTO) y más de 15 agencias gubernamentales internacionales consolidadas.**")
st.divider()

col_izq, col_centro, col_der = st.columns([1, 2, 1])
with col_centro:
    with st.form("formulario_busqueda", clear_on_submit=False):
        st.subheader("Datos de Búsqueda")
        col_nom, col_ape = st.columns(2)
        with col_nom: nombre = st.text_input("Nombre(s) *", placeholder="Ej: Nicolas")
        with col_ape: apellido = st.text_input("Apellido(s) *", placeholder="Ej: Maduro")
        cedula = st.text_input("Identificación (Opcional)", placeholder="Cédula o Pasaporte")
        st.markdown("<br>", unsafe_allow_html=True)
        boton = st.form_submit_button("Consultar Antecedentes", use_container_width=True)

# --- PROCESAMIENTO ---
if boton:
    if not nombre and not apellido:
        st.warning("Por favor, ingresa el nombre o el apellido para realizar la búsqueda.")
    else:
        with st.spinner("Buscando en bases de datos internacionales..."):
            nom_query = nombre.strip().upper()
            ape_query = apellido.strip().upper()
            coincidencias = []
            
            query_directa = {"$and": [{"nombre_completo": {"$regex": nom_query, "$options": "i"}}, {"nombre_completo": {"$regex": ape_query, "$options": "i"}}]}
            resultados = list(coleccion.find(query_directa, {"_id": 0}).limit(3))
            
            if resultados:
                for d in resultados:
                    obs = str(d.get("observaciones", "No hay detalles públicos adicionales."))
                    coincidencias.append({"nombre_sancionado": d.get("nombre_completo"), "similitud_porcentaje": 100, "detalles": {"fuente": traducir_fuentes(d.get("fuente", "")), "motivo_delito": traducir_motivos(d.get("programas", "")), "programas_originales": d.get("programas", ""), "antecedentes_original": obs, "resumen_espanol": generar_resumen_espanol(obs)}})
            else:
                input_completo = f"{nom_query} {ape_query}".strip()
                condiciones = []
                if nom_query: condiciones.append({"nombre_completo": {"$regex": nom_query, "$options": "i"}})
                if ape_query: condiciones.append({"nombre_completo": {"$regex": ape_query, "$options": "i"}})
                
                if condiciones:
                    registros_db = list(coleccion.find({"$or": condiciones}, {"_id": 0}).limit(100))
                    lista_nombres = [r["nombre_completo"] for r in registros_db if "nombre_completo" in r]
                    
                    if lista_nombres:
                        fuzzy_results = process.extract(input_completo, lista_nombres, limit=3, scorer=fuzz.token_set_ratio)
                        for n_encontrado, score in fuzzy_results:
                            if score >= 85:
                                d = next((item for item in registros_db if item["nombre_completo"] == n_encontrado), None)
                                if d:
                                    obs = str(d.get("observaciones", "No hay detalles públicos adicionales."))
                                    coincidencias.append({"nombre_sancionado": n_encontrado, "similitud_porcentaje": score, "detalles": {"fuente": traducir_fuentes(d.get("fuente", "")), "motivo_delito": traducir_motivos(d.get("programas", "")), "programas_originales": d.get("programas", ""), "antecedentes_original": obs, "resumen_espanol": generar_resumen_espanol(obs)}})

            st.divider() 
            if not coincidencias:
                st.success(f"ESTADO: APROBADO - No se encontraron registros en las listas restrictivas vinculantes para: {nombre} {apellido}.")
            else:
                st.error("ESTADO: ALERTA - Se encontraron posibles coincidencias en las bases de datos.")
                st.markdown("<br>", unsafe_allow_html=True)
                
                agrupados = {}
                for c in coincidencias:
                    n_match = c["nombre_sancionado"]
                    if n_match not in agrupados: agrupados[n_match] = {"similitud": c["similitud_porcentaje"], "registros": []}
                    agrupados[n_match]["registros"].append(c["detalles"])
                
                for nombre_match, info in agrupados.items():
                    with st.container():
                        st.markdown(f"### Objetivo: {nombre_match}")
                        st.caption(f"Nivel de Similitud: {info['similitud']}%")
                        st.progress(int(info['similitud']))
                        
                        pestañas = st.tabs([det["fuente"] for det in info["registros"]])
                        for i, pestaña in enumerate(pestañas):
                            with pestaña:
                                det = info["registros"][i]
                                col1, col2 = st.columns(2)
                                with col1: st.error(f"**Motivos / Delitos:**\n\n{det.get('motivo_delito', 'No especificado')}")
                                with col2: st.info(f"**Fuente Original:**\n\n{det.get('fuente', 'Desconocida')}")
                                st.success(f"**Resumen de Perfil:**\n\n{det.get('resumen_espanol', '')}")
                                with st.expander("Ver registro técnico original (Inglés)"):
                                    st.write(f"**Programa Legal:** {det.get('programas_originales', '')}")
                                    st.write(det.get('antecedentes_original', ''))
                    st.divider()