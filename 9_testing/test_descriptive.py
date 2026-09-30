#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie descriptive-stap (stap 5 uit de organisatie-README; origineel: stap 12).

Draaien:
    pytest _organisatie_code/99_testing/test_descriptive.py -v
    python _organisatie_code/99_testing/test_descriptive.py

De descriptive-stap maakt heatmap/histogrammen over feature-kolommen die met 'x' beginnen
(de conventie uit het origineel). Daarom testen we met een synthetische features-CSV met
x-kolommen; aanvullend draaien we op een echte pipeline-output (Y-target) voor het tekstrapport.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

# --- Maak de modules importeerbaar ---
HERE = Path(__file__).resolve().parent
CLEANING_DIR = (HERE.parent / "1_cleaning").resolve()
FEATURES_DIR = (HERE.parent / "3_features").resolve()
DESC_DIR = (HERE.parent / "5_descriptive").resolve()
DUMMY_DIR = (HERE.parent / "0_dummy_data" / "voorbeeld_fake").resolve()
for d in (CLEANING_DIR, FEATURES_DIR, DESC_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from descriptive_pipeline import build_descriptive_report, newest_features_csv  # noqa: E402


def _write_synthetic(path: Path, n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "Player_Profile_ID": range(n),
        "x1_a": rng.normal(size=n),
        "x2_b": rng.normal(size=n),
        "x3_c": rng.integers(0, 5, n).astype(float),
        "cat": rng.choice(["p", "q"], n),
        "y_target": rng.integers(0, 2, n),
    })
    df.to_csv(path, index=False)
    return df


def _only_dated_subdir(base: Path) -> Path:
    subs = [p for p in base.iterdir() if p.is_dir()]
    assert len(subs) == 1, f"verwacht 1 dated submap, kreeg {subs}"
    return subs[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_report_and_plots_for_x_features():
    """Synthetische x-features → tekstrapport + heatmap + target-plot + histogrammen."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_desc_"))
    try:
        src = tmp / "features_20250101_120000_test_all.csv"
        _write_synthetic(src)
        out = build_descriptive_report(src, output_dir=tmp / "out", target="y_target")

        names = {p.name for p in out.glob("*")}
        stem = src.stem
        assert f"{stem}_descriptive_stats.txt" in names
        assert f"{stem}_corr_heatmap.png" in names
        assert f"{stem}_target_distribution.png" in names
        # Minstens één histogram voor de x-kolommen.
        assert any(n.startswith(f"{stem}_hist_x") for n in names)

        txt = (out / f"{stem}_descriptive_stats.txt").read_text(encoding="utf-8")
        assert "Target Variable Distribution" in txt
        assert "Correlation matrix" in txt
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_report_without_target():
    """Zonder target: tekstrapport wordt nog steeds gemaakt, geen target-plot."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_desc_"))
    try:
        src = tmp / "features_x.csv"
        _write_synthetic(src)
        out = build_descriptive_report(src, output_dir=tmp / "out", target=None)
        names = {p.name for p in out.glob("*")}
        assert "features_x_descriptive_stats.txt" in names
        assert "features_x_target_distribution.png" not in names
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_runs_on_real_pipeline_features():
    """Op echte pipeline-output (Y-target): tekstrapport met target-verdeling."""
    from clean_pipeline import clean_directory
    from parse_pipeline import build_features

    tmp = Path(tempfile.mkdtemp(prefix="organisatie_desc_real_"))
    try:
        raw = tmp / "raw"
        raw.mkdir()
        for csv in DUMMY_DIR.glob("*.csv"):
            shutil.copy(csv, raw / csv.name)
        cleaned = clean_directory(input_dir=raw, clean_out_dir=tmp / "cl",
                                  chunksize=2000, do_label=True, verbose=False)
        feat_csv = tmp / "features_run.csv"
        df = build_features(cleaned_dir=cleaned, scenario="Y-target", features_out=feat_csv,
                            x_tijdspad="01062025:30062025", y_tijdspad="01072026:31072026",
                            chunksize=2000, verbose=False)
        target = [c for c in df.columns if c.startswith("y_")][0]

        out = build_descriptive_report(feat_csv, output_dir=tmp / "out", target=target)
        txt = (out / "features_run_descriptive_stats.txt").read_text(encoding="utf-8")
        assert "Target Variable Distribution" in txt
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_newest_features_csv_picker():
    """newest_features_csv kiest een features_*.csv in een map."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_desc_pick_"))
    try:
        (tmp / "features_a.csv").write_text("Player_Profile_ID\n1\n", encoding="utf-8")
        assert newest_features_csv(tmp).name == "features_a.csv"
        assert newest_features_csv(tmp / "bestaat_niet") is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_report_and_plots_for_x_features,
        test_report_without_target,
        test_runs_on_real_pipeline_features,
        test_newest_features_csv_picker,
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
