import re

import groq as groq_sdk

from src.config import GROQ_API_KEY, GROQ_MODEL, DATABRICKS_CATALOG, DATABRICKS_SCHEMA
from src.schema import format_schema_for_prompt

_client = groq_sdk.Groq(api_key=GROQ_API_KEY)

_BLOCK_RE = re.compile(r"```(?:sql)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_sql(text: str) -> str:
    match = _BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _build_user_message(question: str, error_context: str | None) -> str:
    if error_context is None:
        return f"Pregunta: {question}"
    return (
        f"Pregunta: {question}\n\n"
        f"{error_context}\n\n"
        "Por favor corregí el SQL para resolver el error."
    )


def _few_shot() -> str:
    db = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}"
    return (
        f"Pregunta: ¿Cuántos clientes hay por segmento?\n"
        f"SQL:\n"
        f"SELECT segment, COUNT(*) AS total_clientes\n"
        f"FROM {db}.customer_analytics\n"
        f"GROUP BY segment\n"
        f"ORDER BY total_clientes DESC\n\n"
        f"Pregunta: ¿Cuál es el canal de venta con mayor facturación total?\n"
        f"SQL:\n"
        f"SELECT channel, SUM(amount) AS facturacion_total\n"
        f"FROM {db}.fact_sales\n"
        f"GROUP BY channel\n"
        f"ORDER BY facturacion_total DESC\n"
        f"LIMIT 1\n\n"
        f"Pregunta: ¿Cuál fue el mes con más ventas en el segmento VIP?\n"
        f"SQL:\n"
        f"SELECT DATE_TRUNC('month', fs.sale_date) AS mes, SUM(fs.amount) AS total_ventas\n"
        f"FROM {db}.fact_sales fs\n"
        f"JOIN {db}.customer_analytics ca\n"
        f"  ON fs.customer_id = ca.customer_id\n"
        f"WHERE ca.segment = 'VIP'\n"
        f"GROUP BY mes\n"
        f"ORDER BY total_ventas DESC\n"
        f"LIMIT 1\n"
    )


def _build_system_prompt() -> str:
    schema = format_schema_for_prompt()
    db = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}"
    return (
        "Eres un experto en DuckDB SQL para una concesionaria automotriz.\n"
        "Tu única tarea es convertir preguntas en español a queries SQL válidas para DuckDB.\n"
        "Respondé ÚNICAMENTE con el SQL, sin explicaciones, comentarios ni bloques de código markdown.\n"
        f"El catálogo y esquema por defecto es {db}.\n\n"
        "Ejemplos:\n"
        f"{_few_shot()}\n"
        "Esquema disponible:\n"
        f"{schema}"
    )


def generate_sql(question: str, error_context: str | None = None) -> str:
    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_message(question, error_context)},
            ],
            temperature=0,
        )
    except Exception as exc:
        raise RuntimeError(f"Error al llamar a Groq para '{question}': {exc}") from exc
    if not response.choices:
        raise RuntimeError(f"Groq devolvió una respuesta vacía para '{question}'")
    raw = response.choices[0].message.content
    return _extract_sql(raw)
