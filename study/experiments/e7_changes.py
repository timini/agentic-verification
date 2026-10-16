"""H7: do real changes leave changed lines unchecked? ``verify`` on recent upstream commits.

Each change commit from data/bench2/commits.json is rebuilt as a fresh repository whose HEAD is
the parent and whose working tree is the commit (source and tests), then verified against HEAD.
"""

import json
import shutil
import sys

from bench2.common import ROOT, repo, build_repo, commits, entry, write_config
from harness.records import Recorder
from tsa import config
from tsa.audit import run_audit
from tsa.report.write import write

BUDGET_MIN = 15


def main() -> None:
    only = sys.argv[1:] or None
    for name, sel in commits().items():
        if only and name not in only:
            continue
        e = entry(name)
        rec = Recorder("e7_changes", e)
        for c in sel["change"]:
            ws = ROOT / "e7" / name / c["commit"][:12]
            if ws.exists():
                shutil.rmtree(ws)
            changed = sorted(set(c["source_files"]) | set(c["test_files"]) | set(_all_changed(e, c)))
            build_repo(e, ws, c["parent"], c["commit"], changed)
            write_config(e, ws, e.venv / "bin" / "python")
            cfg = config.load(ws)
            cfg.workers = 4
            st = run_audit(cfg, "verify", BUDGET_MIN, None, ws / ".test-suite-audit", progress=lambda m: None,
                           base="HEAD")
            jp, _ = write(st)
            report = json.loads(jp.read_text())
            rec.write("verify", commit=c["commit"], parent=c["parent"], subject=c["subject"],
                      change=report["change"], baseline=report["baseline"], flakiness=report["flakiness"],
                      mutation={k: v for k, v in report["mutation"].items()}, status=report["run"]["status"],
                      started=report["run"]["started"], finished=report["run"]["finished"])
            print(name, c["commit"][:10], report["change"]["verdict"], flush=True)
            shutil.rmtree(ws)
        rec.close()


def _all_changed(e, c) -> list[str]:
    import subprocess
    out = subprocess.run(["git", "diff", "--name-only", c["parent"], c["commit"]], cwd=repo(e),
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p]


if __name__ == "__main__":
    main()
