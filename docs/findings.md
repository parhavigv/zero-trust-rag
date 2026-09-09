# Findings, Limitations & Future Work

> Status: measured run on the synthetic corpus. All numbers below are computed
> outputs of the code in this repository (see `results/comparison.md` and
> `results/runs/`), **not** excerpts of published papers and **not** fabricated.
> Generation metrics were produced with a deterministic extractive provider;
> real-model generation metrics remain **"Not yet evaluated"**.

## Run conditions

| Item | Value |
|------|-------|
| Corpus | 42 synthetic docs, 6 departments + tenant-beta, seeded build |
| Users | 9 (roles, depts, two tenants, one disabled) |
| Queries | 26 oracle-labeled (9 allow / 17 deny) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (real model, CPU) |
| Index / retriever | FAISS `IndexFlatIP` (cosine), shared across A/B/C |
| Generation | extractive provider (deterministic sentence pick) |
| k / k_cand | 5 / 10 |
| Audit | SQLite append-only store (1352 decisions logged) |

## Headline results (measured)

| Metric | A baseline | B retrieve-then-filter | C pre-retrieval RBAC |
|--------|-----------:|------------------------:|---------------------:|
| S1 unauthorized share in context | **0.646** | 0.000 | **0.000** |
| S2 unauthorized docs in context (mean) | **3.23** | 0.00 | **0.00** |
| S3 unauthorized docs in candidate lists (total) | 84 | **178** | **0** |
| S5 security-balanced | 0.68 | 1.00 | **1.00** |
| S6 denial-correctness | 0.00 | 1.00 | **1.00** |
| S7 false-deny (over-block) rate | 0.00 | 0.00 | 0.00 |
| S8 deny authz latency mean (ms) | 0.00 | 0.27 | 0.86 |
| R1 recall@k (allow queries) | 1.00 | 1.00 | 1.00 |
| R3 nDCG@k (allow queries) | 0.848 | 0.848 | 0.877 |
| R4 MRR (allow queries) | 0.796 | 0.796 | 0.833 |
| P1 end-to-end latency mean (ms) | 33.8 | 31.1 | 31.8 |
| P2 authz-stage latency mean (ms) | 0.00 | 0.28 | 0.86 |
| U1 decision-trace completeness | n/a | 1.00 | 1.00 |
| U2 reconstructable runs | 1.00 | 1.00 | 1.00 |
| U3 all decisions logged | 1.00 | 1.00 | 1.00 |

## Hypothesis evaluation

| ID | Hypothesis | Verdict | Evidence |
|----|------------|---------|----------|
| H1 | Pre-retrieval RBAC reduces unauthorized context vs baseline | **Supported** | S1 0.646 → 0.000; S2 3.23 → 0.00 |
| H2 | Pre-retrieval RBAC reduces unauthorized retrieval vs retrieve-then-filter | **Supported** | S3: C returns 0 unauthorized candidates; B returns 178 (retrieved-then-dropped) |
| H3 | Authorization adds measurable latency | **Supported (small)** | C adds ~0.86 ms vs A 0.00 ms (<3% of ~32 ms total) |
| H4 | Authorization metadata keeps retrieval quality acceptable | **Supported on this corpus** | R1 equal at 1.00; R3/MRR slightly *higher* under C (0.877 vs 0.848) |
| H5 | Auditing improves traceability | **Supported** | U1/U2/U3 = 1.00 for B and C; A has no pre-authz decision stage by design |

A defense-in-depth note visible in the data: B keeps the *context* clean
(S1 = 0.000, same as C) but its candidate stage still surfaces unauthorized
documents (S3 = 178 vs 0). If any downstream component (reranker, logger,
embedding cache) touches candidates before filtering, B leaks a signal that C
does not. This is the root of the B-vs-C security difference in H2.

## Secondary research questions

1. **Does pre-retrieval RBAC reduce unauthorized retrieval?** Yes, on this run:
   S3 = 0 for C, 178 for B, 84 for A.
2. **How does it compare with retrieve-then-filter?** B achieves clean contexts
   too, but only in the final filter; C never raises unauthorized candidates.
3. **What latency overhead does authorization introduce?** ~0.86 ms mean for C,
   0.28 ms for B, 0.00 for A — measurable but negligible vs ~32 ms total.
4. **Does authorization reduce retrieval quality?** Not observed: recall equal,
   ranking metrics slightly better under C.
5. **Does it reduce sensitive-information leakage?** Yes on context-level
   metrics (S1/S2). Answer-level leakage is pending a real LLM provider.
6. **Can every authorization decision be audited?** Yes by design: U1/U3 = 1.00
   and every decision row carries subject, role, dept, object, classification,
   tenant, rule_id, reason, effector, timestamp.
7. **How does RBAC compare with fine-grained policy?** **Not yet evaluated.**
   The attribute-based variant (`attr_mode`) is implemented as a policy
   configuration but has not been run in this checkpoint.

## Limitations

1. **Single small synthetic corpus.** 42 docs / 26 queries; statistics are
   indicative, no confidence intervals, no significance claims.
2. **Generation is an extractive baseline.** G1–G3 were computed with the
   deterministic provider, so they are *not* evidence about a production LLM.
   **Real-model generation metrics: Not yet evaluated.**
3. **No hybrid retrieval.** Dense-only; sparse/hybrid could change ranking but
   is orthogonal to authorization placement (flagged as future work).
4. **Static RBAC policy.** No attribute-conditions ablation (secondary Q7) has
   been measured yet.
5. **Identity is a static seed set.** No real IdP/OIDC/token verification; the
   `auth` module resolves users from `users.json` for the prototype.
6. **Single-thread CPU timings.** Latency deltas are sub-millisecond; throughput
   at scale (100k+ docs) is not evaluated.
7. **R2 choice of gold.** Gold targets are single-document; with k=5 the
   absolute precision is low (~0.2) — consistent across configs, so the H4
   *comparison* still holds, but absolute numbers must not be over-read.

## Engineering design choices (flagged, not literature claims)

- Deny-by-default rule ordering in `backend/rbac/engine.py` is our own
  specification (matches `docs/rbac-policy-model.md`), not a standard.
- `authorized_ids()` computes the allow-set per query (continuous authorization,
  Zero-Trust) rather than caching approved sets — deliberately conservative.
- Scoped FAISS search builds a temporary index over the authorized subset
  (correct by construction, but at scale the id-filtered search is where a
  production implementation would optimize).

## Reproducibility

```bash
python -m venv .venv && .venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m backend.scripts.build_corpus    # 42 docs, 9 users, 26 queries
python -m experiments.run_all             # A, B, C over all queries
python -m evaluation.aggregate            # results/comparison.md + figures
python -m pytest tests -q                 # 36 tests
```

The corpus/query generation is seeded (`ZTRUST_SEED`), and run records are
stored under `results/runs/<CONFIG>/<QUERY>.json` for full auditability.

## Integrity & reporting rules honored

- No fabricated citations, datasets, or numbers; every table value is an
  artifact of this repository's own execution.
- Claims are separated here into: implementation (what we built), experimental
  (measured numbers), interpretation (limitations-flagged), and
  literature-untested items (marked "Not yet evaluated").
- Generation-quality claims are explicitly provisional pending a real LLM.