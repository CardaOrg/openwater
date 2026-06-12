# operator_filters.py
"""
Operator-specifieke prevalidatie-filters (gestuurd via OPERATOR_PREFIX)
======================================================================

Doel
----
Voer *kleine, auditeerbare en performante* filters uit vóór schema-validatie,
zodat bekende uitzonderingen geen lawine aan WARN/ERROR berichten veroorzaken.

Sturing per run
---------------
- Kies een operator via environment variabele `OPERATOR_PREFIX`.
  Voorbeeld:
      export OPERATOR_PREFIX="b"
- Er is **geen** fallback op bestandsnaam; de keuze is expliciet per run.

Gedrag (huidige operators)
--------------------------
- Operator "b":
    1) Drop rijen met lege `Transaction_Amount`.
    2) Vul lege `Game_Session_Rounds_Won` met "0" (string), vóór validatie.

Algemene opties
---------------
- Dry-run: `RG_FILTER_DRYRUN=1` → alleen rapporteren wat er zou gebeuren (geen mutatie).
- Drop-waarschuwing bij hoge fractie:
    `RG_FILTER_MAXDROP_FRACTION` (default 0.10 = 10%).
    Dit geeft *alleen* een WARNING; het gedrag blijft verder gelijk.

Publieke API
------------
operator_specific_filter(
    df: pd.DataFrame,
    *,
    raw_filename: str,
    chunk_index: int,
    rows_processed_so_far: int,
    logger=None
) -> tuple[pd.DataFrame, dict]

Retourneert:
- Het (eventueel) gefilterde DataFrame
- Een compact rapport-dict (applied, operator, dropped, fraction, mode, examples, fills)
"""

from __future__ import annotations

import os
from typing import Tuple, Dict, Any, Callable

import pandas as pd

# ---------- Omgevingsvariabelen ----------
OPERATOR_PREFIX = os.getenv("OPERATOR_PREFIX", "").strip()
EMPTY_TOKENS = {"", " ", "null", "NULL", "NaN", "N/A"}


# ---------- Kleine hulpfuncties (vectorized) ----------

def _is_empty_strlike(v: Any) -> bool:
    """True als de waarde None of een 'lege/NULL-achtige' string is."""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() in EMPTY_TOKENS
    return False


def _would_drop_mask_empty_amount(df: pd.DataFrame, column: str) -> pd.Series:
    """
    Bepaal *vectorized* welke rijen 'leeg' zijn in `column`. 
    Als de kolom ontbreekt → mask is overal False (niets te droppen).
    """
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[column]
    return s.isna() | s.map(_is_empty_strlike)


def _fill_empty_with(df: pd.DataFrame, column: str, fill_value: str) -> int:
    """
    Vervang *vectorized* lege/NULL-achtige waarden in `column` door `fill_value`.
    Retourneert het aantal vervangen rijen. Geen per-rij logging.
    """
    if column not in df.columns:
        return 0
    s = df[column]
    mask = s.isna() | s.map(_is_empty_strlike)
    count = int(mask.sum())
    if count > 0:
        # In pre-validatiestap houden we strings aan; "0" is dus prima hier.
        df.loc[mask, column] = fill_value
    return count


# ---------- Operator-specifieke filterfuncties ----------
# Elke operator-functie voert ALLES uit wat voor die operator hoort
# (droppende regels bepalen, en eventuele fills uitvoeren als níet dry-run).
# De functie retourneert: (drop_mask, meta_dict)

def _filter_w(
    df: pd.DataFrame,
    *,
    dryrun: bool,
    raw_filename: str,
    chunk_index: int,
    rows_processed_so_far: int,
    logger=None,
) -> tuple[pd.Series, Dict[str, Any]]:
    """
    Operator 'w' — MM/DD/YYYY-correctie voor Player_Profile:
    - Player_Profile_Registration_Datetime
    - Player_Profile_DOB
    """
    mask = pd.Series(False, index=df.index)  # geen drop
    fills = 0

    # Alleen toepassen voor WOK_Player_Profile.csv
    if "WOK_Player_Profile" in raw_filename:
        for col in ["Player_Profile_Registration_Datetime", "Player_Profile_DOB"]:
            if col in df.columns:
                if not dryrun:
                    # Verwacht MM/DD/YYYY HH:MM:SS → ISO
                    df[col] = (
                        pd.to_datetime(df[col], format="%m/%d/%Y %H:%M:%S", errors="coerce")
                        .dt.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    fills += int(df[col].notna().sum())
                else:
                    fills += df[col].notna().sum()

    meta = {
        "rule": "convert_MMDDYYYY_to_ISO",
        "drop_column": None,
        "fills": fills,
        "fill_column": "Player_Profile_Registration_Datetime,Player_Profile_DOB",
    }
    return mask, meta

def _filter_b(
    df: pd.DataFrame,
    *,
    dryrun: bool,
    raw_filename: str,
    chunk_index: int,
    rows_processed_so_far: int,
    logger=None,
) -> tuple[pd.Series, Dict[str, Any]]:
    """
    Operator 'b' — alles-in-één:
    1) Drop: rijen met lege Transaction_Amount
    2) Fill: lege Game_Session_Rounds_Won → "0" (alleen toepassen als níet dry-run)
    """
    # --- 1) DROP: Transaction_Amount leeg? -> droppen
    col_drop = "Transaction_Amount"
    drop_mask = _would_drop_mask_empty_amount(df, col_drop)
    would_drop = int(drop_mask.sum())

    # --- 2) FILL: Game_Session_Rounds_Won leeg? -> "0"
    col_fill = "Game_Session_Rounds_Won"
    fills = 0
    if col_fill in df.columns:
        # Bij dry-run enkel tellen; niet vullen.
        if dryrun:
            s = df[col_fill]
            fill_mask = s.isna() | s.map(_is_empty_strlike)
            fills = int(fill_mask.sum())
        else:
            fills = _fill_empty_with(df, col_fill, "0")

    # Compacte meta-info voor rapportage/logging (géén per-rij details)
    meta = {
        "rule": "drop_empty_amount + fill_rounds_won_zero",
        "drop_column": col_drop,
        "fill_column": col_fill,
        "fills": fills,              # hoeveel waarden zijn (of zouden worden) gevuld
    }
    return drop_mask, meta


# ---------- Registry (makkelijk uitbreidbaar) ----------
# Voeg later eenvoudig een nieuwe operator toe, bijv.:
# def _filter_c(...): ...
# _FILTERS["c"] = _filter_c
_FILTERS: dict[str, Callable[..., tuple[pd.Series, Dict[str, Any]]]] = {
    "b": _filter_b,
    "w": _filter_w,
}


# ---------- Publieke entrypoint ----------
def operator_specific_filter(
    df: pd.DataFrame,
    *,
    raw_filename: str,
    chunk_index: int,
    rows_processed_so_far: int,
    logger=None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Pas (indien aanwezig) het operator-specifieke filter toe, vóór schema-validatie.

    Parameters
    ----------
    df : pd.DataFrame
        Chunk met ruwe data (string-kolommen).
    raw_filename : str
        Bestandsnaam; puur voor context in logging/rapport.
    chunk_index : int
        1-gebaseerde chunk-index (handig voor logging).
    rows_processed_so_far : int
        Aantal rijen vóór deze chunk (voor globale rijnummer-voorbeelden).
    logger : logging.Logger | None
        Optionele logger; als None wordt print() gebruikt.

    Returns
    -------
    (df_filtered, report) : tuple[pd.DataFrame, dict]
        - df_filtered: df of subset na toepassen drops (en eventuele fills).
        - report: compact audit-rapport met:
            applied, operator, rule, column, dropped, would_drop, fraction, mode, examples, fills
    """
    # Geen operator gezet → geen filter
    if not OPERATOR_PREFIX:
        return df, {"applied": False}

    # Dry-run & drop-waarschuwingsdrempel uit omgeving
    dryrun = os.getenv("RG_FILTER_DRYRUN", "0") == "1"
    try:
        max_fraction = float(os.getenv("RG_FILTER_MAXDROP_FRACTION", "0.10"))
        if not (0.0 <= max_fraction <= 1.0):
            max_fraction = 0.10
    except Exception:
        max_fraction = 0.10

    # Zoek de filterfunctie op basis van gekozen operator
    filter_fn = _FILTERS.get(OPERATOR_PREFIX)
    if filter_fn is None:
        # Onbekende operator → stilletjes geen filter toepassen
        return df, {"applied": False, "operator": OPERATOR_PREFIX, "note": "no filter for operator"}

    # Laat de operator-functie het werk doen (mask + meta)
    drop_mask, meta = filter_fn(
        df,
        dryrun=dryrun,
        raw_filename=raw_filename,
        chunk_index=chunk_index,
        rows_processed_so_far=rows_processed_so_far,
        logger=logger,
    )

    to_drop = int(drop_mask.sum())
    total = int(len(df))
    frac = (to_drop / total) if total > 0 else 0.0

    # Voorbeelden van globale rijnummers (max 3) voor audit (header=1 → data start op 2)
    example_local_idx = list(df[drop_mask].index[:3])
    examples_global = [rows_processed_so_far + 2 + i for i in example_local_idx]

    # Waarschuw bij hoge drop-fractie (alleen logging; gedrag blijft gelijk)
    if to_drop > 0 and frac > max_fraction:
        msg = (f"[FILTER-GUARD] {raw_filename} chunk {chunk_index} dropped {frac:.1%} "
               f"({to_drop}/{total}) rows for {OPERATOR_PREFIX}:{meta.get('rule','?')} "
               f"— above threshold {max_fraction:.0%}.")
        if logger:
            logger.warning(msg)
        else:
            print(msg, flush=True)

    # Bouw rapport (compact, geen per-rij details)
    report: Dict[str, Any] = {
        "applied": True,
        "operator": OPERATOR_PREFIX,
        "rule": meta.get("rule", "unknown_rule"),
        "column": meta.get("drop_column"),
        "dropped": 0 if dryrun else to_drop,
        "would_drop": to_drop,
        "fraction": frac,
        "mode": "dryrun" if dryrun else "apply",
        "examples": examples_global,
        "fills": meta.get("fills", 0),
        "fill_column": meta.get("fill_column"),
    }

    # Toepassen van drop (tenzij dry-run)
    if not dryrun and to_drop > 0:
        df = df[~drop_mask].copy()

    # Optioneel: één samenvattende regel voor fills (géén per-rij logging)
    fills = report["fills"]
    if fills > 0:
        msg = (f"[FILTER] {raw_filename} chunk {chunk_index}: "
               f"{fills} lege waarden in {report['fill_column']} → '0'")
        if logger:
            logger.warning(msg)
        else:
            print(msg, flush=True)

    return df, report