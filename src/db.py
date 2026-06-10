import os

import duckdb
import pandas as pd

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "warehouse.duckdb",
)

_con: duckdb.DuckDBPyConnection | None = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = duckdb.connect(":memory:")
        _con.execute(f"ATTACH '{_DB_PATH}' AS client_segmentation (READ_ONLY)")
    return _con


def run_query(sql: str) -> pd.DataFrame:
    return _get_connection().execute(sql).df()


def verify_connectivity() -> dict:
    from src.config import AVAILABLE_TABLES, DATABRICKS_CATALOG, DATABRICKS_SCHEMA

    result: dict = {"ok": False, "table_counts": {}, "customer_analytics_columns": []}

    try:
        for table in AVAILABLE_TABLES:
            df = run_query(
                f'SELECT COUNT(*) AS cnt FROM "{DATABRICKS_CATALOG}"."{DATABRICKS_SCHEMA}"."{table}"'
            )
            result["table_counts"][table] = int(df["cnt"].iloc[0])

        df_cols = run_query(
            f'DESCRIBE "{DATABRICKS_CATALOG}"."{DATABRICKS_SCHEMA}"."customer_analytics"'
        )
        result["customer_analytics_columns"] = df_cols["column_name"].tolist()
        result["ok"] = True

    except Exception as exc:
        result["error"] = str(exc)

    return result


if __name__ == "__main__":
    report = verify_connectivity()
    if report["ok"]:
        print("Conectividad OK")
        for table, count in report["table_counts"].items():
            print(f"  {table}: {count:,} filas")
        print(f"  customer_analytics columnas: {report['customer_analytics_columns']}")
    else:
        print(f"Error: {report.get('error')}")
