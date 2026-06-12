#!/usr/bin/env python3
"""
build_all_stats.py — create per-operator 1-row ALL aggregate CSVs from existing merged CSVs.

For each operator and each period prefix, reads the existing base-scenario merged CSV,
computes mean/std/min/max over the ALL_FEATURES columns, and saves a 1-row CSV named:
    {data_dir}/{op}/{period_prefix}_ALL_merged.csv

Usage:
    python build_all_stats.py \
        --data-dir /projects/prjs1763/4_feature_files_after_07_10_25 \
        --base-scenario Flexible_spanish_plus \
        --prefixes "01052025_31052025_01062025_30062025_valid,01052025_30062025_01072025_31072025_test,..."
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ALL_FEATURES = [
    "f0_net_winloss",
    "f3_total_wagered",
    "f25_voluntary_suspensions",
    "f12_deposits_per_day",
    "f11_withdrawals_per_day",
]
ALL_STATS = ["mean", "std", "min", "max"]

# Identifier baked into the output filename so you can see what was used
# e.g. "f0f3f25f12f11_mean-std-min-max"
_FEATURE_ID = "".join(f.split("_")[0] for f in ALL_FEATURES)   # f0f3f25f12f11
_STATS_ID   = "-".join(ALL_STATS)                               # mean-std-min-max
ALL_SUFFIX  = f"ALL_{_FEATURE_ID}_{_STATS_ID}"                  # ALL_f0f3f25f12f11_mean-std-min-max


def find_latest_file(op_dir: Path, prefix: str) -> Path:
    candidates = sorted(op_dir.glob(f"{prefix}*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No files matching {op_dir}/{prefix}*.csv")
    return candidates[0]


def load_merged_df(op_dir: Path, period_prefix: str, base_scenario: str) -> pd.DataFrame:
    """Load full merged CSV, falling back to joining x+y parts if it doesn't exist."""
    try:
        src = find_latest_file(op_dir, f"{period_prefix}_{base_scenario}")
        print(f"[INFO] {op_dir.name}/{period_prefix}: using full merged {src.name}")
        return pd.read_csv(src)
    except FileNotFoundError:
        pass

    # Parse prefix: expect {xs}_{xe}_{ys}_{ye}_{pass}
    parts = period_prefix.split("_")
    date_parts = [p for p in parts if len(p) == 8 and p.isdigit()]
    pass_parts = [p for p in parts if not (len(p) == 8 and p.isdigit())]
    if len(date_parts) < 4 or not pass_parts:
        raise FileNotFoundError(
            f"No full merged file for {period_prefix} and prefix cannot be parsed for x+y fallback"
        )
    xs, xe, ys, ye = date_parts[0], date_parts[1], date_parts[2], date_parts[3]
    pass_label = pass_parts[0]
    x_prefix = f"{xs}_{xe}_{pass_label}_{base_scenario}_x"
    y_prefix = f"{ys}_{ye}_{pass_label}_y"
    try:
        x_file = find_latest_file(op_dir, x_prefix)
        y_file = find_latest_file(op_dir, y_prefix)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"No full merged file for {period_prefix} and x+y fallback failed: {e}"
        )
    print(f"[INFO] {op_dir.name}/{period_prefix}: x+y fallback — {x_file.name} + {y_file.name}")
    df_x = pd.read_csv(x_file)
    df_y = pd.read_csv(y_file)
    return df_x.merge(df_y, on="Player_Profile_ID", how="inner", suffixes=("", "_y"))


# NB (organisatie-versie): de stats-berekening is uit `build_all_stats_for_operator` gelicht naar
# de herbruikbare functie `compute_all_stats_row(df)`, zodat de organisatie-pijplijn (die op één
# features-CSV werkt i.p.v. op a..z operator-mappen) exact dezelfde berekening gebruikt.
# Tevens is in het error-pad de verwijzing naar de niet-bestaande variabele `src` (een
# latente NameError in het origineel) vervangen door een betekenisvolle context-string.
def compute_all_stats_row(df: pd.DataFrame, *, context: str = "") -> dict:
    """Bereken mean/std/min/max over de ALL_FEATURES-kolommen die in `df` aanwezig zijn."""
    present = [f for f in ALL_FEATURES if f in df.columns]
    if not present:
        raise ValueError(f"None of {ALL_FEATURES} found in {context or '<dataframe>'}")

    row = {}
    for col in present:
        vals = df[col].dropna()
        row[f"mean_{col}"] = float(vals.mean()) if len(vals) > 0 else float("nan")
        row[f"std_{col}"]  = float(vals.std())  if len(vals) > 0 else float("nan")
        row[f"min_{col}"]  = float(vals.min())  if len(vals) > 0 else float("nan")
        row[f"max_{col}"]  = float(vals.max())  if len(vals) > 0 else float("nan")
    return row


def build_all_stats_for_operator(op_dir: Path, period_prefix: str, base_scenario: str) -> Path:
    df = load_merged_df(op_dir, period_prefix, base_scenario)

    row = compute_all_stats_row(df, context=f"{op_dir.name}/{period_prefix}")

    out_path = op_dir / f"{period_prefix}_{ALL_SUFFIX}_merged.csv"
    pd.DataFrame([row]).to_csv(out_path, index=False)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--base-scenario", default="Flexible_spanish_plus")
    ap.add_argument("--prefixes", required=True, help="Comma-separated period prefixes (valid and test)")
    ap.add_argument("--operators", default="", help="Comma-separated operators (default: all a-z dirs)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    prefixes = [p.strip() for p in args.prefixes.split(",") if p.strip()]

    if args.operators:
        operators = [o.strip() for o in args.operators.split(",") if o.strip()]
    else:
        operators = sorted(d.name for d in data_dir.iterdir() if d.is_dir() and len(d.name) == 1)

    ok = 0
    errors = 0
    for op in operators:
        op_dir = data_dir / op
        if not op_dir.is_dir():
            print(f"[SKIP] {op}: dir not found")
            continue
        for pref in prefixes:
            try:
                out = build_all_stats_for_operator(op_dir, pref, args.base_scenario)
                print(f"[OK] {op} / {pref} → {out.name} ({len(ALL_FEATURES)*4} stats)")
                ok += 1
            except Exception as e:
                print(f"[ERR] {op} / {pref}: {e}")
                errors += 1

    print(f"\nDone: {ok} OK, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
