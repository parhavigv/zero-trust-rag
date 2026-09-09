# Metrics

24-metric evaluation framework covering security, retrieval quality, generation quality, performance, and auditability.

## Security (S1–S8)

| ID | Metric | Definition |
|----|--------|------------|
| S1 | Unauthorized context ratio | Fraction of sentences/chunks in LLM context from unauthorized docs |
| S2 | Unauthorized docs in context | Count of top-k chunks traceable to unauthorized docs |
| S3 | Unauthorized retrieval | Retrieved top-k containing docs outside `gold_allowed_docs` (per oracle) |
| S4 | Sensitive keyword density | Sensitive keyword / PII-passing density in context/answers |
| S5 | Security-balanced metric | Balanced accuracy combining unauthorized-retrieval rate and legit-retrieval rate |
| S6 | Denial correctness | Fraction of deny queries where context contains zero unauthorized docs |
| S7 | False-deny rate | Legitimate content wrongly blocked (target ≤ 10%) |
| S8 | Deny latency | Latency of the deny decision (audit timestamps) |

S1 and S2 are computed per-query and averaged across the query set.

## Retrieval (R1–R4)

Computed only on `allow` queries to isolate authorization impact from denial behavior.

| ID | Metric | Definition |
|----|--------|------------|
| R1 | Recall@k | Share of `gold_allowed_docs` present in authorized context chunk set |
| R2 | Precision@k | Share of returned chunks that are allowed AND in `gold_allowed_docs` |
| R3 | nDCG@k | Ranking quality of authorized results vs oracle gold ranking |
| R4 | MRR | Mean reciprocal rank (for single-gold queries) |

## Generation (G1–G4)

| ID | Metric | Definition |
|----|--------|------------|
| G1 | Faithfulness | % of claim atoms in answer entailed by context |
| G2 | Answer accuracy | Exact/partial-match against oracle answers |
| G3 | Answer coverage | Share of gold answer spans present |
| G4 | Context completeness | Share of gold-allowed docs actually present in context |

G1–G3 are computed with the deterministic extractive provider. Real-LLM generation metrics are not yet evaluated.

## Performance (P1–P4)

| ID | Metric | Definition |
|----|--------|------------|
| P1 | End-to-end latency | Total query time per config |
| P2 | Authorization latency | Policy-engine step only |
| P3 | Retrieval latency | Embedding search time only |
| P4 | Generation latency | Generation time only |

Each latency is mean/median/p95 per config.

## Auditability (U1–U3)

| ID | Metric | Definition |
|----|--------|------------|
| U1 | Decision-trace completeness | Share of decisions with complete chain (user, role, rule, reason, doc, timestamp, query) |
| U2 | Reconstructable runs | Share of query records fully reconstructable from audit store |
| U3 | All decisions logged | Whether every allow/deny decision is present in the audit log |

## Metric → Configuration Applicability

| Metric | A (baseline) | B (filter) | C (pre-retrieval) |
|--------|:---:|:---:|:---:|
| S1 | ✅ | ✅ | ✅ |
| S2 | ✅ | ✅ | ✅ |
| S3 | ✅ | ✅ | ✅ |
| S5 | ✅ | ✅ | ✅ |
| S6 | — | ✅ | ✅ |
| S7 | — | ✅ | ✅ |
| S8 | — | ✅ | ✅ |
| R1–R4 | ✅ | ✅ | ✅ |
| G1–G4 | ✅ | ✅ | ✅ |
| P1–P4 | ✅ | ✅ | ✅ |
| U1–U3 | — | ✅ | ✅ |
