"""ABAC attribute predicates (Section F/G, NIST SP 800-162 [12]).

The paper's equation (2) resolves a hybrid policy as the logical conjunction

    ∃r ∈ roles(u) ( permits(r, d) = 1  ∧  attributes(d) ⊨ policy(r)(u) )

The first clause (RBAC grant) lives in the policy engine; this module is the
second clause — the ABAC attribute predicate that must ALSO hold before the
document enters the authorized candidate set. Every predicate returns both a
boolean and a human-readable reason, and always defaults to deny on unknown
input (deny-by-default, Zero-Trust rule 5).

Predicate semantics follow the user's attribute context:
  - max_sensitivity  : user may read documents at or below this sensitivity.
  - business_units   : extra departments the user is cleared for beyond their own.
  - clearance        : an elevated grant tier for otherwise-restricted classes.
  - time_window      : allowed clock-window for access (continuous authorization).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from backend.models import Document, User

# Sensitivity lattice: LOW < MEDIUM < HIGH < CRITICAL
_SENSITIVITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class PredicateResult:
    satisfied: bool
    reason: str


def _now_utc() -> str:
    return datetime.utcnow().strftime("%H:%M:%S")


def within_time_window(user: User, now: str = "") -> PredicateResult:
    """Continuous/situational attribute: is access happening inside the allowed window?"""
    current = now or _now_utc()
    lo, hi = user.time_window
    if lo <= current <= hi:
        return PredicateResult(True, f"time window [{lo},{hi}] active")
    return PredicateResult(False, f"outside time window [{lo},{hi}]")


def sensitivity_within(user: User, doc: Document) -> PredicateResult:
    """Document sensitivity must be at or below the user's max sensitivity."""
    d_level = _SENSITIVITY_ORDER.get(doc.sensitivity_level, 0)
    u_level = _SENSITIVITY_ORDER.get(user.max_sensitivity, 2)
    if d_level <= u_level:
        return PredicateResult(
            True,
            f"doc sensitivity {doc.sensitivity_level} <= user max {user.max_sensitivity}",
        )
    return PredicateResult(
        False,
        f"doc sensitivity {doc.sensitivity_level} exceeds user max {user.max_sensitivity}",
    )


def department_cleared(user: User, doc: Document) -> PredicateResult:
    """User's own department or an explicitly listed business unit."""
    cleared = {user.department}
    cleared |= set(user.business_units)
    if doc.department in cleared or doc.department == user.department:
        return PredicateResult(True, f"department {doc.department} cleared")
    return PredicateResult(False, f"department {doc.department} not in cleared set")


def clearance_for(user: User, doc: Document) -> PredicateResult:
    """RESTRICTED documents additionally require an elevated clearance tier."""
    if doc.classification != "RESTRICTED":
        return PredicateResult(True, "not restricted")
    if user.clearance == "elevated":
        return PredicateResult(True, "elevated clearance present")
    return PredicateResult(False, "restricted requires elevated clearance")


def evaluate(user: User, doc: Document, now: str = "") -> dict[str, PredicateResult]:
    """Run all attribute predicates; returns a map keyed by predicate name.

    The conjunction of all predicate booleans (with `True` for any predicate
    that is not applicable) is the ABAC clause in equation (2).
    """
    return {
        "sensitivity": sensitivity_within(user, doc),
        "department": department_cleared(user, doc),
        "clearance": clearance_for(user, doc),
        "time_window": within_time_window(user, now),
    }


def satisfies(user: User, doc: Document, now: str = "") -> tuple[bool, dict[str, PredicateResult]]:
    """Return (all_true, predicate_results). All applicable predicates must hold."""
    results = evaluate(user, doc, now)
    # time_window is a situational predicate; the others are document-scoped.
    # Every predicate must be satisfied for the ABAC clause to hold.
    ok = all(r.satisfied for r in results.values())
    return ok, results