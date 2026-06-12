#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_report.py  (organisatie-versie)
===========================

Pure-Python *runner* die de twee rapportage-stappen combineert (organisatie-stappen 10 & 11;
origineel 17 "HP-dekkingsgraad" + 18 "Rapportage maken"). Vervangt
`hpsearch_coverage_report.sbatch` + `create_model_report.sbatch`.

Op één grid-run-map (output van stap 7, `run_grid.py`) draait dit achter elkaar:
1. **Dekkingsgraad** (`hpsearch_coverage_report.py`): per (operator, model, run_variant, grid)
   hoeveel trials gedraaid zijn t.o.v. het grid, of het tijdsbudget geraakt is, en de beste
   CV-/test-AUPRC — als tabel op stdout.
2. **Modelrapport** (`create_model_report.py`): een uitgebreid tekstrapport (`<label>_report.txt`)
   met o.a. compleetheid, beste model per operator, tuning-analyse en feature-importance.

Beide scripts verwachten de geneste layout `operator/model/run_variant/grid/` die `run_grid.py`
nu wegschrijft.

Gebruik
-------
    python run_report.py --run-dir /pad/naar/grid_run
    python run_report.py --run-dir /pad/naar/grid_run --out /pad/rapport.txt
    python run_report.py --run-dir /pad/naar/grid_run --coverage-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import hpsearch_coverage_report  # noqa: E402
import create_model_report       # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Pure-Python rapportage-runner (organisatie): dekkingsgraad + modelrapport."
    )
    p.add_argument("--run-dir", required=True, type=Path,
                   help="Grid-run-map (output van stap 7) met operator/model/run_variant/grid/.")
    p.add_argument("--out", type=Path, default=None,
                   help="Pad voor het tekstrapport (default: <run-dir>/<label>_report.txt).")
    p.add_argument("--coverage-only", action="store_true", default=False,
                   help="Alleen de dekkingsgraad-tabel, geen modelrapport.")
    p.add_argument("--report-only", action="store_true", default=False,
                   help="Alleen het modelrapport, geen dekkingsgraad-tabel.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        sys.exit(f"❌ --run-dir bestaat niet: {run_dir}")

    label = run_dir.name
    out_path = args.out if args.out is not None else run_dir / f"{label}_report.txt"

    # 1) Dekkingsgraad (stap 10)
    if not args.report_only:
        print("=" * 80)
        print("  [1] HP-DEKKINGSGRAAD")
        print("=" * 80)
        hpsearch_coverage_report.main([str(run_dir)])

    # 2) Modelrapport (stap 11)
    if not args.coverage_only:
        print("\n" + "=" * 80)
        print("  [2] MODELRAPPORT")
        print("=" * 80)
        written = create_model_report.generate_report(label, run_folder=run_dir, out_path=out_path)
        print(f"\n[run_report] ✅ Rapport: {written}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
