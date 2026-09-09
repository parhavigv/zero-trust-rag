# Architecture

## Research role of this document

Defines *what* the prototype is, *why* each component exists (mapped to the
research question), and *how* the three configurations are kept comparable.
This is the Phase-1 deliverable referenced in the README status table.

## System pipeline

```
 User
   │  identity verification (token / user lookup)
   ▼
 Role identification  (user_id → role + department + tenant)
   │
   ▼
 RBAC Policy Engine  (user, query, document.metadata) → Decision{allow,deny}
   │                    deny-by-default; re-evaluated per query (continuous authz)
   ▼
 Authorized Candidate Set   ←  C only: the searchable universe is scoped here
   │
   ▼
 Semantic Retrieval  (dense embeddings over the authorized set only)
   │
   ▼
 Secure Context Construction  (decorate chunks; keep provenance)
   │
   ▼
 LLM  (configurable provider; stub provider for headless evaluation)
   │
   ▼
 Response
   │
   ▼
 Audit Log  (user, role, query, document, decision, reason, trace, t)
```

## Configuration A — Baseline RAG

```
query ─▶ retriever(all corpus, top-k) ─▶ k chunks ─▶ LLM ─▶ answer
```

- No authorization anywhere. All chunks from any department/tenant are
  retrievable and enter context.
- Serves as the upper-bound-exposure / upper-bound-quality reference.

## Configuration B — Retrieve-then-filter

```
query ─▶ retriever(all corpus, top-k_cand) ─▶ RBAC filter ─▶ authorized k ─▶ LLM
```

- The retriever searches **all** documents; authorization happens *after*
  ranking. Unauthorized documents are retrieved (they can be surfaced in the
  candidate ranking and can pollute intermediate scoring) and then dropped.
- To keep `k` comparable, the runner retrieves `k_cand >= k` and keeps the
  first `k` allowed chunks; if fewer than `k` allowed chunks remain, the
  context is smaller (a quality consequence we measure).

## Configuration C — Pre-retrieval RBAC (proposed)

```
query ─▶ RBAC policy engine ─▶ authorized_ids = {d : allow(user, d)}
       ─▶ retriever scoped to authorized_ids, top-k ─▶ LLM ─▶ answer ─▶ audit
```

- **Contract:** unauthorized documents are never passed to the retriever and
  can never appear in the top-k or the LLM context. The embedding search runs
  over the authorized candidate set only.
- Implementation note: the index stores all corpus vectors; the pre-retrieval
  step computes `authorized_ids` from metadata and the search is executed over
  exactly that subset (scoped FAISS search). This is not "search-all-then-hide".

## Module responsibilities

| Module | Responsibility | Why the research question needs it |
|--------|----------------|------------------------------------|
| `auth` | Verify user + derive role/tenant context at request time | Zero-Trust #1/#2: never trust inside-network identity; explicit verification |
| `rbac` | Policy evaluation: `allow(user, doc metadata)`, deny-by-default | Core independent variable: authorization placement and semantics |
| `retrieval` | Embed, index, **scoped** search (A/B/C share it; C scopes it) | Retrieval metrics + the B vs C contrast |
| `generation` | LLM provider abstraction (stub / ollama / openai-compatible) | Generation metrics; reproducible headless runs |
| `audit` | Append-only, reconstructable authorization records | Auditability metrics + Zero-Trust #7 |
| `api` | FastAPI layer (interactive demo + measurement endpoint) | Provide the same pipeline behind HTTP for real runs |
| `evaluation` | Metric definitions/aggregation; oracle query set | Phase 9–11; no fabricated numbers |

## Fresh-scaffold design choices (flagged, not literature-claimed)

These are engineering decisions for a reproducible student prototype, not
claims validated by literature:

1. Dense-only retrieval (sentence-transformers `all-MiniLM-L6-v2` + FAISS).
   Hybrid sparse/dense is orthogonal to authorization placement and is listed
   as future work; keeping it single-retriever isolates the independent
   variable.
2. SQLite for users + audit (brief explicitly permits it; avoids an extra
   service for a local prototype).
3. Policy set stored as versioned JSON/YAML in `data/policies/` (simple,
   diffable, reviewable) rather than a policy database.
4. Synthetic corpus and oracle-labeled query set (see `docs/data-model.md`) so
   every retrieval decision has a ground-truth authorization answer
   (needed for precision/recall and security metrics).

## Data flow at query time (all configs)

1. Resolve identity → `(user_id, role, department, tenant_id)`.
2. Run the config-specific wiring:
   - A: no authz.
   - B: search all → filter by `allow(user, doc)`.
   - C: compute `authorized_ids` → scoped search.
3. Gather chunks; record `(query_id, chunk_ids, decision per chunk)`.
4. Build context; optionally call LLM (with a provider).
5. Append one audit row per authorization decision + one per request.

## Latency accounting

Authorization latency is measured as the time of the policy-engine step only:
- B: elapsed time of the post-hoc RBAC filter.
- C: elapsed time of `authorized_ids` computation **plus** scoped-search
  setup (the true pre-retrieval cost).
Total = `auth_latency + retrieval_latency + (generation_latency) + audit_latency`.

This split is what makes H3 (latency overhead) measurable and lets us answer
secondary question 3 without conflating retriever and policy costs.