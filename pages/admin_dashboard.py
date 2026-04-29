import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import logging
from datetime import timedelta
from database import (
    get_db_connection,
    get_generation_logs,
    obtener_documentos_cargados,
    get_overall_document_stats,
)
from estadisticas import (
    obtener_estadisticas_globales_todas_las_preguntas,
    obtener_resumen_actividad_general,
    obtener_documentos_mas_usados,
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

if not st.user.is_logged_in:
    st.warning("Por favor, inicia sesión para acceder a esta funcionalidad.")
    if st.button("Iniciar sesión"):
        st.login()
    st.stop()

is_admin = False
try:
    admin_config = st.secrets.get("auth", {})
    admin_email_list = admin_config.get("admin_emails", [])

    if not isinstance(admin_email_list, list):
        logger.error(
            "La configuración 'admin_emails' en secrets.toml ([auth]) no es una lista válida."
        )
        st.error("Error interno de configuración de permisos.")
        st.stop()

    current_user_email = st.user.email.lower()
    authorized_admins = [email.lower() for email in admin_email_list]

    if current_user_email in authorized_admins:
        is_admin = True
    else:
        st.error("Acceso denegado.")
        st.warning(
            f"El usuario **{st.user.email}** no tiene permisos para acceder a esta sección."
        )
        st.stop()
except Exception as e:
    logger.error(f"Error al verificar permisos de administrador: {e}", exc_info=True)
    st.error("Ocurrió un error al verificar tus permisos.")
    st.stop()

st.header("Admin Dashboard")
st.success(f"Acceso de administrador concedido para: {st.user.email}")
st.markdown("*Supervisión del sistema y estadísticas agregadas.*")

conn = get_db_connection()
if not conn:
    st.error(
        "Error crítico: conexión a base de datos no disponible. No se puede cargar el dashboard."
    )
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Métricas Clave",
        "Documentos y Generación",
        "Análisis de Preguntas",
        "Actividad de Usuarios",
    ]
)

with tab1:
    st.subheader("Métricas Clave del Sistema")
    try:
        summary = obtener_resumen_actividad_general(conn)
        if summary:
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Usuarios con Respuestas", summary.get("usuarios_con_respuestas", 0)
            )
            col2.metric(
                "Total Respuestas Registradas",
                summary.get("total_respuestas_registradas", 0),
            )
            col3.metric(
                "Documentos Cargados", summary.get("total_documentos_cargados", 0)
            )

            col4, col5, col6 = st.columns(3)
            col4.metric(
                "Total Preguntas Generadas", summary.get("total_preguntas_generadas", 0)
            )
            avg_rating = summary.get("feedback_promedio_rating")
            col5.metric(
                "Rating Promedio Feedback",
                f"{avg_rating:.2f}" if avg_rating is not None else "N/A",
                help="Promedio de calificaciones de 1-5 estrellas.",
            )
            col6.metric(
                "Total Feedbacks Enviados", summary.get("total_feedback_enviado", 0)
            )

            avg_session_duration_secs = summary.get("avg_session_duration_seconds", 0)
            if avg_session_duration_secs:
                avg_duration_str = str(
                    timedelta(seconds=int(avg_session_duration_secs))
                )

                st.metric("Duración Prom. Sesión (Ejemplo)", avg_duration_str)

        else:
            st.warning("No se pudo obtener el resumen de actividad general.")
    except Exception as e:
        st.error(f"Error cargando métricas clave: {e}")
        logger.error(f"Error en UI - Métricas Clave: {e}", exc_info=True)

with tab2:
    st.subheader("Visión General de Documentos")
    try:
        doc_stats_data = get_overall_document_stats(conn)
        if doc_stats_data:
            df_docs = pd.DataFrame(doc_stats_data)
            if not df_docs.empty:
                df_docs["created_at_fmt"] = pd.to_datetime(
                    df_docs["created_at"]
                ).dt.strftime("%Y-%m-%d %H:%M")

                df_docs["total_answers_all_users"] = (
                    df_docs["total_correct_answers_all_users"]
                    + df_docs["total_incorrect_answers_all_users"]
                )
                df_docs["accuracy_global"] = (
                    (
                        (
                            df_docs["total_correct_answers_all_users"]
                            / df_docs["total_answers_all_users"]
                        )
                        * 100
                    )
                    .where(df_docs["total_answers_all_users"] > 0, 0)
                    .round(1)
                )

                st.dataframe(
                    df_docs[
                        [
                            "id",
                            "nombre",
                            "total_questions",
                            "unique_users_attempted",
                            "accuracy_global",
                            "curso_tag",
                            "grado_tag",
                            "num_pages_pdf",
                            "created_at_fmt",
                            "hash",
                        ]
                    ].rename(
                        columns={
                            "id": "Doc ID",
                            "nombre": "Nombre Archivo",
                            "total_questions": "Nº Preguntas",
                            "unique_users_attempted": "Usuarios Únicos",
                            "accuracy_global": "Precisión Global (%)",
                            "curso_tag": "Curso",
                            "grado_tag": "Grado",
                            "num_pages_pdf": "Páginas PDF",
                            "created_at_fmt": "Fecha Creación",
                            "hash": "Hash Doc/Preguntas",
                        }
                    ),
                    use_container_width=True,
                )

                if not df_docs.empty and "total_questions" in df_docs.columns:
                    fig_q_per_doc, ax_q_per_doc = plt.subplots()
                    df_chart_docs = df_docs.nlargest(20, "total_questions").sort_values(
                        "total_questions", ascending=False
                    )
                    ax_q_per_doc.bar(
                        df_chart_docs["nombre"],
                        df_chart_docs["total_questions"],
                        color="teal",
                    )
                    ax_q_per_doc.set_ylabel("Número de Preguntas Generadas")
                    ax_q_per_doc.set_title("Preguntas Generadas por Documento (Top 20)")
                    plt.xticks(rotation=75, ha="right")
                    plt.tight_layout()
                    st.pyplot(fig_q_per_doc)
            else:
                st.info("No hay datos de documentos disponibles.")
        else:
            st.info(
                "No hay estadísticas de documentos disponibles o la función devolvió None/empty."
            )
    except Exception as e:
        st.error(f"Error cargando estadísticas de documentos: {e}")
        logger.error(f"Error en UI - Visión General Documentos: {e}", exc_info=True)

    st.divider()
    st.subheader("Registro de Generación de Preguntas Recientes")
    try:
        logs = get_generation_logs(conn, limit=50)
        if logs:
            df_logs = pd.DataFrame(logs)
            df_logs["upload_time_fmt"] = pd.to_datetime(
                df_logs["upload_time"]
            ).dt.strftime("%Y-%m-%d %H:%M:%S")
            df_logs["processing_time_fmt"] = df_logs["processing_time_seconds"].map(
                lambda x: f"{x:.2f}s" if pd.notnull(x) else "-"
            )
            df_logs["ocr_status_icon"] = df_logs["ocr_success"].map(
                {True: "Éxito", False: "Fallo", None: "N/A"}
            )
            df_logs["llm_status_icon"] = df_logs["llm_success"].map(
                {True: "Éxito", False: "Fallo", None: "N/A"}
            )

            st.dataframe(
                df_logs[
                    [
                        "upload_time_fmt",
                        "filename",
                        "usuario_id",
                        "ocr_status_icon",
                        "llm_status_icon",
                        "model_used",
                        "num_questions_generated",
                        "document_id",
                        "processing_time_fmt",
                        "error_message",
                    ]
                ].rename(
                    columns={
                        "upload_time_fmt": "Timestamp",
                        "filename": "Archivo",
                        "usuario_id": "Usuario",
                        "ocr_status_icon": "OCR",
                        "llm_status_icon": "LLM",
                        "model_used": "Modelo LLM",
                        "num_questions_generated": "Preguntas Gen.",
                        "document_id": "Doc ID Asignado",
                        "processing_time_fmt": "Tiempo Proc.",
                        "error_message": "Mensaje Error",
                    }
                ),
                height=400,
                use_container_width=True,
            )
        else:
            st.info("No hay registros de generación disponibles.")
    except Exception as e:
        st.error(f"Error cargando logs de generación: {e}")
        logger.error(f"Error en UI - Logs de Generación: {e}", exc_info=True)

with tab3:
    st.subheader("Análisis Detallado por Pregunta (Global)")
    try:
        all_q_stats_data = obtener_estadisticas_globales_todas_las_preguntas(conn)

        if not all_q_stats_data:
            st.warning(
                "No hay datos de estadísticas de preguntas disponibles para analizar."
            )

        else:
            df_q_stats = pd.DataFrame(all_q_stats_data)

            numeric_cols = [
                "total_intentos_global",
                "total_correctas_global",
                "total_incorrectas_global",
                "tiempo_promedio_global_secs",
                "usuarios_unicos_intentaron",
            ]
            for col in numeric_cols:
                df_q_stats[col] = pd.to_numeric(
                    df_q_stats[col], errors="coerce"
                ).fillna(0)

            df_q_stats["precision_global_%"] = (
                (
                    df_q_stats["total_correctas_global"]
                    / df_q_stats["total_intentos_global"]
                    * 100
                )
                .where(df_q_stats["total_intentos_global"] > 0, 0)
                .round(1)
            )

            st.markdown("#### Filtros de Análisis de Preguntas")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                try:
                    lista_docs_raw = obtener_documentos_cargados(conn)
                    doc_options = {doc["nombre"]: doc["id"] for doc in lista_docs_raw}
                    doc_options_list = ["Todos"] + sorted(list(doc_options.keys()))
                    selected_doc_names = st.multiselect(
                        "Filtrar por Documento(s):",
                        options=doc_options_list,
                        default=["Todos"],
                    )
                except Exception as e_doc_filter:
                    st.error(
                        f"Error al cargar lista de docs para filtro: {e_doc_filter}"
                    )
                    selected_doc_names = ["Todos"]
                search_text = st.text_input(
                    "Buscar en texto de pregunta:", key="q_search_text"
                )

            with col_f2:
                min_acc, max_acc = st.slider(
                    "Rango de Precisión Global (%):",
                    0.0,
                    100.0,
                    (0.0, 100.0),
                    1.0,
                    key="q_acc_slider",
                )
                min_attempts = st.number_input(
                    "Mínimo de Intentos Totales:",
                    0,
                    value=0,
                    step=1,
                    key="q_min_attempts",
                )

            with col_f3:
                min_unique_users = st.number_input(
                    "Mínimo de Usuarios Únicos que Intentaron:",
                    0,
                    value=0,
                    step=1,
                    key="q_min_users",
                )
                sort_options_q = {
                    "Documento, ID Pregunta": ["documento_id", "pregunta_id"],
                    "Más Intentada": ["total_intentos_global"],
                    "Menos Intentada": ["total_intentos_global"],
                    "Más Incorrecta (Abs)": ["total_incorrectas_global"],
                    "Menor Precisión (%)": ["precision_global_%"],
                    "Mayor Precisión (%)": ["precision_global_%"],
                    "Mayor Tiempo Promedio": ["tiempo_promedio_global_secs"],
                }
                sort_by_q = st.selectbox(
                    "Ordenar preguntas por:",
                    options=sort_options_q.keys(),
                    key="q_sort_by",
                )

            df_filtered_q = df_q_stats.copy()
            if selected_doc_names and "Todos" not in selected_doc_names:
                selected_doc_ids = [
                    doc_options[name]
                    for name in selected_doc_names
                    if name in doc_options
                ]
                if selected_doc_ids:
                    df_filtered_q = df_filtered_q[
                        df_filtered_q["documento_id"].isin(selected_doc_ids)
                    ]
            if search_text:
                df_filtered_q = df_filtered_q[
                    df_filtered_q["pregunta_texto"].str.contains(
                        search_text, case=False, na=False
                    )
                ]
            df_filtered_q = df_filtered_q[
                (df_filtered_q["precision_global_%"] >= min_acc)
                & (df_filtered_q["precision_global_%"] <= max_acc)
            ]
            df_filtered_q = df_filtered_q[
                df_filtered_q["total_intentos_global"] >= min_attempts
            ]
            df_filtered_q = df_filtered_q[
                df_filtered_q["usuarios_unicos_intentaron"] >= min_unique_users
            ]

            sort_cols_q = sort_options_q[sort_by_q]
            asc_map_q = {"Menos Intentada": True, "Menor Precisión (%)": True}

            if sort_by_q == "Documento, ID Pregunta":
                asc_q = [True, True]
            elif len(sort_cols_q) == 1:
                asc_q = asc_map_q.get(sort_by_q, False)
            else:
                asc_q = False

            df_filtered_q = df_filtered_q.sort_values(by=sort_cols_q, ascending=asc_q)

            st.markdown(
                f"#### Resultados del Análisis ({len(df_filtered_q)} preguntas)"
            )
            if not df_filtered_q.empty:
                display_cols_q = {
                    "pregunta_id": "ID",
                    "pregunta_texto": "Pregunta",
                    "documento_nombre": "Documento",
                    "curso_tag": "Curso",
                    "grado_tag": "Grado",
                    "total_intentos_global": "Intentos",
                    "total_correctas_global": "Correctas",
                    "total_incorrectas_global": "Incorrectas",
                    "precision_global_%": "Precisión (%)",
                    "tiempo_promedio_global_secs": "Tiempo Prom (s)",
                    "usuarios_unicos_intentaron": "Usuarios Únicos",
                }
                df_display_q = df_filtered_q[list(display_cols_q.keys())].rename(
                    columns=display_cols_q
                )
                df_display_q["Tiempo Prom (s)"] = df_display_q["Tiempo Prom (s)"].map(
                    "{:.2f}".format
                )
                st.dataframe(df_display_q, use_container_width=True, height=600)

                if len(df_filtered_q) > 1:
                    st.markdown("##### Visualizaciones (Datos Filtrados de Preguntas)")

                    fig_prec, ax_prec = plt.subplots()
                    ax_prec.hist(
                        df_filtered_q["precision_global_%"].dropna(),
                        bins=20,
                        color="skyblue",
                        edgecolor="black",
                    )
                    ax_prec.set_title("Distribución de Precisión Global de Preguntas")
                    ax_prec.set_xlabel("Precisión Global (%)")
                    ax_prec.set_ylabel("Número de Preguntas")
                    st.pyplot(fig_prec)
            else:
                st.info("Ninguna pregunta coincide con los filtros seleccionados.")

    except Exception as e:
        st.error(
            f"Error al cargar o procesar estadísticas detalladas de preguntas: {e}"
        )
        logger.error(f"Error en UI - Análisis de Preguntas: {e}", exc_info=True)
        st.exception(e)


with tab4:
    st.subheader("Actividad de Usuarios y Feedback")

    st.markdown("#### Documentos Más Usados (por intentos de cuestionario)")
    try:
        top_docs = obtener_documentos_mas_usados(conn, limit=10)
        if top_docs:
            df_top_docs = pd.DataFrame(top_docs)
            st.dataframe(
                df_top_docs.rename(
                    columns={
                        "documento_id": "Doc ID",
                        "documento_nombre": "Nombre Documento",
                        "numero_intentos_cuestionario": "Nº Intentos de Cuestionario",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.info("No hay datos sobre el uso de documentos en cuestionarios.")
    except Exception as e:
        st.error(f"Error cargando documentos más usados: {e}")
        logger.error(f"Error en UI - Documentos más usados: {e}", exc_info=True)

    st.divider()

    st.markdown("#### Resumen de Feedback Reciente")
    try:
        sql_query_feedback = """
            SELECT f.submitted_at, f.usuario_id, d.nombre as documento_nombre,
                   f.rating, f.comment, f.feedback_type
            FROM feedback_usuario f
            LEFT JOIN documentos d ON f.documento_id = d.id
            ORDER BY f.submitted_at DESC
            LIMIT 10;
        """
        df_feedback = pd.read_sql_query(sql_query_feedback, conn)

        if not df_feedback.empty:
            if (
                pd.api.types.is_datetime64_any_dtype(df_feedback["submitted_at"])
                and df_feedback["submitted_at"].dt.tz is not None
            ):
                df_feedback["submitted_at"] = df_feedback[
                    "submitted_at"
                ].dt.tz_localize(None)

            df_feedback["submitted_at_fmt"] = pd.to_datetime(
                df_feedback["submitted_at"]
            ).dt.strftime("%Y-%m-%d %H:%M")

            st.dataframe(
                df_feedback[
                    [
                        "submitted_at_fmt",
                        "usuario_id",
                        "documento_nombre",
                        "rating",
                        "comment",
                        "feedback_type",
                    ]
                ].rename(
                    columns={
                        "submitted_at_fmt": "Fecha",
                        "usuario_id": "Usuario",
                        "documento_nombre": "Documento",
                        "rating": "Rating (1-5)",
                        "comment": "Comentario",
                        "feedback_type": "Tipo",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.info("No hay registros de feedback disponibles.")

    except Exception as e:
        st.error(f"Error cargando resumen de feedback: {e}")
        logger.error(f"Error en UI - Resumen de Feedback: {e}", exc_info=True)
