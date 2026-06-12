#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
operator_features_pipeline.py  (organisatie-versie)
===========================================

Pure-Python orkestratie voor stap 3b (**Extra features voor het totaalalgoritme**) uit de
organisatie-README (origineel: stap 10). Dit vervangt `run_ALL_build_operator_features.sbatch`.

Wat doet deze stap? Wanneer je niet per operator een apart model traint maar één
TOTAALalgoritme over alle operators, helpt het om per operator een paar samenvattende
("operator-specifieke") features toe te voegen: het gemiddelde, de spreiding (std) en de
min/max van een vaste set kernfeatures (`ALL_FEATURES` in `build_all_stats.py`). Die 1-rij
aggregaten ondersteunen het tree-model.

Op Snellius liep `build_all_stats.py` over een mappenstructuur `data_dir/<operator>/` met
per-periode merged CSV's. Op de organisatie is er één dataset (= één operator), dus we aggregeren
simpelweg over één features-CSV (de output van stap 3).

De feitelijke berekening (`compute_all_stats_row`) en de naamgeving (`ALL_SUFFIX`) komen
ongewijzigd uit `build_all_stats.py`, zodat het resultaat identiek is aan het origineel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from build_all_stats import compute_all_stats_row, ALL_FEATURES, ALL_SUFFIX


def build_all_stats_for_file(
    features_csv: str | Path,
    out_path: Optional[str | Path] = None,
) -> Path:
    """
    Lees één merged features-CSV en schrijf de 1-rij ALL-aggregaat-CSV
    (mean/std/min/max over de aanwezige ALL_FEATURES-kolommen).

    Parameters
    ----------
    features_csv : pad naar de merged features-CSV (output van stap 3).
    out_path     : doelpad. Default: `<stem>_<ALL_SUFFIX>_merged.csv` naast de input.

    Returns
    -------
    Path naar de geschreven aggregaat-CSV.
    """
    src = Path(features_csv).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"features-CSV niet gevonden: {src}")

    df = pd.read_csv(src)
    row = compute_all_stats_row(df, context=src.name)

    if out_path is None:
        out_path = src.with_name(f"{src.stem}_{ALL_SUFFIX}_merged.csv")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([row]).to_csv(out_path, index=False)

    present = [f for f in ALL_FEATURES if f in df.columns]
    print(f"[build_all_stats] {src.name}: {len(present)}/{len(ALL_FEATURES)} kernfeatures "
          f"aanwezig → {len(row)} stats-kolommen")
    print(f"[build_all_stats] geschreven → {out_path}")
    return out_path
