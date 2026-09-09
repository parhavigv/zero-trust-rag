"""Scoped-search tests: scope is a hard constraint, never a post-hoc mask."""
from __future__ import annotations

import numpy as np

from backend.retrieval.index import RagIndex


def _index():
    vectors = np.array(
        [[1.0, 0.0, 0.0], [0.99, 0.14, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
    )
    return RagIndex.build(vectors, ["a", "b", "c"])


def test_full_search_returns_all_in_order():
    idx = _index()
    ids, scores = idx.search(np.array([[1.0, 0.01, 0.0]]), 3, scope=None)
    assert ids == ["a", "b", "c"]


def test_scoped_search_excludes_out_of_scope_nearest():
    idx = _index()
    ids, _ = idx.search(np.array([[1.0, 0.01, 0.0]]), 3, scope={"b", "c"})
    assert "a" not in ids
    assert ids[0] == "b"


def test_scoped_search_respects_k():
    idx = _index()
    ids, _ = idx.search(np.array([[1.0, 0.01, 0.0]]), 1, scope={"b", "c"})
    assert len(ids) == 1


def test_empty_scope_returns_nothing():
    idx = _index()
    ids, scores = idx.search(np.array([[1.0, 0.0, 0.0]]), 3, scope=set())
    assert ids == []
    assert scores == []