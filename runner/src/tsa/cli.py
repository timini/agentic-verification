"""Command line: ``quick``, ``deep``, ``verify``, ``prune-check`` and ``replay``.

Installed as ``agentic-verification``, with ``tsa`` kept as an alias for older instructions.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config
from .audit import run_audit
from .project import Project
from .pytest_run import run_pytest
from .report.write import write


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentic-verification",
                                 description="Measure whether a pytest suite would catch broken code")
    sub = ap.add_subparsers(dest="cmd", required=True)
    helps = {"quick": "baseline, timings and coverage of the whole suite (no mutants)",
             "deep": "full suite audit: order dependence, mutants, weak tests, removal candidates",
             "verify": "check that the tests catch mutants of the lines changed since --base",
             "prune-check": "check that removing a set of tests loses no mutant kill or covered line"}
    for name, minutes in (("quick", 5), ("deep", 30), ("verify", 10), ("prune-check", 20)):
        p = sub.add_parser(name, help=helps[name])
        p.add_argument("path", nargs="?", default=".")
        p.add_argument("--budget-minutes", type=float, default=minutes)
        p.add_argument("--max-mutants", type=int, default=None)
        p.add_argument("--out", default=None, help="output root (default: <path>/.test-suite-audit)")
        p.add_argument("--python", default=None, help="interpreter of the project's environment (overrides config)")
        if name == "verify":
            p.add_argument("--base", default="HEAD", help="git revision to compare with (default: HEAD, "
                           "i.e. uncommitted changes); use a branch such as main for a whole branch")
            p.add_argument("--fail-on-gaps", action="store_true",
                           help="exit 1 if the verdict is gaps and 3 if it is incomplete (for hooks and CI)")
        if name == "prune-check":
            p.add_argument("--tests", nargs="*", default=[], help="node IDs of the tests to remove")
            p.add_argument("--tests-file", default=None, help="file with one node ID per line")
            p.add_argument("--from-run", default=None,
                           help="deep audit directory; its mutants are excluded, so the check uses fresh ones")
    r = sub.add_parser("replay", help="re-run one recorded mutant in a disposable copy")
    r.add_argument("--run", required=True, help="audit output directory")
    r.add_argument("--mutant", required=True)
    r.add_argument("--all", action="store_true",
                   help="run the whole suite, not only the tests recorded for this mutant; use it to check "
                        "that a newly written test kills the mutant")
    args = ap.parse_args(argv)

    if args.cmd == "replay":
        return _replay(Path(args.run), args.mutant, args.all)

    cfg = config.load(Path(args.path))
    if args.python:
        from dataclasses import replace
        cfg.project = replace(cfg.project, python=Path(args.python))
        cfg.discovered["python"] = "--python"
    out_root = Path(args.out) if args.out else cfg.project.root / ".test-suite-audit"
    extra: dict = {}
    if args.cmd == "verify":
        extra["base"] = args.base
    if args.cmd == "prune-check":
        tests = list(args.tests)
        if args.tests_file:
            tests += [ln.strip() for ln in Path(args.tests_file).read_text().splitlines() if ln.strip()]
        if not tests:
            print("prune-check needs --tests or --tests-file", file=sys.stderr)
            return 2
        extra["removed"] = tests
        if args.from_run:
            rep = json.loads((Path(args.from_run) / "report.json").read_text())
            extra["exclude_ids"] = frozenset(r["mutant_id"] for r in rep["mutation"].get("results", []))
    st = run_audit(cfg, args.cmd, args.budget_minutes, args.max_mutants, out_root,
                   progress=lambda m: print(m, file=sys.stderr, flush=True), **extra)
    jp, mp = write(st)
    summary = {"status": st.status, "report_md": str(mp), "report_json": str(jp), "findings": len(st.findings)}
    if st.change:
        summary["verdict"] = st.change.get("verdict")
    if st.prune:
        summary["verdict"] = st.prune.get("verdict")
    print(json.dumps(summary))
    if args.cmd == "verify" and args.fail_on_gaps:
        return {"gaps": 1, "incomplete": 3}.get(summary["verdict"], 0)
    return 0


def _replay(run_dir: Path, mutant_id: str, all_tests: bool = False) -> int:
    report = json.loads((run_dir / "report.json").read_text())
    rec = next((r for r in report["mutation"].get("results", []) if r["mutant_id"] == mutant_id), None)
    if rec is None:
        print(f"mutant {mutant_id} not in {run_dir}/report.json", file=sys.stderr)
        return 2
    c = report["run"]["config"]
    root = Path(c["root"])
    proj = Project(root=root, python=Path(c["python"]), source=tuple(c["source"]), tests=tuple(c["tests"]),
                   pytest_args=tuple(c["pytest_args"]))
    # Tests that fail without the mutant are not kills; run the same selection on the original first.
    select = None if all_tests else (rec["scope"] or None)
    with tempfile.TemporaryDirectory(prefix="tsa-replay-") as tmp:
        ws = proj.copy_to(Path(tmp) / "proj")
        failing_before = run_pytest(ws, select=select).failed_ids()
    patch = (run_dir / "mutants" / f"{mutant_id}.patch").read_text()
    with tempfile.TemporaryDirectory(prefix="tsa-replay-") as tmp:
        ws = proj.copy_to(Path(tmp) / "proj")
        ap = subprocess.run(["patch", "-p1", "--quiet"], input=patch, text=True, cwd=ws.root)
        if ap.returncode != 0:
            print("patch did not apply: source changed since the audit", file=sys.stderr)
            return 2
        print(patch)
        run = run_pytest(ws, select=select, activation=(ws.root / rec["file"], [rec["start_line"]]))
        killers = sorted(run.failed_ids() - failing_before)
        print(json.dumps({"recorded_status": rec["status"], "recorded_killers": rec["killers"],
                          "scope": "whole suite" if select is None else f"{len(select)} recorded tests",
                          "killed_now": bool(killers), "killers_now": killers,
                          "failing_without_mutant": sorted(failing_before),
                          "activated_now": bool(run.activation_hits)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
