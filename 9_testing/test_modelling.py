#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie modelling-stap (stappen 7 & 8; origineel 14 & 15).

Draaien:
    pytest _organisatie_code/99_testing/test_modelling.py -v
    python _organisatie_code/99_testing/test_modelling.py

Beide zoekstrategieën worden getest op een synthetische prebuilt dataset (stap 6):
- grid (deterministisch, via hpsearch_runner)
- optuna (tijd-gebudgetteerd, via optuna_runner) — alleen dat het draait + output schrijft.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# --- Maak de modules importeerbaar ---
HERE = Path(__file__).resolve().parent
MS_DIR = (HERE.parent / "6_merge_sample").resolve()
MODEL_DIR = (HERE.parent / "7_modelling").resolve()
for d in (MS_DIR, MODEL_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from merge_sample_pipeline import build_config, merge_and_sample  # noqa: E402
from modelling_pipeline import (  # noqa: E402
    enumerate_grid_tasks, run_grid_search, run_optuna_search, make_effective_config,
)

PREFIX = "01062025_30062025_01072025_31072025_valid"
BASE = "Flexible_spanish_plus"
TARGET = "y_self_exclusion_20250701_20250731"


def _make_dataset_and_config(tmp: Path, n: int = 300, seed: int = 0) -> tuple[Path, Path]:
    """Bouw een synthetische prebuilt dataset (stap 6) + een mini model-config. Geef (cfg_path, ds)."""
    rng = np.random.default_rng(seed)
    op = tmp / "data" / "x"
    op.mkdir(parents=True)
    pd.DataFrame({
        "Player_Profile_ID": range(n),
        "x1": rng.normal(size=n), "x2": rng.normal(size=n), "x3": rng.normal(size=n),
        "ACTIVE_FLAG": True,
        TARGET: rng.choice([0, 1], n, p=[0.85, 0.15]),
    }).to_csv(op / f"{PREFIX}_{BASE}.csv", index=False)

    ds = tmp / "ds"
    merge_and_sample(build_config(dataset_path=ds, data_dir=tmp / "data",
                                  validation_period_prefixes=[PREFIX],
                                  all_operators=["x"], sampling_ratio=0))

    cfg = {
        "data_dir": str(tmp / "data"),
        "validation_period_prefixes": [PREFIX],
        "test_period_prefixes": [PREFIX],
        "operators": ["x"],
        "target_col": "",
        "time_budget_seconds": 5,
        "run_variants": [{"name": "base",
                          "preprocessing": {"imputer": "median", "scaler": "none"},
                          "imbalance": {"strategy": "none"}}],
        "models": {"decision_tree": {"grids": {"mini": {"mode": "cartesian", "fixed": {},
                                                        "params": {"max_depth": [2, 3]}}}}},
    }
    cfg_path = tmp / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    return cfg_path, ds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_enumerate_grid_tasks_respects_only_models():
    """De taak-enumeratie past de only_models-filtering toe (zoals submit_hpsearch.sh)."""
    cfg = {
        "operators": ["x", "y"],
        "run_variants": [{"name": "base", "only_models": ["m1"]}, {"name": "all"}],
        "models": {"m1": {"grids": {"g1": {}, "g2": {}}}, "m2": {"grids": {"g1": {}}}},
    }
    tasks = enumerate_grid_tasks(cfg)
    # Per operator: m1 → (base,all) × (g1,g2) = 4; m2 → (all) × (g1) = 1 → 5; × 2 operators = 10.
    assert len(tasks) == 10
    # base geldt niet voor m2.
    assert not any(t["model"] == "m2" and t["run_variant"] == "base" for t in tasks)


def test_grid_writes_outputs_and_two_trials():
    """run_grid_search schrijft results.csv (2 trials) + best.json + meta.json per taak."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_model_"))
    try:
        cfg_path, ds = _make_dataset_and_config(tmp)
        cfg = make_effective_config(cfg_path, dataset_path=ds)
        produced = run_grid_search(cfg, tmp / "grid", models=["decision_tree"],
                                   cv_folds=2, run_test=False)
        assert len(produced) == 1
        task = produced[0]
        res = pd.read_csv(task / "results.csv")
        assert len(res) == 2  # max_depth 2 en 3
        assert (task / "best.json").exists()
        assert (task / "meta.json").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_grid_metrics_deterministic():
    """Twee identieke grid-runs geven identieke CV-metrieken (deterministisch)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_model_"))
    try:
        cfg_path, ds = _make_dataset_and_config(tmp)
        cfg = make_effective_config(cfg_path, dataset_path=ds)
        p1 = run_grid_search(cfg, tmp / "g1", models=["decision_tree"], cv_folds=2, run_test=False)[0]
        p2 = run_grid_search(cfg, tmp / "g2", models=["decision_tree"], cv_folds=2, run_test=False)[0]
        m = ["cv_mean_auprc", "cv_std_auprc", "cv_mean_auc", "cv_std_auc", "params_json"]
        r1 = pd.read_csv(p1 / "results.csv")[m]
        r2 = pd.read_csv(p2 / "results.csv")[m]
        assert r1.equals(r2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_optuna_runs_and_writes_outputs():
    """run_optuna_search draait (klein tijdsbudget) en schrijft de optuna-output."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_model_"))
    try:
        cfg_path, ds = _make_dataset_and_config(tmp)
        cfg = make_effective_config(cfg_path, dataset_path=ds)
        out = run_optuna_search(cfg, tmp / "opt", time_budget=3, cv_folds=1,
                                validate_best=True, cv5_top_n=2, no_multivariate=True)
        assert (out / "optuna_meta.json").exists()
        assert (out / "optuna_results.csv").exists()
        res = pd.read_csv(out / "optuna_results.csv")
        assert len(res) >= 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_enumerate_grid_tasks_respects_only_models,
        test_grid_writes_outputs_and_two_trials,
        test_grid_metrics_deterministic,
        test_optuna_runs_and_writes_outputs,
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
