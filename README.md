# ExamGen

ExamGen es una aplicación web para generar preguntas de opción múltiple a partir de documentos PDF. Combina extracción de texto, OCR, generación con modelos locales mediante LM Studio y seguimiento de respuestas en PostgreSQL.

## Funcionalidades

| Módulo | Descripción |
| --- | --- |
| Generación de preguntas | Carga PDFs, extrae texto por página y genera preguntas validadas en JSON. |
| Cuestionario | Presenta lotes de preguntas, registra respuestas y conserva el progreso por usuario. |
| Estadísticas personales | Muestra desempeño por documento, pregunta más fallada y tiempo promedio de respuesta. |
| Dashboard administrativo | Consolida métricas de uso, documentos, generación, preguntas y feedback. |

## Tecnologías

| Componente | Uso |
| --- | --- |
| Python 3.11+ | Runtime de la aplicación. |
| Streamlit | Interfaz web, autenticación y manejo de sesión. |
| LM Studio API | Generación local de preguntas mediante endpoint de chat compatible. |
| PostgreSQL | Persistencia de documentos, preguntas, progreso, sesiones, intentos y feedback. |
| EasyOCR y PyMuPDF | Extracción de texto y OCR desde PDFs. |
| pandas y matplotlib | Tablas y visualizaciones del dashboard. |

## Instalación

```bash
git clone https://github.com/<usuario>/examgen.git
cd examgen

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

En macOS o Linux, activa el entorno con:

```bash
source .venv/bin/activate
```

## Configuración

1. Crea una base de datos PostgreSQL para la aplicación.
2. Copia `secrets.example.toml` como `.streamlit/secrets.toml`.
3. Ajusta las credenciales de base de datos y los correos administradores.
4. Si LM Studio usa una URL distinta, define `LMSTUDIO_URL` en el entorno o en un archivo `.env`.

Ejemplo de `.env`:

```env
LMSTUDIO_URL=http://localhost:1234/v1/chat/completions
LMSTUDIO_MAX_OUTPUT_TOKENS=2048
```

Ejecuta la aplicación con:

```bash
streamlit run app.py
```

## Uso

1. Inicia sesión en la aplicación.
2. Sube un PDF desde la página de generación.
3. Selecciona páginas y número de preguntas.
4. Genera, valida y guarda las preguntas.
5. Responde cuestionarios y consulta tus estadísticas.

## Estructura

```text
app.py                         Entrada principal de Streamlit
database.py                    Esquema, conexión y operaciones de PostgreSQL
lmstudio_api.py                Cliente para generación de preguntas
ocr.py                         Extracción de texto y OCR de PDFs
validation.py                  Esquema JSON y validación
utils.py                       Utilidades compartidas
pages/admin_dashboard.py       Dashboard administrativo
pages/generar_preguntas.py     Flujo de carga y generación
pages/realizar_cuestionario.py Flujo de cuestionarios
pages/estadisticas_usuario.py  Estadísticas personales
```

## Autores

* Yohana Yamille Ornelas Ochoa (@yohana0609)
* Kenya Alexandra Ramos Valadez (@kenini8)
* Pedro Antonio Ibarra Facio (@Peter24a)

## Licencia

Este proyecto se distribuye bajo los términos de la Licencia MIT.
