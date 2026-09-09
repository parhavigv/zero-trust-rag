"""RBAC engine unit tests (Phase 3). Rule order matches docs/rbac-policy-model.md."""
from __future__ import annotations

import pytest

from backend.models import Document, User
from backend.rbac.engine import Override, Policy, allow, authorized_ids


def _policy(rules=None, overrides=None):
    return Policy(version="1", rules=rules or {}, overrides=overrides or [])


def _user(role="EMPLOYEE", dept="Sales", tenant="tenant-acme", enabled=True):
    return User(user_id="u", name="U", role=role, department=dept,
                tenant_id=tenant, enabled=enabled)


def _doc(did="D-0001", dept="Sales", cls="PUBLIC", roles=None, tenant="tenant-acme"):
    return Document(document_id=did, title="t", department=dept, classification=cls,
                    allowed_roles=tuple(roles or ()), owner="o", tenant_id=tenant,
                    created_at="2025-01-01", sensitivity_level="LOW", content="c")


def test_rule1_cross_tenant_denied():
    u = _user(tenant="tenant-acme")
    d = _doc(cls="PUBLIC", tenant="tenant-beta")
    dec = allow(u, d, _policy())
    assert not dec.allowed and dec.rule_id == "rule1"


def test_rule2_disabled_account_denied():
    u = _user(enabled=False)
    dec = allow(u, _doc(cls="PUBLIC"), _policy())
    assert not dec.allowed and dec.rule_id == "rule2"


def test_rule4_public_allowed():
    dec = allow(_user(), _doc(cls="PUBLIC"), _policy())
    assert dec.allowed and dec.rule_id == "rule4"


def test_rule5_internal_same_department_allowed():
    dec = allow(_user(dept="Sales"), _doc(cls="INTERNAL", dept="Sales"), _policy())
    assert dec.allowed and dec.rule_id == "rule5"


def test_rule5_internal_cross_department_denied():
    dec = allow(_user(dept="Engineering"), _doc(cls="INTERNAL", dept="Sales"), _policy())
    assert not dec.allowed and dec.rule_id == "rule5"


def test_rule6_confidential_role_allowed():
    dec = allow(_user(role="HR_MANAGER"),
                _doc(cls="CONFIDENTIAL", dept="HR", roles=["HR_MANAGER", "HR_ADMIN"]),
                _policy())
    assert dec.allowed and dec.rule_id == "rule6"


def test_rule6_confidential_role_denied():
    dec = allow(_user(role="ENGINEER"),
                _doc(cls="CONFIDENTIAL", dept="HR", roles=["HR_MANAGER"]), _policy())
    assert not dec.allowed


def test_rule8_deny_by_default():
    dec = allow(_user(), _doc(cls="CONFIDENTIAL", roles=[]), _policy())
    assert not dec.allowed and dec.rule_id == "rule8"


def test_rule7_override_grants():
    pol = _policy(overrides=[Override(role="ENGINEER", department="Engineering",
                                      classifications=("CONFIDENTIAL",))])
    dec = allow(_user(role="ENGINEER", dept="Engineering"),
                _doc(cls="CONFIDENTIAL", dept="Engineering", roles=[]), pol)
    assert dec.allowed and dec.rule_id == "rule7"


def test_decision_fields_populated():
    dec = allow(_user(role="HR_MANAGER"),
                _doc(cls="CONFIDENTIAL", dept="HR", roles=["HR_MANAGER"]), _policy())
    d = dec.to_dict()
    for key in ("subject", "subject_role", "subject_department", "object",
                "object_department", "object_classification", "object_tenant",
                "tenant_id", "allowed", "rule_id", "reason", "effector", "timestamp"):
        assert key in d and d[key] not in (None, "")


def test_authorized_ids_respects_policy():
    u = _user(role="HR_MANAGER", dept="HR")
    docs = [
        _doc("P", cls="PUBLIC"),
        _doc("I", dept="HR", cls="INTERNAL"),
        _doc("C", dept="HR", cls="CONFIDENTIAL", roles=["HR_MANAGER"]),
        _doc("R", dept="HR", cls="CONFIDENTIAL", roles=["HR_ADMIN"]),
        _doc("X", dept="Finance", cls="INTERNAL"),
    ]
    ids = authorized_ids(u, docs, _policy())
    assert ids == {"P", "I", "C"}


def test_policy_load_from_default_file():
    from backend.config import POLICIES_FILE

    pol = Policy.load(POLICIES_FILE)
    assert pol.version == "1"
    assert pol.rules["tenant_scope"] == "strict"