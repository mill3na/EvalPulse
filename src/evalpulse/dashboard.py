import os

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("EVALPULSE_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="EvalPulse", page_icon="💓", layout="wide")
st.title("EvalPulse")
st.caption("Continuous, reproducible evaluations for AI agents")


def fetch_runs() -> list[dict]:
    response = httpx.get(f"{API_URL}/api/runs", timeout=10)
    response.raise_for_status()
    return response.json()


def start_run() -> dict:
    response = httpx.post(f"{API_URL}/api/runs", json={}, timeout=30)
    response.raise_for_status()
    return response.json()


if st.button("Run demo evaluation", type="primary"):
    try:
        with st.spinner("Evaluating the demo agent..."):
            st.session_state["selected_run"] = start_run()["id"]
        st.success("Evaluation completed")
    except httpx.HTTPError as error:
        st.error(f"Could not start the evaluation: {error}")

try:
    runs = fetch_runs()
except httpx.HTTPError as error:
    st.error(f"The API is unavailable at {API_URL}: {error}")
    st.stop()

if not runs:
    st.info("No runs yet. Start the demo evaluation to create the first baseline.")
    st.stop()

selected_id = st.selectbox(
    "Evaluation run",
    options=[run["id"] for run in runs],
    format_func=lambda run_id: next(
        f"{run['created_at'][:19]} · {run['agent']} · {run['score']:.0%}"
        for run in runs
        if run["id"] == run_id
    ),
    index=next(
        (
            index
            for index, run in enumerate(runs)
            if run["id"] == st.session_state.get("selected_run")
        ),
        0,
    ),
)
selected = next(run for run in runs if run["id"] == selected_id)
comparison = selected.get("comparison")

status_column, score_column, delta_column, cost_column, latency_column = st.columns(5)
status_column.metric("Status", "Passed" if selected["passed"] else "Failed")
score_column.metric("Overall score", f"{selected['score']:.0%}")
delta_column.metric(
    "Baseline delta",
    "First run" if comparison is None else f"{comparison['score_delta']:+.0%}",
)
cost_column.metric("Cost", f"${selected['total_cost_usd']:.4f}")
latency_column.metric("Latency", f"{selected['total_latency_ms']:.1f} ms")

if comparison:
    if comparison["regressed_cases"]:
        st.error("Regression detected: " + ", ".join(comparison["regressed_cases"]))
    elif comparison["improved_cases"]:
        st.success("Improved cases: " + ", ".join(comparison["improved_cases"]))
    else:
        st.info("No score changes compared with the previous run.")

case_rows = pd.DataFrame(selected["cases"])
case_rows["score"] = case_rows["score"].map(lambda value: f"{value:.0%}")
case_rows["latency_ms"] = case_rows["latency_ms"].map(lambda value: f"{value:.3f}")
st.subheader("Case results")
st.dataframe(
    case_rows[["case_id", "metric", "score", "threshold", "passed", "latency_ms", "cost_usd"]],
    use_container_width=True,
    hide_index=True,
)

if len(runs) > 1:
    history = pd.DataFrame(
        {
            "created_at": pd.to_datetime([run["created_at"] for run in reversed(runs)]),
            "score": [run["score"] for run in reversed(runs)],
        }
    ).set_index("created_at")
    st.subheader("Quality over time")
    st.line_chart(history, y="score")

with st.expander("Inputs and outputs"):
    for case in selected["cases"]:
        st.markdown(f"**{case['case_id']}**")
        st.code(f"Input: {case['input']}\nExpected: {case['expected']}\nActual: {case['actual']}")
