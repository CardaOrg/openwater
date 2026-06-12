#!/usr/bin/env python3
"""
Bucket-sort: memory-efficient replacement for date_sorting.py.

Instead of loading all files at once, does two passes:
  Pass 1 – bucket : read input CSVs in chunks, append each row to its YYYY_MM bucket file.
  Pass 2 – sort   : load each (small) bucket file, sort by date col, write back.

Buckets span 2023_07 .. 2025_07.
  - rows before 2023-07  →  first bucket  (no data loss)
  - rows after  2025-07  →  last  bucket  (no data loss)
  - NaT rows             →  {table}_NaT.csv

Drop-in replacement for date_sorting.py: same CLI arguments, same output dir.
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import List, Tuple

import pandas as pd

# ----------------------------
# TABLE -> SORT COLUMN mapping (de enige bron van waarheid)
# ----------------------------
TABLE_SORT_COL = {
    "WOK_Bet": "Bet_Start_Datetime",
    "WOK_Complaint": "Complaint_Datetime",
    "WOK_Game_Session": "Game_Session_Start_Datetime",
    "WOK_Game": "Game_Datetime_Introduction",
    "WOK_Intervention": "Intervention_Begin_Datetime",
    "WOK_Net_Deposit_Threshold": "Net_Deposit_Threshold_Datetime",
    "WOK_Operator": "Concerned_Date",
    "WOK_Player_Account_Transaction": "Transaction_Datetime",
    "WOK_Player_Flags": "Extraction_Date",
    "WOK_Player_Limits": "Extraction_Date",
    "WOK_Player_Profile": "Player_Profile_Modified",
}

# ----------------------------
# Bucket range  (first bucket catches underflow, last catches overflow)
# ----------------------------
BUCKET_START = (2023, 7)
BUCKET_END   = (2025, 7)


def _build_buckets() -> List[str]:
    buckets = []
    y, m = BUCKET_START
    while (y * 100 + m) <= (BUCKET_END[0] * 100 + BUCKET_END[1]):
        buckets.append(f"{y:04d}_{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return buckets


ALL_BUCKETS  = _build_buckets()
FIRST_BUCKET = ALL_BUCKETS[0]
LAST_BUCKET  = ALL_BUCKETS[-1]
LO = int(FIRST_BUCKET.replace("_", ""))
HI = int(LAST_BUCKET.replace("_", ""))


# ----------------------------
# utils  (kept identical to date_sorting.py)
# ----------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def fmt_int(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")

def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def count_rows_fast(csv_path: str | Path) -> int:
    n = 0
    with open(csv_path, "rb") as f:
        for _ in f:
            n += 1
    return max(0, n - 1)

_suffix_re = re.compile(r"^(?P<stem>.+?)(?:_(?P<num>\d+))?\.csv$", re.IGNORECASE)

def natural_suffix_key(path: str | Path) -> Tuple[str, int]:
    bn = Path(path).name
    m = _suffix_re.match(bn)
    if not m:
        return (bn, 0)
    stem = m.group("stem") or bn
    num = m.group("num")
    return (stem, int(num) if num is not None else 0)

def collect_table_files(cleaned_dir: str | Path, table: str) -> List[str]:
    cd = Path(cleaned_dir)
    pattern = re.compile(rf"^{re.escape(table)}(?:_(\d+))?\.csv$", re.IGNORECASE)
    files: List[str] = []
    for p in cd.glob("*.csv"):
        if pattern.match(p.name):
            files.append(str(p))
    files = sorted(set(files), key=lambda p: natural_suffix_key(p))
    files = [f for f in files if "_labelled" not in Path(f).name]
    return files


# ----------------------------
# Bucketing helper
# ----------------------------
def assign_bucket(dt_series: pd.Series) -> pd.Series:
    """Map a non-null datetime Series to bucket label strings, clamped to range.

    LET OP (legacy): clampt op het vaste venster ALL_BUCKETS (2023_07..2025_07). De organisatie-versie
    gebruikt sinds de datagedreven-fix `_month_labels` + `_scan_month_range` (zie sort_table) en
    roept deze functie niet meer aan; ze blijft alleen voor terugwaartse compatibiliteit staan.
    """
    ym     = dt_series.dt.year * 100 + dt_series.dt.month
    labels = (dt_series.dt.year.astype(str).str.zfill(4)
              + "_"
              + dt_series.dt.month.astype(str).str.zfill(2))
    labels = labels.where(ym >= LO, FIRST_BUCKET)
    labels = labels.where(ym <= HI, LAST_BUCKET)
    return labels


def _month_labels(dt_series: pd.Series) -> pd.Series:
    """Datagedreven label 'YYYY_MM' per datum — géén clamping (range dekt de data exact)."""
    return (dt_series.dt.year.astype(int).astype(str).str.zfill(4)
            + "_"
            + dt_series.dt.month.astype(int).astype(str).str.zfill(2))


def _scan_month_range(input_files: List[str], sort_col: str, chunksize: int):
    """Bepaal de werkelijke [min, max] maand (als YYYYMM-ints) in de sorteerkolom.

    Returnt (None, None) als er geen enkele geldige datum is (alles NaT). Streamt in chunks en
    leest alléén de sorteerkolom, zodat dit ook op grote bestanden goedkoop blijft.
    """
    lo = hi = None
    for f in input_files:
        if Path(f).stat().st_size == 0:
            continue
        for chunk in pd.read_csv(f, usecols=[sort_col], chunksize=chunksize, low_memory=False):
            dt = pd.to_datetime(chunk[sort_col], format="ISO8601", errors="coerce", utc=True).dropna()
            if dt.empty:
                continue
            ym = (dt.dt.year * 100 + dt.dt.month).astype(int)
            cur_lo, cur_hi = int(ym.min()), int(ym.max())
            lo = cur_lo if lo is None else min(lo, cur_lo)
            hi = cur_hi if hi is None else max(hi, cur_hi)
    return lo, hi


def _months_between(lo_ym: int, hi_ym: int) -> List[str]:
    """Alle 'YYYY_MM'-buckets van lo_ym t/m hi_ym (inclusief), maand voor maand."""
    out: List[str] = []
    y, m = lo_ym // 100, lo_ym % 100
    while y * 100 + m <= hi_ym:
        out.append(f"{y:04d}_{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# ----------------------------
# sort_table — kernlogica per (operator, tabel)
# ----------------------------
# NB (organisatie-versie): in het origineel zat onderstaande logica volledig in main(). Hier is
# de body verplaatst naar de herbruikbare functie `sort_table(...)` zodat sort_pipeline.py
# 'm over alle tabellen kan loopen (de SLURM-array die dat op Snellius deed vervalt). De
# `main()` hieronder is een dunne CLI-wrapper die exact dezelfde argumenten houdt.
def sort_table(
    operator_letter: str,
    cleaned_dir: str | Path,
    table: str,
    out_dir: str | Path | None = None,
    chunksize: int = 200_000,
) -> dict:
    """
    Bucket-sort één tabel binnen één cleaned-map op de bijbehorende datumkolom.

    Returns een dict met o.a. {table, skipped, ok, rows_in, rows_out, out_dir}.
    """
    letter      = operator_letter
    cleaned_dir = Path(cleaned_dir)

    # organisatie: relationele tabellen (WOK_Bet_Parts, WOK_Bet_Transaction, WOK_Player_Limits_*, …) staan
    # niet in TABLE_SORT_COL. In plaats van te crashen geven we die ongesorteerd door (passthrough),
    # zodat ze beschikbaar blijven voor de feature-stap.
    sort_col = TABLE_SORT_COL.get(table)

    if not cleaned_dir.exists():
        raise FileNotFoundError(f"cleaned_dir not found: {cleaned_dir}")

    if out_dir:
        out_dir = Path(out_dir)
    else:
        sort_dt = time.strftime("%Y%m%d_%H%M%S")
        out_dir = cleaned_dir.parent / f"{cleaned_dir.name}_sorted_{sort_dt}"
    safe_mkdir(out_dir)

    print("\n" + "=" * 80)
    print(f"[START] {letter} | {table} | sort={sort_col} | {_now()}")
    print(f"cleaned_dir = {cleaned_dir}")
    print(f"out_dir     = {out_dir}")
    print(f"buckets     = datagedreven (maand-buckets o.b.v. het werkelijke datumbereik)")
    print("=" * 80)

    input_files = collect_table_files(cleaned_dir, table)
    if not input_files:
        print(f"[SKIP] No files found for table={table} in {cleaned_dir}")
        return {"table": table, "skipped": True, "ok": True,
                "rows_in": 0, "rows_out": 0, "out_dir": str(out_dir)}

    print(f"\n[{letter}|{table}] {len(input_files)} input file(s) found")

    # organisatie-uitbreiding: als de sorteerkolom volledig ontbreekt in het bestand (organisatie-data levert
    # niet voor elke tabel een datumkolom, bv. WOK_Game zonder Game_Datetime_Introduction of
    # WOK_Player_Limits zonder Extraction_Date), dan kunnen we niet op tijd sorteren. We geven de
    # bestanden dan ONGESORTEERD door (gekopieerd naar de output), zodat de tabel beschikbaar
    # blijft voor de feature-stap. Geen dataverlies; alleen geen sortering.
    head_cols = list(pd.read_csv(input_files[0], nrows=0).columns)
    # organisatie-data is snake_case; resolve de (mogelijk CamelCase) sorteerkolom case-insensitief.
    if sort_col is not None and sort_col not in head_cols:
        _ci = {c.lower(): c for c in head_cols}
        sort_col = _ci.get(sort_col.lower(), sort_col)
    if sort_col is None or sort_col not in head_cols:
        import shutil as _shutil
        rows_passthrough = 0
        for f in input_files:
            _shutil.copy(f, out_dir / Path(f).name)
            rows_passthrough += count_rows_fast(f)
        warn = (
            "\n" + "⚠️ " * 26 + "\n"
            f"⚠️⚠️  WAARSCHUWING [{letter}|{table}]: sorteerkolom '{sort_col}' ONTBREEKT in de data!\n"
            f"⚠️⚠️  De {len(input_files)} bestand(en) zijn ONGESORTEERD doorgegeven "
            f"({fmt_int(rows_passthrough)} rijen).\n"
            f"⚠️⚠️  Sorting hoort normaal gesproken te werken — controleer of deze tabel terecht\n"
            f"⚠️⚠️  geen datumkolom '{sort_col}' heeft. Tijd-afhankelijke features op deze tabel\n"
            f"⚠️⚠️  zijn dan NIET op chronologische volgorde gebaseerd.\n"
            + "⚠️ " * 26
        )
        print(warn, flush=True)
        return {"table": table, "skipped": False, "ok": True, "unsorted": True,
                "rows_in": rows_passthrough, "rows_out": rows_passthrough, "out_dir": str(out_dir)}

    # organisatie-fix (datagedreven bucketing): bepaal de buckets uit het WERKELIJKE datumbereik van deze
    # tabel — precies de maanden die voorkomen — i.p.v. een vast venster 2023_07..2025_07. Eén
    # bucket per maand, ongeacht het jaar, en zonder underflow/overflow-clamping (een losse rij in
    # 2026 verdwijnt dus niet meer in een geclampte 2025-bucket).
    lo_ym, hi_ym = _scan_month_range(input_files, sort_col, chunksize)
    local_buckets = _months_between(lo_ym, hi_ym) if lo_ym is not None else []
    first_bucket = local_buckets[0] if local_buckets else None
    last_bucket  = local_buckets[-1] if local_buckets else None
    print(f"[{letter}|{table}] datumbereik → "
          + (f"{first_bucket} .. {last_bucket}  ({len(local_buckets)} maand-bucket(s))"
             if local_buckets else "geen geldige datums (alles → NaT)"))

    bucket_paths = {b: out_dir / f"{table}_{i+1}.csv" for i, b in enumerate(local_buckets)}
    nat_path     = out_dir / f"{table}_NaT.csv"

    # ------------------------------------------------------------------ #
    # PASS 1 – bucket                                                      #
    # ------------------------------------------------------------------ #
    print(f"\n[{letter}|{table}] PASS 1: bucketing in chunks of {fmt_int(chunksize)}...")

    written       = set()   # tracks which output files already have a header row
    rows_in_total = 0
    rows_nat      = 0

    for f in input_files:
        if Path(f).stat().st_size == 0:
            print(f"  skipping {Path(f).name} (empty file)")
            continue
        print(f"  reading {Path(f).name}...")
        for chunk in pd.read_csv(f, chunksize=chunksize, low_memory=False):
            rows_in_total += len(chunk)
            dt = pd.to_datetime(chunk[sort_col], format="ISO8601", errors="coerce", utc=True)

            # NaT rows — write separately, unsorted
            nat_mask = dt.isna()
            if nat_mask.any():
                rows_nat += int(nat_mask.sum())
                chunk[nat_mask].to_csv(nat_path, mode="a",
                                       header=nat_path not in written, index=False)
                written.add(nat_path)

            # Valid rows — route to monthly bucket
            valid = chunk[~nat_mask].copy()
            if valid.empty:
                continue

            valid["_b"] = _month_labels(dt[~nat_mask])
            for bucket, group in valid.groupby("_b", sort=False):
                bp = bucket_paths[bucket]
                group.drop(columns=["_b"]).to_csv(
                    bp, mode="a", header=bp not in written, index=False)
                written.add(bp)

    print(f"[{letter}|{table}] PASS 1 done: {fmt_int(rows_in_total)} rows read, "
          f"{fmt_int(rows_nat)} NaT")

    # ------------------------------------------------------------------ #
    # PASS 2 – sort each bucket                                            #
    # ------------------------------------------------------------------ #
    print(f"\n[{letter}|{table}] PASS 2: sorting buckets...")

    rows_out_total = 0
    for b in local_buckets:
        bp = bucket_paths[b]
        if not bp.exists():
            continue
        df = pd.read_csv(bp, low_memory=False)
        df["_sort_key"] = pd.to_datetime(df[sort_col], format="ISO8601", errors="coerce", utc=True)
        df = df.sort_values("_sort_key", kind="mergesort", na_position="last")
        df = df.drop(columns=["_sort_key"]).reset_index(drop=True)
        df.to_csv(bp, index=False)
        rows_out_total += len(df)
        print(f"  -> {bp.name}: {fmt_int(len(df))} rows")

    rows_out_total += rows_nat  # NaT file is already written, not re-sorted

    # ------------------------------------------------------------------ #
    # Audit                                                                #
    # ------------------------------------------------------------------ #
    ok = (rows_in_total == rows_out_total)
    print("\n" + "-" * 80)
    print(f"[{letter}|{table}] AUDIT  "
          f"rows_in={fmt_int(rows_in_total)}  rows_out={fmt_int(rows_out_total)}")
    if ok:
        print(f"[{letter}|{table}] PASS")
    else:
        print(f"[{letter}|{table}] FAIL: mismatch detected")

    # ------------------------------------------------------------------ #
    # Sort check – laatste (nieuwste) maand-bucket                         #
    # ------------------------------------------------------------------ #
    if last_bucket is None:
        print(f"\n[{letter}|{table}] Sort check: n.v.t. (geen maand-buckets, alles NaT)")
        last_bp = None
    else:
        last_bp = bucket_paths[last_bucket]
    print(f"\n[{letter}|{table}] Sort check: {last_bp.name if last_bp else '-'}")
    if last_bp is None or not last_bp.exists():
        print(f"  (file does not exist – no overflow data, skipping check)")
    else:
        dt_check = pd.to_datetime(
            pd.read_csv(last_bp, usecols=[sort_col], low_memory=False)[sort_col],
            format="ISO8601", errors="coerce", utc=True,
        ).dropna()
        if len(dt_check) < 2:
            print(f"  ({fmt_int(len(dt_check))} non-NaT rows – nothing to verify)")
        elif (dt_check.diff().iloc[1:] < pd.Timedelta(0)).any():
            raise RuntimeError(
                f"[{letter}|{table}] Sort check FAILED: {last_bp.name} is not sorted by {sort_col}"
            )
        else:
            print(f"  OK – {fmt_int(len(dt_check))} rows are sorted")

    print(f"[DONE] {letter} | {table} | {_now()}")

    return {"table": table, "skipped": False, "ok": ok,
            "rows_in": rows_in_total, "rows_out": rows_out_total,
            "out_dir": str(out_dir)}


# ----------------------------
# main — dunne CLI-wrapper (identieke argumenten als het origineel)
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator-letter", required=True)
    ap.add_argument("--cleaned-dir",     required=True)
    ap.add_argument("--table",           required=True)
    ap.add_argument("--out-dir",         required=False, default=None)
    ap.add_argument("--chunksize",       type=int, default=200_000)
    args = ap.parse_args()

    sort_table(
        operator_letter=args.operator_letter,
        cleaned_dir=args.cleaned_dir,
        table=args.table,
        out_dir=args.out_dir,
        chunksize=args.chunksize,
    )


if __name__ == "__main__":
    main()
