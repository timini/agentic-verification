"""H1: do high-overlap test pairs have the same fault-detection ability?

Pairs with coverage Jaccard >= 0.9 (union >= 5 lines), up to 50 per project, plus a comparison
sample of 50 pairs with Jaccard in [0.5, 0.9). For each pair, up to 40 mutants on lines in
C(a) | C(b) run against both tests in one session; each test's outcome is recorded, so the
pair's kill sets are complete (no stop-at-first-kill).
"""

import argparse
import random

from harness import corpus
from harness.records import SEED, Recorder
from tsa.evidence.overlap import jaccard_pairs
from tsa.mutation.execute import Executor

from .common import WORKERS, prepare, write_result

HIGH, LOW = 0.9, 0.5
PAIRS_PER_STRATUM = 50
MUTANTS_PER_PAIR = 40
MIN_UNION = 5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        prep = prepare(e)
        rng = random.Random(f"{SEED}-{e.name}-h1")
        lines = {t: v for t, v in prep.cov.run_lines.items() if t in prep.stable and v}
        pairs = jaccard_pairs(lines, LOW, MIN_UNION)
        high = [p for p in pairs if p[2] >= HIGH]
        low = [p for p in pairs if p[2] < HIGH]
        sample = [("high", p) for p in rng.sample(high, min(PAIRS_PER_STRATUM, len(high)))]
        sample += [("comparison", p) for p in rng.sample(low, min(PAIRS_PER_STRATUM, len(low)))]
        rec = Recorder("e1_overlap", e)
        rec.write("pair_population", tests_with_coverage=len(lines), high=len(high), comparison=len(low))

        by_line: dict = {}
        for m in prep.mutants:
            for ln in m.lines:
                by_line.setdefault((m.file, ln), []).append(m)
        tasks = []
        for stratum, (a, b, jac, union) in sample:
            region = lines[a] | lines[b]
            cands = {m.id: m for ln in region for m in by_line.get(ln, [])}
            chosen = rng.sample(sorted(cands), min(MUTANTS_PER_PAIR, len(cands)))
            pair_id = f"{a} <> {b}"
            rec.write("pair", pair_id=pair_id, stratum=stratum, a=a, b=b, jaccard=jac, union=union,
                      mutants=chosen, same_function=a.split("[", 1)[0] == b.split("[", 1)[0])
            for mid in chosen:
                tasks.append((pair_id, prep.task(cands[mid], select=(a, b))))
        print(f"{e.name}: {len(high)} high / {len(low)} comparison pairs; {len(tasks)} runs", flush=True)
        labels = {id(t): pid for pid, t in tasks}
        with Executor(e.project(), WORKERS) as ex:
            ex.run([t for _, t in tasks], lambda t, r: write_result(rec, labels[id(t)], t, r))
        rec.close()


if __name__ == "__main__":
    main()
