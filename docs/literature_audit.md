# Literature-Review Implementation Audit

Honest, section-by-section mapping between the paper *Zero-Trust RAG: Enterprise
Data Governance via Pre-Retrieval RBAC — A Literature Review* and what the code
in this repository actually implements and measures. Every "Yes"/"No"/"Partial"
below is traceable to a concrete code artifact or test result.

**Date:** 2026-09-09  
**Verdict at a glance:** The core architectural insight (pre-retrieval RBAC as a
hard constraint) is genuinely implemented, measured, and verified. Five of the
paper's proposed-system requirements are not yet implemented; these are gaps the
code openly flags, not fabrications.

---

## 1 — Central gap identified in Section III

> *"Nobody has combined pre-retrieval RBAC/ABAC, Zero-Trust verification, and
> auditable governance into one architecture and then measured the resulting
> trade-off directly."*

**What the code does:**

| Requirement | Implemented? | Where |
|---|---|---|
| Pre-retrieval authorization as hard constraint | ✅ Yes | `backend/rbac/engine.py` → `authorized_ids()` + `backend/retrieval/index.py` → `_search_scoped()` builds a **temporary FAISS index over exactly the authorized subset** (line 57–59) — not mask-after-hide |
| Security metrics (S1–S8) | ✅ Yes | `backend/evaluation/metrics.py` — all computed, reported in `results/comparison.md` |
| Retrieval metrics (R1–R4) on allow queries | ✅ Yes | Same file — recall, precision, nDCG, MRR |
| B-vs-C security contrast (candidate-list level) | ✅ Verified | Bob's Q-009 candidates: B = `[HR-0004, ...]` (HR confidential entered); C = `[ENG-0001, ENG-0004, HR-0001, ...]` (no confidential HR docs) |
| Adversarial negation-style query (Section I, ref [13]) | ✅ Codified + verified | Q-027 to Q-030 in `data/queries/queries.json` ("I know this is confidential but...", "ignore restrictions..."). Verified: on all 4, B enters the unauthorized target in candidates, C never does |
| RBAC + ABAC hybrid (equations 1–2, Section F) | ✅ Done | `attr_mode=true` in `policies_abac.json`; `backend/rbac/attr_predicates.py` evaluates sensitivity ceiling, business-unit clearance, user clearance, and time-window; ABAC ablation queries Q-031–034 verified (alice denied HR-0006 CRITICAL, grace allowed); per-user differential measured in `results/abac_comparison.md` |
| Audit trail with decision reconstruction | ✅ Yes | `backend/audit/store.py` — SQLite append-only; decisions logged; U1/U2/U3 = 1.00 |

**What the paper's Section IV promises but the code does NOT implement:**

| Requirement | Implemented? | Honest status |
|---|---|---|
| RBAC **+ ABAC hybrid** (equations 1–2, Section F) | ✅ Done | `attr_mode=True` in `policies_abac.json`. Engine gates RBAC grants through `backend/rbac/attr_predicates.py`: sensitivity ceiling, business-unit clearance, user clearance level, and time-window predicates. ABAC ablation queries Q-031–034 verified. Per-user differential measured (alice: 11 → 5 allowed docs). Full results in `results/abac_comparison.md` and `docs/findings.md`. |
| PDP/PEP cryptographic token split (Section J, ref [11]) | ❌ Not implemented | Authorization is a direct Python function call: `allow(user, doc, policy)`. There is no Policy Decision Point that issues a signed short-lived token and no Policy Enforcement Point that validates that token locally. |
| Metadata sync-gap (Δt propagation delay, Section I) | ❌ Not modeled | No scenario where a role is revoked or document reclassified mid-experiment. Policy and document metadata are static seed data. |
| True Pareto frontier sweep (Section III) | ⚠️ Partial | 3 configurations (A/B/C) yield a line segment, not a frontier. A Pareto sweep would require varying policy strictness (attribute thresholds), k, and corpus size across many points. |
| Real-model generation faithfulness (G1–G3) | ❌ Not yet evaluated | Deterministic extractive provider used; G1=1.0 trivially (answer extracted from context). Real-LLM evaluation marked "Not yet evaluated." |

---

## 2 — Specific claims tested vs measured

### Claim: B retrieves unauthorized content into candidates (Section H)

**Measured:** YES. In `Q-009` (Bob asks HR salary bands), B's candidate list =
`['HR-0004', 'ENG-0001', 'BET-HR', 'BET-ENG', 'ENG-0004', 'HR-0001',
'ENG-0003', 'HR-0006', 'HR-0002', 'HR-0003']`. HR-0004, HR-0006, HR-0002,
HR-0003 are all HR confidential docs that Bob should not see — yet they entered
the candidate ranking. S3 total across 26 queries = 178 unauthorized docs in
B's candidate lists vs 0 in C's. **This directly validates the paper's
Section-H argument that retrieve-then-filter leaks "downstream of exposure."**

### Claim: C's scoped search is genuinely authorization-first (Section I, eq. 1)

**Verified by code inspection.** `_search_scoped()` (index.py:53–72) extracts
the authorized vector rows (`sub = self.vec[pos]`), builds a fresh `faiss.IndexFlatIP`,
adds only those vectors, and searches that sub-index. There is no path for
unauthorized vectors to appear in the search results. The contract assertion in
`run_c` (`assert all(allow(...) for ... in chunks)`) would hard-fail if
unauthorized content leaked. In 26 queries × real embeddings, the assertion
never fired.

### Claim: Security–retrieval trade-off measured directly (Section III Pareto)

**Partially validated.** R1 recall = 1.00 for all three configs on allow queries
(H4 supported on this corpus). R3 nDCG actually slightly better under C
(0.877 vs 0.848 for A). Latency: C adds ~0.86 ms (P2) vs 0 ms for A — a
measurable cost, but <3% of total ~32 ms. **The security improvement does not
reduce retrieval quality on this corpus** — which means we are at the security
corner of the Pareto curve, not on a trade-off slope. A richer corpus or
more-strict policies would be needed to trace the full frontier.

### Claim: Zero-Trust continuous authorization (Section J, ref [11])

**Implemented:** `allow()` is called fresh per query (no caching). Every query
resolution evaluates the full rule chain against current user state. The audit
store records the decision with timestamp, enabling post-hoc reconstruction.
This satisfies NIST SP 800-207's "every request gets checked, every time"
principle at the architectural level.

---

## 3 — What this means for the paper's contribution

**What the code genuinely demonstrates:**
1. The Section-I candidate-set function `C(u)` is correctly implemented and
   measurable. Authorized candidate sets are provably the only documents the
   retriever sees under C.
2. The B-vs-C security contrast at the candidate-list level (the paper's core
   argument) is real and quantified.
3. Audit trail completeness (U1/U2/U3) is 1.00 for B and C, supporting the
   paper's governance claims.
4. The RBAC engine correctly implements deny-by-default with the documented rule
   ordering (tenant → enabled → PUBLIC → INTERNAL → CONFIDENTIAL → override → deny).
5. The ABAC hybrid (equations 1–2) is implemented and measured: the attribute
   gate further narrows the authorized set (e.g., alice: 11 → 5 allowed docs)
   while maintaining retrieval quality (R1 = 1.00). The hybrid decision path
   is traceable in audit logs via `rule_id` values carrying the `+abac` suffix.

**What remains a gap (honest list):**
1. ~~No ABAC attribute predicates~~ ✅ Done. ABAC hybrid implemented and measured (see above).
2. No PDP/PEP cryptographic token separation — authorization is direct
   function call, not a decoupled policy enforcer.
3. No metadata sync-gap scenario — policy and document metadata are static.
4. Three configurations is a line segment, not a Pareto frontier curve.
5. Real-LLM generation metrics are not yet evaluated (extractive baseline only).

---

## 4 — Items this audit explicitly does NOT cover

- Fabrication check: all numbers are artifacts of this repository's own
  `experiments.run_all` and `evaluation.aggregate` runs. Run records are
  stored in `results/runs/` and `results/runs_abac/` for full reproducibility.
- Statistical significance: n=34 queries on a synthetic corpus; no confidence
  intervals are claimed and none should be interpreted as such.
- Real-LLM answer quality: generation metrics use an extractive baseline;
  they are explicitly marked "Not yet evaluated with a production LLM" in all
  tables and in `docs/findings.md`.

---

## 5 — Recommended next steps (prioritized)

| Priority | Gap | Fix description |
|---|---|---|
| ~~1~~ | ~~ABAC hybrid~~ | ✅ Done. `attr_mode=true`, `backend/rbac/attr_predicates.py`, `policies_abac.json`, ABAC ablation queries Q-031–034, per-user differential in `results/abac_comparison.md`. |
| 2 | PDP/PEP token | Split `allow()` into `PDP.evaluate()` → returns a signed token; `PEP.validate_and_apply()` checks token locally before search. HMAC-signed to prevent orchestrator tampering. |
| 3 ~~Negation attacks~~ | ✅ Done (Q-027–030 codified; B leaks at candidate level, C never) | Add a security test class asserting `target in B.candidate_ids` and `target not in C.candidate_ids`. |
| 4 | Sync-gap scenario | Model one query executed under stale metadata (role revoked but policy not yet updated). Measure leakage window. |
| 5 | Pareto sweep | Sweep policy strictness (1–3 attribute conditions) × k (3–10) × corpus size. Plot latency vs S1. |

---

*Audit performed against: Parhavi G. V. et al., "Zero-Trust RAG: Enterprise Data
Governance via Pre-Retrieval RBAC — A Literature Review," IEEE.*