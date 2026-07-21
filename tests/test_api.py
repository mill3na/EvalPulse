from fastapi.testclient import TestClient

import evalpulse.api as api_module
from evalpulse.api import app
from evalpulse.datasets import DatasetStore
from evalpulse.store import RunStore


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_demo_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_store", RunStore(tmp_path / "runs.jsonl"))
    response = client.post("/api/runs", json={})
    assert response.status_code == 201
    payload = response.json()
    assert payload["agent"] == "demo-faq-agent"
    assert payload["dataset_id"] == "qa-demo"
    assert len(payload["cases"]) == 2


def test_second_run_compares_with_previous(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_store", RunStore(tmp_path / "runs.jsonl"))
    first = client.post("/api/runs", json={}).json()
    second = client.post("/api/runs", json={}).json()

    assert first["comparison"] is None
    assert second["comparison"]["baseline_run_id"] == first["id"]
    assert second["comparison"]["score_delta"] == 0


def test_dataset_catalog() -> None:
    response = client.get("/api/datasets")

    assert response.status_code == 200
    assert {dataset["id"] for dataset in response.json()} >= {
        "qa-demo",
        "rag-demo",
        "security-demo",
    }
    assert all("revision" in dataset for dataset in response.json())


def test_metric_catalog() -> None:
    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert "faithfulness" in {metric["name"] for metric in response.json()}


def test_agent_catalog() -> None:
    response = client.get("/api/agents")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "demo-faq-agent"


def test_unknown_agent_is_rejected() -> None:
    response = client.post("/api/runs", json={"agent_id": "missing"})

    assert response.status_code == 404


def test_upload_dataset(tmp_path, monkeypatch) -> None:
    store = DatasetStore(tmp_path / "builtin", tmp_path / "uploaded")
    monkeypatch.setattr(app.state, "dataset_store", store)
    response = client.post(
        "/api/datasets",
        json={
            "id": "uploaded-suite",
            "name": "Uploaded suite",
            "version": "1.0.0",
            "suite_type": "qa",
            "cases": [
                {
                    "id": "case-1",
                    "input": "Question",
                    "expected": "Answer",
                    "metrics": [{"name": "exact_match", "threshold": 1}],
                }
            ],
        },
    )

    assert response.status_code == 201
    assert store.get("uploaded-suite") is not None
