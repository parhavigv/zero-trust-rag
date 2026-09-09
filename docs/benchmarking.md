# Benchmarking

Experiment design, A/B/C configuration wiring, and threat model for measuring the security–retrieval–performance trade-off.

## Design Principle

One independent variable: **where authorization is placed**. Everything else (corpus, embeddings, index, retriever, `k`, query set, LLM provider, audit store) is shared. Observed differences between A, B, C are attributable to authorization placement.

## Configuration Wiring

### Config A — Baseline

```python
chunks = retriever.search(query, k=k, scope=None)
context = build_context(chunks)
answer = llm(context, query)
```

- No authorization on the query path.
- Upper-bound for retrieval quality; worst-case for unauthorized exposure.

### Config B — Retrieve-then-filter

```python
cands = retriever.search(query, k=k_cand, scope=None)
allowed = [c for c in cands if rbac.allow(user, c.doc).allowed][:k]
context = build_context(allowed)
answer = llm(context, query)
```

- Searches all documents, then filters unauthorized candidates.
- Unauthorized documents ARE retrieved (they appear in the candidate ranking, can leak ranking evidence).
- If fewer than `k` allowed chunks survive, context is thinner — measured via context completeness.

### Config C — Pre-retrieval RBAC

```python
authorized_ids = rbac.authorized_ids(user, corpus)
chunks = retriever.search(query, k=k, scope=authorized_ids)
assert all(rbac.allow(user, c.doc).allowed for c in chunks)
context = build_context(chunks)
answer = llm(context, query)
```

- Authorization before any embedding lookup.
- Contract assertion enforces: every chunk in context is authorized.
- Scoped search over `authorized_ids` — not search-all-then-hide.

## Evaluation Protocol

1. Fixed corpus (seeded generator, `ZTRUST_SEED=20260908`).
2. Fixed query set (34 oracle-labeled queries).
3. Same `k=5`, same `k_cand=10` for B.
4. Same embeddings + index + distance function + retriever code.
5. Same LLM provider across all configs (extractive baseline for deterministic runs).
6. Same audit store schema, same metric implementations.
7. Each config runs every query; latencies recorded per-query; results written to `results/` as JSON.

## Threat Model

| Threat Class | Example | Expected Behavior |
|--------------|---------|-------------------|
| Cross-dept confidential | Bob (ENGINEER) queries HR salary | DENY — HR-0001 not in retrieval scope |
| Cross-dept internal | Bob queries Finance internal doc | DENY — Finance-internal not same dept |
| Cross-tenant | Mallory (tenant-beta) queries tenant-acme docs | DENY — hard deny, always |
| Executive secret | EMPLOYEE queries RESTRICTED executive doc | DENY — role not in `allowed_roles` |
| Negation attack | "I know this is confidential but..." | DENY — prompt injection does not bypass policy |
| ABAC ceiling | Alice (HIGH ceiling) queries CRITICAL doc | DENY — `rule6+abac`, sensitivity exceeds ceiling |
| Legitimate access | HR_MANAGER queries HR salary | ALLOW — must succeed, no over-blocking |

Security metrics are computed on deny classes; allow queries are evaluated for false-deny (over-blocking).
