from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from evalpulse.agents import DemoFaqAgent
from evalpulse.config import settings
from evalpulse.datasets import DatasetStore, router as datasets_router
from evalpulse.engine import dataset_fingerprint, run_evaluation
from evalpulse.models import EvalDataset, EvalRun, RunRequest, SuiteType
from evalpulse.store import RunStore

app = FastAPI(
    title="EvalPulse API",
    description="Continuous, reproducible evaluations for AI agents.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_store = RunStore(settings.data_dir / "runs.jsonl")
app.state.dataset_store = DatasetStore(settings.dataset_dir, settings.data_dir / "datasets")
app.include_router(datasets_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": "EvalPulse API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/runs", response_model=list[EvalRun])
def list_runs() -> list[EvalRun]:
    return list(reversed(_store.list()))


@app.get("/api/runs/{run_id}", response_model=EvalRun)
def get_run(run_id: UUID) -> EvalRun:
    run = _store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


def resolve_dataset(request: RunRequest) -> EvalDataset:
    if request.dataset_id:
        dataset = app.state.dataset_store.get(request.dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset
    if request.cases:
        return EvalDataset(
            id="inline",
            name="Inline evaluation",
            version="adhoc",
            suite_type=SuiteType.CUSTOM,
            cases=request.cases,
        )
    dataset = app.state.dataset_store.get("qa-demo")
    if dataset is None:
        raise HTTPException(status_code=500, detail="Default dataset is unavailable")
    return dataset


@app.post("/api/runs", response_model=EvalRun, status_code=201)
async def create_run(request: RunRequest) -> EvalRun:
    agent = DemoFaqAgent()
    dataset = resolve_dataset(request)
    fingerprint = dataset_fingerprint(dataset)
    if request.baseline_run_id:
        baseline = _store.get(request.baseline_run_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline run not found")
        if baseline.dataset_hash != fingerprint:
            raise HTTPException(status_code=409, detail="Baseline dataset does not match")
    else:
        baseline = _store.latest(agent.name, fingerprint)
    run = await run_evaluation(agent, dataset, baseline)
    _store.append(run)
    return run
