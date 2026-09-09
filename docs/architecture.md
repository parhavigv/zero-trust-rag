# Architecture

System pipeline, configuration design, and module responsibilities for the Zero-Trust RAG engine.

## Pipeline

```
User (id, role, dept, tenant)
  │
  ▼
Identity Resolution ── user lookup + enabled check
  │
  ▼
RBAC / ABAC Policy Engine ── deny-by-default, evaluated per query
  │   authorized_docs = { d ∈ corpus : policy.allow(user, d) }
  │
  ▼
Authorized Candidate Set  ←  retriever is scoped to THIS set only
  │
  ▼
Semantic Retrieval (dense FAISS, top-k)
  │
  ▼
Context Builder
  │
  ▼
LLM Provider
  │
  ▼
Response
  │
  ▼
Audit Log (every decision, reconstructable)
```

## Configurations

### Config A — Baseline RAG

```
query → retriever(all corpus, top-k) → context → LLM → answer
```

No authorization. All chunks from any department/tenant are retrievable and enter context. Serves as the upper-bound exposure / upper-bound quality reference.

### Config B — Retrieve-then-filter

```
query → retriever(all corpus, top-k_cand) → RBAC filter → authorized k → LLM
```

Retriever searches all documents; authorization happens after ranking. Unauthorized documents are retrieved (they appear in the candidate ranking) and then dropped. To keep `k` comparable, the runner retrieves `k_cand >= k` and keeps the first `k` allowed chunks.

### Config C — Pre-retrieval RBAC (Zero-Trust)

```
query → RBAC engine → authorized_ids → scoped retriever(top-k) → LLM → answer → audit
```

Authorization happens before any embedding lookup. The `authorized_ids` computation produces a document set that the retriever is scoped to. Unauthorized documents never enter the candidate ranking or the search results.

**Contract:** the scoped FAISS search builds a temporary index over exactly the authorized subset. This is not "search-all-then-hide" — unauthorized vectors are never added to the search index.

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `backend/auth` | Identity verification: resolve user from token/lookup, derive role + department + tenant context |
| `backend/rbac` | Policy evaluation: `allow(user, doc, policy)` → `Decision`. Deny-by-default rule ordering. ABAC attribute predicates via `attr_predicates.py` |
| `backend/retrieval` | Embedding (sentence-transformers), FAISS index, scoped search over authorized subset |
| `backend/generation` | LLM provider abstraction — extractive baseline, OpenAI-compatible, Ollama |
| `backend/audit` | Append-only SQLite store for authorization decisions. Reconstructable per-query traces |
| `backend/evaluation` | 24-metric implementation: security (S1–S8), retrieval (R1–R4), generation (G1–G4), performance (P1–P4), auditability (U1–U3) |
| `backend/api` | FastAPI layer (planned) |
| `backend/scripts` | Corpus generation, user seeding, index building |

## Design Decisions

1. **Dense-only retrieval.** sentence-transformers `all-MiniLM-L6-v2` + FAISS `IndexFlatIP`. Hybrid sparse/dense is orthogonal to authorization placement and listed as future work.
2. **SQLite for audit.** Avoids extra services for a local prototype. Append-only store with decision reconstruction.
3. **Policy as JSON.** Versioned policy files in `data/policies/` — simple, diffable, reviewable. Policy configuration changes without code changes.
4. **Seeded synthetic corpus.** Fixed random seed (`ZTRUST_SEED`) for reproducible document generation across all configurations.
5. **Per-query authorization.** `allow()` is called fresh on every query — no caching. Every request gets checked, every time.
6. **Scoped FAISS search.** Builds a temporary `IndexFlatIP` over the authorized subset only. Correct by construction; at scale, id-filtered search would be the optimization target.

## Latency Accounting

Authorization latency is measured as the time of the policy-engine step only:

- **Config B:** elapsed time of the post-hoc RBAC filter.
- **Config C:** elapsed time of `authorized_ids` computation plus scoped-search setup (the true pre-retrieval cost).

Total = `auth_latency + retrieval_latency + generation_latency + audit_latency`.
