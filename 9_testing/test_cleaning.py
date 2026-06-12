#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie cleaning-stap (stap 4 uit de README).

Draaien kan op twee manieren:

    # met pytest:
    pytest _organisatie_code/99_testing/test_cleaning.py -v

    # of gewoon als script:
    python _organisatie_code/99_testing/test_cleaning.py

De tests draaien de pure-Python pijplijn (`clean_directory`) op een *kopie* van de
dummy-data in een tijdelijke map, zodat `_organisatie_code/0_dummy_data/` zelf schoon blijft.
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

from clean_pipeline import clean_directory          # noqa: E402
from check_format import resolve_schema_key, organisatie_SCHEMA_BY_FILE  # noqa: E402

# Bestanden die in 0_dummy_data staan en hun verwachte schema-key.
EXPECTED_SCHEMA_KEYS = {
    "WOK_Bet.csv": "WOK_Bet.csv",
    "WOK_Complaint.csv": "WOK_Complaint.csv",
    "WOK_Game.csv": "WOK_Game.csv",
    "WOK_Game_Session_1.csv": "WOK_Game_Session.csv",
    "WOK_Intervention.csv": "WOK_Intervention.csv",
    "WOK_Net_Deposit_Threshold.csv": "WOK_Net_Deposit_Threshold.csv",
    "WOK_Operator.csv": "WOK_Operator.csv",
    "WOK_Player_Account_Transaction_1.csv": "WOK_Player_Account_Transaction.csv",
    "WOK_Player_Flags.csv": "WOK_Player_Flags.csv",
    "WOK_Player_Limits.csv": "WOK_Player_Limits.csv",
    "WOK_Player_Profile.csv": "WOK_Player_Profile.csv",
}


def _stage_dummy_data() -> tuple[Path, Path]:
    """Kopieer dummy-CSV's naar een tijdelijke input-map; geef (input_dir, out_dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_clean_test_"))
    input_dir = tmp / "raw"
    out_dir = tmp / "out"
    input_dir.mkdir()
    out_dir.mkdir()
    for csv in DUMMY_DIR.glob("*.csv"):
        shutil.copy(csv, input_dir / csv.name)
    return input_dir, out_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resolve_schema_key_for_dummy_files():
    """Elke dummy-bestandsnaam moet op de juiste schema-key mappen."""
    keys = organisatie_SCHEMA_BY_FILE.keys()
    for fname, expected in EXPECTED_SCHEMA_KEYS.items():
        skey, _suffix = resolve_schema_key(fname, keys)
        assert skey == expected, f"{fname} → {skey} (verwacht {expected})"






def test_only_first_chunk_writes_test_dir():
    """--onlyfirstchunk schrijft naar een TEST_cleaned_<stamp>/ map."""
    input_dir, out_dir = _stage_dummy_data()
    try:
        cleaned_dir = clean_directory(
            input_dir=input_dir,
            clean_out_dir=out_dir,
            chunksize=2000,
            only_first_chunk=True,
            do_label=False,  # labelling niet nodig voor deze smoke-test
            verbose=False,
        )
        assert cleaned_dir.name.startswith("TEST_cleaned_"), cleaned_dir.name
        assert list(cleaned_dir.glob("*.csv")), "Geen output in TEST_cleaned-map"
    finally:
        shutil.rmtree(input_dir.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_dummy_data_present,
        test_resolve_schema_key_for_dummy_files,
        test_clean_directory_produces_all_files,
        test_headers_normalized_and_labels_added,
        test_only_first_chunk_writes_test_dir,
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
