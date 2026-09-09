"""LLM provider abstraction.

- extractive: deterministic sentence selection from context (no model), used as
  the default reproducible provider. It exercises the metric pipeline but is
  explicitly *not* a real LLM; generation metrics (G1–G3) computed from it are
  labelled "extractive baseline, real-model evaluation pending".
- noop: empty answers (context-level metrics only).
- A real-model provider (e.g. Ollama) can be plugged in via the same interface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GenerationResult:
    answer: str
    provider: str
    meta: dict


class NoopProvider:
    def __init__(self, why: str = ""):
        self.why = why

    def generate(self, question: str, context: list[str]) -> GenerationResult:
        return GenerationResult(answer="", provider="noop", meta={"note": self.why})


class ExtractiveProvider:
    """Returns the context sentence with the highest lexical overlap to the query."""

    def _score(self, query_tokens: set[str], sentence: str) -> int:
        toks = set(re.findall(r"[a-z0-9]+", sentence.lower()))
        return len(query_tokens & toks)

    def generate(self, question: str, context: list[str]) -> GenerationResult:
        qt = set(re.findall(r"[a-z0-9]+", question.lower()))
        best, best_score = "", -1
        for chunk in context:
            for sent in re.split(r"(?<=[.!?])\s+", chunk):
                s = self._score(qt, sent)
                if s > best_score:
                    best, best_score = sent, s
        return GenerationResult(
            answer=best,
            provider="extractive",
            meta={"mode": "extractive-baseline", "top_score": best_score},
        )


def make_provider(kind: str = "extractive") -> object:
    if kind == "noop":
        return NoopProvider(why="no LLM configured")
    return ExtractiveProvider()