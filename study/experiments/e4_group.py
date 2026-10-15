"""H4: are individually removable tests jointly removable?

Units are test files with 10 to 60 stable tests that have coverage; up to 3 per project. For
each file, up to 150 mutants on lines its tests cover run against all of the file's tests in one
session, giving a full kill matrix. Leave-one-out and group removal are computed in analysis.
"""

import argparse
import random
from collections import defaultdict

from harness import corpus
from harness.records import SEED, Recorder
from tsa.mutation.execute import Executor

from .common import WORKERS, prepare, write_result

MIN_TESTS, MAX_TESTS, FILES, MUTANTS = 10, 60, 3, 150


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        prep = prepare(e)
        rng = random.Random(f"{SEED}-{e.name}-h4")
        by_file: dict[str, list[str]] = defaultdict(list)
        for t in sorted(prep.stable):
            if prep.cov.run_lines.get(t):
                by_file[t.split("::", 1)[0]].append(t)
        eligible = sorted(f for f, ts in by_file.items() if MIN_TESTS <= len(ts) <= MAX_TESTS)
        files = rng.sample(eligible, min(FILES, len(eligible)))
        rec = Recorder("e4_group", e)
        rec.write("units", eligible=eligible, chosen=files)
        tasks = []
        for f in files:
            tests = by_file[f]
            lines = set().union(*(prep.cov.run_lines[t] for t in tests))
            cands = sorted({m.id: m for m in prep.mutants if any((m.file, ln) in lines for ln in m.lines)}.items())
            chosen = rng.sample(cands, min(MUTANTS, len(cands)))
            rec.write("unit", file=f, tests=tests, mutants=[mid for mid, _ in chosen])
            tasks += [(f, prep.task(m, select=tuple(tests))) for _, m in chosen]
        print(f"{e.name}: files={files} runs={len(tasks)}", flush=True)
        labels = {id(t): f for f, t in tasks}
        with Executor(e.project(), WORKERS) as ex:
            ex.run([t for _, t in tasks], lambda t, r: write_result(rec, labels[id(t)], t, r))
        rec.close()


if __name__ == "__main__":
    main()
