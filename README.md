# Text-to-SQL en Español — Concesionaria Automotriz

Pregunta en español → SQL → resultados + gráfico automático, sobre DuckDB embebido.

---

![Demo](Screenshot/Captura%20de%20pantalla%202026-06-10%20141010.png)

---

## Qué resuelve

Consultar un data warehouse requiere conocer SQL, el esquema de tablas y el dialecto específico del motor — barreras que dejan fuera a analistas, vendedores y gerentes que son quienes más necesitan los datos.

Esta aplicación elimina esa barrera: el usuario escribe una pregunta en español, un LLM la convierte en una query SQL válida para DuckDB, se valida automáticamente y se ejecuta. Los resultados se muestran como tabla y, cuando tiene sentido, como gráfico generado sin configuración manual.

El flujo incluye **auto-corrección**: si la primera query falla, el error se reenvía al LLM para un segundo intento antes de mostrarle algo al usuario.

---

## Contexto del Dataset

El esquema estrella `client_segmentation.tablas` contiene cuatro tablas almacenadas en `data/warehouse.duckdb`:

| Tabla | Filas aprox. | Descripción |
|---|---|---|
| `fact_sales` | 42.500 | Transacciones de ventas (importe, fecha, producto, cliente, canal) |
| `dim_customer` | 5.000 | Atributos del cliente (nombre, región, tipo) |
| `dim_product` | 1.200 | Catálogo de productos (categoría, marca, modelo) |
| `customer_analytics` | 5.000 | Segmentación RFM + clustering K-means por cliente |

### Segmentación RFM + K-means

`customer_analytics` es el resultado de un proceso de segmentación:

1. **RFM**: a cada cliente se le calculan tres métricas sobre su historial de compras — *Recency* (días desde la última compra), *Frequency* (cantidad de transacciones) y *Monetary* (gasto total).
2. **K-means**: los valores RFM normalizados se agrupan en clusters. Cada cluster recibe una etiqueta de negocio (`segment`): `VIP`, `Leal`, `En Riesgo`, `Perdido`, `Nuevo`, etc.

Esto permite responder preguntas como _"¿Cuáles son los productos más comprados por clientes VIP?"_ combinando `customer_analytics` con `fact_sales`.

---

## Cómo funciona

```
Usuario (pregunta en español)
        │
        ▼
  ┌─────────────┐
  │  Streamlit  │  ← UI: input, ejemplos, historial
  └──────┬──────┘
         │ pregunta
         ▼
  ┌─────────────┐    esquema + few-shot
  │  src/llm.py │ ─────────────────────► Groq API (llama-3.3-70b)
  └──────┬──────┘ ◄─────────────────────  SQL generado
         │ SQL
         ▼
  ┌──────────────────┐
  │ src/guardrails.py│  ← validar SELECT, inyectar LIMIT 1000
  └──────┬───────────┘
         │ SQL validado
         ▼
  ┌─────────────┐
  │  src/db.py  │  ← DuckDB embebido (data/warehouse.duckdb)
  └──────┬──────┘
         │ DataFrame
         ▼
  ┌──────────────────┐
  │ src/charting.py  │  ← gráfico automático (bar / line)
  └──────────────────┘
         │
         ▼
  UI: tabla + gráfico + SQL expandible + historial de sesión
```

El flujo completo está orquestado por `src/pipeline.py`. Ante un error de ejecución en DuckDB, `pipeline.run_pipeline` reenvía el SQL fallido y el mensaje de error al LLM para un segundo intento (**self-correction**) antes de propagar el fallo a la UI.

---

## Función de cada script

| Archivo | Función |
|---|---|
| [app.py](app.py) | UI Streamlit: campo de texto, botones de preguntas de ejemplo, expander con el SQL generado, `st.dataframe` con resultados, gráfico automático, historial de sesión en `st.session_state` y warmup del esquema cacheado al iniciar. |
| [src/pipeline.py](src/pipeline.py) | Orquesta el flujo `generate_sql → apply_guardrails → run_query` con manejo de self-correction; devuelve `{sql, df, error, corrected}`. |
| [src/llm.py](src/llm.py) | Cliente Groq con `temperature=0`. Construye el system prompt en español con el esquema completo + 3 ejemplos few-shot (incluyendo un JOIN entre `fact_sales` y `customer_analytics`). Extrae el SQL del bloque de código en la respuesta. Acepta `error_context` para el reintento de self-correction. |
| [src/guardrails.py](src/guardrails.py) | Parsea el SQL con `sqlglot` en dialecto DuckDB. Rechaza todo lo que no sea un único `SELECT` (DDL, DML, múltiples sentencias) y lanza `GuardrailError`. Inyecta `LIMIT 1000` si no está presente. |
| [src/db.py](src/db.py) | Conecta un DuckDB en memoria y adjunta `data/warehouse.duckdb` como catálogo `client_segmentation`. Expone `run_query(sql) → pd.DataFrame`. |
| [src/schema.py](src/schema.py) | Introspección vía `DESCRIBE` cacheada a nivel módulo. Obtiene valores posibles de columnas categóricas clave (`segment`, `channel`, `product_category`) con `SELECT DISTINCT`. Expone `get_schema()` y `format_schema_for_prompt()` para enriquecer el prompt del LLM. |
| [src/charting.py](src/charting.py) | Heurística de gráfico automático: si el DataFrame tiene al menos una columna dimensional y una numérica, sugiere `bar` o `line`. Elige `line` cuando la columna x es de tipo datetime o su nombre contiene palabras temporales (`mes`, `fecha`, `year`, etc.). |
| [src/config.py](src/config.py) | Carga `.env` con `python-dotenv` y expone las constantes del proyecto: clave y modelo de Groq, catálogo/esquema y lista de tablas. |
| [verify_e2e.py](verify_e2e.py) | Verificación end-to-end: chequea imports, conectividad DuckDB, caso (a) JOIN + agregación temporal → `line chart`, caso (b) conteo por segmento → `bar chart`, y caso (c) consulta destructiva → rechazada por guardrails. Imprime `[PASS]`/`[FAIL]` por chequeo. |

---

## Stack

| Componente | Tecnología |
|---|---|
| UI | Streamlit |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Base de datos | DuckDB embebido (`data/warehouse.duckdb`) |
| Validación SQL | `sqlglot` |
| Lenguaje | Python 3.10+ |
| Deploy | Streamlit Community Cloud |

---

## Setup

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd "Text to SQL"
```

### 2. Variables de entorno

Crear un archivo `.env` en la raíz con la única variable requerida:

```env
GROQ_API_KEY=<tu-api-key-de-groq>
```

> Obtener una API key gratuita en [console.groq.com](https://console.groq.com).
> El archivo `.env` está en `.gitignore` y nunca debe commitearse.

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Correr la app

```bash
streamlit run app.py
```

La aplicación abre en `http://localhost:8501`. Escribir una pregunta en el campo de texto o hacer clic en uno de los botones de ejemplo.

Para correr la verificación end-to-end (requiere `GROQ_API_KEY` en `.env`):

```bash
python verify_e2e.py
```

---

## Preguntas de Ejemplo

```
¿Cuál fue el mes con más ventas en el segmento VIP?
¿Cuántos clientes hay por segmento?
¿Cuáles son los 5 productos más vendidos por unidades?
¿Cuál es el canal de venta con mayor facturación total?
¿Qué porcentaje de los ingresos proviene de clientes VIP?
¿Cuáles son los clientes en riesgo con mayor gasto histórico?
¿Cuántas ventas hubo por mes durante el último año?
¿Cuál es el ticket promedio por segmento de cliente?
```

---

## Tests

La suite en [tests/](tests/) cubre los módulos principales con mocks, sin requerir credenciales ni conexión real:

| Archivo | Qué cubre |
|---|---|
| [tests/test_guardrails.py](tests/test_guardrails.py) | Casos válidos e inválidos de `apply_guardrails`: DDL, DML, múltiples sentencias, inyección de LIMIT. |
| [tests/test_charting.py](tests/test_charting.py) | Heurística de `suggest_chart`: bar vs. line, columnas temporales, DataFrames sin dimensión/numérica. |
| [tests/test_pipeline.py](tests/test_pipeline.py) | Flujo completo de `run_pipeline` con mocks de `generate_sql` y `run_query`, incluyendo el camino de self-correction. |
| [tests/test_llm.py](tests/test_llm.py) | `generate_sql` con mock del cliente Groq: extracción de SQL desde bloques markdown y manejo de `error_context`. |

```bash
pytest
```

---

## Estructura del Repositorio

```
Text to SQL/
├── README.md
├── requirements.txt
├── .gitignore
├── .env                        ← solo GROQ_API_KEY (NO commitear)
├── app.py                      ← UI Streamlit
├── verify_e2e.py               ← verificación end-to-end
├── conftest.py
├── src/
│   ├── config.py               ← constantes y carga de .env
│   ├── db.py                   ← DuckDB ATTACH y run_query()
│   ├── schema.py               ← DESCRIBE, caché de módulo, valores posibles
│   ├── llm.py                  ← cliente Groq, prompt few-shot, self-correction
│   ├── guardrails.py           ← validación sqlglot, LIMIT automático
│   ├── charting.py             ← heurística de gráfico automático
│   └── pipeline.py             ← orquestación del pipeline
├── tests/
│   ├── test_guardrails.py
│   ├── test_charting.py
│   ├── test_pipeline.py
│   └── test_llm.py
├── data/
│   ├── warehouse.duckdb        ← dataset embebido (~10 MB)
│   ├── dim_customer.csv
│   ├── dim_product.csv
│   └── fact_sales.csv
└── scripts/
    └── export_to_duckdb.py     ← script desechable de exportación desde Databricks
```
