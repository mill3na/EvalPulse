# EvalPulse

Continuous, reproducible evaluations for AI agents.

EvalPulse answers one practical question: **did this agent get better or worse?**
It runs versionable test cases, records deterministic scores and latency, persists
the results, and compares each execution with its baseline.

## What is included

- FastAPI evaluation API with OpenAPI documentation
- Streamlit dashboard with run history, quality trend and case drill-down
- Exact-match and token-overlap metrics
- Per-case thresholds and aggregate pass/fail status
- Latency, token and USD cost contracts ready for real provider adapters
- Automatic comparison with the previous run
- Dataset fingerprints that prevent invalid baseline comparisons
- Regression and improvement detection by case
- Append-only JSONL persistence in a Docker volume
- Deterministic FAQ agent for a zero-cost local demo
- Docker Compose, health checks, tests, lint and GitHub Actions CI
- Versioned dataset and a CLI quality gate that returns a non-zero exit code on failure

## Quick start

Requirements: Docker with Compose.

```bash
docker compose up --build
```

Then open:

- Dashboard: [http://localhost:8501](http://localhost:8501)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

Click **Run demo evaluation**. The first run becomes the baseline; later runs are
compared automatically.

## API example

Start a run with the built-in dataset:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Or provide versioned cases from your own dataset:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "cases": [{
      "id": "description",
      "input": "What is EvalPulse?",
      "expected": "EvalPulse evaluates AI agents continuously.",
      "metric": "exact_match",
      "threshold": 1
    }]
  }'
```

Pass `baseline_run_id` to compare against a specific run. When omitted, EvalPulse
uses the most recent run of the same agent.

## Architecture

```text
Browser
   │
   ▼
Streamlit dashboard :8501
   │ HTTP
   ▼
FastAPI :8000 ──► evaluation engine ──► agent adapter
   │                    │
   │                    └── exact match / token overlap
   ▼
JSONL run store on Docker volume
```

```text
src/evalpulse/
├── agents.py       # agent protocol and deterministic demo adapter
├── engine.py       # evaluation and baseline comparison
├── metrics.py      # deterministic scorers
├── models.py       # API and evaluation contracts
├── store.py        # append-only local persistence
├── api.py          # FastAPI endpoints
└── dashboard.py    # Streamlit interface
```

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn evalpulse.api:app --reload
```

In another terminal:

```bash
EVALPULSE_API_URL=http://localhost:8000 streamlit run src/evalpulse/dashboard.py
```

Run the checks:

```bash
ruff check .
pytest --cov=evalpulse
```

Run the same quality gate used by CI:

```bash
evalpulse datasets/demo.json --output evalpulse-report.json
```

The generated report contains the complete run contract and can be uploaded as a
CI artifact. A failed threshold or case regression exits with status `1`.

## Roadmap

- Provider adapters and token/cost capture
- Configurable regression tolerance and CI quality gate
- Rubric-based and LLM-as-judge metrics with judge metadata
- Exportable HTML/JSON reports

Kubernetes is intentionally outside the initial scope. The project should remain
fully demonstrable with one local command before adding deployment complexity.
