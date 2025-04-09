import streamlit as st
from database import get_db_connection

# 1. Configuración de página PRIMERO
st.set_page_config(
    page_title="QGenerator Pro",
    page_icon="❓",
    layout="wide",
    initial_sidebar_state="expanded", # La barra lateral puede aparecer brevemente, pero su contenido se controla después
)

# 2. Verificación de inicio de sesión INMEDIATAMENTE después
if not st.experimental_user.is_logged_in:
    # Muestra solo el mensaje y botón de inicio de sesión, y detiene todo lo demás
    st.warning("🔒 Necesitas iniciar sesión para usar esta aplicación.")
    if st.button("👤 Iniciar sesión con Google"):
        st.login()
    st.stop() # Detiene la ejecución del script aquí si no está logueado


# 3. Conexión a BD (ahora que sabemos que el usuario está logueado)
try:
    conn = get_db_connection()
    db_ready = conn is not None
except Exception:
    db_ready = False

# 4. Título y contenido principal (visible solo para usuarios logueados)
st.title("Bienvenido a QGenerator Pro 🧠")

st.markdown("""
Esta aplicación utiliza modelos de lenguaje locales (a través de LM Studio) y OCR
para generar automáticamente preguntas de opción múltiple a partir de documentos PDF.

**Funcionalidades:**

*   **📚 Generar Preguntas:** Sube un PDF para extraer texto y generar preguntas.
*   **✍️ Realizar Cuestionario:** Pon a prueba tus conocimientos con las preguntas generadas usando Active Recall.
*   **📊 Estadísticas Usuario:** Revisa tu rendimiento personal en los cuestionarios.
*   **⚙️ Admin Dashboard:** Supervisa el uso y rendimiento del sistema.

**Selecciona una opción en la barra lateral izquierda para comenzar.**
""")

# 5. Configuración de la barra lateral (visible solo para usuarios logueados)
with st.sidebar:
    st.divider()
    try:
        st.write(f"Bienvenido/a, **{st.experimental_user.name}**!")
        st.caption(st.experimental_user.email)
        st.button("🚪 Cerrar Sesión", on_click=st.logout, key="logout_button_sidebar")
    except Exception as e:
        st.error("Hubo un problema al mostrar la información del usuario.")
        st.exception(e)

    st.sidebar.divider()
    st.sidebar.markdown("--- \n *Investigación en curso*")

    # Muestra estado de BD en la barra lateral
    if db_ready:
        st.sidebar.success("Conexión a BD exitosa.")
    else:
        st.sidebar.error("Error en conexión a BD.")

