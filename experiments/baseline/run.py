"""Configuration A — Baseline RAG (no authorization)."""
from __future__ import annotations

from experiments.common import RunRecord, ms, timer


def run_a(query, user, index, embedder, provider, docs_by_id, k=5, audit=None,
          policy=None, k_cand=0, run_id=""):
    rec = RunRecord(
        query_id=query["query_id"], config="A_baseline", user_id=user.user_id,
        expected=query["expected"], category=query["category"], k=k,
        embedding_mode=embedder.mode,
    )
    t0 = timer()
    qv = embedder.embed_one(query["text"])
    t1 = timer()
    ids, _ = index.search(qv, k, scope=None)
    t2 = timer()
    rec.candidate_ids = ids
    rec.context_ids = list(ids)
    rec.lat_authz_ms = 0.0
    rec.lat_retrieval_ms = ms(t1, t2)
    context_texts = [docs_by_id[did].content for did in ids if did in docs_by_id]
    gen = provider.generate(query["text"], context_texts)
    t3 = timer()
    rec.answer = gen.answer
    rec.provider = gen.provider
    rec.lat_gen_ms = ms(t2, t3)
    rec.lat_total_ms = ms(t0, t3)
    rec.scope_size = -1
    if audit is not None:
        audit.log_run(rec.query_id, "A_baseline", query["query_id"], user.user_id,
                      lat_authz_ms=0.0, lat_retrieval_ms=rec.lat_retrieval_ms,
                      lat_gen_ms=rec.lat_gen_ms, lat_audit_ms=0.0, k=k, scope_size=-1)
    return rec