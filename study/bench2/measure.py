"""Independent measurement of the verify benchmark (V1 to V4). Never run by the agents.

For each final workspace, a copy is made with the production source restored to the commit's
version, so an agent that edited source cannot change its own score.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from bench2.common import DATA, ROOT, build_repo, entry, file_hash, write_config
from tsa import config
from tsa.audit import run_audit
from tsa.pytest_run import run_pytest
from tsa.report.write import write

VERIFY_MIN = 30


def git(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def show(e, rev, path) -> bytes | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=e.dir, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def restore_source(e, ws: Path, rev: str, files: list[str]) -> None:
    for f in files:
        data = show(e, rev, f)
        if data is None:
            (ws / f).unlink(missing_ok=True)
        else:
            (ws / f).write_bytes(data)


def touched_tests(ws: Path, e) -> list[str]:
    out = git(ws, "status", "--porcelain", "--untracked-files=all")
    files = [ln[3:].split(" -> ")[-1] for ln in out.splitlines()]
    return sorted(f for f in files if f.endswith(".py") and not any(
        f == s or f.startswith(s.rstrip("/") + "/") for s in e.source) and (ws / f).exists())


def verify_run(ws: Path) -> dict:
    cfg = config.load(ws)
    cfg.workers = 4
    st = run_audit(cfg, "verify", VERIFY_MIN, None, ws / ".test-suite-audit", progress=lambda m: None, base="HEAD")
    write(st)
    res = st.mutation.get("results", [])
    k = sum(r["status"] == "killed" for r in res)
    s = sum(r["status"] == "survived" for r in res)
    u = sum(r["status"] == "uncovered" for r in res)
    return {"verdict": st.change.get("verdict"), "killed": k, "survived": s, "uncovered": u,
            "rate": k / (k + s + u) if k + s + u else None, "not_run": st.mutation.get("not_run"),
            "uncovered_changed_lines": st.change.get("uncovered_changed_lines"), "status": st.status}


def measure(w: dict) -> dict:
    e = entry(w["project"])
    src_ws = Path(w["workspace"])
    rec = {k: w[k] for k in ("arm", "project", "task", "commit")}
    rec["source_modified"] = file_hash(src_ws, w["source_files"]) != w["source_hash"]
    with tempfile.TemporaryDirectory(prefix="m2-") as tmp:
        ws = Path(tmp) / "ws"
        shutil.copytree(src_ws, ws, symlinks=True, ignore=shutil.ignore_patterns(".test-suite-audit", "__pycache__",
                                                                                 ".pytest_cache", ".hypothesis"))
        restore_source(e, ws, w["commit"], w["source_files"])
        proj = config.load(ws).project
        collected = run_pytest(proj, collect_only=True, timeout_s=600).collected or []
        after = {x["nodeid"] for x in collected}
        rec["tests_removed"] = sorted(set(w["tests_before"]) - after)
        rec["tests_added"] = sorted(after - set(w["tests_before"]))
        tests = touched_tests(ws, e)
        rec["test_files_touched"] = tests
        # V4: the whole suite on the commit's source.
        full = run_pytest(proj, timeout_s=1800)
        rec["failing_on_commit"] = sorted(full.failed_ids())
        # V1: tests in touched files that pass on the commit's source and fail on the parent's.
        if tests:
            p = replace(proj, tests=tuple(tests))
            on_new = run_pytest(p, timeout_s=900)
            passed = {n for n, o in on_new.outcomes.items() if o.outcome == "passed"}
            restore_source(e, ws, w["parent"], w["source_files"])
            on_old = run_pytest(p, timeout_s=900)
            rec["detecting"] = sorted(passed & on_old.failed_ids())
            rec["parent_collection_error"] = on_old.collection_error
            restore_source(e, ws, w["commit"], w["source_files"])
        else:
            rec["detecting"] = []
        rec["detects_fault"] = bool(rec["detecting"])
        # V2: changed-line detection rate of the final suite.
        rec["verify"] = verify_run(ws)
    return rec


def reference(task: str, project: str, commit: str, parent: str) -> dict:
    """The upstream developers' own tests for the change, measured like the agents' (V2 only)."""
    e = entry(project)
    with tempfile.TemporaryDirectory(prefix="m2ref-") as tmp:
        ws = Path(tmp) / "ws"
        names = git(e.dir, "diff", "--name-only", parent, commit).split()
        build_repo(e, ws, parent, commit, names)
        write_config(e, ws, e.venv / "bin" / "python")
        return {"arm": "upstream", "project": project, "task": task, "commit": commit, "verify": verify_run(ws)}


if __name__ == "__main__":
    wss = json.loads((DATA / "workspaces.json").read_text())
    only = set(sys.argv[1:])
    out_path = DATA / "measurements.jsonl"
    done = set()
    if out_path.exists():
        done = {(r["arm"], r["task"]) for r in map(json.loads, out_path.read_text().splitlines())}
    with open(out_path, "a") as fh:
        for w in wss:
            if (only and w["task"] not in only) or (w["arm"], w["task"]) in done:
                continue
            r = measure(w)
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(r["arm"], r["task"], "detects" if r["detects_fault"] else "misses", r["verify"]["rate"], flush=True)
        for w in wss:
            if w["arm"] != "skill" or ("upstream", w["task"]) in done or (only and w["task"] not in only):
                continue
            r = reference(w["task"], w["project"], w["commit"], w["parent"])
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print("upstream", w["task"], r["verify"]["rate"], flush=True)
