"""Shared pytest fixtures. Regenerates the corpus once if it is missing."""
from __future__ import annotations

import pytest

from backend.config import DOCUMENTS_DIR, QUERIES_FILE
from backend.io import load_documents, load_policy, load_queries, load_users
from backend.retrieval.embedder import Embedder
from backend.retrieval.index import RagIndex


@pytest.fixture(scope="session")
def corpus():
    if not QUERIES_FILE.exists() or not any(DOCUMENTS_DIR.glob("*.json")):
        from backend.scripts.build_corpus import main as build

        build()
    docs = load_documents()
    users = load_users()
    policy = load_policy()
    queries = load_queries()
    docs_by_id = {d.document_id: d for d in docs}
    users_by_id = {u.user_id: u for u in users}
    queries_by_id = {q["query_id"]: q for q in queries}
    return {
        "docs": docs,
        "docs_by_id": docs_by_id,
        "users": users,
        "users_by_id": users_by_id,
        "policy": policy,
        "queries": queries,
        "queries_by_id": queries_by_id,
    }


@pytest.fixture(scope="session")
def hash_retriever(corpus):
    embedder = Embedder(force_hash=True)
    vectors = embedder.encode([d.title + ". " + d.content for d in corpus["docs"]])
    index = RagIndex.build(vectors, [d.document_id for d in corpus["docs"]])
    return {"embedder": embedder, "index": index}