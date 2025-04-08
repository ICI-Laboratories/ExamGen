# --- START OF FILE pages/3_📊_Estadisticas_Usuario.py ---
import streamlit as st
from database import get_db_connection, obtener_documentos_cargados, obtener_preguntas_por_documento
from estadisticas import (
    obtener_pregunta_mas_equivocada,
    obtener_promedio_tiempo_respuesta,
    obtener_estadisticas_por_documento_usuario # Asegúrate de que es esta la función llamada
)
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

if not st.experimental_user.is_logged_in:
    st.warning("Por favor, inicia sesión para ver tus estadísticas.")
    st.stop()

user_email = st.experimental_user.email
st.header(f"📊 Estadísticas Personales ({user_email})")

conn = get_db_connection()
if not conn:
    st.error("Conexión a base de datos no disponible.")
    st.stop()

# ... (Código para Resumen General Personal - sin cambios) ...
st.subheader("Resumen General Personal")

try:
    pregunta_mas_errada_info = obtener_pregunta_mas_equivocada(conn, usuario_id=user_email)
    promedio_tiempo_seg = obtener_promedio_tiempo_respuesta(conn, usuario_id=user_email)

    col1, col2 = st.columns(2)

    with col1:
        if pregunta_mas_errada_info:
            q_text = "Pregunta no encontrada"
            try:
                 all_questions_flat = []
                 all_docs = obtener_documentos_cargados(conn)
                 for doc in all_docs:
                     all_questions_flat.extend(obtener_preguntas_por_documento(conn, doc['id']))

                 found_q = next((q for q in all_questions_flat if q['id'] == pregunta_mas_errada_info['pregunta_id']), None)
                 if found_q:
                     q_text = found_q['question']

            except Exception as e:
                 st.warning(f"No se pudo obtener el texto de la pregunta más errada (ID: {pregunta_mas_errada_info['pregunta_id']}): {e}")

            st.metric(
                label=f"Pregunta Más Fallada (ID: {pregunta_mas_errada_info['pregunta_id']})",
                value=f"{pregunta_mas_errada_info['errores']} veces",
                help=f"Texto: {q_text}"
            )
        else:
            st.info("No hay datos suficientes para determinar la pregunta más fallada.")

    with col2:
        if promedio_tiempo_seg is not None:
            st.metric(label="Tiempo Promedio por Respuesta", value=f"{promedio_tiempo_seg:.2f} seg")
        else:
            st.info("No hay datos de tiempo de respuesta registrados.")

except Exception as e:
    st.error(f"Error al cargar estadísticas generales personales: {e}")


st.divider()

st.subheader("Rendimiento Personal por Documento")

try:
    documentos_cargados = obtener_documentos_cargados(conn)
    if not documentos_cargados:
        st.warning("No hay documentos cargados.")
        st.stop()

    nombres_documentos = {doc["nombre"]: doc["id"] for doc in documentos_cargados}
    doc_nombre_seleccionado = st.selectbox(
        "Selecciona un Documento para ver tus estadísticas",
        options=nombres_documentos.keys(),
        key="doc_select_stats_user"
    )

    if doc_nombre_seleccionado:
        documento_id_seleccionado = nombres_documentos[doc_nombre_seleccionado]

        # Llama a la función que ahora usa COALESCE
        user_doc_stats = obtener_estadisticas_por_documento_usuario(conn, documento_id_seleccionado, user_email)

        if user_doc_stats:
            df_stats = pd.DataFrame(user_doc_stats)

            # --- Eliminar o comentar esta línea ---
            # df_stats.fillna({
            #     'total_respuestas_usuario': 0,
            #     'correctas_usuario': 0,
            #     'incorrectas_usuario': 0,
            #     'tiempo_promedio_usuario': 0.0
            # }, inplace=True)
            # ------------------------------------

            # Las columnas ya deberían tener tipos numéricos correctos gracias a COALESCE
            # Verificar tipos si es necesario (para depuración):
            # st.write(df_stats.dtypes)

            # Calcular accuracy
            df_stats['accuracy_usuario'] = df_stats.apply(
                lambda row: (row['correctas_usuario'] / row['total_respuestas_usuario'] * 100)
                            if row['total_respuestas_usuario'] > 0 else 0,
                axis=1
            )
            # Asegurarse de que el tiempo promedio sea float para el redondeo
            df_stats['tiempo_promedio_usuario'] = pd.to_numeric(df_stats['tiempo_promedio_usuario'], errors='coerce').fillna(0.0).round(2)


            st.write(f"Estadísticas para **{doc_nombre_seleccionado}**:")
            st.dataframe(df_stats[[
                'pregunta_id',
                'question',
                'total_respuestas_usuario',
                'correctas_usuario',
                'incorrectas_usuario',
                'tiempo_promedio_usuario',
                'accuracy_usuario'
            ]].rename(columns={
                'question': 'Pregunta',
                'total_respuestas_usuario': 'Tus Respuestas',
                'correctas_usuario': 'Tus Correctas',
                'incorrectas_usuario': 'Tus Incorrectas',
                'tiempo_promedio_usuario': 'Tu Tiempo Prom (s)',
                'accuracy_usuario': 'Tu Precisión (%)'
            }), use_container_width=True)

            # ... (Código de los gráficos - sin cambios necesarios aquí) ...
            st.subheader("Gráficos de Rendimiento Personal")

            df_answered = df_stats[df_stats['total_respuestas_usuario'] > 0]

            if not df_answered.empty:
                col_chart1, col_chart2 = st.columns(2)

                with col_chart1:
                    fig1, ax1 = plt.subplots()
                    ax1.bar(df_answered["pregunta_id"].astype(str), df_answered["tiempo_promedio_usuario"], color='skyblue')
                    ax1.set_xlabel("ID Pregunta")
                    ax1.set_ylabel("Tu Tiempo Promedio (segundos)")
                    ax1.set_title("Tu Tiempo Promedio por Pregunta Respondida")
                    plt.xticks(rotation=45, ha='right')
                    st.pyplot(fig1)

                with col_chart2:
                    fig2, ax2 = plt.subplots()
                    bar_width = 0.35
                    index = np.arange(len(df_answered["pregunta_id"]))

                    bars1 = ax2.bar(index - bar_width/2, df_answered["correctas_usuario"], bar_width, label="Correctas", color='lightgreen')
                    bars2 = ax2.bar(index + bar_width/2, df_answered["incorrectas_usuario"], bar_width, label="Incorrectas", color='salmon')

                    ax2.set_xlabel("ID Pregunta")
                    ax2.set_ylabel("Número de Tus Respuestas")
                    ax2.set_title("Tus Respuestas Correctas vs Incorrectas")
                    ax2.set_xticks(index)
                    ax2.set_xticklabels(df_answered["pregunta_id"].astype(str), rotation=45, ha='right')
                    ax2.legend()
                    st.pyplot(fig2)
            else:
                 st.info("No has respondido ninguna pregunta de este documento todavía.")

        else:
            # Esto podría ocurrir si el documento existe pero no tiene preguntas O si la función DB devuelve vacío
            st.info("No hay estadísticas de preguntas disponibles para ti en este documento.")

except Exception as e:
    st.error(f"Error al cargar estadísticas por documento: {e}")
    st.exception(e) # Muestra el traceback completo para depuración

# --- END OF FILE pages/3_📊_Estadisticas_Usuario.py ---