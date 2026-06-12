#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_descriptive.py  (organisatie-versie)
================================

Pure-Python *runner* voor stap 5 (**Descriptive tasks uitvoeren**) uit de organisatie-README
(origineel: stap 12). Vervangt:

    run_ALL_description.sbatch  →  descriptive_stats.py

Maakt van een feature-CSV (output van stap 3) een beschrijvend tekstrapport + plots
(target-verdeling, correlatie-heatmap, histogrammen) in een dated submap.

Gebruik
-------
    # Op een concrete features-CSV:
    python run_descriptive.py --features-csv /pad/naar/features_..._all.csv \
        --target y_self_exclusion_20250701_20250731

    # Of: kies automatisch de nieuwste features_*.csv in een map:
    python run_descriptive.py --parent-dir /pad/naar/output --target <kolom>

    # Eigen output-map:
    python run_descriptive.py --features-csv <csv> --output-dir /pad/descriptive_out
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

from descriptive_pipeline import build_descriptive_report, newest_features_csv  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python descriptive runner (organisatie): rapport + plots voor een features-CSV."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--features-csv",
        type=Path,
        default=None,
        help="Feature-CSV (output van stap 3) om te beschrijven.",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Map; kies automatisch de nieuwste features_*.csv hierin.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Basis-output-map (er komt een dated submap in). Default: 'descriptive/' naast input.",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Naam van de target-kolom (voor target-verdeling + correlatie).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.features_csv is not None:
        features_csv = args.features_csv.resolve()
        if not features_csv.is_file():
            sys.exit(f"❌ --features-csv bestaat niet: {features_csv}")
    else:
        features_csv = newest_features_csv(args.parent_dir)
        if features_csv is None:
            sys.exit(f"❌ Geen features_*.csv gevonden in {args.parent_dir}.")
        print(f"🔎 Nieuwste features-CSV gekozen: {features_csv}")

    print(f"[run_descriptive] features-csv: {features_csv}")
    print(f"[run_descriptive] target      : {args.target or '(geen)'}")
    print(f"[run_descriptive] output-dir  : {args.output_dir or '(descriptive/ naast input)'}")

    t0 = time.perf_counter()
    out = build_descriptive_report(features_csv, output_dir=args.output_dir, target=args.target)
    dt = time.perf_counter() - t0

    print(f"\n[run_descriptive] ✅ Klaar in {dt:,.2f}s")
    print(f"[run_descriptive] Output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
