"""Shared helpers for the change-verification experiments (../VERIFY_BENCHMARK.md)."""

import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

from harness import corpus
from harness.corpus import STUDY, TOOLING, WORK, sh

DATA = STUDY / "data" / "bench2"
ROOT = WORK / "bench2"
COMMITS = DATA / "commits.json"


def commits() -> dict:
    return json.loads(COMMITS.read_text())


def entry(name: str) -> corpus.Entry:
    return corpus.load([name])[0]


def repo(e: corpus.Entry) -> Path:
    """A full bare clone used for all history access. The study's checkouts are partial clones
    and are left untouched."""
    d = ROOT / "mirrors" / f"{e.name}.git"
    if not d.exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", "--bare", e.repo, str(d)], check=True)
    return d


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {r.stderr[:300]}")
    return r.stdout


def build_repo(e: corpus.Entry, dest: Path, parent: str, overlay: str, paths: list[str]) -> None:
    """A fresh repository: HEAD is ``parent``'s tree (one commit, no history), and the working
    tree has ``paths`` replaced by their version in ``overlay``. No upstream history is present,
    so the overlay commit's other files (such as its tests) cannot be looked up."""
    dest.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", "--format=tar", parent], cwd=repo(e), capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        tf.extractall(dest, filter="data")
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _submodules(e, dest, parent)
    _git(dest, "-c", "user.email=bench@example.com", "-c", "user.name=bench", "commit", "-qm", "base", "--no-gpg-sign")
    for p in paths:
        r = subprocess.run(["git", "show", f"{overlay}:{p}"], cwd=repo(e), capture_output=True)
        target = dest / p
        if r.returncode != 0:
            target.unlink(missing_ok=True)  # deleted in the overlay commit
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.stdout)


def _submodules(e: corpus.Entry, dest: Path, rev: str) -> None:
    """git archive leaves submodules empty; fill each with the commit ``rev`` pins, untracked and ignored."""
    if not e.submodules:
        return
    tree = subprocess.run(["git", "ls-tree", "-r", rev], cwd=repo(e), capture_output=True, text=True, check=True).stdout
    mods = subprocess.run(["git", "show", f"{rev}:.gitmodules"], cwd=repo(e), capture_output=True, text=True).stdout
    urls = dict(re.findall(r"path = (\S+)\s+url = (\S+)", mods))
    for line in tree.splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind != "commit" or path not in urls:
            continue
        mirror = ROOT / "mirrors" / (Path(urls[path]).stem + ".git")
        if not mirror.exists():
            subprocess.run(["git", "clone", "--quiet", "--bare", urls[path], str(mirror)], check=True)
        tar = subprocess.run(["git", "archive", "--format=tar", sha], cwd=mirror, capture_output=True, check=True).stdout
        (dest / path).mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            tf.extractall(dest / path, filter="data")
        with open(dest / ".git" / "info" / "exclude", "a") as fh:
            fh.write(f"{path}/\n")


def make_venv(e: corpus.Entry, root: Path) -> Path:
    py = root / ".venv" / "bin" / "python"
    env = {**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": e.tag.lstrip("v")}
    subprocess.run(["uv", "venv", "-q", "-p", corpus.PYTHON, str(root / ".venv")], check=True)
    subprocess.run(["uv", "pip", "install", "-q", "-p", str(py), *e.install, *TOOLING], cwd=root, env=env, check=True)
    # The workspace's virtual environment and tool output stay out of `git status`.
    with open(root / ".git" / "info" / "exclude", "a") as fh:
        fh.write("\n.venv/\n.test-suite-audit/\n")
    return py


def file_hash(root: Path, paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        f = root / p
        h.update(p.encode() + b"\0" + (f.read_bytes() if f.exists() else b"<missing>"))
    return h.hexdigest()


def write_config(e: corpus.Entry, root: Path, python: Path) -> None:
    """test-suite-audit.toml with the study's configuration, so every verify run sees the same scope."""
    args = list(e.pytest_args) + ["-p", "no:randomly"]
    lines = [f'python = "{python}"', f"source = {json.dumps(list(e.source))}", f"tests = {json.dumps(list(e.tests))}",
             f"pytest_args = {json.dumps(args)}"]
    (root / "test-suite-audit.toml").write_text("\n".join(lines) + "\n")
    with open(root / ".git" / "info" / "exclude", "a") as fh:
        fh.write("test-suite-audit.toml\n")
