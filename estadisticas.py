# --- START OF FILE estadisticas.py ---

from psycopg2.extras import RealDictCursor
import psycopg2
import logging

def obtener_pregunta_mas_equivocada(conn, usuario_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT pregunta_id, COUNT(*) as errores
            FROM estadisticas_respuestas
            WHERE usuario_id = %s AND es_correcta = FALSE
            GROUP BY pregunta_id
            ORDER BY errores DESC
            LIMIT 1
        """, (usuario_id,))
        result = cur.fetchone()
        return result

def obtener_promedio_tiempo_respuesta(conn, usuario_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT AVG(tiempo_respuesta_seconds) AS promedio_segundos
            FROM estadisticas_respuestas
            WHERE usuario_id = %s
        """, (usuario_id,))
        row = cur.fetchone()
        return row["promedio_segundos"] if row and row["promedio_segundos"] is not None else None

def obtener_estadisticas_por_documento_usuario(conn, documento_id, usuario_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id as pregunta_id, p.question,
                   -- COUNT(er.id) ya devuelve 0 si no hay respuestas er para p en LEFT JOIN
                   COUNT(er.id) as total_respuestas_usuario,
                   -- Usa COALESCE para SUM y AVG para reemplazar NULL con 0 o 0.0
                   COALESCE(SUM(CASE WHEN er.es_correcta THEN 1 ELSE 0 END), 0) as correctas_usuario,
                   COALESCE(SUM(CASE WHEN NOT er.es_correcta THEN 1 ELSE 0 END), 0) as incorrectas_usuario,
                   COALESCE(AVG(er.tiempo_respuesta_seconds), 0.0) as tiempo_promedio_usuario
            FROM preguntas p
            LEFT JOIN estadisticas_respuestas er ON p.id = er.pregunta_id
                                                 AND er.documento_id = %s
                                                 AND er.usuario_id = %s
            WHERE p.documento_id = %s
            GROUP BY p.id, p.question
            ORDER BY p.id
        """, (documento_id, usuario_id, documento_id))
        return cur.fetchall()

def obtener_estadisticas_por_documento_agregado(conn, documento_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id as pregunta_id, p.question,
                   COUNT(er.id) as total_respuestas,
                   COALESCE(SUM(CASE WHEN er.es_correcta THEN 1 ELSE 0 END), 0) as correctas,
                   COALESCE(SUM(CASE WHEN NOT er.es_correcta THEN 1 ELSE 0 END), 0) as incorrectas,
                   COALESCE(AVG(er.tiempo_respuesta_seconds), 0.0) as tiempo_promedio_agregado
            FROM preguntas p
            LEFT JOIN estadisticas_respuestas er ON p.id = er.pregunta_id
                                                 AND er.documento_id = %s
            WHERE p.documento_id = %s
            GROUP BY p.id, p.question
            ORDER BY p.id
        """, (documento_id, documento_id))
        return cur.fetchall()

def obtener_estadisticas_todas_las_preguntas(conn):
    """
    Obtiene estadísticas agregadas para cada pregunta en la base de datos,
    incluyendo información del documento.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # LEFT JOIN desde preguntas para incluir incluso las no respondidas
            # LEFT JOIN a documentos para obtener el nombre
            cur.execute("""
                SELECT
                    p.id AS pregunta_id,
                    p.question AS pregunta_texto,
                    p.documento_id,
                    d.nombre AS documento_nombre,
                    COUNT(er.id) AS total_intentos, -- Total de veces respondida por CUALQUIER usuario
                    COALESCE(SUM(CASE WHEN er.es_correcta THEN 1 ELSE 0 END), 0) AS total_correctas,
                    COALESCE(SUM(CASE WHEN NOT er.es_correcta THEN 1 ELSE 0 END), 0) AS total_incorrectas,
                    COALESCE(AVG(er.tiempo_respuesta_seconds), 0.0) AS tiempo_promedio_global,
                    COUNT(DISTINCT er.usuario_id) AS usuarios_unicos_intentaron -- Cuántos usuarios distintos la respondieron
                FROM preguntas p
                LEFT JOIN documentos d ON p.documento_id = d.id
                LEFT JOIN estadisticas_respuestas er ON p.id = er.pregunta_id
                GROUP BY p.id, p.question, p.documento_id, d.nombre
                ORDER BY p.documento_id, p.id -- Ordenar por documento y luego pregunta
            """)
            return cur.fetchall()
    except psycopg2.Error as db_err:
         logging.error(f"Database error in obtener_estadisticas_todas_las_preguntas: {db_err}")
         if "transaction is aborted" in str(db_err):
              try:
                  conn.rollback()
              except Exception as rb_err:
                   logging.error(f"Error during rollback attempt in obtener_estadisticas_todas_las_preguntas: {rb_err}")
         raise
    except Exception as e:
         logging.error(f"Unexpected error in obtener_estadisticas_todas_las_preguntas: {e}")
         raise