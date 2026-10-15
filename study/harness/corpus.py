"""Clone corpus projects at their pinned commits and build one uv environment per project."""

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tsa.project import Project

STUDY = Path(__file__).resolve().parent.parent
WORK = STUDY / "work"
PYTHON = "3.12"
# Test tooling installed into every corpus environment. Exact pins so runs are comparable.
TOOLING = ["pytest==9.1.1", "pytest-cov==7.1.0", "coverage==7.16.2", "pytest-randomly==3.16.0"]


@dataclass(frozen=True)
class Entry:
    name: str
    repo: str
    tag: str
    sha: str
    source: tuple[str, ...]
    tests: tuple[str, ...]
    install: tuple[str, ...]
    pytest_args: tuple[str, ...]
    reason: str
    submodules: bool = False

    @property
    def dir(self) -> Path:
        return WORK / self.name / "src"

    @property
    def venv(self) -> Path:
        return WORK / self.name / ".venv"

    def project(self) -> Project:
        args = list(self.pytest_args)
        # pytest-randomly is installed for H6 only; every other run uses file order.
        args += ["-p", "no:randomly"]
        if has_module(self, "hypothesis"):
            args += ["--hypothesis-seed=0"]
        return Project(
            root=self.dir, python=self.venv / "bin" / "python",
            source=self.source, tests=self.tests, pytest_args=tuple(args),
        )


def load(only: list[str] | None = None) -> list[Entry]:
    data = tomllib.loads((STUDY / "corpus.toml").read_text())
    entries = [
        Entry(
            name=p["name"], repo=p["repo"], tag=p["tag"], sha=p["sha"],
            source=tuple(p["source"]), tests=tuple(p["tests"]), install=tuple(p["install"]),
            pytest_args=tuple(p.get("pytest_args", [])), reason=p["reason"],
            submodules=p.get("submodules", False),
        )
        for p in data["project"]
    ]
    return [e for e in entries if not only or e.name in only]


def sh(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def setup(e: Entry) -> None:
    if not (e.dir / ".git").exists():
        e.dir.parent.mkdir(parents=True, exist_ok=True)
        sh(["git", "clone", "--quiet", "--filter=blob:none", e.repo, str(e.dir)])
    sh(["git", "checkout", "--quiet", "--force", e.sha], cwd=e.dir)
    head = sh(["git", "rev-parse", "HEAD"], cwd=e.dir).strip()
    if head != e.sha:
        raise RuntimeError(f"{e.name}: HEAD {head} != pinned {e.sha}")
    if e.submodules:
        sh(["git", "submodule", "update", "--init", "--quiet"], cwd=e.dir)
    if not e.venv.exists():
        sh(["uv", "venv", "-q", "-p", PYTHON, str(e.venv)])
    py = str(e.venv / "bin" / "python")
    sh(["uv", "pip", "install", "-q", "-p", py, *e.install, *TOOLING], cwd=e.dir)
    freeze = sh(["uv", "pip", "freeze", "-p", py])
    (WORK / e.name / "freeze.txt").write_text(freeze)


def has_module(e: Entry, mod: str) -> bool:
    py = e.venv / "bin" / "python"
    r = subprocess.run([str(py), "-c", f"import {mod}"], capture_output=True)
    return r.returncode == 0


def freeze(e: Entry) -> str:
    return (WORK / e.name / "freeze.txt").read_text()


if __name__ == "__main__":
    for e in load(sys.argv[1:] or None):
        print(f"setting up {e.name} @ {e.tag}", flush=True)
        try:
            setup(e)
            print(json.dumps({"name": e.name, "ok": True}))
        except subprocess.CalledProcessError as exc:
            print(json.dumps({"name": e.name, "ok": False, "stderr": exc.stderr[-2000:]}))
