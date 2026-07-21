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


def start_run(dataset_id: str, dataset_revision: int, agent_id: str) -> dict:
    response = httpx.post(
        f"{API_URL}/api/runs",
        json={
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "agent_id": agent_id,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def save_dataset(dataset: dict) -> dict:
    response = httpx.post(f"{API_URL}/api/datasets", json=dataset, timeout=10)
    response.raise_for_status()
    return response.json()


def non_empty_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


try:
    datasets = api_get("/api/datasets")
    metrics = api_get("/api/metrics")
    agents = api_get("/api/agents")
except httpx.HTTPError as error:
    st.error(f"The API is unavailable at {API_URL}: {error}")
    st.stop()

run_tab, dataset_tab, metrics_tab = st.tabs(
    ["Run evaluation", "➕ Add / manage datasets", "Metrics"]
)

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
    with st.expander("➕ Import a new dataset JSON"):
        st.caption(
            "Upload a validated dataset here, or use the visual builder in the "
            "Add / manage datasets tab."
        )
        quick_upload = st.file_uploader("Dataset JSON", type="json", key="quick-dataset-upload")
        if quick_upload and st.button("Import and select", key="quick-import-button"):
            try:
                saved = save_dataset(json.loads(quick_upload.getvalue()))
                st.session_state["preferred_dataset_id"] = saved["id"]
                st.success(f"Imported {saved['name']} as revision {saved['revision']}")
                st.rerun()
            except (json.JSONDecodeError, httpx.HTTPError) as error:
                st.error(f"Invalid dataset: {error}")
    selected_dataset_id = st.selectbox(
        "Dataset",
        options=dataset_ids,
        format_func=lambda dataset_id: next(
            f"{item['name']} · {item['suite_type'].upper()} · v{item['version']} · "
            f"rev {item['revision']} · {item['updated_at'][:10]}"
            for item in datasets
            if item["id"] == dataset_id
        ),
        index=(
            dataset_ids.index(st.session_state["preferred_dataset_id"])
            if st.session_state.get("preferred_dataset_id") in dataset_ids
            else 0
        ),
    )
    dataset_summary = next(item for item in datasets if item["id"] == selected_dataset_id)
    dataset_revisions = api_get(f"/api/datasets/{selected_dataset_id}/revisions")
    selected_revision = st.selectbox(
        "Revision",
        options=[revision["revision"] for revision in dataset_revisions],
        format_func=lambda revision_number: next(
            f"rev {item['revision']} · v{item['version']} · updated {item['updated_at'][:19]}"
            for item in dataset_revisions
            if item["revision"] == revision_number
        ),
    )
    selected_revision_summary = next(
        item for item in dataset_revisions if item["revision"] == selected_revision
    )
    st.caption(
        f"{dataset_summary['description']} · {dataset_summary['case_count']} case(s) · "
        + ", ".join(dataset_summary["metrics"])
    )
    st.info(
        "Metrics belong to the selected dataset revision, not to an individual run. "
        "To evaluate with different metrics, save a new revision in the Datasets tab."
    )
    selected_dataset = api_get(f"/api/datasets/{selected_dataset_id}/revisions/{selected_revision}")
    with st.expander("Preview dataset cases"):
        st.caption(
            f"Created: {selected_revision_summary['created_at'][:19]} · "
            f"Updated: {selected_revision_summary['updated_at'][:19]} · "
            f"Fingerprint: {selected_revision_summary['fingerprint']}"
        )
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
                    selected_dataset_id, selected_revision, selected_agent_id
                )["id"]
            st.success("Evaluation completed")
        except httpx.HTTPError as error:
            st.error(f"Could not start the evaluation: {error}")

with dataset_tab:
    create_tab, import_tab, browse_tab = st.tabs(["Create visually", "Import JSON", "Browse"])
    with create_tab:
        st.subheader("Create a dataset")
        st.caption(
            "Saving an existing Dataset ID creates a new immutable revision; previous revisions "
            "remain available for reproducible runs."
        )
        identity_column, version_column, suite_column = st.columns([2, 1, 1])
        new_name = identity_column.text_input("Name", placeholder="Customer support QA")
        new_version = version_column.text_input("Version", value="1.0.0")
        new_suite = suite_column.selectbox("Suite type", ["qa", "rag", "security", "custom"])
        new_id = st.text_input(
            "Dataset ID",
            placeholder="customer-support-qa",
            help="Lowercase letters, numbers, hyphens and underscores only.",
        )
        new_description = st.text_area("Description", height=80)
        case_count = st.number_input("Number of cases", min_value=1, max_value=10, value=1)
        suite_metrics = [
            metric["name"]
            for metric in metrics
            if new_suite in metric["suites"] or new_suite == "custom"
        ]
        default_metrics = {
            "qa": ["token_overlap"],
            "rag": ["token_overlap", "faithfulness", "context_recall", "source_citation"],
            "security": ["refusal", "forbidden_pattern_absence"],
            "custom": ["token_overlap"],
        }
        new_cases = []
        for case_index in range(int(case_count)):
            with st.expander(f"Case {case_index + 1}", expanded=case_index == 0):
                case_id = st.text_input(
                    "Case ID", value=f"case-{case_index + 1:03}", key=f"builder-id-{case_index}"
                )
                case_input = st.text_area("Input", key=f"builder-input-{case_index}")
                expected = ""
                contexts: list[str] = []
                expected_sources: list[str] = []
                forbidden_patterns: list[str] = []
                if new_suite != "security":
                    expected = st.text_area("Expected answer", key=f"builder-expected-{case_index}")
                if new_suite == "rag":
                    contexts = non_empty_lines(
                        st.text_area(
                            "Retrieved contexts (one per line)",
                            key=f"builder-contexts-{case_index}",
                        )
                    )
                    expected_sources = non_empty_lines(
                        st.text_area(
                            "Expected sources (one per line)", key=f"builder-sources-{case_index}"
                        )
                    )
                if new_suite == "security":
                    forbidden_patterns = non_empty_lines(
                        st.text_area(
                            "Forbidden patterns (one per line)",
                            key=f"builder-patterns-{case_index}",
                        )
                    )
                selected_metrics = st.multiselect(
                    "Metrics",
                    suite_metrics,
                    default=[name for name in default_metrics[new_suite] if name in suite_metrics],
                    key=f"builder-metrics-{case_index}",
                )
                configured_metrics = [
                    {
                        "name": metric_name,
                        "threshold": st.slider(
                            f"{metric_name} threshold",
                            min_value=0.0,
                            max_value=1.0,
                            value=0.8 if metric_name in {"token_overlap", "faithfulness"} else 1.0,
                            step=0.05,
                            key=f"builder-threshold-{case_index}-{metric_name}",
                        ),
                    }
                    for metric_name in selected_metrics
                ]
                new_cases.append(
                    {
                        "id": case_id,
                        "input": case_input,
                        "expected": expected,
                        "contexts": contexts,
                        "expected_sources": expected_sources,
                        "forbidden_patterns": forbidden_patterns,
                        "metrics": configured_metrics,
                    }
                )
        if st.button("Validate and save", type="primary"):
            try:
                saved = save_dataset(
                    {
                        "id": new_id,
                        "name": new_name,
                        "version": new_version,
                        "suite_type": new_suite,
                        "description": new_description,
                        "cases": new_cases,
                    }
                )
                st.success(f"Saved {saved['name']} ({saved['id']})")
                st.rerun()
            except httpx.HTTPStatusError as error:
                st.error(f"Dataset validation failed: {error.response.text}")

    with import_tab:
        uploaded_file = st.file_uploader("Import a dataset", type="json")
        if uploaded_file and st.button("Validate and save JSON"):
            try:
                saved = save_dataset(json.loads(uploaded_file.getvalue()))
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

    with browse_tab:
        st.subheader("Available datasets")
        st.dataframe(pd.DataFrame(datasets), use_container_width=True, hide_index=True)

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
    st.info(
        "Metrics are selected per case when creating a dataset. Adding a completely new metric "
        "implementation still requires code and tests; the UI configures metrics already in the catalog."
    )

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
        f"{run['created_at'][:19]} · {run.get('dataset_id', 'legacy')} "
        f"rev {run.get('dataset_revision', 1)} · {run['score']:.0%}"
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
    f"Dataset: {selected.get('dataset_id', 'legacy')} v{selected.get('dataset_version', '?')} "
    f"rev {selected.get('dataset_revision', 1)} · "
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
