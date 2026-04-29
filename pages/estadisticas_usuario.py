import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging
from database import get_db_connection, obtener_documentos_cargados
from estadisticas import (
    obtener_pregunta_mas_equivocada_usuario,
    obtener_promedio_tiempo_respuesta_usuario,
    obtener_estadisticas_por_documento_para_usuario,
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

if not st.user.is_logged_in:
    st.warning("Por favor, inicia sesión para ver tus estadísticas personales.")
    if st.button("Iniciar sesión"):
        st.login()
    st.stop()

user_email = st.user.email
st.header(f"Estadísticas Personales ({user_email})")

conn = get_db_connection()
if not conn:
    st.error(
        "Error crítico: conexión a base de datos no disponible. No se pueden cargar las estadísticas."
    )
    st.stop()

st.subheader("Resumen General Personal")
try:
    pregunta_mas_errada_info = obtener_pregunta_mas_equivocada_usuario(
        conn, usuario_id=user_email
    )
    promedio_tiempo_seg = obtener_promedio_tiempo_respuesta_usuario(
        conn, usuario_id=user_email
    )

    col1, col2 = st.columns(2)

    with col1:
        if (
            pregunta_mas_errada_info
            and "pregunta_texto" in pregunta_mas_errada_info
            and pregunta_mas_errada_info["pregunta_texto"] is not None
        ):
            st.metric(
                label=f"Pregunta Más Fallada (ID: {pregunta_mas_errada_info['pregunta_id']})",
                value=f"{pregunta_mas_errada_info['numero_errores']} veces",
                help=f"Texto: {pregunta_mas_errada_info['pregunta_texto']}",
            )
        elif pregunta_mas_errada_info and "pregunta_id" in pregunta_mas_errada_info:
            st.metric(
                label=f"Pregunta Más Fallada (ID: {pregunta_mas_errada_info['pregunta_id']})",
                value=f"{pregunta_mas_errada_info.get('numero_errores', 'N/A')} veces",
            )
            st.caption(
                "No se pudo recuperar el texto de la pregunta o no hay errores registrados."
            )
        else:
            st.info(
                "No hay datos suficientes para determinar tu pregunta más fallada o no has cometido errores."
            )

    with col2:
        if promedio_tiempo_seg is not None:
            st.metric(
                label="Tiempo Promedio por Respuesta",
                value=f"{promedio_tiempo_seg:.2f} seg",
            )
        else:
            st.info("No hay datos de tiempo de respuesta registrados para ti.")

except Exception as e:
    st.error(f"Ocurrió un error al cargar tus estadísticas generales personales: {e}")
    logger.error(
        f"Error en UI - Estadísticas Generales Personales para {user_email}: {e}",
        exc_info=True,
    )

st.divider()

st.subheader("Rendimiento Personal por Documento")
try:
    documentos_cargados_raw = obtener_documentos_cargados(conn)
    if not documentos_cargados_raw:
        st.warning(
            "No hay documentos cargados en el sistema para mostrar estadísticas."
        )

    else:
        documentos_cargados_sorted = sorted(
            documentos_cargados_raw, key=lambda x: x["nombre"]
        )
        nombres_documentos_map = {
            doc["nombre"]: doc["id"] for doc in documentos_cargados_sorted
        }

        if not nombres_documentos_map:
            st.warning("No se pudieron procesar los documentos para la selección.")

        else:
            doc_nombre_seleccionado = st.selectbox(
                "Selecciona un Documento para ver tus estadísticas detalladas:",
                options=list(nombres_documentos_map.keys()),
                key="doc_select_stats_user_page",
            )

            if doc_nombre_seleccionado:
                documento_id_seleccionado = nombres_documentos_map[
                    doc_nombre_seleccionado
                ]
                st.write(
                    f"Mostrando estadísticas para el documento: **{doc_nombre_seleccionado}** (ID: {documento_id_seleccionado})"
                )

                user_doc_stats_data = obtener_estadisticas_por_documento_para_usuario(
                    conn, documento_id_seleccionado, user_email
                )

                if user_doc_stats_data:
                    df_stats = pd.DataFrame(user_doc_stats_data)

                    expected_cols = [
                        "pregunta_id",
                        "pregunta_texto",
                        "total_respuestas_usuario",
                        "correctas_usuario",
                        "incorrectas_usuario",
                        "tiempo_promedio_usuario_secs",
                    ]
                    missing_cols = [
                        col for col in expected_cols if col not in df_stats.columns
                    ]
                    if missing_cols:
                        st.error(
                            f"Faltan columnas en los datos de estadísticas: {', '.join(missing_cols)}. Verifica la función 'obtener_estadisticas_por_documento_para_usuario'."
                        )
                        st.dataframe(df_stats)

                    else:
                        df_stats["accuracy_usuario_%"] = df_stats.apply(
                            lambda row: (
                                (
                                    row["correctas_usuario"]
                                    / row["total_respuestas_usuario"]
                                    * 100
                                )
                                if row["total_respuestas_usuario"] > 0
                                else 0.0
                            ),
                            axis=1,
                        ).round(1)

                        df_stats["tiempo_promedio_usuario_secs"] = pd.to_numeric(
                            df_stats["tiempo_promedio_usuario_secs"], errors="coerce"
                        ).fillna(0.0)

                        display_df = df_stats.rename(
                            columns={
                                "pregunta_id": "ID Pregunta",
                                "pregunta_texto": "Pregunta",
                                "total_respuestas_usuario": "Tus Intentos",
                                "correctas_usuario": "Correctas",
                                "incorrectas_usuario": "Incorrectas",
                                "tiempo_promedio_usuario_secs": "Tu Tiempo Prom. (s)",
                                "accuracy_usuario_%": "Tu Precisión (%)",
                            }
                        )

                        st.dataframe(
                            display_df[
                                [
                                    "ID Pregunta",
                                    "Pregunta",
                                    "Tus Intentos",
                                    "Correctas",
                                    "Incorrectas",
                                    "Tu Tiempo Prom. (s)",
                                    "Tu Precisión (%)",
                                ]
                            ],
                            use_container_width=True,
                        )

                        st.subheader(
                            "Gráficos de Rendimiento Personal (para este documento)"
                        )
                        df_answered = df_stats[
                            df_stats["total_respuestas_usuario"] > 0
                        ].copy()

                        if not df_answered.empty:
                            df_answered["pregunta_id_str"] = df_answered[
                                "pregunta_id"
                            ].astype(str)

                            col_chart1, col_chart2 = st.columns(2)
                            with col_chart1:
                                fig1, ax1 = plt.subplots()
                                ax1.bar(
                                    df_answered["pregunta_id_str"],
                                    df_answered["tiempo_promedio_usuario_secs"],
                                    color="skyblue",
                                )
                                ax1.set_xlabel("ID Pregunta")
                                ax1.set_ylabel("Tu Tiempo Promedio (segundos)")
                                ax1.set_title("Tiempo Promedio por Pregunta Respondida")
                                plt.setp(
                                    ax1.get_xticklabels(),
                                    rotation=45,
                                    ha="right",
                                    rotation_mode="anchor",
                                )
                                plt.tight_layout()
                                st.pyplot(fig1)

                            with col_chart2:
                                fig2, ax2 = plt.subplots()
                                bar_width = 0.35
                                index = np.arange(len(df_answered["pregunta_id_str"]))

                                bars1 = ax2.bar(
                                    index - bar_width / 2,
                                    df_answered["correctas_usuario"],
                                    bar_width,
                                    label="Correctas",
                                    color="lightgreen",
                                )
                                bars2 = ax2.bar(
                                    index + bar_width / 2,
                                    df_answered["incorrectas_usuario"],
                                    bar_width,
                                    label="Incorrectas",
                                    color="salmon",
                                )

                                ax2.set_xlabel("ID Pregunta")
                                ax2.set_ylabel("Número de Tus Respuestas")
                                ax2.set_title("Correctas vs. Incorrectas")
                                ax2.set_xticks(index)
                                ax2.set_xticklabels(df_answered["pregunta_id_str"])
                                plt.setp(
                                    ax2.get_xticklabels(),
                                    rotation=45,
                                    ha="right",
                                    rotation_mode="anchor",
                                )
                                ax2.legend()
                                plt.tight_layout()
                                st.pyplot(fig2)
                        else:
                            st.info(
                                "No has respondido ninguna pregunta de este documento todavía para generar gráficos."
                            )
                else:
                    st.info(
                        f"No hay estadísticas de preguntas disponibles para ti en el documento '{doc_nombre_seleccionado}'."
                    )
                    st.caption(
                        "Esto puede ser porque el documento no tiene preguntas o porque aún no has interactuado con ellas."
                    )

except Exception as e:
    st.error(f"Ocurrió un error al cargar las estadísticas por documento: {e}")
    doc_name_for_log = (
        doc_nombre_seleccionado
        if "doc_nombre_seleccionado" in locals() and doc_nombre_seleccionado
        else "N/A"
    )
    logger.error(
        f"Error en UI - Estadísticas por Documento para {user_email}, Doc: {doc_name_for_log}: {e}",
        exc_info=True,
    )
