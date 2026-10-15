"""H2: survivors per CPU-minute, classical (mutmut operators) vs deterministic deletion.

Each strategy gets the same wall-clock budget per project, run one after the other in a
seeded random order. Mutants are drawn in seeded random order from the whole population, so
uncovered mutants are included (they cost no test execution and are not survivors).
"""

import argparse
import random
import time

from harness import corpus
from harness.records import SEED, Recorder
from tsa.mutation.execute import Executor

from .common import WORKERS, prepare, write_result

BUDGET_S = 20 * 60


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        prep = prepare(e)
        rng = random.Random(f"{SEED}-{e.name}-h2")
        strategies = ["classical", "deletion"]
        rng.shuffle(strategies)
        rec = Recorder("e2_budget", e)
        for strategy in strategies:
            pop = [m for m in prep.mutants if m.population == strategy]
            rng.shuffle(pop)
            rec.write("strategy_start", strategy=strategy, population=len(pop), budget_s=args.budget_s,
                      workers=WORKERS)
            start = time.monotonic()
            with Executor(e.project(), WORKERS) as ex:
                n = ex.run((prep.task(m) for m in pop),
                           lambda t, r: write_result(rec, strategy, t, r),
                           deadline=start + args.budget_s)
            elapsed = time.monotonic() - start
            rec.write("strategy_end", strategy=strategy, completed=n, elapsed_s=elapsed,
                      exhausted=n == len(pop))
            print(f"{e.name} {strategy}: {n}/{len(pop)} mutants in {elapsed:.0f}s", flush=True)
        rec.close()


if __name__ == "__main__":
    main()
