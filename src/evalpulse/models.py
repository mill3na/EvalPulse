from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MetricName(StrEnum):
    EXACT_MATCH = "exact_match"
    TOKEN_OVERLAP = "token_overlap"


class EvalCase(BaseModel):
    id: str
    input: str
    expected: str
    metric: MetricName = MetricName.EXACT_MATCH
    threshold: float = Field(default=1.0, ge=0, le=1)


class AgentResponse(BaseModel):
    content: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)


class CaseResult(BaseModel):
    case_id: str
    input: str
    expected: str
    actual: str
    metric: MetricName
    score: float
    threshold: float
    passed: bool
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0


class RunComparison(BaseModel):
    baseline_run_id: UUID
    score_delta: float
    regressed_cases: list[str]
    improved_cases: list[str]


class EvalRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent: str
    dataset_hash: str = ""
    score: float
    passed: bool
    cases: list[CaseResult]
    total_latency_ms: float = 0
    total_tokens: int = 0
    total_cost_usd: float = 0
    comparison: RunComparison | None = None


class RunRequest(BaseModel):
    cases: list[EvalCase] | None = None
    baseline_run_id: UUID | None = None
