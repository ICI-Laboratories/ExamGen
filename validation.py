from jsonschema import validate, ValidationError
import streamlit as st

schema = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": { "type": "string" },
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": { "type": "string" },
                            "B": { "type": "string" },
                            "C": { "type": "string" },
                            "D": { "type": "string" }
                        }
                    },
                    "correct_answer": { "type": "string" }
                },
                "required": ["question", "options", "correct_answer"]
            }
        }
    },
    "required": ["questions"]
}

def is_valid_json(json_data):
    try:
        validate(instance=json_data, schema=schema)
        return True
    except ValidationError as e:
        st.error(f"Error en el JSON: {e.message}")
        return False
