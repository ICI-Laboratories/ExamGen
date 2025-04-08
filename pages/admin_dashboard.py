# --- START OF FILE pages/4_⚙️_Admin_Dashboard.py ---
import streamlit as st
from database import (
    get_db_connection,
    get_generation_logs,
    get_overall_document_stats,
    get_user_activity_summary,
    obtener_documentos_cargados # Necesario para el filtro de documentos
)
# Importar la nueva función de estadísticas
from estadisticas import obtener_estadisticas_todas_las_preguntas
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging

# --- Autenticación y Autorización Admin (como antes) ---
if not st.experimental_user.is_logged_in:
    st.warning("🔒 Por favor, inicia sesión para acceder.")
    st.stop()

is_admin = False
try:
    admin_email_list = st.secrets.get("auth", {}).get("admin_emails", [])
    if not isinstance(admin_email_list, list):
        logging.error("La configuración 'admin_emails' en secrets.toml no es una lista válida.")
        st.error("Error interno de configuración de permisos.")
        st.stop()
    current_user_email = st.experimental_user.email.lower()
    authorized_admins = [email.lower() for email in admin_email_list]
    if current_user_email in authorized_admins:
        is_admin = True
    else:
        st.error("🚫 Acceso Denegado.")
        st.warning(f"El usuario **{st.experimental_user.email}** no tiene permisos para acceder a esta sección.")
        st.stop()
except Exception as e:
    logging.error(f"Error al verificar permisos de administrador: {e}")
    st.error("Ocurrió un error al verificar tus permisos.")
    st.stop()

# --- Contenido Principal del Dashboard Admin ---
st.header("⚙️ Admin Dashboard")
st.success(f"Acceso concedido para: {st.experimental_user.email}")
st.markdown("*Supervisión del sistema y estadísticas agregadas.*")

conn = get_db_connection()
if not conn:
    st.error("Conexión a base de datos no disponible.")
    st.stop()

# --- Secciones Anteriores (Métricas Clave, Documentos, Logs) ---
st.subheader("Métricas Clave del Sistema")
try:
    summary = get_user_activity_summary(conn)
    if summary:
        col1, col2, col3 = st.columns(3)
        col1.metric("Usuarios Activos (con respuestas)", summary.get('active_users', 0))
        col2.metric("Total Respuestas Registradas", summary.get('total_answers_recorded', 0))
        col3.metric("Documentos Procesados (con preguntas)", summary.get('documents_processed', 0))
    else:
        st.warning("No se pudo obtener el resumen de actividad.")
except Exception as e:
    st.error(f"Error cargando métricas clave: {e}")

st.divider()

st.subheader("Visión General de Documentos y Preguntas")
try:
    doc_stats = get_overall_document_stats(conn)
    if doc_stats:
        df_docs = pd.DataFrame(doc_stats)
        df_docs['created_at'] = pd.to_datetime(df_docs['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        df_docs['avg_response_time_secs'] = df_docs['avg_response_time_secs'].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
        df_docs['accuracy'] = df_docs['accuracy'].map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A")
        st.dataframe(df_docs[[
            'id', 'nombre', 'total_questions', 'total_responses', 'accuracy',
            'avg_response_time_secs', 'created_at', 'hash'
        ]].rename(columns={
             'id': 'Doc ID', 'nombre': 'Nombre Archivo', 'total_questions': 'Preguntas',
             'total_responses': 'Respuestas Totales', 'accuracy': 'Precisión Global',
             'avg_response_time_secs': 'Tiempo Prom Global (s)', 'created_at': 'Fecha Creación',
             'hash': 'Hash Preguntas'
        }), use_container_width=True)
        # ... (Gráfico de preguntas por documento) ...
        fig_q_per_doc, ax_q_per_doc = plt.subplots()
        df_chart_docs = df_docs.head(20).sort_values('total_questions', ascending=False)
        ax_q_per_doc.bar(df_chart_docs['nombre'], df_chart_docs['total_questions'], color='teal')
        ax_q_per_doc.set_ylabel('Número de Preguntas Generadas')
        ax_q_per_doc.set_title('Preguntas Generadas por Documento (Top 20)')
        plt.xticks(rotation=75, ha='right')
        st.pyplot(fig_q_per_doc)
    else:
        st.info("No hay estadísticas de documentos disponibles.")
except Exception as e:
    st.error(f"Error cargando estadísticas de documentos: {e}")

st.divider()

st.subheader("Registro de Generación de Preguntas Recientes")
try:
    logs = get_generation_logs(conn, limit=50)
    if logs:
        df_logs = pd.DataFrame(logs)
        df_logs['upload_time'] = pd.to_datetime(df_logs['upload_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_logs['processing_time_seconds'] = df_logs['processing_time_seconds'].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")
        df_logs['ocr_success'] = df_logs['ocr_success'].map({True: '✅', False: '❌', None: '?'})
        df_logs['llm_success'] = df_logs['llm_success'].map({True: '✅', False: '❌', None: '?'})
        st.dataframe(df_logs[[
            'upload_time', 'filename', 'ocr_success', 'llm_success',
            'num_questions_generated', 'document_id', 'processing_time_seconds', 'error_message'
        ]].rename(columns={
            'upload_time': 'Timestamp', 'filename': 'Archivo', 'ocr_success': 'OCR OK',
            'llm_success': 'LLM OK', 'num_questions_generated': 'Preguntas Gen.',
            'document_id': 'Doc ID', 'processing_time_seconds': 'Tiempo (s)',
            'error_message': 'Mensaje Error'
        }), height=300, use_container_width=True)
    else:
        st.info("No hay registros de generación disponibles.")
except Exception as e:
    st.error(f"Error cargando logs de generación: {e}")

# --- NUEVA SECCIÓN: Análisis Detallado por Pregunta ---
st.divider()
st.subheader("📊 Análisis Detallado por Pregunta (Global)")

try:
    # 1. Obtener todos los datos de preguntas
    all_q_stats_data = obtener_estadisticas_todas_las_preguntas(conn)

    if not all_q_stats_data:
        st.warning("No hay datos de estadísticas de preguntas disponibles.")
        st.stop()

    df_q_stats = pd.DataFrame(all_q_stats_data)

    # 2. Calcular métricas adicionales en Pandas
    df_q_stats['precision_global_%'] = (
        df_q_stats['total_correctas'] / df_q_stats['total_intentos'] * 100
    ).where(df_q_stats['total_intentos'] > 0, 0).round(1) # Poner 0% si no hay intentos

    # 3. Crear Controles de Filtro
    st.markdown("#### Filtros")
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        # Filtro por Documento
        try:
            lista_docs = obtener_documentos_cargados(conn)
            doc_options = {doc['nombre']: doc['id'] for doc in lista_docs}
            doc_options_list = ["Todos"] + list(doc_options.keys()) # Añadir opción "Todos"
            selected_doc_names = st.multiselect(
                "Filtrar por Documento(s):",
                options=doc_options_list,
                default=["Todos"] # Por defecto mostrar todos
            )
        except Exception as e:
            st.error(f"Error al cargar lista de documentos para filtro: {e}")
            selected_doc_names = ["Todos"] # Fallback

        # Filtro por texto en la pregunta
        search_text = st.text_input("Buscar en texto de pregunta:")

    with col_f2:
        # Filtro por Precisión (%)
        min_acc, max_acc = st.slider(
            "Rango de Precisión Global (%):",
            min_value=0.0,
            max_value=100.0,
            value=(0.0, 100.0), # Por defecto todo el rango
            step=1.0
        )
        # Filtro por número mínimo de intentos
        min_attempts = st.number_input(
            "Mínimo de Intentos Totales:",
            min_value=0,
            value=0, # Por defecto incluir preguntas sin intentos
            step=1
        )

    with col_f3:
         # Filtro por número mínimo de usuarios únicos
        min_unique_users = st.number_input(
            "Mínimo de Usuarios Únicos que Intentaron:",
            min_value=0,
            value=0, # Por defecto incluir preguntas no intentadas por nadie
            step=1
        )
        # Opción de ordenación inicial
        sort_options = {
            "Documento, ID Pregunta": ["documento_id", "pregunta_id"],
            "Más Intentada": ["total_intentos"],
            "Menos Intentada": ["total_intentos"],
            "Más Incorrecta (Abs)": ["total_incorrectas"],
            "Menor Precisión (%)": ["precision_global_%"],
            "Mayor Precisión (%)": ["precision_global_%"],
            "Mayor Tiempo Promedio": ["tiempo_promedio_global"],
        }
        sort_by = st.selectbox("Ordenar por:", options=sort_options.keys())


    # 4. Aplicar Filtros al DataFrame
    df_filtered = df_q_stats.copy() # Trabajar sobre una copia

    # Aplicar filtro de documento
    if selected_doc_names and "Todos" not in selected_doc_names:
        selected_doc_ids = [doc_options[name] for name in selected_doc_names if name in doc_options]
        if selected_doc_ids:
            df_filtered = df_filtered[df_filtered['documento_id'].isin(selected_doc_ids)]

    # Aplicar filtro de texto
    if search_text:
        df_filtered = df_filtered[df_filtered['pregunta_texto'].str.contains(search_text, case=False, na=False)]

    # Aplicar filtro de precisión
    df_filtered = df_filtered[
        (df_filtered['precision_global_%'] >= min_acc) &
        (df_filtered['precision_global_%'] <= max_acc)
    ]

    # Aplicar filtro de intentos mínimos
    df_filtered = df_filtered[df_filtered['total_intentos'] >= min_attempts]

    # Aplicar filtro de usuarios únicos mínimos
    df_filtered = df_filtered[df_filtered['usuarios_unicos_intentaron'] >= min_unique_users]


    # 5. Aplicar Ordenación
    sort_columns = sort_options[sort_by]
    ascending_map = {
        "Menos Intentada": True,
        "Menor Precisión (%)": True,
        # El resto por defecto es descendente (False) o el orden natural (True)
    }
    ascending = ascending_map.get(sort_by, False if len(sort_columns) == 1 else [True, True]) # Default a desc para métricas, asc para IDs
    if sort_by == "Documento, ID Pregunta":
        ascending = [True, True]

    df_filtered = df_filtered.sort_values(by=sort_columns, ascending=ascending)


    # 6. Mostrar Tabla Filtrada y Ordenada
    st.markdown("#### Resultados")
    st.info(f"Mostrando {len(df_filtered)} de {len(df_q_stats)} preguntas según filtros.")

    if not df_filtered.empty:
        # Seleccionar y renombrar columnas para mostrar
        display_columns = {
            "pregunta_id": "ID",
            "pregunta_texto": "Pregunta",
            "documento_nombre": "Documento",
            "total_intentos": "Intentos Totales",
            "total_correctas": "Correctas",
            "total_incorrectas": "Incorrectas",
            "precision_global_%": "Precisión (%)",
            "tiempo_promedio_global": "Tiempo Prom (s)",
            "usuarios_unicos_intentaron": "Usuarios Únicos"
        }
        df_display = df_filtered[list(display_columns.keys())].rename(columns=display_columns)

        # Formatear columnas numéricas si es necesario (opcional)
        df_display['Tiempo Prom (s)'] = df_display['Tiempo Prom (s)'].map('{:.2f}'.format)
        #df_display['Precisión (%)'] = df_display['Precisión (%)'].map('{:.1f}%'.format) # Ya redondeado, añadir % si se quiere

        st.dataframe(df_display, use_container_width=True, height=600) # Ajustar altura

        # 7. Gráficos (Opcional) - Basados en datos filtrados
        st.markdown("#### Visualizaciones (Datos Filtrados)")
        if len(df_filtered) > 1: # Necesitamos más de 1 dato para la mayoría de gráficos
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                # Histograma de Precisión
                fig_acc, ax_acc = plt.subplots()
                ax_acc.hist(df_filtered['precision_global_%'].dropna(), bins=10, color='skyblue', edgecolor='black')
                ax_acc.set_title('Distribución de Precisión Global (%)')
                ax_acc.set_xlabel('Precisión (%)')
                ax_acc.set_ylabel('Número de Preguntas')
                st.pyplot(fig_acc)

            with col_g2:
                # Histograma de Tiempo Promedio (filtrando tiempos > 0)
                tiempos_validos = df_filtered[df_filtered['tiempo_promedio_global'] > 0]['tiempo_promedio_global']
                if not tiempos_validos.empty:
                    fig_time, ax_time = plt.subplots()
                    ax_time.hist(tiempos_validos.dropna(), bins=10, color='lightcoral', edgecolor='black')
                    ax_time.set_title('Distribución de Tiempo Promedio (s)')
                    ax_time.set_xlabel('Tiempo Promedio (s)')
                    ax_time.set_ylabel('Número de Preguntas')
                    st.pyplot(fig_time)
                else:
                    st.caption("No hay datos de tiempo válidos (>0s) para graficar.")

# Top N Preguntas más difíciles (menor precisión)
            st.markdown("##### Top 5 Preguntas Más Difíciles (Menor Precisión)")
            # Ordenar primero por precisión, luego seleccionar las 5 primeras
            df_dificiles = df_filtered[df_filtered['total_intentos'] > 0].sort_values(by='precision_global_%', ascending=True).head(5)

            if not df_dificiles.empty:
                 # 1. Seleccionar columnas con los NOMBRES ORIGINALES del DataFrame df_dificiles
                 df_top_display = df_dificiles[[
                     'pregunta_id',           # Nombre original
                     'pregunta_texto',        # Nombre original
                     'documento_nombre',      # Nombre original
                     'precision_global_%',    # Nombre original
                     'total_intentos'         # Nombre original
                 ]]
                 # 2. RENOMBRAR las columnas justo antes de mostrar
                 df_top_display = df_top_display.rename(columns={
                     'pregunta_id': 'ID',
                     'pregunta_texto': 'Pregunta',
                     'documento_nombre': 'Documento',
                     'precision_global_%': 'Precisión (%)', # Corregir nombre aquí también
                     'total_intentos': 'Intentos Totales'
                 })
                 # 3. Mostrar el DataFrame renombrado
                 st.dataframe(
                      df_top_display,
                      use_container_width=True
                 )
            else:
                 st.caption("No hay preguntas con intentos para mostrar este ranking.")


    else:
        st.warning("Ninguna pregunta coincide con los filtros seleccionados.")


except Exception as e:
    st.error(f"Error al cargar o procesar estadísticas detalladas de preguntas: {e}")
    st.exception(e) # Muestra el traceback completo


# --- END OF FILE pages/4_⚙️_Admin_Dashboard.py ---