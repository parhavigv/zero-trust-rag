"""Configuration C — Pre-retrieval RBAC (proposed).

Authorization happens BEFORE any retrieval: the authorized candidate set is
computed first, then the retriever searches exactly that set. The contract
assertion makes unauthorized-in-context a hard failure.
"""
from __future__ import annotations

from experiments.common import RunRecord, ms, timer
from backend.rbac.engine import allow, authorized_ids


def run_c(query, user, index, embedder, provider, docs_by_id, policy,
          k=5, audit=None, run_id="", k_cand=0):
    rec = RunRecord(
        query_id=query["query_id"], config="C_pre_retrieval_rbac",
        user_id=user.user_id, expected=query["expected"],
        category=query["category"], k=k, embedding_mode=embedder.mode,
    )
    t0 = timer()
    all_docs = list(docs_by_id.values())
    all_ids = list(docs_by_id.keys())
    t_a0 = timer()
    scope = authorized_ids(user, all_docs, policy)
    t_a1 = timer()
    rec.scope_size = len(scope)
    rec.lat_authz_ms = ms(t_a0, t_a1)
    qv = embedder.embed_one(query["text"])
    t1 = timer()
    ids, _ = index.search(qv, k, scope=scope)
    t2 = timer()
    violation = [did for did in ids if not allow(user, docs_by_id[did], policy).allowed]
    if violation:
        raise AssertionError(
            f"pre-retrieval contract violated: unauthorized docs in retrieval {violation}"
        )
    rec.candidate_ids = ids
    rec.context_ids = list(ids)
    rec.lat_retrieval_ms = ms(t1, t2)
    context_texts = [docs_by_id[did].content for did in ids if did in docs_by_id]
    gen = provider.generate(query["text"], context_texts)
    t3 = timer()
    rec.answer = gen.answer
    rec.provider = gen.provider
    rec.lat_gen_ms = ms(t2, t3)
    rec.lat_total_ms = ms(t0, t3)

    decisions = [allow(user, docs_by_id[did], policy) for did in all_ids]
    rec.decisions = [d.to_dict() for d in decisions]
    if audit is not None:
        for dec in decisions:
            audit.log_decision(dec, query["query_id"], run_id)
        audit.log_run(rec.query_id, "C_pre_retrieval_rbac", query["query_id"],
                      user.user_id, lat_authz_ms=rec.lat_authz_ms,
                      lat_retrieval_ms=rec.lat_retrieval_ms, lat_gen_ms=rec.lat_gen_ms,
                      lat_audit_ms=0.0, k=k, scope_size=len(scope))
    return rec