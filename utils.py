import hashlib
import json
import re
import streamlit as st
from datetime import datetime

def calcular_hash_completo(preguntas_json):
    return hashlib.md5(json.dumps(preguntas_json, sort_keys=True).encode('utf-8')).hexdigest()

def clean_json_response(generated_text):
    generated_text = generated_text.replace("\n", "").replace("\r", "").strip()
    generated_text = re.sub(r',\s*}', '}', generated_text)
    generated_text = re.sub(r',\s*]', ']', generated_text)
    generated_text = re.sub(r'(\d+):', '', generated_text)
    return generated_text

def enumerar_opciones(opciones):
    # Retornar las opciones tal cual están, ya que contienen las letras
    opciones_enumeradas = opciones  # Las claves ya son 'A', 'B', 'C', etc.
    return opciones_enumeradas

def verificar_respuestas(respuestas_seleccionadas, preguntas):
    incorrectas = []
    resultados = []

    for i, pregunta in enumerate(preguntas):
        seleccionada = respuestas_seleccionadas[i].strip().upper()
        correcta = pregunta["correct_answer"].strip().upper()
        if seleccionada == correcta:
            resultados.append(True)
        else:
            resultados.append(False)
            incorrectas.append(pregunta)

    return incorrectas, resultados
