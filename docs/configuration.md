# Configuration

Environment variables, policy file formats, and runtime configuration reference.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZTRUST_SEED` | `20260908` | Random seed for reproducible corpus and index generation |
| `ZTRUST_TOP_K` | `5` | Number of chunks returned by the retriever |
| `ZTRUST_K_CAND` | `10` | Candidate pool size for config B (retrieve-then-filter) |
| `ZTRUST_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model identifier |
| `ZTRUST_DATA` | `./data` | Root data directory |
| `ZTRUST_RESULTS` | `./results` | Results output directory |

## Policy Files

### RBAC Policy (`data/policies/policies.json`)

```json
{
  "version": "1",
  "rules": {
    "tenant_scope": "strict",
    "public": "all",
    "internal": "same_department",
    "confidential": "explicit_allowed_roles",
    "restricted": "explicit_allowed_roles"
  },
  "overrides": [
    {
      "role": "EXECUTIVE_VP",
      "department": "Executive",
      "classifications": ["CONFIDENTIAL", "RESTRICTED"],
      "note": "Executive override"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `version` | Policy version string |
| `rules.tenant_scope` | `strict` = cross-tenant always denied |
| `rules.public` | `all` = all authenticated users |
| `rules.internal` | `same_department` = department match required |
| `rules.confidential` | `explicit_allowed_roles` = role must be in `allowed_roles` |
| `rules.restricted` | `explicit_allowed_roles` = role must be in `allowed_roles` |
| `overrides` | List of role-department-classification overrides |

### ABAC Policy (`data/policies/policies_abac.json`)

Same structure as RBAC, plus:

```json
{
  "version": "abac-v1",
  "attr_mode": true,
  "rules": { ... },
  "overrides": [ ... ]
}
```

| Field | Description |
|-------|-------------|
| `attr_mode` | `true` = RBAC grants are gated through attribute predicates |

When `attr_mode=true`, every RBAC grant (rules 4–7) is additionally checked against the user's attribute predicates before being honored. See [Authorization](authorization.md#abac-hybrid) for predicate details.

## Query Execution

```bash
# Run all configurations under RBAC policy
python -m experiments.run_all

# Run all configurations under ABAC policy
python -m experiments.run_all --policy abac

# Run specific configurations only
python -m experiments.run_all --configs B,C

# Skip audit store writes
python -m experiments.run_all --no-audit

# Override k
python -m experiments.run_all --k 10 --k-cand 20
```

## Results Output

| Path | Contents |
|------|----------|
| `results/comparison.md` | RBAC policy comparison table (all metrics) |
| `results/abac_comparison.md` | ABAC policy comparison + per-user differential |
| `results/runs/<CONFIG>/<QUERY>.json` | Per-query run records (RBAC) |
| `results/runs_abac/<CONFIG>/<QUERY>.json` | Per-query run records (ABAC) |
| `results/figures/*.png` | Generated metric charts |

## Run Record Schema

```json
{
  "query_id": "Q-001",
  "config": "C_pre_retrieval_rbac",
  "user_id": "alice",
  "expected": "allow",
  "candidate_ids": ["HR-0001", "HR-0002", ...],
  "context_ids": ["HR-0001", "HR-0002", ...],
  "decisions": [
    {
      "document_id": "HR-0001",
      "allowed": true,
      "rule_id": "rule6+abac",
      "reason": "grant + attributes satisfied"
    }
  ],
  "lat_authz_ms": 0.78,
  "lat_retrieval_ms": 0.20,
  "lat_gen_ms": 0.05,
  "k": 5,
  "scope_size": 11,
  "answer": "Executive summary: salary bands ...",
  "provider": "extractive"
}
```
