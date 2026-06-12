#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_cleaning.py  (organisatie-versie)
=============================

Pure-Python *runner* voor stap 4 (**CLEANING**) uit de README. Dit vervangt op de
organisatie-omgeving de Snellius-keten van:

    run_ALL_clean_only.sbatch  →  clean_runner.py  →  clean_and_parse.py --mode clean

Op Snellius werd het schoonmaken per operator (a..z) over een SLURM-array verdeeld,
met $TMPDIR-staging en symlinks. De organisatie werkt simpelweg met lokale CSV's in een map,
dus die hele orchestratie vervalt: je geeft één inputmap met ruwe WOK-CSV's mee en
het schoonmaken + labellen draait in één Python-proces.

Gebruik
-------
    # Schoon de standaard dummy-data (../0_dummy_data) → cleaned_<stamp>/ ernaast:
    python run_cleaning.py

    # Eigen input/output map:
    python run_cleaning.py --input-dir /pad/naar/raw_csvs --clean-out-dir /pad/naar/output

    # Snelle test op alleen de eerste chunk (kleine TEST_cleaned_<stamp>/ map):
    python run_cleaning.py --onlyfirstchunk --chunksize 2000

    # Zonder automatische outlier-labelling:
    python run_cleaning.py --no-label

De feitelijke schoonmaaklogica zit in `clean_pipeline.clean_directory`, die op zijn
beurt `cleaner.clean_csv_streaming` (per bestand, streamend) en `outlier_labeling.label_outliers`
aanroept — exact dezelfde functies als in de hoofdrepo.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Zorg dat de modules naast dit script importeerbaar zijn, ongeacht vanwaar je het start.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from clean_pipeline import clean_directory  # noqa: E402

# Default input: de dummy-data die in _organisatie_code/0_dummy_data staat.
DEFAULT_INPUT_DIR = (SCRIPT_DIR.parent / "0_dummy_data").resolve()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python cleaning runner (organisatie) voor ruwe WOK-CSV's."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Map met ruwe WOK-CSV's (default: {DEFAULT_INPUT_DIR}).",
    )
    parser.add_argument(
        "--clean-out-dir",
        type=Path,
        default=None,
        help="Rootmap waaronder cleaned_<stamp>/ wordt aangemaakt "
             "(default: naast --input-dir).",
    )
    parser.add_argument(
        "--glob",
        default="*.csv",
        help="Glob-patroon voor input-CSV's (default: *.csv).",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=400_000,
        help="Chunkgrootte bij streamend inlezen (default: 400_000).",
    )
    parser.add_argument(
        "--onlyfirstchunk",
        action="store_true",
        default=False,
        help="Alleen de eerste chunk schoonmaken (snelle test → TEST_cleaned_<stamp>/).",
    )
    parser.add_argument(
        "--no-label",
        dest="do_label",
        action="store_false",
        default=True,
        help="Sla de automatische outlier-labelling na het schoonmaken over.",
    )
    parser.add_argument(
        "--operator-prefix",
        default=None,
        help="Optioneel: zet OPERATOR_PREFIX zodat operator-specifieke prevalidatie-"
             "filters (operator_filters.py) actief worden. Default: geen filter.",
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

    # OPERATOR_PREFIX stuurt de operator-specifieke filters in operator_filters.py.
    # Op de organisatie staat die standaard leeg (= geen filter), maar je kunt 'm meegeven.
    if args.operator_prefix is not None:
        os.environ["OPERATOR_PREFIX"] = args.operator_prefix

    print(f"[run_cleaning] input-dir      : {args.input_dir}")
    print(f"[run_cleaning] clean-out-dir  : {args.clean_out_dir or '(naast input)'}")
    print(f"[run_cleaning] chunksize      : {args.chunksize:,}")
    print(f"[run_cleaning] onlyfirstchunk : {args.onlyfirstchunk}")
    print(f"[run_cleaning] labelling      : {args.do_label}")
    print(f"[run_cleaning] OPERATOR_PREFIX: {os.environ.get('OPERATOR_PREFIX', '') or '(leeg → geen filter)'}")

    t0 = time.perf_counter()
    cleaned_dir = clean_directory(
        input_dir=args.input_dir,
        clean_out_dir=args.clean_out_dir,
        glob_pattern=args.glob,
        chunksize=args.chunksize,
        only_first_chunk=args.onlyfirstchunk,
        verbose=args.verbose,
        do_label=args.do_label,
    )
    dt = time.perf_counter() - t0

    print(f"\n[run_cleaning] ✅ Klaar in {dt:,.2f}s")
    print(f"[run_cleaning] Cleaned output: {cleaned_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
