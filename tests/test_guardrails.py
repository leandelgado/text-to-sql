import pytest
import sqlglot
from sqlglot import exp

from src.config import DEFAULT_ROW_LIMIT
from src.guardrails import GuardrailError, _ensure_select_only, _inject_limit, _parse, apply_guardrails


# ---------------------------------------------------------------------------
# _parse
# ---------------------------------------------------------------------------


class TestParse:
    def test_single_select_returns_expression(self):
        result = _parse("SELECT 1")
        assert isinstance(result, exp.Expression)

    def test_multiple_statements_raises(self):
        with pytest.raises(GuardrailError, match="sentencia"):
            _parse("SELECT 1; DROP TABLE x")

    def test_empty_string_raises(self):
        with pytest.raises(GuardrailError, match="vacío"):
            _parse("")

    def test_whitespace_only_raises(self):
        with pytest.raises(GuardrailError, match="vacío"):
            _parse("   ")

    def test_unparseable_sql_raises(self):
        with pytest.raises(GuardrailError):
            _parse("(((")


# ---------------------------------------------------------------------------
# _ensure_select_only
# ---------------------------------------------------------------------------


class TestEnsureSelectOnly:
    def test_plain_select_passes(self):
        expr = _parse("SELECT 1")
        _ensure_select_only(expr)  # no raise

    def test_select_with_where_passes(self):
        expr = _parse("SELECT id FROM t WHERE x = 1")
        _ensure_select_only(expr)  # no raise

    def test_cte_select_passes(self):
        expr = _parse("WITH cte AS (SELECT 1) SELECT * FROM cte")
        _ensure_select_only(expr)  # no raise

    def test_insert_raises(self):
        expr = sqlglot.parse("INSERT INTO t VALUES (1)", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_update_raises(self):
        expr = sqlglot.parse("UPDATE t SET x = 1", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_delete_raises(self):
        expr = sqlglot.parse("DELETE FROM t WHERE x = 1", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_drop_table_raises(self):
        expr = sqlglot.parse("DROP TABLE t", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_create_table_raises(self):
        expr = sqlglot.parse("CREATE TABLE t (id INT)", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_alter_table_raises(self):
        expr = sqlglot.parse("ALTER TABLE t ADD COLUMN x INT", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)

    def test_truncate_table_raises(self):
        expr = sqlglot.parse("TRUNCATE TABLE t", dialect="duckdb")[0]
        with pytest.raises(GuardrailError):
            _ensure_select_only(expr)


# ---------------------------------------------------------------------------
# _inject_limit
# ---------------------------------------------------------------------------


class TestInjectLimit:
    def test_select_without_limit_gets_default_limit(self):
        expr = _parse("SELECT segment FROM t")
        result = _inject_limit(expr)
        result_sql = result.sql(dialect="duckdb")
        assert f"LIMIT {DEFAULT_ROW_LIMIT}" in result_sql

    def test_select_with_limit_1_preserved(self):
        expr = _parse("SELECT segment FROM t LIMIT 1")
        result = _inject_limit(expr)
        result_sql = result.sql(dialect="duckdb")
        assert "LIMIT 1" in result_sql
        assert f"LIMIT {DEFAULT_ROW_LIMIT}" not in result_sql

    def test_select_with_large_limit_preserved(self):
        expr = _parse("SELECT segment FROM t LIMIT 5000")
        result = _inject_limit(expr)
        result_sql = result.sql(dialect="duckdb")
        assert "LIMIT 5000" in result_sql


# ---------------------------------------------------------------------------
# apply_guardrails — end-to-end
# ---------------------------------------------------------------------------


class TestApplyGuardrails:
    def test_valid_query_without_limit_gets_limit_injected(self):
        result = apply_guardrails("SELECT segment FROM customer_analytics")
        assert f"LIMIT {DEFAULT_ROW_LIMIT}" in result

    def test_valid_query_with_limit_preserved(self):
        result = apply_guardrails("SELECT segment FROM customer_analytics LIMIT 50")
        assert "LIMIT 50" in result
        assert f"LIMIT {DEFAULT_ROW_LIMIT}" not in result

    def test_delete_raises_guardrail_error(self):
        with pytest.raises(GuardrailError):
            apply_guardrails("DELETE FROM dim_customer WHERE id = 1")

    def test_drop_table_raises_guardrail_error(self):
        with pytest.raises(GuardrailError):
            apply_guardrails("DROP TABLE dim_customer")

    def test_returns_string(self):
        result = apply_guardrails("SELECT 1")
        assert isinstance(result, str)

    def test_multiple_statements_raises_guardrail_error(self):
        with pytest.raises(GuardrailError):
            apply_guardrails("SELECT 1; DROP TABLE dim_customer")
