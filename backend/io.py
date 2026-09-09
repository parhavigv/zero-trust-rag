"""Loaders for corpus / users / policies from data/."""
from __future__ import annotations

import json
from typing import Union

from backend.config import DOCUMENTS_DIR, POLICIES_FILE, QUERIES_FILE, USERS_FILE
from backend.models import Document, User
from backend.rbac.engine import Policy


def load_documents() -> list[Document]:
    docs: list[Document] = []
    for path in sorted(DOCUMENTS_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            docs.append(Document.from_dict(json.load(fh)))
    return docs


def load_users() -> list[User]:
    with open(USERS_FILE, "r", encoding="utf-8") as fh:
        return [User.from_dict(d) for d in json.load(fh)]


def load_policy() -> Policy:
    return Policy.load(POLICIES_FILE)


def load_queries() -> list[dict]:
    with open(QUERIES_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def user_by_id(users: list[User], user_id: str) -> Union[User, None]:
    for u in users:
        if u.user_id == user_id:
            return u
    return None