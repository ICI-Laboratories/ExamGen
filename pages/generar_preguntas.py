# MIT License — 2025
# Copyright (c) 2025
# Yohana Yamille Ornelas Ochoa, Kenya Alexandra Ramos Valadez,
# Pedro Antonio Ibarra Facio


import logging
import streamlit as st
from database import (
    get_db_connection,
    insertar_documento,
    insertar_preguntas_json,
    log_generation_attempt,
    insert_page_contents,       # New import
    get_page_contents_for_document # New import
)
from ocr import extract_text_and_pages_with_ocr # Updated import
from lmstudio_api import generate_questions_with_lmstudio
from validation import is_valid_json, schema
from utils import calcular_hash_completo
import time
import hashlib # For hashing page content

if not st.user.is_logged_in:
    st.warning("Por favor, inicia sesión para generar preguntas.")
    st.stop()

st.header("📚 Generador de Preguntas desde PDF")

user_email = st.user.email
st.caption(f"Usuario: {user_email}")

# --- Configuration for token counting/truncation ---
# This is a VERY ROUGH heuristic. Replace with a proper tokenizer for your model.
# Average characters per token (e.g., for English, often around 4)
CHARS_PER_TOKEN_ESTIMATE = 4
# Max tokens your LLM can handle for the input CONTEXT (not output).
# Check your LM Studio model's config. Leave a buffer.
MODEL_CONTEXT_TOKEN_LIMIT = st.secrets.get("MODEL_CONTEXT_TOKEN_LIMIT", 20000) # Example: 20k tokens, from secrets
SAFETY_BUFFER_TOKENS = st.secrets.get("SAFETY_BUFFER_TOKENS", 2000) # Tokens reserved for prompt, system messages, etc.

def estimate_tokens(text):
    return len(text) // CHARS_PER_TOKEN_ESTIMATE

def truncate_text_by_tokens(text, max_tokens):
    max_chars = max_tokens * CHARS_PER_TOKEN_ESTIMATE
    if len(text) > max_chars:
        truncated = text[:max_chars]
        # Try to truncate at a sentence boundary if possible (simple version)
        last_period = truncated.rfind('.')
        if last_period != -1:
            truncated = truncated[:last_period+1]
        logging.warning(f"Context truncated from {len(text)} chars to {len(truncated)} chars to fit token limit.")
        return truncated
    return text
# --- End of token config ---

conn = get_db_connection()
if not conn:
    st.error("Conexión a base de datos no disponible.")
    st.stop()

# Initialize session state for this page if not already done
if 'gen_doc_id' not in st.session_state:
    st.session_state.gen_doc_id = None
if 'gen_pages_data' not in st.session_state:
    st.session_state.gen_pages_data = []
if 'gen_total_pages' not in st.session_state:
    st.session_state.gen_total_pages = 0
if 'gen_ocr_done' not in st.session_state:
    st.session_state.gen_ocr_done = False

uploaded_file = st.file_uploader("Sube un archivo PDF", type="pdf", key="pdf_uploader_main")

if uploaded_file and not st.session_state.gen_ocr_done:
    st.info(f"Archivo cargado: **{uploaded_file.name}**. Procesando...")
    pdf_bytes = uploaded_file.getvalue() # Read once
    pdf_size_bytes = len(pdf_bytes)
    start_ocr_time = time.time()

    try:
        with st.spinner("Extrayendo texto del PDF página por página... (puede tardar)"):
            pages_data, total_pages = extract_text_and_pages_with_ocr(pdf_bytes)

        if pages_data:
            st.success(f"Texto extraído de {total_pages} páginas.")
            st.session_state.gen_pages_data = pages_data
            st.session_state.gen_total_pages = total_pages
            st.session_state.gen_ocr_done = True

            # Create a hash for the entire document based on concatenated page texts (simple version)
            # A more robust hash would be based on the PDF file bytes itself before OCR
            # For now, let's use a hash of the uploaded file name and size as a proxy for the document
            # or the actual file hash if you implement it.
            # Here, we'll use a simpler "document identifier" approach for now for `insertar_documento`'s hash
            temp_doc_hash_input = uploaded_file.name + str(pdf_size_bytes)
            document_content_hash = hashlib.sha256(temp_doc_hash_input.encode('utf-8')).hexdigest()


            st.session_state.gen_doc_id, is_new_doc = insertar_documento(conn,
                                                                    nombre_documento=uploaded_file.name,
                                                                    hash_documento=document_content_hash, # This hash represents the file
                                                                    num_pages=total_pages,
                                                                    pdf_size=pdf_size_bytes)
            if is_new_doc or not get_page_contents_for_document(conn, st.session_state.gen_doc_id): # If new or no page content yet
                with st.spinner("Guardando contenido de páginas en la base de datos..."):
                    insert_page_contents(conn, st.session_state.gen_doc_id, pages_data)
                st.success("Contenido de páginas guardado.")
            else:
                st.info("Contenido de páginas ya existente para este documento.")
            st.rerun() # Rerun to show next steps now that OCR is done
        else:
            st.warning("No se pudo extraer texto de ninguna página.")
            st.session_state.gen_ocr_done = False # Reset
    except Exception as e:
        st.error(f"Error durante OCR o guardado inicial: {e}")
        log_generation_attempt(conn, usuario_id=user_email, filename=uploaded_file.name,
                               ocr_success=False, llm_success=False, model_used=None,
                               num_questions=0, doc_id=st.session_state.get('gen_doc_id'),
                               error=f"OCR/DB Error: {e}", duration_seconds=time.time() - start_ocr_time)
        st.session_state.gen_ocr_done = False # Reset

if st.session_state.gen_ocr_done and st.session_state.gen_doc_id:
    st.success(f"Documento '{uploaded_file.name}' procesado (ID: {st.session_state.gen_doc_id}, {st.session_state.gen_total_pages} páginas).")
    st.markdown("### Configuración de Generación de Preguntas")

    page_options = [f"Página {i+1}" for i in range(st.session_state.gen_total_pages)]
    
    selection_mode = st.radio("Seleccionar páginas para generar preguntas:", ("Todas las páginas", "Páginas específicas"), key="page_selection_mode")

    selected_page_numbers_for_context = []
    if selection_mode == "Páginas específicas":
        selected_pages_display = st.multiselect(
            "Elige las páginas:",
            options=page_options,
            key="pages_multiselect"
        )
        # Convert display strings "Página X" back to 1-indexed numbers
        selected_page_numbers_for_context = [int(p.split(" ")[1]) for p in selected_pages_display]
    else: # "Todas las páginas"
        selected_page_numbers_for_context = list(range(1, st.session_state.gen_total_pages + 1))

    num_questions_desired = st.number_input(
        "Número de preguntas a generar:",
        min_value=1,
        max_value=20, # Sensible max to avoid overly long LLM calls
        value=5,
        step=1,
        key="num_questions_input"
    )

    # Placeholder for difficulty - can be added to prompt later
    # difficulty = st.selectbox("Nivel de dificultad:", ["Fácil", "Medio", "Difícil"], key="difficulty_select")


    if st.button("🚀 Generar Preguntas", key="generate_questions_button"):
        if not selected_page_numbers_for_context:
            st.warning("Por favor, selecciona al menos una página.")
            st.stop()

        with st.spinner("Ensamblando contexto y generando preguntas..."):
            start_generation_time = time.time()
            
            # 1. Fetch page content for selected pages
            page_contents_list = get_page_contents_for_document(conn, st.session_state.gen_doc_id, selected_page_numbers_for_context)
            
            if not page_contents_list:
                st.error("No se encontró contenido para las páginas seleccionadas.")
                st.stop()

            # 2. Assemble context
            # For now, just concatenate the full text of selected pages
            # Later, this is where you'd use summaries if implemented
            assembled_context = "\n\n".join([pc['text_content'] for pc in page_contents_list if pc['text_content']])
            
            if not assembled_context.strip():
                st.error("El contexto ensamblado de las páginas seleccionadas está vacío.")
                st.stop()

            # 3. Tokenize and Truncate (CRITICAL STEP)
            # available_tokens_for_context = MODEL_CONTEXT_TOKEN_LIMIT - estimate_tokens(PROMPT_TEMPLATE_APPROX_LENGTH) - SAFETY_BUFFER_TOKENS
            # For simplicity, let's use a direct character limit derived from token limit
            # This assumes prompt tokens are part of SAFETY_BUFFER_TOKENS implicitly
            max_context_tokens = MODEL_CONTEXT_TOKEN_LIMIT - SAFETY_BUFFER_TOKENS
            final_context_for_llm = truncate_text_by_tokens(assembled_context, max_context_tokens)

            # 4. Call LLM
            json_questions = None
            llm_success = False
            generation_error_msg = None
            model_used_for_gen = None # TODO: Get from LMStudio if possible

            try:
                json_questions = generate_questions_with_lmstudio(final_context_for_llm, num_questions_desired, model_identifier=model_used_for_gen)

                if json_questions and isinstance(json_questions, dict) and "questions" in json_questions:
                    if is_valid_json(json_questions): # validation.py
                        st.success("Preguntas generadas y validadas correctamente!")
                        st.json(json_questions) # Display generated questions
                        llm_success = True
                        
                        # Calculate hash of the *generated questions* for duplicate question set detection
                        questions_set_hash = calcular_hash_completo(json_questions)
                        
                        # NOTE: The current `insertar_documento` uses a hash of the *file*.
                        # If you want to avoid inserting duplicate *sets of questions* even if from different source files
                        # or different page selections of the same file, you'd need a different logic or table.
                        # For now, we link questions to the `st.session_state.gen_doc_id`.

                        with st.spinner("Guardando preguntas en la base de datos..."):
                            num_inserted = insertar_preguntas_json(conn, json_questions, st.session_state.gen_doc_id)
                            if num_inserted > 0:
                                st.success(f"{num_inserted} preguntas nuevas insertadas para el Documento ID: {st.session_state.gen_doc_id}.")
                            else:
                                st.info("No se insertaron preguntas nuevas (posiblemente ya existían o hubo un error).")
                    else:
                        generation_error_msg = "JSON validation failed after generation."
                        # st.error is called by is_valid_json
                else:
                    generation_error_msg = "LLM did not return valid question structure or returned None."
                    if not json_questions: # If json_questions itself is None from the API call
                        st.error("La API de LM Studio no devolvió datos de preguntas.")
                    else: # Structure is wrong
                        st.error(f"Estructura de preguntas inválida: {str(json_questions)[:200]}...")


            except Exception as e:
                st.error(f"Error durante la generación o guardado de preguntas: {e}")
                generation_error_msg = f"LLM/DB Processing Error: {e}"
                llm_success = False
            
            total_duration = time.time() - start_generation_time
            log_generation_attempt(conn,
                                   usuario_id=user_email,
                                   filename=uploaded_file.name, # Assuming uploaded_file is still in scope
                                   ocr_success=True, # OCR was done earlier
                                   llm_success=llm_success,
                                   model_used=model_used_for_gen,
                                   num_questions=len(json_questions['questions']) if llm_success and json_questions and 'questions' in json_questions else 0,
                                   doc_id=st.session_state.gen_doc_id,
                                   error=generation_error_msg,
                                   duration_seconds=total_duration)
            
            if llm_success:
                 st.balloons()
            else:
                if not generation_error_msg: # If no specific error message was set from try-except
                    st.error("Falló la generación de preguntas. Revisa los logs de LM Studio.")


    st.markdown("---")
    st.subheader("Previsualización de Contenido de Página (Primeros 500 caracteres)")
    if st.session_state.gen_pages_data:
        preview_page_num_str = st.selectbox(
            "Selecciona página para previsualizar:",
            options=[f"Página {pd['page_number']}" for pd in st.session_state.gen_pages_data],
            key="page_preview_select"
        )
        if preview_page_num_str:
            preview_page_num = int(preview_page_num_str.split(" ")[1])
            for pd_item in st.session_state.gen_pages_data:
                if pd_item['page_number'] == preview_page_num:
                    st.text_area(f"Contenido Página {preview_page_num}:", pd_item['text'][:500]+"...", height=150, key=f"preview_{preview_page_num}")
                    break


# Clear button to allow uploading a new file
if st.session_state.gen_ocr_done or uploaded_file:
    if st.button("Limpiar y Cargar Nuevo PDF", key="clear_state_button"):
        # Reset relevant session state keys
        keys_to_reset = ['gen_doc_id', 'gen_pages_data', 'gen_total_pages', 'gen_ocr_done', 'pdf_uploader_main']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

st.divider()
st.subheader("Esquema JSON Esperado por el LLM para Preguntas")
st.json(schema) # from validation.py