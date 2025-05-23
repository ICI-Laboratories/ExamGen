# --- START OF FILE utils.py ---

import hashlib
import json
# import re # Not used
import streamlit as st
# from datetime import datetime # Not used

def calcular_hash_completo(preguntas_json):
    """Calculates MD5 hash of the questions JSON for duplicate detection."""
    serialized = json.dumps(preguntas_json, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.md5(serialized).hexdigest()

def enumerar_opciones(opciones_dict):
    """Ensures options are returned as a dictionary with uppercase keys A, B, C, D."""
    if not isinstance(opciones_dict, dict):
        # Log or handle error appropriately if st.error is not desired in a utility function
        # For now, keeping st.error as it's used within a Streamlit app context
        st.error(f"Error interno: Se esperaba un diccionario de opciones, se recibió {type(opciones_dict)}")
        return {}

    standardized_options = {str(k).upper(): v for k, v in opciones_dict.items()}
    valid_keys = {"A", "B", "C", "D"}
    # Ensure all valid keys are present, even if with None or empty string if missing,
    # or filter only existing ones as done here.
    # The current approach only includes keys A,B,C,D if they are in standardized_options.
    final_options = {k: standardized_options[k] for k in valid_keys if k in standardized_options}
    
    # If strict A,B,C,D options are required, you might want to ensure all are present:
    # final_options = {k: standardized_options.get(k, "") for k in valid_keys} # Example: default to empty string
    return final_options


def verificar_respuestas(respuestas_seleccionadas_dict, preguntas_actuales):
    """
    Verifies user answers against correct answers.
    This function is a general utility and is NOT currently used by realizar_cuestionario.py,
    as that file implements its own verification logic tailored to its needs (timing, DB logging).
    It's kept here as it might be useful for other purposes or future refactoring.

    Args:
        respuestas_seleccionadas_dict (dict): {index: 'selected_letter'}
        preguntas_actuales (list): List of question dictionaries from the database.
                                   Each dict must have 'correct_answer' and 'id'.

    Returns:
        tuple: (list_of_incorrect_question_dicts, list_of_boolean_results)
               - list_of_incorrect_question_dicts: Contains full question dicts for incorrect answers.
               - list_of_boolean_results: A list of booleans, True if correct, False if incorrect,
                                          corresponding to preguntas_actuales order.
    """
    incorrectas_info_full_question = [] # Stores full question dicts for incorrect answers
    resultados_bool = []

    for i, pregunta in enumerate(preguntas_actuales):
        # Ensure 'correct_answer' key exists, otherwise this util is misused
        if "correct_answer" not in pregunta:
            # Handle error: log, raise exception, or mark as incorrect by default
            # For a utility, raising an error or logging might be better than st.error
            # print(f"Warning: 'correct_answer' missing in pregunta at index {i}, ID {pregunta.get('id')}")
            resultados_bool.append(False) # Default to incorrect if malformed
            # Optionally add to incorrectas_info_full_question if it should be surfaced
            # incorrectas_info_full_question.append(pregunta) 
            continue

        seleccionada = respuestas_seleccionadas_dict.get(i, "").strip().upper() # User's choice, e.g., "A"
        correcta = pregunta["correct_answer"].strip().upper() # Correct answer letter, e.g., "A"

        is_correct_answer = (seleccionada == correcta)
        resultados_bool.append(is_correct_answer)

        if not is_correct_answer:
            incorrectas_info_full_question.append(pregunta)
            # You could also append a more detailed dict here if needed:
            # incorrectas_info_detailed.append({
            #      "index": i,
            #      "pregunta_id": pregunta.get("id"),
            #      "question_text": pregunta.get("question"),
            #      "user_selected": seleccionada if seleccionada else "No respondida",
            #      "correct_answer_letter": correcta
            # })
            
    return incorrectas_info_full_question, resultados_bool

# --- END OF FILE utils.py ---