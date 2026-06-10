import pandas as pd

_TEMPORAL_KEYWORDS = frozenset(
    {
        "mes", "fecha", "date", "month",
        "año", "anio", "year",
        "día", "dia", "day",
        "semana", "week",
        "trimestre", "quarter",
    }
)


def suggest_chart(df: pd.DataFrame) -> dict | None:
    """
    Returns {"type": "bar"|"line", "x": <col>, "y": <col>} or None.
    None when: df is None/empty, fewer than 2 columns, no numeric column,
    or no non-numeric (dimension) column.
    Line when x column is datetime dtype or its name contains a temporal keyword.
    Bar otherwise.
    """
    if df is None or df.empty or len(df.columns) < 2:
        return None

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    dim_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

    if not numeric_cols or not dim_cols:
        return None

    x = dim_cols[0]
    y = numeric_cols[0]

    if pd.api.types.is_datetime64_any_dtype(df[x]):
        chart_type = "line"
    elif any(kw in x.lower() for kw in _TEMPORAL_KEYWORDS):
        chart_type = "line"
    else:
        chart_type = "bar"

    return {"type": chart_type, "x": x, "y": y}
