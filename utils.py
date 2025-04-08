# --- START OF FILE utils.py ---

import hashlib
import json
import re # Keep re in case needed elsewhere, but not for clean_json_response
import streamlit as st
from datetime import datetime

def calcular_hash_completo(preguntas_json):
    """Calculates MD5 hash of the questions JSON for duplicate detection."""
    serialized = json.dumps(preguntas_json, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.md5(serialized).hexdigest()

# REMOVED clean_json_response function

def enumerar_opciones(opciones_dict):
    """Ensures options are returned as a dictionary with uppercase keys A, B, C, D."""
    if not isinstance(opciones_dict, dict):
        st.error(f"Error interno: Se esperaba un diccionario de opciones, se recibió {type(opciones_dict)}")
        return {}

    standardized_options = {str(k).upper(): v for k, v in opciones_dict.items()}
    valid_keys = {"A", "B", "C", "D"}
    final_options = {k: standardized_options[k] for k in valid_keys if k in standardized_options}
    return final_options


def verificar_respuestas(respuestas_seleccionadas_dict, preguntas_actuales):
    """
    Verifies user answers against correct answers.

    Args:
        respuestas_seleccionadas_dict (dict): {index: 'selected_letter'}
        preguntas_actuales (list): List of question dictionaries.

    Returns:
        tuple: (list_of_incorrect_question_dicts, list_of_boolean_results)
    """
    incorrectas_info = []
    resultados_bool = []

    for i, pregunta in enumerate(preguntas_actuales):
        seleccionada = respuestas_seleccionadas_dict.get(i, "").strip().upper()
        correcta = pregunta.get("correct_answer", "").strip().upper()

        if seleccionada == correcta:
            resultados_bool.append(True)
        else:
            resultados_bool.append(False)
            incorrectas_info.append({
                 "index": i,
                 "pregunta_id": pregunta.get("id"),
                 "question": pregunta.get("question"),
                 "selected": seleccionada if seleccionada else "No respondida",
                 "correct": correcta
            })

    indices_incorrectos = {info['index'] for info in incorrectas_info}
    preguntas_incorrectas_list = [p for i, p in enumerate(preguntas_actuales) if i in indices_incorrectos]

    return preguntas_incorrectas_list, resultados_bool

# --- END OF FILE utils.py ---