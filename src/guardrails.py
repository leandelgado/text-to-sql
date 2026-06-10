import sqlglot
from sqlglot import exp

from src.config import DEFAULT_ROW_LIMIT

_DIALECT = "duckdb"


class GuardrailError(ValueError):
    """SQL rechazado por los guardrails (no es un único SELECT)."""


def _parse(sql: str) -> exp.Expression:
    stripped = sql.strip()
    if not stripped:
        raise GuardrailError("SQL vacío o en blanco")

    try:
        statements = sqlglot.parse(stripped, dialect=_DIALECT, error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as exc:
        raise GuardrailError(f"SQL no parseable: {exc}") from exc

    statements = [s for s in statements if s is not None]

    if len(statements) == 0:
        raise GuardrailError("SQL vacío o en blanco")
    if len(statements) > 1:
        raise GuardrailError(
            f"Solo se permite una sentencia SQL; se detectaron {len(statements)}"
        )

    return statements[0]


def _ensure_select_only(expression: exp.Expression) -> None:
    if not isinstance(expression, exp.Select):
        raise GuardrailError(
            f"Solo se permiten sentencias SELECT; se recibió: {type(expression).__name__}"
        )


def _inject_limit(expression: exp.Expression) -> exp.Expression:
    if expression.args.get("limit") is None:
        return expression.limit(DEFAULT_ROW_LIMIT)
    return expression


def apply_guardrails(sql: str) -> str:
    expression = _parse(sql)
    _ensure_select_only(expression)
    expression = _inject_limit(expression)
    return expression.sql(dialect=_DIALECT)
