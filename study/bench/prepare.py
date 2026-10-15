"""Create one fresh workspace per (arm, project) for the skill benchmark (see ../BENCHMARK.md)."""

import hashlib
import json
import shutil
import sys

from harness import corpus
from harness.corpus import TOOLING, WORK, sh

BENCH = WORK / "bench"
# Like the runner's copy rule, but keep .git: some projects take their version from it.
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".pytest_cache", ".hypothesis", ".coverage")
ARMS = ("skill", "baseline")


def tree_hash(root, e: corpus.Entry) -> str:
    h = hashlib.sha256()
    for top in (*e.source, *e.tests):
        for f in sorted((root / top).rglob("*.py")):
            h.update(str(f.relative_to(root)).encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def prepare(e: corpus.Entry, arm: str) -> dict:
    ws = BENCH / arm / e.name
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(e.dir, ws, ignore=IGNORE, symlinks=True)
    py = ws / ".venv" / "bin" / "python"
    sh(["uv", "venv", "-q", "-p", corpus.PYTHON, str(ws / ".venv")])
    sh(["uv", "pip", "install", "-q", "-p", str(py), *e.install, *TOOLING], cwd=ws)
    return {"arm": arm, "project": e.name, "workspace": str(ws), "hash_before": tree_hash(ws, e)}


if __name__ == "__main__":
    BENCH.mkdir(parents=True, exist_ok=True)
    out = []
    for e in corpus.load(sys.argv[1:] or None):
        for arm in ARMS:
            out.append(prepare(e, arm))
            print(json.dumps(out[-1]), flush=True)
    (BENCH / "workspaces.json").write_text(json.dumps(out, indent=2))
