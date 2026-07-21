from fastapi.testclient import TestClient

import evalpulse.api as api_module
from evalpulse.api import app
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
    assert len(payload["cases"]) == 3


def test_second_run_compares_with_previous(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_store", RunStore(tmp_path / "runs.jsonl"))
    first = client.post("/api/runs", json={}).json()
    second = client.post("/api/runs", json={}).json()

    assert first["comparison"] is None
    assert second["comparison"]["baseline_run_id"] == first["id"]
    assert second["comparison"]["score_delta"] == 0
