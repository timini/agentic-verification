"""Audit configuration: ``test-suite-audit.toml`` if present, otherwise discovery.

Explicit configuration always wins over discovery. Discovery is reported in the run record so
the user can see what was assumed.
"""

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .project import Project

CONFIG_NAME = "test-suite-audit.toml"


@dataclass
class AuditConfig:
    project: Project
    protected: list[str] = field(default_factory=list)  # node ID prefixes or marker names
    discovered: dict[str, str] = field(default_factory=dict)  # field -> how it was found
    workers: int = 4


def load(root: Path) -> AuditConfig:
    root = root.resolve()
    data: dict = {}
    if (root / CONFIG_NAME).exists():
        data = tomllib.loads((root / CONFIG_NAME).read_text())
    found: dict[str, str] = {}

    python = data.get("python")
    if python:
        found["python"] = "config"
    else:
        for cand in (root / ".venv/bin/python", root / "venv/bin/python"):
            if cand.exists():
                python, found["python"] = str(cand), f"discovered {cand.relative_to(root)}"
                break
        else:
            python, found["python"] = shutil.which("python3") or "python3", "PATH python3"

    source = data.get("source")
    if source:
        found["source"] = "config"
    else:
        source = _discover_source(root)
        found["source"] = "discovered " + ", ".join(source) if source else "none found"

    tests = data.get("tests")
    if tests:
        found["tests"] = "config"
    else:
        tests = [d for d in ("tests", "test") if (root / d).is_dir()] or ["."]
        found["tests"] = "discovered " + ", ".join(tests)

    project = Project(
        root=root, python=Path(python), source=tuple(source), tests=tuple(tests),
        pytest_args=tuple(data.get("pytest_args", ["-p", "no:cacheprovider", "-p", "no:randomly"])),
        env=dict(data.get("env", {})),
    )
    return AuditConfig(project, list(data.get("protected", [])), found, int(data.get("workers", 4)))


def _discover_source(root: Path) -> list[str]:
    src = root / "src"
    base = src if src.is_dir() else root
    out = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "__init__.py").exists() and d.name not in ("tests", "test", "docs"):
            out.append(str(d.relative_to(root)))
    return out
