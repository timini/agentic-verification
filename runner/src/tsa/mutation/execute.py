"""Patch-replay mutant execution: one mutant at a time per worker, each in its own copy.

Each worker process owns a disposable copy of the project. For every mutant it writes the
mutated file, runs the selected tests with the activation check enabled, then restores the
original file. Statuses follow ``model.STATUSES``. A kill requires a test that passed in
every baseline run to fail or error under the mutant.
"""

import os
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from ..project import Project
from ..pytest_run import EXIT_OK, EXIT_TESTS_FAILED, run_pytest
from . import model
from .model import Mutant


@dataclass
class MutantResult:
    mutant_id: str
    status: str
    scope: list[str]  # tests run against the mutant
    killers: list[str] = field(default_factory=list)
    activated: bool | None = None
    wall_s: float = 0.0
    cpu_s: float = 0.0
    timeout_s: float | None = None
    returncode: int | None = None
    message: str | None = None

    def record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Task:
    mutant: Mutant
    select: tuple[str, ...]
    stable_pass: frozenset[str]  # subset of select that passed in every baseline run
    timeout_s: float


_ws: Project | None = None
_ws_dir: str | None = None


def _init_worker(project: Project, parent: str) -> None:
    global _ws, _ws_dir
    _ws_dir = tempfile.mkdtemp(prefix=f"w{os.getpid()}-", dir=parent)
    _ws = project.copy_to(Path(_ws_dir) / "proj")


def _run_task(task: Task) -> MutantResult:
    assert _ws is not None
    return execute_one(_ws, task)


def execute_one(ws: Project, task: Task) -> MutantResult:
    m = task.mutant
    res = MutantResult(m.id, model.INVALID, list(task.select), timeout_s=task.timeout_s)
    try:
        compile(m.mutated_source, m.file, "exec")
    except (SyntaxError, ValueError) as exc:
        res.message = f"compile: {exc}"[:300]
        return res
    if not task.select:
        res.status = model.UNCOVERED
        return res
    target = ws.root / m.file
    original = target.read_text()
    try:
        target.write_text(m.mutated_source)
        run = run_pytest(
            ws, select=list(task.select), timeout_s=task.timeout_s,
            activation=(target, [m.start_line]),
        )
    finally:
        target.write_text(original)
        shutil.rmtree(ws.root / ".hypothesis", ignore_errors=True)
    res.wall_s, res.cpu_s, res.returncode = run.wall_s, run.cpu_s, run.returncode
    res.activated = None if run.activation_hits is None else bool(run.activation_hits)
    killers = sorted(run.failed_ids() & task.stable_pass)
    if run.timed_out:
        res.status = model.TIMEOUT
    elif run.collection_error:
        res.status = model.INVALID
        res.message = _last_error(run.output_tail)
    elif killers:
        res.status = model.KILLED
        res.killers = killers
    elif run.returncode not in (EXIT_OK, EXIT_TESTS_FAILED):
        res.status = model.INFRA
        res.message = _last_error(run.output_tail)
    elif res.activated is None:
        res.status = model.UNKNOWN_ACTIVATION
    elif not res.activated:
        res.status = model.NOT_ACTIVATED
    else:
        res.status = model.SURVIVED
    return res


def _last_error(tail: str) -> str:
    lines = [ln for ln in tail.splitlines() if "Error" in ln or "error" in ln]
    return (lines[-1] if lines else tail[-300:])[:300]


class Executor:
    """Run tasks over a pool of worker processes, each with its own project copy."""

    def __init__(self, project: Project, workers: int, workdir: Path | None = None):
        self.project = project
        self.workers = workers
        self._tmp = tempfile.mkdtemp(prefix="tsa-ws-", dir=workdir)
        self._pool = ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker, initargs=(project, self._tmp),
        )

    def run(
        self, tasks: Iterable[Task], on_result: Callable[[Task, MutantResult], None],
        deadline: float | None = None,
    ) -> int:
        """Submit tasks in order, keeping at most ``2 * workers`` in flight.

        Stops submitting once ``deadline`` (time.monotonic) passes; in-flight tasks finish.
        Returns the number of tasks completed.
        """
        from concurrent.futures import FIRST_COMPLETED, wait

        it = iter(tasks)
        in_flight = {}
        done_count = 0
        exhausted = False
        while True:
            while not exhausted and len(in_flight) < 2 * self.workers:
                if deadline is not None and time.monotonic() >= deadline:
                    exhausted = True
                    break
                try:
                    t = next(it)
                except StopIteration:
                    exhausted = True
                    break
                in_flight[self._pool.submit(_run_task, t)] = t
            if not in_flight:
                return done_count
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for f in done:
                t = in_flight.pop(f)
                on_result(t, f.result())
                done_count += 1

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=True)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
