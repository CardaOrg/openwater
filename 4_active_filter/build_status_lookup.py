#!/usr/bin/env python3
"""
build_status_lookup.py — maak per operator een LAST_STATUS_LOOKUP_BEFORE_{DDMMYYYY}.csv

Voor elke (operator, cutoff-datum) leest dit script alle WOK_Player_Profile_*.csv
bestanden uit de meest recente cleaned_*_sorted_* map en slaat de laatste bekende
Player_Profile_Status vóór de cutoff op per speler.

Uitvoer: {features_root}/{op}/LAST_STATUS_LOOKUP_BEFORE_{DDMMYYYY}.csv
Kolommen: Player_Profile_ID, last_status

Usage:
    python build_status_lookup.py \
        --cleaned-root /projects/prjs1763/3_cleaned_files_after_07_10_25 \
        --features-root /projects/prjs1763/4_feature_files_after_07_10_25 \
        --cutoffs "01082024|01092024"
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

USECOLS = ["Player_Profile_ID", "Player_Profile_Modified", "Player_Profile_Status"]
CHUNKSIZE = 200_000


def parse_ddmmyyyy(s: str) -> pd.Timestamp:
    return pd.Timestamp(f"{s[4:8]}-{s[2:4]}-{s[:2]}")


def _resolve_usecols(path, wanted):
    """Resolve de gevraagde (CamelCase) kolommen case-insensitief tegen de echte header.

    organisatie-data is snake_case (player_profile_id ↔ Player_Profile_ID). Retourneert
    (actual_cols, rename_map) zodat we met de échte namen kunnen lezen en daarna terug-hernoemen
    naar de CamelCase-namen die de rest van de functie verwacht. (None, None) als een kolom mist.
    """
    try:
        head_cols = list(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return None, None
    ci = {c.lower(): c for c in head_cols}
    actual, rename = [], {}
    for w in wanted:
        a = ci.get(w.lower())
        if a is None:
            return None, None
        actual.append(a)
        if a != w:
            rename[a] = w
    return actual, rename


# NB (organisatie-versie): de kernberekening (laatste status vóór cutoff uit een lijst
# WOK_Player_Profile-bestanden) is uitgelicht naar `last_status_before_cutoff(...)`, zodat de
# organisatie-pijplijn 'm op één gesorteerde map kan toepassen. `build_lookup(...)` (die zelf de
# nieuwste cleaned_*_sorted_* map opzoekt) blijft ongewijzigd van gedrag voor de CLI.
def last_status_before_cutoff(profile_files, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Laatst bekende Player_Profile_Status vóór `cutoff` per speler, uit `profile_files`."""
    chunks = []
    for f in profile_files:
        actual, rename = _resolve_usecols(f, USECOLS)
        if actual is None:
            print(f"    [warn] {f.name}: kolommen {USECOLS} niet gevonden (ook niet snake_case) — overgeslagen", flush=True)
            continue
        try:
            for chunk in pd.read_csv(f, usecols=actual, chunksize=CHUNKSIZE):
                if rename:
                    chunk = chunk.rename(columns=rename)
                ts = (
                    pd.to_datetime(chunk["Player_Profile_Modified"], errors="coerce", utc=True)
                    .dt.tz_localize(None)
                )
                mask = ts < cutoff
                if not mask.any():
                    continue
                sub = chunk.loc[mask, ["Player_Profile_ID", "Player_Profile_Modified", "Player_Profile_Status"]].copy()
                sub["_ts"] = ts[mask].values
                chunks.append(sub[["Player_Profile_ID", "_ts", "Player_Profile_Status"]])
        except Exception as e:
            print(f"    [warn] Kan {f.name} niet lezen: {e}", flush=True)

    if not chunks:
        return pd.DataFrame(columns=["Player_Profile_ID", "last_status"])

    df = pd.concat(chunks, ignore_index=True)
    last = (
        df.sort_values("_ts")
        .groupby("Player_Profile_ID")["Player_Profile_Status"]
        .last()
        .reset_index()
        .rename(columns={"Player_Profile_Status": "last_status"})
    )
    return last


def build_lookup(op_cleaned: Path, cutoff: pd.Timestamp) -> pd.DataFrame:
    sorted_dirs = sorted(op_cleaned.glob("cleaned_*_sorted_*"))
    if not sorted_dirs:
        raise FileNotFoundError(f"Geen cleaned_*_sorted_* map in {op_cleaned}")
    latest = sorted_dirs[-1]
    profile_files = sorted(latest.glob("WOK_Player_Profile_*.csv"))
    if not profile_files:
        raise FileNotFoundError(f"Geen WOK_Player_Profile_*.csv in {latest}")

    return last_status_before_cutoff(profile_files, cutoff)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleaned-root", required=True)
    ap.add_argument("--features-root", required=True)
    ap.add_argument("--cutoffs", required=True,
                    help="Pipe-gescheiden DDMMYYYY cutoff-datums, bijv. '01082024|01092024'")
    ap.add_argument("--operators", default="",
                    help="Kommagescheiden operators (default: alle 1-letter mappen in features-root)")
    ap.add_argument("--overwrite", action="store_true",
                    help="Overschrijf bestaande lookup-bestanden")
    args = ap.parse_args()

    cleaned_root = Path(args.cleaned_root)
    features_root = Path(args.features_root)
    cutoffs = [c.strip() for c in args.cutoffs.split("|") if c.strip()]

    if args.operators:
        operators = [o.strip() for o in args.operators.split(",") if o.strip()]
    else:
        operators = sorted(
            d.name for d in features_root.iterdir()
            if d.is_dir() and len(d.name) == 1
        )

    ok = errors = skipped = 0
    for op in operators:
        op_cleaned = cleaned_root / op
        op_features = features_root / op
        if not op_cleaned.is_dir():
            print(f"[SKIP] {op}: {op_cleaned} niet gevonden")
            skipped += 1
            continue
        for cutoff_str in cutoffs:
            out_path = op_features / f"LAST_STATUS_LOOKUP_BEFORE_{cutoff_str}.csv"
            if out_path.exists() and not args.overwrite:
                print(f"[SKIP] {op}/{cutoff_str}: bestand bestaat al ({out_path.name})")
                skipped += 1
                continue
            try:
                cutoff = parse_ddmmyyyy(cutoff_str)
                df = build_lookup(op_cleaned, cutoff)
                op_features.mkdir(parents=True, exist_ok=True)
                df.to_csv(out_path, index=False)
                n_active = (df["last_status"].str.upper() == "ACTIVE").sum()
                print(f"[OK] {op}/{cutoff_str}: {len(df):,} spelers, {n_active:,} actief → {out_path.name}")
                ok += 1
            except Exception as e:
                print(f"[ERR] {op}/{cutoff_str}: {e}")
                errors += 1

    print(f"\nKlaar: {ok} OK, {skipped} overgeslagen, {errors} fouten")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
