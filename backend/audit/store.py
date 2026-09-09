"""Authorization audit store (SQLite). Append-only, reconstructable."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class AuditStore:
    """Append-only decision and run records backed by SQLite."""

    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                d_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT, run_id TEXT,
                subject TEXT, subject_role TEXT, subject_department TEXT,
                object TEXT, object_department TEXT, object_classification TEXT,
                object_tenant TEXT, tenant_id TEXT,
                allowed INTEGER, rule_id TEXT, reason TEXT, effector TEXT,
                ts TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                r_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT, config TEXT, query_id TEXT, user_id TEXT,
                ts TEXT, lat_authz_ms REAL, lat_retrieval_ms REAL,
                lat_gen_ms REAL, lat_audit_ms REAL, k INTEGER, scope_size INTEGER
            )
            """
        )
        conn.commit()

    def log_decision(self, decision, query_id: str, run_id: str):
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO decisions
              (query_id, run_id, subject, subject_role, subject_department,
               object, object_department, object_classification, object_tenant,
               tenant_id, allowed, rule_id, reason, effector, ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                query_id, run_id,
                decision.subject, decision.subject_role, decision.subject_department,
                decision.object, decision.object_department, decision.object_classification,
                decision.object_tenant, decision.tenant_id,
                int(decision.allowed), decision.rule_id, decision.reason,
                decision.effector, decision.timestamp,
            ),
        )
        conn.commit()
        self._flush_runs_if_due()

    def log_run(self, run_id, config, query_id, user_id, lat_authz_ms=-1.0,
                lat_retrieval_ms=-1.0, lat_gen_ms=-1.0, lat_audit_ms=-1.0,
                k=0, scope_size=-1):
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO runs
              (run_id, config, query_id, user_id, ts, lat_authz_ms, lat_retrieval_ms,
               lat_gen_ms, lat_audit_ms, k, scope_size)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id, config, query_id, user_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                lat_authz_ms, lat_retrieval_ms, lat_gen_ms, lat_audit_ms, k, scope_size,
            ),
        )
        conn.commit()

    def _flush_runs_if_due(self):
        pass

    def decisions_for_query(self, query_id: str) -> list[dict]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM decisions WHERE query_id = ? ORDER BY d_id", (query_id,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def runs_for_config(self, config: str) -> list[dict]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM runs WHERE config = ? ORDER BY r_id", (config,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def count_decisions(self) -> int:
        conn = self._connect()
        return conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None