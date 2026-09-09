"""Metric implementation tests (Phase 9)."""
from __future__ import annotations

from backend.evaluation.metrics import aggregate, query_metrics
from backend.models import Document, User
from backend.rbac.engine import Policy
from experiments.common import RunRecord

PUB = Document(document_id="PUB-1", title="t", department="HR", classification="PUBLIC",
               allowed_roles=(), owner="o", tenant_id="tenant-acme", created_at="2025-01-01",
               sensitivity_level="LOW", content="Public onboarding FAQ for everyone.")
SEC = Document(document_id="SEC-1", title="t", department="HR", classification="CONFIDENTIAL",
               allowed_roles=("HR_MANAGER",), owner="o", tenant_id="tenant-acme",
               created_at="2025-01-01", sensitivity_level="HIGH",
               content="Confidential salary bands are 100k to 200k.")

docs_by_id = {PUB.document_id: PUB, SEC.document_id: SEC}
perm_hr = User(user_id="alice", name="A", role="HR_MANAGER", department="HR",
               tenant_id="tenant-acme")
perm_eng = User(user_id="bob", name="B", role="ENGINEER", department="Engineering",
                tenant_id="tenant-acme")
policy = Policy(version="1", rules={"tenant_scope": "strict", "public": "all",
                                    "internal": "same_department",
                                    "confidential": "explicit_allowed_roles",
                                    "restricted": "explicit_allowed_roles"})

q_allow = {"query_id": "Q-1", "expected": "allow", "category": "legit",
           "as_user": "alice", "target_docs": ["PUB-1", "SEC-1"],
           "gold_allowed_docs": ["PUB-1", "SEC-1"],
           "gold_answer_text": "Salary bands are confidential."}
q_deny = {"query_id": "Q-2", "expected": "deny", "category": "cross_dept_confidential",
          "as_user": "bob", "target_docs": ["SEC-1"], "gold_allowed_docs": [],
          "gold_answer_text": ""}


def _rec(qid, config, ctx, cands=None, decisions=None, lat_authz=1.0):
    return RunRecord(query_id=qid, config=config, user_id="x", expected="allow",
                     category="c", candidate_ids=cands or ctx, context_ids=ctx,
                     decisions=decisions or [], lat_authz_ms=lat_authz,
                     lat_retrieval_ms=2.0, lat_gen_ms=1.0, lat_total_ms=5.0, k=3,
                     scope_size=len(ctx), answer="", provider="extractive",
                     embedding_mode="test")


def test_s1_s2_unauthorized_context_counted():
    rec = _rec("Q-2", "C_pre_retrieval_rbac", ctx=["PUB-1"])  # SEC never in scope
    m = query_metrics(rec, perm_eng, docs_by_id, policy, q_deny)
    assert m["S1"] == 0.0
    assert m["S2"] == 0

    rec2 = _rec("Q-2", "B_retrieve_then_filter", ctx=["PUB-1"], cands=["PUB-1", "SEC-1"])
    m2 = query_metrics(rec2, perm_eng, docs_by_id, policy, q_deny)
    assert m2["S3"] == 1


def test_s6_denial_correctness():
    rec = _rec("Q-2", "C_pre_retrieval_rbac", ctx=["PUB-1"])
    m = query_metrics(rec, perm_eng, docs_by_id, policy, q_deny)
    assert m["S6"] == 1


def test_r1_recall_on_allow():
    rec = _rec("Q-1", "A_baseline", ctx=["PUB-1", "SEC-1"])
    m = query_metrics(rec, perm_hr, docs_by_id, policy, q_allow)
    assert m["R1"] == 1.0
    assert m["R2"] == 1.0


def test_r1_recall_partial():
    rec = _rec("Q-1", "A_baseline", ctx=["PUB-1"])
    m = query_metrics(rec, perm_hr, docs_by_id, policy, q_allow)
    assert m["R1"] == 0.5


def test_ndcg_ranks_gold_first():
    rec = _rec("Q-1", "A_baseline", ctx=["SEC-1", "PUB-1"])
    m = query_metrics(rec, perm_hr, docs_by_id, policy, q_allow)
    assert m["R3"] == 1.0


def test_aggregate_over_allow_and_deny():
    recs = [
        _rec("Q-1", "A_baseline", ctx=["PUB-1", "SEC-1"]),
        _rec("Q-2", "B_retrieve_then_filter", ctx=["PUB-1"], cands=["PUB-1", "SEC-1"]),
    ]
    users = {"alice": perm_hr, "bob": perm_eng}
    queries = {"Q-1": q_allow, "Q-2": q_deny}
    recs[0].user_id = "alice"
    recs[1].user_id = "bob"
    agg = aggregate(recs, users, docs_by_id, policy, queries)
    assert agg["n_queries"] == 2
    assert agg["n_allow"] == 1
    assert agg["n_deny"] == 1
    assert agg["R1_allow_only"] == 1.0
    assert agg["S6_denial_correct"] == 1.0
    assert agg["U2_reconstructable"] is not None


def test_missing_decision_breaks_reconstruction():
    rec = _rec("Q-1", "C_pre_retrieval_rbac", ctx=["PUB-1"],
               decisions=[{"object": "SEC-1", "subject": "x", "rule_id": "r", "reason": "z", "ts": "t"}])
    users = {"alice": perm_hr}
    queries = {"Q-1": q_allow}
    rec.user_id = "alice"
    agg = aggregate([rec], users, docs_by_id, policy, queries)
    assert agg["U2_reconstructable"] == 0.0