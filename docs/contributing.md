# Contributing

Development setup, conventions, and workflow for the Zero-Trust RAG project.

## Development Setup

```bash
git clone https://github.com/parhavigv/zero-trust-rag.git
cd zero-trust-rag
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m backend.scripts.build_corpus
python -m backend.scripts.build_index
```

## Running Tests

```bash
python -m pytest tests -q              # all tests (47)
python -m pytest tests/test_abac.py    # ABAC predicate tests only
python -m pytest tests/test_rbac.py    # RBAC engine tests only
python -m pytest tests/test_audit.py   # Audit store tests only
```

## Code Conventions

- **Python 3.10+** with `from __future__ import annotations`.
- **Type hints** on all public functions. Use `dataclass(frozen=True)` for data models.
- **No comments** unless explicitly requested.
- **Deny-by-default** for authorization logic — when in doubt, deny.
- **Seeded determinism** — all generation uses `ZTRUST_SEED` for reproducibility.
- **JSON for data** — policies, users, documents, queries are plain JSON. Diffable, inspectable.

## Project Layout

```
backend/
├── rbac/           # Policy engine — the core authorization logic
├── retrieval/      # Embeddings + FAISS index
├── generation/     # LLM provider abstraction
├── audit/          # SQLite audit store
├── evaluation/     # Metric implementations
├── scripts/        # Corpus & index builders
├── auth/           # Identity verification (stub)
├── models.py       # User, Document, Decision dataclasses
└── config.py       # Path configuration, env vars

experiments/        # One runner per configuration (A, B, C)
evaluation/         # Metric aggregation + reporting
data/               # Corpus, users, queries, policies
tests/              # Unit + security test suites
docs/               # Architecture, data model, authorization, metrics, results
```

## Adding a New Configuration

1. Create `experiments/<name>/run.py` with a `run()` function matching the signature of existing runners.
2. Register it in `experiments/run_all.py` under `RUNNERS`.
3. Add test cases in `tests/`.
4. Run `python -m experiments.run_all --configs <NAME>` to validate.

## Adding Metrics

1. Implement the metric function in `backend/evaluation/metrics.py`.
2. Add it to the `query_metrics()` return dict.
3. Add it to `aggregate()` in `backend/evaluation/metrics.py`.
4. Add a `table_row()` call in `evaluation/aggregate.py`.

## Data Integrity Rules

- No fabricated results. All numbers come from `results/runs/` or `results/runs_abac/`.
- Run records are JSON artifacts of the experiment runners — not hand-written.
- Generation metrics are explicitly marked "extractive baseline" until a real LLM provider is used.
- Policy changes go through `data/policies/*.json` — no hardcoded permissions.
