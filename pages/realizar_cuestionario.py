# --- START OF FILE pages/2_✍️_Realizar_Cuestionario.py ---
# MIT License — 2025
# Copyright (c) 2025
# Yohana Yamille Ornelas Ochoa, Kenya Alexandra Ramos Valadez,
# Pedro Antonio Ibarra Facio

import streamlit as st
from database import (
    get_db_connection,
    obtener_documentos_cargados,
    obtener_preguntas_por_documento, # Para obtener el total de preguntas
    reiniciar_progreso,
    registrar_progreso,
    registrar_respuesta_estadistica, # La función que registra cada intento
    obtener_preguntas_aleatorias_para_cuestionario, # Nueva función para obtener preguntas
    crear_quiz_attempt,                # Nueva función
    actualizar_quiz_attempt_final,     # Nueva función
    registrar_feedback                 # Nueva función
    # obtener_ids_preguntas_respondidas_correctamente # Esta se usa internamente por la de arriba, no necesitas importarla aquí
)
from utils import enumerar_opciones # verificar_respuestas no se usa directamente aquí
import json
from datetime import datetime
import time
# import pandas as pd # Not used in this file

if not st.user.is_logged_in:
    st.warning("Por favor, inicia sesión para realizar el cuestionario.")
    st.stop()

st.header("✍️ Recuperación Activa - Cuestionario")

user_email = st.user.email
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
init_session_state_key("current_quiz_attempt_id", None) # For tracking current batch attempt
init_session_state_key("questions_presented_in_batch", 0) # For current batch attempt stats

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

progreso_actual_mostrado = st.session_state[state_prefix + "total_answered_correctly"] / total_preguntas_en_doc if total_preguntas_en_doc > 0 else 0
st.progress(progreso_actual_mostrado, text=f"Progreso: {st.session_state[state_prefix + 'total_answered_correctly']}/{total_preguntas_en_doc} correctas")

col_btn1, col_btn2, col_btn3 = st.columns([1,1,1])

with col_btn1:
    if st.button("▶️ Cargar Preguntas", key="load_questions_btn", help=f"Cargar hasta {NUM_QUESTIONS_PER_BATCH} preguntas no respondidas"):
        try:
            # Limpiar estado de respuestas y resultados para el nuevo lote
            st.session_state[state_prefix + "respuestas_usuario"] = {}
            st.session_state[state_prefix + "resultados_verificacion"] = []
            st.session_state[state_prefix + "start_times"] = {}

            # Crear un nuevo intento de cuestionario (batch)
            current_progress_percentage = st.session_state[state_prefix + "total_answered_correctly"] / total_preguntas_en_doc if total_preguntas_en_doc > 0 else 0.0
            attempt_id = crear_quiz_attempt(conn, user_email, documento_id_seleccionado, NUM_QUESTIONS_PER_BATCH, current_progress_percentage)
            st.session_state[state_prefix + "current_quiz_attempt_id"] = attempt_id

            preguntas_nuevas = obtener_preguntas_aleatorias_para_cuestionario(conn, documento_id_seleccionado, user_email, NUM_QUESTIONS_PER_BATCH)
            st.session_state[state_prefix + "preguntas_actuales"] = preguntas_nuevas
            st.session_state[state_prefix + "questions_presented_in_batch"] = len(preguntas_nuevas)


            st.session_state[state_prefix + "quiz_finished"] = False # Reset finished flag
            if not preguntas_nuevas and st.session_state[state_prefix + "total_answered_correctly"] >= total_preguntas_en_doc:
                st.success("🎉 ¡Felicidades! Has respondido correctamente a todas las preguntas de este documento.")
                st.session_state[state_prefix + "quiz_finished"] = True
            elif not preguntas_nuevas:
                 st.info("No quedan más preguntas por cargar en este momento.")

            st.rerun()
        except Exception as e:
            st.error(f"Error al cargar preguntas aleatorias o crear intento: {e}")

with col_btn3:
    if st.button("🔄 Reiniciar Progreso", key="reset_progress_btn", help="Borra tu progreso y respuestas para este documento"):
        try:
            reiniciar_progreso(conn, user_email, documento_id_seleccionado)
            # Adicionalmente, podrías querer limpiar los quiz_attempts y estadisticas_respuestas para este usuario y documento.
            # Por ahora, solo reinicia el progreso_usuario.
            keys_to_clear = [k for k in st.session_state if k.startswith(state_prefix)]
            for key in keys_to_clear:
                del st.session_state[key]
            st.success("Progreso reiniciado para este documento.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error al reiniciar el progreso: {e}")

preguntas_a_mostrar = st.session_state.get(state_prefix + "preguntas_actuales", [])

if preguntas_a_mostrar:
    st.subheader("Preguntas Actuales")
    current_quiz_attempt_id = st.session_state.get(state_prefix + "current_quiz_attempt_id")
    if current_quiz_attempt_id is None:
        st.warning("No se ha iniciado un intento de cuestionario. Por favor, carga preguntas primero.")
        # Podrías intentar crear uno aquí si tiene sentido, o forzar la carga.
        # Forzar la carga puede ser peligroso si el usuario no lo espera.
    
    with st.form(key="quiz_form"):
        respuestas_temp = {}
        for i, pregunta in enumerate(preguntas_a_mostrar):
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

                seleccion = st.radio(
                    f"Respuesta:",
                    options=opciones_mostradas,
                    key=f"{state_prefix}_radio_{i}",
                    label_visibility="collapsed"
                )
                seleccion_letra = seleccion.split(')', 1)[0].strip().upper()
                respuestas_temp[i] = seleccion_letra

            except json.JSONDecodeError:
                st.error(f"Error al procesar opciones para pregunta {i+1}. Opciones recibidas: {options_json}")
            except Exception as e:
                 st.error(f"Error inesperado mostrando pregunta {i+1}: {e}")

        submitted = st.form_submit_button("✅ Verificar Respuestas")

        if submitted:
            st.session_state[state_prefix + "respuestas_usuario"] = respuestas_temp
            if st.session_state[state_prefix + "respuestas_usuario"] and current_quiz_attempt_id is not None:
                respuestas_seleccionadas_list = [st.session_state[state_prefix + "respuestas_usuario"].get(i) for i in range(len(preguntas_a_mostrar))]

                preguntas_correctas_ids = []
                resultados_bool = [] 
                num_answered_this_submit = 0

                for i, pregunta_actual in enumerate(preguntas_a_mostrar):
                    start_time = st.session_state[state_prefix + "start_times"].get(i, datetime.now())
                    end_time = datetime.now()
                    tiempo_respuesta = end_time - start_time

                    seleccionada = respuestas_seleccionadas_list[i] # Letra seleccionada e.g. "A"
                    correcta_letra = pregunta_actual["correct_answer"].strip().upper()
                    
                    es_correcta = (seleccionada is not None and seleccionada == correcta_letra)
                    resultados_bool.append(es_correcta)
                    
                    if seleccionada is not None: # Contamos como respondida si se seleccionó algo
                        num_answered_this_submit += 1

                    try:
                        registrar_respuesta_estadistica(
                            conn=conn,
                            usuario_id=user_email,
                            pregunta_id=pregunta_actual["id"],
                            documento_id=documento_id_seleccionado,
                            quiz_attempt_id=current_quiz_attempt_id, # Pasar el ID del intento
                            tiempo_delta=tiempo_respuesta,
                            es_correcta=es_correcta,
                            respuesta_seleccionada=seleccionada if seleccionada else "" # Guardar la letra
                        )
                    except Exception as e:
                        st.error(f"Error guardando respuesta para pregunta ID {pregunta_actual['id']}: {e}")

                    if es_correcta:
                        preguntas_correctas_ids.append(pregunta_actual["id"])

                st.session_state[state_prefix + "resultados_verificacion"] = resultados_bool

                if preguntas_correctas_ids:
                    try:
                        num_newly_correct = registrar_progreso(conn, user_email, documento_id_seleccionado, preguntas_correctas_ids)
                        st.session_state[state_prefix + "total_answered_correctly"] += num_newly_correct
                    except Exception as e:
                         st.error(f"Error al registrar progreso: {e}")

                # Actualizar el intento de cuestionario (batch)
                try:
                    questions_presented_in_batch = st.session_state[state_prefix + "questions_presented_in_batch"]
                    correct_in_batch = sum(resultados_bool)
                    # incorrect_in_batch = num_answered_this_submit - correct_in_batch # Solo de las respondidas
                    incorrect_in_batch = len(resultados_bool) - correct_in_batch # De todas las presentadas en este submit

                    final_progress_percentage = st.session_state[state_prefix + "total_answered_correctly"] / total_preguntas_en_doc if total_preguntas_en_doc > 0 else 0.0
                    
                    actualizar_quiz_attempt_final(
                        conn,
                        attempt_id=current_quiz_attempt_id,
                        questions_presented=questions_presented_in_batch, # Total en el batch original
                        questions_answered=num_answered_this_submit, # Las que se respondieron en este submit
                        correct_in_batch=correct_in_batch,
                        incorrect_in_batch=incorrect_in_batch,
                        final_progress_percentage=final_progress_percentage
                    )
                    # Decidir si el current_quiz_attempt_id se resetea o no.
                    # Si quedan preguntas incorrectas, el "intento" lógico del usuario continúa,
                    # pero este "batch de respuestas" para el quiz_attempt_id ya se registró.
                    # Si se cargan nuevas preguntas, se creará un nuevo attempt_id.
                    # Si se reintentan las incorrectas de ESTE MISMO LOTE, ¿se usa el mismo attempt_id o uno nuevo?
                    # Por ahora, el attempt_id se asocia con una carga de preguntas y la verificación de ese lote.
                    # Si las preguntas incorrectas se mantienen, el siguiente "Verificar" seguirá usando el mismo ID.
                    # Esto está bien. Se limpiará al cargar un nuevo lote.

                except Exception as e:
                    st.error(f"Error al actualizar el intento de cuestionario: {e}")


                preguntas_incorrectas_actuales = []
                for i, pregunta_original in enumerate(preguntas_a_mostrar):
                    if not resultados_bool[i]: 
                        preguntas_incorrectas_actuales.append(pregunta_original)

                st.session_state[state_prefix + "preguntas_actuales"] = preguntas_incorrectas_actuales
                st.session_state[state_prefix + "respuestas_usuario"] = {} # Limpiar para el siguiente posible intento de las incorrectas
                st.session_state[state_prefix + "start_times"] = {}     # Limpiar timers para las incorrectas

                st.rerun()
            elif current_quiz_attempt_id is None:
                 st.error("Error crítico: No se encontró un ID de intento de cuestionario activo. Por favor, recarga las preguntas.")


    resultados_guardados = st.session_state.get(state_prefix + "resultados_verificacion", [])
    if resultados_guardados: 
        st.subheader("Resultados de la Verificación Anterior")
        
        num_total_verificadas = len(resultados_guardados)
        num_correctas_verificadas = sum(resultados_guardados)
        num_incorrectas_verificadas = num_total_verificadas - num_correctas_verificadas

        if num_correctas_verificadas > 0:
            st.success(f"Respondiste correctamente a {num_correctas_verificadas} de {num_total_verificadas} preguntas verificadas.")
        if num_incorrectas_verificadas > 0:
             st.warning(f"Tienes {num_incorrectas_verificadas} preguntas incorrectas pendientes en este lote.")
        
        if num_total_verificadas > 0 and num_incorrectas_verificadas == 0 : # Todas correctas en el lote actual
            st.balloons()
            st.success("¡Todas las preguntas de este lote fueron correctas!")
            if not st.session_state[state_prefix + "preguntas_actuales"]: 
                 st.info("Presiona 'Cargar Preguntas' para el siguiente lote o si has terminado.")
        
        st.session_state[state_prefix + "resultados_verificacion"] = []


elif st.session_state.get(state_prefix + "quiz_finished", False):
    st.success("🎉 ¡Felicidades! Has respondido correctamente a todas las preguntas de este documento.")
    st.info("Puedes reiniciar el progreso o seleccionar otro documento.")

elif not st.session_state.get(state_prefix + "preguntas_actuales", []): 
    st.info("Has terminado las preguntas de este lote o no hay preguntas para cargar.")
    st.info("Presiona 'Cargar Preguntas' para obtener un nuevo lote.")