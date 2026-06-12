#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie label-only stap (stap 5 uit de README).

Draaien kan op twee manieren:

    pytest _organisatie_code/99_testing/test_label_only.py -v
    python _organisatie_code/99_testing/test_label_only.py

Aanpak: eerst de dummy-data schoonmaken ZONDER labelling (do_label=False) in een
tijdelijke map, en daarna de losse label-only stap erop draaien. Zo testen we exact
het pad dat op Snellius `--mode label_only` was.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

# --- Maak de cleaning-modules importeerbaar (ze staan in ../1_cleaning) ---
HERE = Path(__file__).resolve().parent
CLEANING_DIR = (HERE.parent / "1_cleaning").resolve()
DUMMY_DIR = (HERE.parent / "0_dummy_data" / "voorbeeld_fake").resolve()
if str(CLEANING_DIR) not in sys.path:
    sys.path.insert(0, str(CLEANING_DIR))

from clean_pipeline import (  # noqa: E402
    clean_directory,
    label_only_directory,
    newest_cleaned_dir,
)

LABEL_COLS = ["outlier_Registration_Date", "outlier_Player_Profile_Modified"]


def _stage_dummy_data() -> tuple[Path, Path]:
    """Kopieer dummy-CSV's naar een tijdelijke input-map; geef (input_dir, out_dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_label_test_"))
    input_dir = tmp / "raw"
    out_dir = tmp / "out"
    input_dir.mkdir()
    out_dir.mkdir()
    for csv in DUMMY_DIR.glob("*.csv"):
        shutil.copy(csv, input_dir / csv.name)
    return input_dir, out_dir


def _clean_without_labels(input_dir: Path, out_dir: Path) -> Path:
    """Schoon de data zonder labelling, geef de cleaned_<stamp>/ map terug."""
    return clean_directory(
        input_dir=input_dir,
        clean_out_dir=out_dir,
        chunksize=2000,
        do_label=False,   # labelling expliciet overslaan → dat doet de label-only stap
        verbose=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_label_only_dependency_present():
    """De enige dependency voor label-only (outlier_labeling) moet importeerbaar zijn."""
    import outlier_labeling  # noqa: F401
    assert hasattr(outlier_labeling, "label_outliers")


def test_clean_without_labels_has_no_label_columns():
    """Sanity: zonder labelling staan de outlier-kolommen er nog NIET in."""
    input_dir, out_dir = _stage_dummy_data()
    try:
        cleaned_dir = _clean_without_labels(input_dir, out_dir)
        prof = pd.read_csv(cleaned_dir / "WOK_Player_Profile.csv")
        for col in LABEL_COLS:
            assert col not in prof.columns, f"{col} zou er nog niet moeten zijn"
    finally:
        shutil.rmtree(input_dir.parent, ignore_errors=True)








# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_label_only_dependency_present,
        test_clean_without_labels_has_no_label_columns,
        test_label_only_adds_columns_via_cleaned_dir,
        test_label_only_autopicks_newest_via_parent_dir,
        test_label_only_registration_mode_only,
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
