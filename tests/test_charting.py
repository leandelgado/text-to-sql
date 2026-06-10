import pandas as pd
import pytest

from src.charting import _TEMPORAL_KEYWORDS, suggest_chart


class TestEdgeCases:
    def test_none_returns_none(self):
        assert suggest_chart(None) is None

    def test_empty_df_returns_none(self):
        assert suggest_chart(pd.DataFrame()) is None

    def test_single_column_df_returns_none(self):
        df = pd.DataFrame({"total": [1, 2, 3]})
        assert suggest_chart(df) is None


class TestBarChart:
    def test_categorical_plus_numeric_returns_bar(self):
        df = pd.DataFrame({"segment": ["VIP", "Leal"], "total": [100, 200]})
        result = suggest_chart(df)
        assert result == {"type": "bar", "x": "segment", "y": "total"}


class TestLineChart:
    def test_temporal_keyword_in_column_name_returns_line(self):
        df = pd.DataFrame({"mes": ["2024-01", "2024-02"], "total_ventas": [1000, 2000]})
        result = suggest_chart(df)
        assert result is not None
        assert result["type"] == "line"
        assert result["x"] == "mes"
        assert result["y"] == "total_ventas"

    def test_datetime_dtype_column_returns_line(self):
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "monto": [500, 600],
            }
        )
        result = suggest_chart(df)
        assert result is not None
        assert result["type"] == "line"
        assert result["x"] == "fecha"
        assert result["y"] == "monto"

    def test_all_temporal_keywords_recognized(self):
        for kw in _TEMPORAL_KEYWORDS:
            df = pd.DataFrame({kw: ["a", "b"], "valor": [1, 2]})
            result = suggest_chart(df)
            assert result is not None and result["type"] == "line", (
                f"keyword '{kw}' not recognized as temporal"
            )


class TestAllNumeric:
    def test_all_numeric_columns_returns_none(self):
        df = pd.DataFrame({"total": [1, 2], "cantidad": [3, 4]})
        assert suggest_chart(df) is None

    def test_all_non_numeric_columns_returns_none(self):
        df = pd.DataFrame({"category": ["A", "B"], "label": ["X", "Y"]})
        assert suggest_chart(df) is None


class TestColumnSelection:
    def test_first_dim_and_first_numeric_selected(self):
        df = pd.DataFrame(
            {
                "region": ["Norte", "Sur"],
                "segment": ["VIP", "Leal"],
                "total": [100, 200],
                "cantidad": [10, 20],
            }
        )
        result = suggest_chart(df)
        assert result is not None
        assert result["x"] == "region"
        assert result["y"] == "total"
