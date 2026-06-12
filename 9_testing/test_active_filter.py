#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie active-filter stap (stap 4 uit de organisatie-README; origineel: stap 11).

Draaien:
    pytest _organisatie_code/99_testing/test_active_filter.py -v
    python _organisatie_code/99_testing/test_active_filter.py

Aanpak: dummy-data schoonmaken (stap 1) → sorteren (stap 2) → last-status lookups (stap 4).
De dummy-profielen zijn gewijzigd op 2026-06-01, dus een cutoff van 01072026 vangt alle
spelers; 01062026 vangt niemand.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

# --- Maak de modules importeerbaar ---
HERE = Path(__file__).resolve().parent
CLEANING_DIR = (HERE.parent / "1_cleaning").resolve()
SORTING_DIR = (HERE.parent / "2_sorting").resolve()
ACTIVE_DIR = (HERE.parent / "4_active_filter").resolve()
DUMMY_DIR = (HERE.parent / "0_dummy_data" / "voorbeeld_fake").resolve()
for d in (CLEANING_DIR, SORTING_DIR, ACTIVE_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from clean_pipeline import clean_directory                     # noqa: E402
from sort_pipeline import sort_directory                       # noqa: E402
from active_filter_pipeline import build_status_lookups, newest_sorted_dir  # noqa: E402

CUTOFF_ALL = "01072026"   # ná de dummy modified-datums (2026-06-01) → alle spelers
CUTOFF_NONE = "01062026"  # vóór de dummy modified-datums → geen spelers


def _clean_and_sort() -> tuple[Path, Path]:
    """Maak een gesorteerde map van de dummy-data; geef (tmp_root, sorted_dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_active_test_"))
    raw = tmp / "raw"
    raw.mkdir()
    for csv in DUMMY_DIR.glob("*.csv"):
        shutil.copy(csv, raw / csv.name)
    cleaned_dir = clean_directory(
        input_dir=raw, clean_out_dir=tmp / "out", chunksize=2000, do_label=True, verbose=False
    )
    sorted_dir = sort_directory(cleaned_dir=cleaned_dir, chunksize=2000)
    return tmp, sorted_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------




def test_multiple_cutoffs_one_file_each():
    """Meerdere cutoffs → één lookup-bestand per cutoff, met juiste naam."""
    tmp, sorted_dir = _clean_and_sort()
    try:
        paths = build_status_lookups(sorted_dir, [CUTOFF_ALL, CUTOFF_NONE], out_dir=tmp)
        names = {p.name for p in paths}
        assert names == {
            f"LAST_STATUS_LOOKUP_BEFORE_{CUTOFF_ALL}.csv",
            f"LAST_STATUS_LOOKUP_BEFORE_{CUTOFF_NONE}.csv",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_skip_existing_without_overwrite():
    """Bestaande lookup wordt overgeslagen tenzij overwrite=True."""
    tmp, sorted_dir = _clean_and_sort()
    try:
        build_status_lookups(sorted_dir, [CUTOFF_ALL], out_dir=tmp)
        out = tmp / f"LAST_STATUS_LOOKUP_BEFORE_{CUTOFF_ALL}.csv"
        mtime1 = out.stat().st_mtime_ns
        # Zonder overwrite: bestand blijft ongewijzigd.
        build_status_lookups(sorted_dir, [CUTOFF_ALL], out_dir=tmp, overwrite=False)
        assert out.stat().st_mtime_ns == mtime1
        # Met overwrite: bestand wordt opnieuw geschreven.
        build_status_lookups(sorted_dir, [CUTOFF_ALL], out_dir=tmp, overwrite=True)
        assert out.stat().st_mtime_ns != mtime1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_requires_sorted_profile_files():
    """Een map zonder WOK_Player_Profile_*.csv geeft een nette FileNotFoundError."""
    import pytest
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_active_empty_"))
    try:
        (tmp / "leeg").mkdir()
        with pytest.raises(FileNotFoundError):
            build_status_lookups(tmp / "leeg", [CUTOFF_ALL], out_dir=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_newest_sorted_dir_picks_latest():
    """newest_sorted_dir kiest een cleaned_*_sorted_* map (en negeert gewone cleaned-mappen)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_active_pick_"))
    try:
        (tmp / "cleaned_20250101_120000").mkdir()
        s = tmp / "cleaned_20250101_120000_sorted_20250101_130000"
        s.mkdir()
        assert newest_sorted_dir(tmp) == s.resolve()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_lookup_has_expected_schema_and_all_players,
        test_cutoff_before_all_modified_is_empty,
        test_multiple_cutoffs_one_file_each,
        test_skip_existing_without_overwrite,
        test_requires_sorted_profile_files,
        test_newest_sorted_dir_picks_latest,
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
