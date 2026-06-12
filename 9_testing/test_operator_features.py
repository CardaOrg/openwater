#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie operator-specific-features stap (stap 3b; origineel: stap 10).

Draaien:
    pytest _organisatie_code/99_testing/test_operator_features.py -v
    python _organisatie_code/99_testing/test_operator_features.py

De build_all_stats-stap aggregeert over een vaste set kernfeatures (f0/f3/f25/f12/f11).
Die kolommen ontstaan normaal uit een groot scenario (Flexible_spanish_plus) en niet uit de
mini dummy-data, dus we testen met een *synthetische* merged features-CSV.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# --- Maak de module importeerbaar ---
HERE = Path(__file__).resolve().parent
OPFEAT_DIR = (HERE.parent / "3b_operator_specific_features").resolve()
if str(OPFEAT_DIR) not in sys.path:
    sys.path.insert(0, str(OPFEAT_DIR))

from operator_features_pipeline import build_all_stats_for_file  # noqa: E402
from build_all_stats import ALL_FEATURES, ALL_SUFFIX, compute_all_stats_row  # noqa: E402


def _write_synthetic_features(path: Path, cols=None) -> pd.DataFrame:
    """Schrijf een synthetische merged features-CSV met bekende waarden."""
    cols = cols if cols is not None else ALL_FEATURES
    df = pd.DataFrame({
        "Player_Profile_ID": [1, 2, 3, 4],
    })
    base = {
        "f0_net_winloss":          [10.0, -5.0, 0.0, 25.0],
        "f3_total_wagered":        [100.0, 200.0, 50.0, 400.0],
        "f25_voluntary_suspensions": [0.0, 1.0, 0.0, 2.0],
        "f12_deposits_per_day":    [1.5, 0.0, 3.0, 2.0],
        "f11_withdrawals_per_day": [0.2, 0.5, 0.0, 1.0],
    }
    for c in cols:
        df[c] = base[c]
    # Wat ruis-kolommen die genegeerd moeten worden:
    df["some_other_col"] = [1, 2, 3, 4]
    df.to_csv(path, index=False)
    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_stats_row_has_expected_columns_and_values():
    """compute_all_stats_row levert mean/std/min/max per feature met juiste waarden."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_opfeat_"))
    try:
        src = tmp / "features.csv"
        df = _write_synthetic_features(src)
        row = compute_all_stats_row(pd.read_csv(src), context="features.csv")

        # 5 features × 4 stats = 20 kolommen
        assert len(row) == len(ALL_FEATURES) * 4
        # Spot-check tegen pandas zelf (zelfde definitie: std = sample std, ddof=1)
        vals = df["f3_total_wagered"]
        assert row["mean_f3_total_wagered"] == pytest.approx(vals.mean())
        assert row["std_f3_total_wagered"] == pytest.approx(vals.std())
        assert row["min_f3_total_wagered"] == pytest.approx(vals.min())
        assert row["max_f3_total_wagered"] == pytest.approx(vals.max())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_all_stats_for_file_writes_one_row():
    """build_all_stats_for_file schrijft een 1-rij aggregaat met ALL_SUFFIX in de naam."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_opfeat_"))
    try:
        src = tmp / "features_20250101_120000_Flexible_spanish_plus_all.csv"
        _write_synthetic_features(src)
        out = build_all_stats_for_file(src)

        assert out.exists()
        assert ALL_SUFFIX in out.name and out.name.endswith("_merged.csv")
        agg = pd.read_csv(out)
        assert len(agg) == 1
        assert agg.shape[1] == len(ALL_FEATURES) * 4
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_partial_features_only_present_columns():
    """Als maar een deel van ALL_FEATURES aanwezig is, worden alleen die geaggregeerd."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_opfeat_"))
    try:
        src = tmp / "features.csv"
        _write_synthetic_features(src, cols=["f0_net_winloss", "f3_total_wagered"])
        out = build_all_stats_for_file(src, out_path=tmp / "agg.csv")
        agg = pd.read_csv(out)
        assert agg.shape[1] == 2 * 4  # 2 features × 4 stats
        assert "mean_f0_net_winloss" in agg.columns
        assert "mean_f25_voluntary_suspensions" not in agg.columns
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_features_raises():
    """Zonder enige ALL_FEATURE-kolom volgt een nette ValueError (geen NameError)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_opfeat_"))
    try:
        src = tmp / "features.csv"
        pd.DataFrame({"Player_Profile_ID": [1, 2], "x": [3, 4]}).to_csv(src, index=False)
        with pytest.raises(ValueError):
            build_all_stats_for_file(src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_custom_out_path():
    """Met --out / out_path wordt exact dat pad gebruikt."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_opfeat_"))
    try:
        src = tmp / "features.csv"
        _write_synthetic_features(src)
        target = tmp / "sub" / "mijn_aggregaat.csv"
        out = build_all_stats_for_file(src, out_path=target)
        assert out == target and target.exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_stats_row_has_expected_columns_and_values,
        test_build_all_stats_for_file_writes_one_row,
        test_partial_features_only_present_columns,
        test_no_features_raises,
        test_custom_out_path,
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
