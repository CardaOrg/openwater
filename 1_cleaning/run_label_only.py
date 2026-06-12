#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_label_only.py  (organisatie-versie)
===============================

Pure-Python *runner* voor stap 5 (**Outlier detection via labelling**) uit de README.

Op Snellius werd dit als aparte job gedraaid om geheugen/tijd te besparen:

    run_ALL_label_only.sbatch  →  label_runner.py  →  clean_and_parse.py --mode label_only

Dat `--mode label_only` zocht per operator (a..z) de nieuwste `cleaned_<stamp>/` map
op en draaide daar `label_outliers(..., inplace=True, only_label=True)` op. De
schoonmaak zelf doet dit al automatisch (zie run_cleaning.py); deze losse stap is
puur om de labelling apart te kunnen herhalen.

Op de organisatie vervalt de SLURM-array / OPERATOR_PREFIX-lookup: je wijst gewoon een
bestaande cleaned-map aan (of een parent-map waarin de nieuwste automatisch wordt
gekozen) en de labelling draait in-place.

Gebruik
-------
    # Direct een concrete cleaned_<stamp>/ map labellen:
    python run_label_only.py --cleaned-dir /pad/naar/cleaned_20260101_120000

    # Of: kies automatisch de nieuwste cleaned_<stamp>/ in een parent-map:
    python run_label_only.py --parent-dir /pad/naar/0_dummy_data

    # Alleen registratie- of modified-labels (default: both):
    python run_label_only.py --cleaned-dir <dir> --mode registration

Enige afhankelijkheid is `outlier_labeling.label_outliers` (al aanwezig in deze map).
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

from clean_pipeline import label_only_directory  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python label-only runner (organisatie) voor een geschoonde map."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--cleaned-dir",
        type=Path,
        default=None,
        help="Concrete cleaned_<stamp>/ map om te labellen.",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Parent-map; de nieuwste cleaned_<stamp>/ daarin wordt automatisch gekozen.",
    )
    parser.add_argument(
        "--mode",
        choices=["both", "registration", "modified"],
        default="both",
        help="Welke outlier-labels berekend worden (default: both).",
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

    print(f"[run_label_only] cleaned-dir : {args.cleaned_dir or '(auto via parent)'}")
    print(f"[run_label_only] parent-dir  : {args.parent_dir or '(n.v.t.)'}")
    print(f"[run_label_only] mode        : {args.mode}")

    t0 = time.perf_counter()
    target = label_only_directory(
        cleaned_dir=args.cleaned_dir,
        parent_dir=args.parent_dir,
        verbose=args.verbose,
        mode=args.mode,
    )
    dt = time.perf_counter() - t0

    print(f"\n[run_label_only] ✅ Klaar in {dt:,.2f}s")
    print(f"[run_label_only] Gelabelde map: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
