#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_maak_fake_big_data.py
==========================

Genereert dezelfde fake organisatie-dataset als `_maak_fake.py` (zelfde blueprint, format en
relationele structuur), maar **streamend** zodat je moeiteloos bestanden van enkele GB maakt
zonder het geheugen te laten vollopen.

Twee verschillen t.o.v. `_maak_fake.py`:

1. **Constant geheugen.** We bouwen niet alle rijen in één dict om ze aan het eind weg te
   schrijven; per speler schrijven we direct naar 13 open ``csv.writer``-streams (QUOTE_ALL,
   ``;``-gescheiden) en gooien de rijen meteen weg. Geheugengebruik is O(1) in datasetgrootte.

2. **Globaal-unieke ``pk_id``'s.** We houden per operator één persistente pk-teller aan over álle
   spelers (de kleine generator maakt per speler een nieuwe teller → dubbele pk's binnen een
   operator, wat de relationele joins kruisbesmet). De big-data-variant is dus relationeel
   correct, óók bij miljoenen rijen.

De **blueprint, value-sets, format-helpers en rij-generatie worden geïmporteerd** uit
`_maak_fake` (één bron van waarheid — geen gedupliceerde kolomdefinities).

Gebruik:
    # tot ~2 GB (som over alle 13 tabellen):
    python _maak_fake_big_data.py --target-gb 2

    # of een vast aantal spelers:
    python _maak_fake_big_data.py --players 1000000 --operators 26

    # eigen pad / seed:
    python _maak_fake_big_data.py --out ./groot --target-gb 5 --seed 7

Multi-period (standaard) holdout-vensters, zelfde als _maak_fake:
    validatie : x=01012026:30042026  y=01052026:31052026
    test      : x=01012026:30042026  y=01062026:30062026
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path
from typing import Dict, List

# Eén bron van waarheid: blueprint + rij-generatie hergebruiken (niet dupliceren).
from _maak_fake import (
    COLUMNS, _PK, _game_catalog, _player_rows,
    ACTIVE_MONTHS, TARGET_MONTH, TARGET_MONTHS, YEAR, STATUS_SELF_EXCL,
)


class _CountingWriter:
    """Dunne wrapper om een file-object die geschreven tekens telt (voor de GB-target).

    csv.writer schrijft via ``.write(str)``; we tellen ``len(s)`` (≈ bytes voor grotendeels
    ASCII-data) in een gedeelde accumulator, zodat we de totale grootte goedkoop kunnen volgen
    zonder elke keer te hoeven flushen + ``stat()``-en.
    """
    __slots__ = ("_fh", "_acc")

    def __init__(self, fh, acc: List[int]):
        self._fh = fh
        self._acc = acc

    def write(self, s: str):
        self._acc[0] += len(s)
        return self._fh.write(s)


def maak_fake_big(
    out_dir: str | Path,
    *,
    target_gb: float | None = None,
    players: int | None = None,
    operators: int = 26,
    seed: int = 42,
    signal: bool = True,
    multi_period: bool = True,
    progress_every: int = 50_000,
    buffer_bytes: int = 1 << 20,
) -> Path:
    """Schrijf een fake organisatie-dataset streamend naar `out_dir`.

    Stopconditie: `target_gb` (som van alle tabel-CSV's) óf een vast aantal `players`. Geef er
    minstens één; als beide leeg zijn vallen we terug op `target_gb=1.0`.
    """
    if target_gb is None and players is None:
        target_gb = 1.0
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    op_letters = [chr(ord("a") + (i % 26)) + ("" if i < 26 else str(i // 26))
                  for i in range(operators)]

    # 13 open writer-streams (QUOTE_ALL ; -CSV, identiek format als _maak_fake).
    acc = [0]                       # gedeelde teken-teller over alle streams
    handles: Dict[str, object] = {}
    writers: Dict[str, csv.writer] = {}
    paths: Dict[str, Path] = {}
    for t, header in COLUMNS.items():
        p = out / f"{t}.csv"
        fh = open(p, "w", newline="", encoding="utf-8", buffering=buffer_bytes)
        w = csv.writer(_CountingWriter(fh, acc), delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(header)
        handles[t], writers[t], paths[t] = fh, w, p

    # Persistente pk-teller + spel-catalogus per operator (globaal-uniek over alle spelers).
    pk_by_op: Dict[str, _PK] = {}
    games_by_op: Dict[str, List[str]] = {}
    for op in op_letters:
        pk = _PK(op)
        pk_by_op[op] = pk
        grows, gids = _game_catalog(rng, pk, op)
        games_by_op[op] = gids
        writers["WOK_Game"].writerows(grows)

    target_chars = int(target_gb * (1024 ** 3)) if target_gb is not None else None
    t0 = time.time()
    i = 0
    n_excl = 0
    try:
        while True:
            op = op_letters[i % len(op_letters)]
            pid = f"{op}{i:08d}"
            prows = _player_rows(rng, pk_by_op[op], op, pid, games_by_op[op],
                                 signal=signal, multi_period=multi_period)
            for t, rws in prows.items():
                if rws:
                    writers[t].writerows(rws)
            # tel uitsluiters (eind-status-rij = 2e profielrij, kolomindex 11 = player_profile_status)
            pp = prows.get("WOK_Player_Profile")
            if pp and pp[-1][11] == STATUS_SELF_EXCL:
                n_excl += 1
            i += 1

            if players is not None and i >= players:
                break
            if target_chars is not None and acc[0] >= target_chars:
                break
            if i % progress_every == 0:
                gb = acc[0] / 1024 ** 3
                rate = i / max(1e-9, time.time() - t0)
                tail = f" / {target_gb:.1f} GB" if target_gb else f" / {players:,} spelers"
                print(f"  {i:>12,} spelers — {gb:6.2f} GB{tail}  ({rate:,.0f} spelers/s)", flush=True)
    finally:
        for fh in handles.values():
            fh.close()

    total_bytes = sum(p.stat().st_size for p in paths.values())
    dt = time.time() - t0
    print(f"\n✅ fake_big geschreven naar: {out}")
    print(f"   spelers={i:,}  operators={len(op_letters)}  uitsluiters={n_excl:,}  "
          f"({total_bytes / 1024 ** 3:.2f} GB op schijf, {dt:,.1f}s)")
    _targets = TARGET_MONTHS if multi_period else [TARGET_MONTH]
    print(f"   {'multi' if multi_period else 'single'}-period — activiteit "
          f"{YEAR}-{ACTIVE_MONTHS[0]:02d}..{YEAR}-{ACTIVE_MONTHS[-1]:02d}  "
          f"targets: {', '.join(f'{YEAR}-{m:02d}' for m in _targets)}")
    for t in COLUMNS:
        print(f"     {t}.csv: {paths[t].stat().st_size / 1024 ** 2:,.1f} MB")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Genereer streamend een (grote) fake organisatie-dataset — blueprint van _maak_fake.")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "fake_big"))
    ap.add_argument("--target-gb", type=float, default=None,
                    help="Stop zodra de som van alle tabel-CSV's dit aantal GB bereikt.")
    ap.add_argument("--players", type=int, default=None,
                    help="Stop na dit aantal spelers (alternatief voor --target-gb).")
    ap.add_argument("--operators", type=int, default=26)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-signal", dest="signal", action="store_false", default=True,
                    help="Features onafhankelijk van het label (lekkage-canary).")
    ap.add_argument("--single-period", dest="multi_period", action="store_false", default=True,
                    help="Geen echte holdout: alle uitsluiters in juni. Standaard multi-period (mei+juni).")
    ap.add_argument("--progress-every", type=int, default=50_000)
    args = ap.parse_args(argv)
    maak_fake_big(args.out, target_gb=args.target_gb, players=args.players,
                      operators=args.operators, seed=args.seed, signal=args.signal,
                      multi_period=args.multi_period, progress_every=args.progress_every)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
