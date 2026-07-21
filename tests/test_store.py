from evalpulse.models import EvalRun
from evalpulse.store import RunStore


def test_store_persists_runs(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.jsonl")
    run = EvalRun(agent="test-agent", dataset_hash="abc", score=1, passed=True, cases=[])

    store.append(run)

    assert store.get(run.id) == run
    assert store.latest("test-agent", "abc") == run
    assert store.latest("test-agent", "different") is None
