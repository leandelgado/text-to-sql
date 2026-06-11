from src.db import run_query
from src.guardrails import GuardrailError, apply_guardrails
from src.llm import DomainError, generate_sql


def run_pipeline(question: str) -> dict:
    result = {"sql": None, "df": None, "error": None, "corrected": False}
    sql = None

    try:
        sql = generate_sql(question)
        validated = apply_guardrails(sql)
        result["sql"] = validated
    except DomainError as exc:
        result["error"] = f"Pregunta fuera de dominio: {exc}"
        return result
    except GuardrailError as exc:
        result["sql"] = sql
        result["error"] = f"Consulta rechazada por guardrails: {exc}"
        return result
    except Exception as exc:
        result["error"] = f"Error generando SQL: {exc}"
        return result

    first_exc = None
    try:
        result["df"] = run_query(validated)
        return result
    except Exception as exc:
        first_exc = exc

    error_context = f"El siguiente SQL falló:\n{validated}\n\nError: {first_exc}"
    try:
        sql2 = generate_sql(question, error_context=error_context)
        validated2 = apply_guardrails(sql2)
        result["sql"] = validated2
        result["df"] = run_query(validated2)
        result["corrected"] = True
    except GuardrailError as exc:
        result["error"] = f"Consulta rechazada por guardrails tras corrección: {exc}"
    except Exception as exc:
        result["error"] = f"Error tras auto-corrección: {exc}"

    return result
