# ExamGen

Generador automático de exámenes y tarjetas de estudio basado en **repetición espaciada** y **active recall**. Utiliza **Streamlit**, **OpenAI** y **PostgreSQL** para ofrecer una plataforma interactiva que convierte tus apuntes en evaluaciones personalizadas.

---

## ✨ Funcionalidades principales

| Módulo                                | Descripción                                                                                                                      |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Carga de PDF/Markdown**             | Extrae texto con OCR (EasyOCR) y PyMuPDF, normaliza y guarda en PostgreSQL.                                                      |
| **Generación de preguntas**           | Llama al modelo OpenAI (GPT‑4o) para crear preguntas de opción múltiple y tarjetas tipo *flashcard*.                             |
| **Algoritmo de repetición espaciada** | Programa la práctica según la curva de olvido de Ebbinghaus; registra desempeño por usuario.                                     |
| **Dashboard de progreso**             | Métricas clave: precisión, tiempo de respuesta, próximos repasos. Visualizado con pandas + matplotlib + Streamlit native charts. |
| **Exportación**                       | Permite descargar conjuntos de preguntas en CSV o PDF.                                                                           |

---

## ⚙️ Tecnologías

* **Python 3.11**
* **Streamlit 1.35**
* **OpenAI Python 1.30**
* **PostgreSQL 15** + SQLAlchemy
* **EasyOCR** y **PyMuPDF** para OCR/parseo
* **pandas / matplotlib / plotly** para análisis y gráficas

---

## 🚀 Instalación rápida

```bash
# 1. Clonar el repositorio
$ git clone https://github.com/<usuario>/examgen.git
$ cd examgen

# 2. Crear entorno virtual
$ python -m venv .venv
$ source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
$ pip install -r requirements.txt

# 4. Configurar variables de entorno
$ cp .env.example .env  # y edita OPENAI_API_KEY, DATABASE_URL, etc.

# 5. Crear la base de datos (PostgreSQL)
$ createdb examgen

# 6. Ejecutar la aplicación
$ streamlit run app.py
```

---

## 🖼️ Capturas de pantalla

| Inicio              | Generador           | Dashboard           |
| ------------------- | ------------------- | ------------------- |
| \_screenshot\_1.png | \_screenshot\_2.png | \_screenshot\_3.png |

*(Agrega imágenes en la carpeta `docs/` y actualiza las rutas).*

---

## 📝 Uso

1. Sube tus apuntes en PDF o Markdown.
2. Ajusta el número de preguntas y tipo de respuesta.
3. Resuelve el cuestionario generado y registra tu puntuación.
4. Revisa tu dashboard para ver progreso y próximos repasos.

> Los datos se guardan de forma local en tu propia instancia de PostgreSQL; no enviamos información sensible a terceros.

---

## 📐 Arquitectura resumida

```
┌───────────────┐        ┌───────────────┐
│   Streamlit   │  API   │   OpenAI GPT  │
└───────┬───────┘        └───────┬───────┘
        │                        │
        │ SQLAlchemy             │
        ▼                        ▼
  ┌────────────┐          ┌────────────┐
  │ PostgreSQL │◀────────▶│   modelos  │
  └────────────┘          └────────────┘
```

---

## 🤝 Contribuciones

¡Toda ayuda es bienvenida! Si deseas contribuir:

1. Crea un *fork* del repositorio.
2. Crea una rama con tu nueva funcionalidad (`git checkout -b feature/mi-funcion`).
3. Envía un *pull request* describiendo tus cambios.


---

## 👥 Autores

* **Yohana Yamille Ornelas Ochoa** (@yohana0609)
* **Kenya Alexandra Ramos Valadez** (@kenini8)
* **Pedro Antonio Ibarra Facio** (@Peter24a)

---

## 📄 Licencia

Este proyecto se distribuye bajo los términos de la **Licencia MIT**.

---
