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
| Streamlit | Interfaz web y manejo server-side de sesión. |
| SARA Identity | Autoridad única mediante Authorization Code + PKCE. |
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
3. Ajusta PostgreSQL y la configuración de SARA Identity.
4. Si LM Studio usa una URL distinta, define `LMSTUDIO_URL` en el entorno o en un archivo `.env`.

La configuración mínima de autenticación es:

```toml
SARA_AUTH_PORTAL_URL = "https://identity.example.com"
SARA_IDENTITY_URL = "https://identity-api.example.com"
SARA_AUTH_CALLBACK_URL = "http://localhost:8501/"
SARA_AUTH_TRANSACTION_KEY = "CLAVE_FERNET_GENERADA"
SARA_AUTH_TRANSACTION_DB = ".data/examgen_auth_transactions.sqlite3"
```

`SARA_AUTH_CALLBACK_URL` usa `http://localhost:8501/` por defecto y debe coincidir
byte por byte con el redirect registrado para `examgen-web`. No hay callbacks
adicionales implícitos. `SARA_AUTH_PORTAL_URL` es la base del portal y ExamGen
abre `${SARA_AUTH_PORTAL_URL}/authorize`. Genera la clave local con:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

El callback canjea el código mediante `POST /oauth/token`. Después, cada sesión
se valida con `GET /auth/introspect` y la audiencia fija
`X-Resource-Audience: examgen`; ni el navegador ni la configuración pueden
cambiarla. Access y refresh tokens permanecen únicamente en el estado server-side
de Streamlit. El código se elimina de la URL antes del canje y nunca se persiste.

### Transacciones de autorización

El almacén transitorio predeterminado es SQLite en modo WAL. Conserva únicamente
`SHA-256(state)`, el verifier PKCE cifrado/autenticado con Fernet, `client_id`, el
callback exacto y los tiempos de creación, expiración y consumo. No almacena
códigos, tokens ni datos de la cuenta. El consumo usa una transacción de escritura
inmediata, por lo que sólo un callback concurrente puede ganar. El TTL y límite se
configuran con `SARA_AUTH_TRANSACTION_TTL_SECONDS` y
`SARA_AUTH_TRANSACTION_MAX_PENDING`.

SQLite sólo es válido cuando todas las instancias se ejecutan en un mismo host.
Un despliegue multi-host debe sustituirlo por Redis o Postgres compartido que
mantenga el mismo consumo atómico single-use; no debe compartir el SQLite mediante
un filesystem de red.

### Identidad, históricos y administradores

Las cuentas sin asociación legacy usan el UUID central como `usuario_id`. Para continuar un
historial anterior bajo su identificador existente, copia `legacy_identities.example.json` a
`legacy_identities.json`, configura `SARA_LEGACY_IDENTITY_MANIFEST` y agrega sólo
asociaciones revisadas UUID → identificador legacy. No existe búsqueda, fallback
ni merge automático por email, nombre o rol; los datos legacy no se eliminan.

El dashboard administrativo exige una capacidad central `examgen.admin` o
`platform.manage`. Como fallback operacional puede configurarse
`SARA_EXAMGEN_ADMIN_UUIDS` con UUID centrales explícitos. Emails, nombres y el
campo textual `role` no otorgan acceso.

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
auth_helpers.py                Integración Streamlit con SARA Identity
sara_auth.py                   PKCE, sesión, refresh y almacén single-use
database.py                    Esquema, conexión y operaciones de PostgreSQL
lmstudio_api.py                Cliente para generación de preguntas
ocr.py                         Extracción de texto y OCR de PDFs
validation.py                  Esquema JSON y validación
utils.py                       Utilidades compartidas
pages/admin_dashboard.py       Dashboard administrativo
pages/generar_preguntas.py     Flujo de carga y generación
pages/realizar_cuestionario.py Flujo de cuestionarios
pages/estadisticas_usuario.py  Estadísticas personales
legacy_identities.example.json Ejemplo explícito de continuidad histórica
```

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check sara_auth.py auth_helpers.py tests
```

## Autores

* Yohana Yamille Ornelas Ochoa (@yohana0609)
* Kenya Alexandra Ramos Valadez (@kenini8)
* Pedro Antonio Ibarra Facio (@Peter24a)

## Licencia

Este proyecto se distribuye bajo los términos de la Licencia MIT.
