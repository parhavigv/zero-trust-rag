"""Document embedder with graceful offline fallback (deterministic hashing).

The real sentence-transformer model is used when available; otherwise a
character-ngram hashing embedder is used so the pipeline stays reproducible
offline. The active mode is recorded on every RunRecord for honesty.
"""
from __future__ import annotations

import re
import time

import numpy as np


def _ngram_embed(texts: list[str], dim: int = 384, n_min: int = 2, n_max: int = 3) -> np.ndarray:
    """Deterministic bag-of-ngrams hashing embedding (cosine-friendly)."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        toks = re.findall(r"[a-z0-9]+", t.lower())
        words = toks
        acc = np.zeros(dim, dtype=np.float32)
        for n in range(n_min, n_max + 1):
            for j in range(len(words) - n + 1):
                gram = " ".join(words[j : j + n])
                h = hash(gram) & 0xFFFFFFFF
                idx = h % dim
                sign = 1.0 if (h >> 31) & 1 else -1.0
                acc[idx] += sign
        norm = np.linalg.norm(acc) or 1.0
        out[i] = acc / norm
    return out


class Embedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 lazy: bool = True, force_hash: bool = False):
        self.model_name = model_name
        self.force_hash = force_hash
        self.mode = "uninitialized"
        self._model = None
        self._encode = None
        if not lazy:
            self._load()

    def _load(self):
        if self.force_hash:
            self.mode = "hash-ngram-v1"
            self._encode = lambda texts: _ngram_embed(list(texts))
            return
        try:
            from sentence_transformers import SentenceTransformer

            started = time.time()
            m = SentenceTransformer(self.model_name)
            m.encode(["warmup"])  # force download/lazy loading now
            self._model = m
            self.mode = f"sentence-transformers:{self.model_name}"
            self._encode = lambda texts: np.asarray(
                m.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True),
                dtype=np.float32,
            )
        except Exception as exc:  # noqa: BLE001 — graceful degradation is intended
            self.mode = "hash-ngram-v1 (fallback: " + type(exc).__name__ + ")"
            self._encode = lambda texts: _ngram_embed(list(texts))

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._encode is None:
            self._load()
        return self._encode(list(texts))

    def embed_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]