# --- START OF FILE database.py ---
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import streamlit as st
import logging
from datetime import datetime, timedelta
import hashlib # For hashing page content and document hash

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

DB_SCHEMA_SQL = [
    # Tabla: documentos
    """
    CREATE TABLE IF NOT EXISTS documentos (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(255),
        hash VARCHAR(64) UNIQUE, -- Hash of the document file or identifying content
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        curso_tag VARCHAR(100),
        grado_tag VARCHAR(100),
        num_pages_pdf INTEGER,
        pdf_size_bytes BIGINT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_docs_hash ON documentos(hash);",
    "CREATE INDEX IF NOT EXISTS idx_docs_nombre ON documentos(nombre);",

    # Tabla: page_content (stores raw text per page)
    """
    CREATE TABLE IF NOT EXISTS page_content (
        id SERIAL PRIMARY KEY,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        page_number INTEGER NOT NULL,
        text_content TEXT,
        text_hash VARCHAR(64), -- Hash of the page's text_content to detect changes
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE (documento_id, page_number)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_page_content_doc_page ON page_content(documento_id, page_number);",

    # Tabla: preguntas
    """
    CREATE TABLE IF NOT EXISTS preguntas (
        id SERIAL PRIMARY KEY,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        question TEXT,
        options JSONB,
        correct_answer VARCHAR(1),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE (documento_id, question)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_preguntas_doc_id ON preguntas(documento_id);",

    # Tabla: progreso_usuario
    """
    CREATE TABLE IF NOT EXISTS progreso_usuario (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255) NOT NULL,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        pregunta_id INT REFERENCES preguntas(id) ON DELETE CASCADE,
        UNIQUE (usuario_id, documento_id, pregunta_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_progreso_user_doc_q ON progreso_usuario(usuario_id, documento_id, pregunta_id);",

    # Tabla: quiz_attempts
    """
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        end_time TIMESTAMP WITH TIME ZONE,
        completed BOOLEAN DEFAULT FALSE,
        batch_size_configured INTEGER,
        questions_presented_in_batch INTEGER,
        questions_answered_in_batch INTEGER,
        correct_in_batch INTEGER,
        incorrect_in_batch INTEGER,
        initial_progress_percentage FLOAT,
        final_progress_percentage FLOAT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_doc ON quiz_attempts(user_id, documento_id);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_start_time ON quiz_attempts(start_time DESC);",

    # Tabla: estadisticas_respuestas
    """
    CREATE TABLE IF NOT EXISTS estadisticas_respuestas (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255) NOT NULL,
        pregunta_id INT REFERENCES preguntas(id) ON DELETE CASCADE,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        quiz_attempt_id INT REFERENCES quiz_attempts(id) ON DELETE SET NULL,
        tiempo_respuesta_seconds FLOAT,
        es_correcta BOOLEAN,
        respuesta_seleccionada VARCHAR(10),
        recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_stats_user_doc_q ON estadisticas_respuestas(usuario_id, documento_id, pregunta_id);",
    "CREATE INDEX IF NOT EXISTS idx_stats_pregunta_id ON estadisticas_respuestas(pregunta_id);",
    "CREATE INDEX IF NOT EXISTS idx_stats_recorded_at ON estadisticas_respuestas(recorded_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_stats_quiz_attempt_id ON estadisticas_respuestas(quiz_attempt_id);",

    # Tabla: generation_logs
    """
    CREATE TABLE IF NOT EXISTS generation_logs (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255),
        filename VARCHAR(255),
        upload_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        ocr_success BOOLEAN,
        llm_success BOOLEAN,
        model_used VARCHAR(255),
        num_questions_generated INT,
        document_id INT REFERENCES documentos(id) ON DELETE SET NULL,
        error_message TEXT,
        processing_time_seconds FLOAT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_gen_logs_time ON generation_logs(upload_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_gen_logs_user_id ON generation_logs(usuario_id);",

    # Tabla: sesiones_usuario
    """
    CREATE TABLE IF NOT EXISTS sesiones_usuario (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255) NOT NULL,
        login_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        logout_time TIMESTAMP WITH TIME ZONE,
        duration_seconds INTEGER,
        last_activity_time TIMESTAMP WITH TIME ZONE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sesiones_usuario_id_login ON sesiones_usuario(usuario_id, login_time DESC);",

    # Tabla: feedback_usuario
    """
    CREATE TABLE IF NOT EXISTS feedback_usuario (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255) NOT NULL,
        documento_id INT REFERENCES documentos(id) ON DELETE SET NULL,
        quiz_attempt_id INT REFERENCES quiz_attempts(id) ON DELETE SET NULL,
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        feedback_type VARCHAR(50),
        submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_feedback_usuario_id ON feedback_usuario(usuario_id);",
    "CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_usuario(feedback_type);"
]


def create_tables_if_not_exist(conn):
    try:
        with conn.cursor() as cur:
            for command in DB_SCHEMA_SQL:
                cur.execute(command)
        conn.commit()
        logger.info("Esquema de base de datos verificado/creado exitosamente.")
    except Exception as e:
        logger.error(f"Error creando/verificando tablas de base de datos: {e}", exc_info=True)
        conn.rollback()
        raise


@st.cache_resource
def init_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            host=st.secrets["DB_HOST"],
            port=st.secrets["DB_PORT"]
        )
        conn.autocommit = False
        logger.info("Conexión a base de datos establecida.")
        create_tables_if_not_exist(conn)
        return conn
    except KeyError as ke:
        logger.error(f"Error de configuración: Falta la clave '{ke}' en st.secrets (secrets.toml).")
        st.error(f"Error de configuración: Falta la clave '{ke}' en los secretos de la aplicación.")
        st.stop()
    except Exception as e:
        logger.error(f"Error conectando a PostgreSQL o inicializando tablas: {e}", exc_info=True)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        st.error(f"Error Crítico: No se pudo conectar o inicializar la base de datos. Revise los logs. {e}")
        st.stop()


def get_db_connection():
    conn = init_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as oe:
        logger.warning(f"Conexión a BD cacheada está inactiva ({oe}). Limpiando caché y reintentando.")
        st.cache_resource.clear()
        conn = init_connection()
    except psycopg2.InternalError as ie:
        if "transaction is aborted" in str(ie).lower():
            logger.warning(f"Conexión a BD cacheada encontrada en estado de transacción abortada: {ie}. Realizando rollback.")
            try:
                conn.rollback()
            except Exception as rb_err:
                logger.error(f"Error durante el rollback de la transacción abortada: {rb_err}", exc_info=True)
                st.cache_resource.clear()
                conn = init_connection()
        else:
            logger.error(f"Error interno en la conexión a BD cacheada: {ie}. Re-lanzando.", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"Error inesperado verificando conexión a BD cacheada: {e}. Re-lanzando.", exc_info=True)
        raise
    return conn

# --- Funciones CRUD para 'documentos' ---
def insertar_documento(conn, nombre_documento: str, hash_documento: str,
                       num_pages: int = None, pdf_size: int = None,
                       curso_tag: str = None, grado_tag: str = None):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, num_pages_pdf FROM documentos WHERE hash = %s", (hash_documento,))
            result = cur.fetchone()
            if not result:
                cur.execute(
                    """
                    INSERT INTO documentos (nombre, hash, num_pages_pdf, pdf_size_bytes, curso_tag, grado_tag)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (nombre_documento, hash_documento, num_pages, pdf_size, curso_tag, grado_tag)
                )
                documento_id = cur.fetchone()['id']
                conn.commit()
                logger.info(f"Nuevo documento '{nombre_documento}' insertado con ID: {documento_id}, Pages: {num_pages}")
                return documento_id, True
            else:
                documento_id = result['id']
                existing_num_pages = result['num_pages_pdf']
                updated = False
                if num_pages is not None and existing_num_pages is None:
                    cur.execute("UPDATE documentos SET num_pages_pdf = %s WHERE id = %s", (num_pages, documento_id))
                    conn.commit()
                    logger.info(f"Documento ID {documento_id} actualizado con num_pages_pdf: {num_pages}")
                    updated = True
                if not updated:
                    logger.info(f"Documento '{nombre_documento}' (hash: {hash_documento[:8]}...) ya existe con ID: {documento_id}. Pages: {existing_num_pages or num_pages}")
                return documento_id, False
    except Exception as e:
        logger.error(f"Error en insertar_documento para hash {hash_documento}: {e}", exc_info=True)
        conn.rollback()
        raise

def obtener_documentos_cargados(conn):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (nombre) id, nombre, hash, created_at, curso_tag, grado_tag, num_pages_pdf
                FROM documentos
                ORDER BY nombre, created_at DESC
            """)
            documentos = cur.fetchall()
        return list(documentos)
    except Exception as e:
        logger.error(f"Error en obtener_documentos_cargados: {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

# --- Funciones CRUD para 'page_content' ---
def insert_page_contents(conn, documento_id: int, pages_data: list):
    if not pages_data:
        return 0
    inserted_count = 0
    updated_count = 0
    try:
        with conn.cursor() as cur:
            for page in pages_data:
                page_num = page['page_number']
                text_content = page['text']
                text_h = hashlib.sha256(text_content.encode('utf-8')).hexdigest() if text_content else None

                cur.execute(
                    "SELECT id, text_hash FROM page_content WHERE documento_id = %s AND page_number = %s",
                    (documento_id, page_num)
                )
                existing_page_row = cur.fetchone() # Renamed to avoid conflict

                if not existing_page_row:
                    cur.execute(
                        """
                        INSERT INTO page_content (documento_id, page_number, text_content, text_hash)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (documento_id, page_num, text_content, text_h)
                    )
                    inserted_count += 1
                elif existing_page_row[1] != text_h: # existing_page_row[1] is text_hash
                    cur.execute(
                        """
                        UPDATE page_content SET text_content = %s, text_hash = %s, created_at = NOW()
                        WHERE id = %s
                        """,
                        (text_content, text_h, existing_page_row[0]) # existing_page_row[0] is id
                    )
                    updated_count += 1
        conn.commit()
        logger.info(f"Page contents for doc ID {documento_id}: {inserted_count} inserted, {updated_count} updated.")
        return inserted_count + updated_count
    except Exception as e:
        logger.error(f"Error en insert_page_contents para doc ID {documento_id}: {e}", exc_info=True)
        conn.rollback()
        raise

def get_page_contents_for_document(conn, documento_id: int, page_numbers: list = None):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT page_number, text_content FROM page_content WHERE documento_id = %s"
            params = [documento_id]
            if page_numbers:
                if not all(isinstance(pn, int) for pn in page_numbers):
                    raise ValueError("page_numbers must be a list of integers.")
                query += " AND page_number = ANY(%s)"
                params.append(page_numbers)
            query += " ORDER BY page_number ASC"
            cur.execute(query, tuple(params))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error en get_page_contents_for_document (doc ID {documento_id}): {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

# --- Funciones CRUD para 'preguntas' ---
def insertar_preguntas_json(conn, preguntas_json: dict, documento_id: int):
    """Inserta preguntas desde un JSON, evitando duplicados para el mismo documento."""
    preguntas_para_insertar = []
    if not preguntas_json or 'questions' not in preguntas_json or not isinstance(preguntas_json['questions'], list):
        logger.warning(f"Formato de preguntas JSON inválido o vacío para documento ID {documento_id}.")
        return 0

    for pregunta_data in preguntas_json["questions"]:
        if not all(k in pregunta_data for k in ("question", "options", "correct_answer")):
            logger.warning(f"Saltando pregunta malformada en documento {documento_id}: {pregunta_data}")
            continue
        options_dict = pregunta_data.get("options", {})
        if not isinstance(options_dict, dict) or not all(k in options_dict for k in ("A", "B", "C", "D")): # Basic check
            logger.warning(f"Saltando pregunta con estructura de opciones inválida en documento {documento_id}: {pregunta_data}")
            continue
        preguntas_para_insertar.append((
            documento_id,
            pregunta_data["question"],
            json.dumps(options_dict),
            pregunta_data["correct_answer"].upper()
        ))

    if not preguntas_para_insertar:
        return 0

    num_inserted = 0
    try:
        with conn.cursor() as cur:
            insert_query = """
            INSERT INTO preguntas (documento_id, question, options, correct_answer)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (documento_id, question) DO NOTHING;
            """
            # executemany is more efficient for multiple inserts
            cur.executemany(insert_query, preguntas_para_insertar)
            num_inserted = cur.rowcount # Number of rows affected by the last command
        conn.commit()
        if num_inserted > 0:
            logger.info(f"{num_inserted} preguntas nuevas insertadas/actualizadas para documento ID {documento_id}.")
        else:
            logger.info(f"No se insertaron preguntas nuevas para documento ID {documento_id} (posiblemente ya existían).")
    except Exception as e:
        logger.error(f"Error durante inserción masiva en insertar_preguntas_json para doc {documento_id}: {e}", exc_info=True)
        conn.rollback()
        raise
    return num_inserted

def obtener_preguntas_por_documento(conn, documento_id: int):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM preguntas WHERE documento_id = %s ORDER BY id", (documento_id,))
            preguntas = cur.fetchall()
        return preguntas
    except Exception as e:
        logger.error(f"Error en obtener_preguntas_por_documento (ID: {documento_id}): {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

# --- Funciones para 'progreso_usuario' ---
def registrar_progreso(conn, usuario_id: str, documento_id: int, preguntas_resueltas_ids: list):
    if not preguntas_resueltas_ids:
        return 0
    num_inserted = 0
    try:
        with conn.cursor() as cur:
            progreso_data = [(usuario_id, documento_id, pregunta_id) for pregunta_id in preguntas_resueltas_ids]
            insert_query = """
            INSERT INTO progreso_usuario (usuario_id, documento_id, pregunta_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario_id, documento_id, pregunta_id) DO NOTHING;
            """
            cur.executemany(insert_query, progreso_data)
            num_inserted = cur.rowcount
        conn.commit()
        if num_inserted > 0:
             logger.info(f"{num_inserted} progresos registrados para usuario '{usuario_id}', doc ID {documento_id}.")
    except Exception as e:
        logger.error(f"Error en registrar_progreso para usuario '{usuario_id}', doc {documento_id}: {e}", exc_info=True)
        conn.rollback()
        raise
    return num_inserted

def reiniciar_progreso(conn, usuario_id: str, documento_id: int):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM progreso_usuario
                WHERE usuario_id = %s AND documento_id = %s
            """, (usuario_id, documento_id))
            rows_deleted = cur.rowcount
        conn.commit()
        logger.info(f"Progreso reiniciado para usuario '{usuario_id}', doc ID {documento_id}. Registros eliminados: {rows_deleted}.")
    except Exception as e:
        logger.error(f"Error en reiniciar_progreso para usuario '{usuario_id}', doc {documento_id}: {e}", exc_info=True)
        conn.rollback()
        raise

def obtener_ids_preguntas_respondidas_correctamente(conn, usuario_id: str, documento_id: int):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pregunta_id FROM progreso_usuario
                WHERE usuario_id = %s AND documento_id = %s
            """, (usuario_id, documento_id))
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error obteniendo IDs respondidos para usuario '{usuario_id}', doc {documento_id}: {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

# --- Funciones para Cuestionarios y Respuestas ---
def obtener_preguntas_aleatorias_para_cuestionario(conn, documento_id: int, usuario_id: str, num_preguntas: int = 5):
    ids_ya_respondidas_correctamente = obtener_ids_preguntas_respondidas_correctamente(conn, usuario_id, documento_id)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query_params = [documento_id]
            not_in_clause = ""
            if ids_ya_respondidas_correctamente:
                not_in_clause = "AND id NOT IN %s"
                query_params.append(tuple(ids_ya_respondidas_correctamente))

            query_params.append(num_preguntas)

            query = f"""
                SELECT * FROM preguntas
                WHERE documento_id = %s {not_in_clause}
                ORDER BY RANDOM()
                LIMIT %s;
            """
            cur.execute(query, tuple(query_params)) # Ensure query_params is a tuple
            preguntas_no_respondidas = cur.fetchall()
        return preguntas_no_respondidas
    except Exception as e:
        logger.error(f"Error en obtener_preguntas_aleatorias (doc {documento_id}, user '{usuario_id}'): {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise


def registrar_respuesta_estadistica(conn, usuario_id: str, pregunta_id: int, documento_id: int,
                                   quiz_attempt_id: int, tiempo_delta: timedelta,
                                   es_correcta: bool, respuesta_seleccionada: str):
    tiempo_segundos = tiempo_delta.total_seconds()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO estadisticas_respuestas
                    (usuario_id, pregunta_id, documento_id, quiz_attempt_id, tiempo_respuesta_seconds, es_correcta, respuesta_seleccionada, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (usuario_id, pregunta_id, documento_id, quiz_attempt_id, tiempo_segundos, es_correcta, respuesta_seleccionada))
        conn.commit()
    except Exception as e:
        logger.error(f"Error en registrar_respuesta_estadistica para user '{usuario_id}', q_id {pregunta_id}: {e}", exc_info=True)
        conn.rollback()
        raise

# --- Funciones para 'generation_logs' ---
def log_generation_attempt(conn, usuario_id: str, filename: str, ocr_success: bool, llm_success: bool,
                           model_used: str, num_questions: int, doc_id: int = None,
                           error: str = None, duration_seconds: float = None):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO generation_logs
                (usuario_id, filename, ocr_success, llm_success, model_used, num_questions_generated, document_id, error_message, processing_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (usuario_id, filename, ocr_success, llm_success, model_used, num_questions, doc_id, error, duration_seconds))
        conn.commit()
    except Exception as e:
        logger.error(f"Fallo al registrar intento de generación para archivo '{filename}': {e}", exc_info=True)
        conn.rollback()

def get_generation_logs(conn, limit: int = 50):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM generation_logs ORDER BY upload_time DESC LIMIT %s", (limit,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error obteniendo logs de generación: {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

# --- Funciones para 'quiz_attempts' ---
def crear_quiz_attempt(conn, user_id: str, documento_id: int, batch_size_configured: int, initial_progress_percentage: float):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quiz_attempts (user_id, documento_id, batch_size_configured, initial_progress_percentage, start_time)
                VALUES (%s, %s, %s, %s, NOW()) RETURNING id
                """,
                (user_id, documento_id, batch_size_configured, initial_progress_percentage)
            )
            attempt_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"Nuevo quiz_attempt creado ID: {attempt_id} para user '{user_id}', doc {documento_id}.")
            return attempt_id
    except Exception as e:
        logger.error(f"Error creando quiz_attempt para user '{user_id}', doc {documento_id}: {e}", exc_info=True)
        conn.rollback()
        raise

def actualizar_quiz_attempt_final(conn, attempt_id: int, questions_presented: int, questions_answered: int,
                                 correct_in_batch: int, incorrect_in_batch: int, final_progress_percentage: float):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE quiz_attempts
                SET end_time = NOW(), completed = TRUE,
                    questions_presented_in_batch = %s,
                    questions_answered_in_batch = %s,
                    correct_in_batch = %s,
                    incorrect_in_batch = %s,
                    final_progress_percentage = %s
                WHERE id = %s
                """,
                (questions_presented, questions_answered, correct_in_batch, incorrect_in_batch, final_progress_percentage, attempt_id)
            )
            conn.commit()
            logger.info(f"Quiz_attempt ID: {attempt_id} finalizado y actualizado.")
    except Exception as e:
        logger.error(f"Error actualizando quiz_attempt ID {attempt_id}: {e}", exc_info=True)
        conn.rollback()
        raise

# --- Funciones para 'sesiones_usuario' ---
def registrar_inicio_sesion_db(conn, usuario_id: str):
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sesiones_usuario (usuario_id, login_time, last_activity_time) VALUES (%s, NOW(), NOW()) RETURNING id",
                (usuario_id,)
            )
            session_db_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"Inicio de sesión registrado en BD para {usuario_id}, session_db_id: {session_db_id}")
            return session_db_id
    except Exception as e:
        logger.error(f"Error al registrar inicio de sesión en BD para {usuario_id}: {e}", exc_info=True)
        conn.rollback()
        raise

def registrar_fin_sesion_db(conn, session_db_id: int):
    if not session_db_id:
        logger.warning("Intento de registrar fin de sesión sin session_db_id.")
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT login_time FROM sesiones_usuario WHERE id = %s", (session_db_id,))
            result = cur.fetchone()
            if result:
                login_time_db = result[0]
                # Use timezone-aware now, psycopg2 can handle it
                logout_time_db = datetime.now(psycopg2.tz.FixedOffsetTimezone(offset=0, name=None)) # UTC
                duration = logout_time_db - login_time_db
                duration_seconds = int(duration.total_seconds())

                cur.execute(
                    "UPDATE sesiones_usuario SET logout_time = %s, duration_seconds = %s WHERE id = %s",
                    (logout_time_db, duration_seconds, session_db_id)
                )
                conn.commit()
                logger.info(f"Fin de sesión registrado en BD para session_db_id: {session_db_id}, Duración: {duration_seconds}s")
            else:
                logger.warning(f"No se encontró la sesión con id {session_db_id} para registrar logout.")
    except Exception as e:
        logger.error(f"Error al registrar fin de sesión en BD para session_db_id {session_db_id}: {e}", exc_info=True)
        conn.rollback()


def actualizar_actividad_sesion_db(conn, session_db_id: int):
    if not session_db_id:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sesiones_usuario SET last_activity_time = NOW() WHERE id = %s",
                (session_db_id,)
            )
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando actividad para sesión DB ID {session_db_id}: {e}", exc_info=True)
        conn.rollback() # Rollback on warning if it's a DB modification attempt

# --- Funciones para 'feedback_usuario' ---
def registrar_feedback(conn, usuario_id: str, documento_id: int = None, quiz_attempt_id: int = None,
                       rating: int = None, comment: str = None, feedback_type: str = "general"):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback_usuario
                (usuario_id, documento_id, quiz_attempt_id, rating, comment, feedback_type, submitted_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (usuario_id, documento_id, quiz_attempt_id, rating, comment, feedback_type)
            )
            conn.commit()
            logger.info(f"Feedback registrado para usuario '{usuario_id}', tipo: {feedback_type}.")
    except Exception as e:
        logger.error(f"Error registrando feedback para usuario '{usuario_id}': {e}", exc_info=True)
        conn.rollback()
        raise

# --- Funciones de Estadísticas Agregadas (ejemplos, adaptar de tu archivo estadisticas.py) ---
def get_overall_document_stats(conn):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    d.id, d.nombre, d.hash, d.created_at, d.curso_tag, d.grado_tag, d.num_pages_pdf,
                    COUNT(DISTINCT p.id) as total_questions,
                    COALESCE(SUM(qa.correct_in_batch), 0) as total_correct_answers_all_users,
                    COALESCE(SUM(qa.incorrect_in_batch), 0) as total_incorrect_answers_all_users,
                    COUNT(DISTINCT qa.user_id) as unique_users_attempted,
                    AVG(qa.final_progress_percentage - qa.initial_progress_percentage) as avg_progress_gain_per_batch
                FROM documentos d
                LEFT JOIN preguntas p ON d.id = p.documento_id
                LEFT JOIN quiz_attempts qa ON d.id = qa.documento_id AND qa.completed = TRUE
                GROUP BY d.id, d.nombre, d.hash, d.created_at, d.curso_tag, d.grado_tag, d.num_pages_pdf
                ORDER BY d.created_at DESC;
            """)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error en get_overall_document_stats: {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
        raise

def get_user_activity_summary(conn):
    summary = {}
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(DISTINCT usuario_id) as active_users_sessions FROM sesiones_usuario WHERE logout_time IS NOT NULL OR last_activity_time > NOW() - INTERVAL '1 hour';") # More robust active user
            res = cur.fetchone()
            summary['active_users_sessions'] = res['active_users_sessions'] if res else 0

            cur.execute("SELECT COUNT(*) as total_answers_recorded FROM estadisticas_respuestas;")
            res = cur.fetchone()
            summary['total_answers_recorded'] = res['total_answers_recorded'] if res else 0

            cur.execute("SELECT COUNT(DISTINCT id) as docs_with_questions FROM documentos WHERE id IN (SELECT DISTINCT documento_id FROM preguntas);")
            res = cur.fetchone()
            summary['documents_with_questions'] = res['docs_with_questions'] if res else 0

            cur.execute("SELECT AVG(duration_seconds) as avg_session_duration_seconds FROM sesiones_usuario WHERE duration_seconds IS NOT NULL AND duration_seconds > 0;") # Exclude 0 duration
            res = cur.fetchone()
            summary['avg_session_duration_seconds'] = res['avg_session_duration_seconds'] if res and res['avg_session_duration_seconds'] is not None else 0

            return summary
    except Exception as e:
        logger.error(f"Error en get_user_activity_summary: {e}", exc_info=True)
        if "transaction is aborted" in str(e).lower(): conn.rollback()
    return summary 