from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SuiteType(StrEnum):
    QA = "qa"
    RAG = "rag"
    SECURITY = "security"
    CUSTOM = "custom"


class MetricName(StrEnum):
    EXACT_MATCH = "exact_match"
    TOKEN_OVERLAP = "token_overlap"
    FAITHFULNESS = "faithfulness"
    CONTEXT_RECALL = "context_recall"
    SOURCE_CITATION = "source_citation"
    REFUSAL = "refusal"
    FORBIDDEN_PATTERN_ABSENCE = "forbidden_pattern_absence"


class MetricConfig(BaseModel):
    name: MetricName
    threshold: float = Field(default=1.0, ge=0, le=1)


class EvalCase(BaseModel):
    id: str = Field(min_length=1)
    input: str = Field(min_length=1)
    expected: str = ""
    contexts: list[str] = Field(default_factory=list)
    expected_sources: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    metrics: list[MetricConfig] = Field(default_factory=list)
    # Legacy single-metric fields remain accepted for existing API clients.
    metric: MetricName | None = None
    threshold: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def ensure_metrics(self) -> "EvalCase":
        if not self.metrics:
            self.metrics = [
                MetricConfig(name=self.metric or MetricName.EXACT_MATCH, threshold=self.threshold)
            ]
        return self


class EvalDataset(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    suite_type: SuiteType
    description: str = ""
    revision: int = Field(default=1, ge=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_suite(self) -> "EvalDataset":
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case ids must be unique within a dataset")

        suite_metrics = {
            SuiteType.QA: {
                MetricName.EXACT_MATCH,
                MetricName.TOKEN_OVERLAP,
            },
            SuiteType.RAG: {
                MetricName.TOKEN_OVERLAP,
                MetricName.FAITHFULNESS,
                MetricName.CONTEXT_RECALL,
                MetricName.SOURCE_CITATION,
            },
            SuiteType.SECURITY: {
                MetricName.REFUSAL,
                MetricName.FORBIDDEN_PATTERN_ABSENCE,
            },
            SuiteType.CUSTOM: set(MetricName),
        }
        requirements = {
            MetricName.EXACT_MATCH: "expected",
            MetricName.TOKEN_OVERLAP: "expected",
            MetricName.FAITHFULNESS: "contexts",
            MetricName.CONTEXT_RECALL: "contexts",
            MetricName.SOURCE_CITATION: "expected_sources",
            MetricName.FORBIDDEN_PATTERN_ABSENCE: "forbidden_patterns",
        }
        for case in self.cases:
            for metric in case.metrics:
                if metric.name not in suite_metrics[self.suite_type]:
                    raise ValueError(
                        f"metric {metric.name.value} is not valid for {self.suite_type.value} suites"
                    )
                required_field = requirements.get(metric.name)
                if required_field and not getattr(case, required_field):
                    raise ValueError(
                        f"case {case.id} requires {required_field} for {metric.name.value}"
                    )
        return self


class DatasetSummary(BaseModel):
    id: str
    name: str
    version: str
    suite_type: SuiteType
    description: str
    revision: int
    created_at: datetime
    updated_at: datetime
    fingerprint: str
    case_count: int
    metrics: list[MetricName]


class AgentResponse(BaseModel):
    content: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)


class AgentSummary(BaseModel):
    id: str
    name: str
    description: str
    provider: str
    model: str


class MetricResult(BaseModel):
    name: MetricName
    score: float
    threshold: float
    passed: bool
    reason: str = ""


class CaseResult(BaseModel):
    case_id: str
    input: str
    expected: str
    actual: str
    metric: MetricName | None = None
    score: float
    threshold: float = 1.0
    passed: bool
    metrics: list[MetricResult] = Field(default_factory=list)
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
    dataset_id: str = "inline"
    dataset_version: str = "legacy"
    dataset_revision: int = 1
    suite_type: SuiteType = SuiteType.QA
    dataset_hash: str = ""
    score: float
    passed: bool
    cases: list[CaseResult]
    total_latency_ms: float = 0
    total_tokens: int = 0
    total_cost_usd: float = 0
    comparison: RunComparison | None = None


class RunRequest(BaseModel):
    agent_id: str = "demo-faq-agent"
    dataset_id: str | None = None
    dataset_revision: int | None = Field(default=None, ge=1)
    cases: list[EvalCase] | None = None
    baseline_run_id: UUID | None = None


class MetricDefinition(BaseModel):
    name: MetricName
    suites: list[SuiteType]
    description: str
    requires: list[str] = Field(default_factory=list)
