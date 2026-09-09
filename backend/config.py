"""Path configuration — single source of truth for data/result locations."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("ZTRUST_DATA", ROOT / "data"))
DOCUMENTS_DIR = DATA_DIR / "documents"
USERS_FILE = DATA_DIR / "users" / "users.json"
QUERIES_FILE = DATA_DIR / "queries" / "queries.json"
POLICIES_FILE = DATA_DIR / "policies" / "policies.json"
INDEX_DIR = DATA_DIR / "index"
INDEX_FILE = INDEX_DIR / "index.faiss"
IDMAP_FILE = INDEX_DIR / "id_map.json"

RESULTS_DIR = Path(os.environ.get("ZTRUST_RESULTS", ROOT / "results"))
RUNS_DIR = RESULTS_DIR / "runs"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_FILE = RESULTS_DIR / "comparison.md"

AUDIT_DB = DATA_DIR / "audit.db"

EMBEDDING_MODEL = os.environ.get("ZTRUST_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOP_K = int(os.environ.get("ZTRUST_TOP_K", "5"))
K_CAND = int(os.environ.get("ZTRUST_K_CAND", "10"))
SEED = int(os.environ.get("ZTRUST_SEED", "20260908"))