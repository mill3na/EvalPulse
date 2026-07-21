from fastapi import APIRouter, HTTPException, Request, status

from evalpulse.metrics import METRIC_CATALOG
from evalpulse.models import DatasetSummary, EvalDataset, MetricDefinition

router = APIRouter(prefix="/api", tags=["Datasets"])


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(request: Request) -> list[DatasetSummary]:
    return request.app.state.dataset_store.list()


@router.get("/datasets/{dataset_id}/revisions", response_model=list[DatasetSummary])
def list_dataset_revisions(dataset_id: str, request: Request) -> list[DatasetSummary]:
    revisions = request.app.state.dataset_store.revisions(dataset_id)
    if not revisions:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return revisions


@router.get("/datasets/{dataset_id}/revisions/{revision}", response_model=EvalDataset)
def get_dataset_revision(dataset_id: str, revision: int, request: Request) -> EvalDataset:
    dataset = request.app.state.dataset_store.get(dataset_id, revision)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset revision not found")
    return dataset


@router.get("/datasets/{dataset_id}", response_model=EvalDataset)
def get_dataset(dataset_id: str, request: Request) -> EvalDataset:
    dataset = request.app.state.dataset_store.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.post("/datasets", response_model=EvalDataset, status_code=status.HTTP_201_CREATED)
def save_dataset(dataset: EvalDataset, request: Request) -> EvalDataset:
    return request.app.state.dataset_store.save(dataset)


@router.get("/metrics", response_model=list[MetricDefinition])
def list_metrics() -> list[MetricDefinition]:
    return METRIC_CATALOG
