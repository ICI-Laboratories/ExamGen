# --- START OF FILE lmstudio_api.py ---

import requests
import json
import os
from dotenv import load_dotenv
import streamlit as st
import logging

# Import the schema definition from your validation file
from validation import schema as questions_schema

logging.basicConfig(level=logging.INFO)
load_dotenv()

LMSTUDIO_API_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")

def generate_questions_with_lmstudio(text):
    """
    Generates questions using LM Studio's structured output feature.
    """
    # Simplified prompt focusing on the task, not the format
    prompt = (
        "Based on the following text, generate exactly 5 multiple-choice questions suitable for assessing understanding. "
        "Each question should have 4 options labeled A, B, C, and D, with one single correct answer indicated."
        f"\n\n--- TEXT START ---\n{text}\n--- TEXT END ---"
    )

    headers = {'Content-Type': 'application/json'}

    # Construct the structured response format using the imported schema
    structured_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "quiz_questions_format", # Descriptive name
            "strict": True, # Enforce strict adherence to the schema
            "schema": questions_schema # Use the schema defined in validation.py
        }
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are an assistant that generates multiple-choice questions based on provided text."},
            {"role": "user", "content": prompt}
        ],
        "response_format": structured_format, # Add the structured format parameter
        "temperature": 0.6, # Adjust temperature as needed
        "max_tokens": 2048, # Increase if needed for complex schemas/longer answers
        "stream": False
        # You might need to specify the model if multiple are loaded in LM Studio
        # "model": "loaded-model-name.gguf"
    }

    raw_response_content = "" # Initialize to store raw response for debugging

    try:
        logging.info(f"Sending request to LM Studio: {LMSTUDIO_API_URL}")
        response = requests.post(LMSTUDIO_API_URL, headers=headers, json=payload, timeout=180) # Increased timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        # Extract the content which *should* now be just the valid JSON string
        raw_response_content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not raw_response_content:
             st.error("Error: LM Studio devolvió una respuesta vacía.")
             logging.error("LM Studio returned empty content.")
             return None

        # Attempt to parse the JSON content directly
        parsed_json = json.loads(raw_response_content)

        # Optional but recommended: Re-validate the parsed structure just in case
        # LM Studio's adherence isn't perfect or the schema has subtle issues.
        # (Requires importing is_valid_json)
        # from validation import is_valid_json
        # if not is_valid_json(parsed_json):
        #     logging.error(f"Parsed JSON failed validation against schema. Received: {raw_response_content}")
        #     # st.error is already called by is_valid_json if it fails
        #     return None

        logging.info("Successfully received and parsed structured JSON from LM Studio.")
        return parsed_json # Return the parsed Python dictionary

    except requests.exceptions.Timeout:
        st.error(f"Error: La solicitud a LM Studio excedió el tiempo límite ({180}s). El servidor podría estar ocupado o el modelo es muy lento.")
        logging.error("Request to LM Studio timed out.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión al intentar conectar con LM Studio ({LMSTUDIO_API_URL}): {e}")
        logging.error(f"Connection error to LM Studio: {e}")
        return None
    except json.JSONDecodeError as e:
        # This error should be much less common now with structured output
        st.error(f"Error al decodificar la respuesta JSON de LM Studio, incluso con formato estructurado: {e}")
        st.text_area("Respuesta recibida (con error JSON):", raw_response_content, height=200)
        logging.error(f"JSONDecodeError despite structured output. Raw response: {raw_response_content}. Error: {e}")
        return None
    except Exception as e:
        st.error(f"Error inesperado durante la llamada a LM Studio: {e}")
        st.text_area("Respuesta recibida (error inesperado):", raw_response_content, height=200)
        logging.exception("Unexpected error during LM Studio call.") # Log full traceback
        return None

# --- END OF FILE lmstudio_api.py ---