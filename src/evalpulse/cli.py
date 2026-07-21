import argparse
import asyncio
from pathlib import Path

from pydantic import TypeAdapter

from evalpulse.agents import DemoFaqAgent
from evalpulse.engine import run_evaluation
from evalpulse.models import EvalCase, EvalRun


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalpulse",
        description="Run a versioned evaluation dataset against the demo agent.",
    )
    parser.add_argument("dataset", type=Path, help="JSON file containing a list of eval cases")
    parser.add_argument("--baseline", type=Path, help="Previous EvalPulse report")
    parser.add_argument("--output", type=Path, default=Path("evalpulse-report.json"))
    return parser


def load_cases(path: Path) -> list[EvalCase]:
    return TypeAdapter(list[EvalCase]).validate_json(path.read_text(encoding="utf-8"))


def load_baseline(path: Path | None) -> EvalRun | None:
    if path is None:
        return None
    return EvalRun.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> None:
    args = build_parser().parse_args()
    run = asyncio.run(
        run_evaluation(DemoFaqAgent(), load_cases(args.dataset), load_baseline(args.baseline))
    )
    args.output.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    print(f"EvalPulse score: {run.score:.1%} | {'PASS' if run.passed else 'FAIL'}")
    if run.comparison:
        print(f"Baseline delta: {run.comparison.score_delta:+.1%}")
    if not run.passed or (run.comparison and run.comparison.regressed_cases):
        raise SystemExit(1)
