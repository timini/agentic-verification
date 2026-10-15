"""Shared preparation: baseline scope, per-test coverage and the mutant populations."""

import gzip
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from harness import corpus
from harness.records import RAW, RUN_ID, read_all
from tsa.evidence import coverage_matrix
from tsa.evidence.coverage_matrix import CoverageMatrix, Line
from tsa.mutation import classical, deletion
from tsa.mutation.execute import Task
from tsa.mutation.model import Mutant

WORKERS = 8
TIMEOUT_FACTOR = 10
TIMEOUT_EXTRA_S = 10


@dataclass
class Prepared:
    entry: corpus.Entry
    stable: frozenset[str]
    durations: dict[str, float]
    startup_s: float
    cov: CoverageMatrix
    covering: dict[Line, set[str]]
    mutants: list[Mutant]

    def select_for(self, m: Mutant) -> tuple[str, ...]:
        tests: set[str] = set()
        for ln in m.lines:
            tests |= self.covering.get((m.file, ln), set())
        return tuple(sorted(tests & self.stable))

    def task(self, m: Mutant, select: tuple[str, ...] | None = None) -> Task:
        sel = self.select_for(m) if select is None else tuple(sorted(set(select) & self.stable))
        expected = sum(self.durations.get(t, 0.0) for t in sel) + self.startup_s
        return Task(m, sel, frozenset(sel), TIMEOUT_FACTOR * expected + TIMEOUT_EXTRA_S)


def baseline(e: corpus.Entry) -> tuple[frozenset[str], dict[str, float], float]:
    recs = read_all("e0_baseline", e.name)
    summary = [r for r in recs if r["kind"] == "baseline_summary"][-1]
    runs = [r for r in recs if r["kind"] == "baseline_run" and r["run_id"] == summary["run_id"]]
    durations: dict[str, list[float]] = {}
    for r in runs:
        for t, d in r["durations"].items():
            durations.setdefault(t, []).append(d)
    med = {t: statistics.median(v) for t, v in durations.items()}
    overhead = statistics.median(r["wall_s"] - sum(r["durations"].values()) for r in runs)
    return frozenset(summary["stable_pass"]), med, max(overhead, 2.0)


def coverage(e: corpus.Entry) -> CoverageMatrix:
    """Per-test coverage, measured once per project and stored as raw data."""
    d = RAW / e.name / "coverage"
    existing = sorted(d.glob("*.json.gz"))
    if existing:
        data = json.loads(gzip.decompress(existing[-1].read_bytes()))
    else:
        cov = coverage_matrix.measure(e.project(), timeout_s=1800)
        data = {
            "project": e.name, "project_sha": e.sha, "run_id": RUN_ID,
            "wall_s": cov.run.wall_s if cov.run else None,
            "run": {t: sorted(map(list, v)) for t, v in cov.run_lines.items()},
            "setup": {t: sorted(map(list, v)) for t, v in cov.setup_lines.items()},
            "unattributed": sorted(map(list, cov.unattributed)),
        }
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{RUN_ID}.json.gz").write_bytes(gzip.compress(json.dumps(data).encode()))
    conv = lambda v: {(f, int(n)) for f, n in v}
    return CoverageMatrix(
        {t: conv(v) for t, v in data["run"].items()},
        {t: conv(v) for t, v in data["setup"].items()},
        conv(data["unattributed"]),
    )


def mutants(e: corpus.Entry) -> list[Mutant]:
    out: list[Mutant] = []
    root = e.dir
    for f in e.project().source_files():
        rel = str(f.relative_to(root))
        out.extend(classical.generate(root, rel))
        out.extend(deletion.generate(root, rel))
    return out


def prepare(e: corpus.Entry) -> Prepared:
    stable, durations, startup = baseline(e)
    cov = coverage(e)
    return Prepared(e, stable, durations, startup, cov, cov.tests_covering(), mutants(e))


def write_result(rec, label: str, task: Task, result, **extra) -> None:
    """One mutant execution, with the exact patch so it can be replayed without regeneration."""
    original = (rec.entry.dir / task.mutant.file).read_text()
    rec.write("mutant_result", label=label, mutant=task.mutant.record(),
              patch=task.mutant.patch(original), result=result.record(), **extra)
