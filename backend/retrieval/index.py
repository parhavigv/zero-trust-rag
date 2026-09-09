"""FAISS index with honest scoped (subset) search.

Scoped search builds a temporary index over exactly the authorized vectors and
searches that — never searching the full index then masking (which would leak
unauthorized candidates into ranking).
"""
from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from backend.config import IDMAP_FILE, INDEX_DIR, INDEX_FILE


class RagIndex:
    def __init__(self, vectors: np.ndarray, doc_ids: list[str]):
        self.dim = vectors.shape[1]
        self.ids = list(doc_ids)
        self.vec = np.asarray(vectors, dtype=np.float32)
        norm = np.linalg.norm(self.vec, axis=1, keepdims=True)
        self.norm = norm
        self.id_to_pos = {did: i for i, did in enumerate(self.ids)}
        self.index = self._build_full_index()

    def _build_full_index(self) -> faiss.Index:
        v = self.vec
        faiss.normalize_L2(v)
        self.vec = v
        idx = faiss.IndexFlatIP(self.dim)
        ids_int = np.arange(len(self.ids), dtype=np.int64)
        idx2 = faiss.IndexIDMap2(idx)
        idx2.add_with_ids(self.vec, ids_int)
        return idx2

    def _search_full(self, qv: np.ndarray, k: int) -> tuple[list[str], list[float]]:
        q = np.asarray(qv, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        faiss.normalize_L2(q)
        scores, idxs = self.index.search(q, min(k, len(self.ids)))
        hit_ids: list[str] = []
        hit_scores: list[float] = []
        for i, score in zip(idxs[0], scores[0]):
            if i < 0:
                continue
            hit_ids.append(self.ids[int(i)])
            hit_scores.append(float(score))
        return hit_ids, hit_scores

    def _search_scoped(self, qv: np.ndarray, k: int, scope: set[str] | list[str]) -> tuple[list[str], list[float]]:
        pos = [self.id_to_pos[did] for did in scope if did in self.id_to_pos]
        if not pos:
            return [], []
        sub = self.vec[pos]  # already L2-normalized
        tmp = faiss.IndexFlatIP(self.dim)
        tmp.add(sub)
        q = np.asarray(qv, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        faiss.normalize_L2(q)
        scores, idxs = tmp.search(q, min(k, len(pos)))
        hit_ids: list[str] = []
        hit_scores: list[float] = []
        for i, score in zip(idxs[0], scores[0]):
            if i < 0:
                continue
            hit_ids.append(self.ids[pos[int(i)]])
            hit_scores.append(float(score))
        return hit_ids, hit_scores

    def search(self, qv: np.ndarray, k: int, scope: set[str] | None = None) -> tuple[list[str], list[float]]:
        """Returns (doc_ids ranked best-to-worst, cosine scores)."""
        if scope is None:
            return self._search_full(qv, k)
        return self._search_scoped(qv, k, set(scope))

    @classmethod
    def build(cls, vectors: np.ndarray, doc_ids: list[str]) -> "RagIndex":
        return cls(vectors, doc_ids)

    def save(self, directory: Path = INDEX_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "index.faiss"))
        with open(directory / "id_map.json", "w", encoding="utf-8") as fh:
            json.dump({"ids": self.ids, "dim": self.dim}, fh)

    @classmethod
    def load(cls, directory: Path = INDEX_DIR) -> "RagIndex":
        idx = faiss.read_index(str(directory / "index.faiss"))
        with open(directory / "id_map.json", "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        obj = cls.__new__(cls)
        obj.dim = meta["dim"]
        obj.ids = list(meta["ids"])
        obj.index = idx
        obj.id_to_pos = {did: i for i, did in enumerate(obj.ids)}
        obj.vec = np.zeros((len(obj.ids), obj.dim), dtype=np.float32)
        obj.norm = np.ones((len(obj.ids), 1), dtype=np.float32)
        return obj