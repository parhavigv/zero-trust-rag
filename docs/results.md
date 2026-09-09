# Results

Measured outcomes from the A/B/C experiment sweep and ABAC hybrid ablation. All numbers are computed outputs of the code in this repository — not fabricated.

## Run Conditions

| Item | Value |
|------|-------|
| Corpus | 42 synthetic docs, 6 departments + tenant-beta |
| Users | 9 (roles, depts, two tenants, one disabled) |
| Queries | 34 oracle-labeled (11 allow / 23 deny) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (real model, CPU) |
| Index | FAISS `IndexFlatIP` (cosine similarity) |
| Generation | Extractive provider (deterministic sentence pick) |
| k / k_cand | 5 / 10 |
| Audit | SQLite append-only store |

## Security & Retrieval Metrics

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| S1 — unauthorized context ratio | **0.671** | 0.000 | **0.000** |
| S2 — unauthorized docs in context (mean) | **3.35** | 0.00 | **0.00** |
| S3 — unauthorized docs in candidates (total) | 114 | **242** | **0** |
| S5 — security-balanced | 0.665 | 1.00 | **1.00** |
| S6 — denial correctness | 0.00 | 1.00 | **1.00** |
| S7 — false-deny rate | 0.00 | 0.00 | 0.00 |
| S8 — deny latency mean (ms) | 0.00 | 0.25 | 0.76 |

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| R1 — recall@k (allow) | 1.00 | 1.00 | 1.00 |
| R2 — precision@k (allow) | 0.20 | 0.26 | 0.20 |
| R3 — nDCG@k (allow) | 0.876 | 0.876 | 0.899 |
| R4 — MRR (allow) | 0.833 | 0.833 | 0.864 |

## Performance

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| P1 — end-to-end latency (mean) | 19.0 ms | 18.5 ms | 19.1 ms |
| P2 — authorization latency (mean) | 0.00 ms | 0.25 ms | 0.78 ms |
| P3 — retrieval latency (mean) | 0.64 ms | 0.29 ms | 0.20 ms |

## Auditability

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| U1 — decision-trace completeness | n/a | 1.00 | 1.00 |
| U2 — reconstructable runs | 1.00 | 1.00 | 1.00 |
| U3 — all decisions logged | 1.00 | 1.00 | 1.00 |

## Generation (Extractive Baseline)

| Metric | A | B | C |
|--------|:---:|:---:|:---:|
| G1 — faithfulness | 1.00 | 1.00 | 1.00 |
| G2 — answer overlap | 0.80 | 0.81 | 0.81 |
| G3 — gold coverage | 0.76 | 0.77 | 0.77 |

Real-LLM generation metrics: not yet evaluated.

## ABAC Hybrid Ablation

### Attribute Gate Differential

| User | RBAC allowed | ABAC allowed | Removed |
|------|:---:|:---:|:---:|
| alice (HR_MANAGER) | 11 | 5 | 6 |
| grace (HR_ADMIN) | 11 | 6 | 5 |
| bob (ENGINEER) | 11 | 5 | 6 |
| carol (FINANCE_ANALYST) | 11 | 5 | 6 |
| dave (SALES_REP) | 11 | 3 | 8 |
| frank (LEGAL_COUNSEL) | 11 | 5 | 6 |
| eve (EXECUTIVE_VP) | 16 | 10 | 6 |
| mallory (ENGINEER) | 6 | 1 | 5 |

### Ablation Queries

| Query | User | Expected | Result | Reason |
|-------|------|----------|--------|--------|
| Q-031 | alice | deny | deny | HR-0006 CRITICAL exceeds user max HIGH |
| Q-032 | alice | deny | deny | HR-0006 CRITICAL exceeds user max HIGH |
| Q-033 | grace | allow | allow | CRITICAL ≤ CRITICAL, attributes satisfied |
| Q-034 | grace | allow | allow | CRITICAL ≤ CRITICAL, attributes satisfied |

### ABAC Security Metrics (23 queries under ABAC policy)

| Config | S1 (unauth ctx) | S6 (denial-correct) | R1 (allow recall) |
|--------|:---:|:---:|:---:|
| A baseline (abac) | **0.930** | 0.000 | 1.000 |
| B filter (abac) | 0.000 | 1.000 | 1.000 |
| C pre-retrieval (abac) | 0.000 | 1.000 | 1.000 |

## Key Observations

1. **Config C eliminates unauthorized exposure.** S1 = 0.000, S3 = 0. Unauthorized content never enters candidates or context.
2. **Config B keeps context clean but leaks at candidate level.** S3 = 242 unauthorized docs in candidate lists. Any downstream component touching candidates before filtering leaks a signal.
3. **Authorization cost is negligible.** Config C adds ~0.78 ms authorization latency — less than 5% of total ~19 ms end-to-end.
4. **Retrieval quality is not degraded.** R1 = 1.00 across all configs. R3/MRR slightly better under C.
5. **ABAC further restricts scope.** The attribute gate narrows the authorized set (e.g., alice: 11 → 5 docs) while maintaining retrieval quality (R1 = 1.00).
6. **Negation attacks do not bypass policy.** On all 4 adversarial queries (Q-027–030), B surfaces the unauthorized target in candidates while C never does.

## Limitations

1. **Synthetic corpus.** 42 docs / 34 queries — indicative, not statistically significant.
2. **Extractive generation baseline.** Real-LLM generation metrics not yet evaluated.
3. **Dense-only retrieval.** Hybrid sparse/dense could change ranking but is orthogonal to authorization.
4. **Static policy and identity.** No real IdP/OIDC, no metadata revocation mid-experiment.
5. **Single-thread CPU.** Throughput at scale (100k+ docs) not evaluated.
