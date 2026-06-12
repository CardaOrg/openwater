#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_with_log.py  (organisatie-versie)
=============================

Generieke logging-wrapper rond elke organisatie-runner. Dit is het pure-Python equivalent van wat
`clean_runner.py` / `label_runner.py` / `parse_runner.py` in de hoofdrepo deden: een dunne
launcher die het echte werk als subprocess draait en de volledige output naar één getimestampt
logbestand tee't (plus exitcode / wall time / piekgeheugen).

Waar de originelen elk aan één fase vastzaten (clean / label_only / parse), is dit generiek:
je geeft een `--phase` mee en daarachter het commando dat gedraaid moet worden.

Gebruik
-------
    # Wrap de cleaning-runner en log naar logs/<scenario>_clean_<stamp>.log :
    python run_with_log.py --logdir logs --scenario Scenario_1 --phase clean -- \
        python ../1_cleaning/run_cleaning.py --input-dir ../0_dummy_data --clean-out-dir out

    # Wrap de optuna-runner:
    python run_with_log.py --logdir logs --phase optuna -- \
        python ../7_modelling/run_optuna.py --config cfg.yaml --dataset-path ds --out-dir run

Alles na `--` is het commando dat letterlijk wordt uitgevoerd. De exitcode van dat commando
wordt doorgegeven als exitcode van deze wrapper.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_logger import make_logfile, run_and_log, log, detect_env  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Draai een commando en log de volledige output naar één logbestand.",
    )
    p.add_argument("--logdir", default="logs", help="Map voor het logbestand (default: logs/).")
    p.add_argument("--scenario", default="run", help="Scenario-label in de bestandsnaam (default: run).")
    p.add_argument("--phase", default="run", help="Fase-label in de bestandsnaam (clean/label_only/parse/...).")
    p.add_argument("--logfile", default=None, help="Expliciet logbestand-pad (overschrijft --logdir/--scenario/--phase).")
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="Het uit te voeren commando, na '--'.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    cmd = args.command
    # argparse.REMAINDER houdt een leidende '--' vast; strip die.
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        sys.exit("❌ Geen commando opgegeven. Gebruik: run_with_log.py [opties] -- <commando...>")

    env = detect_env()
    log(f"Detected environment: {env}")

    if args.logfile:
        logfile = Path(args.logfile)
    else:
        logfile = make_logfile(args.logdir, args.scenario, args.phase, env=env)

    ret = run_and_log(cmd, logfile)
    return ret


if __name__ == "__main__":
    raise SystemExit(main())
