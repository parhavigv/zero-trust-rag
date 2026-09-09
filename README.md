# Zero-Trust RAG

Enterprise RAG authorization engine. Pre-retrieval RBAC + ABAC policy enforcement that prevents unauthorized documents from ever reaching the retriever or LLM context.

```
Zero-Trust RAG vs Traditional RAG

Traditional (retrieve-then-filter):
  Query → Search ALL docs → Filter unauthorized → LLM
                              ↑ exposed in candidates

Zero-Trust (pre-retrieval):
  Query → Authorize user → Search AUTHORIZED docs only → LLM
                            ↑ never sees unauthorized content
```

## Features

- **Pre-retrieval authorization** — RBAC policy engine computes the authorized document set before any embedding search runs. Unauthorized content is structurally excluded.
- **RBAC + ABAC hybrid** — Role-based grants gated by attribute predicates: sensitivity ceiling, business-unit clearance, user clearance level, time-window constraints.
- **Three comparable configurations** — Baseline (A), retrieve-then-filter (B), and pre-retrieval RBAC (C) sharing identical corpus, embeddings, and retriever. Differences are attributable to authorization placement.
- **Full audit trail** — Every authorization decision (allow/deny) is logged with subject, role, document, rule, reason, and timestamp. Append-only SQLite store.
- **Deterministic & reproducible** — Seeded corpus generation, real embeddings (sentence-transformers), FAISS index. All experiment artifacts stored as JSON for full reproducibility.
- **24 metrics** — Security (S1–S8), retrieval quality (R1–R4), generation quality (G1–G4), performance (P1–P4), auditability (U1–U3).

## Quick Start

```bash
# Clone
git clone https://github.com/parhavigv/zero-trust-rag.git
cd zero-trust-rag

# Setup
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Generate corpus & index
python -m backend.scripts.build_corpus    # 42 docs, 9 users, 34 queries
python -m backend.scripts.build_index     # embed + FAISS index

# Run tests
python -m pytest tests -q                 # 47 tests

# Run experiments
python -m experiments.run_all             # A, B, C configs (RBAC policy)
python -m experiments.run_all --policy abac  # ABAC hybrid variant
python -m evaluation.aggregate            # results/comparison.md + abac_comparison.md
```

## Architecture

```
                    ┌──────────────┐
                    │   User       │
                    │ (id, role,   │
                    │  dept, tenant)│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  RBAC / ABAC │  ← deny-by-default, evaluated per query
                    │  Policy      │
                    │  Engine      │
                    └──────┬───────┘
                           │ authorized document IDs
                    ┌──────▼───────┐
                    │  Scoped      │  ← FAISS search over authorized subset only
                    │  Retriever   │
                    └──────┬───────┘
                           │ top-k authorized chunks
                    ┌──────▼───────┐
                    │  Context     │
                    │  Builder     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  LLM         │
                    │  Provider    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Audit Log   │  ← append-only, every decision traced
                    └──────────────┘
```

## Configurations

| Config | Authorization | Unauthorized doc in retrieval? |
|--------|:---:|:---:|
| **A** — Baseline | None | Yes |
| **B** — Retrieve-then-filter | Post-retrieval filter | Yes (retrieved, then dropped) |
| **C** — Pre-retrieval RBAC | Pre-retrieval scope | **No** |

All three share: corpus, embeddings, index, retriever, `k`, query set, provider. Only the authorization placement differs.

## Project Structure

```
zero-trust-rag/
├── backend/
│   ├── api/                    # API routes (planned)
│   ├── auth/                   # Identity verification
│   ├── rbac/                   # Policy engine + attribute predicates
│   ├── retrieval/              # Embeddings, FAISS index, scoped search
│   ├── generation/             # LLM provider abstraction
│   ├── audit/                  # Authorization audit store
│   ├── evaluation/             # Metric implementations
│   └── scripts/                # Corpus & index builders
├── data/
│   ├── documents/              # Synthetic corpus (text + metadata)
│   ├── users/                  # User/role seed data
│   ├── queries/                # Oracle-labeled evaluation queries
│   └── policies/               # RBAC + ABAC policy definitions
├── experiments/                # Configuration runners (A, B, C)
├── evaluation/                 # Metric aggregation + reporting
├── tests/                      # Unit + security test suites
├── docs/                       # Architecture, data model, authorization, metrics
└── results/                    # Generated tables + run records
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZTRUST_SEED` | `20260908` | Random seed for reproducible corpus generation |
| `ZTRUST_TOP_K` | `5` | Number of chunks returned by the retriever |
| `ZTRUST_K_CAND` | `10` | Candidate pool size for retrieve-then-filter (config B) |
| `ZTRUST_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `ZTRUST_DATA` | `./data` | Data directory path |
| `ZTRUST_RESULTS` | `./results` | Results output directory |

### Policy Files

| File | Description |
|------|-------------|
| `data/policies/policies.json` | RBAC policy — role/classification matrix, overrides |
| `data/policies/policies_abac.json` | ABAC hybrid policy — adds attribute predicates to RBAC grants |

## Benchmarks

Measured on the synthetic corpus (42 docs, 9 users, 34 queries):

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| Unauthorized in context (S1) | **0.671** | 0.000 | **0.000** |
| Unauthorized in candidates (S3) | 114 | **242** | **0** |
| Denial correctness (S6) | 0.00 | 1.00 | **1.00** |
| Recall@k (R1) | 1.00 | 1.00 | 1.00 |
| Authorization latency (P2) | 0.00 ms | 0.25 ms | 0.78 ms |
| End-to-end latency (P1) | 19.0 ms | 18.5 ms | 19.1 ms |

Full results: [`results/comparison.md`](results/comparison.md), [`results/abac_comparison.md`](results/abac_comparison.md)

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/architecture.md) | System pipeline, configuration design, module responsibilities |
| [Data Model](docs/data-model.md) | Document, User, Query schemas and conventions |
| [Authorization](docs/authorization.md) | RBAC + ABAC policy model, rule ordering, Zero-Trust mapping |
| [Benchmarking](docs/benchmarking.md) | Experiment design, A/B/C configurations, threat model |
| [Metrics](docs/metrics.md) | 24-metric evaluation framework (security, retrieval, performance) |
| [Results](docs/results.md) | Measured outcomes, ABAC ablation, limitations |
| [Configuration](docs/configuration.md) | Environment variables, policy config reference |

## License

Research prototype — see repository for details.
