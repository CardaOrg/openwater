#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_logger.py  (organisatie-versie)
===========================

Geconsolideerde logging voor de organisatie — dwarsliggende hulpfunctie (geen data-stap).

In de hoofdrepo deden de drie runner-wrappers `clean_runner.py`, `label_runner.py` en
`parse_runner.py` **allemaal exact dezelfde** logging: ze startten het echte werk als een
subprocess, schreven de gecombineerde stdout/stderr live weg naar één getimestampt logbestand
(én naar de terminal), en logden na afloop de exitcode, wall time en piekgeheugen. Op een HPC-cluster
ving de SLURM `.out` dat normaal op; deze module brengt diezelfde logging samen in één plek,
zodat ook een lokale organisatie-run één terugleesbaar logbestand oplevert.

De logregels, de tee-loop en de footer zijn **ongewijzigd** overgenomen uit die runners; alleen
de bestandsnaam-fase (`clean` / `label_only` / `parse` / ...) is een parameter geworden.
"""

import os
import sys
import time
import resource
import subprocess
import socket
from pathlib import Path
from datetime import datetime


def log(msg):
    """Print een logregel met timestamp naar stdout (flush=True voor live logging)."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def detect_env():
    """
    Bepaal of we lokaal of op een HPC-cluster draaien.

    Retourneert:
        'hpc'      — als er een SLURM-job actief is (env-var SLURM_JOB_ID).
        'local'    — in alle andere gevallen.
    """
    if os.environ.get("SLURM_JOB_ID"):
        return "hpc"
    return "local"


def make_logfile(logdir, scenario, phase, env=None):
    """
    Bouw het logbestand-pad zoals de originele runners dat deden:
      - lokaal  : <scenario>_<phase>_latest.log   (overschrijvend, makkelijk terugkijken)
      - hpc     : <scenario>_<phase>_<timestamp>.log

    `phase` generaliseert de fase die in het origineel vastlag per runner
    (clean_runner → 'clean', label_runner → 'label_only', parse_runner → 'parse').
    """
    env = env or detect_env()
    Path(logdir).mkdir(parents=True, exist_ok=True)
    if env == "local":
        return Path(logdir) / f"{scenario.lower()}_{phase}_latest.log"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(logdir) / f"{scenario.lower()}_{phase}_{stamp}.log"


def run_and_log(cmd, logfile, env=None):
    """
    Draai `cmd` (lijst) als subprocess en tee de gecombineerde stdout/stderr live naar zowel
    de terminal als `logfile`. Na afloop: exitcode, wall time en piekgeheugen (van het kind).
    Geeft de exitcode terug.

    Dit is exact het logging-gedrag van clean_runner.py / label_runner.py / parse_runner.py.
    """
    logfile = Path(logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)

    env_vars = (env or os.environ).copy()
    env_vars["PYTHONUNBUFFERED"] = "1"
    env_vars["PYTHONIOENCODING"] = "utf-8"

    log(f"Launching: {' '.join(str(c) for c in cmd)}")
    log(f"Logs → {logfile}")
    t0 = time.perf_counter()

    with open(logfile, "w", buffering=1, encoding="utf-8") as lf:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=env_vars, text=True, encoding="utf-8", bufsize=1)
        for line in proc.stdout:
            lf.write(line)
            print(line, end="")
        ret = proc.wait()

    dt = time.perf_counter() - t0
    rss_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    log(f"Exit code: {ret}")
    log(f"Wall time: {dt:,.2f} s")
    log(f"Peak RSS (child): {rss_mb:,.2f} MB")
    log(f"Log file saved → {logfile}")
    return ret
