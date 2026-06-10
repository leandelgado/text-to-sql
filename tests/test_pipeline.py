from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.guardrails import GuardrailError
from src.pipeline import run_pipeline


_SQL = "SELECT segment, COUNT(*) AS cnt FROM t"
_SQL_VALIDATED = _SQL + " LIMIT 1000"


def _df(temporal=False):
    if temporal:
        return pd.DataFrame({"mes": ["2024-01", "2024-02"], "ventas": [100, 200]})
    return pd.DataFrame({"segment": ["VIP", "Leal"], "cnt": [50, 30]})


class TestRunPipelineNormalPath:
    def test_happy_path_df_populated(self):
        df = _df()
        with patch("src.pipeline.generate_sql", return_value=_SQL), \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", return_value=df):
            result = run_pipeline("¿Cuántos clientes hay por segmento?")
        assert result["error"] is None
        assert result["corrected"] is False
        assert result["df"] is not None
        assert not result["df"].empty

    def test_happy_path_sql_stored(self):
        df = _df()
        with patch("src.pipeline.generate_sql", return_value=_SQL), \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", return_value=df):
            result = run_pipeline("¿Cuántos clientes hay por segmento?")
        assert result["sql"] == _SQL_VALIDATED


class TestRunPipelineGuardrailRejects:
    def test_guardrail_error_sets_error_message(self):
        with patch("src.pipeline.generate_sql", return_value="DROP TABLE dim_customer"), \
             patch("src.pipeline.apply_guardrails", side_effect=GuardrailError("solo SELECT")), \
             patch("src.pipeline.run_query") as mock_query:
            result = run_pipeline("Borrá la tabla de clientes")
        assert "rechazada por guardrails" in result["error"]

    def test_guardrail_rejection_skips_run_query(self):
        with patch("src.pipeline.generate_sql", return_value="DROP TABLE dim_customer"), \
             patch("src.pipeline.apply_guardrails", side_effect=GuardrailError("solo SELECT")), \
             patch("src.pipeline.run_query") as mock_query:
            run_pipeline("Borrá la tabla de clientes")
        mock_query.assert_not_called()


class TestRunPipelineSelfCorrection:
    def test_self_correction_sets_corrected_flag(self):
        df = _df(temporal=True)
        with patch("src.pipeline.generate_sql", return_value=_SQL) as mock_gen, \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", side_effect=[Exception("column not found"), df]):
            result = run_pipeline("¿Cuál fue el mes con más ventas?")
        assert result["corrected"] is True
        assert result["df"] is not None
        assert not result["df"].empty

    def test_self_correction_calls_generate_sql_twice(self):
        df = _df()
        with patch("src.pipeline.generate_sql", return_value=_SQL) as mock_gen, \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", side_effect=[Exception("bad column"), df]):
            run_pipeline("¿Cuántos clientes?")
        assert mock_gen.call_count == 2

    def test_self_correction_passes_error_context(self):
        df = _df()
        with patch("src.pipeline.generate_sql", return_value=_SQL) as mock_gen, \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", side_effect=[Exception("bad column"), df]):
            run_pipeline("¿Cuántos clientes?")
        second_call_kwargs = mock_gen.call_args_list[1].kwargs
        assert second_call_kwargs.get("error_context") is not None


class TestRunPipelinePersistentFailure:
    def test_persistent_failure_sets_error_message(self):
        with patch("src.pipeline.generate_sql", return_value=_SQL), \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", side_effect=Exception("db error")):
            result = run_pipeline("¿Cuántos clientes?")
        assert "tras auto-corrección" in result["error"]

    def test_persistent_failure_df_is_none(self):
        with patch("src.pipeline.generate_sql", return_value=_SQL), \
             patch("src.pipeline.apply_guardrails", return_value=_SQL_VALIDATED), \
             patch("src.pipeline.run_query", side_effect=Exception("db error")):
            result = run_pipeline("¿Cuántos clientes?")
        assert result["df"] is None
