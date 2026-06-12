#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_registry_tables_consistency.py
===================================

Beantwoordt + bewaakt de vraag: "Bet_Parts staat niet in de registry-`usecols`, maar wél in
`tables` — kan dat geen problemen geven?"

Kernpunt (bewezen door deze tests):

* De registry-**`usecols`** is functioneel **niet bindend**: `load_tables_local` negeert
  `usecols_by_table` ("kept for signature compatibility; not used here"). Elke feature leest z'n
  kolommen zelf — rechtstreeks via `iter_csv_chunks` of via de join-helpers (`build_bet_parts_map`
  enz.) die hun éigen usecols meegeven. `usecols` dient dus puur als **administratie/documentatie**
  van welke kolommen per tabel gelezen worden; die is inmiddels gecorrigeerd zodat ze de
  werkelijkheid (incl. de relationele sub-tabellen) weerspiegelt.

* Wat **wél** telt is de registry-**`tables`**-lijst: die bepaalt welke CSV's `load_tables_local`
  inlaadt. Leest een feature-body `tables.get("WOK_Bet_Parts")` terwijl die tabel NIET in
  `tables` staat, dan krijgt de feature `None` → lege join-map → **stil fout** (alles 0), zónder
  exception. Dát is de echte valkuil, en `test_every_read_table_is_declared` vangt 'm af.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
organisatie = HERE.parent
sys.path.insert(0, str(organisatie / "3_features"))

import feature_engineering_spanish as fes  # noqa: E402

DATA = organisatie / "0_dummy_data" / "voorbeeld_fake"
# Multi-period: activiteit jan–apr → x-venster jan–apr.
X = ["01012026", "30042026"]


def _paths(table: str):
    return [DATA / f"{table}.csv"]


# ---------------------------------------------------------------------------
# 1) f49 leest Bet_Parts via de join-helper — ondanks dat het niet in usecols staat.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not (DATA / "WOK_Bet_Parts.csv").exists(), reason="voorbeeld_fake ontbreekt")
def test_f49_reads_bet_parts_and_administration_reflects_it():
    tables = {t: _paths(t) for t in ("WOK_Bet", "WOK_Bet_Transaction", "WOK_Bet_Parts")}
    df = fes.f49_percentage_live_bets(tables, x_tijdspad=X, chunksize=5000)
    assert len(df) > 0
    # Parts worden daadwerkelijk gelezen → live-percentage is niet-triviaal (> 0).
    assert df["f49_percentage_live_bets"].mean() > 0.0
    # Administratie klopt nu: WOK_Bet_Parts staat in ZOWEL `tables` als `usecols`.
    spec = fes.FEATURES_REGISTRY["f49_percentage_live_bets"]
    assert "WOK_Bet_Parts" in spec["tables"]
    assert "WOK_Bet_Parts" in spec["usecols"]


# ---------------------------------------------------------------------------
# 2) DE ECHTE valkuil: ontbreekt WOK_Bet_Parts in `tables`, dan stil fout (alles 0, geen crash).
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not (DATA / "WOK_Bet_Parts.csv").exists(), reason="voorbeeld_fake ontbreekt")
def test_f49_silently_wrong_when_bet_parts_missing_from_tables():
    tables = {t: _paths(t) for t in ("WOK_Bet", "WOK_Bet_Transaction")}  # GEEN WOK_Bet_Parts
    df = fes.f49_percentage_live_bets(tables, x_tijdspad=X, chunksize=5000)
    # Geen exception — maar alle live-percentages zijn 0 (de parts zijn nooit gelezen).
    assert (df["f49_percentage_live_bets"] == 0).all()


# ---------------------------------------------------------------------------
# 3) GUARD: elke tabel die een feature-body via tables.get("X")/tables["X"] leest, moet in de
#    registry-`tables` staan. Dit vangt toekomstige "Bet_Parts-achtige" omissies af.
# ---------------------------------------------------------------------------
def _tables_read_in_body(fn) -> set:
    """Alle string-literals X in `tables.get("X"[, ...])` en `tables["X"]` in de functie-broncode."""
    tree = ast.parse(inspect.getsource(fn))
    found: set = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "tables" and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            found.add(node.args[0].value)
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == "tables" and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            found.add(node.slice.value)
    return found


@pytest.mark.parametrize("key", list(fes.FEATURES_REGISTRY.keys()))
def test_every_read_table_is_declared(key):
    spec = fes.FEATURES_REGISTRY[key]
    fn = spec.get("stream_fn")
    if fn is None:
        pytest.skip("geen stream_fn")
    declared = set(spec.get("tables", []))
    read = _tables_read_in_body(fn)
    missing = read - declared
    assert not missing, (
        f"{key}: leest in de body {sorted(missing)} via tables.get(...), maar die staan NIET in de "
        f"registry-`tables` {sorted(declared)} → die tabel wordt niet ingeladen → stil fout."
    )


@pytest.mark.parametrize("key", list(fes.FEATURES_REGISTRY.keys()))
def test_usecols_tables_are_subset_of_declared_tables(key):
    """Administratie-consistentie: elke tabel met een `usecols`-entry moet ook in `tables` staan.
    Vangt af dat de gedocumenteerde kolommen verwijzen naar een tabel die niet wordt ingeladen."""
    spec = fes.FEATURES_REGISTRY[key]
    usecols_tables = set(spec.get("usecols", {}).keys())
    declared = set(spec.get("tables", []))
    stray = usecols_tables - declared
    assert not stray, f"{key}: usecols noemt {sorted(stray)} die niet in `tables` {sorted(declared)} staan."
