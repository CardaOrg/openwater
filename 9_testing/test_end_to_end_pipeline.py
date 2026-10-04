#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end test: van CSV-basisdata → werkend model & rapportage (via Optuna).

Eén test die de hele organisatie-rits doorloopt op de meegeleverde relationele `voorbeeld_fake`:

    stap 1  cleaning   (incl. automatische outlier-labelling)
    stap 2  sorting
    stap 3  features   (scenario met target + numerieke features over de x-periode)
    stap 3b operator-stats (ALL-aggregaat)
    stap 4  active-filter (last-status lookup → ACTIVE_FLAG)
    stap 6  merge & sample (gecombineerde HPO-dataset: valid_sampled.pkl / test_full.pkl)
    stap 7/8 modelling via OPTUNA → optuna-rapportage (meta + resultaten = model + report)

Overgeslagen (zoals in de README aangegeven): outlier-labelling is al onderdeel van stap 1;
descriptive (stap 5) is een losse zij-analyse en niet nodig voor model+rapport; de gridsearch
(stap 7) en het grid-modelrapport (stap 10/11) vervallen omdat we voor Optuna kiezen — daar is
de optuna-output zelf de rapportage. Logging (stap 9) is dwarsliggend en apart getest.

Draaien:
    pytest _organisatie_code/9_testing/test_end_to_end_pipeline.py -q
    python _organisatie_code/9_testing/test_end_to_end_pipeline.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
organisatie = HERE.parent
# Modulemappen van de stappen op sys.path (3_features eerst i.v.m. gedeelde path_finding).
for sub in ("3_features", "1_cleaning", "2_sorting", "3b_operator_specific_features",
            "4_active_filter", "6_merge_sample", "7_modelling"):
    p = str(organisatie / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
if str(organisatie) not in sys.path:
    sys.path.insert(0, str(organisatie))

from _relational_fixture import (stage, X_PAD, Y_PAD, Y_START_DDMMYYYY,  # noqa: E402
                                 VALID_PREFIX, TEST_PREFIX)
from clean_pipeline import clean_directory                          # noqa: E402
from sort_pipeline import sort_directory                            # noqa: E402
from parse_pipeline import build_features                           # noqa: E402
from operator_features_pipeline import build_all_stats_for_file     # noqa: E402
from active_filter_pipeline import build_status_lookups             # noqa: E402
from merge_sample_pipeline import build_config, merge_and_sample    # noqa: E402
from modelling_pipeline import run_optuna_search                    # noqa: E402

BASE_SCENARIO = "Flexible_spanish_plus"
# X_PAD/Y_PAD/VALID_PREFIX/TEST_PREFIX/Y_START_DDMMYYYY komen uit _relational_fixture (2026-vensters).


def _process_operator(op_raw_dir: Path, tmp: Path, feat_root: Path) -> int:
    """Verwerk één operator: clean → sort → features → 3b → active. Geeft #positieven terug."""
    op = op_raw_dir.name  # bv. 'Operator_1'
    # 1) cleaning (incl. labelling)
    cleaned = clean_directory(input_dir=op_raw_dir, clean_out_dir=tmp / "clean" / op,
                              chunksize=5000, do_label=True, verbose=False)
    # 2) sorting
    sorted_dir = sort_directory(cleaned_dir=cleaned, chunksize=5000)

    # 3) features → naar de door stap 6 verwachte layout: feat_root/<op>/<prefix>_<scenario>.csv
    op_feat_dir = feat_root / op
    op_feat_dir.mkdir(parents=True, exist_ok=True)
    feat_csv = op_feat_dir / f"{VALID_PREFIX}_{BASE_SCENARIO}.csv"
    df = build_features(cleaned_dir=sorted_dir, scenario=BASE_SCENARIO, features_out=feat_csv,
                        x_tijdspad=X_PAD, y_tijdspad=Y_PAD, chunksize=5000, verbose=False)
    # zelfde features ook als test-periode (zelfde venster → eenvoudige e2e)
    shutil.copy(feat_csv, op_feat_dir / f"{TEST_PREFIX}_{BASE_SCENARIO}.csv")

    # 3b) operator-stats (ALL-aggregaat) → {prefix}_ALL_..._merged.csv
    build_all_stats_for_file(feat_csv, out_path=op_feat_dir / f"{VALID_PREFIX}_ALL_merged.csv")

    # 4) active-filter → LAST_STATUS_LOOKUP_BEFORE_<ys>.csv naast de features
    build_status_lookups(sorted_dir, [Y_START_DDMMYYYY], out_dir=op_feat_dir)

    ycol = [c for c in df.columns if c.startswith("y_")][0]
    return int(df[ycol].sum())


def test_end_to_end_csv_to_model_and_report():
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_e2e_"))
    try:
        # 0) genereer basisdata (2 operators, 20 spelers elk)
        ds = stage(tmp / "raw", operators=("Operator_1", "Operator_2"))
        operators = sorted(p.name for p in ds.glob("Operator_*"))
        assert operators == ["Operator_1", "Operator_2"]

        # 1-4) per operator door de eerste stappen
        feat_root = tmp / "feature_files"
        total_pos = sum(_process_operator(ds / op, tmp, feat_root) for op in operators)
        assert total_pos > 0, "geen positieve (self-exclusion) targets gegenereerd"

        # 6) merge & sample → gecombineerde HPO-dataset
        dataset_path = tmp / "hpo_dataset"
        cfg6 = build_config(
            dataset_path=dataset_path, data_dir=feat_root,
            validation_period_prefixes=[VALID_PREFIX], test_period_prefixes=[TEST_PREFIX],
            all_operators=operators, sampling_ratio=0, base_scenario=BASE_SCENARIO,
        )
        merge_and_sample(cfg6)
        assert (dataset_path / "valid_sampled.pkl").exists()
        meta_ds = json.loads((dataset_path / "meta.json").read_text(encoding="utf-8"))
        assert meta_ds["n_pos_valid"] > 0 and meta_ds["n_features"] > 0

        # 7/8) modelling via OPTUNA (klein tijdsbudget) → optuna-rapportage
        cfg_model = {
            "data_dir": str(feat_root), "dataset_path": str(dataset_path), "all_mode": True,
            "validation_period_prefixes": [VALID_PREFIX], "test_period_prefixes": [TEST_PREFIX],
            "operators": operators, "all_operators": operators, "target_col": "",
            "base_scenario": BASE_SCENARIO,
        }
        out = run_optuna_search(cfg_model, tmp / "optuna_run", time_budget=4, cv_folds=1,
                                validate_best=True, cv5_top_n=2, no_multivariate=True)

        # Rapportage + model: optuna-output bestaat en bevat een beste model + scores
        assert (out / "optuna_meta.json").exists()
        assert (out / "optuna_results.csv").exists()
        opt_meta = json.loads((out / "optuna_meta.json").read_text(encoding="utf-8"))
        assert isinstance(opt_meta, dict) and len(opt_meta) > 0
        res = pd.read_csv(out / "optuna_results.csv")
        assert len(res) >= 1, "optuna heeft geen trials voltooid"
        print(f"[E2E] positives={total_pos}  dataset={meta_ds['n_valid']} rijen  "
              f"optuna_trials={len(res)}  → model+rapport OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        test_end_to_end_csv_to_model_and_report()
        print("PASS  test_end_to_end_csv_to_model_and_report")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  test_end_to_end_csv_to_model_and_report: {e}")
        raise
