import psycopg2
from psycopg2.extras import RealDictCursor
import json

def conectar_postgresql():
    try:
        conn = psycopg2.connect(
            dbname="qgenerator",
            user="postgres",
            password="Pedriximo24",
            host="localhost",
            port="5432"
        )
        return conn
    except Exception as e:
        raise Exception(f"Error conectando a PostgreSQL: {e}")

def insertar_documento(conn, nombre_documento, hash_documento):
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
            return documento_id  # Nuevo documento insertado
        else:
            return result[0]  # Documento ya existe

def insertar_preguntas_json(conn, preguntas_json, documento_id):
    preguntas = []
    for pregunta in preguntas_json["questions"]:
        preguntas.append((
            documento_id,
            pregunta["question"],
            json.dumps(pregunta["options"]),
            pregunta["correct_answer"]
        ))
    with conn.cursor() as cur:
        insert_query = """
        INSERT INTO preguntas (documento_id, question, options, correct_answer)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (documento_id, question) DO NOTHING
        """
        cur.executemany(insert_query, preguntas)
        conn.commit()
        num_inserted = cur.rowcount
    return num_inserted

def obtener_documentos_cargados(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, nombre, hash FROM documentos")
        documentos = cur.fetchall()
    # Filtrar documentos únicos por nombre
    documentos_unicos = {doc["nombre"]: doc for doc in documentos}.values()
    return list(documentos_unicos)

def obtener_preguntas_por_documento(conn, documento_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM preguntas WHERE documento_id = %s", (documento_id,))
        preguntas = cur.fetchall()
    return preguntas

def obtener_preguntas_aleatorias(conn, documento_id, usuario_id, num_preguntas=5):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Obtener IDs de preguntas ya respondidas
        cur.execute("""
            SELECT pregunta_id FROM progreso_usuario
            WHERE usuario_id = %s AND documento_id = %s
        """, (usuario_id, documento_id))
        ids_respondidos = [row['pregunta_id'] for row in cur.fetchall()]
        
        # Obtener preguntas no respondidas
        if ids_respondidos:
            # Si ids_respondidos tiene solo un elemento, agregar una coma para formar una tupla
            ids_tuple = tuple(ids_respondidos) if len(ids_respondidos) > 1 else (ids_respondidos[0],)
            cur.execute("""
                SELECT * FROM preguntas
                WHERE documento_id = %s AND id NOT IN %s
                ORDER BY RANDOM()
                LIMIT %s
            """, (documento_id, ids_tuple, num_preguntas))
        else:
            cur.execute("""
                SELECT * FROM preguntas
                WHERE documento_id = %s
                ORDER BY RANDOM()
                LIMIT %s
            """, (documento_id, num_preguntas))
        preguntas_no_respondidas = cur.fetchall()
    return preguntas_no_respondidas

def reiniciar_progreso(conn, usuario_id, documento_id):
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM progreso_usuario
            WHERE usuario_id = %s AND documento_id = %s
        """, (usuario_id, documento_id))
        conn.commit()

def registrar_progreso(conn, usuario_id, documento_id, preguntas_resueltas):
    with conn.cursor() as cur:
        progreso = [(usuario_id, documento_id, pregunta_id) for pregunta_id in preguntas_resueltas]
        insert_query = """
        INSERT INTO progreso_usuario (usuario_id, documento_id, pregunta_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
        """
        cur.executemany(insert_query, progreso)
        conn.commit()

def registrar_respuesta(conn, usuario_id, pregunta_id, documento_id, tiempo_respuesta, es_correcta):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO estadisticas_respuestas (usuario_id, pregunta_id, documento_id, tiempo_respuesta, es_correcta)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (usuario_id, pregunta_id) DO UPDATE
            SET tiempo_respuesta = EXCLUDED.tiempo_respuesta,
                es_correcta = EXCLUDED.es_correcta
        """, (usuario_id, pregunta_id, documento_id, tiempo_respuesta, es_correcta))
        conn.commit()
