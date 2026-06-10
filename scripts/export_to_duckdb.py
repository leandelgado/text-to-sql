#!/usr/bin/env python
"""
One-time export: Databricks → data/warehouse.duckdb

Run this ONCE while Databricks access is still valid:
    python scripts/export_to_duckdb.py

Requires .env with DATABRICKS_* credentials and databricks-sql-connector installed.
Creates data/warehouse.duckdb with schema 'tablas' containing all 4 tables.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SERVER = os.environ["DATABRICKS_SERVER_HOSTNAME"]
HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
CATALOG = os.getenv("DATABRICKS_CATALOG", "client_segmentation")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "tablas")

TABLES = ["fact_sales", "dim_customer", "dim_product", "customer_analytics"]
OUT_PATH = os.path.join(PROJECT_ROOT, "data", "warehouse.duckdb")


def main() -> None:
    try:
        from databricks import sql as databricks_sql
    except ImportError:
        sys.exit("databricks-sql-connector is not installed. Run: pip install databricks-sql-connector")

    try:
        import duckdb
    except ImportError:
        sys.exit("duckdb is not installed. Run: pip install duckdb")

    import pandas as pd

    if os.path.exists(OUT_PATH):
        print(f"Warning: {OUT_PATH} already exists — tables will be replaced.")

    print(f"Connecting to Databricks {SERVER}...")
    db_con = databricks_sql.connect(
        server_hostname=SERVER,
        http_path=HTTP_PATH,
        access_token=TOKEN,
    )

    print(f"Opening {OUT_PATH} ...")
    duck = duckdb.connect(OUT_PATH)
    duck.execute("CREATE SCHEMA IF NOT EXISTS tablas")

    all_ok = True
    for table in TABLES:
        fqn = f"`{CATALOG}`.`{SCHEMA}`.`{table}`"
        print(f"  Exporting {fqn} ...", end="", flush=True)

        with db_con.cursor() as cur:
            cur.execute(f"SELECT * FROM {fqn}")
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

        df = pd.DataFrame(rows, columns=columns)
        src_count = len(df)
        print(f" {src_count:,} rows", end="")

        duck.execute(f"DROP TABLE IF EXISTS tablas.{table}")
        duck.register("_src", df)
        duck.execute(f"CREATE TABLE tablas.{table} AS SELECT * FROM _src")

        dst_count = duck.execute(f"SELECT COUNT(*) FROM tablas.{table}").fetchone()[0]
        ok = dst_count == src_count
        print(f" → DuckDB: {dst_count:,} rows {'✓' if ok else '✗ MISMATCH'}")
        if not ok:
            all_ok = False

    db_con.close()
    duck.close()

    if all_ok:
        size_mb = os.path.getsize(OUT_PATH) / 1024 / 1024
        print(f"\nDone. {OUT_PATH} ({size_mb:.1f} MB)")
        print("Commit data/warehouse.duckdb to the repo before deploying.")
    else:
        print("\nExport finished with mismatches — check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
