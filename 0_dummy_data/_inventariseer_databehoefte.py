#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_inventariseer_databehoefte.py
==============================

Tapt uit ``FEATURES_REGISTRY`` af **welke organisatie-tabellen** (CSV-bestanden) en **welke kolommen** de
feature-laag nodig heeft, en print dat als data-aanlever-specificatie.

Waarom een script en geen statische lijst?
    De behoefte volgt 1-op-1 uit de registry: per feature staan in ``tables`` de in te laden CSV's
    en in ``usecols`` de kolommen per tabel. Door dat hier te aggregeren blijft de spec automatisch
    in sync met de code — voeg je een feature/kolom toe, dan verschijnt die hier vanzelf.

Casing:
    De registry vraagt sommige kolommen CamelCase (oude conventie), maar **op schijf is de
    organisatie-export snake_case**. De case-tolerante reader overbrugt dat. Voor een aanlever-spec willen we
    de schijf-waarheid, dus normaliseren we elke kolomnaam met ``.lower()`` → snake_case.

Join-targets:
    Een tabel met een ``pk_id``-kolom is een **join-doel**: de sub-tabellen verwijzen ernaar via
    ``wok_<parent>_pk_id``. Die markeren we, zodat duidelijk is welke kolommen de relaties dragen.

Gebruik:
    python _inventariseer_databehoefte.py            # leesbare tabel-overzicht
    python _inventariseer_databehoefte.py --json      # JSON {tabel: [kolommen]}
    python _inventariseer_databehoefte.py --csv spec.csv   # platte CSV (tabel,kolom,is_join_target)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "3_features"))

import feature_engineering_spanish as fes  # noqa: E402

# `operator_id` is geen feature-kolom maar een **routing-kolom**: hij scheidt de operators binnen
# één export. In de organisatie-data staat hij alleen in de **parent/top-level** tabellen; de sub-/transactie-
# tabellen dragen 'm niet, maar bereiken de operator via hun join naar de parent. Onderstaande set is
# de op schijf geverifieerde werkelijkheid (voorbeeld_11); met --data-dir wordt dit per run gesnift.
OPERATOR_COL = "operator_id"
DEFAULT_OPERATOR_ID_TABLES = frozenset({
    "WOK_Bet", "WOK_Game", "WOK_Game_Session",
    "WOK_Player_Account_Transaction", "WOK_Player_Limits", "WOK_Player_Profile",
})


def sniff_operator_id_tables(data_dir: Path) -> set[str]:
    """Lees de header van elke ``<tabel>.csv`` in ``data_dir`` en geef de tabellen die ``operator_id``
    daadwerkelijk dragen. Zo blijft "waar mogelijk" de schijf-waarheid i.p.v. een aanname."""
    found: set[str] = set()
    for csv_path in sorted(data_dir.glob("*.csv")):
        try:
            header = csv_path.open("r", encoding="utf-8", errors="replace").readline()
        except OSError:
            continue
        cols = {c.strip().strip('"').lower() for c in header.split(";")}
        if OPERATOR_COL in cols:
            found.add(csv_path.stem)
    return found


def collect_requirements(operator_id_tables: set[str] | frozenset[str] | None = None) -> dict[str, set[str]]:
    """Aggregeer per tabel de benodigde kolommen (on-disk snake_case) over alle features.

    ``operator_id`` wordt toegevoegd aan elke tabel waar die op schijf bestaat
    (``operator_id_tables``; default = de geverifieerde parent-tabellen)."""
    op_tables = DEFAULT_OPERATOR_ID_TABLES if operator_id_tables is None else operator_id_tables
    per: dict[str, set[str]] = {}
    for spec in fes.FEATURES_REGISTRY.values():
        # `tables` bepaalt welke CSV's worden ingeladen (functioneel bindend).
        for table in spec.get("tables", []):
            per.setdefault(table, set())
        # `usecols` documenteert de kolommen; normaliseer naar de schijf-waarheid (snake_case).
        for table, cols in spec.get("usecols", {}).items():
            per.setdefault(table, set()).update(c.lower() for c in cols)
    # Routing-kolom: overal toevoegen waar 'ie op schijf bestaat.
    for table in per:
        if table in op_tables:
            per[table].add(OPERATOR_COL)
    return per


def as_rows(per: dict[str, set[str]]) -> list[tuple[str, str, bool]]:
    """Platte (tabel, kolom, is_join_target)-rijen, gesorteerd."""
    rows: list[tuple[str, str, bool]] = []
    for table in sorted(per):
        cols = sorted(per[table])
        is_target = "pk_id" in cols
        for col in cols:
            rows.append((table, col, is_target))
    return rows


def render_spec(per: dict[str, set[str]], *, join_remarks: bool = True) -> str:
    """Bouw de leesbare data-aanlever-spec als string.

    join_remarks=False laat de ``join via``- en per-tabel operator_id-regels weg → een schone lijst
    (tabel + kolommen + join-target-tag), geschikt voor het .txt-bestand waar de README naar linkt."""
    n_tables = len(per)
    n_cols = sum(len(c) for c in per.values())
    n_op = sum(1 for c in per.values() if OPERATOR_COL in c)
    lines = [
        f"=== organisatie data-aanlever-spec: {n_tables} bestanden, {n_cols} kolommen "
        f"(snake_case, zoals op schijf) ===",
        f"    operator_id (routing) aanwezig in {n_op}/{n_tables} tabellen",
        "",
    ]
    for table in sorted(per):
        cols = sorted(per[table])
        tag = "   ← join-target (pk_id)" if "pk_id" in cols else ""
        lines.append(f"{table}.csv  ({len(cols)} kolommen){tag}")
        lines.append(f"    {', '.join(cols)}")
        if join_remarks:
            join_fk = sorted(c for c in cols if c.startswith("wok_") and c.endswith("_pk_id"))
            if join_fk:
                lines.append(f"    join via: {', '.join(join_fk)} → parent.pk_id")
            if OPERATOR_COL in cols:
                lines.append("    operator_id: routing-kolom (scheidt operators in de export)")
            elif join_fk:
                lines.append("    operator_id: n.v.t. — operator via de parent-join bereikbaar")
        lines.append("")
    lines.append("Formaat: ;-gescheiden, dubbele-quotes, komma-decimalen, NULL voor missing.")
    return "\n".join(lines)


def print_human(per: dict[str, set[str]]) -> None:
    print(render_spec(per, join_remarks=True))


def main() -> None:
    ap = argparse.ArgumentParser(description="Inventariseer de organisatie-databehoefte uit FEATURES_REGISTRY.")
    ap.add_argument("--data-dir", metavar="PAD",
                    help="sniff de echte CSV-headers in deze map om te bepalen welke tabellen "
                         "operator_id dragen (i.p.v. de geverifieerde default-set)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="print als JSON {tabel: [kolommen]}")
    g.add_argument("--csv", metavar="PAD", help="schrijf platte CSV (tabel,kolom,is_join_target)")
    g.add_argument("--txt", metavar="PAD", help="schrijf de schone leesbare spec (zonder join-"
                                                "opmerkingen) naar een .txt — waar de README naar linkt")
    args = ap.parse_args()

    op_tables = None
    if args.data_dir:
        data_dir = Path(args.data_dir)
        if not data_dir.is_dir():
            ap.error(f"--data-dir bestaat niet: {data_dir}")
        op_tables = sniff_operator_id_tables(data_dir)

    per = collect_requirements(op_tables)

    if args.json:
        print(json.dumps({t: sorted(c) for t, c in sorted(per.items())}, indent=2, ensure_ascii=False))
    elif args.csv:
        import csv
        out = Path(args.csv)
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["tabel", "kolom", "is_join_target"])
            w.writerows(as_rows(per))
        print(f"Geschreven: {out}  ({sum(len(c) for c in per.values())} rijen)")
    elif args.txt:
        out = Path(args.txt)
        out.write_text(render_spec(per, join_remarks=False) + "\n", encoding="utf-8")
        print(f"Geschreven: {out}")
    else:
        print_human(per)


if __name__ == "__main__":
    main()
