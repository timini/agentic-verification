"""Per-test line coverage from coverage.py dynamic contexts (pytest-cov ``--cov-context=test``)."""

import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from coverage import CoverageData

from ..project import Project
from ..pytest_run import PytestRun, run_pytest

Line = tuple[str, int]  # (path relative to project root, line number)


@dataclass
class CoverageMatrix:
    run_lines: dict[str, set[Line]]  # test id -> lines executed in its "run" phase
    setup_lines: dict[str, set[Line]] = field(default_factory=dict)  # setup + teardown phases
    unattributed: set[Line] = field(default_factory=set)  # import time, session fixtures, etc.
    run: PytestRun | None = None

    def tests_covering(self) -> dict[Line, set[str]]:
        idx: dict[Line, set[str]] = defaultdict(set)
        for t, lines in self.run_lines.items():
            for ln in lines:
                idx[ln].add(t)
        return idx

    def any_covered(self) -> set[Line]:
        out = set(self.unattributed)
        for d in (self.run_lines, self.setup_lines):
            for lines in d.values():
                out |= lines
        return out


def measure(project: Project, timeout_s: float | None = None, select: list[str] | None = None) -> CoverageMatrix:
    with tempfile.TemporaryDirectory(prefix="tsa-cov-") as tmp:
        data_file = Path(tmp) / ".coverage"
        args = [f"--cov={(project.root / s)}" for s in project.source]
        args += ["--cov-context=test", "--cov-report=", "-p", "no:randomly"]
        run = run_pytest(
            project, select=select, extra_args=tuple(args), timeout_s=timeout_s,
            env={"COVERAGE_FILE": str(data_file)},
        )
        if not data_file.exists():
            raise RuntimeError(f"coverage produced no data file:\n{run.output_tail}")
        matrix = read(data_file, project.root)
        matrix.run = run
        return matrix


def read(data_file: Path, root: Path) -> CoverageMatrix:
    data = CoverageData(basename=str(data_file))
    data.read()
    run_lines: dict[str, set[Line]] = defaultdict(set)
    setup_lines: dict[str, set[Line]] = defaultdict(set)
    unattributed: set[Line] = set()
    root_real = root.resolve()
    for fname in data.measured_files():
        try:
            rel = str(Path(fname).resolve().relative_to(root_real))
        except ValueError:
            continue
        for lineno, contexts in (data.contexts_by_lineno(fname) or {}).items():
            for ctx in contexts:
                if not ctx:
                    unattributed.add((rel, lineno))
                    continue
                test, _, phase = ctx.rpartition("|")
                if phase == "run":
                    run_lines[test].add((rel, lineno))
                else:
                    setup_lines[test].add((rel, lineno))
    return CoverageMatrix(dict(run_lines), dict(setup_lines), unattributed)
