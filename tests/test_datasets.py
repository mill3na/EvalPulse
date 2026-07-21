from evalpulse.datasets import DatasetStore
from evalpulse.models import EvalDataset


def qa_dataset(version: str = "1.0.0") -> EvalDataset:
    return EvalDataset.model_validate(
        {
            "id": "versioned-qa",
            "name": "Versioned QA",
            "version": version,
            "suite_type": "qa",
            "cases": [
                {
                    "id": "case-1",
                    "input": "Question",
                    "expected": "Answer",
                    "metrics": [{"name": "exact_match", "threshold": 1}],
                }
            ],
        }
    )


def test_saving_existing_dataset_creates_revision(tmp_path) -> None:
    store = DatasetStore(tmp_path / "builtin", tmp_path / "uploaded")

    first = store.save(qa_dataset())
    second = store.save(qa_dataset("1.1.0"))

    assert first.revision == 1
    assert second.revision == 2
    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at
    assert store.get("versioned-qa", 1).version == "1.0.0"
    assert store.get("versioned-qa", 2).version == "1.1.0"
    assert [item.revision for item in store.revisions("versioned-qa")] == [2, 1]
