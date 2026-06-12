#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gedeelde test-fixture voor de e2e-tests: stage de meegeleverde **relationele** dataset
`0_dummy_data/voorbeeld_fake/` in `Operator_*`-submappen (zoals de pijplijn verwacht).

Vervangt de oude generator `_maak_dummy_csvs` (oud CDB/JSON-format zonder `pk_id`), die niet
compatibel is met de relationele feature-code.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# 0_dummy_data/voorbeeld_fake/ — relationeel, ;-gescheiden, jan–apr 2026 activiteit, mei+juni targets.
VOORBEELD_FAKE = (Path(__file__).resolve().parent.parent / "0_dummy_data" / "voorbeeld_fake").resolve()

# Tijdvensters die bij voorbeeld_fake passen (echte holdout: validatie y=mei, test y=juni).
X_PAD = "01012026:30042026"
Y_PAD = "01052026:31052026"
Y_START_DDMMYYYY = "01052026"
VALID_PREFIX = "01012026_30042026_01052026_31052026_valid"
# Zelfde y-venster als valid: voor de simpele e2e die de valid-features hergebruikt als test
# (test_end_to_end). Voor een ECHT juni-holdout gebruikt test_run_pipeline VALID/TEST_PREFIXES_3.
TEST_PREFIX = "01012026_30042026_01052026_31052026_test"
# Drie lookback-horizonten (p0/p1/p2): zelfde x-eind/target, andere x-start.
VALID_PREFIXES_3 = [
    "01012026_30042026_01052026_31052026_valid",
    "01022026_30042026_01052026_31052026_valid",
    "01032026_30042026_01052026_31052026_valid",
]
TEST_PREFIXES_3 = [
    "01012026_30042026_01062026_30062026_test",
    "01022026_30042026_01062026_30062026_test",
    "01032026_30042026_01062026_30062026_test",
]


def stage(raw: Path, operators=("Operator_a",)) -> Path:
    """Kopieer voorbeeld_fake naar `raw/<operator>/` voor elke operator; geef `raw` terug."""
    raw.mkdir(parents=True, exist_ok=True)
    for op in operators:
        d = raw / op
        d.mkdir(parents=True, exist_ok=True)
        for csv in VOORBEELD_FAKE.glob("*.csv"):
            shutil.copy(csv, d / csv.name)
    return raw
