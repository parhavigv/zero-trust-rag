"""Evaluation metrics (Phase 9). Definitions follow docs/metrics.md.

Security unauthorized-set is the *engine's* global allowed set; retrieval
quality gold is the *oracle's* target docs. This keeps "unauthorized" a
policy fact and "retrieval quality" a task fact.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from backend.rbac.engine import authorized_ids


def _allowed_all(user, docs_by_id, policy) -> set[str]:
    return authorized_ids(user, list(docs_by_id.values()), policy)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _recall(hits: set[str], gold: set[str]) -> float:
    return len(hits & gold) / len(gold) if gold else 1.0


def _precision(hits: set[str], gold: set[str]) -> float:
    return len(hits & gold) / len(hits) if hits else 0.0


def _token_f1(ans: str, gold: str) -> float:
    a, g = _tokens(ans), _tokens(gold)
    if not a and not g:
        return 1.0
    inter = len(a & g)
    if inter == 0:
        return 0.0
    p, r = inter / len(a), inter / len(g)
    return 2 * p * r / (p + r)


def _ndcg(ranking: list[str], gold: set[str]) -> float:
    if not gold:
        return 1.0
    dcg = sum(1.0 / math.log2(i + 2.0) for i, did in enumerate(ranking) if did in gold)
    idcg = sum(1.0 / math.log2(i + 2.0) for i in range(min(len(gold), len(ranking))))
    return dcg / idcg if idcg else 0.0


def query_metrics(rec, user, docs_by_id, policy, q):
    """Per-query metric vector. Returns a dict (some keys may be None)."""
    gold = set(q.get("gold_allowed_docs", []))
    allowed_all = _allowed_all(user, docs_by_id, policy)
    cands, ctx = rec.candidate_ids, rec.context_ids
    gold_text = q.get("gold_answer_text", "")

    unauth_ctx = [d for d in ctx if d not in allowed_all]
    unauth_cand = [d for d in cands if d not in allowed_all]
    s1 = len(unauth_ctx) / len(ctx) if ctx else 0.0
    s2 = len(unauth_ctx)
    s3 = len(unauth_cand)
    r1 = _recall(set(ctx), gold)
    r2 = _precision(set(ctx), gold)
    r3 = _ndcg(cands, gold)
    r4 = 0.0
    if len(gold) == 1 and cands and next(iter(gold)) in cands:
        r4 = 1.0 / (cands.index(next(iter(gold))) + 1.0)

    ctx_tokens = set()
    for cid in ctx:
        if cid in docs_by_id:
            ctx_tokens |= _tokens(docs_by_id[cid].content)
    ans_tokens = _tokens(rec.answer)
    g1 = len(ans_tokens & ctx_tokens) / len(ans_tokens) if ans_tokens else 1.0
    g2 = _token_f1(rec.answer, gold_text)
    gold_tokens = _tokens(gold_text)
    g3 = len(ans_tokens & gold_tokens) / len(gold_tokens) if gold_tokens else 1.0
    g4 = _recall(set(ctx), gold)

    s5 = 0.5 * (1.0 - s1) + 0.5 * (1.0 if not gold else r1)

    completeness = 1.0
    if rec.config == "B_retrieve_then_filter":
        evaluated = set(rec.candidate_ids)
    elif rec.config == "C_pre_retrieval_rbac":
        evaluated = set(docs_by_id.keys())
    else:
        evaluated = set()
    found = Counter(d.get("object") for d in rec.decisions)
    if evaluated:
        missing = [oid for oid in evaluated if found.get(oid, 0) < 1]
        completeness = 0.0 if missing else 1.0
        row_ok = all(
            all(d.get(f) for f in ("subject", "object", "rule_id", "reason", "timestamp"))
            for d in rec.decisions
        )
    else:
        row_ok = None

    return {
        "S1": s1, "S2": s2, "S3": s3, "S5": s5,
        "S6": int(s2 == 0), "S7": int(len(gold & set(ctx)) < len(gold)) if gold else None,
        "S8_deny_authz_ms": rec.lat_authz_ms,
        "R1": r1, "R2": r2, "R3": r3, "R4": r4,
        "G1": g1, "G2": g2, "G3": g3, "G4": g4,
        "P1_total_ms": rec.lat_total_ms, "P2_authz_ms": rec.lat_authz_ms,
        "P3_retrieval_ms": rec.lat_retrieval_ms, "P4_gen_ms": rec.lat_gen_ms,
        "U1": row_ok, "U2": completeness, "U3": completeness,
        "s2_deny_ok": s2,
    }


_M = ["S1", "S2", "S3", "S5", "S6", "R1", "R2", "R3", "R4",
       "G1", "G2", "G3", "G4", "P1_total_ms", "P2_authz_ms",
       "P3_retrieval_ms", "P4_gen_ms"]


def aggregate(recs, users, docs_by_id, policy, queries_by_id, doc_ids_all=None):
    """Aggregate per-query metric vectors into per-config numbers (mean/median/p95).

    Pass doc_ids_all to scope the evaluated set for completeness (used by the
    ABAC variant so reconstruction compares against the full corpus).
    """
    rows = []
    for rec in recs:
        q = queries_by_id[rec.query_id]
        user = users[rec.user_id]
        m = query_metrics(rec, user, docs_by_id, policy, q)
        m["_allow"] = q["expected"] == "allow"
        m["_deny"] = not m["_allow"]
        rows.append(m)

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        n = len(vals)
        return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2

    def p95(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        idx = min(len(vals) - 1, int(0.95 * (len(vals) - 1)))
        return vals[idx]

    out = {}
    for key in _M:
        allv = [r[key] for r in rows if r[key] is not None]
        if key in ("P1_total_ms", "P2_authz_ms", "P3_retrieval_ms", "P4_gen_ms"):
            out[key] = {
                "mean": round(mean(allv), 3) if allv else None,
                "median": round(median(allv), 3) if allv else None,
                "p95": round(p95(allv), 3) if allv else None,
            }
        else:
            out[key] = round(mean(allv), 4) if allv else None

    allow_rows = [r for r in rows if r["_allow"]]
    deny_rows = [r for r in rows if r["_deny"]]
    out["n_queries"] = len(rows)
    out["n_allow"] = len(allow_rows)
    out["n_deny"] = len(deny_rows)

    out["S1_deny_only"] = round(mean([r["S1"] for r in deny_rows]), 4) if deny_rows else None
    out["S2_deny_total"] = sum(r["S2"] for r in deny_rows) if deny_rows else None
    out["S3_unauth_candidates"] = sum(r["S3"] for r in rows)
    out["S6_denial_correct"] = round(mean([r["S6"] for r in deny_rows]), 4) if deny_rows else None
    out["S7_false_deny_rate"] = round(mean([r["S7"] for r in allow_rows if r["S7"] is not None]), 4) \
        if any(r["S7"] is not None for r in allow_rows) else None
    out["S8_deny_authz_mean_ms"] = round(mean([r["S8_deny_authz_ms"] for r in deny_rows]), 3) \
        if deny_rows else None

    out["R1_allow_only"] = round(mean([r["R1"] for r in allow_rows]), 4) if allow_rows else None
    out["R2_allow_only"] = round(mean([r["R2"] for r in allow_rows]), 4) if allow_rows else None
    out["R3_allow_only"] = round(mean([r["R3"] for r in allow_rows]), 4) if allow_rows else None
    out["R4_allow_only"] = round(mean([r["R4"] for r in allow_rows]), 4) if allow_rows else None

    out["G4_allow_context_complete"] = round(mean([r["G4"] for r in allow_rows]), 4) if allow_rows else None
    out["G1_allow_only"] = round(mean([r["G1"] for r in allow_rows]), 4) if allow_rows else None
    out["G2_allow_only"] = round(mean([r["G2"] for r in allow_rows]), 4) if allow_rows else None
    out["G3_allow_only"] = round(mean([r["G3"] for r in allow_rows]), 4) if allow_rows else None

    u1v = [r["U1"] for r in rows if r["U1"] is not None]
    u23v = [r["U2"] for r in rows if r["U2"] is not None]
    out["U1_trace_complete"] = round(mean(u1v), 4) if u1v else None
    out["U2_reconstructable"] = round(mean(u23v), 4) if u23v else None
    out["U3_all_logged"] = round(mean(u23v), 4) if u23v else None
    return out