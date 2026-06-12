#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie sorting-stap (stap 2 uit de organisatie-README; origineel: stap 6).

Draaien kan op twee manieren:

    pytest _organisatie_code/99_testing/test_sorting.py -v
    python _organisatie_code/99_testing/test_sorting.py

Aanpak: eerst de dummy-data schoonmaken (stap 1) in een tijdelijke map, daarna de
bucket-sort (stap 2) erop draaien. We controleren rij-behoud per tabel (geen data-
verlies) en de sorteervolgorde binnen een bucket.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

# --- Maak de modules importeerbaar (cleaning in ../1_cleaning, sorting in ../2_sorting) ---
HERE = Path(__file__).resolve().parent
CLEANING_DIR = (HERE.parent / "1_cleaning").resolve()
SORTING_DIR = (HERE.parent / "2_sorting").resolve()
DUMMY_DIR = (HERE.parent / "0_dummy_data" / "voorbeeld_fake").resolve()
for d in (CLEANING_DIR, SORTING_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from clean_pipeline import clean_directory          # noqa: E402
from sort_pipeline import sort_directory, newest_cleaned_dir, ALL_TABLES  # noqa: E402
from bucket_sort import TABLE_SORT_COL, collect_table_files  # noqa: E402


def _stage_and_clean() -> tuple[Path, Path]:
    """Kopieer dummy-data, schoon het, geef (tmp_root, cleaned_dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_sort_test_"))
    raw = tmp / "raw"
    out = tmp / "out"
    raw.mkdir()
    out.mkdir()
    for csv in DUMMY_DIR.glob("*.csv"):
        shutil.copy(csv, raw / csv.name)
    cleaned_dir = clean_directory(
        input_dir=raw, clean_out_dir=out, chunksize=2000, do_label=True, verbose=False
    )
    return tmp, cleaned_dir


def _rows_in_cleaned(cleaned_dir: Path, table: str) -> int:
    """Aantal datarijen voor een tabel in de cleaned-map (alle chunk-bestanden samen)."""
    total = 0
    for f in collect_table_files(cleaned_dir, table):
        total += len(pd.read_csv(f, low_memory=False))
    return total


def _rows_in_sorted(sorted_dir: Path, table: str) -> int:
    """Aantal datarijen voor een tabel in de gesorteerde map (buckets + NaT)."""
    pat = re.compile(rf"^{re.escape(table)}_(?:\d+|NaT)\.csv$")
    total = 0
    for p in sorted_dir.glob(f"{table}_*.csv"):
        if pat.match(p.name):
            total += len(pd.read_csv(p, low_memory=False))
    return total


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_sorting_dependency_present():
    """De enige dependency voor sorting (bucket_sort) moet importeerbaar zijn."""
    import bucket_sort  # noqa: F401
    assert hasattr(bucket_sort, "sort_table")
    assert len(ALL_TABLES) == 11


def test_sort_directory_creates_output_and_passes_audit():
    """sort_directory draait alle tabellen en de row-audit slaagt (geen exception)."""
    tmp, cleaned_dir = _stage_and_clean()
    try:
        sorted_dir = sort_directory(cleaned_dir=cleaned_dir, chunksize=2000)
        assert sorted_dir.exists() and sorted_dir.is_dir()
        assert sorted_dir.name.endswith("_sorted_" + sorted_dir.name.split("_sorted_")[-1])
        # Er moet voor minstens één tabel output zijn.
        assert list(sorted_dir.glob("*.csv")), "Geen output-bestanden gevonden"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_row_counts_preserved_per_table():
    """Per tabel: som van cleaned-rijen == som van gesorteerde rijen (buckets + NaT)."""
    tmp, cleaned_dir = _stage_and_clean()
    try:
        sorted_dir = sort_directory(cleaned_dir=cleaned_dir, chunksize=2000)
        for table in ALL_TABLES:
            n_in = _rows_in_cleaned(cleaned_dir, table)
            n_out = _rows_in_sorted(sorted_dir, table)
            assert n_in == n_out, f"{table}: {n_in} cleaned != {n_out} sorted"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_within_bucket_sort_order_is_ascending():
    """Binnen elk bucket-bestand is de sorteerkolom (NaT genegeerd) oplopend gesorteerd.

    De geschoonde relationele data is snake_case (bv. ``bet_start_datetime``), terwijl
    ``TABLE_SORT_COL`` de CamelCase-namen heeft; de bucket-sort matcht case-tolerant, dus zoeken we
    de kolom hier óók case-insensitief op. Sub-tabellen zonder datumkolom (sort=None) en tabellen
    waarvan de sorteerkolom niet in deze dataset zit, worden overgeslagen.
    """
    tmp, cleaned_dir = _stage_and_clean()
    try:
        sorted_dir = sort_directory(cleaned_dir=cleaned_dir, chunksize=2000)
        checked_any = False
        for table in ALL_TABLES:
            sort_col = TABLE_SORT_COL.get(table)
            if not sort_col:
                continue  # sub-tabel zonder datumkolom
            bucket_re = re.compile(rf"^{re.escape(table)}_\d+\.csv$")
            for p in sorted_dir.glob(f"{table}_*.csv"):
                if not bucket_re.match(p.name):
                    continue
                df = pd.read_csv(p, low_memory=False)
                # case-insensitief: de relationele output is snake_case
                col = next((c for c in df.columns if c.lower() == sort_col.lower()), None)
                if col is None:
                    continue  # sorteerkolom zit niet in deze tabel
                dt = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
                if len(dt) >= 2:
                    assert dt.is_monotonic_increasing, f"{p.name} niet oplopend gesorteerd op {col}"
                    checked_any = True
        assert checked_any, "Geen enkel bucket met >=2 rijen om volgorde te checken"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)




def test_subset_tables_only_sorts_requested():
    """Met een tabel-subset worden alleen die tabellen weggeschreven."""
    tmp, cleaned_dir = _stage_and_clean()
    try:
        subset = ["WOK_Player_Profile", "WOK_Bet"]
        sorted_dir = sort_directory(cleaned_dir=cleaned_dir, tables=subset, chunksize=2000)
        produced_tables = set()
        for p in sorted_dir.glob("*.csv"):
            m = re.match(r"^(WOK_[A-Za-z_]+?)_(?:\d+|NaT)\.csv$", p.name)
            if m:
                produced_tables.add(m.group(1))
        assert produced_tables <= set(subset), f"Onverwachte tabellen: {produced_tables - set(subset)}"
        assert "WOK_Player_Profile" in produced_tables
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_newest_cleaned_dir_autopick():
    """sort_directory via parent-dir kiest de nieuwste cleaned_<stamp>/ map."""
    tmp, cleaned_dir = _stage_and_clean()
    try:
        out_parent = cleaned_dir.parent
        assert newest_cleaned_dir(out_parent) == cleaned_dir
        sorted_dir = sort_directory(parent_dir=out_parent, chunksize=2000)
        # De gesorteerde map is gebaseerd op de gekozen cleaned-map.
        assert sorted_dir.name.startswith(cleaned_dir.name + "_sorted_")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_sorting_dependency_present,
        test_sort_directory_creates_output_and_passes_audit,
        test_row_counts_preserved_per_table,
        test_within_bucket_sort_order_is_ascending,
        test_subset_tables_only_sorts_requested,
        test_newest_cleaned_dir_autopick,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests geslaagd.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
