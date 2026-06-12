#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descriptive_pipeline.py  (organisatie-versie)
=====================================

Pure-Python orkestratie voor stap 5 (**Descriptive tasks uitvoeren**) uit de organisatie-README
(origineel: stap 12). Vervangt `run_ALL_description.sbatch`.

Maakt van een feature-CSV (output van stap 3) een beschrijvend rapport: een tekstbestand met
target-verdeling, `describe()` per numerieke kolom, value-counts per object-kolom en een
correlatiematrix, plus plots (target-verdeling, correlatie-heatmap, histogrammen). Alles
landt in een dated submap `{output_dir}/{stamp}/`.

Op Snellius liep dit per operator (a..z) over `data_dir/<letter>.csv`. Op de organisatie is er één
dataset, dus je wijst één features-CSV aan.

De feitelijke rapportage (`generate_descriptive_report`) komt ongewijzigd uit
`descriptive_stats.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from descriptive_stats import generate_descriptive_report


def newest_features_csv(parent_dir: str | Path) -> Optional[Path]:
    """Nieuwste features_*.csv in `parent_dir` (op mtime), of None."""
    parent = Path(parent_dir)
    if not parent.is_dir():
        return None
    cands = sorted(parent.glob("features_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0].resolve() if cands else None


def build_descriptive_report(
    features_csv: str | Path,
    *,
    output_dir: Optional[str | Path] = None,
    target: Optional[str] = None,
) -> Path:
    """
    Maak het beschrijvende rapport + plots voor één features-CSV.

    Parameters
    ----------
    features_csv : pad naar de feature-CSV (output van stap 3).
    output_dir   : basis-output-map; er wordt een dated submap `{stamp}/` in aangemaakt.
                   Default: een map `descriptive_<...>` naast de input.
    target       : naam van de target-kolom (voor target-verdeling + correlatie).

    Returns
    -------
    Path naar de aangemaakte dated output-map.
    """
    src = Path(features_csv).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"features-CSV niet gevonden: {src}")

    if output_dir is None:
        output_dir = src.parent / "descriptive"
    out = generate_descriptive_report(src, output_dir, target)
    print(f"[descriptive] rapport + plots → {out}")
    return out
