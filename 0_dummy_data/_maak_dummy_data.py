#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_maak_dummy_data.py
=======================

Genereert een synthetische test-dataset in het **echte organisatie-formaat** (anders dan het oude
format, dat per-operator mappen + JSON-embedded velden gebruikte).

Belangrijkste verschillen t.o.v. het oude formaat:

* **Eén map, alle operators bij elkaar** — onderscheid via de `operator_id`-kolom; géén
  `Operator_N/`-submappen, en **één bestand per tabel** (geen `_1`/`_2`-splitsing).
* **Relationeel** (niet JSON-embedded): losse tabellen gekoppeld via `wok_*_pk_id` → `pk_id`.
  - `WOK_Bet` heeft géén speler-kolom → speler via `WOK_Bet_Transaction`; legs via `WOK_Bet_Parts`.
  - `WOK_Game_Session` → speler via `WOK_Game_Session_Transaction`.
  - `WOK_Player_Limits_{Deposit,Game_Type,Login}` koppelen via `wok_player_limit_pk_id`
    naar `WOK_Player_Profile.pk_id` (er is géén aparte parent-limit-tabel).
* **Formaat-quirks van de organisatie-export:**
  - `;`-gescheiden CSV's.
  - datetime **zonder T/Z, mét milliseconden**: ``2025-06-01 11:36:24.123``.
  - decimalen met **komma**: ``12,50``.
  - missing = ``NULL``.
  - meerdere `WOK_Bet_Transaction`-records per bet (stake bij *placed* én *settled*).
  - meerdere limietregels op dezelfde `wok_player_limit_pk_id`.
  - **géén** `*_balance`-limiettabel / `balance_time_window`-kolom.

Het leerbare target blijft hetzelfde idee als voorheen: een deel van de spelers sluit zich uit
(`player_profile_status = SELF_EXCLUDED_TEMP`, met `player_profile_modified` in de y-periode);
uitsluiters gokken zwaarder (tenzij `signal=False` → lekkage-canary). Met `multi_period=True`
zijn er twee target-maanden (juli + augustus) voor een echte temporele holdout.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# -----------------------------------------------------------------------------
# Kolom-volgorde per tabel (exact zoals de organisatie-export)
# -----------------------------------------------------------------------------
COLUMNS: Dict[str, List[str]] = {
    "WOK_Player_Profile": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id", "player_profile_registration_datetime",
        "player_profile_dob", "player_profile_modified", "player_profile_status",
        "player_profile_eod_balance",
    ],
    "WOK_Player_Account_Transaction": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id", "transaction_id", "transaction_datetime",
        "transaction_amount", "transaction_deposit_instrument", "transaction_type",
        "transaction_status",
    ],
    "WOK_Bet": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "bet_id", "bet_start_datetime", "bet_cancellation_reason",
        "bet_type", "bet_xy", "bet_commission", "bet_total_stake", "bet_status",
    ],
    "WOK_Bet_Parts": [
        "created_at", "pk_id", "wok_bet_pk_id", "part_id", "part_event", "part_odds", "part_sport",
        "part_live", "part_bank", "part_match_datetime", "part_prognosis_result_type",
        "part_prognosis_value", "part_stake", "part_cancellation_reason",
    ],
    "WOK_Bet_Transaction": [
        "created_at", "pk_id", "wok_bet_pk_id", "transactions_id", "player_profile_id",
    ],
    "WOK_Game": [
        "AanmaakDatumTijd", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "game_id", "game_type", "game_commercial_name",
        "game_datetime_introduction", "game_datetime_active", "game_datetime_inactive",
    ],
    "WOK_Game_Session": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "game_id", "game_session_id", "game_session_start_datetime",
        "game_session_end_datetime", "game_session_commission", "game_session_rounds",
        "game_session_rounds_won",
    ],
    "WOK_Game_Session_Transaction": [
        "created_at", "pk_id", "wok_game_session_pk_id", "transaction_id", "player_profile_id",
    ],
    "WOK_Player_Limits": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id",
    ],
    "WOK_Player_Limits_Deposit": [
        "created_at", "pk_id", "wok_player_limit_pk_id", "deposit_request_datetime",
        "deposit_start_datetime", "deposit_amount", "deposit_time_window",
    ],
    "WOK_Player_Limits_Game_Type": [
        "created_at", "pk_id", "wok_player_limit_pk_id", "game_type_request_datetime",
        "game_type_start_datetime", "game_type_end_datetime", "game_type_type",
        "game_type_time_window",
    ],
    "WOK_Player_Limits_Login": [
        "created_at", "pk_id", "wok_player_limit_pk_id", "login_request_datetime",
        "login_start_datetime", "login_duration", "login_time_window",
    ],
}

# Waarde-sets
DEPOSIT_INSTRUMENTS = ["CREDIT_CARD", "ELECTRONIC_MONEY", "BANK_TRANSFER", "OTHER"]
TX_STATUSES = ["SUCCESSFUL", "SUCCESSFUL", "SUCCESSFUL", "UNSUCCESSFUL"]
TX_TYPES_W = (["DEPOSIT", "STAKE", "WINNING", "WITHDRAWAL", "OTHER"], [3, 4, 2, 1, 1])
BET_STATUSES = ["BET_WON", "BET_LOST", "BET_CANCELLED", "BET_OPEN"]
BET_TYPES = ["SINGLE", "COMBI", "SYSTEM"]
GAME_TYPES = ["SLOTS", "TABLE", "LIVE"]
SPORTS = ["FOOTBALL", "TENNIS", "BASKETBALL"]
GAME_NAMES = ["Starburst", "Book of Dead", "Gonzo Quest", "Blackjack", "Roulette",
              "Mega Moolah", "Reactoonz", "Sweet Bonanza"]
TIME_WINDOWS = ["DAY", "WEEK", "MONTH"]
STATUS_ACTIVE = "ACTIVE"
STATUS_SELF_EXCL = "SELF_EXCLUDED_TEMP"
NULL = "NULL"


# -----------------------------------------------------------------------------
# Format-helpers (organisatie-conventies)
# -----------------------------------------------------------------------------
def _dt(rng: random.Random, year: int, month: int, day_lo: int, day_hi: int) -> str:
    """Datetime 'YYYY-MM-DD HH:MM:SS.fff' (geen T/Z, mét milliseconden)."""
    base = datetime(year, month, rng.randint(day_lo, day_hi),
                    rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
    return base.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0, 999):03d}"


def _dt_after(rng: random.Random, ts: str, max_min: int = 240) -> str:
    """Een datetime ná `ts` (zelfde formaat), voor bv. session-eind of bet-settlement."""
    base = datetime.strptime(ts[:23], "%Y-%m-%d %H:%M:%S.%f")
    nxt = base + timedelta(minutes=rng.randint(1, max_min), seconds=rng.randint(0, 59))
    return nxt.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0, 999):03d}"


def _dec(value: float, decimals: int = 2) -> str:
    """Decimaal met komma: 12.5 → '12,50'."""
    return f"{value:.{decimals}f}".replace(".", ",")


def _date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


class _PK:
    """Globale, oplopende surrogate-sleutel (pk_id) over alle tabellen."""
    def __init__(self, start: int = 1):
        self.n = start

    def next(self) -> int:
        v = self.n
        self.n += 1
        return v


# -----------------------------------------------------------------------------
# Per-speler generatie
# -----------------------------------------------------------------------------
def _player_rows(rng: random.Random, pk: _PK, op: str, pid: str, game_ids: List[str],
                 extraction_date: str, multi_period: bool, signal: bool) -> Dict[str, List[list]]:
    """Genereer alle rijen (per tabel) voor één speler. Rijen zijn lijsten in kolom-volgorde."""
    rows: Dict[str, List[list]] = {t: [] for t in COLUMNS}
    self_excl = rng.random() < 0.20

    # Tijdsstructuur (zoals de oude generator): single-period (juni→juli) of multi-period
    # (mei–juli activiteit; uitsluiting juli óf augustus → 2 target-maanden).
    if multi_period:
        excl_month = rng.choice([7, 8]) if self_excl else 8
        active_month, final_month, tx_months = 5, excl_month, [5, 6, 7]
    else:
        active_month, final_month, tx_months = 6, 7, [6]

    def tx_month() -> int:
        return rng.choice(tx_months)

    # Activiteits-intensiteit (signal=True → uitsluiters gokken zwaarder; False → label ⊥ features)
    if signal and self_excl:
        intensity, amount_scale = 2.5, 60.0
    else:
        intensity, amount_scale = 1.0, 20.0
    n_tx = int(rng.randint(5, 12) * intensity)
    n_bets = int(rng.randint(2, 5) * intensity)
    n_sessions = int(rng.randint(2, 5) * intensity)

    dob = _date(rng.randint(1965, 2003), rng.randint(1, 12), rng.randint(1, 28))
    reg = _dt(rng, 2025, rng.randint(1, 4), 1, 28)

    # --- WOK_Player_Profile: ACTIVE-snapshot + eind-status (target). pk_id van de ACTIVE-rij
    #     dient als koppelpunt voor de limieten (wok_player_limit_pk_id). ---
    eod_active = _dec(rng.uniform(0, 8) if (signal and self_excl) else rng.uniform(10, 500))
    eod_final = _dec(rng.uniform(0, 3) if (signal and self_excl) else rng.uniform(10, 500))
    profile_pk = pk.next()
    rows["WOK_Player_Profile"].append([
        _dt(rng, 2025, active_month, 1, 5), profile_pk, f"rec-{profile_pk}", extraction_date, op,
        f"ds-{pid}", NULL, pid, reg, dob, _dt(rng, 2025, active_month, 1, 28),
        STATUS_ACTIVE, eod_active,
    ])
    final_status = STATUS_SELF_EXCL if self_excl else STATUS_ACTIVE
    final_pk = pk.next()
    rows["WOK_Player_Profile"].append([
        _dt(rng, 2025, final_month, 1, 5), final_pk, f"rec-{final_pk}", extraction_date, op,
        f"ds-{pid}", NULL, pid, reg, dob, _dt(rng, 2025, final_month, 1, 28),
        final_status, eod_final,
    ])

    # --- WOK_Player_Account_Transaction ---
    tx_ids: List[str] = []
    for k in range(n_tx):
        ttype = rng.choices(TX_TYPES_W[0], weights=TX_TYPES_W[1])[0]
        tid = f"{pid}-t{k}"
        tx_ids.append(tid)
        tpk = pk.next()
        rows["WOK_Player_Account_Transaction"].append([
            _dt(rng, 2025, tx_month(), 1, 28), tpk, f"rec-{tpk}", extraction_date, op, f"ds-{pid}",
            NULL, pid, tid, _dt(rng, 2025, tx_month(), 1, 28), _dec(rng.uniform(1, amount_scale)),
            rng.choice(DEPOSIT_INSTRUMENTS) if ttype == "DEPOSIT" else NULL, ttype,
            rng.choice(TX_STATUSES),
        ])

    # --- WOK_Bet (+ Parts + Transaction). Bet heeft géén speler-kolom; koppeling via Bet_Transaction. ---
    for b in range(n_bets):
        bet_pk = pk.next()
        bstart = _dt(rng, 2025, tx_month(), 1, 28)
        btype = rng.choice(BET_TYPES)
        rows["WOK_Bet"].append([
            _dt(rng, 2025, tx_month(), 1, 28), bet_pk, f"rec-{bet_pk}", extraction_date, op,
            f"ds-{pid}", NULL, f"{pid}-b{b}", bstart, NULL, btype, NULL,
            _dec(rng.uniform(0, 2)), _dec(rng.uniform(1, amount_scale)), rng.choice(BET_STATUSES),
        ])
        # legs (parts)
        n_parts = rng.randint(1, 3) if btype != "SINGLE" else 1
        for q in range(n_parts):
            ppk = pk.next()
            rows["WOK_Bet_Parts"].append([
                _dt(rng, 2025, tx_month(), 1, 28), ppk, bet_pk, f"{pid}-b{b}-p{q}",
                "|Team A| |v| |Team B|", _dec(rng.uniform(1.5, 12.0)), rng.choice(SPORTS),
                rng.choice(["true", "false"]), "false", _dt(rng, 2025, tx_month(), 1, 28),
                "MATCH ODDS", "|Draw|", _dec(rng.uniform(1, 50)), NULL,
            ])
        # transacties per bet: vaak twee (stake bij placed + bij settled) → quirk
        tid = tx_ids[b % len(tx_ids)] if tx_ids else f"{pid}-t0"
        for _ in range(rng.choice([1, 2, 2])):
            btpk = pk.next()
            rows["WOK_Bet_Transaction"].append([
                _dt_after(rng, bstart), btpk, bet_pk, tid, pid,
            ])

    # --- WOK_Game_Session (+ Session_Transaction). Speler via Session_Transaction. ---
    for s in range(n_sessions):
        sess_pk = pk.next()
        sstart = _dt(rng, 2025, tx_month(), 1, 28)
        rows["WOK_Game_Session"].append([
            _dt(rng, 2025, tx_month(), 1, 28), sess_pk, f"rec-{sess_pk}", extraction_date, op,
            f"ds-{pid}", NULL, rng.choice(game_ids), f"{pid}-s{s}", sstart, _dt_after(rng, sstart),
            _dec(rng.uniform(0, 2)), rng.randint(1, 40), rng.randint(0, 10),
        ])
        for j in range(rng.randint(1, 3)):
            stpk = pk.next()
            rows["WOK_Game_Session_Transaction"].append([
                _dt_after(rng, sstart), stpk, sess_pk,
                tx_ids[(s + j) % len(tx_ids)] if tx_ids else f"{pid}-t0", pid,
            ])

    # --- Limieten: parent-tabel WOK_Player_Limits koppelt de limiet aan de speler
    #     (player_profile_id); de sub-tabellen koppelen via wok_player_limit_pk_id →
    #     WOK_Player_Limits.pk_id. Quirk: soms meerdere sub-regels op dezelfde pk_id. ---
    limit_pk = pk.next()
    rows["WOK_Player_Limits"].append([
        _dt(rng, 2025, rng.choice(tx_months), 1, 20), limit_pk, f"rec-{limit_pk}",
        extraction_date, op, f"ds-{pid}", NULL, pid,
    ])
    for _ in range(rng.randint(1, 2)):
        dpk = pk.next()
        drq = _dt(rng, 2025, rng.choice(tx_months), 1, 20)
        rows["WOK_Player_Limits_Deposit"].append([
            _dt(rng, 2025, rng.choice(tx_months), 1, 20), dpk, limit_pk, drq,
            _dt_after(rng, drq, 1440), _dec(float(rng.choice([50, 100, 200, 500, 1000]))),
            rng.choice(TIME_WINDOWS),
        ])
    if rng.random() < 0.5:
        gpk = pk.next()
        grq = _dt(rng, 2025, rng.choice(tx_months), 1, 20)
        rows["WOK_Player_Limits_Game_Type"].append([
            _dt(rng, 2025, rng.choice(tx_months), 1, 20), gpk, limit_pk, grq,
            _dt_after(rng, grq, 1440), NULL, rng.choice(GAME_TYPES), rng.choice(TIME_WINDOWS),
        ])
    if rng.random() < 0.5:
        lpk = pk.next()
        lrq = _dt(rng, 2025, rng.choice(tx_months), 1, 20)
        rows["WOK_Player_Limits_Login"].append([
            _dt(rng, 2025, rng.choice(tx_months), 1, 20), lpk, limit_pk, lrq,
            _dt_after(rng, lrq, 1440), rng.randint(30, 240), rng.choice(TIME_WINDOWS),
        ])

    return rows


# -----------------------------------------------------------------------------
# Hoofdfunctie
# -----------------------------------------------------------------------------
def _maak_dummy_data(
    out_dir: str | Path | None = None,
    *,
    n_operators: int = 5,
    players_per_operator: int = 20,
    seed: int = 42,
    multi_period: bool = True,   # standaard: twee target-maanden → echte temporele holdout
    signal: bool = True,
) -> Path:
    """Genereer de organisatie-formaat dataset: één map met één `;`-gescheiden CSV per tabel."""
    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / "0_dummy_data" / "organisatie_format_dataset"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    master = random.Random(seed)
    extraction_date = _date(2025, 8, 31)
    operators = [chr(ord("a") + i) for i in range(min(n_operators, 26))]

    all_rows: Dict[str, List[list]] = {t: [] for t in COLUMNS}
    pk = _PK(1000)

    # Game-catalogus: per operator een paar games (gedeeld door zijn spelers).
    for op in operators:
        op_rng = random.Random(master.randint(0, 2**31))
        game_ids = []
        for g in range(5):
            gpk = pk.next()
            gid = f"{op}-g{g}"
            game_ids.append(gid)
            all_rows["WOK_Game"].append([
                _dt(op_rng, 2024, op_rng.randint(1, 12), 1, 28), gpk, f"rec-{gpk}", extraction_date,
                op, f"ds-{gid}", NULL, gid, op_rng.choice(GAME_TYPES), op_rng.choice(GAME_NAMES),
                _dt(op_rng, 2024, 1, 1, 28), _dt(op_rng, 2024, 2, 1, 28), NULL,
            ])
        for i in range(1, players_per_operator + 1):
            pid = f"{op}{i:03d}"
            prows = _player_rows(op_rng, pk, op, pid, game_ids, extraction_date,
                                 multi_period, signal)
            for t, rws in prows.items():
                all_rows[t].extend(rws)

    # Schrijf elke tabel als één ;-gescheiden CSV (waarden zijn al geformatteerd).
    for table, cols in COLUMNS.items():
        lines = [";".join(cols)]
        for row in all_rows[table]:
            lines.append(";".join(str(v) for v in row))
        (out_dir / f"{table}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return out_dir


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    path = _maak_dummy_data(target)
    print(f"✅ organisatie-formaat dataset gegenereerd in: {path}")
    for f in sorted(path.glob("*.csv")):
        print(f"   {f.name}: {sum(1 for _ in f.open(encoding='utf-8')) - 1} rijen")
