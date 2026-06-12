#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie rapportage-stap (8_rapportages; organisatie-stappen 10 & 11, origineel 17 & 18).

Draaien:
    pytest _organisatie_code/99_testing/test_report.py -v
    python _organisatie_code/99_testing/test_report.py

We bouwen een mini grid-run (stap 6 → stap 7, met valid + test zodat er test_auprc is) en
draaien daarop de dekkingsgraad + het modelrapport.
"""

from __future__ import annotations

import io
import contextlib
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
REPORT_DIR = (HERE.parent / "8_rapportages").resolve()
for d in (MS_DIR, MODEL_DIR, REPORT_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from merge_sample_pipeline import build_config, merge_and_sample  # noqa: E402
from modelling_pipeline import make_effective_config, run_grid_search  # noqa: E402
import hpsearch_coverage_report  # noqa: E402
import create_model_report       # noqa: E402
import run_report                # noqa: E402

VP = "01062025_30062025_01072025_31072025_valid"
TP = "01062025_30062025_01082025_31082025_test"
BASE = "Flexible_spanish_plus"
VT = "y_self_exclusion_20250701_20250731"
TT = "y_self_exclusion_20250801_20250831"


def _build_grid_run(tmp: Path) -> Path:
    """Bouw dataset (valid+test) → grid-run (genest). Geef de grid-run-map terug."""
    n = 300
    op = tmp / "data" / "x"
    op.mkdir(parents=True)

    def mk(target, seed):
        r = np.random.default_rng(seed)
        return pd.DataFrame({
            "Player_Profile_ID": range(n),
            "x1": r.normal(size=n), "x2": r.normal(size=n), "x3": r.normal(size=n),
            "ACTIVE_FLAG": True, target: r.choice([0, 1], n, p=[0.85, 0.15]),
        })
    mk(VT, 0).to_csv(op / f"{VP}_{BASE}.csv", index=False)
    mk(TT, 1).to_csv(op / f"{TP}_{BASE}.csv", index=False)

    ds = tmp / "ds"
    merge_and_sample(build_config(dataset_path=ds, data_dir=tmp / "data",
                                  validation_period_prefixes=[VP], test_period_prefixes=[TP],
                                  all_operators=["x"], sampling_ratio=0))

    cfg = {
        "data_dir": str(tmp / "data"), "validation_period_prefixes": [VP],
        "test_period_prefixes": [TP], "operators": ["x"], "target_col": "",
        "time_budget_seconds": 5,
        "run_variants": [{"name": "base", "preprocessing": {"imputer": "median", "scaler": "none"},
                          "imbalance": {"strategy": "none"}}],
        "models": {"decision_tree": {"grids": {"mini": {"mode": "cartesian", "fixed": {},
                                                        "params": {"max_depth": [2, 3]}}}}},
    }
    (tmp / "cfg.yaml").write_text(yaml.safe_dump(cfg))
    eff = make_effective_config(tmp / "cfg.yaml", dataset_path=ds)
    run_dir = tmp / "grid_run"
    run_grid_search(eff, run_dir, models=["decision_tree"], cv_folds=2,
                    run_valid=True, run_test=True)
    return run_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_grid_run_has_nested_layout():
    """run_grid_search schrijft de geneste operator/model/run_variant/grid layout."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_report_"))
    try:
        run_dir = _build_grid_run(tmp)
        assert (run_dir / "x" / "decision_tree" / "base" / "mini" / "results.csv").exists()
        assert (run_dir / "x" / "decision_tree" / "base" / "mini" / "best.json").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_coverage_report_prints_table():
    """De dekkingsgraad-tabel toont de taak met 100% coverage."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_report_"))
    try:
        run_dir = _build_grid_run(tmp)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hpsearch_coverage_report.main([str(run_dir)])
        out = buf.getvalue()
        assert "HPSEARCH COVERAGE REPORT" in out
        assert "decision_tree" in out
        assert "Tasks found: 1" in out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_model_report_written_with_sections():
    """generate_report schrijft een tekstrapport met de verwachte kop/staart."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_report_"))
    try:
        run_dir = _build_grid_run(tmp)
        out_path = tmp / "report.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            written = create_model_report.generate_report("grid_run", run_folder=run_dir, out_path=out_path)
        assert Path(written) == out_path and out_path.exists()
        text = out_path.read_text()
        assert "END OF REPORT" in text
        assert "decision_tree" in text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_report_combined():
    """run_report.main draait coverage + modelrapport en schrijft het rapportbestand."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_report_"))
    try:
        run_dir = _build_grid_run(tmp)
        with contextlib.redirect_stdout(io.StringIO()):
            ret = run_report.main(["--run-dir", str(run_dir)])
        assert ret == 0
        assert (run_dir / "grid_run_report.txt").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_report_coverage_only_skips_report():
    """--coverage-only schrijft geen rapportbestand."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_report_"))
    try:
        run_dir = _build_grid_run(tmp)
        with contextlib.redirect_stdout(io.StringIO()):
            ret = run_report.main(["--run-dir", str(run_dir), "--coverage-only"])
        assert ret == 0
        assert not (run_dir / "grid_run_report.txt").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_grid_run_has_nested_layout,
        test_coverage_report_prints_table,
        test_model_report_written_with_sections,
        test_run_report_combined,
        test_run_report_coverage_only_skips_report,
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
