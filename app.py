import altair as alt
import pandas as pd
import streamlit as st

from src.charting import suggest_chart
from src.pipeline import run_pipeline
from src.schema import get_schema

st.set_page_config(page_title="Text-to-SQL | Concesionaria", layout="wide")

_EXAMPLE_QUESTIONS = [
    "¿Cuál fue el mes con más ventas en el segmento VIP?",
    "¿Cuántos clientes hay por segmento?",
    "¿Cuáles son los 5 productos más vendidos por unidades?",
    "¿Cuál es el canal de venta con mayor facturación total?",
    "¿Qué porcentaje de los ingresos proviene de clientes VIP?",
    "¿Cuáles son los clientes en riesgo con mayor gasto histórico?",
    "¿Cuántas ventas hubo por mes durante el último año?",
    "¿Cuál es el ticket promedio por segmento de cliente?",
]


@st.cache_resource
def _warmup_schema():
    return get_schema()


def main():
    _warmup_schema()

    st.title("Text-to-SQL — Concesionaria Automotriz")
    st.caption(
        "Consultá el data warehouse en español. "
        "El LLM genera SQL para DuckDB, se valida y ejecuta automáticamente."
    )

    if "history" not in st.session_state:
        st.session_state["history"] = []

    st.subheader("Preguntas de ejemplo")
    cols = st.columns(4)
    for i, q in enumerate(_EXAMPLE_QUESTIONS):
        if cols[i % 4].button(q, key=f"example_{i}"):
            st.session_state["question_input"] = q
            st.rerun()

    question = st.text_input(
        "Tu pregunta",
        key="question_input",
        placeholder="ej. ¿Cuántos clientes hay por segmento?",
    )

    if st.button("Consultar", type="primary"):
        if not question.strip():
            st.warning("Por favor ingresá una pregunta.")
        else:
            with st.spinner("Generando SQL y ejecutando consulta..."):
                res = run_pipeline(question.strip())

            st.session_state["history"].insert(
                0,
                {"question": question.strip(), "sql": res["sql"], "error": res["error"]},
            )

            if res["error"]:
                st.error(res["error"])
            else:
                with st.expander("SQL generado", expanded=False):
                    st.code(res["sql"], language="sql")

                if res["corrected"]:
                    st.info("El primer intento de SQL falló. Se aplicó auto-corrección.")

                if res["df"] is not None and not res["df"].empty:
                    st.dataframe(res["df"], use_container_width=True)

                    chart_spec = suggest_chart(res["df"])
                    if chart_spec is not None:
                        chart_df = res["df"].copy()
                        x_col = chart_spec["x"]
                        y_col = chart_spec["y"]
                        if pd.api.types.is_datetime64_any_dtype(chart_df[x_col]):
                            chart_df[x_col] = chart_df[x_col].dt.strftime("%Y-%m")
                        row_order = chart_df[x_col].tolist()
                        if chart_spec["type"] == "line":
                            st.line_chart(chart_df.set_index(x_col)[[y_col]])
                        else:
                            st.altair_chart(
                                alt.Chart(chart_df).mark_bar().encode(
                                    x=alt.X(x_col, sort=row_order, title=x_col),
                                    y=alt.Y(y_col, title=y_col),
                                ).properties(width="container"),
                                use_container_width=True,
                            )
                else:
                    st.warning("La consulta no devolvió resultados.")

    if st.session_state["history"]:
        with st.sidebar:
            st.subheader("Historial de consultas")
            for entry in st.session_state["history"]:
                icon = "❌" if entry["error"] else "✅"
                with st.expander(f"{icon} {entry['question'][:60]}"):
                    if entry["sql"]:
                        st.code(entry["sql"], language="sql")
                    if entry["error"]:
                        st.error(entry["error"])


main()
