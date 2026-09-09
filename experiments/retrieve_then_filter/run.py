"""Configuration B — Retrieve-then-filter.

The retriever searches the whole corpus (k_cand), then the RBAC filter drops
unauthorized candidates; the first k allowed chunks in rank order form context.
"""
from __future__ import annotations

from experiments.common import RunRecord, ms, timer
from backend.rbac.engine import allow


def run_b(query, user, index, embedder, provider, docs_by_id, policy,
          k=5, k_cand=10, audit=None, run_id=""):
    rec = RunRecord(
        query_id=query["query_id"], config="B_retrieve_then_filter",
        user_id=user.user_id, expected=query["expected"],
        category=query["category"], k=k, embedding_mode=embedder.mode,
    )
    t0 = timer()
    qv = embedder.embed_one(query["text"])
    t1 = timer()
    cand_ids, _ = index.search(qv, k_cand, scope=None)
    t2 = timer()
    rec.candidate_ids = cand_ids
    t_a0 = timer()
    allowed_ids: list[str] = []
    decisions = []
    for did in cand_ids:
        doc = docs_by_id[did]
        dec = allow(user, doc, policy)
        decisions.append(dec)
        if dec.allowed:
            allowed_ids.append(did)
    t_a1 = timer()
    rec.decisions = [d.to_dict() for d in decisions]
    rec.lat_authz_ms = ms(t_a0, t_a1)
    context_ids = allowed_ids[:k]
    rec.context_ids = context_ids
    rec.lat_retrieval_ms = ms(t1, t2)
    context_texts = [docs_by_id[did].content for did in context_ids if did in docs_by_id]
    gen = provider.generate(query["text"], context_texts)
    t3 = timer()
    rec.answer = gen.answer
    rec.provider = gen.provider
    rec.lat_gen_ms = ms(t2, t3)
    rec.lat_total_ms = ms(t0, t3)
    rec.scope_size = -1
    if audit is not None:
        for dec in decisions:
            audit.log_decision(dec, query["query_id"], run_id)
        audit.log_run(rec.query_id, "B_retrieve_then_filter", query["query_id"],
                      user.user_id, lat_authz_ms=rec.lat_authz_ms,
                      lat_retrieval_ms=rec.lat_retrieval_ms, lat_gen_ms=rec.lat_gen_ms,
                      lat_audit_ms=0.0, k=k, scope_size=len(allowed_ids))
    return rec