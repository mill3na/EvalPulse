import json
import os

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("EVALPULSE_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="EvalPulse", page_icon="💓", layout="wide")
st.title("EvalPulse")
st.caption("Continuous, reproducible evaluations for AI agents")

with st.expander("How to read the metrics"):
    st.markdown(
        """
- **Exact match:** the normalized response must equal the expected answer.
- **Token overlap:** how much of the expected answer appears in the response.
- **Faithfulness:** how much of the response is supported by the supplied RAG context.
- **Context recall:** how much of the expected answer was present in the retrieved context.
- **Source citation:** whether the response cites the expected source identifiers.
- **Refusal:** whether an unsafe request receives an explicit refusal.
- **Forbidden pattern absence:** whether configured sensitive patterns are absent.

Every metric scores from **0% to 100%** and passes when it meets its own threshold.
A case passes only when all of its configured metrics pass.
"""
    )


def api_get(path: str) -> list[dict] | dict:
    response = httpx.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def start_run(dataset_id: str, agent_id: str) -> dict:
    response = httpx.post(
        f"{API_URL}/api/runs",
        json={"dataset_id": dataset_id, "agent_id": agent_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def upload_dataset(payload: bytes) -> dict:
    dataset = json.loads(payload)
    response = httpx.post(f"{API_URL}/api/datasets", json=dataset, timeout=10)
    response.raise_for_status()
    return response.json()


try:
    datasets = api_get("/api/datasets")
    metrics = api_get("/api/metrics")
    agents = api_get("/api/agents")
except httpx.HTTPError as error:
    st.error(f"The API is unavailable at {API_URL}: {error}")
    st.stop()

run_tab, dataset_tab, metrics_tab = st.tabs(["Run evaluation", "Datasets", "Metrics"])

with run_tab:
    agent_ids = [agent["id"] for agent in agents]
    selected_agent_id = st.selectbox(
        "Agent",
        options=agent_ids,
        format_func=lambda agent_id: next(
            item["name"] for item in agents if item["id"] == agent_id
        ),
    )
    selected_agent = next(item for item in agents if item["id"] == selected_agent_id)
    agent_column, provider_column, model_column = st.columns([2, 1, 1])
    agent_column.info(selected_agent["description"])
    provider_column.metric("Provider", selected_agent["provider"])
    model_column.metric("Model", selected_agent["model"])

    dataset_ids = [dataset["id"] for dataset in datasets]
    selected_dataset_id = st.selectbox(
        "Dataset",
        options=dataset_ids,
        format_func=lambda dataset_id: next(
            f"{item['name']} · {item['suite_type'].upper()} · v{item['version']}"
            for item in datasets
            if item["id"] == dataset_id
        ),
    )
    dataset_summary = next(item for item in datasets if item["id"] == selected_dataset_id)
    st.caption(
        f"{dataset_summary['description']} · {dataset_summary['case_count']} case(s) · "
        + ", ".join(dataset_summary["metrics"])
    )
    selected_dataset = api_get(f"/api/datasets/{selected_dataset_id}")
    with st.expander("Preview dataset cases"):
        for case in selected_dataset["cases"]:
            st.markdown(f"**{case['id']}** · `{case['input']}`")
            if case.get("expected"):
                st.caption(f"Expected: {case['expected']}")
            st.write(
                "Metrics: "
                + ", ".join(
                    f"{metric['name']} ≥ {metric['threshold']:.0%}" for metric in case["metrics"]
                )
            )
    if st.button("Run selected dataset", type="primary"):
        try:
            with st.spinner("Evaluating the demo agent..."):
                st.session_state["selected_run"] = start_run(
                    selected_dataset_id, selected_agent_id
                )["id"]
            st.success("Evaluation completed")
        except httpx.HTTPError as error:
            st.error(f"Could not start the evaluation: {error}")

with dataset_tab:
    st.subheader("Available datasets")
    st.dataframe(pd.DataFrame(datasets), use_container_width=True, hide_index=True)
    uploaded_file = st.file_uploader("Import a dataset", type="json")
    if uploaded_file and st.button("Validate and save dataset"):
        try:
            saved = upload_dataset(uploaded_file.getvalue())
            st.success(f"Saved {saved['name']} ({saved['id']})")
            st.rerun()
        except (json.JSONDecodeError, httpx.HTTPError) as error:
            st.error(f"Invalid dataset: {error}")
    with st.expander("Dataset JSON example"):
        st.code(
            json.dumps(
                {
                    "id": "my-qa-suite",
                    "name": "My Q&A suite",
                    "version": "1.0.0",
                    "suite_type": "qa",
                    "cases": [
                        {
                            "id": "case-001",
                            "input": "Question",
                            "expected": "Expected answer",
                            "metrics": [{"name": "token_overlap", "threshold": 0.8}],
                        }
                    ],
                },
                indent=2,
            ),
            language="json",
        )

with metrics_tab:
    st.subheader("Metric catalog")
    metric_rows = [
        {
            "metric": metric["name"],
            "suites": ", ".join(metric["suites"]),
            "requires": ", ".join(metric["requires"]) or "response only",
            "description": metric["description"],
        }
        for metric in metrics
    ]
    st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)
    st.info("Metrics are selected per case in the dataset JSON, each with its own threshold.")

try:
    runs = api_get("/api/runs")
except httpx.HTTPError as error:
    st.error(f"Could not load run history: {error}")
    st.stop()

st.divider()
st.header("Run history")
if not runs:
    st.info("No runs yet. Select a dataset and start the first evaluation.")
    st.stop()

filter_dataset, filter_status = st.columns(2)
dataset_filter = filter_dataset.selectbox(
    "Filter by dataset",
    options=["All"] + sorted({run.get("dataset_id", "legacy") for run in runs}),
)
status_filter = filter_status.selectbox("Filter by status", options=["All", "Passed", "Failed"])
filtered_runs = [
    run
    for run in runs
    if (dataset_filter == "All" or run.get("dataset_id", "legacy") == dataset_filter)
    and (
        status_filter == "All"
        or (status_filter == "Passed" and run["passed"])
        or (status_filter == "Failed" and not run["passed"])
    )
]
if not filtered_runs:
    st.info("No runs match the selected filters.")
    st.stop()

selected_id = st.selectbox(
    "Evaluation run",
    options=[run["id"] for run in filtered_runs],
    format_func=lambda run_id: next(
        f"{run['created_at'][:19]} · {run.get('dataset_id', 'legacy')} · {run['score']:.0%}"
        for run in filtered_runs
        if run["id"] == run_id
    ),
    index=next(
        (
            index
            for index, run in enumerate(filtered_runs)
            if run["id"] == st.session_state.get("selected_run")
        ),
        0,
    ),
)
selected = next(run for run in filtered_runs if run["id"] == selected_id)
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
st.caption(
    "Overall score = average of the metric scores inside each case, then average across cases. "
    "The run passes only when every configured metric reaches its threshold."
)

st.caption(
    f"Dataset: {selected.get('dataset_id', 'legacy')} v{selected.get('dataset_version', '?')} · "
    f"Suite: {selected.get('suite_type', 'qa').upper()} · Agent: {selected['agent']}"
)

if comparison:
    if comparison["regressed_cases"]:
        st.error("Regression detected: " + ", ".join(comparison["regressed_cases"]))
    elif comparison["improved_cases"]:
        st.success("Improved cases: " + ", ".join(comparison["improved_cases"]))
    else:
        st.info("No score changes compared with the previous compatible run.")

metric_rows = []
for case in selected["cases"]:
    results = case.get("metrics") or [
        {
            "name": case.get("metric", "legacy"),
            "score": case["score"],
            "threshold": case.get("threshold", 1),
            "passed": case["passed"],
        }
    ]
    for metric in results:
        metric_rows.append(
            {
                "case": case["case_id"],
                "metric": metric["name"],
                "score": metric["score"],
                "threshold": metric["threshold"],
                "passed": metric["passed"],
                "reason": metric.get("reason", "Legacy metric result"),
                "latency_ms": case["latency_ms"],
            }
        )
st.subheader("Metric results")
st.dataframe(
    pd.DataFrame(metric_rows),
    use_container_width=True,
    hide_index=True,
    column_config={
        "metric": st.column_config.TextColumn(
            "Metric",
            help="Evaluation criterion selected by the dataset for this case.",
        ),
        "score": st.column_config.NumberColumn(
            "Score",
            help="Observed quality from 0% to 100%.",
            format="percent",
        ),
        "threshold": st.column_config.NumberColumn(
            "Threshold",
            help="Minimum score required for this metric to pass.",
            format="percent",
        ),
        "passed": st.column_config.CheckboxColumn(
            "Passed",
            help="True when score is greater than or equal to the threshold.",
        ),
        "reason": st.column_config.TextColumn(
            "Reason",
            help="Short explanation generated by the metric evaluator.",
        ),
        "latency_ms": st.column_config.NumberColumn(
            "Latency (ms)",
            help="End-to-end response time measured for this case.",
            format="%.3f",
        ),
    },
)

compatible_runs = [
    run for run in reversed(runs) if run.get("dataset_hash") == selected.get("dataset_hash")
]
if len(compatible_runs) > 1:
    history = pd.DataFrame(
        {
            "created_at": pd.to_datetime([run["created_at"] for run in compatible_runs]),
            "score": [run["score"] for run in compatible_runs],
        }
    ).set_index("created_at")
    st.subheader("Quality over time")
    st.line_chart(history, y="score")

with st.expander("Inputs and outputs"):
    for case in selected["cases"]:
        st.markdown(f"**{case['case_id']}**")
        st.code(f"Input: {case['input']}\nExpected: {case['expected']}\nActual: {case['actual']}")
