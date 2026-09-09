# Data Model

Schemas for the synthetic corpus, user seed data, and evaluation query set. All objects are plain JSON — inspectable and diffable.

## Document

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

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | Stable unique ID (`{DEPT}-{NNNN}`) |
| `department` | string | Owning business unit (HR, Finance, Engineering, Legal, Sales, Executive) |
| `classification` | enum | `PUBLIC` / `INTERNAL` / `CONFIDENTIAL` / `RESTRICTED` |
| `allowed_roles` | list | Explicit role allow-list (empty = PUBLIC-equivalent) |
| `owner` | string | Document owner email |
| `tenant_id` | string | Tenant namespace — cross-tenant access is always denied |
| `created_at` | string | ISO date, seeded deterministically |
| `sensitivity_level` | enum | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| `content` | string | Synthetic text (templated factual statements) |

### Classification → Access Mapping

| Classification | Accessible by | Notes |
|----------------|---------------|-------|
| PUBLIC | All roles | Deny-by-default still applies to tenant |
| INTERNAL | Same department | Any role whose department matches |
| CONFIDENTIAL | Explicit `allowed_roles` | Or department + role in list |
| RESTRICTED | Explicit `allowed_roles` only | Rarest class, audit-flagged |

## User

```json
{
  "user_id": "alice",
  "name": "Alice Wang",
  "role": "HR_MANAGER",
  "department": "HR",
  "tenant_id": "tenant-acme",
  "enabled": true,
  "max_sensitivity": "HIGH",
  "business_units": [],
  "clearance": "standard",
  "time_window": ["00:00:00", "23:59:59"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string | Login identity |
| `role` | string | Coarse role (see Authorization docs) |
| `department` | string | User's business unit |
| `tenant_id` | string | Tenant scoping |
| `enabled` | bool | Disabled accounts are denied everything |
| `max_sensitivity` | enum | ABAC: highest sensitivity the user may read |
| `business_units` | list | ABAC: additional departments the user can access |
| `clearance` | enum | ABAC: grant tier (`standard` / `elevated`) |
| `time_window` | [string, string] | ABAC: allowed access hours (HH:MM:SS) |

### Seed Users

| user_id | role | department | tenant | clearance |
|---------|------|------------|--------|-----------|
| alice | HR_MANAGER | HR | tenant-acme | standard |
| bob | ENGINEER | Engineering | tenant-acme | standard |
| carol | FINANCE_ANALYST | Finance | tenant-acme | standard |
| dave | SALES_REP | Sales | tenant-acme | standard |
| eve | EXECUTIVE_VP | Executive | tenant-acme | elevated |
| frank | LEGAL_COUNSEL | Legal | tenant-acme | standard |
| grace | HR_ADMIN | HR | tenant-acme | elevated |
| mallory | ENGINEER | Engineering | tenant-beta | standard |
| disabled_user | EMPLOYEE | Engineering | tenant-acme | standard (enabled=false) |

## Query

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

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Query string |
| `as_user` | string | Identity to execute the query as |
| `expected` | enum | `allow` / `deny` (authorization oracle) |
| `target_docs` | list | Documents whose content is required to answer |
| `gold_allowed_docs` | list | All docs the user is allowed to retrieve for this query |
| `category` | string | Query class for metric grouping |

### Query Categories

| Category | Description | Count |
|----------|-------------|-------|
| `legit` | Authorized access, answer expected | 11 |
| `cross_dept_confidential` | Unauthorized cross-department confidential access | 8 |
| `cross_dept_internal` | Unauthorized cross-department internal access | 4 |
| `cross_tenant` | Unauthorized cross-tenant access | 2 |
| `executive_secret` | Unauthorized RESTRICTED access | 4 |
| `negation_attack` | Adversarial prompt-injection style queries | 4 |
| `abac_attribute_deny` | ABAC hybrid: role allowed but attributes fail | 2 |
| `abac_attribute_allow` | ABAC hybrid: role + attributes both pass | 2 |
| `public_lookup` | Public document lookups | 1 |

## Directory Layout

| Path | Contents |
|------|----------|
| `data/documents/*.json` | One JSON file per synthetic document |
| `data/users/users.json` | Seed users |
| `data/queries/queries.json` | Oracle-labeled evaluation query set |
| `data/policies/*.json` | RBAC and ABAC policy definitions |
| `data/index/` | Built FAISS index + ID mapping (generated, git-ignored) |
