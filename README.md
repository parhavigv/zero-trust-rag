# Zero-Trust RAG: Enterprise Data Governance via Pre-Retrieval RBAC

A research prototype that implements and **experimentally measures** whether
moving authorization from *after* retrieval (retrieve-then-filter) to *before*
retrieval (pre-retrieval RBAC) reduces unauthorized information exposure in an
enterprise RAG system — and what that costs in retrieval quality, answer
quality, and latency.

The system is built as three explicit, comparable configurations:

- **A — Baseline RAG**: retrieve over the whole corpus, no authorization.
- **B — Retrieve-then-filter**: retrieve over the whole corpus, then drop
  chunks the user is not allowed to see.
- **C — Zero-Trust pre-retrieval RBAC**: authorize the document candidate set
  *first*; the semantic retriever only ever searches authorized documents, so
  unauthorized content cannot enter the retrieval results or LLM context.

> **Academic positioning (no novelty claim).** Prior literature already covers
> RAG privacy, enterprise access control, permission-aware RAG, and
> authorization-first retrieval. The gap this project investigates is narrower:
> *a unified Zero-Trust enterprise RAG architecture that operationalizes
> pre-retrieval RBAC, least-privilege enforcement, continuous authorization,
> auditability, and measurable security–retrieval-performance trade-offs.*
> What is ours is the integrated experimental comparison of B vs C on one code
> base with one synthetic corpus, an oracle-labeled query set, and defined
> security/retrieval/generation/latency/auditability metrics.

---

## Research question

**Primary.** How can pre-retrieval RBAC based on Zero-Trust principles prevent
unauthorized enterprise information from entering the RAG retrieval and LLM
context pipeline?

**Secondary.**
1. Does pre-retrieval RBAC reduce unauthorized retrieval?
2. How does it compare with retrieve-then-filter?
3. What latency overhead does authorization introduce?
4. Does authorization reduce retrieval precision/recall?
5. Does the approach reduce sensitive-information leakage?
6. Can every authorization decision be audited?
7. How does RBAC compare with a more fine-grained policy mechanism?

## Hypotheses

| ID | Hypothesis |
|----|------------|
| H1 | Pre-retrieval RBAC reduces unauthorized context exposure vs. baseline RAG. |
| H2 | Pre-retrieval RBAC reduces unauthorized retrieval vs. retrieve-then-filter. |
| H3 | Pre-retrieval authorization introduces measurable latency overhead. |
| H4 | Correctly configured authorization metadata keeps retrieval quality acceptable. |
| H5 | Zero-Trust auditing improves traceability of authorization decisions. |

The final report will **let the evidence decide** — the proposed architecture
is not assumed to win.

## Architecture (summary)

Identity → role → RBAC policy engine → **authorized candidate set** →
semantic retrieval → secure context construction → LLM → audit log.

```
 User
   │  identity (user_id, role, department, tenant_id)
   ▼
 RBAC Policy Engine ── deny-by-default, continuous/authz-per-query
   │   authorized_docs = { d ∈ corpus : policy.allow(user, d.metadata) }
   ▼
 Authorized Candidate Set   ←  the retriever is scoped to THIS set only
   ▼
 Semantic Retrieval (dense FAISS, top-k)
   ▼
 Secure Context Construction
   ▼
 LLM → Response
   ▼
 Audit Log (every decision, reconstructable)
```

## Repository layout

```
zero-trust-rag/
├── backend/                 # re-usable python package
│   ├── api/                 # FastAPI routes (query, admin)
│   ├── auth/                # identity verification (users, tokens)
│   ├── rbac/                # policy engine + policy data
│   ├── retrieval/           # embeddings, FAISS index, scoped search
│   ├── generation/          # LLM provider abstraction (+ stub for tests)
│   ├── audit/               # authorization audit store + trail
│   └── evaluation/          # metric implementations
├── data/
│   ├── documents/           # synthetic corpus (text + metadata)
│   ├── users/               # user/role seed data
│   └── policies/            # RBAC policy definitions
├── experiments/             # one runner per configuration
│   ├── baseline/
│   ├── retrieve_then_filter/
│   └── pre_retrieval_rbac/
├── evaluation/              # query set (oracle-labeled), metric aggregation
├── results/                 # generated tables + figures
├── tests/                   # unit + security case suites
├── docs/                    # architecture, data model, RBAC, experiments, metrics
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m backend.scripts.build_corpus    # Phase 2: generate synthetic corpus
python -m backend.scripts.build_index     # embed + index the corpus
python -m pytest tests/ -q                 # run unit + security suites
python -m experiments.run_all             # run A, B, C; write results/
python -m evaluation.aggregate            # tables + figures
uvicorn backend.api.app:app --reload      # optional interactive API
```

## Experimental configurations (independent variable = *where authorization sits*)

| Config | Pipeline | Unauthorized doc can enter retrieval? |
|--------|----------|--------------------------------------|
| A baseline | retrieve → LLM | yes (always) |
| B retrieve-then-filter | retrieve (all) → RBAC filter → LLM | yes (retrieved, then dropped) |
| C pre-retrieval RBAC | RBAC scope → retrieve (authorized only) → LLM | **no** |

All three share: corpus, embeddings, index, retriever, `k`, query set, LLM
provider. Only the authorization placement differs — so observed differences
are attributable to authorization placement, not to the retriever.

## Status (phases)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | Architecture + README + models + experiment & metric design | ✅ |
| 2 | Synthetic corpus + oracle-labeled query set | ✅ 42 docs, 9 users, 26 queries |
| 3 | Users, roles, permissions, RBAC engine (deny-by-default) | ✅ |
| 4 | Baseline RAG (A) | ✅ |
| 5 | Retrieve-then-filter (B) | ✅ |
| 6 | Pre-retrieval RBAC (C) | ✅ |
| 7 | Audit logging | ✅ SQLite store, 1352 decisions |
| 8 | Security test cases | ✅ 36 tests passing |
| 9 | Evaluation metrics | ✅ 24 metrics implemented |
| 10 | Run experiments | ✅ 26 queries × 3 configs |
| 11 | Comparison tables + figures | ✅ `results/comparison.md` + 4 charts |
| 12 | Findings, limitations, future work | ✅ `docs/findings.md` |

## Headline measured result

On the seeded synthetic corpus, unauthorized content in the LLM context dropped
from **0.646 → 0.000** (S1) and unauthorized docs in candidate lists from
**84/178 → 0** (S3) when moving from baseline / retrieve-then-filter to
pre-retrieval RBAC, at a measured authorization cost of ~0.86 ms/query.
Retrieval quality was not degraded (recall equal, ranking metrics slightly
better under C). All numbers are artifacts of this repository — see
`docs/findings.md` and `results/comparison.md`.

## Integrity & reporting rules

- No fabricated citations, results, datasets, or claims.
- Until experiments actually run, the report states **"Not yet evaluated."**
- Claims are clearly separated into: *literature-supported*,
  *system implementation*, *experimental results*, *researcher interpretation*.
- Implementation decisions not grounded in literature are flagged as
  **engineering design choices**.

See `docs/` for the architecture, data model, RBAC policy model, experiment
design, evaluation metrics, and security threat model.