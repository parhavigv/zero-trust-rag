# RBAC Policy Model

## Objective

A deterministic, inspectable authorization engine used by all three
configurations (B and C consume the same `allow()` predicate; only *where* it
is applied differs). The engine answers secondary questions 1–2 and 4–7 by
being the single authorization primitive under test.

## Core semantics

- **Subjects** = users (each with exactly one role and department).
- **Objects** = documents (metadata: department, classification,
  `allowed_roles`, `tenant_id`).
- **Action** = `retrieve` (also used as a proxy for "enter LLM context").
- **Decision** = `ALLOW` or `DENY`, with the governing rule recorded.

### Evaluation order (first match wins)

```
1. Tenant check        user.tenant_id != doc.tenant_id        → DENY (cross-tenant)
2. Enabled check       user.enabled == False                   → DENY
3. Deny-by-default     no matching rule below                  → DENY
4. PUBLIC              doc.classification == PUBLIC            → ALLOW
5. INTERNAL            doc.classification == INTERNAL
                        AND user.department == doc.department   → ALLOW
6. CONFIDENTIAL|RESTRICTED
                        user.role in doc.allowed_roles         → ALLOW
7. Explicit allow-role  (policy override list)
                        (user.role, doc.department) in policy.overrides → ALLOW
8. otherwise                                                  → DENY
```

```python
# Structural signature (implemented in Phase 3)
def allow(user: User, doc: Document) -> Decision:
    """Deterministic; used identically by configs B and C."""
```

`Decision` carries: `allowed: bool`, `rule_id` (one of the numbered rules),
`reason` (human-readable chain), `effector` (which input made it fail/pass).
This powers audit reconstruction and metric numerators (false authz vs false
denial).

## Role → permission matrix (initial policy)

| Role | PUBLIC | INTERNAL (own dept) | CONFIDENTIAL | RESTRICTED |
|------|--------|---------------------|--------------|------------|
| EMPLOYEE | ✅ | ✅ | ❌ | ❌ |
| ENGINEER | ✅ | ✅ | ❌ | ❌ |
| HR_MANAGER | ✅ | ✅ | HR docs (allowed_roles) | via allowed_roles |
| HR_ADMIN | ✅ | ✅ | HR docs (allowed_roles) | via allowed_roles |
| FINANCE_ANALYST | ✅ | ✅ | Finance docs (allowed_roles) | via allowed_roles |
| SALES_REP | ✅ | ✅ | ❌ | ❌ |
| LEGAL_COUNSEL | ✅ | ✅ | Legal docs (allowed_roles) | via allowed_roles |
| EXECUTIVE_VP | ✅ | Executive+below | explicit allowed_roles | via allowed_roles |

The exact matrix lives in `data/policies/policies.json` so experiments can
vary it **without code changes** (needed for ablation: e.g., a
"finer-grained" variant, secondary question 7).

## Example decisions (from the brief)

| Query-as-user | Document | Decision | Rule |
|---------------|----------|----------|------|
| HR_MANAGER asks HR salary info | HR-0001 (confidential, allowed [HR_MANAGER, HR_ADMIN]) | ALLOW | rule 6 |
| ENGINEER asks HR salary info | HR-0001 | DENY | rule 6 fails, no override → deny-by-default |
| FINANCE_ANALYST asks engineering confidential | ENG-0012 | DENY | rule 6 fails |
| EMPLOYEE asks executive confidential | EXEC-0003 | DENY | rule 6 fails |
| any user, foreign tenant doc | anything | DENY | rule 1 |
| legitimate question with answer in allowed doc | PUB-0012 | ALLOW | rule 4 |

## Zero-Trust principle mapping

| Principle | Mechanism in this model |
|-----------|-------------------------|
| 1. Never trust inside the network | identity resolved per request; enabled check; no IP/location assumption |
| 2. Explicitly verify identity | `auth` resolves token → user before any policy call |
| 3. Authorize every retrieval request | `allow()` called on the query path in B **and** C |
| 4. Least privilege | CONFIDENTIAL/RESTRICTED require exact role in `allowed_roles`; no wildcard dept access |
| 5. Deny by default | rule 3/8 |
| 6. Not location-dependent | no network-source conditions in policy |
| 7. Log authorization decisions | audit store records every `Decision` with `rule_id` |
| 8. Re-evaluate per query | no caching of `allow()` across queries in the experiments (measured fresh) |
| 9. Cross-department prevention | rule 5 (INTERNAL scoped to dept) + rule 6 |
| 10. Cross-tenant prevention | rule 1 (hard deny) |

## Fine-grained alternative (for secondary question 7)

A variant policy introduces attribute conditions beyond role
(e.g., `sensitivity_level <= user.max_sensitivity`, `department ∈
user.business_units`, time-of-day window, `owner == user`). This is kept as an
optional experiment flag (`policy.mode = rbac | rbac_plus_attrs`) rather than
a second engine, so the RBAC-vs-finer-grained comparison is a *policy
configuration* change — methodologically cleaner than two implementations.

## Integrity note

"Least privilege", "deny-by-default", and "continuous authorization" are
Key-Trust concepts; the *specific* rule ordering in this document is an
**engineering design choice** for a student prototype, not a literature claim.