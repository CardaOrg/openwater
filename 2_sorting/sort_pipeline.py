#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sort_pipeline.py  (organisatie-versie)
==============================

Pure-Python orkestratie voor stap 2 (**Sorting op date**) uit de organisatie-README
(origineel: stap 6). Dit vervangt de Snellius-`run_ALL_sorting.sbatch`, die per
operator (a..z) × tabel (11 stuks) een SLURM-array-taak afvuurde.

Op de organisatie is er geen per-operator mappenstructuur: je hebt één geschoonde map
(`cleaned_<stamp>/`, output van stap 1). Deze pijplijn loopt daar simpelweg in één
Python-proces over alle tabellen en sorteert elke tabel op zijn datumkolom via de
bucket-sort uit `bucket_sort.py` (memory-efficiënt, twee passes).

De feitelijke sorteerlogica zit ongewijzigd in `bucket_sort.sort_table` (de body die
in het origineel in `main()` zat). Per tabel ontstaan maand-buckets `<tabel>_<n>.csv`
plus een `<tabel>_NaT.csv` voor rijen zonder geldige datum. De som van de rijen wordt
geaudit (rows_in == rows_out).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Optional

from bucket_sort import sort_table, TABLE_SORT_COL

# Herkent `cleaned_YYYYmmdd_HHMMSS` (en TEST_cleaned_...) mapnamen — om de nieuwste
# geschoonde map automatisch te kunnen kiezen (zelfde patroon als in 1_cleaning).
CLEANED_RE = re.compile(r"^(?:TEST_)?cleaned_(\d{8})_(\d{6})$", re.IGNORECASE)

# Alle tabellen die gesorteerd kunnen worden (bron van waarheid = bucket_sort).
ALL_TABLES: List[str] = list(TABLE_SORT_COL.keys())


def newest_cleaned_dir(parent_dir: str | Path) -> Optional[Path]:
    """Geef de nieuwste cleaned_<stamp>/ submap in `parent_dir`, of None."""
    parent = Path(parent_dir)
    if not parent.is_dir():
        return None
    cands = [p for p in parent.iterdir() if p.is_dir() and CLEANED_RE.match(p.name)]
    if not cands:
        return None
    return sorted(cands, key=lambda p: p.name)[-1].resolve()


def sort_directory(
    cleaned_dir: Optional[str | Path] = None,
    *,
    parent_dir: Optional[str | Path] = None,
    out_dir: Optional[str | Path] = None,
    operator_letter: str = "organisatie",
    tables: Optional[List[str]] = None,
    chunksize: int = 200_000,
) -> Path:
    """
    Sorteer alle (of een subset) tabellen in een geschoonde map op hun datumkolom.

    Parameters
    ----------
    cleaned_dir : concrete cleaned_<stamp>/ map (output van stap 1).
    parent_dir  : alternatief; kies automatisch de nieuwste cleaned_<stamp>/ hierin.
    out_dir     : doelmap. Default: `<cleaned_dir>_sorted_<stamp>/` als sibling.
    operator_letter : puur een logginglabel (organisatie kent geen a..z-operators).
    tables      : subset van tabellen; default alle uit TABLE_SORT_COL.
    chunksize   : chunkgrootte bij het bucketen (pass 1).

    Returns
    -------
    Path naar de aangemaakte gesorteerde map.
    """
    if cleaned_dir is None and parent_dir is None:
        raise ValueError("Geef óf cleaned_dir óf parent_dir mee.")

    if cleaned_dir is None:
        src = newest_cleaned_dir(parent_dir)
        if src is None:
            raise FileNotFoundError(f"Geen cleaned_<stamp>/ map gevonden onder {parent_dir}.")
        print(f"🔎 Nieuwste cleaned-map gekozen: {src}")
    else:
        src = Path(cleaned_dir).resolve()
        if not src.is_dir():
            raise FileNotFoundError(f"cleaned-map bestaat niet: {src}")

    # Eén gedeelde output-map voor alle tabellen (sibling van de cleaned-map).
    if out_dir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_dir = src.parent / f"{src.name}_sorted_{stamp}"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Default: ontdek álle WOK-tabellen die in de cleaned-map staan (niet alleen die met een
    # bekende sorteerkolom) — anders belanden de organisatie-relationele tabellen (WOK_Bet_Parts,
    # WOK_Bet_Transaction, WOK_Player_Limits_*, …) niet in de sorted-map en zijn ze weg voor de features.
    if not tables:
        import re as _re
        seen: List[str] = []
        for _p in sorted(Path(src).glob("*.csv")):
            if "_labelled" in _p.name or not _p.stem.startswith("WOK"):
                continue
            _name = _re.sub(r"_\d+$", "", _p.stem)   # strip eventuele chunk-suffix (_1, _24, …)
            if _name not in seen:
                seen.append(_name)
        tables = seen or ALL_TABLES

    print("\n" + "#" * 80)
    print(f"# SORT DIRECTORY  src={src}")
    print(f"#                 out={out_dir}")
    print(f"#                 tables={len(tables)}")
    print("#" * 80)

    results = []
    for table in tables:
        res = sort_table(
            operator_letter=operator_letter,
            cleaned_dir=src,
            table=table,
            out_dir=out_dir,
            chunksize=chunksize,
        )
        results.append(res)

    # Samenvatting over alle tabellen.
    sorted_n = sum(1 for r in results if not r["skipped"])
    skipped_n = sum(1 for r in results if r["skipped"])
    failed = [r["table"] for r in results if not r["skipped"] and not r["ok"]]

    print("\n" + "=" * 80)
    print(f"[SORT SUMMARY] {sorted_n} tabel(len) gesorteerd, {skipped_n} overgeslagen.")
    if failed:
        print(f"[SORT SUMMARY] ⚠️ AUDIT-mismatch voor: {', '.join(failed)}")
    else:
        print("[SORT SUMMARY] ✅ Alle gesorteerde tabellen passen qua rij-aantallen (audit OK).")
    print(f"[SORT SUMMARY] Output: {out_dir}")
    print("=" * 80)

    if failed:
        raise RuntimeError(f"Sort-audit mislukt voor tabellen: {failed}")

    return out_dir
