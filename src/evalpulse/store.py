import json
from pathlib import Path
from threading import Lock
from uuid import UUID

from evalpulse.models import EvalRun


class RunStore:
    """Append-only JSONL store suitable for the local single-process MVP."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[EvalRun]:
        if not self.path.exists():
            return []
        with self._lock, self.path.open(encoding="utf-8") as source:
            return [EvalRun.model_validate_json(line) for line in source if line.strip()]

    def get(self, run_id: UUID) -> EvalRun | None:
        return next((run for run in self.list() if run.id == run_id), None)

    def latest(self, agent: str, dataset_hash: str) -> EvalRun | None:
        return next(
            (
                run
                for run in reversed(self.list())
                if run.agent == agent and run.dataset_hash == dataset_hash
            ),
            None,
        )

    def append(self, run: EvalRun) -> None:
        payload = json.dumps(run.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as destination:
            destination.write(f"{payload}\n")
