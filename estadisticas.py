from psycopg2.extras import RealDictCursor

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
        return result if result else None

def obtener_promedio_tiempo_respuesta(conn, usuario_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT AVG(EXTRACT(EPOCH FROM tiempo_respuesta)) AS promedio
            FROM estadisticas_respuestas
            WHERE usuario_id = %s
        """, (usuario_id,))
        row = cur.fetchone()
        return row["promedio"] if row and row["promedio"] is not None else None

def obtener_estadisticas_por_documento(conn, documento_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT pregunta_id,
                   COUNT(*) as total_respuestas,
                   SUM(CASE WHEN es_correcta THEN 1 ELSE 0 END) as correctas,
                   SUM(CASE WHEN NOT es_correcta THEN 1 ELSE 0 END) as incorrectas,
                   AVG(EXTRACT(EPOCH FROM tiempo_respuesta)) as tiempo_promedio
            FROM estadisticas_respuestas
            WHERE documento_id = %s
            GROUP BY pregunta_id
        """, (documento_id,))
        return cur.fetchall()
