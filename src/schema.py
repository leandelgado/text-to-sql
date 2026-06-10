from src.config import DATABRICKS_CATALOG, DATABRICKS_SCHEMA, AVAILABLE_TABLES
from src.db import run_query

_cache: dict = {}

_CATEGORICAL_COLS: dict[str, list[str]] = {
    "customer_analytics": ["segment"],
    "fact_sales": ["channel"],
    "dim_product": ["product_category"],
}


def _load_schema() -> dict:
    schema: dict = {}
    for table in AVAILABLE_TABLES:
        fqn = f'"{DATABRICKS_CATALOG}"."{DATABRICKS_SCHEMA}"."{table}"'
        df = run_query(f"DESCRIBE {fqn}")
        mask = df["column_name"].str.strip().ne("") & ~df["column_name"].str.startswith("#")
        schema[table] = {
            "columns": [
                {"name": row["column_name"], "type": row["column_type"]}
                for _, row in df[mask].iterrows()
            ],
            "categorical_values": {},
        }

    for table, cols in _CATEGORICAL_COLS.items():
        fqn = f'"{DATABRICKS_CATALOG}"."{DATABRICKS_SCHEMA}"."{table}"'
        for col in cols:
            df = run_query(f'SELECT DISTINCT "{col}" FROM {fqn} ORDER BY "{col}"')
            schema[table]["categorical_values"][col] = df[col].dropna().tolist()

    return schema


def get_schema() -> dict:
    if not _cache:
        _cache.update(_load_schema())
    return _cache


def format_schema_for_prompt() -> str:
    schema = get_schema()
    parts: list[str] = []
    for table, info in schema.items():
        fqn = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.{table}"
        col_str = ", ".join(f"{c['name']} ({c['type']})" for c in info["columns"])
        parts.append(f"- {fqn}: {col_str}")
        for col, values in info["categorical_values"].items():
            vals = ", ".join(str(v) for v in values)
            parts.append(f"  * Valores posibles de {col}: {vals}")
    return "\n".join(parts)


if __name__ == "__main__":
    print(format_schema_for_prompt())
