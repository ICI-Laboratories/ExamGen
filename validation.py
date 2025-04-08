# --- START OF FILE validation.py ---

from jsonschema import validate, ValidationError
import streamlit as st

# Your schema remains the same
schema = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1, # Ensure at least one question is generated
            "items": {
                "type": "object",
                "properties": {
                    "question": { "type": "string", "minLength": 5 }, # Basic check
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": { "type": "string", "minLength": 1 },
                            "B": { "type": "string", "minLength": 1 },
                            "C": { "type": "string", "minLength": 1 },
                            "D": { "type": "string", "minLength": 1 }
                        },
                        "required": ["A", "B", "C", "D"], # Ensure all 4 options exist
                        "additionalProperties": False # Disallow options other than A,B,C,D
                    },
                    "correct_answer": {
                        "type": "string",
                        "enum": ["A", "B", "C", "D"] # Ensure correct answer is one of the option keys
                        }
                },
                "required": ["question", "options", "correct_answer"]
            }
        }
    },
    "required": ["questions"]
}

def is_valid_json(json_data):
    """Validates JSON data against the schema. Returns True if valid, False otherwise."""
    try:
        validate(instance=json_data, schema=schema)
        return True
    except ValidationError as e:
        st.error(f"Error de Validación JSON: {e.message}\nEn la ruta: {list(e.path)}")
        # Optionally show the problematic part of the JSON
        # st.json(e.instance) # Be careful showing potentially large/complex data
        return False
    except Exception as e: # Catch other potential errors during validation
        st.error(f"Error inesperado durante la validación JSON: {e}")
        return False