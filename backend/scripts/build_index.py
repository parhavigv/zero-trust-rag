"""Embed + build the FAISS index over the corpus (Phase 4).

Run: python -m backend.scripts.build_index
"""
from __future__ import annotations

from backend.config import INDEX_DIR, SEED
from backend.io import load_documents
from backend.retrieval.embedder import Embedder
from backend.retrieval.index import RagIndex

if __name__ == "__main__":
    docs = load_documents()
    docs = sorted(docs, key=lambda d: d.document_id)
    texts = [d.title + ". " + d.content for d in docs]
    embedder = Embedder()
    vectors = embedder.encode(texts)
    print(f"embedding_mode={embedder.mode} vectors={vectors.shape}")
    index = RagIndex.build(vectors, [d.document_id for d in docs])
    index.save(INDEX_DIR)
    print(f"index saved: {len(index.ids)} docs -> {INDEX_DIR}")