#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_maak_fake.py
=================

Genereert een synthetische test-dataset die **exact de blueprint van `voorbeeld_11/` volgt**
(de echte, gemaskeerde organisatie-export), maar met **realistische waarden** en een **relevant
datumbereik (jan–jun 2026)**, zodat de hele pijplijn (clean → sort → features → model)
end-to-end getest kan worden op niet-lege data.

Verschillen t.o.v. `voorbeeld_11/` (dat is pure structuur-data):
* echte, gevarieerde waarden i.p.v. placeholders (`AAAA`, `1111-11-11`);
* **multi-period (standaard)**: activiteit jan–apr 2026, uitsluiters verdeeld over **twee**
  target-maanden (mei + juni) → een **echte temporele holdout** mogelijk (validatie y=mei,
  test y=juni). Met `--single-period` vallen alle uitsluiters in juni (geen holdout);
* ~100 spelers over enkele operators, relationeel consistent gekoppeld.

Formaat-fidelity (1-op-1 met `voorbeeld_11/`):
* `;`-gescheiden, **alle velden tussen quotes** (`csv.QUOTE_ALL`);
* decimalen met **komma** (`12,50`); missing = `NULL`;
* datetime `YYYY-MM-DD HH:MM:SS.fff` (millis); `WOK_Game.AanmaakDatumTijd` met 7 decimalen;
* tabel `WOK_Player_Limits` (parent) + sub-tabellen Deposit/Login/Game_Type/**Balance**.

Gebruik:
    python _maak_fake.py                      # → _organisatie_code/voorbeeld_fake/ (100 spelers)
    python _maak_fake.py --out ./ander_pad --players 250 --seed 7

Vensters voor een ECHTE temporele holdout (multi-period):
    validatie : x=01012026:30042026  y=01052026:31052026   (features jan–apr, target mei)
    test      : x=01012026:30042026  y=01062026:30062026   (zelfde features, target juni — later!)
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# -----------------------------------------------------------------------------
# Kolom-volgorde per tabel — EXACT zoals voorbeeld_11/ (headers 1-op-1 overgenomen)
# -----------------------------------------------------------------------------
COLUMNS: Dict[str, List[str]] = {
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
    "WOK_Player_Account_Transaction": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id", "transaction_id", "transaction_datetime",
        "transaction_amount", "transaction_deposit_instrument", "transaction_type",
        "transaction_status",
    ],
    "WOK_Player_Limits": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id",
    ],
    "WOK_Player_Limits_Balance": [
        "created_at", "pk_id", "wok_player_limit_pk_id", "balance_request_datetime",
        "balance_start_datetime", "balance_amount", "balance_time_window",
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
    "WOK_Player_Limits_Participation": [
        "created_at", "pk_id", "wok_player_limit_pk_id", "participation_request_datetime",
        "participation_start_datetime", "participation_amount", "participation_time_window",
    ],
    "WOK_Player_Profile": [
        "created_at", "pk_id", "record_id", "extraction_date", "operator_id", "data_safe_id",
        "replaced_record_id", "player_profile_id", "player_profile_registration_datetime",
        "player_profile_dob", "player_profile_modified", "player_profile_status",
        "player_profile_eod_balance",
    ],
}

# Waarde-sets (afgeleid uit voorbeeld_11/: 'COMBINED', 'Football', 'SLOTS', 'Month', ...)
DEPOSIT_INSTRUMENTS = ["CREDIT_CARD", "ELECTRONIC_MONEY", "BANK_TRANSFER", "OTHER"]
TX_STATUSES = ["SUCCESSFUL", "SUCCESSFUL", "SUCCESSFUL", "UNSUCCESSFUL"]
TX_TYPES_W = (["DEPOSIT", "STAKE", "WINNING", "WITHDRAWAL", "OTHER"], [3, 4, 2, 1, 1])
BET_STATUSES = ["BET_PLACED", "BET_WON", "BET_LOST", "BET_CANCELLED"]
BET_TYPES = ["SINGLE", "COMBINED", "SYSTEM"]
GAME_TYPES = ["SLOTS", "TABLE", "LIVE", "BINGO"]
SPORTS = ["Football", "Tennis", "Basketball"]
COMPETITIONS = ["UEFA Champions League", "Eredivisie", "Premier League", "ATP Tour"]
DUTCH_CLUBS = ["Feyenoord Rotterdam", "Ajax", "PSV Eindhoven", "AZ Alkmaar", "FC Twente"]
FOREIGN_CLUBS = ["Fenerbahce Istanbul", "Real Madrid", "Bayern Munich", "Arsenal", "Juventus"]
GAME_NAMES = ["PNG Colt Lightning Firestorm", "Starburst", "Book of Dead", "Gonzo Quest",
              "Blackjack VIP", "Lightning Roulette", "Mega Moolah", "Sweet Bonanza"]
TIME_WINDOWS = ["Day", "Week", "Month"]
GAME_TYPE_LIMITS = ["SPORTSBOOK", "CASINO"]
STATUS_ACTIVE = "ACTIVE"
STATUS_SELF_EXCL = "SELF_EXCLUDED_TEMP"
NULL = "NULL"

# Activiteit jan–apr 2026 (de feature-vensters); twee target-maanden voor een ECHTE temporele
# holdout: validatie y=mei, test y=juni. Uitsluiters worden over die twee maanden verdeeld.
ACTIVE_MONTHS = [1, 2, 3, 4]
TARGET_MONTHS = [5, 6]          # [validatie-target, test-target]
TARGET_MONTH = TARGET_MONTHS[-1]  # legacy/single-period fallback (juni)
YEAR = 2026
EXTRACTION_DATE = "2026-06-30 23:59:59.000"


# -----------------------------------------------------------------------------
# Format-helpers (organisatie-conventies)
# -----------------------------------------------------------------------------
def _dt(rng: random.Random, month: int, day_lo: int = 1, day_hi: int = 28) -> str:
    """Datetime 'YYYY-MM-DD HH:MM:SS.fff' (millis, geen T/Z)."""
    base = datetime(YEAR, month, rng.randint(day_lo, day_hi),
                    rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
    return base.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0, 999):03d}"


def _dt_after(rng: random.Random, ts: str, max_min: int = 240) -> str:
    """Een datetime ná `ts` (zelfde millis-formaat)."""
    base = datetime.strptime(ts[:23], "%Y-%m-%d %H:%M:%S.%f")
    nxt = base + timedelta(minutes=rng.randint(1, max_min), seconds=rng.randint(0, 59))
    return nxt.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0, 999):03d}"


def _game_dt(rng: random.Random, month: int) -> str:
    """WOK_Game.AanmaakDatumTijd: zelfde datum maar met 7 decimalen (zoals voorbeeld_11)."""
    base = datetime(YEAR, month, rng.randint(1, 28),
                    rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
    return base.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0, 9999999):07d}"


def _dec(value: float, decimals: int = 2) -> str:
    """Decimaal met komma: 12.5 → '12,50'."""
    return f"{value:.{decimals}f}".replace(".", ",")


def _date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


class _PK:
    """Globale, oplopende surrogate-sleutel (pk_id-string) over alle tabellen."""
    def __init__(self, op: str):
        self.op = op
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"{self.op}-pk-{self.n:08d}"


# -----------------------------------------------------------------------------
# Spel-catalogus (gedeeld over operators): WOK_Game
# -----------------------------------------------------------------------------
def _game_catalog(rng: random.Random, pk: _PK, op: str) -> tuple:
    """Bouw een kleine WOK_Game-catalogus; retourneer (rows, [game_ids])."""
    rows: List[list] = []
    game_ids: List[str] = []
    for name in GAME_NAMES:
        gid = f"{op}-game-{len(game_ids):03d}"
        game_ids.append(gid)
        intro = _game_dt(rng, rng.choice(ACTIVE_MONTHS))
        rows.append([
            intro, pk.next(), f"rec-{pk.n}", EXTRACTION_DATE, op, f"PROD_{op}", NULL,
            gid, rng.choice(GAME_TYPES), name, intro, intro, NULL,
        ])
    return rows, game_ids


# -----------------------------------------------------------------------------
# Per-speler generatie
# -----------------------------------------------------------------------------
def _player_rows(rng: random.Random, pk: _PK, op: str, pid: str, game_ids: List[str],
                 signal: bool, multi_period: bool = True) -> Dict[str, List[list]]:
    rows: Dict[str, List[list]] = {t: [] for t in COLUMNS}
    self_excl = rng.random() < 0.20

    # uitsluiters gokken zwaarder (signal); anders noise-canary
    if signal and self_excl:
        intensity, amount_scale = 2.2, 80.0
    else:
        intensity, amount_scale = 1.0, 20.0
    n_tx = max(3, int(rng.randint(5, 12) * intensity))
    n_bets = max(2, int(rng.randint(2, 5) * intensity))
    n_sessions = max(2, int(rng.randint(2, 5) * intensity))

    def amonth() -> int:
        return rng.choice(ACTIVE_MONTHS)

    dob = _date(rng.randint(1965, 2003), rng.randint(1, 12), rng.randint(1, 28))
    reg = _dt(rng, ACTIVE_MONTHS[0], 1, 28)

    # --- WOK_Player_Profile: ACTIVE-snapshot + eind-status (target) ---
    eod_active = _dec(rng.uniform(0, 8) if (signal and self_excl) else rng.uniform(10, 500))
    eod_final = _dec(rng.uniform(0, 3) if (signal and self_excl) else rng.uniform(10, 500))
    rows["WOK_Player_Profile"].append([
        _dt(rng, ACTIVE_MONTHS[0], 1, 5), pk.next(), f"rec-{pk.n}", EXTRACTION_DATE, op, f"ds-{pid}",
        NULL, pid, reg, dob, _dt(rng, ACTIVE_MONTHS[-1], 1, 28), STATUS_ACTIVE, eod_active,
    ])
    final_status = STATUS_SELF_EXCL if self_excl else STATUS_ACTIVE
    # Multi-period: verdeel uitsluiters over de twee target-maanden (mei/juni) → echte holdout.
    # Single-period (legacy): alle uitsluiters in de laatste target-maand (juni).
    if self_excl:
        excl_month = rng.choice(TARGET_MONTHS) if multi_period else TARGET_MONTH
        final_month = excl_month
    else:
        final_month = ACTIVE_MONTHS[-1]
    rows["WOK_Player_Profile"].append([
        _dt(rng, final_month, 1, 5), pk.next(), f"rec-{pk.n}", EXTRACTION_DATE, op, f"ds-{pid}",
        NULL, pid, reg, dob, _dt(rng, final_month, 1, 28), final_status, eod_final,
    ])

    # --- WOK_Player_Account_Transaction ---
    tx_ids: List[str] = []
    for k in range(n_tx):
        ttype = rng.choices(TX_TYPES_W[0], weights=TX_TYPES_W[1])[0]
        tid = f"{pid}-t{k}"
        tx_ids.append(tid)
        tdt = _dt(rng, amonth())
        rows["WOK_Player_Account_Transaction"].append([
            tdt, pk.next(), f"rec-{pk.n}", EXTRACTION_DATE, op, f"ds-{pid}", NULL, pid, tid, tdt,
            _dec(rng.uniform(1, amount_scale)),
            rng.choice(DEPOSIT_INSTRUMENTS) if ttype == "DEPOSIT" else NULL,
            ttype, rng.choice(TX_STATUSES),
        ])

    # --- WOK_Bet (+ Parts + Transaction). Speler via Bet_Transaction. ---
    for b in range(n_bets):
        bet_pk = pk.next()
        bstart = _dt(rng, amonth())
        btype = rng.choice(BET_TYPES)
        rows["WOK_Bet"].append([
            _dt(rng, amonth()), bet_pk, f"rec-{bet_pk}", EXTRACTION_DATE, op, f"ds-{pid}", NULL,
            f"{pid}-b{b}", bstart, NULL, btype, NULL, _dec(rng.uniform(0, 2)),
            _dec(rng.uniform(1, amount_scale)), rng.choice(BET_STATUSES),
        ])
        n_parts = rng.randint(1, 3) if btype != "SINGLE" else 1
        for q in range(n_parts):
            home = rng.choice(DUTCH_CLUBS if rng.random() < 0.5 else FOREIGN_CLUBS)
            away = rng.choice(FOREIGN_CLUBS)
            event = f"{rng.choice(COMPETITIONS)}|{home} : {away}"
            rows["WOK_Bet_Parts"].append([
                _dt(rng, amonth()), pk.next(), bet_pk, f"{pid}-b{b}-p{q}", event,
                _dec(rng.uniform(1.2, 12.0)), rng.choice(SPORTS),
                str(rng.randint(0, 1)), str(rng.randint(0, 1)), _dt(rng, amonth()),
                "MATCH ODDS", away.split()[0], _dec(rng.uniform(1, amount_scale)), NULL,
            ])
        # vaak twee transacties per bet (stake bij placed + settled) → quirk
        tid = tx_ids[b % len(tx_ids)] if tx_ids else f"{pid}-t0"
        for _ in range(rng.choice([1, 2, 2])):
            rows["WOK_Bet_Transaction"].append([
                _dt_after(rng, bstart), pk.next(), bet_pk, tid, pid,
            ])

    # --- WOK_Game_Session (+ Session_Transaction). Speler via Session_Transaction. ---
    for s in range(n_sessions):
        sess_pk = pk.next()
        sstart = _dt(rng, amonth())
        rows["WOK_Game_Session"].append([
            _dt(rng, amonth()), sess_pk, f"rec-{sess_pk}", EXTRACTION_DATE, op, f"ds-{pid}", NULL,
            rng.choice(game_ids), f"{pid}-s{s}", sstart, _dt_after(rng, sstart),
            _dec(rng.uniform(0, 2)), str(rng.randint(1, 40)), str(rng.randint(0, 10)),
        ])
        for j in range(rng.randint(1, 3)):
            tid = tx_ids[(s + j) % len(tx_ids)] if tx_ids else f"{pid}-t0"
            rows["WOK_Game_Session_Transaction"].append([
                _dt_after(rng, sstart), pk.next(), sess_pk, tid, pid,
            ])

    # --- Limieten: parent WOK_Player_Limits + sub-tabellen (incl. Balance) ---
    limit_pk = pk.next()
    rows["WOK_Player_Limits"].append([
        _dt(rng, amonth(), 1, 20), limit_pk, f"rec-{limit_pk}", EXTRACTION_DATE, op,
        f"ds-{pid}", NULL, pid,
    ])
    # Participation is de PRIMAIRE bron voor f22/f23 (apart document in het organisatie-model).
    if rng.random() < 0.7:
        for _ in range(rng.randint(2, 3)):
            prq = _dt(rng, amonth(), 1, 20)
            rows["WOK_Player_Limits_Participation"].append([
                _dt(rng, amonth(), 1, 20), pk.next(), limit_pk, prq, _dt_after(rng, prq, 1440),
                _dec(float(rng.choice([50, 100, 200, 500, 1000]))), rng.choice(TIME_WINDOWS),
            ])
    for _ in range(rng.randint(1, 2)):
        drq = _dt(rng, amonth(), 1, 20)
        rows["WOK_Player_Limits_Deposit"].append([
            _dt(rng, amonth(), 1, 20), pk.next(), limit_pk, drq, _dt_after(rng, drq, 1440),
            _dec(float(rng.choice([50, 100, 200, 500, 1000]))), rng.choice(TIME_WINDOWS),
        ])
    if rng.random() < 0.6:
        brq = _dt(rng, amonth(), 1, 20)
        rows["WOK_Player_Limits_Balance"].append([
            _dt(rng, amonth(), 1, 20), pk.next(), limit_pk, brq, _dt_after(rng, brq, 1440),
            _dec(float(rng.choice([100, 250, 500, 1000]))), rng.choice(TIME_WINDOWS),
        ])
    if rng.random() < 0.5:
        grq = _dt(rng, amonth(), 1, 20)
        rows["WOK_Player_Limits_Game_Type"].append([
            _dt(rng, amonth(), 1, 20), pk.next(), limit_pk, grq, _dt_after(rng, grq, 1440), NULL,
            rng.choice(GAME_TYPE_LIMITS), rng.choice(TIME_WINDOWS),
        ])
    if rng.random() < 0.5:
        lrq = _dt(rng, amonth(), 1, 20)
        rows["WOK_Player_Limits_Login"].append([
            _dt(rng, amonth(), 1, 20), pk.next(), limit_pk, lrq, _dt_after(rng, lrq, 1440),
            str(rng.randint(30, 240)), rng.choice(TIME_WINDOWS),
        ])

    return rows


# -----------------------------------------------------------------------------
# Schrijven (quoted ; -CSV, exact als voorbeeld_11)
# -----------------------------------------------------------------------------
def _write_csv(path: Path, header: List[str], rows: List[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)


def maak_organisatie_fake(out_dir: str | Path, *, players: int = 100, operators: int = 3,
                  seed: int = 42, signal: bool = True, multi_period: bool = True) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    all_rows: Dict[str, List[list]] = {t: [] for t in COLUMNS}
    op_letters = [chr(ord("a") + i) for i in range(operators)]

    # spelers verdelen over operators
    for i in range(players):
        op = op_letters[i % operators]
        pk = _PK(op)
        # game-catalogus per operator één keer
        if i < operators:
            grows, game_ids = _game_catalog(rng, pk, op)
            all_rows["WOK_Game"].extend(grows)
            _OP_GAMES[op] = game_ids
        game_ids = _OP_GAMES[op]
        pid = f"{op}{i:04d}"
        prows = _player_rows(rng, pk, op, pid, game_ids, signal=signal, multi_period=multi_period)
        for t, rws in prows.items():
            all_rows[t].extend(rws)

    for t, header in COLUMNS.items():
        _write_csv(out / f"{t}.csv", header, all_rows[t])

    # uitsluiters per target-maand (kolom 10 = player_profile_modified, 11 = player_profile_status)
    excl_per_month: Dict[int, int] = {}
    for r in all_rows["WOK_Player_Profile"]:
        if r[11] == STATUS_SELF_EXCL:
            m = int(str(r[10])[5:7])
            excl_per_month[m] = excl_per_month.get(m, 0) + 1
    n_excl = sum(excl_per_month.values())
    print(f"✅ voorbeeld_fake geschreven naar: {out}")
    mode = f"multi-period (target-maanden {TARGET_MONTHS})" if multi_period else "single-period (alleen juni)"
    print(f"   spelers={players}  operators={op_letters}  signal={signal}  {mode}")
    print(f"   uitsluiters(rijen)={n_excl}  per maand={dict(sorted(excl_per_month.items()))}")
    print(f"   activiteit: {YEAR}-{ACTIVE_MONTHS[0]:02d}..{YEAR}-{ACTIVE_MONTHS[-1]:02d}  "
          f"targets: {', '.join(f'{YEAR}-{m:02d}' for m in (TARGET_MONTHS if multi_period else [TARGET_MONTH]))}")
    for t in COLUMNS:
        print(f"     {t}.csv: {len(all_rows[t])} rijen")
    return out


_OP_GAMES: Dict[str, List[str]] = {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genereer een fake organisatie-dataset (blueprint van voorbeeld_11).")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "voorbeeld_fake"))
    ap.add_argument("--players", type=int, default=100)
    ap.add_argument("--operators", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-signal", dest="signal", action="store_false", default=True,
                    help="Features onafhankelijk van het label (lekkage-canary).")
    ap.add_argument("--single-period", dest="multi_period", action="store_false", default=True,
                    help="Geen echte holdout: alle uitsluiters in één target-maand (juni). "
                         "Standaard is multi-period (mei + juni) voor een echte temporele holdout.")
    args = ap.parse_args(argv)
    maak_organisatie_fake(args.out, players=args.players, operators=args.operators,
                  seed=args.seed, signal=args.signal, multi_period=args.multi_period)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
