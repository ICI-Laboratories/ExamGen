# --- START OF FILE lmstudio_api.py ---

import requests
import json
import os
from dotenv import load_dotenv
import streamlit as st
import logging

from validation import schema as questions_schema # Assuming this schema is flexible enough for variable question counts

logging.basicConfig(level=logging.INFO) # Consider moving to a central app config
load_dotenv()

LMSTUDIO_API_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")
# Define a practical max token limit for your LM Studio model if known, or use a conservative default
# This is for the *output* (generated questions), not the input context limit.
LMSTUDIO_MAX_OUTPUT_TOKENS = os.getenv("LMSTUDIO_MAX_OUTPUT_TOKENS", 2048)


def generate_questions_with_lmstudio(text_context: str, num_questions_desired: int, model_identifier: str = None):
    """
    Generates questions using LM Studio's structured output feature.
    text_context: The (potentially truncated) text to generate questions from.
    num_questions_desired: How many questions the user wants.
    model_identifier: Optional, to pass to LM Studio if you have multiple models loaded.
    """
    if not text_context or not text_context.strip():
        st.error("Error: El contexto proporcionado para generar preguntas está vacío.")
        logging.error("generate_questions_with_lmstudio called with empty text_context.")
        return None

    prompt = (
        f"Based on the following text, generate exactly {num_questions_desired} multiple-choice questions suitable for assessing understanding. "
        "Each question should have 4 options labeled A, B, C, and D, with one single correct answer indicated. "
        "Ensure your entire response is a single JSON object matching the provided schema."
        f"\n\n--- TEXT START ---\n{text_context}\n--- TEXT END ---"
    )

    headers = {'Content-Type': 'application/json'}

    # Adjust schema if it has fixed minItems/maxItems for the questions array.
    # For now, assuming 'questions_schema' is flexible (e.g., "minItems": 1 for the array).
    # If your schema is very strict about expecting exactly 5 questions, for example,
    # then LM Studio's `response_format` might enforce that, overriding the prompt.
    # It's usually better for the schema to define the structure of *one* question,
    # and the `questions` field to be an array of such question objects.
    structured_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "quiz_questions_format",
            "strict": True,
            "schema": questions_schema # Defined in validation.py
        }
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are an assistant that generates multiple-choice questions based on provided text, adhering strictly to the requested JSON format."},
            {"role": "user", "content": prompt}
        ],
        "response_format": structured_format,
        "temperature": 0.6,
        "max_tokens": int(LMSTUDIO_MAX_OUTPUT_TOKENS), # Max tokens for the *generated response*
        "stream": False
    }
    if model_identifier: # If you want to specify a model in LM Studio
        payload["model"] = model_identifier


    raw_response_content = ""

    try:
        logging.info(f"Sending request to LM Studio ({LMSTUDIO_API_URL}) for {num_questions_desired} questions. Context length approx: {len(text_context)} chars.")
        response = requests.post(LMSTUDIO_API_URL, headers=headers, json=payload, timeout=300) # Increased timeout
        response.raise_for_status()

        response_data = response.json()
        raw_response_content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not raw_response_content:
             st.error("Error: LM Studio devolvió una respuesta vacía.")
             logging.error("LM Studio returned empty content.")
             return None

        parsed_json = json.loads(raw_response_content)
        
        # Basic validation of returned structure (can be enhanced)
        if not isinstance(parsed_json, dict) or "questions" not in parsed_json or not isinstance(parsed_json["questions"], list):
            st.error(f"Error: LM Studio devolvió una estructura JSON inesperada. Se esperaba un objeto con una lista 'questions'. Recibido: {raw_response_content[:500]}")
            logging.error(f"LM Studio returned unexpected JSON structure. Expected dict with 'questions' list. Raw: {raw_response_content}")
            return None
        
        # You can also check if len(parsed_json["questions"]) == num_questions_desired here if needed,
        # though is_valid_json (from validation.py) will do more thorough checks.

        logging.info(f"Successfully received and parsed structured JSON from LM Studio. Generated {len(parsed_json.get('questions',[]))} questions.")
        return parsed_json

    except requests.exceptions.Timeout:
        st.error(f"Error: La solicitud a LM Studio excedió el tiempo límite ({300}s). El servidor podría estar ocupado o el modelo es muy lento procesando el contexto.")
        logging.error("Request to LM Studio timed out.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión al intentar conectar con LM Studio ({LMSTUDIO_API_URL}): {e}")
        logging.error(f"Connection error to LM Studio: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Error al decodificar la respuesta JSON de LM Studio: {e}")
        st.text_area("Respuesta recibida (con error JSON):", raw_response_content, height=200)
        logging.error(f"JSONDecodeError. Raw response: {raw_response_content}. Error: {e}")
        return None
    except Exception as e:
        st.error(f"Error inesperado durante la llamada a LM Studio: {e}")
        st.text_area("Respuesta recibida (error inesperado):", raw_response_content, height=200)
        logging.exception("Unexpected error during LM Studio call.")
        return None