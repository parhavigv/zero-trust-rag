# Experiment Design (Configurations A, B, C)

All numbers in this document are *targets*. Nothing is measured yet.

## Design principle

One independent variable: **where authorization is placed**. Everything else
(corpus, embeddings, index, retriever, `k`, query set, LLM provider, audit
store) is shared so any observed difference between A, B, C is attributable to
authorization placement. Each config is a thin *wiring* of shared components.

## Configuration A — Baseline RAG

Pipeline: `retriever(whole corpus, top-k) → context → LLM`.

- No RBAC on the query path at all (audit still records "no-authz" rows).
- Metric role: upper-bound for retrieval quality & answer quality;
  worst-case for unauthorized exposure.
- Expected finding (hypothesis H1): exposes unauthorized documents.

```python
# experiments/baseline/run.py (signature, Phase 4)
def run(query, k=N) -> RunRecord:
    chunks = retriever.search(query, k=k, scope=None)
    context = build_context(chunks)
    answer = llm(context, query)
    return RunRecord(chunks, context, answer, timeline=t())
```

## Configuration B — Retrieve-then-filter

Pipeline: `retriever(whole corpus, top-k_cand) → RBAC filter → top-k allowed → LLM`.

- Retrieval candidates `k_cand` (search-all) then keep the first `k`
  **allowed** chunks in rank order.
- Consequences we measure:
  - Unauthorized docs ARE retrieved (can leak ranking evidence / latency).
  - If < `k` allowed chunks survive, context is thinner — measured via
    context-completeness and answer quality (H4 / secondary Q4).
- Audit: one `Decision` per candidate chunk + summary row.

```python
# experiments/retrieve_then_filter/run.py (signature, Phase 5)
def run(query, user, k, k_cand) -> RunRecord:
    cands = retriever.search(query, k=k_cand, scope=None)
    allowed = [c for c in cands if rbac.allow(user, c.doc).allowed][:k]
    context = build_context(allowed)
    answer = llm(context, query)
    return RunRecord(cands, allowed, context, answer, timeline=t())
```

## Configuration C — Pre-retrieval RBAC (proposed)

Pipeline: `RBAC engine → authorized_ids → retriever(scope=authorized_ids, top-k) → LLM → audit`.

- **Authorization happens before any embedding lookup.**
- Contract (assertion-run enforced): every chunk in `context` is authorized;
  unauthorized chunks never appear in candidates or context.
- Scoped search over `authorized_ids` (FAISS subset search works over
  `id_map` / explicit vector selection, NOT search-all-then-hide).
- Audit: one `Decision` per document evaluated + scoped-set size + chunk ids.

```python
# experiments/pre_retrieval_rbac/run.py (signature, Phase 6)
def run(query, user, k) -> RunRecord:
    authorized_ids = rbac.authorized_ids(user, corpus)      # pre-retrieval
    chunks = retriever.search(query, k=k, scope=authorized_ids)
    assert all(rbac.allow(user, c.doc).allowed for c in chunks)  # contract
    context = build_context(chunks)
    answer = llm(context, query)
    return RunRecord(chunks, context, answer, timeline=t())
```

## Shared evaluation protocol

1. Fixed corpus (Phase 2 generator, seeded).
2. Fixed query set (oracle-labeled, see data-model doc).
3. Same `k` (default 5) and same `k_cand` for B (`k_cand = 2*k`).
4. Same embeddings + index + distance function; same retriever code.
5. Same LLM provider across all configs (or stub provider for cost-free runs).
6. Same audit store schema, same metric implementations.
7. Each config runs every query in the set; latencies per-query recorded;
   results written to `results/` as JSON/CSV for table+figure generation.

## Run matrix (target)

| Config | #queries | Groups measured |
|--------|----------|-----------------|
| A | full set | retrieval + generation + security-over-exposure |
| B | full set | same + filter effectiveness |
| C | full set | same + denial correctness + audit completeness |

Statistical treatment (to be finalized in Phase 10 — flagged as a design
decision): paired per-query comparisons A-vs-C and B-vs-C; report mean/median,
Δ, and 95% CI where sample size permits; state the CI method used.

## Threat model (security measurement)

- **Cross-dept confidential access**: e.g., Bob(ENGINEER) queries HR salary.
- **Cross-dept internal access**: e.g., Bob queries Engineering INTERNAL doc
  he *is* allowed vs Finance INTERNAL doc he is not.
- **Cross-tenant access**: Mallory(tenant-beta) queries tenant-acme docs.
- **Executive secret access**: EMPLOYEE queries RESTRICTED executive doc.
- **Legit access preserved**: HR_MANAGER queries HR salary doc (must still
  succeed — no over-blocking).

Security metrics (cf. metrics.md) are computed on these classes; denial is the
"hit", allow is evaluated solely for false-deny (over-blocking).