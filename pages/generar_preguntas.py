import streamlit as st
from database import (
    get_db_connection,
    insertar_documento,
    insertar_preguntas_json,
    log_generation_attempt
)
from ocr import extract_text_with_ocr
from lmstudio_api import generate_questions_with_lmstudio
from validation import is_valid_json, schema
from utils import calcular_hash_completo
import time

# Este check es ahora redundante debido a app.py, pero se mantiene por robustez
if not st.experimental_user.is_logged_in:
    st.warning("Por favor, inicia sesión para generar preguntas.")
    st.stop()

st.header("📚 Generador de Preguntas desde PDF")

user_email = st.experimental_user.email
st.caption(f"Usuario: {user_email}")

conn = get_db_connection()
if not conn:
    st.error("Conexión a base de datos no disponible.")
    st.stop()

uploaded_file = st.file_uploader("Sube un archivo PDF", type="pdf", key="pdf_uploader")

if uploaded_file:
    st.info(f"Archivo cargado: **{uploaded_file.name}**")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Paso 1: Extracción de Texto (OCR)")
        text = None
        ocr_success = False
        start_time = time.time()
        try:
            with st.spinner("Extrayendo texto del PDF... (puede tardar)"):
                text = extract_text_with_ocr(uploaded_file)
            if text and text.strip():
                st.success("Texto extraído correctamente.")
                st.text_area("Texto Extraído (primeros 1000 caracteres)", text[:1000] + "...", height=200)
                ocr_success = True
            else:
                st.warning("No se pudo extraer texto o el texto está vacío.")
        except Exception as e:
            st.error(f"Error durante OCR: {e}")
            log_generation_attempt(conn, uploaded_file.name, False, False, 0, None, f"OCR Error: {e}", time.time() - start_time)
            st.stop()

    with col2:
        st.subheader("Paso 2: Generación de Preguntas (LLM)")
        if ocr_success and text:
            json_questions = None
            llm_success = False
            doc_id = None
            num_inserted = 0
            generation_error = None
            try:
                with st.spinner("Generando preguntas con LM Studio... (puede tardar)"):
                    json_questions = generate_questions_with_lmstudio(text)

                if json_questions and isinstance(json_questions, dict) and "questions" in json_questions:
                    if is_valid_json(json_questions):
                        st.success("Preguntas generadas y validadas correctamente!")
                        st.json(json_questions)
                        llm_success = True
                        hash_documento = calcular_hash_completo(json_questions)

                        with st.spinner("Guardando en la base de datos..."):
                            doc_id, is_new = insertar_documento(conn, uploaded_file.name, hash_documento)
                            if is_new:
                                num_inserted = insertar_preguntas_json(conn, json_questions, doc_id)
                                st.success(f"Documento nuevo. {num_inserted} preguntas insertadas/actualizadas para el Documento ID: {doc_id}.")
                                log_generation_attempt(conn, uploaded_file.name, True, True, len(json_questions.get("questions", [])), doc_id, None, time.time() - start_time)
                            else:
                                st.warning(f"Este conjunto de preguntas (hash: {hash_documento[:8]}...) ya existe en la base de datos para el Documento ID: {doc_id}. No se insertaron nuevas preguntas.")
                                log_generation_attempt(conn, uploaded_file.name, True, True, 0, doc_id, "Duplicate hash found", time.time() - start_time)
                    else:
                        generation_error = "JSON validation failed."
                        llm_success = False
                        log_generation_attempt(conn, uploaded_file.name, True, False, 0, None, generation_error, time.time() - start_time)
                else:
                    generation_error = "LLM did not return valid question structure."
                    llm_success = False
                    log_generation_attempt(conn, uploaded_file.name, True, False, 0, None, generation_error, time.time() - start_time)

            except Exception as e:
                st.error(f"Error durante la generación o guardado de preguntas: {e}")
                generation_error = f"Processing Error: {e}"
                llm_success = False
                log_generation_attempt(conn, uploaded_file.name, True, False, 0, doc_id, generation_error, time.time() - start_time)
        elif not text:
             st.warning("No hay texto extraído para generar preguntas.")
        else:
             st.info("Esperando extracción de texto completa.")

    st.divider()
    st.subheader("Esquema JSON Esperado")
    st.json(schema)