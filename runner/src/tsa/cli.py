"""Command line: ``tsa quick``, ``tsa deep`` and ``tsa replay``."""

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
    ap = argparse.ArgumentParser(prog="tsa", description="Test Suite Auditor runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, minutes in (("quick", 5), ("deep", 30)):
        p = sub.add_parser(name)
        p.add_argument("path", nargs="?", default=".")
        p.add_argument("--budget-minutes", type=float, default=minutes)
        p.add_argument("--max-mutants", type=int, default=None)
        p.add_argument("--out", default=None, help="output root (default: <path>/.test-suite-audit)")
    r = sub.add_parser("replay", help="re-run one recorded mutant in a disposable copy")
    r.add_argument("--run", required=True, help="audit output directory")
    r.add_argument("--mutant", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "replay":
        return _replay(Path(args.run), args.mutant)

    cfg = config.load(Path(args.path))
    out_root = Path(args.out) if args.out else cfg.project.root / ".test-suite-audit"
    st = run_audit(cfg, args.cmd, args.budget_minutes, args.max_mutants, out_root,
                   progress=lambda m: print(m, file=sys.stderr, flush=True))
    jp, mp = write(st)
    print(json.dumps({"status": st.status, "report_md": str(mp), "report_json": str(jp),
                      "findings": len(st.findings)}))
    return 0


def _replay(run_dir: Path, mutant_id: str) -> int:
    report = json.loads((run_dir / "report.json").read_text())
    rec = next((r for r in report["mutation"].get("results", []) if r["mutant_id"] == mutant_id), None)
    if rec is None:
        print(f"mutant {mutant_id} not in {run_dir}/report.json", file=sys.stderr)
        return 2
    c = report["run"]["config"]
    root = Path(c["root"])
    proj = Project(root=root, python=Path(c["python"]), source=tuple(c["source"]), tests=tuple(c["tests"]),
                   pytest_args=tuple(c["pytest_args"]))
    patch = (run_dir / "mutants" / f"{mutant_id}.patch").read_text()
    with tempfile.TemporaryDirectory(prefix="tsa-replay-") as tmp:
        ws = proj.copy_to(Path(tmp) / "proj")
        ap = subprocess.run(["patch", "-p1", "--quiet"], input=patch, text=True, cwd=ws.root)
        if ap.returncode != 0:
            print("patch did not apply: source changed since the audit", file=sys.stderr)
            return 2
        print(patch)
        run = run_pytest(ws, select=rec["scope"] or None, activation=(ws.root / rec["file"], [rec["start_line"]]))
        failed = sorted(run.failed_ids())
        print(json.dumps({"recorded_status": rec["status"], "recorded_killers": rec["killers"],
                          "failed_now": failed, "activated_now": bool(run.activation_hits)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
