"""ABAC attribute-predicate + hybrid-resolution tests (Section F/G, eq. 2)."""
from __future__ import annotations

from backend.models import Document, User
from backend.rbac.attr_predicates import (
    clearance_for,
    department_cleared,
    evaluate,
    satisfies,
    sensitivity_within,
    within_time_window,
)
from backend.rbac.engine import Policy, allow

ABAC = Policy(version="abac", rules={}, overrides=[], attr_mode=True)
RBAC = Policy(version="1", rules={}, overrides=[], attr_mode=False)


def _user(max_sens="HIGH", units=(), clearance="standard", window=("00", "24"), dept="HR"):
    return User(user_id="u", name="U", role="HR_MANAGER", department=dept,
                tenant_id="tenant-acme", enabled=True, max_sensitivity=max_sens,
                business_units=tuple(units), clearance=clearance,
                time_window=(f"{window[0]}:00:00", f"{window[1]}:00:00"))


def _doc(cls="CONFIDENTIAL", sens="HIGH", dept="HR"):
    return Document(document_id="D-1", title="t", department=dept, classification=cls,
                    allowed_roles=("HR_MANAGER",), owner="o", tenant_id="tenant-acme",
                    created_at="2025-01-01", sensitivity_level=sens, content="c")


def test_sensitivity_ceiling():
    assert sensitivity_within(_user(max_sens="HIGH"), _doc(sens="HIGH")).satisfied
    assert not sensitivity_within(_user(max_sens="HIGH"), _doc(sens="CRITICAL")).satisfied
    assert sensitivity_within(_user(max_sens="CRITICAL"), _doc(sens="CRITICAL")).satisfied


def test_department_cleared_via_business_units():
    assert department_cleared(_user(units=("Finance",)), _doc(dept="Finance")).satisfied
    assert not department_cleared(_user(units=("Finance",)), _doc(dept="Legal")).satisfied


def test_clearance_required_for_restricted():
    assert clearance_for(_user(clearance="elevated"), _doc(cls="RESTRICTED")).satisfied
    assert not clearance_for(_user(clearance="standard"), _doc(cls="RESTRICTED")).satisfied
    assert clearance_for(_user(clearance="standard"), _doc(cls="CONFIDENTIAL")).satisfied


def test_time_window():
    u = _user(window=("09:00", "17:00"))
    assert within_time_window(u, now="10:00:00").satisfied
    assert not within_time_window(u, now="18:00:00").satisfied


def test_satisfies_conjunction():
    ok, results = satisfies(_user(max_sens="HIGH"), _doc(sens="HIGH"), now="10:00:00")
    assert ok
    ok2, _ = satisfies(_user(max_sens="MEDIUM"), _doc(sens="HIGH"), now="10:00:00")
    assert not ok2


def test_abac_allows_when_grant_and_attrs_hold():
    u = _user(max_sens="HIGH", clearance="elevated")
    assert allow(u, _doc(sens="HIGH"), ABAC).allowed


def test_abac_denies_when_attribute_fails_despite_rbac_grant():
    # Same role grant, but CRITICAL doc exceeds HIGH ceiling -> eq-2 conjunction fails.
    u = _user(max_sens="HIGH")
    dec = allow(u, _doc(sens="CRITICAL"), ABAC)
    assert not dec.allowed
    assert "+abac" in dec.rule_id
    assert "sensitivity" in dec.reason.lower()


def test_rbac_only_allows_same_case():
    # Pure RBAC has no attribute gate, so the grant alone allows.
    u = _user(max_sens="HIGH")
    assert allow(u, _doc(sens="CRITICAL"), RBAC).allowed


def test_abac_time_window_denies():
    u = _user(max_sens="HIGH", window=("09:00", "17:00"))
    dec = allow(u, _doc(sens="HIGH"), ABAC, now="23:00:00")
    assert not dec.allowed


def test_abac_deny_reason_explains_effector():
    u = _user(max_sens="HIGH")
    dec = allow(u, _doc(sens="CRITICAL"), ABAC)
    assert "exceeds user max" in dec.reason
    assert "CRITICAL" in dec.reason
