import streamlit as st
from database import get_db_connection, registrar_inicio_sesion_db, registrar_fin_sesion_db # Corrected imports
import logging
from datetime import datetime # For st.func.now() replacement in logout (though now handled by _db func)

# 1. Configuración de página PRIMERO
st.set_page_config(
    page_title="MemorIA",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- REMOVED local session functions, will use _db versions from database.py ---

# 2. Flujo de Autenticación INMEDIATAMENTE después de la configuración de página
if not st.user.is_logged_in:
    st.warning("🔒 Necesitas iniciar sesión para usar esta aplicación.")
    st.button("👤 Iniciar sesión con Google", on_click=st.login) 
    st.stop() 

# --- Si el usuario está logueado, continuamos ---

conn = None
db_ready = False
try:
    conn = get_db_connection() 
    db_ready = conn is not None
    if db_ready and 'current_user_session_db_id' not in st.session_state:
        session_db_id = registrar_inicio_sesion_db(conn, st.user.email) # Use _db version
        st.session_state.current_user_session_db_id = session_db_id
except Exception as e: 
    db_ready = False
    logging.error(f"Error crítico al conectar o inicializar sesión en BD: {e}", exc_info=True)
    st.error("Error crítico al conectar con la base de datos. Por favor, contacta al administrador.")
    st.stop() 

st.title(f"Bienvenido a MemorIA, {st.user.name}! 🧠") 

st.markdown("""
Esta aplicación utiliza modelos de lenguaje locales (a través de LM Studio) y OCR
para generar automáticamente preguntas de opción múltiple a partir de documentos PDF.

**Funcionalidades:**

*   **📚 Generar Preguntas:** Sube un PDF para extraer texto y generar preguntas.
*   **✍️ Realizar Cuestionario:** Pon a prueba tus conocimientos con las preguntas generadas usando Active Recall.
*   **📊 Estadísticas Usuario:** Revisa tu rendimiento personal en los cuestionarios.
*   **⚙️ Admin Dashboard:** Supervisa el uso y rendimiento del sistema (si tienes permisos).

**Selecciona una opción en la barra lateral izquierda para comenzar.**
""")

with st.sidebar:
    st.header("Navegación")

    st.divider()
    st.subheader("Información de Usuario")
    try:
        st.write(f"Usuario: **{st.user.name}**")
        st.caption(st.user.email)
        
        def logout_and_record():
            session_to_close = st.session_state.get('current_user_session_db_id')
            # Ensure conn is the one established earlier and is valid
            current_conn = get_db_connection() # Re-fetch or ensure conn from outer scope is used safely
            if current_conn and session_to_close: 
                registrar_fin_sesion_db(current_conn, session_to_close) # Use _db version
            
            # Clean up session state related to user session if any beyond current_user_session_db_id
            if 'current_user_session_db_id' in st.session_state:
                del st.session_state['current_user_session_db_id']
            
            st.logout() 

        st.button("🚪 Cerrar Sesión", on_click=logout_and_record, key="logout_button_sidebar")
    except Exception as e: 
        st.error("Hubo un problema al mostrar la información del usuario.")
        logging.error(f"Error en sidebar con info de usuario: {e}", exc_info=True)

    st.sidebar.divider()
    st.sidebar.markdown("--- \n *EXAMGEN - Investigación en curso*")

    if db_ready:
        st.sidebar.success("Conexión a BD: OK.")
    else:
        st.sidebar.error("Conexión a BD: Error.")