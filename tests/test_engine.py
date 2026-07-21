import pytest

from evalpulse.agents import DemoFaqAgent
from evalpulse.engine import run_evaluation
from evalpulse.models import AgentResponse, EvalCase


class MeteredAgent:
    name = "metered-agent"

    async def answer(self, prompt: str) -> AgentResponse:
        return AgentResponse(content=prompt, input_tokens=2, output_tokens=3, cost_usd=0.001)


@pytest.mark.asyncio
async def test_run_evaluation_reports_pass_and_score() -> None:
    cases = [
        EvalCase(
            id="description",
            input="What is EvalPulse?",
            expected="EvalPulse evaluates AI agents continuously.",
        )
    ]

    run = await run_evaluation(DemoFaqAgent(), cases)

    assert run.passed is True
    assert run.score == 1.0
    assert run.cases[0].passed is True


@pytest.mark.asyncio
async def test_run_aggregates_usage_and_cost() -> None:
    cases = [EvalCase(id="usage", input="same", expected="same")]

    run = await run_evaluation(MeteredAgent(), cases)

    assert run.total_tokens == 5
    assert run.total_cost_usd == 0.001
    assert run.total_latency_ms >= 0


@pytest.mark.asyncio
async def test_incompatible_baseline_is_rejected() -> None:
    baseline = await run_evaluation(
        DemoFaqAgent(),
        [EvalCase(id="first", input="What is EvalPulse?", expected="wrong")],
    )

    with pytest.raises(ValueError, match="Baseline dataset"):
        await run_evaluation(
            DemoFaqAgent(),
            [EvalCase(id="second", input="What is EvalPulse?", expected="wrong")],
            baseline,
        )
