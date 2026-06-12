#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
active_filter_pipeline.py  (organisatie-versie)
=======================================

Pure-Python orkestratie voor stap 4 (**Filteren op 'Active'**) uit de organisatie-README
(origineel: stap 11). Vervangt `run_build_status_lookup.sbatch`.

Wat doet deze stap? Per cutoff-datum bepaalt hij de **laatst bekende
`Player_Profile_Status` vóór die datum** per speler, uit de gesorteerde
`WOK_Player_Profile_*.csv` bestanden (output van stap 2). Daarmee kun je later filteren op
spelers die op een peilmoment `ACTIVE` waren. Uitvoer per cutoff:
`LAST_STATUS_LOOKUP_BEFORE_{DDMMYYYY}.csv` met kolommen `Player_Profile_ID, last_status`.

Op Snellius liep dit per operator over `cleaned_root/<op>/cleaned_*_sorted_*` →
`features_root/<op>/`. Op de organisatie is er één dataset, dus je wijst één gesorteerde map aan.

De kernberekening (`last_status_before_cutoff`) komt ongewijzigd uit `build_status_lookup.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import pandas as pd

from build_status_lookup import last_status_before_cutoff, parse_ddmmyyyy

# Herkent een gesorteerde map (output van stap 2): cleaned_<stamp>_sorted_<...>.
_SORTED_RE = re.compile(r"^(?:TEST_)?cleaned_\d{8}_\d{6}_sorted_", re.IGNORECASE)


def newest_sorted_dir(parent_dir: str | Path) -> Optional[Path]:
    """Geef de nieuwste cleaned_*_sorted_* submap in `parent_dir`, of None."""
    parent = Path(parent_dir)
    if not parent.is_dir():
        return None
    cands = sorted(p for p in parent.iterdir() if p.is_dir() and _SORTED_RE.match(p.name))
    return cands[-1].resolve() if cands else None


def build_status_lookups(
    sorted_dir: str | Path,
    cutoffs: List[str],
    *,
    out_dir: Optional[str | Path] = None,
    overwrite: bool = False,
) -> List[Path]:
    """
    Maak voor elke cutoff een LAST_STATUS_LOOKUP_BEFORE_{DDMMYYYY}.csv op basis van de
    gesorteerde profielbestanden in `sorted_dir`.

    Parameters
    ----------
    sorted_dir : gesorteerde map met WOK_Player_Profile_*.csv (output van stap 2).
    cutoffs    : lijst DDMMYYYY-strings (bijv. ['01072026', '01082026']).
    out_dir    : doelmap voor de lookup-CSV's. Default: naast `sorted_dir` (sibling).
    overwrite  : overschrijf bestaande lookup-bestanden.

    Returns
    -------
    Lijst met geschreven (of bestaande) lookup-paden.
    """
    sdir = Path(sorted_dir).resolve()
    if not sdir.is_dir():
        raise FileNotFoundError(f"gesorteerde map bestaat niet: {sdir}")

    profile_files = sorted(sdir.glob("WOK_Player_Profile_*.csv"))
    if not profile_files:
        raise FileNotFoundError(
            f"Geen WOK_Player_Profile_*.csv in {sdir} — draai eerst stap 2 (sorting)."
        )

    out_dir = Path(out_dir).resolve() if out_dir else sdir.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for cutoff_str in cutoffs:
        cutoff_str = cutoff_str.strip()
        if not cutoff_str:
            continue
        out_path = out_dir / f"LAST_STATUS_LOOKUP_BEFORE_{cutoff_str}.csv"
        if out_path.exists() and not overwrite:
            print(f"[SKIP] {cutoff_str}: bestaat al ({out_path.name})")
            written.append(out_path)
            continue

        cutoff = parse_ddmmyyyy(cutoff_str)
        df = last_status_before_cutoff(profile_files, cutoff)
        df.to_csv(out_path, index=False)
        n_active = (df["last_status"].astype(str).str.upper() == "ACTIVE").sum() if len(df) else 0
        print(f"[OK] {cutoff_str}: {len(df):,} spelers, {n_active:,} actief → {out_path.name}")
        written.append(out_path)

    return written
