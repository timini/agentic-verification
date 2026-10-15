"""Subprocess execution with timeouts, process-group termination and bounded output capture."""

import os
import resource
import signal
import subprocess
import time
from dataclasses import dataclass

OUTPUT_TAIL_BYTES = 8000


@dataclass
class ProcResult:
    returncode: int | None  # None when killed for timeout
    timed_out: bool
    wall_s: float
    cpu_s: float  # user+sys CPU of the child (and its waited-for descendants)
    output_tail: str


def run(cmd: list[str], cwd: str, env: dict[str, str], timeout_s: float | None) -> ProcResult:
    """Run ``cmd`` in its own process group; on timeout the whole group is killed."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(proc)
        out, _ = proc.communicate()
    wall = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    # RUSAGE_CHILDREN is process-wide, so concurrent runs from threads blur this figure.
    # Callers that need exact per-run CPU must run one child at a time per process.
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    text = out.decode("utf-8", "replace")[-OUTPUT_TAIL_BYTES:]
    return ProcResult(None if timed_out else proc.returncode, timed_out, wall, cpu, text)


def kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
