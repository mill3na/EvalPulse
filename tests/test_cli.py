from pathlib import Path

from evalpulse.cli import load_cases


def test_demo_dataset_is_valid() -> None:
    cases = load_cases(Path("datasets/demo.json"))

    assert len(cases) == 3
    assert {case.id for case in cases} == {
        "product-description",
        "local-startup",
        "deployment-requirement",
    }
