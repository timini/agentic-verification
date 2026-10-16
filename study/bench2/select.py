"""Select change commits (H7) and fault commits (verify benchmark). See ../VERIFY_BENCHMARK.md.

Run once: ``uv run python -m bench2.select``. Writes data/bench2/commits.json.
"""

import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from coverage.python import PythonParser

from harness import corpus
from harness.corpus import STUDY, WORK
from tsa.project import is_test_path
from tsa.pytest_run import run_pytest

OUT = STUDY / "data" / "bench2"
TREES = WORK / "bench2" / "select"
MAX_COMMITS = 300
N_CHANGE, N_FAULT = 3, 2
MIN_LINES, MAX_LINES = 2, 60
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
EXCLUDE = r"#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(cover|COVER)"


def git(e, *args, check=True) -> str:
    r = subprocess.run(["git", *args], cwd=e.dir, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:300]}")
    return r.stdout


def show(e, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=e.dir, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def changed(e, parent: str, commit: str) -> dict[str, set[int]]:
    """File -> changed line numbers in the commit's version (additions and modifications)."""
    out: dict[str, set[int]] = {}
    cur = None
    for line in git(e, "diff", "-U0", "--no-color", "--no-ext-diff", parent, commit).splitlines():
        if line.startswith("+++ "):
            p = line[4:]
            cur = None if p == "/dev/null" else p[2:]
        elif cur and (m := HUNK.match(line)):
            start, n = int(m.group(1)), int(m.group(2) or 1)
            if n:
                out.setdefault(cur, set()).update(range(start, start + n))
    return out


def is_source(e, path: str) -> bool:
    return path.endswith(".py") and any(path == s or path.startswith(s.rstrip("/") + "/") for s in e.source) \
        and not is_test_path(path)


def is_test(e, path: str) -> bool:
    return path.endswith(".py") and (is_test_path(path) or any(path.startswith(t.rstrip("/") + "/") for t in e.tests))


def executable(text: str, path: str) -> set[int]:
    try:
        p = PythonParser(text=text, filename=path, exclude=EXCLUDE)
        p.parse_source()
        return set(p.statements)
    except Exception:
        return set()


def spans(text: str) -> list[tuple[str, int, int]]:
    """(qualname, first, last line) of top-level functions and methods of top-level classes."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((n.name, n.lineno, n.end_lineno))
        elif isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((f"{n.name}.{m.name}", m.lineno, m.end_lineno))
    return out


def analyse(e, commit: str) -> dict | None:
    parents = git(e, "rev-list", "--parents", "-n", "1", commit).split()[1:]
    if not parents:
        return None
    parent = parents[0]
    ch = changed(e, parent, commit)
    src = {f: ns for f, ns in ch.items() if is_source(e, f)}
    tests = sorted(f for f in ch if is_test(e, f) and not is_source(e, f))
    exec_changed, inside_existing = 0, True
    for f, ns in src.items():
        new = show(e, commit, f)
        if new is None:
            continue
        ex = ns & executable(new, f)
        exec_changed += len(ex)
        old = show(e, parent, f)
        old_names = {q for q, _, _ in spans(old)} if old else set()
        sp = spans(new)
        for n in ex:
            hit = [q for q, a, b in sp if a <= n <= b]
            if not hit or hit[0] not in old_names:
                inside_existing = False
    return {"commit": commit, "parent": parent, "subject": git(e, "log", "-1", "--format=%s", commit).strip(),
            "source_files": sorted(src), "test_files": tests, "exec_changed": exec_changed,
            "inside_existing": inside_existing}


def fault_check(e, c: dict) -> dict:
    """Run the commit's changed test files on the commit's source and on the parent's source."""
    tree = TREES / e.name / c["commit"][:12]
    if tree.exists():
        shutil.rmtree(tree)
    tree.parent.mkdir(parents=True, exist_ok=True)
    git(e, "worktree", "add", "-f", "--detach", str(tree), c["commit"])
    try:
        proj = replace(e.project(), root=tree)
        files = [f for f in c["test_files"] if (tree / f).exists()]
        if not files:
            return {"ok": False, "why": "no test files"}
        proj = replace(proj, tests=tuple(files))
        on_new = run_pytest(proj, timeout_s=300)
        if on_new.collection_error:
            return {"ok": False, "why": "collection error on commit"}
        passed = {n for n, o in on_new.outcomes.items() if o.outcome == "passed"}
        for f in c["source_files"]:
            old = show(e, c["parent"], f)
            if old is not None:
                (tree / f).write_text(old)
        on_old = run_pytest(proj, timeout_s=300)
        if on_old.collection_error:
            return {"ok": False, "why": "collection error on parent source"}
        detecting = sorted(passed & on_old.failed_ids())
        return {"ok": bool(detecting), "why": None if detecting else "no test distinguishes the versions",
                "passed_on_commit": len(passed), "detecting": detecting}
    finally:
        git(e, "worktree", "remove", "--force", str(tree), check=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {}
    for e in corpus.load(sys.argv[1:] or None):
        revs = git(e, "rev-list", "--no-merges", "-n", str(MAX_COMMITS), e.sha).split()
        change, fault, skips = [], [], []
        for rev in revs:
            if len(change) >= N_CHANGE and len(fault) >= N_FAULT:
                break
            c = analyse(e, rev)
            if c is None or c["exec_changed"] == 0:
                continue
            if len(change) < N_CHANGE:
                change.append(c)
            if len(fault) >= N_FAULT:
                continue
            if not c["test_files"] or not c["inside_existing"] or not MIN_LINES <= c["exec_changed"] <= MAX_LINES:
                continue
            fc = fault_check(e, c)
            if fc["ok"]:
                fault.append({**c, **fc})
            else:
                skips.append({"commit": rev, "why": fc["why"]})
            print(e.name, rev[:10], fc.get("why") or "fault commit", flush=True)
        result[e.name] = {"scanned": len(revs), "change": change, "fault": fault, "fault_skips": skips}
        print(e.name, len(change), "change,", len(fault), "fault", flush=True)
    (OUT / "commits.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
