from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from evalpulse.engine import dataset_fingerprint
from evalpulse.models import DatasetSummary, EvalDataset


class DatasetStore:
    def __init__(self, builtin_dir: Path, user_dir: Path) -> None:
        self.builtin_dir = builtin_dir
        self.user_dir = user_dir
        self.user_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load(path: Path) -> EvalDataset:
        dataset = EvalDataset.model_validate_json(path.read_text(encoding="utf-8"))
        fallback_time = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        return dataset.model_copy(
            update={
                "created_at": dataset.created_at or fallback_time,
                "updated_at": dataset.updated_at or fallback_time,
            }
        )

    def _all(self) -> dict[str, list[EvalDataset]]:
        datasets: dict[str, list[EvalDataset]] = {}
        paths = []
        if self.builtin_dir.exists():
            paths.extend(sorted(self.builtin_dir.glob("*.json")))
        if self.user_dir.exists():
            paths.extend(sorted(self.user_dir.glob("**/*.json")))
        for path in paths:
            dataset = self._load(path)
            datasets.setdefault(dataset.id, []).append(dataset)
        return datasets

    def list(self) -> list[DatasetSummary]:
        summaries = []
        for dataset_id in sorted(self._all()):
            dataset = self.get(dataset_id)
            if dataset is not None:
                summaries.append(
                    DatasetSummary(
                        id=dataset.id,
                        name=dataset.name,
                        version=dataset.version,
                        suite_type=dataset.suite_type,
                        description=dataset.description,
                        revision=dataset.revision,
                        created_at=dataset.created_at,
                        updated_at=dataset.updated_at,
                        fingerprint=dataset_fingerprint(dataset),
                        case_count=len(dataset.cases),
                        metrics=sorted(
                            {metric.name for case in dataset.cases for metric in case.metrics},
                            key=str,
                        ),
                    )
                )
        return summaries

    def revisions(self, dataset_id: str) -> list[DatasetSummary]:
        datasets = sorted(
            self._all().get(dataset_id, []), key=lambda dataset: dataset.revision, reverse=True
        )
        return [
            DatasetSummary(
                id=dataset.id,
                name=dataset.name,
                version=dataset.version,
                suite_type=dataset.suite_type,
                description=dataset.description,
                revision=dataset.revision,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                fingerprint=dataset_fingerprint(dataset),
                case_count=len(dataset.cases),
                metrics=sorted(
                    {metric.name for case in dataset.cases for metric in case.metrics}, key=str
                ),
            )
            for dataset in datasets
        ]

    def get(self, dataset_id: str, revision: int | None = None) -> EvalDataset | None:
        datasets = self._all().get(dataset_id, [])
        if revision is not None:
            return next((dataset for dataset in datasets if dataset.revision == revision), None)
        return max(datasets, key=lambda dataset: dataset.revision, default=None)

    def save(self, dataset: EvalDataset) -> EvalDataset:
        now = datetime.now(UTC)
        previous = self.get(dataset.id)
        revision = previous.revision + 1 if previous else 1
        saved = dataset.model_copy(
            update={
                "revision": revision,
                "created_at": previous.created_at if previous else now,
                "updated_at": now,
            }
        )
        directory = self.user_dir / saved.id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"revision-{saved.revision}.json"
        path.write_text(saved.model_dump_json(indent=2), encoding="utf-8")
        return saved
