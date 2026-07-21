import hashlib
import json
from time import perf_counter

from evalpulse.agents import Agent
from evalpulse.metrics import exact_match, token_overlap
from evalpulse.models import CaseResult, EvalCase, EvalRun, MetricName, RunComparison


def score_answer(metric: MetricName, actual: str, expected: str) -> float:
    scorers = {
        MetricName.EXACT_MATCH: exact_match,
        MetricName.TOKEN_OVERLAP: token_overlap,
    }
    return scorers[metric](actual, expected)


def dataset_fingerprint(cases: list[EvalCase]) -> str:
    payload = [case.model_dump(mode="json") for case in cases]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


async def run_evaluation(
    agent: Agent, cases: list[EvalCase], baseline: EvalRun | None = None
) -> EvalRun:
    fingerprint = dataset_fingerprint(cases)
    if baseline is not None and baseline.dataset_hash != fingerprint:
        raise ValueError("Baseline dataset does not match the current evaluation dataset")
    results: list[CaseResult] = []
    for case in cases:
        started_at = perf_counter()
        response = await agent.answer(case.input)
        latency_ms = (perf_counter() - started_at) * 1000
        score = score_answer(case.metric, response.content, case.expected)
        results.append(
            CaseResult(
                case_id=case.id,
                input=case.input,
                expected=case.expected,
                actual=response.content,
                metric=case.metric,
                score=score,
                threshold=case.threshold,
                passed=score >= case.threshold,
                latency_ms=round(latency_ms, 3),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
            )
        )

    aggregate = sum(result.score for result in results) / len(results) if results else 0.0
    run = EvalRun(
        agent=agent.name,
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
        regressed = [
            item.case_id
            for item in results
            if item.case_id in baseline_scores and item.score < baseline_scores[item.case_id]
        ]
        improved = [
            item.case_id
            for item in results
            if item.case_id in baseline_scores and item.score > baseline_scores[item.case_id]
        ]
        run.comparison = RunComparison(
            baseline_run_id=baseline.id,
            score_delta=round(run.score - baseline.score, 4),
            regressed_cases=regressed,
            improved_cases=improved,
        )
    return run
