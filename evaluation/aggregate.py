"""Aggregate run records into metric tables + figures (Phase 9/11).

Run:  python -m evaluation.aggregate
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from backend.config import FIGURES_DIR, RESULTS_DIR, RUNS_DIR, TABLES_FILE
from backend.evaluation.metrics import aggregate
from backend.io import load_documents, load_policy, load_queries, load_users
from experiments.common import RunRecord

CONFIGS = ["A_baseline", "B_retrieve_then_filter", "C_pre_retrieval_rbac"]


def load_recs(config: str) -> list[RunRecord]:
    recs = []
    for path in sorted((RUNS_DIR / config).glob("*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            recs.append(RunRecord.from_dict(json.load(fh)))
    return recs


def fmt(v, nd=4, suffix="") -> str:
    if v is None:
        return "n/a"
    if isinstance(v, dict):
        return " / ".join(f"{k}={fmt(x, nd, suffix)}" for k, x in v.items())
    return f"{v:.{nd}f}{suffix}"


def main() -> None:
    docs = load_documents()
    users = load_users()
    policy = load_policy()
    queries = load_queries()
    docs_by_id = {d.document_id: d for d in docs}
    users_by_id = {u.user_id: u for u in users}
    queries_by_id = {q["query_id"]: q for q in queries}

    aggregations = {}
    for cfg in CONFIGS:
        recs = load_recs(cfg)
        aggregations[cfg] = aggregate(recs, users_by_id, docs_by_id, policy, queries_by_id)

    rows = [
        (
            r"""
| Metric | Definition (docs/metrics.md) | A (baseline) | B (retrieve-then-filter) | C (pre-retrieval RBAC) | Direction |
|--------|-------------------------------|:------------:|:-------------------------:|:----------------------:|:---------:|"""
        )
    ]

    def table_row(metric, label, nd=4, suffix=""):
        vals = [aggregations[c].get(metric) for c in CONFIGS]
        row = f"| {metric} | {label} | " + " | ".join(fmt(v, nd, suffix) for v in vals) + " |"
        return row

    rows.append("### Security metrics")
    rows.append(table_row("S1", "unauthorized-sentences/chunks-in-context ratio"))
    rows.append(table_row("S2", "unauthorized docs in context (mean count)"))
    rows.append(table_row("S3_unauth_candidates", "unauthorized docs in candidate lists (total count)"))
    rows.append(table_row("S3", "unauthorized docs among retrieved candidates"))
    rows.append(table_row("S5", "security-balanced metric"))
    rows.append(table_row("S6_denial_correct", "denial-correctness rate"))
    rows.append(table_row("S7_false_deny_rate", "false-deny (over-block) rate"))
    rows.append(table_row("S8_deny_authz_mean_ms", "deny-latency (authz), ms"))

    rows.append("### Retrieval metrics (allow queries only)")
    rows.append(table_row("R1_allow_only", "recall@k vs gold-allowed targets"))
    rows.append(table_row("R2_allow_only", "precision@k"))
    rows.append(table_row("R3_allow_only", "nDCG@k"))
    rows.append(table_row("R4_allow_only", "MRR"))

    rows.append("### Generation metrics (extractive-baseline provider)")
    rows.append(table_row("G1_allow_only", "faithfulness (answer tokens in context)"))
    rows.append(table_row("G2_allow_only", "answer overlap vs gold answer"))
    rows.append(table_row("G3_allow_only", "gold-coverage in answer"))
    rows.append(table_row("G4_allow_context_complete", "context completeness"))

    rows.append("### Performance (ms)")
    rows.append(table_row("P1_total_ms", "end-to-end latency, mean/median/p95"))
    rows.append(table_row("P2_authz_ms", "authorization-stage latency"))
    rows.append(table_row("P3_retrieval_ms", "embedding-search latency"))

    rows.append("### Auditability")
    rows.append(table_row("U1_trace_complete", "decision-trace completeness"))
    rows.append(table_row("U2_reconstructable", "reconstructable runs"))
    rows.append(table_row("U3_all_logged", "all decisions logged (share)"))

    rows.append(
        f"### Coverage\nA: {aggregations['A_baseline']['n_queries']} queries "
        f"({aggregations['A_baseline']['n_allow']} allow / "
        f"{aggregations['A_baseline']['n_deny']} deny). "
        "Generation metrics use the deterministic extractive provider; "
        "real-model generation metrics are pending."
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TABLES_FILE, "w", encoding="utf-8") as fh:
        fh.write("# Experiment Comparison\n\n")
        fh.write("Status: Phase 10 execution. " if any(
            aggregations[c].get("n_queries") for c in CONFIGS
        ) else "")
        fh.write("\n\n".join(rows))
        fh.write("\n")

    try:
        _figures(aggregations)
    except Exception as exc:  # noqa: BLE001
        print(f"figure generation skipped: {exc}")

    print(f"tables -> {TABLES_FILE}")
    for cfg in CONFIGS:
        ag = aggregations[cfg]
        print(f"{cfg}: n={ag['n_queries']} "
              f"S1={ag['S1']} S6={ag['S6_denial_correct']} "
              f"R1={ag['R1_allow_only']} R2={ag['R2_allow_only']} "
              f"P2={ag['P2_authz_ms']} U2={ag['U2_reconstructable']}")


def _figures(aggregations: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    labels = ["A baseline", "B retrieve-then-filter", "C pre-retrieval RBAC"]
    colors = ["#9aa5b1", "#d98a00", "#2e7d32"]

    def bar(name, keys, title, ylabel, nd=4):
        def val(cfg, key):
            v = aggregations[cfg].get(key)
            if isinstance(v, dict):
                v = v.get("mean")
            return v if isinstance(v, (int, float)) else 0.0

        fig, ax = plt.subplots(figsize=(7, 3.5))
        x = range(len(keys))
        for off, (cfg, color) in enumerate(zip(CONFIGS, colors)):
            vals = [val(cfg, k) for k in keys]
            ax.bar([i + off * 0.28 for i in x], vals, width=0.28, label=labels[off], color=color)
        ax.set_xticks([i + 0.28 for i in x])
        ax.set_xticklabels([k.replace("_allow_only", " (allow)") for k in keys], rotation=12, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / name, dpi=150)
        plt.close(fig)

    bar("security_exposure.png", ["S1"], "S1: unauthorized sentiment in context", "ratio", 4)
    bar("security_denial.png", ["S6_denial_correct"], "S6: denial-correctness", "rate", 4)
    bar("retrieval_quality.png", ["R1_allow_only", "R2_allow_only", "R3_allow_only",
                                   "R4_allow_only"], "Retrieval quality (allow queries)", "score", 4)
    bar("latency.png", ["P2_authz_ms"], "P2: authorization latency", "ms", 3)


if __name__ == "__main__":
    main()