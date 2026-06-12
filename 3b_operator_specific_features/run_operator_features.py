#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_operator_features.py  (organisatie-versie)
======================================

Pure-Python *runner* voor stap 3b (**Extra features voor het totaalalgoritme**) uit de
organisatie-README (origineel: stap 10). Vervangt:

    run_ALL_build_operator_features.sbatch  →  build_all_stats.py

Op Snellius liep dit per operator (a..z) en per periode-prefix over `data_dir/<op>/`.
Op de organisatie aggregeer je over één merged features-CSV (de output van stap 3): mean/std/min/max
over een vaste set kernfeatures → één 1-rij aggregaat-CSV.

Gebruik
-------
    # Aggregeer over één features-CSV (output van stap 3):
    python run_operator_features.py --features-csv /pad/naar/features_..._all.csv

    # Of: kies automatisch de nieuwste features_*.csv in een map:
    python run_operator_features.py --parent-dir /pad/naar/output

    # Eigen output-pad:
    python run_operator_features.py --features-csv <csv> --out /pad/aggregaat.csv

De berekening zit in `build_all_stats.compute_all_stats_row` (ongewijzigd uit de hoofdrepo).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Zorg dat de modules naast dit script importeerbaar zijn, ongeacht vanwaar je het start.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_features_pipeline import build_all_stats_for_file  # noqa: E402


def _newest_features_csv(parent_dir: Path) -> Path | None:
    """Nieuwste features_*.csv in `parent_dir` (op mtime)."""
    cands = sorted(parent_dir.glob("features_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python runner (organisatie): bouw operator-specifieke ALL-aggregaat features."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--features-csv",
        type=Path,
        default=None,
        help="Merged features-CSV (output van stap 3) om over te aggregeren.",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Map; kies automatisch de nieuwste features_*.csv hierin.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Doelpad voor de aggregaat-CSV (default: <stem>_<ALL_SUFFIX>_merged.csv naast input).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.features_csv is not None:
        features_csv = args.features_csv.resolve()
        if not features_csv.is_file():
            sys.exit(f"❌ --features-csv bestaat niet: {features_csv}")
    else:
        features_csv = _newest_features_csv(args.parent_dir)
        if features_csv is None:
            sys.exit(f"❌ Geen features_*.csv gevonden in {args.parent_dir}.")
        print(f"🔎 Nieuwste features-CSV gekozen: {features_csv}")

    print(f"[run_operator_features] features-csv: {features_csv}")
    print(f"[run_operator_features] out         : {args.out or '(naast input)'}")

    t0 = time.perf_counter()
    out_path = build_all_stats_for_file(features_csv, out_path=args.out)
    dt = time.perf_counter() - t0

    print(f"\n[run_operator_features] ✅ Klaar in {dt:,.2f}s")
    print(f"[run_operator_features] Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
