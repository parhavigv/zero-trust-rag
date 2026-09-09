"""Audit store tests (Phase 7)."""
from __future__ import annotations

from backend.audit.store import AuditStore
from backend.models import Decision


def _decision(oid="HR-0004", allowed=False):
    return Decision(
        allowed=allowed, rule_id="rule6", reason="role not in allowed_roles",
        effector="allowed_roles", subject="bob", subject_role="ENGINEER",
        subject_department="Engineering", object=oid, object_department="HR",
        object_classification="CONFIDENTIAL", object_tenant="tenant-acme",
        tenant_id="tenant-acme", timestamp="2026-09-08T00:00:00Z",
    )


def test_decision_roundtrip(tmp_path):
    db = AuditStore(tmp_path / "audit.db")
    db.log_decision(_decision(), "Q-009", "run-Q-009")
    rows = db.decisions_for_query("Q-009")
    assert len(rows) == 1
    row = rows[0]
    assert row["subject"] == "bob"
    assert row["object"] == "HR-0004"
    assert row["allowed"] == 0
    assert row["rule_id"] == "rule6"
    assert row["reason"]
    assert row["ts"]


def test_run_record(tmp_path):
    db = AuditStore(tmp_path / "audit.db")
    db.log_run("run-Q-009", "B_retrieve_then_filter", "Q-009", "bob",
               lat_authz_ms=2.5, lat_retrieval_ms=1.0, lat_gen_ms=0.5,
               lat_audit_ms=0.1, k=5, scope_size=3)
    rows = db.runs_for_config("B_retrieve_then_filter")
    assert len(rows) == 1
    assert rows[0]["query_id"] == "Q-009"


def test_count_decisions(tmp_path):
    db = AuditStore(tmp_path / "audit.db")
    db.log_decision(_decision("HR-0004"), "Q-1", "r1")
    db.log_decision(_decision("HR-0005"), "Q-1", "r1")
    db.log_decision(_decision("HR-0004", allowed=True), "Q-2", "r2")
    assert db.count_decisions() == 3


def test_append_only(tmp_path):
    db = AuditStore(tmp_path / "audit.db")
    for _ in range(5):
        db.log_decision(_decision("HR-0004"), "Q-9", "r9")
    assert db.count_decisions() == 5