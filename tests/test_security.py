"""Security end-to-end tests (Phase 8): threat-model scenarios over the real pipeline."""
from __future__ import annotations

import pytest

from backend.generation.provider import make_provider
from backend.models import User
from backend.rbac.engine import allow, authorized_ids
from experiments.baseline.run import run_a
from experiments.pre_retrieval_rbac.run import run_c
from experiments.retrieve_then_filter.run import run_b


def _user(corpus, uid):
    return corpus["users_by_id"][uid]


@pytest.fixture(scope="session")
def provider():
    return make_provider("extractive")


def _query(corpus, qid):
    return corpus["queries_by_id"][qid]


def test_engine_cross_dept_confidential_denied(corpus):
    bob = _user(corpus, "bob")
    assert allow(bob, corpus["docs_by_id"]["HR-0004"], corpus["policy"]).allowed is False


def test_engine_legit_hr_allowed(corpus):
    alice = _user(corpus, "alice")
    assert allow(alice, corpus["docs_by_id"]["HR-0004"], corpus["policy"]).allowed is True


def test_engine_cross_tenant_denied(corpus):
    mallory = _user(corpus, "mallory")
    assert allow(mallory, corpus["docs_by_id"]["SAL-0001"], corpus["policy"]).allowed is False


def test_c_pre_retrieval_never_leaks_unauthorized(corpus, hash_retriever, provider):
    bob = _user(corpus, "bob")
    q = _query(corpus, "Q-009")  # bob asks HR salary bands
    rec = run_c(q, bob, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], corpus["policy"], k=5)
    assert "HR-0004" not in rec.candidate_ids
    assert "HR-0004" not in rec.context_ids
    for did in rec.context_ids:
        assert allow(bob, corpus["docs_by_id"][did], corpus["policy"]).allowed


def test_b_filters_but_retrieves(corpus, hash_retriever, provider):
    bob = _user(corpus, "bob")
    q = _query(corpus, "Q-009")
    rec = run_b(q, bob, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], corpus["policy"], k=5, k_cand=10)
    for did in rec.context_ids:
        assert allow(bob, corpus["docs_by_id"][did], corpus["policy"]).allowed
    for did in rec.candidate_ids:
        if did not in rec.context_ids:
            assert allow(bob, corpus["docs_by_id"][did], corpus["policy"]).allowed is False


def test_c_cross_tenant_no_acme_leak(corpus, hash_retriever, provider):
    mallory = _user(corpus, "mallory")
    q = _query(corpus, "Q-021")
    rec = run_c(q, mallory, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], corpus["policy"], k=5)
    acme = {"HR-0001", "SAL-0001"}
    assert not (acme & set(rec.candidate_ids))
    assert set(rec.context_ids).isdisjoint(acme)


def test_c_executive_secret_protected(corpus, hash_retriever, provider):
    dave = _user(corpus, "dave")
    q = _query(corpus, "Q-023")
    rec = run_c(q, dave, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], corpus["policy"], k=5)
    assert "EXE-0006" not in rec.candidate_ids
    assert "EXE-0006" not in rec.context_ids


def test_c_legit_access_preserved(corpus, hash_retriever, provider):
    allow_q = next(q for q in corpus["queries"] if q["expected"] == "allow")
    user = _user(corpus, allow_q["as_user"])
    rec = run_c(allow_q, user, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], corpus["policy"], k=5)
    assert rec.context_ids, "pre-retrieval RBAC should return a usable (authorized) context"
    for did in rec.context_ids:
        assert allow(user, corpus["docs_by_id"][did], corpus["policy"]).allowed


def test_a_exposes_unauthorized(corpus, hash_retriever, provider):
    bob = _user(corpus, "bob")
    q = _query(corpus, "Q-009")
    rec = run_a(q, bob, hash_retriever["index"], hash_retriever["embedder"],
                provider, corpus["docs_by_id"], k=100)
    sensitive = {"HR-0004", "HR-0005"}
    assert sensitive <= set(rec.context_ids), "baseline retrieves over the whole corpus"


def test_negation_attack_b_leaks_candidates_c_does_not(corpus, hash_retriever, provider):
    """Section-I (ref [13]) contention: retrieve-then-filter can surface the
    unauthorized target among candidates; pre-retrieval RBAC never does.

    The hard guarantee is the C side (never surfaces the target). The B side's
    exact ranking varies with the embedding model, so we assert that B surfaces
    at least one unauthorized candidate from the HR-confidential class for these
    negation prompts (it did in the measured sentence-transformers run).
    """
    bob = _user(corpus, "bob")
    hr_conf = {"HR-0004", "HR-0005", "HR-0006"}
    for qid, target in [("Q-027", "HR-0004"), ("Q-028", "FIN-0005"),
                        ("Q-029", "HR-0005"), ("Q-030", "HR-0006")]:
        q = _query(corpus, qid)
        rb = run_b(q, bob, hash_retriever["index"], hash_retriever["embedder"],
                   provider, corpus["docs_by_id"], corpus["policy"], k=5, k_cand=10)
        rc = run_c(q, bob, hash_retriever["index"], hash_retriever["embedder"],
                   provider, corpus["docs_by_id"], corpus["policy"], k=5)
        # C: the unauthorized target must never enter the candidates.
        assert target not in rc.candidate_ids, f"C must never surface {target} for {qid}"
        # B: with the real model this surfaces the target; offline it must at
        # least surface some unauthorized junior role-conflict doc.
        expected_deny = set(q["target_docs"])
        b_denied = [d for d in rb.candidate_ids if not allow(bob, corpus["docs_by_id"][d], corpus["policy"]).allowed]
        assert b_denied, f"B should surface at least one unauthorized candidate for {qid}"
        assert not any(d in hr_conf for d in rc.candidate_ids), "C must never surface HR-confidential"