"""Deny-by-default RBAC policy engine.

Implements the rule ordering documented in docs/rbac-policy-model.md.
The same allow()/authorized_ids() primitives are consumed by configurations B
(retrieve-then-filter) and C (pre-retrieval RBAC); only the place of
application differs.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Iterable

from backend.models import Decision, Document, User
from backend.rbac.attr_predicates import satisfies


class PolicyError(Exception):
    pass


@dataclass
class Override:
    role: str
    department: str
    classifications: tuple[str, ...] = ("CONFIDENTIAL", "RESTRICTED")
    note: str = ""


@dataclass
class Policy:
    version: str
    rules: dict = field(default_factory=dict)
    overrides: list[Override] = field(default_factory=list)
    attr_mode: bool = False
    source_path: str = ""

    @classmethod
    def load(cls, path) -> "Policy":
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        overrides = [
            Override(
                role=o["role"],
                department=o["department"],
                classifications=tuple(o.get("classifications", ["CONFIDENTIAL", "RESTRICTED"])),
                note=o.get("note", ""),
            )
            for o in raw.get("overrides", [])
        ]
        return cls(
            version=raw.get("version", "1"),
            rules=raw.get("rules", {}),
            overrides=overrides,
            attr_mode=bool(raw.get("attr_mode", False)),
            source_path=str(path),
        )

    def ruleset(self) -> dict:
        return {
            "tenant_scope": self.rules.get("tenant_scope", "strict"),
            "public": self.rules.get("public", "all"),
            "internal": self.rules.get("internal", "same_department"),
            "confidential": self.rules.get("confidential", "explicit_allowed_roles"),
            "restricted": self.rules.get("restricted", "explicit_allowed_roles"),
        }


def allow(user: User, doc: Document, policy: Policy, now: str = "") -> Decision:
    """Deterministic authorization decision. First-match-wins rule order."""
    ts = now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def dec(allowed: bool, rule: str, reason: str, effector: str) -> Decision:
        return Decision(
            allowed=allowed,
            rule_id=rule,
            reason=reason,
            effector=effector,
            subject=user.user_id,
            subject_role=user.role,
            subject_department=user.department,
            object=doc.document_id,
            object_department=doc.department,
            object_classification=doc.classification,
            object_tenant=doc.tenant_id,
            tenant_id=user.tenant_id,
            timestamp=ts,
        )

    # Rule 1 — tenant scope (hard deny on mismatch)
    if doc.tenant_id != user.tenant_id:
        return dec(False, "rule1", "cross-tenant access denied", "tenant_id")

    # Rule 2 — enabled check
    if not user.enabled:
        return dec(False, "rule2", "account disabled", "user.enabled")

    rules = policy.ruleset()

    # ABAC gate (Section F, eq. 2): when attribute mode is enabled, a coarse
    # RBAC grant below is only sufficient if the document's attributes also
    # satisfy the user's attribute predicates. We evaluate it once and reuse it
    # across the grant rules so the conjunction is exactly one ABAC clause.
    if policy.attr_mode:
        attr_ok, attr_results = satisfies(user, doc, now=ts)

        def gate(rule: str, eff: str) -> Decision | None:
            if attr_ok:
                return None
            return dec(False, f"{rule}+abac", "ABAC predicate failed: "
                       + "; ".join(f"{r.reason}" for r in attr_results.values() if not r.satisfied), eff)
    else:
        # Rule 4 — PUBLIC (tenant match already required)
        if doc.classification == "PUBLIC" and rules["public"] == "all":
            return dec(True, "rule4", "public document, tenant match", "classification")

        # Rule 5 — INTERNAL same-department
        if doc.classification == "INTERNAL" and rules["internal"] == "same_department":
            if user.department == doc.department:
                return dec(True, "rule5", "internal, same department", "department")
            return dec(False, "rule5", "internal, cross-department", "department")

        # Rule 6 — CONFIDENTIAL / RESTRICTED via explicit allowed_roles
        # Rule 7 — override. Rule 8 — deny by default.
        if doc.classification in ("CONFIDENTIAL", "RESTRICTED"):
            if user.role in doc.allowed_roles:
                return dec(True, "rule6", f"role {user.role} in allowed_roles", "allowed_roles")
            for ov in policy.overrides:
                if ov.role == user.role and ov.department == doc.department and doc.classification in ov.classifications:
                    return dec(True, "rule7", f"override {ov.role}@{ov.department}", "override")
            return dec(False, "rule8", f"role {user.role} not allowed for {doc.classification}", "allowed_roles")

        # Rule 7 — policy override (non-confidential path)
        for ov in policy.overrides:
            if ov.role == user.role and ov.department == doc.department and doc.classification in ov.classifications:
                return dec(True, "rule7", f"override {ov.role}@{ov.department}", "override")

        # Rule 3/8 — deny by default
        return dec(False, "rule8", "deny by default", "classification")

    # ---- Attribute-mode path: resolve the RBAC grant, then AND it with the
    #      attribute predicate (eq-2: exists role grant AND attributes hold).
    def with_attr(rule: str, eff: str) -> Decision:
        g = gate(rule, eff)
        if g is not None:
            return g
        return dec(True, f"{rule}+abac", "grant + attributes satisfied", eff)

    if doc.classification == "PUBLIC" and rules["public"] == "all":
        return with_attr("rule4", "classification")

    if doc.classification == "INTERNAL" and rules["internal"] == "same_department":
        if user.department != doc.department:
            return dec(False, "rule5", "internal, cross-department", "department")
        return with_attr("rule5", "department")

    if doc.classification in ("CONFIDENTIAL", "RESTRICTED"):
        if user.role in doc.allowed_roles:
            return with_attr("rule6", "allowed_roles")
        for ov in policy.overrides:
            if ov.role == user.role and ov.department == doc.department and doc.classification in ov.classifications:
                return with_attr("rule7", "override")
        return dec(False, "rule8", f"role {user.role} not allowed for {doc.classification}", "allowed_roles")

    return dec(False, "rule8", "deny by default", "classification")


def authorized_ids(user: User, docs: Iterable[Document], policy: Policy) -> set[str]:
    """C: pre-retrieval authorized candidate set (set of document_ids)."""
    return {d.document_id for d in docs if allow(user, d, policy).allowed}


def authorize_documents(user: User, docs: Iterable[Document], policy: Policy) -> tuple[list[Document], list[Decision]]:
    """B: evaluate every candidate; returns (allowed_docs, all decisions)."""
    allowed: list[Document] = []
    decisions: list[Decision] = []
    for d in docs:
        dec = allow(user, d, policy)
        decisions.append(dec)
        if dec.allowed:
            allowed.append(d)
    return allowed, decisions