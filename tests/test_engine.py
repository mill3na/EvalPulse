from pathlib import Path

import pytest

from evalpulse.agents import DemoFaqAgent
from evalpulse.cli import load_dataset
from evalpulse.engine import run_evaluation
from evalpulse.models import AgentResponse, EvalCase, EvalDataset, SuiteType


class MeteredAgent:
    name = "metered-agent"

    async def answer(self, prompt: str) -> AgentResponse:
        return AgentResponse(content=prompt, input_tokens=2, output_tokens=3, cost_usd=0.001)


def inline_dataset(case: EvalCase, dataset_id: str = "test") -> EvalDataset:
    return EvalDataset(
        id=dataset_id,
        name="Test dataset",
        version="1.0.0",
        suite_type=SuiteType.CUSTOM,
        cases=[case],
    )


@pytest.mark.asyncio
async def test_all_demo_suites_pass() -> None:
    for path in Path("datasets").glob("*.json"):
        run = await run_evaluation(DemoFaqAgent(), load_dataset(path))
        assert run.passed is True, path


@pytest.mark.asyncio
async def test_run_aggregates_usage_and_cost() -> None:
    dataset = inline_dataset(EvalCase(id="usage", input="same", expected="same"))

    run = await run_evaluation(MeteredAgent(), dataset)

    assert run.total_tokens == 5
    assert run.total_cost_usd == 0.001
    assert run.total_latency_ms >= 0


@pytest.mark.asyncio
async def test_incompatible_baseline_is_rejected() -> None:
    baseline = await run_evaluation(
        DemoFaqAgent(),
        inline_dataset(EvalCase(id="first", input="What is EvalPulse?", expected="wrong"), "first"),
    )

    with pytest.raises(ValueError, match="Baseline dataset"):
        await run_evaluation(
            DemoFaqAgent(),
            inline_dataset(
                EvalCase(id="second", input="What is EvalPulse?", expected="wrong"), "second"
            ),
            baseline,
        )
