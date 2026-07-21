from pathlib import Path

import pytest
from pydantic import ValidationError

from evalpulse.cli import load_dataset
from evalpulse.models import EvalDataset


def test_demo_datasets_are_valid() -> None:
    datasets = [load_dataset(path) for path in Path("datasets").glob("*.json")]

    assert {dataset.id for dataset in datasets} == {"qa-demo", "rag-demo", "security-demo"}
    assert all(dataset.cases for dataset in datasets)


def test_rag_metric_requires_context() -> None:
    with pytest.raises(ValidationError, match="requires contexts"):
        EvalDataset.model_validate(
            {
                "id": "invalid-rag",
                "name": "Invalid RAG",
                "version": "1.0.0",
                "suite_type": "rag",
                "cases": [
                    {
                        "id": "missing-context",
                        "input": "Question",
                        "metrics": [{"name": "faithfulness", "threshold": 0.8}],
                    }
                ],
            }
        )
