"""Run experiments A/B/C over the full query set (Phase 10).

Run:  python -m experiments.run_all [--configs A,B,C] [--provider extractive]
Writes per-query RunRecords under results/runs/<CONFIG>/<QUERY>.json.
"""
from __future__ import annotations

import argparse

from backend.audit.store import AuditStore
from backend.config import AUDIT_DB, K_CAND, RUNS_DIR, TOP_K
from backend.generation.provider import make_provider
from backend.io import load_documents, load_policy, load_queries, load_users, user_by_id
from backend.retrieval.embedder import Embedder
from backend.retrieval.index import RagIndex
from experiments.baseline.run import run_a
from experiments.pre_retrieval_rbac.run import run_c
from experiments.retrieve_then_filter.run import run_b

RUNNERS = {
    "A": run_a,
    "B": run_b,
    "C": run_c,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="A,B,C")
    ap.add_argument("--provider", default="extractive")
    ap.add_argument("--k", type=int, default=TOP_K)
    ap.add_argument("--k-cand", type=int, default=K_CAND)
    ap.add_argument("--no-audit", action="store_true", help="do not write to the audit store")
    args = ap.parse_args()

    docs = load_documents()
    users = load_users()
    policy = load_policy()
    queries = load_queries()
    docs_by_id = {d.document_id: d for d in docs}
    users_by_id = {u.user_id: u for u in users}
    queries_by_id = {q["query_id"]: q for q in queries}

    embedder = Embedder()
    vectors = embedder.encode([d.title + ". " + d.content for d in docs])
    index = RagIndex.build(vectors, [d.document_id for d in docs])
    print(f"embedding_mode={embedder.mode} corpus={len(docs)}")

    audit = None if args.no_audit else AuditStore(AUDIT_DB)
    provider = make_provider(args.provider)

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    for q in queries:
        user = user_by_id(users, q["as_user"])
        run_id = f"run-{q['query_id']}"
        for cfg in configs:
            runner = RUNNERS[cfg]
            rec = runner(q, user, index, embedder, provider, docs_by_id,
                         policy=policy, k=args.k,
                         k_cand=args.k_cand,
                         audit=audit, run_id=run_id)
            rec.save(RUNS_DIR / rec.config / f"{q['query_id']}.json")
        print(f"{q['query_id']} [{user.user_id}] {q['category']} {q['expected']}")

    if audit is not None:
        audit.close()
    print(f"records -> {RUNS_DIR}")


if __name__ == "__main__":
    main()