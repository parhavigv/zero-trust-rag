"""Shared experiment scaffolding: RunRecord + timing helpers."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class RunRecord:
    query_id: str
    config: str
    user_id: str
    expected: str
    category: str
    candidate_ids: list[str] = field(default_factory=list)
    context_ids: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    lat_authz_ms: float = 0.0
    lat_retrieval_ms: float = 0.0
    lat_gen_ms: float = 0.0
    lat_total_ms: float = 0.0
    k: int = 0
    scope_size: int = -1
    answer: str = ""
    provider: str = ""
    embedding_mode: str = ""

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "config": self.config,
            "user_id": self.user_id,
            "expected": self.expected,
            "category": self.category,
            "candidate_ids": self.candidate_ids,
            "context_ids": self.context_ids,
            "decisions": self.decisions,
            "lat_authz_ms": self.lat_authz_ms,
            "lat_retrieval_ms": self.lat_retrieval_ms,
            "lat_gen_ms": self.lat_gen_ms,
            "lat_total_ms": self.lat_total_ms,
            "k": self.k,
            "scope_size": self.scope_size,
            "answer": self.answer,
            "provider": self.provider,
            "embedding_mode": self.embedding_mode,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RunRecord":
        return cls(**d)

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)


def timer():
    return time.perf_counter()


def ms(t0: float, t1: float) -> float:
    return (t1 - t0) * 1000.0