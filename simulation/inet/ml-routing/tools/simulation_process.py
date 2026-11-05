"""Bounded process runner for finite OMNeT++ batch simulations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import signal
import subprocess
import time
from typing import Sequence


@dataclass
class SimulationProcessResult:
    returncode: int
    stdout: str
    stderr: str
    started_at_utc: str
    ended_at_utc: str
    elapsed_seconds: float
    timed_out: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _signal_process_tree(process: subprocess.Popen, sig: int) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        if sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()


def _kill_process_tree(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()


def run_finite_simulation(command: Sequence[str], cwd: str | os.PathLike,
                          timeout_seconds: float, terminate_grace_seconds: float = 5.0
                          ) -> SimulationProcessResult:
    if timeout_seconds <= 0 or terminate_grace_seconds < 0:
        raise ValueError("timeout must be positive and termination grace must be nonnegative")

    started_at = datetime.now(timezone.utc)
    monotonic_start = time.monotonic()
    process = subprocess.Popen(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _signal_process_tree(process, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=terminate_grace_seconds)
        except subprocess.TimeoutExpired:
            _kill_process_tree(process)
            stdout, stderr = process.communicate()

    ended_at = datetime.now(timezone.utc)
    return SimulationProcessResult(
        returncode=process.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
        started_at_utc=started_at.isoformat(),
        ended_at_utc=ended_at.isoformat(),
        elapsed_seconds=time.monotonic() - monotonic_start,
        timed_out=timed_out,
    )


def launch_interactive_simulation(command: Sequence[str], cwd: str | os.PathLike,
                                  log_path: str | os.PathLike) -> int:
    """Start Qtenv without making the batch runner wait for its GUI window."""
    with open(log_path, "w") as log:
        process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
    return process.pid
