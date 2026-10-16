"""One fresh workspace per (arm, fault commit) for the verify benchmark (../VERIFY_BENCHMARK.md).

HEAD is the parent commit; the working tree holds the commit's source changes only.
"""

import json
import shutil
import subprocess
import sys

from bench2.common import DATA, ROOT, build_repo, commits, entry, file_hash, make_venv, write_config
from tsa.pytest_run import run_pytest
from tsa.config import load

ARMS = ("skill", "baseline")


def tasks(only=None) -> list[tuple]:
    out = []
    for name, sel in commits().items():
        if only and name not in only:
            continue
        for c in sel["fault"]:
            out.append((name, c))
    return out


def prepare(name: str, c: dict, arm: str) -> dict:
    e = entry(name)
    ws = ROOT / arm / f"{name}-{c['commit'][:7]}"
    if ws.exists():
        shutil.rmtree(ws)
    build_repo(e, ws, c["parent"], c["commit"], c["source_files"])
    py = make_venv(e, ws)
    write_config(e, ws, py)
    collected = run_pytest(load(ws).project, collect_only=True, timeout_s=600).collected or []
    msg = subprocess.run(["git", "log", "-1", "--format=%B", c["commit"]], cwd=e.dir, capture_output=True,
                         text=True, check=True).stdout.strip()
    return {"arm": arm, "project": name, "task": f"{name}-{c['commit'][:7]}", "commit": c["commit"],
            "parent": c["parent"], "workspace": str(ws), "message": msg, "source_files": c["source_files"],
            "source_hash": file_hash(ws, c["source_files"]), "tests_before": sorted(x["nodeid"] for x in collected)}


if __name__ == "__main__":
    out = []
    for name, c in tasks(sys.argv[1:] or None):
        for arm in ARMS:
            out.append(prepare(name, c, arm))
            print(out[-1]["task"], arm, len(out[-1]["tests_before"]), "tests", flush=True)
    (DATA / "workspaces.json").write_text(json.dumps(out, indent=2))
