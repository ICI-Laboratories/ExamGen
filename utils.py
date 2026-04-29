import streamlit as st


def enumerar_opciones(opciones_dict):
    if not isinstance(opciones_dict, dict):
        st.error(
            f"Error interno: Se esperaba un diccionario de opciones, se recibió {type(opciones_dict)}"
        )
        return {}

    standardized_options = {str(k).upper(): v for k, v in opciones_dict.items()}
    valid_keys = {"A", "B", "C", "D"}

    final_options = {
        k: standardized_options[k] for k in valid_keys if k in standardized_options
    }

    return final_options
