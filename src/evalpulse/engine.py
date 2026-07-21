import hashlib
import json
from time import perf_counter

from evalpulse.agents import Agent
from evalpulse.metrics import score_metric
from evalpulse.models import (
    CaseResult,
    EvalDataset,
    EvalRun,
    MetricResult,
    RunComparison,
)


def dataset_fingerprint(dataset: EvalDataset) -> str:
    encoded = json.dumps(
        dataset.model_dump(mode="json", exclude={"revision", "created_at", "updated_at"}),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


async def run_evaluation(
    agent: Agent, dataset: EvalDataset, baseline: EvalRun | None = None
) -> EvalRun:
    fingerprint = dataset_fingerprint(dataset)
    if baseline is not None and baseline.dataset_hash != fingerprint:
        raise ValueError("Baseline dataset does not match the current evaluation dataset")

    results: list[CaseResult] = []
    for case in dataset.cases:
        started_at = perf_counter()
        response = await agent.answer(case.input)
        latency_ms = (perf_counter() - started_at) * 1000
        metric_results = []
        for metric in case.metrics:
            score, reason = score_metric(metric.name, response.content, case)
            metric_results.append(
                MetricResult(
                    name=metric.name,
                    score=score,
                    threshold=metric.threshold,
                    passed=score >= metric.threshold,
                    reason=reason,
                )
            )
        case_score = sum(metric.score for metric in metric_results) / len(metric_results)
        results.append(
            CaseResult(
                case_id=case.id,
                input=case.input,
                expected=case.expected,
                actual=response.content,
                metric=metric_results[0].name,
                score=round(case_score, 4),
                threshold=metric_results[0].threshold,
                passed=all(metric.passed for metric in metric_results),
                metrics=metric_results,
                latency_ms=round(latency_ms, 3),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
            )
        )

    aggregate = sum(result.score for result in results) / len(results) if results else 0.0
    run = EvalRun(
        agent=agent.name,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        dataset_revision=dataset.revision,
        suite_type=dataset.suite_type,
        dataset_hash=fingerprint,
        score=round(aggregate, 4),
        passed=bool(results) and all(result.passed for result in results),
        cases=results,
        total_latency_ms=round(sum(result.latency_ms for result in results), 3),
        total_tokens=sum(result.input_tokens + result.output_tokens for result in results),
        total_cost_usd=round(sum(result.cost_usd for result in results), 8),
    )
    if baseline is not None:
        baseline_scores = {item.case_id: item.score for item in baseline.cases}
        run.comparison = RunComparison(
            baseline_run_id=baseline.id,
            score_delta=round(run.score - baseline.score, 4),
            regressed_cases=[
                item.case_id
                for item in results
                if item.case_id in baseline_scores and item.score < baseline_scores[item.case_id]
            ],
            improved_cases=[
                item.case_id
                for item in results
                if item.case_id in baseline_scores and item.score > baseline_scores[item.case_id]
            ],
        )
    return run
