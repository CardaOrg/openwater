#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie features-stap (stap 3 uit de organisatie-README; origineel: stap 8).

Draaien:
    pytest _organisatie_code/99_testing/test_features.py -v
    python _organisatie_code/99_testing/test_features.py

Aanpak: dummy-data schoonmaken (stap 1) → features bouwen (stap 3) op scenario's die
op de dummy-data werken. Twee scenario's zijn klein en robuust genoeg om door te rekenen:
'Y-target' (alleen de target) en 'Scenario_1' (avg_nr_of_game_transactions).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# --- Maak de modules importeerbaar ---
HERE = Path(__file__).resolve().parent
CLEANING_DIR = (HERE.parent / "1_cleaning").resolve()
FEATURES_DIR = (HERE.parent / "3_features").resolve()
DUMMY_DIR = (HERE.parent / "0_dummy_data" / "voorbeeld_fake").resolve()
for d in (CLEANING_DIR, FEATURES_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from clean_pipeline import clean_directory                       # noqa: E402
from parse_pipeline import build_features, SCENARIOS, newest_features_input_dir  # noqa: E402

# Tijdvensters die passen bij de dummy-data (juni features / juli target).
X_PAD = "01062025:30062025"
Y_PAD = "01072025:31072025"

# Scenario's die op de dummy-data daadwerkelijk doorrekenen → (verwacht aantal kolommen).
WORKING_SCENARIOS = {
    "Y-target": 2,      # Player_Profile_ID + target
}


def _clean_dummy() -> tuple[Path, Path]:
    """Maak een cleaned-map van de dummy-data; geef (tmp_root, cleaned_dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_feat_test_"))
    raw = tmp / "raw"
    raw.mkdir()
    for csv in DUMMY_DIR.glob("*.csv"):
        shutil.copy(csv, raw / csv.name)
    cleaned_dir = clean_directory(
        input_dir=raw, clean_out_dir=tmp / "cl", chunksize=2000, do_label=True, verbose=False
    )
    return tmp, cleaned_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_features_registry_loads():
    """FEATURES_REGISTRY en SCENARIOS laden zonder ontbrekende dependencies."""
    from parse_pipeline import FEATURES_REGISTRY
    assert len(FEATURES_REGISTRY) > 100
    assert "Y-target" in SCENARIOS and "Flexible_spanish_plus" in SCENARIOS


@pytest.mark.parametrize("scenario,n_cols", list(WORKING_SCENARIOS.items()))
def test_build_features_produces_player_table(scenario, n_cols):
    """build_features levert een tabel met Player_Profile_ID + featurekolom(men)."""
    tmp, cleaned_dir = _clean_dummy()
    try:
        out = tmp / f"{scenario}.csv"
        df = build_features(
            cleaned_dir=cleaned_dir, scenario=scenario, features_out=out,
            x_tijdspad=X_PAD, y_tijdspad=Y_PAD, chunksize=2000, verbose=False,
        )
        assert "Player_Profile_ID" in df.columns
        assert df.shape[1] == n_cols, f"{scenario}: {df.shape[1]} kolommen (verwacht {n_cols})"
        assert len(df) >= 1
        # Output-CSV is weggeschreven en herinleesbaar.
        assert out.exists()
        reread = pd.read_csv(out)
        assert list(reread.columns) == list(df.columns)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)




def test_dedup_on_player_profile_id():
    """Output bevat geen dubbele Player_Profile_ID's."""
    tmp, cleaned_dir = _clean_dummy()
    try:
        df = build_features(
            cleaned_dir=cleaned_dir, scenario="Y-target",
            x_tijdspad=X_PAD, y_tijdspad=Y_PAD, chunksize=2000, verbose=False,
        )
        assert df["Player_Profile_ID"].is_unique
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_newest_features_input_dir_prefers_sorted():
    """newest_features_input_dir kiest een sorted-map boven een gewone cleaned-map."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_feat_pick_"))
    try:
        (tmp / "cleaned_20250101_120000").mkdir()
        sorted_dir = tmp / "cleaned_20250101_120000_sorted_20250101_130000"
        sorted_dir.mkdir()
        picked = newest_features_input_dir(tmp)
        assert picked == sorted_dir.resolve()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        ("test_features_registry_loads", lambda: test_features_registry_loads()),
        ("test_build_features[Y-target]", lambda: test_build_features_produces_player_table("Y-target", 2)),
        ("test_build_features[Scenario_1]", lambda: test_build_features_produces_player_table("Scenario_1", 2)),
        ("test_single_feature_override", lambda: test_single_feature_override()),
        ("test_dedup_on_player_profile_id", lambda: test_dedup_on_player_profile_id()),
        ("test_newest_features_input_dir_prefers_sorted", lambda: test_newest_features_input_dir_prefers_sorted()),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests geslaagd.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
