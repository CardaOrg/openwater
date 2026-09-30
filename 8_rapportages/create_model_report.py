#!/usr/bin/env python3
"""
create_model_report.py - Generate comprehensive HP tuning report

Usage:  python create_model_report.py <run_label>
Example: python create_model_report.py mv_impute_20260304_155356

Output: /projects/prjs1763/7_modelling_reports_after_07_10_25/<run_label>_report.txt
"""

import sys
import os
import json
import math
from itertools import product
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np
import yaml

OUTPUTS_ROOT = Path("/projects/prjs1763/6_model_outputs_after_07_10_25")
REPORTS_ROOT = Path("/projects/prjs1763/7_modelling_reports_after_07_10_25")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt(val, std=None, decimals=4):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    if std is not None and not (isinstance(std, float) and math.isnan(std)):
        return f"{val:.{decimals}f} ±{std:.{decimals}f}"
    return f"{val:.{decimals}f}"


def H1(title, width=80):
    return f"\n{'='*width}\n{title.upper()}\n{'='*width}\n"


def H2(title, width=60):
    return f"\n{'-'*width}\n{title}\n{'-'*width}\n"


def safe_sort_key(v):
    """Sort key that handles None, numeric strings, and mixed types."""
    if v is None:
        return (0, "", 0)
    try:
        return (1, "", float(v))
    except (TypeError, ValueError):
        return (2, str(v), 0)


def expand_grid_spec(spec):
    """Mirrors hpsearch_runner.py expand_grid_spec logic."""
    if spec is None:
        return []
    if isinstance(spec, list):
        return spec
    mode = spec.get("mode", "list")
    if mode == "cartesian":
        fixed = spec.get("fixed", {}) or {}
        params = spec.get("params", {}) or {}
        keys = list(params.keys())
        vals = [params[k] for k in keys]
        trials = []
        for combo in product(*vals):
            t = dict(zip(keys, combo))
            t.update(fixed)
            trials.append(t)
        return trials
    return spec.get("trials", [])


def count_expected_trials(spec):
    if spec is None:
        return 0
    if isinstance(spec, list):
        return len(spec)
    if isinstance(spec, dict):
        mode = spec.get("mode", "list")
        if mode == "cartesian":
            params = spec.get("params", {}) or {}
            n = 1
            for v in params.values():
                if isinstance(v, list):
                    n *= len(v)
            return n
        return len(spec.get("trials", []))
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_best_data(run_folder):
    """Load all best.json + meta.json + feature_importances.csv into a DataFrame.

    Returns (df, failed_list).
    """
    records = []
    failed = []

    # Support both old format (*/*/*/*/best.json) and new per-trial format (*/*/*/*/*/best.json)
    all_best_paths = sorted(
        list(run_folder.glob("*/*/*/*/best.json")) +
        list(run_folder.glob("*/*/*/*/*/best.json"))
    )
    for best_path in all_best_paths:
        rel = best_path.relative_to(run_folder)
        parts = rel.parts
        if len(parts) < 5:
            continue
        operator, model, run_variant, grid_name = parts[:4]

        try:
            with open(best_path, encoding="utf-8") as f:
                best = json.load(f)
        except Exception:
            continue

        meta_path = best_path.parent / "meta.json"
        meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        fi_path = best_path.parent / "feature_importances.csv"
        top_features = []  # list of (feature, importance)
        if fi_path.exists():
            try:
                fi_df = pd.read_csv(fi_path)
                if "feature" in fi_df.columns and "importance" in fi_df.columns:
                    top_features = list(
                        zip(fi_df["feature"].tolist(), fi_df["importance"].tolist())
                    )[:20]
            except Exception:
                pass

        records.append(
            {
                "operator": operator,
                "model": model,
                "run_variant": run_variant,
                "grid_name": grid_name,
                "combo": f"{model}/{run_variant}/{grid_name}",
                "cv_mean_auprc": best.get("cv_mean_auprc"),
                "cv_std_auprc": best.get("cv_std_auprc"),
                "cv_mean_auc": best.get("cv_mean_auc"),
                "cv_std_auc": best.get("cv_std_auc"),
                "test_auprc": best.get("test_auprc"),
                "test_roc_auc": best.get("test_roc_auc"),
                "best_params": best.get("best_params", {}),
                "n_rows": meta.get("n_rows"),
                "n_features": meta.get("n_features"),
                "positives": meta.get("positives"),
                "pos_rate": meta.get("pos_rate"),
                "wall_seconds": meta.get("wall_seconds"),
                "expanded_trials": meta.get("expanded_trials"),
                "mode": meta.get("mode"),
                "top_features": top_features,
            }
        )

    # Collect failed runs
    for fail_path in sorted(list(run_folder.glob("*/*/*/*/meta_failed.json")) + list(run_folder.glob("*/*/*/*/*/meta_failed.json"))):
        rel = fail_path.relative_to(run_folder)
        parts = rel.parts
        if len(parts) >= 5:
            operator, model, run_variant, grid_name = parts[:4]
            failed.append(
                dict(operator=operator, model=model,
                     run_variant=run_variant, grid_name=grid_name)
            )

    return pd.DataFrame(records), failed


def load_all_trials(run_folder):
    """Load all results.csv files, returning a single DataFrame."""
    dfs = []
    for results_path in sorted(list(run_folder.glob("*/*/*/*/results.csv")) + list(run_folder.glob("*/*/*/*/*/results.csv"))):
        rel = results_path.relative_to(run_folder)
        parts = rel.parts
        if len(parts) < 5:
            continue
        operator, model, run_variant, grid_name = parts[:4]
        try:
            df = pd.read_csv(results_path)
            df["operator"] = operator
            df["model"] = model
            df["run_variant"] = run_variant
            df["grid_name"] = grid_name
            df["combo"] = f"{model}/{run_variant}/{grid_name}"

            if "params_json" in df.columns:
                def safe_parse(x):
                    try:
                        return json.loads(x) if pd.notna(x) else {}
                    except Exception:
                        return {}
                df["params"] = df["params_json"].apply(safe_parse)

            dfs.append(df)
        except Exception:
            pass

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def load_yaml_config(run_folder):
    """Load effective_config.yaml (or fallback names) from run folder."""
    for name in ["effective_config.yaml", "hpsearch_config.yaml", "config.yaml"]:
        p = run_folder / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# REPORT SECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def section_header_block(run_label):
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    return [
        "#" * 80,
        "# MODEL TUNING REPORT",
        f"# Run:       {run_label}",
        f"# Generated: {now}",
        "#" * 80,
    ]


def section_completeness(df, failed, config, operators, combos, n_operators):
    lines = [H1("Section 0: Completeness Check")]

    if config:
        # Build expected combos from YAML
        models_cfg = config.get("models", {}) or {}
        run_variants_cfg = config.get("run_variants", []) or []

        rv_only = {}
        for rv in run_variants_cfg:
            if isinstance(rv, dict) and rv.get("only_models"):
                rv_only[rv["name"]] = set(rv["only_models"])

        expected_combos = set()
        expected_trials_count = {}  # combo -> expected n_trials
        for mname, mcfg in models_cfg.items():
            grids = (mcfg or {}).get("grids", {}) or {}
            for rv in run_variants_cfg:
                rv_name = rv["name"]
                if rv_name in rv_only and mname not in rv_only[rv_name]:
                    continue
                for gname, gspec in grids.items():
                    combo = f"{mname}/{rv_name}/{gname}"
                    expected_combos.add(combo)
                    expected_trials_count[combo] = count_expected_trials(gspec)

        expected_total = len(expected_combos) * n_operators
        actual_total = len(df)

        lines.append(f"Expected combos per operator (from YAML): {len(expected_combos)}")
        lines.append(f"Expected total runs: {expected_total}  ({len(expected_combos)} combos × {n_operators} operators)")
        lines.append(f"Actual completed runs: {actual_total}")
        lines.append(f"Missing: {max(0, expected_total - actual_total)}")

        # Per-operator completeness
        lines.append("")
        lines.append(f"  {'Operator':<12} {'Runs':>6} {'Expected':>10}  Status")
        lines.append(f"  {'-'*45}")
        for op in operators:
            op_count = len(df[df["operator"] == op])
            if op_count >= len(expected_combos):
                status = "OK"
            else:
                status = f"MISSING {len(expected_combos) - op_count}"
            lines.append(f"  {op:<12} {op_count:>6} {len(expected_combos):>10}  {status}")

        # Missing combos
        existing_set = set(df["combo"].unique())
        missing_combos = expected_combos - existing_set
        if missing_combos:
            lines.append(f"\nMissing combos (not found for any operator):")
            for c in sorted(missing_combos):
                lines.append(f"  - {c}")

        # Trial count checks (from meta.json expanded_trials)
        lines.append("")
        lines.append("Trial count validation (expected vs executed):")
        lines.append(f"  {'Combo':<75} {'Expected':>10} {'Avg executed':>14}  Status")
        lines.append(f"  {'-'*110}")
        for combo in sorted(expected_combos & existing_set):
            n_exp = expected_trials_count.get(combo, "?")
            sub = df[df["combo"] == combo]
            avg_exec = sub["expanded_trials"].dropna().mean() if "expanded_trials" in sub.columns else None
            if avg_exec is not None and n_exp != "?":
                diff = abs(avg_exec - n_exp)
                status = "OK" if diff <= 2 else f"DIFF={diff:.0f}"
            else:
                status = "N/A"
            avg_str = f"{avg_exec:.0f}" if avg_exec is not None else "N/A"
            lines.append(f"  {combo:<75} {str(n_exp):>10} {avg_str:>14}  {status}")

    else:
        lines.append("WARNING: No YAML config found in run folder. Skipping completeness check.")
        lines.append(f"Operators with data: {', '.join(operators)}")
        lines.append(f"Combos found: {len(combos)}")

    if failed:
        lines.append(f"\nFailed runs ({len(failed)}):")
        for f_ in failed:
            lines.append(f"  - {f_['operator']}/{f_['model']}/{f_['run_variant']}/{f_['grid_name']}")

    return lines


def section_full_table(df, combos):
    lines = [H1("Section 1: Full Model Outputs Table (all runs)")]
    lines.append("Sorted by operator then test_auprc desc.  Higher is better for both metrics.")
    lines.append("")

    if len(df) == 0:
        lines.append("  No data loaded.")
        return lines

    display = df[[
        "operator", "combo", "test_auprc", "test_roc_auc",
        "cv_mean_auprc", "cv_mean_auc", "pos_rate", "n_rows"
    ]].copy().sort_values(["operator", "test_auprc"], ascending=[True, False])

    # Format
    W = {"operator": 10, "combo": 75, "test_auprc": 11, "test_roc_auc": 10,
         "cv_mean_auprc": 11, "cv_mean_auc": 10, "pos_rate": 10, "n_rows": 9}
    hdr_labels = ["operator", "combo", "test_PRAUC", "test_AUC",
                  "cv_PRAUC", "cv_AUC", "pos_rate", "n_rows"]

    header = "  ".join(lbl.ljust(W[col]) for lbl, col in zip(hdr_labels, W))
    lines.append(header)
    lines.append("-" * len(header))

    for _, row in display.iterrows():
        def fv(col):
            v = row[col]
            if pd.isna(v):
                return "N/A"
            if col == "n_rows":
                return f"{int(v):,}"
            if col in ("test_auprc", "test_roc_auc", "cv_mean_auprc", "cv_mean_auc", "pos_rate"):
                return f"{v:.4f}"
            return str(v)
        lines.append("  ".join(fv(col).ljust(W[col]) for col in W))

    # Variants summary
    lines.append(H2("Variants Summary (avg across operators)"))
    lines.append(f"  {'Combo':<75} {'Ops':>5} {'avg_test_PRAUC':>15} {'avg_test_AUC':>13} {'avg_cv_PRAUC':>13}")
    lines.append(f"  {'-'*125}")
    for combo in sorted(combos):
        sub = df[df["combo"] == combo]
        ap = sub["test_auprc"].mean()
        aa = sub["test_roc_auc"].mean()
        cp = sub["cv_mean_auprc"].mean()
        lines.append(f"  {combo:<75} {len(sub):>5} {fmt(ap):>15} {fmt(aa):>13} {fmt(cp):>13}")

    return lines


def section_best_per_operator(df, operators):
    lines = [H1("Section 2: Best Per Operator")]

    for op in operators:
        op_df = df[df["operator"] == op].copy()
        if len(op_df) == 0:
            continue

        lines.append(H2(f"Operator: {op.upper()}  ({len(op_df)} runs)"))

        # Dataset metadata
        m = op_df.iloc[0]
        try:
            nr = f"{int(m['n_rows']):,}" if pd.notna(m["n_rows"]) else "N/A"
            pos = f"{int(m['positives'])}" if pd.notna(m["positives"]) else "N/A"
            pr = fmt(m["pos_rate"]) if pd.notna(m.get("pos_rate")) else "N/A"
            lines.append(f"  Dataset: {nr} rows | {pos} positives | pos_rate={pr}")
        except Exception:
            lines.append("  Dataset: N/A")
        lines.append("")

        # Top 5 by test_auprc
        top5 = op_df.nlargest(5, "test_auprc")
        lines.append("  TOP 5 BY TEST PR-AUC:")
        lines.append(f"  {'#':<3} {'Combo':<75} {'test_PRAUC':>11} {'test_AUC':>10} {'cv_PRAUC':>10} {'cv_AUC':>9} {'secs':>7}")
        lines.append(f"  {'-'*130}")
        for rank, (_, row) in enumerate(top5.iterrows(), 1):
            secs = f"{int(row['wall_seconds'])}" if pd.notna(row.get("wall_seconds")) else "N/A"
            lines.append(
                f"  {rank:<3} {row['combo']:<75} {fmt(row['test_auprc']):>11} "
                f"{fmt(row['test_roc_auc']):>10} {fmt(row['cv_mean_auprc']):>10} "
                f"{fmt(row['cv_mean_auc']):>9} {secs:>7}"
            )
        lines.append("")

        # Top 5 by test_roc_auc
        top5_auc = op_df.nlargest(5, "test_roc_auc")
        lines.append("  TOP 5 BY TEST AUC (ROC):")
        lines.append(f"  {'#':<3} {'Combo':<75} {'test_PRAUC':>11} {'test_AUC':>10}")
        lines.append(f"  {'-'*103}")
        for rank, (_, row) in enumerate(top5_auc.iterrows(), 1):
            lines.append(
                f"  {rank:<3} {row['combo']:<75} {fmt(row['test_auprc']):>11} "
                f"{fmt(row['test_roc_auc']):>10}"
            )
        lines.append("")

        # Worst 3
        worst3 = op_df.nsmallest(3, "test_auprc")
        lines.append("  BOTTOM 3 BY TEST PR-AUC:")
        for rank, (_, row) in enumerate(worst3.iterrows(), 1):
            lines.append(
                f"  {rank}. {row['combo']:<75}  PRAUC={fmt(row['test_auprc'])}  "
                f"AUC={fmt(row['test_roc_auc'])}"
            )

    return lines


def section_tuning_analysis(df, config, operators, n_operators):
    lines = [H1("Section 3: Hyperparameter Tuning Analysis")]

    if not config:
        lines.append("WARNING: No YAML config found. Cannot perform tuning analysis.")
        return lines

    models_cfg = config.get("models", {}) or {}
    run_variants_cfg = config.get("run_variants", []) or []
    rv_names = [rv["name"] for rv in run_variants_cfg if isinstance(rv, dict)]
    rv_only = {}
    for rv in run_variants_cfg:
        if isinstance(rv, dict) and rv.get("only_models"):
            rv_only[rv["name"]] = set(rv["only_models"])

    for mname, mcfg in models_cfg.items():
        model_df = df[df["model"] == mname]
        if len(model_df) == 0:
            continue

        lines.append(H2(f"Model: {mname}  ({len(model_df)} runs across all operators/variants/grids)"))

        grids = (mcfg or {}).get("grids", {}) or {}
        for gname, gspec in grids.items():
            n_exp_trials = count_expected_trials(gspec)
            lines.append(f"\n  Grid: {gname}  (expected {n_exp_trials} trials per run)")

            # Show parameter ranges from YAML
            if isinstance(gspec, dict) and gspec.get("mode") == "cartesian":
                fixed = gspec.get("fixed", {}) or {}
                params = gspec.get("params", {}) or {}
                if fixed:
                    lines.append(f"    Fixed params: {json.dumps(fixed)}")
                if params:
                    lines.append(f"    Swept params (ranges):")
                    for k, v in params.items():
                        lines.append(f"      {k:<30}: {v}")
            elif isinstance(gspec, list):
                lines.append(f"    Mode: explicit list ({len(gspec)} trials)")
                all_keys = set()
                for t in gspec:
                    if isinstance(t, dict):
                        all_keys.update(t.keys())
                for k in sorted(all_keys):
                    vals = sorted(
                        set(str(t.get(k)) for t in gspec if isinstance(t, dict) and k in t)
                    )
                    lines.append(f"      {k:<30}: {vals}")

            # Per-run_variant execution check
            lines.append(f"\n    Execution check per run_variant:")
            lines.append(
                f"    {'run_variant':<38} {'ops':>5}/{str(n_operators):<4} "
                f"{'avg_PRAUC':>11} {'avg_AUC':>10}  Status"
            )
            lines.append(f"    {'-'*85}")

            for rv_name in rv_names:
                if rv_name in rv_only and mname not in rv_only[rv_name]:
                    continue

                combo_key = f"{mname}/{rv_name}/{gname}"
                sub = df[df["combo"] == combo_key]

                if len(sub) == 0:
                    lines.append(
                        f"    {rv_name:<38} {'0':>5}/{str(n_operators):<4} "
                        f"{'N/A':>11} {'N/A':>10}  NOT FOUND"
                    )
                    continue

                avg_prauc = sub["test_auprc"].mean()
                avg_auc = sub["test_roc_auc"].mean()

                # Check trial counts vs expected
                issues = []
                for op in operators:
                    op_sub = sub[sub["operator"] == op]
                    if len(op_sub) == 0:
                        issues.append(f"{op}:MISSING")
                    else:
                        actual_exp = op_sub.iloc[0].get("expanded_trials")
                        if pd.notna(actual_exp) and n_exp_trials > 0:
                            if abs(actual_exp - n_exp_trials) > 2:
                                issues.append(f"{op}:trials={actual_exp:.0f}≠{n_exp_trials}")

                status = "OK" if not issues else f"ISSUES({len(issues)}): " + ", ".join(issues[:4])
                lines.append(
                    f"    {rv_name:<38} {len(sub):>5}/{str(n_operators):<4} "
                    f"{fmt(avg_prauc):>11} {fmt(avg_auc):>10}  {status}"
                )

            # Score distribution across all operators for this grid
            gdf = df[(df["model"] == mname) & (df["grid_name"] == gname)]
            if len(gdf) > 0:
                vals = gdf["test_auprc"].dropna()
                if len(vals) > 0:
                    lines.append(f"\n    Score distribution (test_auprc, all operators/variants):")
                    lines.append(
                        f"    min={vals.min():.4f}  p25={vals.quantile(0.25):.4f}  "
                        f"median={vals.median():.4f}  p75={vals.quantile(0.75):.4f}  "
                        f"max={vals.max():.4f}  mean={vals.mean():.4f}"
                    )

    return lines


def section_feature_importance(df, operators):
    lines = [H1("Section 4: Feature Importance Analysis")]
    lines.append("Features extracted from best model per run. Cross-operator overlap shown at end.")
    lines.append("Higher is better for importance values.")
    lines.append("")

    op_top10_sets = {}

    for op in operators:
        op_df = df[df["operator"] == op]
        if len(op_df) == 0:
            continue

        top5 = op_df.nlargest(5, "test_auprc")

        # Aggregate feature importances across top-5 models
        feat_scores = defaultdict(float)
        feat_counts = defaultdict(int)
        for _, row in top5.iterrows():
            fi = row.get("top_features", [])
            if not fi:
                continue
            for feat, imp in fi[:15]:
                feat_scores[feat] += float(imp) if not math.isnan(float(imp)) else 0
                feat_counts[feat] += 1

        if not feat_scores:
            lines.append(f"  Operator {op}: No feature importance data available.")
            lines.append("")
            op_top10_sets[op] = set()
            continue

        avg_imp = {f: feat_scores[f] / feat_counts[f] for f in feat_scores}
        ranked = sorted(avg_imp.items(), key=lambda x: -x[1])[:12]

        lines.append(f"  Operator {op}  —  top-12 features from top-5 PRAUC models:")
        lines.append(f"  {'#':>3} {'Feature':<55} {'avg_imp':>10} {'in N/5 models':>14}")
        lines.append(f"  {'-'*85}")
        for rank, (feat, imp) in enumerate(ranked, 1):
            cnt = feat_counts[feat]
            lines.append(f"  {rank:>3} {feat:<55} {imp:>10.6f} {cnt:>14}")
        lines.append("")

        op_top10_sets[op] = {f for f, _ in ranked}

    # Cross-operator overlap
    lines.append(H2("Cross-Operator: Most Consistent Top Features"))

    all_feats = set()
    for feats in op_top10_sets.values():
        all_feats.update(feats)

    feat_op_count = {
        f: sum(1 for op in operators if f in op_top10_sets.get(op, set()))
        for f in all_feats
    }
    top_cross = sorted(feat_op_count.items(), key=lambda x: -x[1])[:25]

    lines.append(f"  (Feature appears in top-12 importance for N operators' best models)")
    lines.append(f"  {'Feature':<58} {'#Ops':>6}  Bar")
    lines.append(f"  {'-'*80}")
    for feat, cnt in top_cross:
        bar = "█" * cnt + "░" * (len(operators) - cnt)
        lines.append(f"  {feat:<58} {cnt:>6}  {bar}")

    return lines


def section_cross_operator(df, operators, combos, n_operators):
    lines = [H1("Section 5: Cross-Operator Findings")]

    # ── Best combos overall ──────────────────────────────────────────────────
    lines.append("BEST MODEL/VARIANT COMBINATIONS (ranked by avg test_auprc across operators)")
    lines.append("")

    top1_per_op = {}
    for op in operators:
        sub = df[df["operator"] == op]
        if len(sub) == 0:
            continue
        top1_per_op[op] = sub.nlargest(1, "test_auprc").iloc[0]["combo"]

    top1_counts = defaultdict(int)
    for combo in top1_per_op.values():
        top1_counts[combo] += 1

    agg = (
        df.groupby("combo")
        .agg(
            avg_prauc=("test_auprc", "mean"),
            std_prauc=("test_auprc", "std"),
            avg_auc=("test_roc_auc", "mean"),
            std_auc=("test_roc_auc", "std"),
            n_ops=("operator", "count"),
        )
        .reset_index()
    )
    agg["n_top1"] = agg["combo"].map(lambda c: top1_counts.get(c, 0))
    agg = agg.sort_values("avg_prauc", ascending=False)

    lines.append(
        f"  {'Combo':<75} {'avg_PRAUC':>11} {'std':>7} {'avg_AUC':>10} {'std':>7} "
        f"{'ops':>5} {'#best':>7}"
    )
    lines.append(f"  {'-'*130}")
    for _, row in agg.head(20).iterrows():
        lines.append(
            f"  {row['combo']:<75} {fmt(row['avg_prauc']):>11} {fmt(row['std_prauc']):>7} "
            f"{fmt(row['avg_auc']):>10} {fmt(row['std_auc']):>7} "
            f"{int(row['n_ops']):>5} {int(row['n_top1']):>7}"
        )

    # ── Always-bad models ───────────────────────────────────────────────────
    lines.append(H2("Models that Consistently Score Low (candidates for removal/deprioritisation)"))

    threshold_per_op = df.groupby("operator")["test_auprc"].median().to_dict()

    combo_above = {}
    for combo in combos:
        above = 0
        for op in operators:
            sub = df[(df["combo"] == combo) & (df["operator"] == op)]
            if len(sub) == 0:
                continue
            val = sub.iloc[0]["test_auprc"]
            if pd.notna(val) and val >= threshold_per_op.get(op, 0):
                above += 1
        combo_above[combo] = above

    ranked_bad = sorted(combo_above.items(), key=lambda x: x[1])

    lines.append("  (Sorted by number of operators where the combo is below median PRAUC)")
    lines.append(f"  {'Combo':<75} {'Ops≥median':>12}  avg_PRAUC")
    lines.append(f"  {'-'*105}")
    for combo, n_above in ranked_bad[:20]:
        avg_p = df[df["combo"] == combo]["test_auprc"].mean()
        lines.append(f"  {combo:<75} {n_above:>4}/{n_operators:<7}  {fmt(avg_p)}")

    # ── Best params per best model ──────────────────────────────────────────
    lines.append(H2("Best Params from Top-1 Model per Operator"))
    for op in operators:
        op_df = df[df["operator"] == op]
        if len(op_df) == 0:
            continue
        best = op_df.nlargest(1, "test_auprc").iloc[0]
        p_str = json.dumps(best["best_params"], separators=(", ", "=")).strip("{}")
        lines.append(
            f"  {op}: [{best['combo']}]  "
            f"PRAUC={fmt(best['test_auprc'])}  AUC={fmt(best['test_roc_auc'])}"
        )
        lines.append(f"      params: {p_str}")

    return lines


def section_outlier_performance(df, trials_df, operators, combos, n_operators):
    lines = [H1("Section 6: Outlier Performance & Range Suggestions")]
    lines.append(
        "METHOD: For each hyperparameter with 3+ distinct values, we compute a normalized rank\n"
        "for each operator's best value: 0.0 = chose the minimum, 1.0 = chose the maximum,\n"
        "0.5 = chose the middle (for a 3-value range). A suggestion fires when:\n"
        "  - median normalized rank <= 0.2  AND  >=80% of operators chose the minimum  → DECREASE\n"
        "  - median normalized rank >= 0.8  AND  >=80% of operators chose the maximum  → INCREASE\n"
        "  - otherwise: OK (range looks good, or no consistent directional preference)\n\n"
        "Parameters with only 2 values have no middle reference and are shown for info only.\n"
        "The '#best' column shows how many operators found each value to be their best.\n"
    )

    if len(trials_df) == 0:
        lines.append("WARNING: No results.csv data loaded. Cannot perform outlier analysis.")
        return lines

    metric_col = "cv_mean_auprc" if "cv_mean_auprc" in trials_df.columns else None
    if metric_col is None:
        lines.append("WARNING: cv_mean_auprc column not found in trials data.")
        return lines

    # 80% of available operators must agree on the direction
    RANK_LOW_THRESH = 0.2
    RANK_HIGH_THRESH = 0.8

    all_suggestions = []

    for combo in sorted(combos):
        parts = combo.split("/")
        if len(parts) != 3:
            continue

        ct = trials_df[trials_df["combo"] == combo].copy()
        if len(ct) == 0:
            continue

        # Collect all param keys from parsed params dicts
        all_params = set()
        for p in ct["params"] if "params" in ct.columns else []:
            if isinstance(p, dict):
                all_params.update(p.keys())
        if not all_params:
            continue

        def _extract_param(p, k):
            if not isinstance(p, dict):
                return None
            v = p.get(k)
            # Lists are unhashable; convert to tuple so pandas can call .unique()
            return tuple(v) if isinstance(v, list) else v

        for param in sorted(all_params):
            ct[f"_p_{param}"] = ct["params"].apply(lambda p, k=param: _extract_param(p, k))

        combo_lines = []

        for param in sorted(all_params):
            pcol = f"_p_{param}"
            param_vals = ct[pcol].dropna().unique()
            if len(param_vals) < 2:
                continue

            # Sort: numeric first, then None (e.g. max_depth=null), then strings
            try:
                sorted_vals = sorted(
                    param_vals,
                    key=lambda v: (v is None, float(v) if v is not None else 0),
                )
            except (TypeError, ValueError):
                sorted_vals = sorted(param_vals, key=lambda v: (v is None, str(v)))

            n_unique = len(sorted_vals)
            # Normalized rank map: 0.0 = min, 1.0 = max
            val_to_nrank = {v: i / (n_unique - 1) for i, v in enumerate(sorted_vals)}

            # Per-operator: find best value and its normalized rank
            op_best_val = {}
            op_nrank = {}
            for op in operators:
                op_ct = ct[ct["operator"] == op]
                if len(op_ct) == 0:
                    continue
                grp = op_ct.groupby(pcol)[metric_col].mean()
                if len(grp) == 0:
                    continue
                best_v = grp.idxmax()
                op_best_val[op] = best_v
                op_nrank[op] = val_to_nrank.get(best_v, 0.5)

            if not op_best_val:
                continue

            n_data = len(op_best_val)
            nranks = list(op_nrank.values())
            median_nrank = float(np.median(nranks))

            # Count operators voting for each boundary (exact min / exact max)
            n_low = sum(1 for v in op_best_val.values() if str(v) == str(sorted_vals[0]))
            n_high = sum(1 for v in op_best_val.values() if str(v) == str(sorted_vals[-1]))
            n_mid = n_data - n_low - n_high
            op_threshold = max(2, int(n_data * 0.8))

            # Win count per value (# operators that found it best)
            win_counts = defaultdict(int)
            for v in op_best_val.values():
                win_counts[str(v)] += 1

            # Decision — only flag for 3+ value params; 2-value has no middle
            direction = None
            flag = ""
            if n_unique >= 3:
                if n_low >= op_threshold and median_nrank <= RANK_LOW_THRESH:
                    direction = "DECREASE"
                    flag = (
                        f"<< DECREASE RANGE  "
                        f"[median_rank={median_nrank:.2f}, {n_low}/{n_data} ops chose min={sorted_vals[0]}]"
                    )
                elif n_high >= op_threshold and median_nrank >= RANK_HIGH_THRESH:
                    direction = "INCREASE"
                    flag = (
                        f">> INCREASE RANGE  "
                        f"[median_rank={median_nrank:.2f}, {n_high}/{n_data} ops chose max={sorted_vals[-1]}]"
                    )

            # Aggregate PRAUC per value across all operators
            grp_all = ct.groupby(pcol)[metric_col].agg(["mean", "std", "count"])

            vals_repr = str([str(v) for v in sorted_vals])
            if len(vals_repr) > 72:
                vals_repr = f"[{sorted_vals[0]} ... {sorted_vals[-1]}]  ({n_unique} values)"

            param_lines = [f"\n  Param: {param}  (range: {vals_repr})"]

            # Direction summary line
            rank_bar = "".join(
                "▼" if op_nrank.get(op, 0.5) <= RANK_LOW_THRESH
                else "▲" if op_nrank.get(op, 0.5) >= RANK_HIGH_THRESH
                else "●"
                for op in operators if op in op_nrank
            )
            if n_unique >= 3:
                param_lines.append(
                    f"  median_rank={median_nrank:.2f}  "
                    f"low={n_low}  mid={n_mid}  high={n_high}  "
                    f"ops={n_data}  [{rank_bar}]  (▼=min ●=mid ▲=max)"
                )
            else:
                param_lines.append(
                    f"  2-value param — low={n_low}  high={n_high}  ops={n_data}  [{rank_bar}]"
                )

            # Per-value table
            param_lines.append(
                f"  {'Value':<22} {'avg_PRAUC':>10} {'std':>8} {'n_trials':>9} {'#best':>6}  Position"
            )
            param_lines.append(f"  {'-'*68}")
            for val in sorted_vals:
                if val in grp_all.index:
                    r = grp_all.loc[val]
                    nrank_v = val_to_nrank[val]
                    wins = win_counts.get(str(val), 0)
                    # Visual position in range
                    pos_slots = 10
                    pos_idx = round(nrank_v * (pos_slots - 1))
                    pos_bar = "·" * pos_idx + "█" + "·" * (pos_slots - 1 - pos_idx)
                    position = f"[{pos_bar}]  nrank={nrank_v:.2f}"
                    param_lines.append(
                        f"  {str(val):<22} {r['mean']:>10.4f} {r['std']:>8.4f} "
                        f"{int(r['count']):>9} {wins:>6}  {position}"
                    )

            if direction:
                param_lines.append(f"  *** {flag}")
                op_bv = "  ".join(
                    f"{op}→{op_best_val[op]}" for op in operators if op in op_best_val
                )
                param_lines.append(f"      Per-op best: {op_bv}")
                all_suggestions.append({
                    "combo": combo,
                    "param": param,
                    "direction": direction,
                    "min_val": sorted_vals[0],
                    "max_val": sorted_vals[-1],
                    "median_rank": median_nrank,
                    "n_extreme": max(n_low, n_high),
                    "n_data": n_data,
                })
            elif n_unique < 3:
                param_lines.append(f"  [INFO] 2-value param: no range suggestion applicable.")
            else:
                param_lines.append(
                    f"  [OK] low={n_low}/{n_data}  high={n_high}/{n_data}  "
                    f"mid={n_mid}/{n_data}  median_rank={median_nrank:.2f}"
                )

            combo_lines.extend(param_lines)

        if combo_lines:
            lines.append(H2(f"Option: {combo}"))
            lines.extend(combo_lines)

    # ── Summary ─────────────────────────────────────────────────────────────
    lines.append(H1("Section 6 Summary: All Range Adjustment Suggestions"))

    if all_suggestions:
        all_suggestions.sort(key=lambda x: (-x["n_extreme"], x["median_rank"] if x["direction"] == "DECREASE" else 1 - x["median_rank"]))
        lines.append(
            f"  {'Combo':<75} {'Param':<28} {'Direction':<10} {'Ops agree':>10} "
            f"{'med_rank':>9}  Current range"
        )
        lines.append(f"  {'-'*145}")
        for s in all_suggestions:
            evidence = f"{s['n_extreme']}/{s['n_data']}"
            lines.append(
                f"  {s['combo']:<75} {s['param']:<28} {s['direction']:<10} {evidence:>10} "
                f"{s['median_rank']:>9.2f}  [{s['min_val']}, {s['max_val']}]"
            )
    else:
        lines.append("  No clear range adjustment suggestions found.")
        lines.append(
            "  All parameters appear to have performance spread across the range "
            "(or no consistent directional preference across operators)."
        )

    return lines


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(run_label, run_folder=None, out_path=None):
    # NB (organisatie-versie): `run_folder` en `out_path` zijn optionele parameters geworden zodat de
    # organisatie-runner een concrete run-map + outputpad kan meegeven i.p.v. de hardcoded Snellius-roots.
    # Zonder die parameters is het gedrag identiek aan het origineel (OUTPUTS_ROOT/REPORTS_ROOT).
    run_folder = Path(run_folder) if run_folder else OUTPUTS_ROOT / run_label
    if not run_folder.exists():
        print(f"ERROR: Run folder not found: {run_folder}", file=sys.stderr)
        sys.exit(1)

    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_ROOT / f"{run_label}_report.txt"

    print(f"[1/5] Loading best.json / meta.json / feature_importances.csv ...")
    df, failed = load_best_data(run_folder)
    print(f"      Found {len(df)} completed runs, {len(failed)} failed.")

    print(f"[2/5] Loading all results.csv (trial-level data) ...")
    trials_df = load_all_trials(run_folder)
    print(f"      Loaded {len(trials_df):,} individual trial rows.")

    print(f"[3/5] Loading YAML config ...")
    config = load_yaml_config(run_folder)
    print(f"      Config: {'found' if config else 'NOT found'}")

    operators = sorted(df["operator"].unique()) if len(df) > 0 else []
    combos = sorted(df["combo"].unique()) if len(df) > 0 else []
    n_operators = len(operators)

    print(f"      Operators: {operators}  ({n_operators} total)")
    print(f"      Combos:    {len(combos)} distinct model/variant/grid combinations")

    print(f"[4/5] Generating report sections ...")

    all_lines = []
    W = all_lines.extend

    W(section_header_block(run_label))
    all_lines.append("")
    all_lines.append(f"Run folder:   {run_folder}")
    all_lines.append(f"Completed runs: {len(df)}")
    all_lines.append(f"Failed runs:    {len(failed)}")
    all_lines.append(f"Operators:      {', '.join(operators)}  ({n_operators})")
    all_lines.append(f"Combos/op:      {len(combos)}")
    all_lines.append(f"Total trials:   {len(trials_df):,}")
    all_lines.append("")

    W(section_completeness(df, failed, config, operators, combos, n_operators))
    W(section_full_table(df, combos))
    W(section_best_per_operator(df, operators))
    W(section_tuning_analysis(df, config, operators, n_operators))
    W(section_feature_importance(df, operators))
    W(section_cross_operator(df, operators, combos, n_operators))
    W(section_outlier_performance(df, trials_df, operators, combos, n_operators))

    # Footer
    all_lines.append("")
    all_lines.append("#" * 80)
    all_lines.append(f"# END OF REPORT: {run_label}")
    all_lines.append("#" * 80)

    print(f"[5/5] Writing report ...")
    content = "\n".join(all_lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nReport written to: {out_path}")
    print(f"Lines: {len(all_lines)}  |  Size: {len(content):,} bytes")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <run_label>")
        print(f"       python {sys.argv[0]} mv_impute_20260304_155356")
        sys.exit(1)
    generate_report(sys.argv[1])
