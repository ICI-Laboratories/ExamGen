# --- START OF FILE estadisticas.py ---
# MIT License — 2025
# Copyright (c) 2025
# Yohana Yamille Ornelas Ochoa, Kenya Alexandra Ramos Valadez,
# Pedro Antonio Ibarra Facio

import streamlit as st # Para mostrar errores o información en algunos casos
from psycopg2.extras import RealDictCursor
import psycopg2 # Para psycopg2.Error
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)


def obtener_pregunta_mas_equivocada_usuario(conn, usuario_id: str):
    """
    Obtiene la pregunta (ID y texto) que un usuario específico ha fallado más veces,
    junto con el número de errores.
    """
    if not usuario_id:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    er.pregunta_id,
                    p.question AS pregunta_texto,
                    COUNT(er.id) AS numero_errores
                FROM estadisticas_respuestas er
                JOIN preguntas p ON er.pregunta_id = p.id
                WHERE er.usuario_id = %s AND er.es_correcta = FALSE
                GROUP BY er.pregunta_id, p.question
                ORDER BY numero_errores DESC
                LIMIT 1;
            """, (usuario_id,))
            return cur.fetchone()
    except psycopg2.Error as db_err:
        logger.error(f"Error DB obteniendo pregunta más equivocada para '{usuario_id}': {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        # No relanzar para no romper la UI, pero el error está logueado.
        return None
    except Exception as e:
        logger.error(f"Error inesperado obteniendo pregunta más equivocada para '{usuario_id}': {e}", exc_info=True)
        return None


def obtener_promedio_tiempo_respuesta_usuario(conn, usuario_id: str):
    """
    Calcula el tiempo promedio de respuesta (en segundos) para un usuario específico.
    """
    if not usuario_id:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT AVG(tiempo_respuesta_seconds) AS promedio_segundos
                FROM estadisticas_respuestas
                WHERE usuario_id = %s AND tiempo_respuesta_seconds IS NOT NULL;
            """, (usuario_id,))
            row = cur.fetchone()
            return row["promedio_segundos"] if row and row["promedio_segundos"] is not None else None
    except psycopg2.Error as db_err:
        logger.error(f"Error DB obteniendo promedio tiempo respuesta para '{usuario_id}': {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        return None
    except Exception as e:
        logger.error(f"Error inesperado obteniendo promedio tiempo respuesta para '{usuario_id}': {e}", exc_info=True)
        return None


def obtener_estadisticas_por_documento_para_usuario(conn, documento_id: int, usuario_id: str):
    """
    Obtiene estadísticas detalladas por pregunta para un usuario específico en un documento dado.
    Incluye preguntas del documento incluso si el usuario no las ha respondido.
    """
    if not documento_id or not usuario_id:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    p.id AS pregunta_id,
                    p.question AS pregunta_texto,
                    d.nombre AS documento_nombre,
                    COALESCE(SUM(CASE WHEN er.usuario_id = %s THEN 1 ELSE 0 END), 0) AS total_respuestas_usuario,
                    COALESCE(SUM(CASE WHEN er.usuario_id = %s AND er.es_correcta THEN 1 ELSE 0 END), 0) AS correctas_usuario,
                    COALESCE(SUM(CASE WHEN er.usuario_id = %s AND NOT er.es_correcta THEN 1 ELSE 0 END), 0) AS incorrectas_usuario,
                    COALESCE(AVG(CASE WHEN er.usuario_id = %s THEN er.tiempo_respuesta_seconds ELSE NULL END), 0.0) AS tiempo_promedio_usuario_secs
                FROM preguntas p
                JOIN documentos d ON p.documento_id = d.id
                LEFT JOIN estadisticas_respuestas er
                    ON p.id = er.pregunta_id AND er.documento_id = p.documento_id -- Asegurar que la respuesta sea para esta pregunta y doc
                WHERE p.documento_id = %s
                GROUP BY p.id, p.question, d.nombre
                ORDER BY p.id;
            """, (usuario_id, usuario_id, usuario_id, usuario_id, documento_id))
            # Los COALESCE y el LEFT JOIN aseguran que todas las preguntas del documento aparezcan,
            # con 0s para las métricas del usuario si no ha respondido.
            return cur.fetchall()
    except psycopg2.Error as db_err:
        logger.error(f"Error DB en estadísticas por documento para usuario '{usuario_id}', doc ID {documento_id}: {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        return []
    except Exception as e:
        logger.error(f"Error inesperado en estadísticas por documento para usuario '{usuario_id}', doc ID {documento_id}: {e}", exc_info=True)
        return []


def obtener_estadisticas_agregadas_por_documento(conn, documento_id: int):
    """
    Obtiene estadísticas agregadas (todos los usuarios) por pregunta para un documento específico.
    """
    if not documento_id:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    p.id AS pregunta_id,
                    p.question AS pregunta_texto,
                    d.nombre AS documento_nombre,
                    COUNT(er.id) AS total_respuestas_global, -- Total de intentos para esta pregunta por todos
                    COALESCE(SUM(CASE WHEN er.es_correcta THEN 1 ELSE 0 END), 0) AS total_correctas_global,
                    COALESCE(SUM(CASE WHEN NOT er.es_correcta THEN 1 ELSE 0 END), 0) AS total_incorrectas_global,
                    COALESCE(AVG(er.tiempo_respuesta_seconds), 0.0) AS tiempo_promedio_global_secs,
                    COUNT(DISTINCT er.usuario_id) AS usuarios_unicos_intentaron
                FROM preguntas p
                JOIN documentos d ON p.documento_id = d.id
                LEFT JOIN estadisticas_respuestas er ON p.id = er.pregunta_id AND er.documento_id = p.documento_id
                WHERE p.documento_id = %s
                GROUP BY p.id, p.question, d.nombre
                ORDER BY p.id;
            """, (documento_id,))
            return cur.fetchall()
    except psycopg2.Error as db_err:
        logger.error(f"Error DB en estadísticas agregadas por documento ID {documento_id}: {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        return []
    except Exception as e:
        logger.error(f"Error inesperado en estadísticas agregadas por documento ID {documento_id}: {e}", exc_info=True)
        return []


def obtener_estadisticas_globales_todas_las_preguntas(conn):
    """
    Obtiene estadísticas agregadas para CADA pregunta en la base de datos,
    incluyendo información del documento.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    p.id AS pregunta_id,
                    p.question AS pregunta_texto,
                    p.documento_id,
                    d.nombre AS documento_nombre,
                    d.curso_tag,
                    d.grado_tag,
                    COUNT(er.id) AS total_intentos_global,
                    COALESCE(SUM(CASE WHEN er.es_correcta THEN 1 ELSE 0 END), 0) AS total_correctas_global,
                    COALESCE(SUM(CASE WHEN NOT er.es_correcta THEN 1 ELSE 0 END), 0) AS total_incorrectas_global,
                    COALESCE(AVG(er.tiempo_respuesta_seconds), 0.0) AS tiempo_promedio_global_secs,
                    COUNT(DISTINCT er.usuario_id) AS usuarios_unicos_intentaron
                FROM preguntas p
                LEFT JOIN documentos d ON p.documento_id = d.id
                LEFT JOIN estadisticas_respuestas er ON p.id = er.pregunta_id -- Asume que er.documento_id es igual a p.documento_id
                GROUP BY p.id, p.question, p.documento_id, d.nombre, d.curso_tag, d.grado_tag
                ORDER BY d.nombre, p.id;
            """)
            return cur.fetchall()
    except psycopg2.Error as db_err:
        logger.error(f"Error DB obteniendo estadísticas globales de todas las preguntas: {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        return []
    except Exception as e:
        logger.error(f"Error inesperado obteniendo estadísticas globales de todas las preguntas: {e}", exc_info=True)
        return []

def obtener_resumen_actividad_general(conn):
    """
    Obtiene un resumen general de la actividad en la plataforma.
    (Similar a get_user_activity_summary de database.py, pero puede enfocarse en otros aspectos).
    """
    summary = {
        'total_usuarios_registrados': 0, # Si tuvieras una tabla de usuarios explícita
        'sesiones_activas_hoy': 0, # Ejemplo de métrica avanzada
        'total_documentos_cargados': 0,
        'total_preguntas_generadas': 0,
        'total_respuestas_registradas': 0,
        'feedback_promedio_rating': None,
        'total_feedback_enviado': 0,
    }
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Ejemplo: total de usuarios únicos que han interactuado (respondido algo)
            cur.execute("SELECT COUNT(DISTINCT usuario_id) as usuarios_interactuado FROM estadisticas_respuestas;")
            res = cur.fetchone()
            summary['usuarios_con_respuestas'] = res['usuarios_interactuado'] if res else 0

            cur.execute("SELECT COUNT(id) as total_documentos FROM documentos;")
            res = cur.fetchone()
            summary['total_documentos_cargados'] = res['total_documentos'] if res else 0

            cur.execute("SELECT COUNT(id) as total_preguntas FROM preguntas;")
            res = cur.fetchone()
            summary['total_preguntas_generadas'] = res['total_preguntas'] if res else 0

            cur.execute("SELECT COUNT(id) as total_respuestas FROM estadisticas_respuestas;")
            res = cur.fetchone()
            summary['total_respuestas_registradas'] = res['total_respuestas'] if res else 0

            cur.execute("SELECT AVG(rating) as avg_rating, COUNT(id) as total_feedback FROM feedback_usuario WHERE rating IS NOT NULL;")
            res = cur.fetchone()
            if res:
                summary['feedback_promedio_rating'] = res['avg_rating']
                summary['total_feedback_enviado'] = res['total_feedback']

            # Puedes añadir más consultas para otras métricas
            return summary
    except psycopg2.Error as db_err:
        logger.error(f"Error DB obteniendo resumen de actividad general: {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
    except Exception as e:
        logger.error(f"Error inesperado obteniendo resumen de actividad general: {e}", exc_info=True)
    return summary # Devuelve el summary incluso si algunas consultas fallan, con los valores por defecto

def obtener_documentos_mas_usados(conn, limit=10):
    """Obtiene los documentos más usados basados en el número de quiz_attempts."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    d.id as documento_id,
                    d.nombre as documento_nombre,
                    COUNT(qa.id) as numero_intentos_cuestionario
                FROM documentos d
                JOIN quiz_attempts qa ON d.id = qa.documento_id
                GROUP BY d.id, d.nombre
                ORDER BY numero_intentos_cuestionario DESC
                LIMIT %s;
            """, (limit,))
            return cur.fetchall()
    except psycopg2.Error as db_err:
        logger.error(f"Error DB obteniendo documentos más usados: {db_err}", exc_info=True)
        if "transaction is aborted" in str(db_err).lower(): conn.rollback()
        return []
    except Exception as e:
        logger.error(f"Error inesperado obteniendo documentos más usados: {e}", exc_info=True)
        return []

# --- FIN DE estadisticas.py ---