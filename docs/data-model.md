# Data Model

Grounds the synthetic corpus, the user/role seed data, and the oracle-labeled
query set used by all experiments. Every object is plain JSON so the corpus
and policies are inspectable and diffable.

## Document object

```json
{
  "document_id": "HR-0001",
  "title": "Employee Salary Report FY2025",
  "department": "HR",
  "classification": "confidential",
  "allowed_roles": ["HR_MANAGER", "HR_ADMIN"],
  "owner": "hr-admin@acme.io",
  "tenant_id": "tenant-acme",
  "created_at": "2025-06-01",
  "sensitivity_level": "HIGH",
  "content": "Executive summary: salary bands ..."
}
```

### Fields

| Field | Semantics |
|-------|-----------|
| `document_id` | Stable unique id (`{DEPT}-{NNNN}`) |
| `department` | Owning business unit (HR, Finance, Engineering, Legal, Sales, Executive) |
| `classification` | PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED |
| `allowed_roles` | Explicit role allow-list (empty ⇒ PUBLIC-equivalent) |
| `owner` | Document owner (email) |
| `tenant_id` | Tenant namespace — **cross-tenant access is always denied** |
| `created_at` | ISO date, seeded deterministically |
| `sensitivity_level` | LOW / MEDIUM / HIGH / CRITICAL (for leakage-rate grouping) |
| `content` | Synthetic text (templated factual statements, no real data) |

### Classification → role mapping (policy, not per-document)

| Classification | Default readable by roles | Notes |
|----------------|---------------------------|-------|
| PUBLIC | all roles | deny-by-default still applies to tenant |
| INTERNAL | same department | any role whose department matches |
| CONFIDENTIAL | explicit `allowed_roles` (or dept + role in list) | |
| RESTRICTED | explicit `allowed_roles` only, plus audit-flag | rarest class |

`allowed_roles` is authoritative: even a same-department user is denied if the
role is not listed (least privilege / explicit allow).

## User object

```json
{
  "user_id": "alice",
  "name": "Alice Wang",
  "role": "HR_MANAGER",
  "department": "HR",
  "tenant_id": "tenant-acme",
  "enabled": true
}
```

| Field | Semantics |
|-------|-----------|
| `user_id` | Login identity (like `alice`) |
| `role` | Coarse role (see `docs/rbac-policy-model.md`) |
| `department` | User's business unit; used for same-dept INTERNAL access |
| `tenant_id` | Tenant scoping; never shares documents across tenants |
| `enabled` | Disabled accounts are denied everything (Zero-Trust #1/#2) |

Roles are derived from `data/users/users.json`. Permissions are **computed**
from (role, department) by the RBAC engine — never stored redundantly per
user (single source of truth, avoids permission drift).

## Example users (seed set)

| user_id | role | department | tenant |
|---------|------|------------|--------|
| alice | HR_MANAGER | HR | tenant-acme |
| bob | ENGINEER | Engineering | tenant-acme |
| carol | FINANCE_ANALYST | Finance | tenant-acme |
| dave | EMPLOYEE | Sales | tenant-acme |
| eve | EXECUTIVE_VP | Executive | tenant-acme |
| mallory | ENGINEER | Engineering | tenant-beta  (cross-tenant adversary) |

## Oracle-labeled query set (evaluation ground truth)

Each test query carries an oracle: which documents *should* be retrievable for
that user under the policy, and whether denial is expected.

```json
{
  "query_id": "Q-014",
  "text": "What is Alice's salary band?",
  "as_user": "bob",
  "expected": "deny",
  "target_docs": ["HR-0001"],
  "category": "cross_dept_confidential",
  "gold_allowed_docs": ["PUB-0012"]
}
```

| Field | Semantics |
|-------|-----------|
| `text` | Query string (question or lookup) |
| `as_user` | Identity the query is executed as |
| `expected` | `allow` / `deny` (authorization oracle) |
| `target_docs` | Documents whose content is required to answer |
| `gold_allowed_docs` | All docs the user is allowed to retrieve for this query |
| `category` | allows metrics per query class: `legit`, `cross_dept_confidential`, `cross_dept_internal`, `cross_tenant`, `executive_secret`, `public_lookup`, ... |

The query set is split so *successful retrieval quality* (precision/recall,
answer accuracy) is measured only on `allow` queries over `gold_allowed_docs`,
while *security metrics* are measured on `deny` queries and on the leakage of
non-allowed docs across all queries.

## Directory conventions

| Path | Contents |
|------|----------|
| `data/documents/*.json` | One JSON file per synthetic document |
| `data/users/users.json` | Seed users |
| `data/policies/policies.json` | RBAC policy (role/classification matrix + exceptions) |
| `data/queries/queries.json` | Oracle-labeled evaluation query set |
| `data/index/` | Built FAISS index + id mapping (generated, git-ignored) |

The corpus generator (Phase 2) writes documents with a **fixed random seed**
so every run of the pipeline is byte-identical — reproducibility across the
A/B/C experiments and across machines.