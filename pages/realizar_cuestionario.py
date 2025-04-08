# --- START OF FILE pages/2_✍️_Realizar_Cuestionario.py ---
import streamlit as st
from database import (
    get_db_connection,
    obtener_documentos_cargados,
    obtener_preguntas_por_documento,
    reiniciar_progreso,
    registrar_progreso,
    registrar_respuesta,
    obtener_preguntas_aleatorias
)
from utils import enumerar_opciones, verificar_respuestas
import json
from datetime import datetime
import time
import pandas as pd

if not st.experimental_user.is_logged_in:
    st.warning("Por favor, inicia sesión para realizar el cuestionario.")
    st.stop()

st.header("✍️ Recuperación Activa - Cuestionario")

user_email = st.experimental_user.email
st.caption(f"Usuario: {user_email}")

conn = get_db_connection()
if not conn:
    st.error("Conexión a base de datos no disponible.")
    st.stop()

NUM_QUESTIONS_PER_BATCH = 5

try:
    documentos_cargados = obtener_documentos_cargados(conn)
    if not documentos_cargados:
        st.warning("No hay documentos con preguntas cargadas todavía. Genere algunas preguntas primero.")
        st.stop()
    nombres_documentos = {doc["nombre"]: doc["id"] for doc in documentos_cargados}
    doc_nombre_seleccionado = st.sidebar.selectbox(
        "Selecciona un Documento",
        options=nombres_documentos.keys(),
        key="doc_select_quiz"
    )
except Exception as e:
    st.error(f"Error al cargar la lista de documentos: {e}")
    st.stop()

if not doc_nombre_seleccionado:
    st.info("Por favor, selecciona un documento en la barra lateral.")
    st.stop()

documento_id_seleccionado = nombres_documentos[doc_nombre_seleccionado]
st.info(f"Documento seleccionado: **{doc_nombre_seleccionado}** (ID: {documento_id_seleccionado})")

state_prefix = f"quiz_{user_email}_{documento_id_seleccionado}_"

def init_session_state_key(key, value):
    full_key = state_prefix + key
    if full_key not in st.session_state:
        st.session_state[full_key] = value

init_session_state_key("preguntas_actuales", [])
init_session_state_key("respuestas_usuario", {})
init_session_state_key("resultados_verificacion", [])
init_session_state_key("start_times", {})
init_session_state_key("quiz_finished", False)
init_session_state_key("total_answered_correctly", 0)

try:
    todas_las_preguntas_doc = obtener_preguntas_por_documento(conn, documento_id_seleccionado)
    total_preguntas_en_doc = len(todas_las_preguntas_doc)
except Exception as e:
    st.error(f"Error obteniendo preguntas para el documento: {e}")
    total_preguntas_en_doc = 0

if total_preguntas_en_doc == 0:
    st.warning("Este documento no tiene preguntas asociadas.")
    st.stop()

st.write(f"Total de preguntas en este documento: **{total_preguntas_en_doc}**")

try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT pregunta_id) FROM progreso_usuario
            WHERE usuario_id = %s AND documento_id = %s
        """, (user_email, documento_id_seleccionado))
        initial_correct_count = cur.fetchone()[0]
        init_session_state_key("total_answered_correctly", initial_correct_count)
except Exception as e:
    st.error(f"Error al obtener progreso inicial: {e}")

progreso_actual = st.session_state[state_prefix + "total_answered_correctly"] / total_preguntas_en_doc if total_preguntas_en_doc > 0 else 0
st.progress(progreso_actual, text=f"Progreso: {st.session_state[state_prefix + 'total_answered_correctly']}/{total_preguntas_en_doc} correctas")

col_btn1, col_btn2, col_btn3 = st.columns([1,1,1])

with col_btn1:
    if st.button("▶️ Cargar Preguntas", key="load_questions_btn", help=f"Cargar hasta {NUM_QUESTIONS_PER_BATCH} preguntas no respondidas"):
        try:
            # Limpiar estado anterior antes de cargar nuevas preguntas
            st.session_state[state_prefix + "respuestas_usuario"] = {}
            st.session_state[state_prefix + "resultados_verificacion"] = []
            st.session_state[state_prefix + "start_times"] = {}

            preguntas_nuevas = obtener_preguntas_aleatorias(conn, documento_id_seleccionado, user_email, NUM_QUESTIONS_PER_BATCH)
            st.session_state[state_prefix + "preguntas_actuales"] = preguntas_nuevas

            st.session_state[state_prefix + "quiz_finished"] = False # Reset finished flag
            if not preguntas_nuevas and st.session_state[state_prefix + "total_answered_correctly"] >= total_preguntas_en_doc:
                st.success("🎉 ¡Felicidades! Has respondido correctamente a todas las preguntas de este documento.")
                st.session_state[state_prefix + "quiz_finished"] = True
            elif not preguntas_nuevas:
                 st.info("No quedan más preguntas por cargar en este momento.")


            st.rerun()
        except Exception as e:
            st.error(f"Error al cargar preguntas aleatorias: {e}")

with col_btn3:
    if st.button("🔄 Reiniciar Progreso", key="reset_progress_btn", help="Borra tu progreso y respuestas para este documento"):
        try:
            reiniciar_progreso(conn, user_email, documento_id_seleccionado)
            keys_to_clear = [k for k in st.session_state if k.startswith(state_prefix)]
            for key in keys_to_clear:
                del st.session_state[key]
            st.success("Progreso reiniciado para este documento.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error al reiniciar el progreso: {e}")

# --- Obtener las preguntas actuales ANTES del formulario ---
preguntas_a_mostrar = st.session_state.get(state_prefix + "preguntas_actuales", [])

if preguntas_a_mostrar:
    st.subheader("Preguntas Actuales")
    with st.form(key="quiz_form"):
        respuestas_temp = {}
        for i, pregunta in enumerate(preguntas_a_mostrar):
            # --- Lógica existente para mostrar pregunta y radio button ---
            q_id = pregunta['id']
            q_text = pregunta['question']
            options_json = pregunta['options']

            st.write(f"**{i + 1}. {q_text}**")

            try:
                if isinstance(options_json, str):
                    options_dict = json.loads(options_json)
                elif isinstance(options_json, dict):
                    options_dict = options_json
                else:
                    st.error(f"Formato de opciones inválido para pregunta {i+1}")
                    continue

                opciones_enumeradas = enumerar_opciones(options_dict)
                opciones_mostradas = [f"{letra}) {opcion}" for letra, opcion in opciones_enumeradas.items()]

                if i not in st.session_state[state_prefix + "start_times"]:
                     st.session_state[state_prefix + "start_times"][i] = datetime.now()

                # Asegurarse de que la clave del radio sea única para esta pregunta específica
                # Usar el índice 'i' dentro del lote actual está bien aquí
                seleccion = st.radio(
                    f"Respuesta:",
                    options=opciones_mostradas,
                    key=f"{state_prefix}_radio_{i}", # Clave única por índice en el lote
                    label_visibility="collapsed"
                )
                seleccion_letra = seleccion.split(')', 1)[0].strip().upper()
                respuestas_temp[i] = seleccion_letra

            except json.JSONDecodeError:
                st.error(f"Error al procesar opciones para pregunta {i+1}. Opciones recibidas: {options_json}")
            except Exception as e:
                 st.error(f"Error inesperado mostrando pregunta {i+1}: {e}")
        # --- Fin Lógica para mostrar pregunta ---

        submitted = st.form_submit_button("✅ Verificar Respuestas")

        if submitted:
            st.session_state[state_prefix + "respuestas_usuario"] = respuestas_temp
            if st.session_state[state_prefix + "respuestas_usuario"]:
                # --- Lógica existente de verificación y registro ---
                respuestas_seleccionadas_list = [st.session_state[state_prefix + "respuestas_usuario"].get(i) for i in range(len(preguntas_a_mostrar))]

                preguntas_correctas_ids = []
                resultados_bool = [] # True si correcta, False si incorrecta

                for i, pregunta in enumerate(preguntas_a_mostrar):
                    start_time = st.session_state[state_prefix + "start_times"].get(i, datetime.now())
                    end_time = datetime.now()
                    tiempo_respuesta = end_time - start_time

                    seleccionada = respuestas_seleccionadas_list[i]
                    correcta = pregunta["correct_answer"].strip().upper()
                    # Manejar caso donde no se seleccionó respuesta (None)
                    es_correcta = (seleccionada is not None and seleccionada == correcta)
                    resultados_bool.append(es_correcta)

                    # Registrar cada intento (correcto o incorrecto)
                    try:
                        registrar_respuesta(
                            conn=conn,
                            usuario_id=user_email,
                            pregunta_id=pregunta["id"],
                            documento_id=documento_id_seleccionado,
                            tiempo_respuesta_delta=tiempo_respuesta,
                            es_correcta=es_correcta
                        )
                    except Exception as e:
                        st.error(f"Error guardando respuesta para pregunta ID {pregunta['id']}: {e}")

                    if es_correcta:
                        preguntas_correctas_ids.append(pregunta["id"])

                # Guardar los resultados para mostrarlos después del rerun
                st.session_state[state_prefix + "resultados_verificacion"] = resultados_bool

                # Registrar progreso (solo las correctas)
                if preguntas_correctas_ids:
                    try:
                        num_newly_correct = registrar_progreso(conn, user_email, documento_id_seleccionado, preguntas_correctas_ids)
                        st.session_state[state_prefix + "total_answered_correctly"] += num_newly_correct
                    except Exception as e:
                         st.error(f"Error al registrar progreso: {e}")

                # --- MODIFICACIÓN CLAVE: Filtrar preguntas actuales ---
                # Mantener solo las preguntas que NO fueron contestadas correctamente en este intento
                preguntas_incorrectas_actuales = []
                for i, pregunta in enumerate(preguntas_a_mostrar):
                    if not resultados_bool[i]: # Si resultados_bool[i] es False (incorrecta)
                        preguntas_incorrectas_actuales.append(pregunta)

                st.session_state[state_prefix + "preguntas_actuales"] = preguntas_incorrectas_actuales
                # Limpiar timers y respuestas para las preguntas que quedan (si las hay)
                # Esto es importante para que los timers se reinicien si se muestra la misma pregunta incorrecta de nuevo
                st.session_state[state_prefix + "respuestas_usuario"] = {}
                st.session_state[state_prefix + "start_times"] = {}

                st.rerun() # Re-ejecuta el script para reflejar los cambios

    # --- Mostrar Resultados de Verificación (después del rerun si hubo sumisión) ---
    # Usar los resultados guardados en session_state
    resultados_guardados = st.session_state.get(state_prefix + "resultados_verificacion", [])
    # Necesitamos las preguntas originales de *antes* de la verificación para mostrar los resultados correctamente
    # Podríamos guardar una copia antes de filtrar, o reconstruir el mensaje de manera diferente.
    # Solución más simple: Mostrar un mensaje general si hubo resultados.
    if resultados_guardados: # Si hubo una verificación en el paso anterior
        st.subheader("Resultados de la Verificación Anterior")
        todas_correctas_en_lote = all(resultados_guardados)

        # Ya no podemos iterar sobre preguntas_a_mostrar porque fue filtrado.
        # Podríamos guardar las preguntas originales o simplemente mostrar un resumen.
        num_total = len(resultados_guardados)
        num_correctas = sum(resultados_guardados)
        num_incorrectas = num_total - num_correctas

        if num_correctas > 0:
            st.success(f"Respondiste correctamente a {num_correctas} de {num_total} preguntas.")
        if num_incorrectas > 0:
             st.warning(f"Tienes {num_incorrectas} preguntas incorrectas pendientes en este lote.")
        else:
            st.balloons()
            st.success("¡Todas las preguntas de este lote fueron correctas!")
            if not st.session_state[state_prefix + "preguntas_actuales"]: # Si no quedan preguntas después de filtrar
                 st.info("Presiona 'Cargar Preguntas' para el siguiente lote o si has terminado.")

        # Limpiar los resultados para que no se muestren de nuevo en el siguiente rerun sin verificación
        st.session_state[state_prefix + "resultados_verificacion"] = []


# --- Mensajes Finales (cuando no hay preguntas actuales) ---
elif st.session_state.get(state_prefix + "quiz_finished", False):
    st.success("🎉 ¡Felicidades! Has respondido correctamente a todas las preguntas de este documento.")
    st.info("Puedes reiniciar el progreso o seleccionar otro documento.")

elif not st.session_state.get(state_prefix + "preguntas_actuales", []): # Si la lista está vacía pero el quiz no está marcado como terminado
    st.info("Has terminado las preguntas de este lote o no hay preguntas para cargar.")
    st.info("Presiona 'Cargar Preguntas' para obtener un nuevo lote.")
