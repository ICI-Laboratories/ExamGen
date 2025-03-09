import streamlit as st
from database import (
    conectar_postgresql,
    insertar_documento,
    insertar_preguntas_json,
    obtener_documentos_cargados,
    obtener_preguntas_por_documento,
    reiniciar_progreso,
    registrar_progreso,
    registrar_respuesta,
    obtener_preguntas_aleatorias
)
from ocr import extract_text_with_ocr
from lmstudio_api import generate_questions_with_lmstudio
from validation import is_valid_json
from utils import (
    calcular_hash_completo,
    enumerar_opciones,
    verificar_respuestas
)
from estadisticas import (
    obtener_pregunta_mas_equivocada,
    obtener_promedio_tiempo_respuesta,
    obtener_estadisticas_por_documento
)
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def main():
    st.title("Prototipo para Generación de Preguntas y Aplicación de Active Recall")

    # Conectar a PostgreSQL
    try:
        conn = conectar_postgresql()
    except Exception as e:
        st.error(e)
        return

    # Simulación de un usuario
    usuario_id = "usuario_1"
    documentos_cargados = obtener_documentos_cargados(conn)
    if documentos_cargados:
        nombres_documentos = [doc["nombre"] for doc in documentos_cargados]
    else:
        nombres_documentos = []

    # Crear pestañas para las secciones
    seccion = st.sidebar.selectbox("Selecciona una sección", ["Generar Preguntas", "Realizar Cuestionario", "Estadísticas"])

    if seccion == "Generar Preguntas":
        st.header("Generador de Preguntas")
        uploaded_file = st.file_uploader("Sube un archivo PDF", type="pdf")

        if uploaded_file:
            st.write("Extrayendo texto del PDF...")
            try:
                text = extract_text_with_ocr(uploaded_file)
                st.write("Texto extraído:", text)

                st.write("Generando preguntas, espere un poco ...")
                json_questions = generate_questions_with_lmstudio(text)

                if json_questions and is_valid_json(json_questions):
                    st.write("Preguntas generadas correctamente:", json_questions)

                    # Calcular hash del documento
                    hash_documento = calcular_hash_completo(json_questions)

                    # Insertar metadatos del documento
                    documento_id = insertar_documento(conn, uploaded_file.name, hash_documento)
                    if documento_id:
                        # Insertar preguntas en la base de datos
                        num_preguntas_insertadas = insertar_preguntas_json(conn, json_questions, documento_id)
                        st.success(f"{num_preguntas_insertadas} preguntas insertadas correctamente.")
                    else:
                        st.warning("Este documento ya ha sido cargado anteriormente.")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

    elif seccion == "Realizar Cuestionario":
        st.header("Recuperación Activa")

        # Mostrar documentos cargados en la barra lateral
        documentos_cargados = obtener_documentos_cargados(conn)
        nombres_documentos = [doc["nombre"] for doc in documentos_cargados]
        documento_seleccionado = st.sidebar.selectbox("Selecciona el documento del cual extraer preguntas", nombres_documentos)

        if documento_seleccionado:
            st.write(f"Documento seleccionado: {documento_seleccionado}")
            documento_id = next(doc["id"] for doc in documentos_cargados if doc["nombre"] == documento_seleccionado)

            # Inicializar variables de sesión
            if 'progreso' not in st.session_state:
                st.session_state.progreso = 0
            if 'preguntas_resueltas' not in st.session_state:
                st.session_state.preguntas_resueltas = 0
            if 'respuestas_correctas' not in st.session_state:
                st.session_state.respuestas_correctas = 0
            if 'preguntas_actuales' not in st.session_state:
                st.session_state.preguntas_actuales = []
            if 'documento_anterior' not in st.session_state:
                st.session_state.documento_anterior = documento_seleccionado
            if 'preguntas_terminadas' not in st.session_state:
                st.session_state.preguntas_terminadas = False

            # Reiniciar el progreso si se selecciona un documento diferente
            if st.session_state.documento_anterior != documento_seleccionado:
                reiniciar_progreso(conn, usuario_id, documento_id)
                st.session_state.documento_anterior = documento_seleccionado

            # Obtener el total de preguntas para la barra de progreso
            total_preguntas = len(obtener_preguntas_por_documento(conn, documento_id))
            st.write(f"Total de preguntas en este documento: {total_preguntas}")

            if total_preguntas > 0:
                # Mostrar barra de progreso
                progreso_actual = st.session_state.preguntas_resueltas / total_preguntas
                st.progress(progreso_actual)

                # Botón "Generar preguntas"
                if st.button("Generar preguntas"):
                    # Obtener preguntas aleatorias no respondidas
                    st.session_state.preguntas_actuales = obtener_preguntas_aleatorias(conn, documento_id, usuario_id)
                    st.session_state.progreso = 0
                    # Resetear las selecciones anteriores
                    keys_to_remove = [key for key in st.session_state.keys() if key.startswith("pregunta_")]
                    for key in keys_to_remove:
                        del st.session_state[key]

                if st.session_state.preguntas_actuales:
                    respuestas_seleccionadas = []
                    for i, pregunta in enumerate(st.session_state.preguntas_actuales):
                        st.write(f"**{pregunta['question']}**")

                        # Verifica si 'options' ya es un diccionario
                        if isinstance(pregunta['options'], dict):
                            opciones_enumeradas = enumerar_opciones(pregunta['options'])
                        else:
                            opciones_enumeradas = enumerar_opciones(json.loads(pregunta['options']))

                        # Mostrar las opciones con letras
                        opciones_mostradas = [f"{letra}) {opcion}" for letra, opcion in opciones_enumeradas.items()]

                        # Registrar tiempo de inicio si no existe ya para esta pregunta
                        if f"start_time_{i}" not in st.session_state:
                            st.session_state[f"start_time_{i}"] = datetime.now()

                        seleccion = st.radio(
                            f"Selecciona la respuesta para la pregunta {i + 1}",
                            options=opciones_mostradas,
                            key=f"pregunta_{i}"
                        )
                        # Extraer la letra seleccionada
                        seleccion_letra = seleccion.split(')', 1)[0].strip().upper()
                        respuestas_seleccionadas.append(seleccion_letra)

                    if st.button("Verificar"):
                        # Verificar las respuestas seleccionadas
                        for i, pregunta in enumerate(st.session_state.preguntas_actuales):
                            # Calcular tiempo de respuesta para esta pregunta
                            start_time = st.session_state.get(f"start_time_{i}", datetime.now())
                            end_time = datetime.now()
                            tiempo_respuesta = end_time - start_time

                            correcta = pregunta["correct_answer"].strip().upper()
                            seleccionada = respuestas_seleccionadas[i].strip().upper()
                            es_correcta = (seleccionada == correcta)

                            # Registrar estadísticas
                            registrar_respuesta(
                                conn=conn,
                                usuario_id=usuario_id,
                                pregunta_id=pregunta["id"],
                                documento_id=documento_id,
                                tiempo_respuesta=tiempo_respuesta,
                                es_correcta=es_correcta
                            )
                            st.session_state.pop(f"start_time_{i}", None)

                        incorrectas, resultados = verificar_respuestas(respuestas_seleccionadas, st.session_state.preguntas_actuales)

                        # Mostrar resultados de las respuestas
                        for i, resultado in enumerate(resultados):
                            if resultado:
                                st.success(f"La respuesta a la pregunta {i + 1} es correcta.")
                            else:
                                st.error(f"La respuesta a la pregunta {i + 1} es incorrecta.")

                        # Actualizar el progreso del usuario en la interfaz
                        preguntas_correctas_ids = [pregunta['id'] for pregunta, correcta in zip(st.session_state.preguntas_actuales, resultados) if correcta]
                        registrar_progreso(conn, usuario_id, documento_id, preguntas_correctas_ids)
                        st.session_state.preguntas_resueltas += len(preguntas_correctas_ids)

                        # Filtrar solo las preguntas incorrectas para la próxima ronda
                        st.session_state.preguntas_actuales = [pregunta for pregunta, correcta in zip(st.session_state.preguntas_actuales, resultados) if not correcta]

                        # Actualizar el progreso
                        progreso_actual = st.session_state.preguntas_resueltas / total_preguntas
                        st.progress(progreso_actual)

                        # Verificar si todas las preguntas han sido contestadas
                        if st.session_state.preguntas_resueltas >= total_preguntas:
                            st.session_state.preguntas_terminadas = True

                        # Mensaje si todas las preguntas han sido contestadas correctamente
                        if not st.session_state.preguntas_actuales:
                            st.success("¡Has respondido correctamente a todas las preguntas!")

                # Mostrar botón para reiniciar si se han terminado todas las preguntas
                if st.session_state.preguntas_terminadas:
                    if st.button("Reiniciar cuestionario"):
                        reiniciar_progreso(conn, usuario_id, documento_id)

    elif seccion == "Estadísticas":
        st.header("Estadísticas")

        st.subheader("Estadísticas personales")
        pregunta_mas_equivocada = obtener_pregunta_mas_equivocada(conn, usuario_id=usuario_id)
        promedio_tiempo = obtener_promedio_tiempo_respuesta(conn, usuario_id=usuario_id)

        if pregunta_mas_equivocada:
            st.write(f"Pregunta más equivocada: ID {pregunta_mas_equivocada['pregunta_id']} (Errores: {pregunta_mas_equivocada['errores']})")
        else:
            st.write("No hay suficientes datos para calcular las estadísticas personales.")

        if promedio_tiempo is not None:
            st.write(f"El tiempo promedio por pregunta es: {promedio_tiempo:.2f} segundos")
        else:
            st.write("No hay datos de tiempo disponibles.")

        # Sección: Estadísticas generales por documento
        st.subheader("Estadísticas generales por documento")
        documento_seleccionado = st.selectbox("Selecciona un documento", nombres_documentos)

        if documento_seleccionado:
            documento_id = next(doc["id"] for doc in documentos_cargados if doc["nombre"] == documento_seleccionado)
            estadisticas_documento = obtener_estadisticas_por_documento(conn, documento_id)

            if estadisticas_documento:
                # Convertir los datos a un DataFrame
                df = pd.DataFrame(estadisticas_documento)

                # Mostrar la tabla con las estadísticas
                st.dataframe(df)

                # Gráfico: Tiempo promedio por pregunta
                st.subheader("Gráfico de Tiempo Promedio por Pregunta")
                fig, ax = plt.subplots()
                ax.bar(df["pregunta_id"], df["tiempo_promedio"])
                ax.set_xlabel("ID de Pregunta")
                ax.set_ylabel("Tiempo Promedio (segundos)")
                ax.set_title("Tiempo Promedio por Pregunta")
                st.pyplot(fig)

                # Gráfico: Respuestas correctas e incorrectas
                st.subheader("Gráfico de Respuestas Correctas vs Incorrectas")
                fig, ax = plt.subplots()
                ax.bar(df["pregunta_id"], df["correctas"], label="Correctas", alpha=0.7)
                ax.bar(df["pregunta_id"], df["incorrectas"], label="Incorrectas", alpha=0.7)
                ax.set_xlabel("ID de Pregunta")
                ax.set_ylabel("Número de Respuestas")
                ax.set_title("Respuestas Correctas vs Incorrectas")
                ax.legend()
                st.pyplot(fig)
            else:
                st.write("No hay estadísticas disponibles para este documento.")

    # Cerrar la conexión al finalizar
    conn.close()

if __name__ == "__main__":
    main()
