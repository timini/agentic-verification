"""Run pytest in a target project and read back per-test outcomes recorded by our plugin."""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import procs
from .project import Project

# pytest exit codes: https://docs.pytest.org/en/stable/reference/exit-codes.html
EXIT_OK, EXIT_TESTS_FAILED, EXIT_INTERRUPTED, EXIT_INTERNAL, EXIT_USAGE, EXIT_NO_TESTS = range(6)


@dataclass
class TestOutcome:
    nodeid: str
    outcome: str  # passed | failed | error | skipped | xfailed | xpassed
    setup_s: float = 0.0
    call_s: float = 0.0
    teardown_s: float = 0.0
    message: str | None = None

    @property
    def duration_s(self) -> float:
        return self.setup_s + self.call_s + self.teardown_s


@dataclass
class PytestRun:
    returncode: int | None
    timed_out: bool
    wall_s: float
    cpu_s: float
    outcomes: dict[str, TestOutcome]
    collected: list[dict] | None
    activation_hits: list[int] | None  # None = not requested or monitoring unavailable
    output_tail: str
    collection_error: bool = False
    extra: dict = field(default_factory=dict)

    def failed_ids(self) -> set[str]:
        return {n for n, o in self.outcomes.items() if o.outcome in ("failed", "error")}


def _fold(records: list[dict]) -> dict[str, TestOutcome]:
    """Combine setup/call/teardown phase reports into one outcome per test."""
    out: dict[str, TestOutcome] = {}
    for r in records:
        t = out.setdefault(r["nodeid"], TestOutcome(r["nodeid"], "passed"))
        setattr(t, f"{r['when']}_s", r["duration"])
        if r["outcome"] == "failed":
            if r["when"] == "call":
                t.outcome = "xpassed" if r.get("xfail") else "failed"
            elif t.outcome == "passed":
                t.outcome = "error"
            t.message = t.message or r.get("message")
        elif r["outcome"] == "skipped" and t.outcome == "passed":
            t.outcome = "xfailed" if r.get("xfail") else "skipped"
    return out


def run_pytest(
    project: Project,
    *,
    select: list[str] | None = None,
    extra_args: tuple[str, ...] = (),
    timeout_s: float | None = None,
    activation: tuple[Path, list[int]] | None = None,
    collect: bool = False,
    collect_only: bool = False,
    env: dict[str, str] | None = None,
) -> PytestRun:
    with tempfile.TemporaryDirectory(prefix="tsa-run-") as tmp:
        tmpd = Path(tmp)
        run_env = project.base_env()
        run_env["TSA_RESULTS"] = str(tmpd / "results.jsonl")
        if env:
            run_env.update(env)
        targets: list[str] = list(project.tests)
        if select is not None:
            (tmpd / "select.txt").write_text("\n".join(select) + "\n")
            run_env["TSA_SELECT"] = str(tmpd / "select.txt")
            # Collect only the files holding selected tests; collection of the whole suite
            # would dominate the cost of single-mutant runs.
            files = sorted({nid.split("::", 1)[0] for nid in select})
            targets = files or list(project.tests)
        if collect or collect_only:
            run_env["TSA_COLLECT"] = str(tmpd / "collect.jsonl")
        if activation is not None:
            path, lines = activation
            run_env["TSA_ACT_FILE"] = str(path)
            run_env["TSA_ACT_LINES"] = ",".join(str(x) for x in sorted(set(lines)))
            run_env["TSA_ACT_OUT"] = str(tmpd / "activation.json")
        cmd = [
            str(project.python), "-m", "pytest", "-p", "tsa_pytest_plugin",
            "-q", "--no-header", "-o", "console_output_style=classic",
            *project.pytest_args, *extra_args, *targets,
        ]
        if collect_only:
            cmd.append("--collect-only")
        res = procs.run(cmd, str(project.root), run_env, timeout_s)

        records = _read_jsonl(tmpd / "results.jsonl")
        collected = _read_jsonl(tmpd / "collect.jsonl") if (collect or collect_only) else None
        hits = None
        act_file = tmpd / "activation.json"
        if activation is not None and act_file.exists():
            hits = json.loads(act_file.read_text())["hits"]
        collection_error = res.returncode in (EXIT_INTERRUPTED, EXIT_USAGE) or (
            "errors during collection" in res.output_tail or "ERROR collecting" in res.output_tail
        )
        return PytestRun(
            returncode=res.returncode,
            timed_out=res.timed_out,
            wall_s=res.wall_s,
            cpu_s=res.cpu_s,
            outcomes=_fold(records),
            collected=collected,
            activation_hits=hits,
            output_tail=res.output_tail,
            collection_error=collection_error,
        )


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
