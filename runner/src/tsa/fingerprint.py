"""Provenance for a run: source revision, working-tree state, lockfiles and tool versions."""

import hashlib
import platform
import subprocess
from pathlib import Path

LOCKFILES = ("uv.lock", "poetry.lock", "Pipfile.lock", "requirements.txt", "requirements-dev.txt", "pdm.lock")


def _git(root: Path, *args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def collect(root: Path, python: Path) -> dict:
    status = _git(root, "status", "--porcelain")
    diff = _git(root, "diff", "HEAD") or ""
    locks = {}
    for name in LOCKFILES:
        p = root / name
        if p.exists():
            locks[name] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    versions = subprocess.run(
        [str(python), "-c", "import sys, pytest; print(sys.version.split()[0], pytest.__version__)"],
        capture_output=True, text=True,
    ).stdout.split()
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "dirty": bool(status),
        "worktree_hash": hashlib.sha256((status or "").encode() + diff.encode()).hexdigest()[:16],
        "lockfiles": locks,
        "target_python": versions[0] if versions else None,
        "pytest": versions[1] if len(versions) > 1 else None,
        "platform": f"{platform.system()}-{platform.machine()}",
    }
