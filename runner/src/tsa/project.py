"""A target project: where its code lives, which interpreter runs it, and how to invoke pytest."""

import os
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent / "pytest_plugin"

COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "venv", ".tox", ".nox", "__pycache__", "*.pyc", ".pytest_cache",
    ".mypy_cache", ".hypothesis", ".coverage", ".coverage.*", "htmlcov", "mutants",
    ".test-suite-audit", "node_modules", "build", "dist",
)


def is_test_path(rel: str) -> bool:
    """Test code by pytest's default conventions: a tests/test directory, test_*.py, *_test.py, conftest.py."""
    parts = Path(rel).parts
    name = parts[-1] if parts else ""
    return (
        any(part in ("tests", "test") for part in parts[:-1])
        or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
    )


@dataclass(frozen=True)
class Project:
    root: Path  # directory pytest runs in
    python: Path  # interpreter of the project's environment
    source: tuple[str, ...]  # production package dirs, relative to root
    tests: tuple[str, ...] = ("tests",)
    pytest_args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)

    def source_files(self) -> list[Path]:
        """Production files eligible for mutation. Test code inside a source package is excluded."""
        files: list[Path] = []
        for src in self.source:
            p = self.root / src
            files.extend(sorted(p.rglob("*.py")) if p.is_dir() else [p])
        test_roots = [(self.root / t).resolve() for t in self.tests if t not in (".", "")]
        return [
            f for f in files
            if "__pycache__" not in f.parts
            and not is_test_path(str(f.relative_to(self.root)))
            and not any(f.resolve().is_relative_to(t) for t in test_roots)
        ]

    def import_roots(self) -> list[str]:
        """Directories that must precede site-packages so imports resolve to *this* copy.

        Editable installs point at the original checkout; prepending these roots makes a
        workspace copy shadow it. The activation check confirms the shadowing worked.
        """
        roots = []
        for src in self.source:
            parent = (self.root / src).parent
            if str(parent) not in roots:
                roots.append(str(parent))
        if str(self.root) not in roots:
            roots.append(str(self.root))
        return roots

    def base_env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("TSA_", "PYTEST_", "COV_"))}
        env.update(self.env)
        env["PYTHONPATH"] = os.pathsep.join([str(PLUGIN_DIR), *self.import_roots()])
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = env.get("PYTHONHASHSEED", "0")
        return env

    def copy_to(self, dest: Path) -> "Project":
        """Copy the project tree (without VCS, caches or venvs) to ``dest`` and return it there.

        The original tree is only ever read.
        """
        shutil.copytree(self.root, dest, ignore=COPY_IGNORE, symlinks=True)
        return replace(self, root=dest)
