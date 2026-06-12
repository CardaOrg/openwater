#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_active_filter.py  (organisatie-versie)
==================================

Pure-Python *runner* voor stap 4 (**Filteren op 'Active'**) uit de organisatie-README
(origineel: stap 11). Vervangt:

    run_build_status_lookup.sbatch  →  build_status_lookup.py

Maakt per cutoff-datum een `LAST_STATUS_LOOKUP_BEFORE_{DDMMYYYY}.csv` met de laatst bekende
`Player_Profile_Status` vóór die datum per speler — de basis om later op `ACTIVE` te filteren.
Input is een **gesorteerde** map (output van stap 2), want daar staan de
`WOK_Player_Profile_*.csv` chunk-bestanden.

Gebruik
-------
    # Op een concrete gesorteerde map, met één of meer cutoffs (DDMMYYYY):
    python run_active_filter.py --sorted-dir /pad/naar/cleaned_..._sorted_... \
        --cutoffs 01072026|01082026

    # Of: kies automatisch de nieuwste cleaned_*_sorted_* in een parent-map:
    python run_active_filter.py --parent-dir /pad/naar/output --cutoffs 01072026

    # Eigen output-map / overschrijven:
    python run_active_filter.py --sorted-dir <dir> --cutoffs 01072026 --out-dir /pad/out --overwrite

De cutoffs mogen met '|' of ',' gescheiden worden.
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

from active_filter_pipeline import build_status_lookups, newest_sorted_dir  # noqa: E402


def _parse_cutoffs(s: str) -> list[str]:
    """Splits cutoffs op '|' of ','."""
    return [c.strip() for c in s.replace(",", "|").split("|") if c.strip()]


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure-Python active-filter runner (organisatie): bouw last-status lookups per cutoff."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--sorted-dir",
        type=Path,
        default=None,
        help="Concrete gesorteerde map (cleaned_*_sorted_*) met WOK_Player_Profile_*.csv.",
    )
    src.add_argument(
        "--parent-dir",
        type=Path,
        default=None,
        help="Parent-map; de nieuwste cleaned_*_sorted_* daarin wordt automatisch gekozen.",
    )
    parser.add_argument(
        "--cutoffs",
        required=True,
        help="Cutoff-datums DDMMYYYY, gescheiden met '|' of ',' (bijv. 01072026|01082026).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Doelmap voor de lookup-CSV's (default: naast de gesorteerde map).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overschrijf bestaande lookup-bestanden.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cutoffs = _parse_cutoffs(args.cutoffs)
    if not cutoffs:
        sys.exit("❌ Geen geldige cutoffs opgegeven.")

    if args.sorted_dir is not None:
        sorted_dir = args.sorted_dir.resolve()
        if not sorted_dir.is_dir():
            sys.exit(f"❌ --sorted-dir bestaat niet: {sorted_dir}")
    else:
        sorted_dir = newest_sorted_dir(args.parent_dir)
        if sorted_dir is None:
            sys.exit(f"❌ Geen cleaned_*_sorted_* map gevonden onder {args.parent_dir}.")
        print(f"🔎 Nieuwste gesorteerde map gekozen: {sorted_dir}")

    print(f"[run_active_filter] sorted-dir : {sorted_dir}")
    print(f"[run_active_filter] cutoffs    : {cutoffs}")
    print(f"[run_active_filter] out-dir    : {args.out_dir or '(naast sorted-dir)'}")

    t0 = time.perf_counter()
    paths = build_status_lookups(
        sorted_dir=sorted_dir,
        cutoffs=cutoffs,
        out_dir=args.out_dir,
        overwrite=args.overwrite,
    )
    dt = time.perf_counter() - t0

    print(f"\n[run_active_filter] ✅ Klaar in {dt:,.2f}s — {len(paths)} lookup(s)")
    for p in paths:
        print(f"[run_active_filter]   → {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
