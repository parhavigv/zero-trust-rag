"""Shared data model: User, Document, Decision."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class User:
    user_id: str
    name: str
    role: str
    department: str
    tenant_id: str
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        return cls(
            user_id=d["user_id"],
            name=d["name"],
            role=d["role"],
            department=d["department"],
            tenant_id=d["tenant_id"],
            enabled=bool(d.get("enabled", True)),
        )

    def effective_permissions(self) -> list[str]:
        """Derived, single-source-of-truth permission view (never stored)."""
        perms = ["retrieve"]
        if self.department:
            perms.append(f"{self.department}:internal:read")
        perms.append(f"role:{self.role}")
        perms.append("public:read")
        return perms


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    department: str
    classification: str
    allowed_roles: tuple[str, ...]
    owner: str
    tenant_id: str
    created_at: str
    sensitivity_level: str
    content: str

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(
            document_id=d["document_id"],
            title=d["title"],
            department=d["department"],
            classification=d["classification"],
            allowed_roles=tuple(d.get("allowed_roles", [])),
            owner=d.get("owner", ""),
            tenant_id=d.get("tenant_id", ""),
            created_at=d.get("created_at", ""),
            sensitivity_level=d.get("sensitivity_level", "LOW"),
            content=d.get("content", ""),
        )


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule_id: str
    reason: str
    effector: str = ""
    subject: str = ""
    subject_role: str = ""
    subject_department: str = ""
    object: str = ""
    object_department: str = ""
    object_classification: str = ""
    object_tenant: str = ""
    tenant_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "effector": self.effector,
            "subject": self.subject,
            "subject_role": self.subject_role,
            "subject_department": self.subject_department,
            "object": self.object,
            "object_department": self.object_department,
            "object_classification": self.object_classification,
            "object_tenant": self.object_tenant,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
        }


CLASSIFICATIONS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")


def load_json(path) -> list[dict] | dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)