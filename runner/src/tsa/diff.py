"""Lines changed since a git revision: the scope of ``tsa verify``.

The working tree is compared with ``base``, so committed, staged and unstaged changes all
count. Untracked files count as changed in full. Only line numbers in the current version of
each file are returned, because that is the version the mutants and coverage refer to.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Change:
    base: str
    commit: str | None  # resolved SHA of base
    lines: dict[str, set[int]] = field(default_factory=dict)  # file relative to project root -> changed lines
    untracked: list[str] = field(default_factory=list)


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def changed_lines(root: Path, base: str) -> Change:
    root = root.resolve()
    commit = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
    ch = Change(base, commit)
    diff = _git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--relative", commit, "--", ".")
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            current = None if path == "/dev/null" else path[2:] if path.startswith("b/") else path
        elif current and (m := HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                ch.lines.setdefault(current, set()).update(range(start, start + count))
    for rel in _git(root, "ls-files", "--others", "--exclude-standard", "--", ".").splitlines():
        p = root / rel
        if p.suffix == ".py" and p.is_file():
            ch.untracked.append(rel)
            ch.lines[rel] = set(range(1, len(p.read_text(errors="replace").splitlines()) + 1))
    return ch
