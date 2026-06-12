#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie merge+sample stap (stap 6 uit de organisatie-README; origineel: stap 13).

Draaien:
    pytest _organisatie_code/99_testing/test_merge_sample.py -v
    python _organisatie_code/99_testing/test_merge_sample.py

Dit is de **faithful** variant (`prepare_hpo_dataset` + `hpsearch_runner`), die de
multi-operator data-layout verwacht. We bouwen een synthetische `data_dir/<op>/`-structuur
(merged features + ACTIVE_FLAG + target) en draaien daarop.
"""

from __future__ import annotations

import json
import pickle
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

# --- Maak de modules importeerbaar ---
HERE = Path(__file__).resolve().parent
MS_DIR = (HERE.parent / "6_merge_sample").resolve()
if str(MS_DIR) not in sys.path:
    sys.path.insert(0, str(MS_DIR))

from merge_sample_pipeline import build_config, merge_and_sample  # noqa: E402

PREFIX = "01062025_30062025_01072025_31072025_valid"
TEST_PREFIX = "01062025_30062025_01082025_31082025_test"
BASE = "Flexible_spanish_plus"
TARGET = "y_self_exclusion_20250701_20250731"
TEST_TARGET = "y_self_exclusion_20250801_20250831"


def _make_operator_csv(op_dir: Path, prefix: str, target: str, n: int = 200, seed: int = 0):
    op_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "Player_Profile_ID": range(n),
        "x1_f0_net_winloss": rng.normal(size=n),
        "x2_f3_total_wagered": rng.normal(size=n),
        "ACTIVE_FLAG": rng.choice([True, False], n, p=[0.8, 0.2]),
        target: rng.choice([0, 1], n, p=[0.9, 0.1]),
    })
    df.to_csv(op_dir / f"{prefix}_{BASE}.csv", index=False)
    return df


def _stage(tmp: Path, *, with_test: bool = False) -> Path:
    data_dir = tmp / "data"
    _make_operator_csv(data_dir / "x", PREFIX, TARGET, seed=0)
    if with_test:
        _make_operator_csv(data_dir / "x", TEST_PREFIX, TEST_TARGET, seed=1)
    return data_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_no_sampling_keeps_all_active_rows():
    """sampling_ratio=0 → geen undersampling; ACTIVE_FLAG-filter wel toegepast."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_ms_"))
    try:
        data_dir = _stage(tmp)
        out = tmp / "out"
        cfg = build_config(dataset_path=out, data_dir=data_dir,
                           validation_period_prefixes=[PREFIX], all_operators=["x"],
                           sampling_ratio=0)
        merge_and_sample(cfg)
        meta = json.loads((out / "meta.json").read_text())
        assert meta["sampling_ratio"] == 0
        # 26 OHE-kolommen + 2 features
        assert meta["n_features"] == 28
        # ACTIVE_FLAG-filter laat alleen actieve rijen over.
        d = pickle.load(open(out / "valid_sampled.pkl", "rb"))
        assert d["X"].shape[0] == meta["n_valid"]
        assert int(d["y"].sum()) == meta["n_pos_valid"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_undersampling_ratio_enforced():
    """sampling_ratio=N → behoud alle positives + precies N× zoveel negatives (indien genoeg)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_ms_"))
    try:
        data_dir = _stage(tmp)
        out = tmp / "out"
        cfg = build_config(dataset_path=out, data_dir=data_dir,
                           validation_period_prefixes=[PREFIX], all_operators=["x"],
                           sampling_ratio=5)
        merge_and_sample(cfg)
        meta = json.loads((out / "meta.json").read_text())
        assert meta["n_neg_valid"] == 5 * meta["n_pos_valid"]
        assert meta["n_valid"] == meta["n_pos_valid"] + meta["n_neg_valid"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ohe_columns_present():
    """De 26-koloms a..z one-hot zit in de features (operator x → ohe_x=1)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_ms_"))
    try:
        data_dir = _stage(tmp)
        out = tmp / "out"
        cfg = build_config(dataset_path=out, data_dir=data_dir,
                           validation_period_prefixes=[PREFIX], all_operators=["x"],
                           sampling_ratio=0)
        merge_and_sample(cfg)
        d = pickle.load(open(out / "valid_sampled.pkl", "rb"))
        ohe = [c for c in d["X"].columns if c.startswith("ohe_")]
        assert len(ohe) == 26
        assert (d["X"]["ohe_x"] == 1).all()
        assert (d["X"]["ohe_a"] == 0).all()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_test_period_writes_test_full():
    """Met test-period-prefixes ontstaat ook test_full.pkl + meta-test velden."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_ms_"))
    try:
        data_dir = _stage(tmp, with_test=True)
        out = tmp / "out"
        cfg = build_config(dataset_path=out, data_dir=data_dir,
                           validation_period_prefixes=[PREFIX],
                           test_period_prefixes=[TEST_PREFIX], all_operators=["x"],
                           sampling_ratio=0)
        merge_and_sample(cfg)
        assert (out / "test_full.pkl").exists()
        meta = json.loads((out / "meta.json").read_text())
        assert "n_test" in meta and meta["n_test"] > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_config_shape():
    """build_config zet de verwachte sleutels (all_mode=True etc.)."""
    cfg = build_config(dataset_path="/x", data_dir="/d",
                       validation_period_prefixes=[PREFIX], all_operators=["x"],
                       sampling_ratio=20)
    assert cfg["all_mode"] is True
    assert cfg["sampling_ratio"] == 20
    assert cfg["all_operators"] == ["x"]
    assert cfg["base_scenario"] == "Flexible_spanish_plus"


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_no_sampling_keeps_all_active_rows,
        test_undersampling_ratio_enforced,
        test_ohe_columns_present,
        test_test_period_writes_test_full,
        test_build_config_shape,
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
