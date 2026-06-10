from dotenv import load_dotenv
import os

load_dotenv()

# Catálogo y esquema — coinciden con el ATTACH alias y schema en data/warehouse.duckdb
DATABRICKS_CATALOG = "client_segmentation"
DATABRICKS_SCHEMA = "tablas"

# Groq
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Tablas disponibles para el LLM
AVAILABLE_TABLES = [
    "fact_sales",
    "dim_customer",
    "dim_product",
    "customer_analytics",
]

# Límite de filas por defecto inyectado por guardrails
DEFAULT_ROW_LIMIT = 1000
