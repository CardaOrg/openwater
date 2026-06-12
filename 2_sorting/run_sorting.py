#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_sorting.py  (organisatie-versie)
============================

Pure-Python *runner* voor stap 2 (**Sorting op date**) uit de organisatie-README
(origineel: stap 6). Dit vervangt op de organisatie:

    run_ALL_sorting.sbatch  →  bucket_sort.py

Op Snellius verdeelde de sbatch het werk over een SLURM-array van 26 operators × 11
tabellen en zocht per operator de nieuwste `cleaned_<stamp>/` map. Op de organisatie wijs je
gewoon één geschoonde map aan (of een parent-map waarin de nieuwste wordt gekozen) en
worden alle tabellen in één Python-proces gesorteerd.

Waarom sorteren? Omdat veel features op tijd zijn gebaseerd is het handig de geschoonde
data te sorteren op tijdsvariabelen. Het resultaat is een nieuwe map
`<cleaned_dir>_sorted_<stamp>/` naast de input.

Gebruik
-------
    # Sorteer een concrete cleaned_<stamp>/ map:
    python run_sorting.py --cleaned-dir /pad/naar/cleaned_20260101_120000

    # Of: kies automatisch de nieuwste cleaned_<stamp>/ in een parent-map:
    python run_sorting.py --parent-dir /pad/naar/output

    # Slechts een subset tabellen:
    python run_sorting.py --cleaned-dir <dir> --tables WOK_Player_Profile,WOK_Bet

    # Eigen output-map / chunkgrootte:
    python run_sorting.py --cleaned-dir <dir> --out-dir /pad/out --chunksize 200000

De feitelijke sorteerlogica zit in `bucket_sort.sort_table`; de orkestratie over
tabellen in `sort_pipeline.sort_directory`.
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

from sort_pipeline import sort_directory, ALL_TABLES  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python sorting runner (organisatie): sorteer een geschoonde map op datum."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--cleaned-dir",
        type=Path,
        default=None,
        help="Concrete cleaned_<stamp>/ map om te sorteren.",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Parent-map; de nieuwste cleaned_<stamp>/ daarin wordt automatisch gekozen.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Doelmap (default: <cleaned_dir>_sorted_<stamp>/ als sibling).",
    )
    parser.add_argument(
        "--tables",
        type=str,
        default=None,
        help="Komma-gescheiden subset van tabellen (default: alle). "
             f"Beschikbaar: {', '.join(ALL_TABLES)}",
    )
    parser.add_argument(
        "--operator-letter",
        default="organisatie",
        help="Logginglabel (organisatie kent geen a..z-operators; default: 'organisatie').",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="Chunkgrootte bij het bucketen (default: 200_000).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    tables = [t.strip() for t in args.tables.split(",")] if args.tables else None

    print(f"[run_sorting] cleaned-dir : {args.cleaned_dir or '(auto via parent)'}")
    print(f"[run_sorting] parent-dir  : {args.parent_dir or '(n.v.t.)'}")
    print(f"[run_sorting] out-dir     : {args.out_dir or '(sibling _sorted_<stamp>)'}")
    print(f"[run_sorting] tables      : {tables or 'alle'}")
    print(f"[run_sorting] chunksize   : {args.chunksize:,}")

    t0 = time.perf_counter()
    out_dir = sort_directory(
        cleaned_dir=args.cleaned_dir,
        parent_dir=args.parent_dir,
        out_dir=args.out_dir,
        operator_letter=args.operator_letter,
        tables=tables,
        chunksize=args.chunksize,
    )
    dt = time.perf_counter() - t0

    print(f"\n[run_sorting] ✅ Klaar in {dt:,.2f}s")
    print(f"[run_sorting] Gesorteerde output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
