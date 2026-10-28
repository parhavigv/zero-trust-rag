"""Audit store tests (Phase 7)."""
from __future__ import annotations

import sqlite3

import pytest

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
    with AuditStore(tmp_path / "audit.db") as db:
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
    with AuditStore(tmp_path / "audit.db") as db:
        db.log_run("run-Q-009", "B_retrieve_then_filter", "Q-009", "bob",
                   lat_authz_ms=2.5, lat_retrieval_ms=1.0, lat_gen_ms=0.5,
                   lat_audit_ms=0.1, k=5, scope_size=3)
        rows = db.runs_for_config("B_retrieve_then_filter")
        assert len(rows) == 1
        assert rows[0]["query_id"] == "Q-009"


def test_count_decisions(tmp_path):
    with AuditStore(tmp_path / "audit.db") as db:
        db.log_decision(_decision("HR-0004"), "Q-1", "r1")
        db.log_decision(_decision("HR-0005"), "Q-1", "r1")
        db.log_decision(_decision("HR-0004", allowed=True), "Q-2", "r2")
        assert db.count_decisions() == 3


def test_inserts_accumulate(tmp_path):
    with AuditStore(tmp_path / "audit.db") as db:
        for _ in range(5):
            db.log_decision(_decision("HR-0004"), "Q-9", "r9")
        assert db.count_decisions() == 5


def test_decisions_reject_update_and_delete(tmp_path):
    with AuditStore(tmp_path / "audit.db") as db:
        db.log_decision(_decision(), "Q-009", "run-Q-009")
        conn = db._connect()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE decisions SET allowed = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM decisions")
        assert db.count_decisions() == 1
        row = db.decisions_for_query("Q-009")[0]
        assert row["allowed"] == 0


def test_runs_reject_update_and_delete(tmp_path):
    with AuditStore(tmp_path / "audit.db") as db:
        db.log_run("run-Q-009", "C_pre_retrieval", "Q-009", "bob")
        conn = db._connect()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE runs SET user_id = 'eve'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM runs")
        rows = db.runs_for_config("C_pre_retrieval")
        assert len(rows) == 1
        assert rows[0]["user_id"] == "bob"


def test_existing_db_gains_append_only_triggers(tmp_path):
    db_path = tmp_path / "audit.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE decisions (d_id INTEGER PRIMARY KEY, allowed INTEGER)")
    conn.execute("INSERT INTO decisions (allowed) VALUES (0)")
    conn.commit()
    conn.close()

    with AuditStore(db_path) as db:
        conn = db._connect()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM decisions")
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
