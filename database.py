import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
from dotenv import load_dotenv
import streamlit as st
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS documentos (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(255),
        hash VARCHAR(32) UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
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
    """
    CREATE TABLE IF NOT EXISTS progreso_usuario (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255),
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        pregunta_id INT REFERENCES preguntas(id) ON DELETE CASCADE,
        UNIQUE (usuario_id, documento_id, pregunta_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS estadisticas_respuestas (
        id SERIAL PRIMARY KEY,
        usuario_id VARCHAR(255),
        pregunta_id INT REFERENCES preguntas(id) ON DELETE CASCADE,
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        tiempo_respuesta_seconds FLOAT,
        es_correcta BOOLEAN,
        recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        -- Se elimina la restricción UNIQUE (usuario_id, pregunta_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS generation_logs (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(255),
        upload_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        ocr_success BOOLEAN,
        llm_success BOOLEAN,
        num_questions_generated INT,
        document_id INT REFERENCES documentos(id) ON DELETE SET NULL,
        error_message TEXT,
        processing_time_seconds FLOAT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255),
        documento_id INT REFERENCES documentos(id) ON DELETE CASCADE,
        start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        end_time TIMESTAMP WITH TIME ZONE,
        score INT,
        total_questions_in_quiz INT,
        completed BOOLEAN DEFAULT FALSE
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_docs_hash ON documentos(hash);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_preguntas_doc_id ON preguntas(documento_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_progreso_user_doc ON progreso_usuario(usuario_id, documento_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_stats_user_doc_q ON estadisticas_respuestas(usuario_id, documento_id, pregunta_id);
    """,
     """
    CREATE INDEX IF NOT EXISTS idx_stats_pregunta ON estadisticas_respuestas(pregunta_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_gen_logs_time ON generation_logs(upload_time DESC);
    """
]

def create_tables_if_not_exist(conn):
    try:
        # Use a separate cursor for table creation to avoid interfering with ongoing transactions if possible
        # Although with cache_resource, it might still be the same session context
        with conn.cursor() as cur:
            for command in CREATE_TABLES_SQL:
                cur.execute(command)
        conn.commit() # Commit creation separately
        logging.info("Database tables verified/created successfully.")
    except Exception as e:
        logging.error(f"Error creating/verifying database tables: {e}")
        conn.rollback() # Explicit rollback on creation error
        raise

@st.cache_resource
def init_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        conn.autocommit = False # Ensure transactions are managed explicitly or by 'with' context
        logging.info("Database connection established.")
        create_tables_if_not_exist(conn)
        return conn
    except Exception as e:
        logging.error(f"Error connecting to PostgreSQL or initializing tables: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                 pass # Ignore errors during close if already problematic
        st.error(f"Fatal Error: No se pudo conectar o inicializar la base de datos: {e}")
        st.stop()

def get_db_connection():
    conn = init_connection()
    # Optional: Check connection status before returning
    try:
        # Simple query to check if connection is alive and not in aborted state
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
    except psycopg2.OperationalError as oe:
        logging.error(f"Cached DB connection is dead: {oe}. Clearing cache and retrying.")
        st.cache_resource.clear() # Clear the cache
        conn = init_connection() # Attempt to reconnect
    except psycopg2.InternalError as ie:
         # Check specifically for aborted transaction state on reuse
        if "current transaction is aborted" in str(ie):
            logging.warning(f"Cached DB connection found in aborted state: {ie}. Rolling back and returning.")
            conn.rollback() # Attempt explicit rollback to clear state
        else:
            logging.error(f"Internal error on cached connection: {ie}. Re-raising.")
            raise # Re-raise other internal errors
    except Exception as e:
        logging.error(f"Unexpected error checking cached DB connection: {e}. Re-raising.")
        raise # Re-raise other unexpected errors

    return conn


def insertar_documento(conn, nombre_documento, hash_documento):
    # This function is less likely to cause aborts due to ON CONFLICT handling
    # but we add rollback just in case of other unexpected errors.
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documentos WHERE hash = %s", (hash_documento,))
            result = cur.fetchone()
            if not result:
                cur.execute(
                    "INSERT INTO documentos (nombre, hash) VALUES (%s, %s) RETURNING id",
                    (nombre_documento, hash_documento)
                )
                documento_id = cur.fetchone()[0]
                conn.commit()
                return documento_id, True
            else:
                # No changes, no commit/rollback needed unless the SELECT failed
                return result[0], False
    except Exception as e:
        logging.error(f"Error in insertar_documento for hash {hash_documento}: {e}")
        conn.rollback() # Explicit rollback on any error
        raise # Re-raise the error

def insertar_preguntas_json(conn, preguntas_json, documento_id):
    preguntas = []
    if not preguntas_json or 'questions' not in preguntas_json or not preguntas_json['questions']:
        return 0

    for pregunta in preguntas_json["questions"]:
        if not all(k in pregunta for k in ("question", "options", "correct_answer")):
            logging.warning(f"Skipping malformed question item in document {documento_id}: {pregunta}")
            continue
        # Validate options structure before dumping
        options_dict = pregunta.get("options", {})
        if not isinstance(options_dict, dict) or not all(k in options_dict for k in ("A", "B", "C", "D")):
             logging.warning(f"Skipping question with invalid options structure in document {documento_id}: {pregunta}")
             continue
        preguntas.append((
            documento_id,
            pregunta["question"],
            json.dumps(options_dict), # Ensure options is a dict before dumping
            pregunta["correct_answer"]
        ))

    if not preguntas:
        return 0

    num_inserted = 0
    try:
        with conn.cursor() as cur:
            insert_query = """
            INSERT INTO preguntas (documento_id, question, options, correct_answer)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (documento_id, question) DO NOTHING
            """
            cur.executemany(insert_query, preguntas)
            num_inserted = cur.rowcount
        conn.commit() # Commit only if executemany succeeded
    except Exception as e:
        logging.error(f"Error during bulk insert in insertar_preguntas_json for doc {documento_id}: {e}")
        conn.rollback() # Explicit rollback on insert error
        raise

    return num_inserted

def obtener_documentos_cargados(conn):
    # SELECT operations generally don't cause transaction aborts unless syntax is wrong
    # or connection is already broken
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (nombre) id, nombre, hash, created_at
                FROM documentos
                ORDER BY nombre, created_at DESC
            """)
            documentos = cur.fetchall()
        return list(documentos)
    except psycopg2.Error as db_err:
         # Handle potential issues if the connection was already aborted before this SELECT
         logging.error(f"Database error in obtener_documentos_cargados: {db_err}")
         # Attempting rollback might be needed if error indicates aborted state
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in obtener_documentos_cargados: {rb_err}")
         raise # Re-raise the original error after attempting rollback
    except Exception as e:
         logging.error(f"Unexpected error in obtener_documentos_cargados: {e}")
         raise


def obtener_preguntas_por_documento(conn, documento_id):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM preguntas WHERE documento_id = %s ORDER BY id", (documento_id,))
            preguntas = cur.fetchall()
        return preguntas
    except psycopg2.Error as db_err:
         logging.error(f"Database error in obtener_preguntas_por_documento: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in obtener_preguntas_por_documento: {rb_err}")
         raise
    except Exception as e:
         logging.error(f"Unexpected error in obtener_preguntas_por_documento: {e}")
         raise


def obtener_preguntas_aleatorias(conn, documento_id, usuario_id, num_preguntas=5):
    # SELECT only, less likely to cause issues unless connection broken
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT pregunta_id FROM progreso_usuario
                WHERE usuario_id = %s AND documento_id = %s
            """, (usuario_id, documento_id))
            ids_respondidos = [row['pregunta_id'] for row in cur.fetchall()]

            query_params = [documento_id]
            not_in_clause = ""
            ids_tuple = tuple(ids_respondidos) # Create tuple regardless of length for consistency

            # Handle empty tuple for NOT IN - query needs adjustment or skip clause
            if ids_respondidos:
                not_in_clause = "AND id NOT IN %s"
                query_params.append(ids_tuple)
            # Else: not_in_clause remains empty, ids_tuple is not appended

            query_params.append(num_preguntas)

            query = f"""
                SELECT * FROM preguntas
                WHERE documento_id = %s {not_in_clause}
                ORDER BY RANDOM()
                LIMIT %s
            """

            cur.execute(query, tuple(query_params))
            preguntas_no_respondidas = cur.fetchall()
        return preguntas_no_respondidas
    except psycopg2.Error as db_err:
         logging.error(f"Database error in obtener_preguntas_aleatorias: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in obtener_preguntas_aleatorias: {rb_err}")
         raise
    except Exception as e:
         logging.error(f"Unexpected error in obtener_preguntas_aleatorias: {e}")
         raise

def reiniciar_progreso(conn, usuario_id, documento_id):
    """
    Reinicia el progreso del cuestionario para un usuario y documento específicos,
    permitiendo que las preguntas ya contestadas correctamente vuelvan a aparecer.
    NO BORRA las estadísticas históricas de respuestas.
    """
    try:
        with conn.cursor() as cur:
            # Eliminar SOLO del tracker de progreso actual
            cur.execute("""
                DELETE FROM progreso_usuario
                WHERE usuario_id = %s AND documento_id = %s
            """, (usuario_id, documento_id))
            rows_deleted_progress = cur.rowcount

            # --- NO BORRAR DE estadisticas_respuestas ---
            # cur.execute("""
            #     DELETE FROM estadisticas_respuestas
            #     WHERE usuario_id = %s AND documento_id = %s
            # """, (usuario_id, documento_id))
            # rows_deleted_stats = cur.rowcount
            # ------------------------------------------

        conn.commit() # Commit después de eliminar de progreso_usuario
        # Actualizar mensaje de log
        logging.info(f"Reiniciado seguimiento de progreso para user '{usuario_id}', doc '{documento_id}'. Eliminado: {rows_deleted_progress} registros de progreso.")

    except Exception as e:
        logging.error(f"Error in reiniciar_progreso for user {usuario_id}, doc {documento_id}: {e}")
        conn.rollback() # Rollback si falla la eliminación de progreso
        raise



def registrar_progreso(conn, usuario_id, documento_id, preguntas_resueltas_ids):
    if not preguntas_resueltas_ids:
        return 0
    num_inserted = 0
    try:
        with conn.cursor() as cur:
            progreso = [(usuario_id, documento_id, pregunta_id) for pregunta_id in preguntas_resueltas_ids]
            insert_query = """
            INSERT INTO progreso_usuario (usuario_id, documento_id, pregunta_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario_id, documento_id, pregunta_id) DO NOTHING
            """
            cur.executemany(insert_query, progreso)
            num_inserted = cur.rowcount
        conn.commit()
    except Exception as e:
        logging.error(f"Error in registrar_progreso for user {usuario_id}, doc {documento_id}: {e}")
        conn.rollback()
        raise
    return num_inserted


def registrar_respuesta(conn, usuario_id, pregunta_id, documento_id, tiempo_respuesta_delta, es_correcta):
    """Registra CADA intento de respuesta como una nueva fila."""
    tiempo_respuesta_seconds = tiempo_respuesta_delta.total_seconds()
    try:
        with conn.cursor() as cur:
            # INSERT simple - cada intento es una nueva fila
            cur.execute("""
                INSERT INTO estadisticas_respuestas
                    (usuario_id, pregunta_id, documento_id, tiempo_respuesta_seconds, es_correcta, recorded_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (usuario_id, pregunta_id, documento_id, tiempo_respuesta_seconds, es_correcta))
            # Se elimina la cláusula ON CONFLICT DO UPDATE
        conn.commit()
    except Exception as e:
        logging.error(f"Error in registrar_respuesta (inserting new attempt) for user {usuario_id}, q {pregunta_id}: {e}")
        conn.rollback()
        raise


def log_generation_attempt(conn, filename, ocr_success, llm_success, num_questions, doc_id, error=None, duration=None):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO generation_logs
                (filename, ocr_success, llm_success, num_questions_generated, document_id, error_message, processing_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (filename, ocr_success, llm_success, num_questions, doc_id, error, duration))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to log generation attempt for file '{filename}': {e}")
        conn.rollback() # Rollback on logging failure too

def get_generation_logs(conn, limit=50):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM generation_logs
                ORDER BY upload_time DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except psycopg2.Error as db_err:
         logging.error(f"Database error in get_generation_logs: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in get_generation_logs: {rb_err}")
         raise
    except Exception as e:
        st.error(f"Error fetching generation logs: {e}") # Keep st.error for user feedback here
        raise


def get_overall_document_stats(conn):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.nombre, d.hash, d.created_at, COUNT(p.id) as total_questions
                FROM documentos d
                LEFT JOIN preguntas p ON d.id = p.documento_id
                GROUP BY d.id, d.nombre, d.hash, d.created_at
                ORDER BY d.created_at DESC
            """)
            docs = {doc['id']: doc for doc in cur.fetchall()}

            cur.execute("""
                SELECT
                    documento_id,
                    COUNT(*) as total_responses,
                    SUM(CASE WHEN es_correcta THEN 1 ELSE 0 END) as total_correct,
                    AVG(tiempo_respuesta_seconds) as avg_response_time_secs
                FROM estadisticas_respuestas
                GROUP BY documento_id
            """)
            stats = {row['documento_id']: row for row in cur.fetchall()}

            results = []
            for doc_id, doc_data in docs.items():
                doc_stats = stats.get(doc_id)
                if doc_stats:
                    doc_data['total_responses'] = doc_stats['total_responses']
                    doc_data['total_correct'] = doc_stats['total_correct']
                    doc_data['avg_response_time_secs'] = doc_stats['avg_response_time_secs']
                    doc_data['accuracy'] = (doc_stats['total_correct'] / doc_stats['total_responses'] * 100) if doc_stats['total_responses'] > 0 else 0
                else:
                    doc_data['total_responses'] = 0
                    doc_data['total_correct'] = 0
                    doc_data['avg_response_time_secs'] = None
                    doc_data['accuracy'] = None
                results.append(doc_data)

            results.sort(key=lambda x: x['created_at'], reverse=True)
            return results

    except psycopg2.Error as db_err:
         logging.error(f"Database error in get_overall_document_stats: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in get_overall_document_stats: {rb_err}")
         raise
    except Exception as e:
        st.error(f"Error fetching overall document stats: {e}") # Keep st.error for user feedback
        raise


def get_user_activity_summary(conn):
    summary = {}
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(DISTINCT usuario_id) as active_users FROM estadisticas_respuestas;")
            active_users_data = cur.fetchone()
            summary['active_users'] = active_users_data['active_users'] if active_users_data else 0

            cur.execute("SELECT COUNT(*) as total_answers FROM estadisticas_respuestas;")
            total_answers_data = cur.fetchone()
            summary['total_answers_recorded'] = total_answers_data['total_answers'] if total_answers_data else 0

            cur.execute("SELECT COUNT(DISTINCT id) as docs_with_questions FROM documentos WHERE id IN (SELECT DISTINCT documento_id FROM preguntas);")
            docs_data = cur.fetchone()
            summary['documents_processed'] = docs_data['docs_with_questions'] if docs_data else 0

            return summary
    except psycopg2.Error as db_err:
         logging.error(f"Database error in get_user_activity_summary: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in get_user_activity_summary: {rb_err}")
         raise
    except Exception as e:
        st.error(f"Error fetching user activity summary: {e}") # Keep st.error for user feedback
        raise # Re-raise after logging and showing error
    return {} # Should not be reached if raise happens