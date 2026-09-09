# Authorization

RBAC + ABAC policy model, rule ordering, and Zero-Trust principle mapping for the authorization engine.

## Core Semantics

- **Subjects** — users (each with exactly one role and department).
- **Objects** — documents (metadata: department, classification, `allowed_roles`, `tenant_id`).
- **Action** — `retrieve` (proxy for "enter LLM context").
- **Decision** — `ALLOW` or `DENY`, with the governing rule recorded.

## Rule Evaluation Order (First Match Wins)

| # | Rule | Condition | Result |
|---|------|-----------|--------|
| 1 | Tenant check | `user.tenant_id != doc.tenant_id` | DENY |
| 2 | Enabled check | `user.enabled == False` | DENY |
| 3 | Deny-by-default | No matching rule below | DENY |
| 4 | PUBLIC | `doc.classification == PUBLIC` | ALLOW |
| 5 | INTERNAL | `doc.classification == INTERNAL` AND `user.department == doc.department` | ALLOW |
| 6 | CONFIDENTIAL / RESTRICTED | `user.role ∈ doc.allowed_roles` | ALLOW |
| 7 | Policy override | `(user.role, doc.department) ∈ policy.overrides` | ALLOW |
| 8 | Otherwise | — | DENY |

Rules 4–7 are gated by the ABAC attribute predicates when `attr_mode=true` (see [ABAC Hybrid](#abac-hybrid) below). The rule ID carries a `+abac` suffix when the attribute gate is the reason for denial.

## Role → Permission Matrix

| Role | PUBLIC | INTERNAL (own dept) | CONFIDENTIAL | RESTRICTED |
|------|:------:|:-------------------:|:------------:|:----------:|
| EMPLOYEE | ✅ | ✅ | ❌ | ❌ |
| ENGINEER | ✅ | ✅ | ❌ | ❌ |
| HR_MANAGER | ✅ | ✅ | HR docs | via `allowed_roles` |
| HR_ADMIN | ✅ | ✅ | HR docs | via `allowed_roles` |
| FINANCE_ANALYST | ✅ | ✅ | Finance docs | via `allowed_roles` |
| SALES_REP | ✅ | ✅ | ❌ | ❌ |
| LEGAL_COUNSEL | ✅ | ✅ | Legal docs | via `allowed_roles` |
| EXECUTIVE_VP | ✅ | Executive + below | explicit roles | via `allowed_roles` |

The exact matrix lives in `data/policies/policies.json`. Policy configuration changes without code changes.

## ABAC Hybrid

When `attr_mode=true` in the policy file (`policies_abac.json`), RBAC grants (rules 4–7) are gated through attribute predicates. The grant is only honored when **all** predicates hold:

| Predicate | Implementation |
|-----------|----------------|
| Sensitivity ceiling | `doc.sensitivity_level ≤ user.max_sensitivity` |
| Business-unit clearance | `doc.department ∈ user.business_units` OR user's own department |
| User clearance | `doc.classification ≤ user.clearance` |
| Time window | `user.time_window` contains current time |

### Example: Attribute Gate in Action

Alice (HR_MANAGER, `max_sensitivity=HIGH`) queries HR-0006 (CRITICAL):
- RBAC grant: rule 6 passes (HR_MANAGER ∈ allowed_roles)
- ABAC gate: `CRITICAL > HIGH` → **denied** (`rule6+abac`)
- Result: HR-0006 is excluded from retrieval scope

Grace (HR_ADMIN, `max_sensitivity=CRITICAL`, `clearance=elevated`) queries HR-0006:
- RBAC grant: rule 6 passes
- ABAC gate: `CRITICAL ≤ CRITICAL` → **passes**
- Result: HR-0006 is in retrieval scope

### Per-User Allowed-Set Differentials

Measured reduction in authorized documents when switching from RBAC to ABAC:

| User | RBAC | ABAC | Removed |
|------|:----:|:----:|:-------:|
| alice (HR_MANAGER) | 11 | 5 | 6 |
| grace (HR_ADMIN) | 11 | 6 | 5 |
| bob (ENGINEER) | 11 | 5 | 6 |
| dave (SALES_REP) | 11 | 3 | 8 |
| eve (EXECUTIVE_VP) | 16 | 10 | 6 |

## Zero-Trust Principle Mapping

| Principle | Mechanism |
|-----------|-----------|
| Never trust inside the network | Identity resolved per request; no IP/location assumptions |
| Explicitly verify identity | `auth` resolves token → user before any policy call |
| Authorize every request | `allow()` called on every query path (B and C) |
| Least privilege | CONFIDENTIAL/RESTRICTED require exact role in `allowed_roles` |
| Deny by default | Rule 3/8 |
| Not location-dependent | No network-source conditions in policy |
| Log every decision | Audit store records every `Decision` with `rule_id` |
| Re-evaluate per query | No caching of `allow()` across queries |
| Cross-department prevention | Rule 5 (INTERNAL scoped to dept) + rule 6 |
| Cross-tenant prevention | Rule 1 (hard deny) |

## Design Decisions

- **Deny-by-default rule ordering** is an engineering choice (matches this document), not a standard.
- **Per-query evaluation** — `authorized_ids()` computes the allow-set fresh on every query. Deliberately conservative; at scale, cached allow-sets with TTL would be the optimization target.
- **Scoped FAISS search** builds a temporary index over the authorized subset. Correct by construction; production implementations would optimize with id-filtered search.
