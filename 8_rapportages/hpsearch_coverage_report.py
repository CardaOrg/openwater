#!/usr/bin/env python3
"""
hpsearch_coverage_report.py — show trial coverage per task for a hpsearch run.

Usage:  python hpsearch_coverage_report.py <run_label>
Example: python hpsearch_coverage_report.py mv_impute_20260304_155356

Output: prints a table showing for each (operator, model, run_variant, grid):
  - n_trials_done vs expanded_trials (coverage %)
  - hit time budget (yes/no)
  - best CV AUPRC ± std
  - test AUPRC
"""

import sys
import json
import math
from pathlib import Path

import pandas as pd

OUTPUTS_ROOT = Path("/projects/prjs1763/6_model_outputs_after_07_10_25")


def fmt(val, std=None, decimals=4):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    if std is not None and not (isinstance(std, float) and math.isnan(std)):
        return f"{val:.{decimals}f}±{std:.{decimals}f}"
    return f"{val:.{decimals}f}"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 1:
        print("Usage: python hpsearch_coverage_report.py <run_label_of_run_folder>")
        sys.exit(1)

    # NB (organisatie-versie): het argument mag een concrete run-map zijn (organisatie) óf een run_label onder
    # de Snellius-OUTPUTS_ROOT (origineel gedrag). Een bestaand pad wint.
    run_arg = argv[0]
    run_label = Path(run_arg).name
    run_folder = Path(run_arg) if Path(run_arg).is_dir() else OUTPUTS_ROOT / run_arg

    if not run_folder.is_dir():
        print(f"❌ Run folder not found: {run_folder}")
        sys.exit(1)

    rows = []
    for results_path in sorted(list(run_folder.glob("*/*/*/*/results.csv")) + list(run_folder.glob("*/*/*/*/*/results.csv"))):
        rel = results_path.relative_to(run_folder)
        parts = rel.parts  # operator, model, run_variant, grid_name, results.csv
        if len(parts) < 5:
            continue
        operator, model, run_variant, grid_name = parts[:4]

        # Load results.csv
        try:
            df = pd.read_csv(results_path)
            n_done = len(df)
        except Exception:
            n_done = 0
            df = pd.DataFrame()

        # Load meta.json for expanded_trials and time_budget
        meta_path = results_path.parent / "meta.json"
        expanded_trials = None
        time_budget = None
        n_rows = None
        positives = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                expanded_trials = meta.get("expanded_trials")
                time_budget = meta.get("time_budget_seconds")
                n_rows = meta.get("n_rows")
                positives = meta.get("positives")
            except Exception:
                pass

        # Load best.json
        best_path = results_path.parent / "best.json"
        best_cv_auprc = float("nan")
        best_cv_std = float("nan")
        test_auprc = float("nan")
        if best_path.exists():
            try:
                best = json.loads(best_path.read_text(encoding="utf-8"))
                best_cv_auprc = best.get("cv_mean_auprc", float("nan"))
                best_cv_std = best.get("cv_std_auprc", float("nan"))
                test_auprc = best.get("test_auprc", float("nan"))
            except Exception:
                pass

        # Determine if time budget was hit
        budget_hit = False
        if not df.empty and time_budget and "elapsed_seconds" in df.columns:
            max_elapsed = df["elapsed_seconds"].max()
            budget_hit = max_elapsed >= time_budget * 0.95  # within 5% of budget

        coverage_pct = None
        if expanded_trials and expanded_trials > 0:
            coverage_pct = 100 * n_done / expanded_trials

        rows.append({
            "operator": operator,
            "model": model,
            "run_variant": run_variant,
            "grid": grid_name,
            "done": n_done,
            "total": expanded_trials,
            "coverage_%": f"{coverage_pct:.0f}" if coverage_pct is not None else "?",
            "budget_hit": "YES" if budget_hit else "no",
            "best_cv_auprc": fmt(best_cv_auprc, best_cv_std),
            "test_auprc": fmt(test_auprc),
            "n_rows": n_rows or "",
            "positives": positives or "",
        })

    if not rows:
        print("No results found.")
        sys.exit(0)

    df_out = pd.DataFrame(rows)

    # Summary stats
    n_tasks = len(df_out)
    budget_hit_count = (df_out["budget_hit"] == "YES").sum()

    print(f"\n{'='*100}")
    print(f"  HPSEARCH COVERAGE REPORT: {run_label}")
    print(f"{'='*100}")
    print(f"  Tasks found: {n_tasks}  |  Hit time budget: {budget_hit_count}/{n_tasks}")
    print()

    # Print table
    col_w = {
        "operator": 10, "model": 18, "run_variant": 32, "grid": 24,
        "done": 5, "total": 6, "coverage_%": 9, "budget_hit": 10,
        "best_cv_auprc": 20, "test_auprc": 12,
    }
    header = (
        f"{'operator':<{col_w['operator']}}  "
        f"{'model':<{col_w['model']}}  "
        f"{'run_variant':<{col_w['run_variant']}}  "
        f"{'grid':<{col_w['grid']}}  "
        f"{'done':>{col_w['done']}}  "
        f"{'total':>{col_w['total']}}  "
        f"{'cover%':>{col_w['coverage_%']}}  "
        f"{'budget':>{col_w['budget_hit']}}  "
        f"{'best_cv_auprc':<{col_w['best_cv_auprc']}}  "
        f"{'test_auprc':<{col_w['test_auprc']}}"
    )
    print(header)
    print("-" * len(header))

    for _, r in df_out.sort_values(["operator", "model", "run_variant", "grid"]).iterrows():
        print(
            f"{r['operator']:<{col_w['operator']}}  "
            f"{r['model']:<{col_w['model']}}  "
            f"{r['run_variant']:<{col_w['run_variant']}}  "
            f"{r['grid']:<{col_w['grid']}}  "
            f"{str(r['done']):>{col_w['done']}}  "
            f"{str(r['total'] or '?'):>{col_w['total']}}  "
            f"{r['coverage_%']:>{col_w['coverage_%']}}  "
            f"{r['budget_hit']:>{col_w['budget_hit']}}  "
            f"{r['best_cv_auprc']:<{col_w['best_cv_auprc']}}  "
            f"{r['test_auprc']:<{col_w['test_auprc']}}"
        )

    print()

    # Budget-hit summary per model+grid
    budget_rows = df_out[df_out["budget_hit"] == "YES"][["model", "grid", "done", "total"]].drop_duplicates()
    if not budget_rows.empty:
        print("── Tasks that hit the time budget (incomplete coverage) ─────────────────")
        for _, r in budget_rows.iterrows():
            print(f"  {r['model']}/{r['grid']}: {r['done']}/{r['total']} trials")
        print()


if __name__ == "__main__":
    main()
