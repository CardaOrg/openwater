#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests voor de organisatie logging-hulp (_logging/; organisatie-stap 9).

Draaien:
    pytest _organisatie_code/99_testing/test_logging.py -v
    python _organisatie_code/99_testing/test_logging.py
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

# --- Maak de logging-module importeerbaar (_logging/) ---
HERE = Path(__file__).resolve().parent
LOG_DIR = (HERE.parent / "_logging").resolve()
if str(LOG_DIR) not in sys.path:
    sys.path.insert(0, str(LOG_DIR))

from run_logger import make_logfile, run_and_log  # noqa: E402
import run_with_log  # noqa: E402


def test_run_and_log_writes_child_output_to_logfile():
    """De gecombineerde stdout/stderr van het subprocess belandt in het logbestand."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
    try:
        logfile = tmp / "out.log"
        cmd = [sys.executable, "-c",
               "import sys; print('HELLO_STDOUT'); print('HELLO_STDERR', file=sys.stderr)"]
        ret = run_and_log(cmd, logfile)
        assert ret == 0
        content = logfile.read_text()
        assert "HELLO_STDOUT" in content
        assert "HELLO_STDERR" in content  # stderr is samengevoegd met stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_and_log_propagates_exit_code():
    """De exitcode van het subprocess wordt teruggegeven."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
    try:
        ret = run_and_log([sys.executable, "-c", "import sys; sys.exit(3)"], tmp / "x.log")
        assert ret == 3
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_footer_printed_to_stdout(capsys):
    """De footer (Exit code / Wall time / Peak RSS / Log file saved) gaat naar stdout."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
    try:
        run_and_log([sys.executable, "-c", "print('x')"], tmp / "y.log")
        out = capsys.readouterr().out
        assert "Exit code: 0" in out
        assert "Wall time:" in out
        assert "Peak RSS (child):" in out
        assert "Log file saved" in out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_make_logfile_naming():
    """Lokaal → *_latest.log; snellius → *_<timestamp>.log (zoals de originele runners)."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
    try:
        local = make_logfile(tmp, "Scenario_1", "clean", env="local")
        assert local.name == "scenario_1_clean_latest.log"

        snel = make_logfile(tmp, "Scenario_1", "parse", env="snellius")
        assert re.match(r"^scenario_1_parse_\d{8}_\d{6}\.log$", snel.name), snel.name
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_with_log_wrapper_end_to_end():
    """run_with_log.main wrapt een commando, maakt een logbestand en geeft de exitcode door."""
    tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
    try:
        ret = run_with_log.main([
            "--logdir", str(tmp / "logs"), "--scenario", "T", "--phase", "demo",
            "--", sys.executable, "-c", "print('WRAPPED_OK')",
        ])
        assert ret == 0
        logs = list((tmp / "logs").glob("*.log"))
        assert len(logs) == 1
        assert "WRAPPED_OK" in logs[0].read_text()
        assert logs[0].name == "t_demo_latest.log"  # lokaal → latest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Als script draaien (zonder pytest)
# ---------------------------------------------------------------------------
def _run_all():
    import io
    import contextlib

    simple = [
        test_run_and_log_writes_child_output_to_logfile,
        test_run_and_log_propagates_exit_code,
        test_make_logfile_naming,
        test_run_with_log_wrapper_end_to_end,
    ]
    failures = 0
    for t in simple:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")

    # test_footer_printed_to_stdout heeft de capsys-fixture nodig → mini-emulatie.
    try:
        tmp = Path(tempfile.mkdtemp(prefix="organisatie_log_"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_and_log([sys.executable, "-c", "print('x')"], tmp / "y.log")
        out = buf.getvalue()
        assert "Exit code: 0" in out and "Peak RSS (child):" in out
        shutil.rmtree(tmp, ignore_errors=True)
        print("PASS  test_footer_printed_to_stdout")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"FAIL  test_footer_printed_to_stdout: {e}")

    total = len(simple) + 1
    print(f"\n{total - failures}/{total} tests geslaagd.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
