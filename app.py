import logging

import streamlit as st

import auth_helpers as auth
from database import (
    get_db_connection,
    registrar_fin_sesion_db,
    registrar_inicio_sesion_db,
)

logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="MemorIA",
    layout="wide",
    initial_sidebar_state="expanded",
)


user_info = auth.ensure_authenticated(
    login_title="Bienvenido a MemorIA",
    login_message="Inicia sesión con tu cuenta central de SARA para continuar.",
)
try:
    user_identity = auth.get_data_identity(user_info)
except auth.AuthError:
    logger.error("Central identity mapping rejected.")
    st.error("No se pudo abrir el historial de esta cuenta.")
    st.stop()


conn = None
db_ready = False
try:
    conn = get_db_connection()
    db_ready = conn is not None
    if db_ready and "current_user_session_db_id" not in st.session_state:
        session_db_id = registrar_inicio_sesion_db(conn, user_identity)
        st.session_state.current_user_session_db_id = session_db_id
except Exception:
    db_ready = False
    logger.error("Database connection or session initialization failed.")
    st.error(
        "Error crítico al conectar con la base de datos. Por favor, contacta al administrador."
    )
    st.stop()

st.title(f"Bienvenido a MemorIA, {auth.display_name(user_info)}")

st.markdown("""
Esta aplicación utiliza modelos de lenguaje locales (a través de LM Studio) y OCR
para generar automáticamente preguntas de opción múltiple a partir de documentos PDF.

**Funcionalidades:**

*   **Generar Preguntas:** Sube un PDF para extraer texto y generar preguntas.
*   **Realizar Cuestionario:** Pon a prueba tus conocimientos con las preguntas generadas usando Active Recall.
*   **Estadísticas Usuario:** Revisa tu rendimiento personal en los cuestionarios.
*   **Admin Dashboard:** Supervisa el uso y rendimiento del sistema (si tienes permisos).

**Selecciona una opción en la barra lateral izquierda para comenzar.**
""")

with st.sidebar:
    st.header("Navegación")

    st.divider()
    st.subheader("Información de Usuario")
    st.write(f"Usuario: **{auth.display_name(user_info)}**")
    email = user_info.get("email")
    if isinstance(email, str) and email:
        st.caption(email)
    if st.button("Cerrar Sesión", key="logout_button_sidebar"):
        session_to_close = st.session_state.get("current_user_session_db_id")
        try:
            current_conn = get_db_connection()
            if current_conn and session_to_close:
                registrar_fin_sesion_db(current_conn, session_to_close)
        except Exception:
            logger.warning("Product session close could not be recorded.")
        auth.logout()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("ExamGen")

    if db_ready:
        st.sidebar.success("Conexión a BD: OK.")
    else:
        st.sidebar.error("Conexión a BD: Error.")
