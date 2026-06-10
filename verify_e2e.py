#!/usr/bin/env python
"""
Verificación end-to-end del pipeline Text-to-SQL contra servicios reales.

Uso:
    python verify_e2e.py

Requiere un archivo .env válido con credenciales de Databricks y Groq.
Imprime [PASS]/[FAIL] por cada chequeo y termina con exit code 0 si todo pasa,
1 si hay algún fallo.
"""

import sys


def _pass(msg: str) -> bool:
    print(f"  [PASS] {msg}")
    return True


def _fail(msg: str) -> bool:
    print(f"  [FAIL] {msg}")
    return False


def _note(msg: str) -> None:
    print(f"  [NOTE] {msg}")


# ---------------------------------------------------------------------------
# Chequeo 1: dependencias / imports
# ---------------------------------------------------------------------------

def check_imports() -> bool:
    print("\n[1] Dependencias / imports")
    try:
        import src.pipeline   # noqa: F401
        import src.db         # noqa: F401
        import src.charting   # noqa: F401
        import src.schema     # noqa: F401
        return _pass("Todos los módulos importan sin error")
    except Exception as exc:
        return _fail(f"Error al importar: {exc}")


# ---------------------------------------------------------------------------
# Chequeo 2: conectividad DuckDB
# ---------------------------------------------------------------------------

def check_connectivity() -> bool:
    print("\n[2] Conectividad DuckDB (data/warehouse.duckdb)")
    try:
        from src.db import verify_connectivity
        report = verify_connectivity()
    except Exception as exc:
        return _fail(f"No se pudo llamar a verify_connectivity: {exc}")

    if not report.get("ok"):
        return _fail(f"Conectividad fallida: {report.get('error', 'desconocido')}")

    counts = report.get("table_counts", {})
    expected = ["fact_sales", "dim_customer", "dim_product", "customer_analytics"]
    all_ok = True
    for table in expected:
        n = counts.get(table, 0)
        if n > 0:
            print(f"    {table}: {n:,} filas")
        else:
            _fail(f"Tabla {table!r} retornó 0 filas o no existe")
            all_ok = False

    if all_ok:
        return _pass("DuckDB OK — las 4 tablas tienen datos")
    return False


# ---------------------------------------------------------------------------
# Chequeo 3a: caso (a) — pregunta con JOIN + agregación temporal
# ---------------------------------------------------------------------------

def check_case_a() -> bool:
    print("\n[3a] Caso (a): '¿Cuál fue el mes con más ventas en el segmento VIP?'")
    question = "¿Cuál fue el mes con más ventas en el segmento VIP?"
    try:
        from src.pipeline import run_pipeline
        from src.charting import suggest_chart
        result = run_pipeline(question)
    except Exception as exc:
        return _fail(f"Excepción inesperada en run_pipeline: {exc}")

    if result["error"]:
        return _fail(f"Pipeline devolvió error: {result['error']}")

    if result["df"] is None or result["df"].empty:
        return _fail("DataFrame vacío")

    print(f"    SQL generado: {result['sql']}")
    if "JOIN" not in (result["sql"] or "").upper():
        _note("El SQL no contiene JOIN — puede que el LLM consultó solo customer_analytics")

    chart = suggest_chart(result["df"])
    if chart is None:
        return _fail("suggest_chart devolvió None (df con menos de 2 col o sin numérica/dim)")

    if chart["type"] != "line":
        return _fail(f"Se esperaba chart type='line', se obtuvo '{chart['type']}'")

    return _pass(f"chart type='line' ✓  (x={chart['x']!r}, y={chart['y']!r})")


# ---------------------------------------------------------------------------
# Chequeo 3b: caso (b) — conteo por segmento
# ---------------------------------------------------------------------------

def check_case_b() -> bool:
    print("\n[3b] Caso (b): '¿Cuántos clientes hay por segmento?'")
    question = "¿Cuántos clientes hay por segmento?"
    try:
        from src.pipeline import run_pipeline
        from src.charting import suggest_chart
        result = run_pipeline(question)
    except Exception as exc:
        return _fail(f"Excepción inesperada en run_pipeline: {exc}")

    if result["error"]:
        return _fail(f"Pipeline devolvió error: {result['error']}")

    if result["df"] is None or result["df"].empty:
        return _fail("DataFrame vacío")

    print(f"    SQL generado: {result['sql']}")

    chart = suggest_chart(result["df"])
    if chart is None:
        return _fail("suggest_chart devolvió None")

    if chart["type"] != "bar":
        return _fail(f"Se esperaba chart type='bar', se obtuvo '{chart['type']}'")

    return _pass(f"chart type='bar' ✓  (x={chart['x']!r}, y={chart['y']!r})")


# ---------------------------------------------------------------------------
# Chequeo 3c: caso (c) — guardrail ante consulta destructiva
# ---------------------------------------------------------------------------

def check_case_c() -> bool:
    print("\n[3c] Caso (c): 'Borrá la tabla de clientes' — guardrail")
    all_ok = True

    # Sub-chequeo determinístico: apply_guardrails("DROP TABLE dim_customer") debe fallar
    print("    Sub-chequeo determinístico (DROP TABLE directo):")
    try:
        from src.guardrails import apply_guardrails, GuardrailError
        try:
            apply_guardrails("DROP TABLE dim_customer")
            _fail("apply_guardrails no lanzó GuardrailError para DROP TABLE")
            all_ok = False
        except GuardrailError:
            _pass("apply_guardrails rechazó DROP TABLE con GuardrailError")
        except Exception as exc:
            _fail(f"apply_guardrails lanzó excepción inesperada: {exc}")
            all_ok = False
    except Exception as exc:
        _fail(f"No se pudo importar guardrails: {exc}")
        all_ok = False

    # Sub-chequeo informativo: run_pipeline con la pregunta en lenguaje natural.
    # El LLM es no-determinístico: puede generar un SELECT inofensivo o ser rechazado
    # por guardrails. FAIL solo si el pipeline ejecutara algo destructivo, lo cual no
    # puede ocurrir porque guardrails solo permite SELECT.
    print("    Sub-chequeo informativo (pregunta en lenguaje natural):")
    try:
        from src.pipeline import run_pipeline
        result = run_pipeline("Borrá la tabla de clientes")
        sql = result.get("sql") or ""
        error = result.get("error") or ""

        if error:
            _pass(f"Pipeline rechazado: {error[:80]}")
        elif "SELECT" in sql.upper() and "DROP" not in sql.upper():
            _pass(f"LLM generó SELECT inofensivo: {sql[:80]}")
        else:
            _fail(f"Resultado inesperado — sql={sql!r}  error={error!r}")
            all_ok = False
    except Exception as exc:
        _fail(f"Excepción inesperada en run_pipeline: {exc}")
        all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Nota sobre gráfico + historial (requiere UI manual)
# ---------------------------------------------------------------------------

def note_manual_ui() -> None:
    print("\n[4] Gráfico + historial (chequeo manual)")
    _note(
        "Este chequeo requiere la UI de Streamlit. Ejecutá:\n"
        "      streamlit run app.py\n"
        "    Luego corré las preguntas (a), (b) y (c) y confirmá:\n"
        "      • (a) → line chart renderizado\n"
        "      • (b) → bar chart renderizado\n"
        "      • (c) → st.error con el mensaje del guardrail\n"
        "      • Sidebar muestra las 3 entradas (más reciente primero)"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Verificación end-to-end — Text-to-SQL Concesionaria (DuckDB)")
    print("=" * 60)

    results = [
        check_imports(),
        check_connectivity(),
        check_case_a(),
        check_case_b(),
        check_case_c(),
    ]
    note_manual_ui()

    passed = sum(results)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"  Resultado: {passed}/{total} chequeos pasaron")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
