#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_features.py  (organisatie-versie)
=============================

Pure-Python *runner* voor stap 3 (**Features bouwen**) uit de organisatie-README
(origineel: stap 8, "Features voor een operator maken"). Dit vervangt op de organisatie:

    run_parse_only.sbatch  →  parse_runner.py  →  clean_and_parse.py --mode parse

Op Snellius zocht de sbatch per operator de nieuwste `cleaned_*_sorted_*` map, zette
X_TIJDSPAD/Y_TIJDSPAD via env-vars en bouwde een output-bestandsnaam met operator/periode.
Op de organisatie wijs je gewoon één geschoonde (en bij voorkeur gesorteerde) map aan en kies je
een scenario; de features komen in één CSV met één rij per `Player_Profile_ID`.

Gebruik
-------
    # Features voor een scenario op een concrete (gesorteerde) cleaned-map:
    python run_features.py --cleaned-dir /pad/naar/cleaned_..._sorted_... \
        --scenario Flexible_spanish --x-tijdspad 01062025:30062025 --y-tijdspad 01072025:31072025

    # Of: kies automatisch de nieuwste geschikte map in een parent (sorted > cleaned):
    python run_features.py --parent-dir /pad/naar/output --scenario Y-target

    # Slechts één enkele feature uit een scenario:
    python run_features.py --cleaned-dir <dir> --scenario Flexible_spanish --feature f0_net_winloss

    # Eigen output-pad:
    python run_features.py --cleaned-dir <dir> --scenario Scenario_1 --features-out /pad/feat.csv

De feitelijke berekening zit in `parse_pipeline.build_features` → `run_scenario`
(verbatim overgenomen uit `clean_and_parse.py`), met de feature-functies uit
`feature_engineering*.py`.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Zorg dat de modules naast dit script importeerbaar zijn, ongeacht vanwaar je het start.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from parse_pipeline import build_features, newest_features_input_dir, SCENARIOS  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python features runner (organisatie): bouw features voor een scenario."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--cleaned-dir",
        type=Path,
        default=None,
        help="Concrete geschoonde/gesorteerde map met WOK-CSV's (output van stap 1/2).",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Parent-map; kies automatisch de nieuwste geschikte map "
             "(cleaned_*_sorted_* heeft voorrang op cleaned_<stamp>/).",
    )
    parser.add_argument(
        "--scenario",
        default="Flexible_spanish_plus",
        choices=list(SCENARIOS.keys()),
        help="Te bouwen scenario (default: Flexible_spanish_plus).",
    )
    parser.add_argument(
        "--features-out",
        type=Path,
        default=None,
        help="Pad voor de output-CSV (default: features_<scenario>_<stamp>.csv naast input).",
    )
    parser.add_argument(
        "--x-tijdspad",
        default=None,
        help="X-tijdspad (features-periode), formaat 'DDMMYYYY:DDMMYYYY'.",
    )
    parser.add_argument(
        "--y-tijdspad",
        default=None,
        help="Y-tijdspad (target-periode), formaat 'DDMMYYYY:DDMMYYYY'.",
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Bereken alleen deze ene feature uit het scenario (leeg = alle).",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=400_000,
        help="Chunkgrootte bij het streamend inlezen (default: 400_000).",
    )
    parser.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        default=True,
        help="Minder uitgebreide logging op stdout.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # Bepaal input-map.
    if args.cleaned_dir is not None:
        cleaned_dir = args.cleaned_dir.resolve()
        if not cleaned_dir.is_dir():
            sys.exit(f"❌ --cleaned-dir bestaat niet: {cleaned_dir}")
    else:
        cleaned_dir = newest_features_input_dir(args.parent_dir)
        if cleaned_dir is None:
            sys.exit(f"❌ Geen geschikte cleaned/sorted map gevonden onder {args.parent_dir}.")
        print(f"🔎 Nieuwste input-map gekozen: {cleaned_dir}")

    # Bepaal output-pad.
    if args.features_out is not None:
        features_out = args.features_out
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        feat_part = args.feature or "all"
        features_out = cleaned_dir.parent / f"features_{stamp}_{args.scenario}_{feat_part}.csv"

    print(f"[run_features] cleaned-dir : {cleaned_dir}")
    print(f"[run_features] scenario    : {args.scenario}")
    print(f"[run_features] feature     : {args.feature or '(alle)'}")
    print(f"[run_features] x-tijdspad  : {args.x_tijdspad or '(geen)'}")
    print(f"[run_features] y-tijdspad  : {args.y_tijdspad or '(geen)'}")
    print(f"[run_features] features-out: {features_out}")

    t0 = time.perf_counter()
    df = build_features(
        cleaned_dir=cleaned_dir,
        scenario=args.scenario,
        features_out=features_out,
        x_tijdspad=args.x_tijdspad,
        y_tijdspad=args.y_tijdspad,
        feature=args.feature,
        chunksize=args.chunksize,
        verbose=args.verbose,
    )
    dt = time.perf_counter() - t0

    print(f"\n[run_features] ✅ Klaar in {dt:,.2f}s — vorm {df.shape}")
    print(f"[run_features] Output: {features_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
