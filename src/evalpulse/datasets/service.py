from pathlib import Path

from evalpulse.models import DatasetSummary, EvalDataset


class DatasetStore:
    def __init__(self, builtin_dir: Path, user_dir: Path) -> None:
        self.builtin_dir = builtin_dir
        self.user_dir = user_dir
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for directory in (self.builtin_dir, self.user_dir):
            if directory.exists():
                for path in sorted(directory.glob("*.json")):
                    dataset = EvalDataset.model_validate_json(path.read_text(encoding="utf-8"))
                    paths[dataset.id] = path
        return paths

    def list(self) -> list[DatasetSummary]:
        summaries = []
        for dataset_id in sorted(self._paths()):
            dataset = self.get(dataset_id)
            if dataset is not None:
                summaries.append(
                    DatasetSummary(
                        id=dataset.id,
                        name=dataset.name,
                        version=dataset.version,
                        suite_type=dataset.suite_type,
                        description=dataset.description,
                        case_count=len(dataset.cases),
                        metrics=sorted(
                            {metric.name for case in dataset.cases for metric in case.metrics},
                            key=str,
                        ),
                    )
                )
        return summaries

    def get(self, dataset_id: str) -> EvalDataset | None:
        path = self._paths().get(dataset_id)
        if path is None:
            return None
        return EvalDataset.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, dataset: EvalDataset) -> EvalDataset:
        path = self.user_dir / f"{dataset.id}.json"
        path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
        return dataset
