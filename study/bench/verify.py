"""Independently verify benchmark agents' claims against pristine projects (see ../BENCHMARK.md).

Input: data/bench/<arm>/<project>.md, the agent's final reply ending in a JSON block.
Output: data/bench/verification.jsonl, one record per checked claim, plus a per-run summary.
"""

import ast
import json
import random
import re
import sys
from pathlib import Path

from coverage.python import PythonParser

from experiments.common import WORKERS, prepare
from harness import corpus
from harness.records import STUDY
from tsa.mutation.execute import Executor
from tsa.project import is_test_path

from .prepare import BENCH, tree_hash

DATA = STUDY / "data" / "bench"
SEED = 20261016
VID = __import__("time").strftime("%Y%m%dT%H%M%S")  # identifies one verification pass
MAX_PER_CLAIM = 6
MAX_REMOVAL_MUTANTS = 100
VALID = ("killed", "survived")


def parse_reply(text: str) -> dict | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    for b in reversed(blocks):
        try:
            return json.loads(b)
        except json.JSONDecodeError:
            continue
    return None


def def_lines(path: Path) -> dict[int, str]:
    """def line -> qualname, for top-level functions and methods (same rule as the mutants)."""
    out = {}
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.lineno] = node.name
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, ast.FunctionDef):
                    out[m.lineno] = f"{node.name}.{m.name}"
    return out


def statements(path: Path) -> set[int]:
    p = PythonParser(filename=str(path))
    p.parse_source()
    return set(p.statements)


def run_tasks(e, tasks):
    results = {}
    with Executor(e.project(), WORKERS) as ex:
        ex.run(tasks, lambda t, r: results.__setitem__(id(t), r))
    return results


def verify_untested(e, prep, claims, rng):
    source_files = {str(f.relative_to(e.dir)) for f in e.project().source_files()}
    covered = prep.cov.any_covered()
    out, tasks, owners = [], [], {}
    for i, c in enumerate(claims[:10]):
        f, line = str(c.get("file", "")).lstrip("./"), c.get("line")
        rec = {"kind": "untested", "index": i, "file": f, "line": line, "behaviour": c.get("behaviour")}
        out.append(rec)
        if f not in source_files or is_test_path(f) or not isinstance(line, int):
            rec["verdict"], rec["why"] = "unverifiable", "not a production source line"
            continue
        path = e.dir / f
        fn = def_lines(path).get(line)
        stmts = statements(path)
        if line not in stmts and fn is None:
            rec["verdict"], rec["why"] = "unverifiable", "not an executable line"
            continue
        if line in stmts and (f, line) not in covered:
            rec["verdict"], rec["why"] = "verified", "executable line that no test covers"
            continue
        cands = [m for m in prep.mutants if m.file == f and (
            m.start_line == line or (fn is not None and m.function == fn and m.operator.startswith("body:")))]
        if not cands:
            rec["verdict"], rec["why"] = "unverifiable", "no mutant can be generated on this line"
            continue
        chosen = rng.sample(cands, min(MAX_PER_CLAIM, len(cands)))
        rec["mutants"] = [m.id for m in chosen]
        for m in chosen:
            t = prep.task(m)
            tasks.append(t)
            owners[id(t)] = rec
    results = run_tasks(e, tasks)
    for t in tasks:
        r = results[id(t)]
        owners[id(t)].setdefault("statuses", []).append(r.status)
    for rec in out:
        if "statuses" in rec:
            sts = rec["statuses"]
            if "survived" in sts:
                rec["verdict"], rec["why"] = "verified", "a valid, activated mutant survived"
            elif "killed" in sts:
                rec["verdict"], rec["why"] = "refuted", "every valid mutant was killed"
            else:
                rec["verdict"], rec["why"] = "unverifiable", "no valid, activated mutant"
    return out


def verify_removal(e, prep, tests, rng):
    rec = {"kind": "removal", "tests": tests}
    if not tests:
        rec["verdict"] = "none recommended"
        return rec
    removed = set(tests) & prep.stable
    rec["unknown_ids"] = sorted(set(tests) - prep.stable)
    lines = set().union(*(prep.cov.run_lines.get(t, set()) for t in removed)) if removed else set()
    cands = sorted({m.id: m for m in prep.mutants if any((m.file, ln) in lines for ln in m.lines)}.items())
    chosen = [m for _, m in rng.sample(cands, min(MAX_REMOVAL_MUTANTS, len(cands)))]
    tasks = [prep.task(m) for m in chosen]
    results = run_tasks(e, tasks)
    lost = []
    for t in tasks:
        r = results[id(t)]
        if r.status == "killed" and set(r.killers) <= removed:
            lost.append(t.mutant.id)
    rec.update(mutants=len(tasks), killed=sum(results[id(t)].status == "killed" for t in tasks), lost=lost)
    if not removed or not tasks:
        # No in-scope tests, or the tests cover no production lines: nothing can refute or support it.
        rec["verdict"] = "unverifiable"
    else:
        rec["verdict"] = "refuted" if lost else "not refuted"
    return rec


def flaky_reference() -> dict[str, set]:
    import csv

    ref: dict[str, set] = {}
    with open(STUDY / "data" / "derived" / "h6_intermittent.csv") as fh:
        for row in csv.DictReader(fh):
            ref.setdefault(row["project"], set()).add(row["test"])
    return ref


def main() -> None:
    only = sys.argv[1:] or None
    workspaces = {(w["arm"], w["project"]): w for w in json.loads((BENCH / "workspaces.json").read_text())}
    flaky_ref = flaky_reference()
    out_path = DATA / "verification.jsonl"
    with open(out_path, "a") as fh:
        for e in corpus.load(only):
            prep = prepare(e)
            for arm in ("skill", "baseline", "skill-v0"):
                reply_path = DATA / arm / f"{e.name}.md"
                if not reply_path.exists():
                    continue
                rng = random.Random(f"{SEED}-{arm}-{e.name}")
                reply = parse_reply(reply_path.read_text())
                base = {"arm": arm, "project": e.name, "vid": VID}
                if arm == "skill-v0":
                    # Runs of the defective runner: workspaces were re-prepared, safety recorded first.
                    safety = [json.loads(l) for l in (DATA / arm / "safety.jsonl").read_text().splitlines()]
                    modified = next(r["modified"] for r in safety if r["project"] == e.name)
                else:
                    ws = Path(workspaces[(arm, e.name)]["workspace"])
                    modified = tree_hash(ws, e) != workspaces[(arm, e.name)]["hash_before"]
                fh.write(json.dumps({**base, "kind": "run", "parsed": reply is not None, "modified": modified}) + "\n")
                if reply is None:
                    continue
                for rec in verify_untested(e, prep, reply.get("untested") or [], rng):
                    fh.write(json.dumps({**base, **rec}) + "\n")
                fh.write(json.dumps({**base, **verify_removal(e, prep, reply.get("removable_tests") or [], rng)}) + "\n")
                for t in reply.get("flaky_tests") or []:
                    v = "confirmed" if t in flaky_ref.get(e.name, set()) else "not observed"
                    fh.write(json.dumps({**base, "kind": "flaky", "test": t, "verdict": v}) + "\n")
                fh.flush()
                print(f"{arm}/{e.name} verified", flush=True)


if __name__ == "__main__":
    main()
