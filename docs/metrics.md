# Evaluation Metrics

Status precondition: metrics are *defined* here (Phase 1). Values will be
reported only after runs (Phase 10). Everything in the report must be
either **literature-supported**, **implementation**, **experimental**, or
**researcher interpretation** — never fabricated.

## Metric families

| Family | Count | Purpose |
|--------|-------|---------|
| Security | 8 | Quantiies unauthorized exposure + denial correctness |
| Retrieval | 4 | Retrieval quality implications of authorization placement |
| Generation | 4 | Answer quality implications (not yet evaluated) |
| Performance | 4 | Latency/overhead implications (H3) |
| Auditability | 3 | Zero-Trust traceability (H5) |
| Trust & compliance mapping | 1 | Demonstrates operationally-relevant compliance (flagged as mapping) |

Total defined: 24.

## Security (8)

| ID | Metric | Definition | Applies to |
|----|--------|-----------|------------|
| S1 | Unauthorized-fields-in-context-ratio | of sentences/chunks entering LLM context, fraction from unauthorized docs | B, C |
| S2 | unauthorized-docs-in-context (`S2u`) | count of top-k chunks traceable to unauthorized docs | A, B, C |
| S3 | Unauthorized retrieval (`T1`) | retrieved top-k containing a doc outside `gold_allowed_docs` (per oracle), grouped by security class | A, B, C |
| S4 | Sensitive keyword method | measure sensitive keyword/pii-passing density in context/answers (with corpus being synthetic) | A, B, C |
| S5 | Security-balanced-metrics (`metrics.balanced_acc`) | balanced accuracy combining unauthorized-retrieval rate and legit-retrieval rate | A, B, C |
| S6 | Denial-correctness rate | fraction of deny queries where the remaining context contains zero unauthorized docs | B, C |
| S7 | False-deny (over-blocking) rate | legitimate content wrongly blocked (target ⩽ 10%) | B, C |
| S8 | Deny-latency | latency of the deny decision (audit-timestamps of `Decision`) | B, C |

`S1` and `S2` are computed per-query and averaged across the query set;
citation-free local definitions are written into `evaluation/metrics.py`
(Phase 9) so numbers are reproducible from `RunRecord`s.

## Retrieval (4)

| ID | Metric | Definition |
|----|--------|-----------|
| R1 | Recall@k | share of `gold_allowed_docs` present in authorized context chunk set (target ≥ recall(authorization-free baseline) − 0.05); A baseline = unrestricted recall |
| R2 | Precision@k | share of returned chunks that are allowed *and* in `gold_allowed_docs` |
| R3 | nDCG@k | ranking quality of authorized results vs oracle gold ranking |
| R4 | Mean reciprocal rank (MRR) | for single-gold queries |

Retrieval metrics are computed **only on `allow` queries** so authorization
placement's true retrieval cost (H4) is not confounded by denial behavior.

## Generation (4)

| ID | Metric | Definition |
|----|--------|-----------|
| G1 | Faithfulness | C/NQG-style verdict: % of claim atoms in answer entailed by context (routed to literature-supported context; **not yet evaluated**) |
| G2 | Answer accuracy | exact/partial-match against oracle answers (synthetic QA tasks) |
| G3 | Answer coverage | share of gold answer spans present |
| G4 | Context-completeness | share of gold-allowed docs actually present in context (the B-context-thinning cost) |

## Performance (4)

| ID | Metric | Definition |
|----|--------|-----------|
| P1 | End-to-end latency | total query time per config |
| P2 | Authz-only latency | policy-engine step only (see architecture doc's latency accounting) |
| P3 | Retrieval latency | embedding search time only |
| P4 | Answer latency | generation time only |

Each latency is mean/median/p95 per config; H3 tests the A-vs-B and A-vs-C
authz deltas and the B-vs-C reclaim comparison, not charts.

## Auditability (3)

| ID | Metric | Definition |
|----|--------|-----------|
| U1 | Decision-trace-completeness | share of authorization decisions that have a complete chain (user, role, rule_id, reason, doc ids, timestamp, query id) |
| U2 | Reconstructable runs | share of query records that can be fully reconstructed (all referenced documents re-retrievable from corpus/audit store) |
| U3 | All-authorization-decisions-logged | whether every `allow`/`deny` decision is present in the audit log (boolean check per run) |

U1–U3 make H5 measurable: the *absence* of a decision in the audit log is
itself a violation.

## Trust & compliance (1, flagged)

| ID | Metric | Definition |
|----|--------|-----------|
| T1 | Compliance-mapping | maps S/U metrics to standard trust/security constructs (least-privilege, data minimization, auditability, confidentiality). Demonstrates operational relevance; explicitly flagged as an author interpretation, not a certification claim. |

## Hypothesis-driven metric map (traceability)

| Hypothesis | Metrics | Expected (if literature is right) |
|------------|---------|------------------------------------|
| H1 pre-retrieval reduces exposure vs baseline | S1, S2u, S3 | C ≪ A |
| H2 pre-retrieval reduces exposure vs retrieve-then-filter | S1, S2u, S3 | C ≤ B (eligible unauthorized docs absent from candidates) |
| H3 authorization adds latency | P2, P3 | C additively slower in authz step |
| H4 metadata keeps retrieval quality acceptable | R1, R2, R3, R4, G4 | C ≈ A on allow-query subset |
| H5 audit improves traceability | U1, U2, U3 | C ≥ B > A (B is additive, A lacks pre-authz decisions) |

Goals reported as targets with honesty about the small synthetic corpus:
we report effect sizes and CIs, not over-claimed significance.