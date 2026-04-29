from jsonschema import validate, ValidationError
import streamlit as st


schema = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "minLength": 5},
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": {"type": "string", "minLength": 1},
                            "B": {"type": "string", "minLength": 1},
                            "C": {"type": "string", "minLength": 1},
                            "D": {"type": "string", "minLength": 1},
                        },
                        "required": ["A", "B", "C", "D"],
                        "additionalProperties": False,
                    },
                    "correct_answer": {"type": "string", "enum": ["A", "B", "C", "D"]},
                },
                "required": ["question", "options", "correct_answer"],
            },
        }
    },
    "required": ["questions"],
}


def is_valid_json(json_data):
    """Validates JSON data against the schema. Returns True if valid, False otherwise."""
    try:
        validate(instance=json_data, schema=schema)
        return True
    except ValidationError as e:
        st.error(f"Error de Validación JSON: {e.message}\nEn la ruta: {list(e.path)}")

        return False
    except Exception as e:
        st.error(f"Error inesperado durante la validación JSON: {e}")
        return False
