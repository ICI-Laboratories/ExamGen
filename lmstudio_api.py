import requests
import json
from utils import clean_json_response
import streamlit as st

def generate_questions_with_lmstudio(text):
    prompt = (
        "Genera preguntas en el siguiente formato JSON a partir del texto proporcionado:\n\n"
        "{\n"
        "    \"questions\": [\n"
        "        {\n"
        "            \"question\": \"Aquí va la pregunta\",\n"
        "            \"options\": {\n"
        "                \"A\": \"Opción A\",\n"
        "                \"B\": \"Opción B\",\n"
        "                \"C\": \"Opción C\",\n"
        "                \"D\": \"Opción D\"\n"
        "            },\n"
        "            \"correct_answer\": \"C\"\n"
        "        }\n"
        "    ]\n"
        "}\n\n"
        f"Texto: {text}"
    )

    headers = {'Content-Type': 'application/json'}
    payload = {
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("http://localhost:1234/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code == 200:
            generated_text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return json.loads(clean_json_response(generated_text))
        else:
            st.error(f"Error en la solicitud a LM Studio: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error al intentar conectar con LM Studio: {e}")
        return None
