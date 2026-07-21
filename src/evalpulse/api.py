from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from evalpulse.agents import DemoFaqAgent
from evalpulse.config import settings
from evalpulse.engine import dataset_fingerprint, run_evaluation
from evalpulse.models import EvalCase, EvalRun, MetricName, RunRequest
from evalpulse.store import RunStore

app = FastAPI(
    title="EvalPulse API",
    description="Continuous, reproducible evaluations for AI agents.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_store = RunStore(settings.data_dir / "runs.jsonl")
_demo_cases = [
    EvalCase(
        id="product-description",
        input="What is EvalPulse?",
        expected="EvalPulse evaluates AI agents continuously.",
    ),
    EvalCase(
        id="local-startup",
        input="How do I run it?",
        expected="Run docker compose up.",
    ),
    EvalCase(
        id="deployment-requirement",
        input="Does it need Kubernetes?",
        expected="Kubernetes is not required.",
        metric=MetricName.TOKEN_OVERLAP,
        threshold=0.75,
    ),
]


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


@app.post("/api/runs", response_model=EvalRun, status_code=201)
async def create_run(request: RunRequest) -> EvalRun:
    agent = DemoFaqAgent()
    cases = request.cases or _demo_cases
    if request.baseline_run_id:
        baseline = _store.get(request.baseline_run_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline run not found")
        if baseline.dataset_hash != dataset_fingerprint(cases):
            raise HTTPException(status_code=409, detail="Baseline dataset does not match")
    else:
        baseline = _store.latest(agent.name, dataset_fingerprint(cases))
    run = await run_evaluation(agent, cases, baseline)
    _store.append(run)
    return run
