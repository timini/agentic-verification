"""H3: does killing every whole-function replacement mean the function's calls are tested?

Step 1 runs every body-replacement mutant of every eligible function, classifying each function
as fully killed or not. Step 2 runs a seeded sample of up to 300 call-statement deletions drawn
from all eligible functions, each against pristine source, and records its parent's status.
"""

import argparse
import random

from harness import corpus
from harness.records import SEED, Recorder
from tsa.mutation.execute import Executor

from .common import WORKERS, prepare, write_result

CALL_CAP = 300


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        prep = prepare(e)
        rng = random.Random(f"{SEED}-{e.name}-h3")
        rec = Recorder("e3_effects", e)
        body = [m for m in prep.mutants if m.operator.startswith("body:")]
        calls = [m for m in prep.mutants if m.operator == "call-delete"]
        chosen = rng.sample(calls, min(CALL_CAP, len(calls)))
        rec.write("populations", body=len(body), calls=len(calls), calls_sampled=len(chosen))
        print(f"{e.name}: {len(body)} body mutants, {len(chosen)}/{len(calls)} call deletions", flush=True)
        with Executor(e.project(), WORKERS) as ex:
            ex.run((prep.task(m) for m in body), lambda t, r: write_result(rec, "body", t, r))
            ex.run((prep.task(m) for m in chosen), lambda t, r: write_result(rec, "call", t, r))
        rec.close()


if __name__ == "__main__":
    main()
