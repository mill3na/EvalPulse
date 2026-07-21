# EvalPulse

Continuous, reproducible evaluations for AI agents.

EvalPulse answers one practical question: **did this agent get better or worse?**
It runs versionable test cases, records deterministic scores and latency, persists
the results, and compares each execution with its baseline.

## What is included

- FastAPI evaluation API with OpenAPI documentation
- Streamlit dashboard with run history, quality trend and case drill-down
- QA, RAG, security and custom evaluation suites
- Seven deterministic metrics with multiple metrics per case
- Per-metric thresholds and aggregate pass/fail status
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

Choose one of the bundled QA, RAG or security datasets and click
**Run selected dataset**. You can also import your own JSON dataset from the
**Datasets** tab. The first run becomes the baseline; later compatible runs are
compared automatically.

## API example

List the available datasets and metrics:

```bash
curl http://localhost:8000/api/datasets
curl http://localhost:8000/api/metrics
```

Start a run with a selected dataset:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"rag-demo"}'
```

Create or replace a validated dataset:

```bash
curl -X POST http://localhost:8000/api/datasets \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "my-rag-suite",
    "name": "My RAG suite",
    "version": "1.0.0",
    "suite_type": "rag",
    "cases": [{
      "id": "policy-001",
      "input": "What is the return window?",
      "expected": "Returns are allowed within 30 days.",
      "contexts": ["Returns are allowed within 30 days after purchase."],
      "expected_sources": ["returns-policy.md"],
      "metrics": [
        {"name": "faithfulness", "threshold": 0.6},
        {"name": "context_recall", "threshold": 1.0},
        {"name": "source_citation", "threshold": 1.0}
      ]
    }]
  }'
```

Available metrics:

| Metric | Typical suite | Purpose |
|---|---|---|
| `exact_match` | QA | Normalized answer equality |
| `token_overlap` | QA/RAG | Expected-token recall in the answer |
| `faithfulness` | RAG | Answer content supported by context |
| `context_recall` | RAG | Expected answer covered by retrieved context |
| `source_citation` | RAG | Expected sources cited in the answer |
| `refusal` | Security | Explicit refusal of an unsafe request |
| `forbidden_pattern_absence` | Security | No configured sensitive pattern leaked |

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
   │                    └── QA / RAG / security metric registry
   ▼
JSONL run store on Docker volume
```

```text
src/evalpulse/
├── agents.py       # agent protocol and deterministic demo adapter
├── engine.py       # evaluation and baseline comparison
├── metrics.py      # generic metric registry and deterministic scorers
├── models.py       # API and evaluation contracts
├── store.py        # append-only local persistence
├── datasets/       # dataset catalog service and routes
├── api.py          # run endpoints and application assembly
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
evalpulse datasets/qa-demo.json --output evalpulse-report.json
```

The generated report contains the complete run contract and can be uploaded as a
CI artifact. A failed threshold or case regression exits with status `1`.

## Roadmap

- Provider adapters with real token/cost capture
- Configurable regression tolerance and CI quality gate
- Semantic, rubric-based and LLM-as-judge metrics with judge metadata
- Exportable HTML/JSON reports

Kubernetes is intentionally outside the initial scope. The project should remain
fully demonstrable with one local command before adding deployment complexity.
