"""H6: how many intermittent tests do 60 repeat runs reveal, and would 3 runs have caught them?

30 runs in file order, then 30 in random order via pytest-randomly with seeds 1 to 30.
"""

import argparse
from dataclasses import replace

from harness import corpus
from harness.records import Recorder
from tsa.pytest_run import run_pytest

RUNS = 30


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--runs", type=int, default=RUNS)
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        fixed = e.project()
        # Drop the "-p" that preceded "no:randomly".
        cleaned, skip = [], False
        for i, a in enumerate(fixed.pytest_args):
            if a == "-p" and i + 1 < len(fixed.pytest_args) and fixed.pytest_args[i + 1] == "no:randomly":
                skip = True
                continue
            if skip:
                skip = False
                continue
            cleaned.append(a)
        rand = replace(fixed, pytest_args=tuple(cleaned))
        rec = Recorder("e6_flaky", e)
        for order, proj in (("fixed", fixed), ("random", rand)):
            for i in range(args.runs):
                extra = (f"--randomly-seed={i + 1}",) if order == "random" else ()
                r = run_pytest(proj, extra_args=extra, timeout_s=900)
                rec.write("flake_run", order=order, index=i, returncode=r.returncode, wall_s=r.wall_s,
                          outcomes={k: v.outcome for k, v in r.outcomes.items()},
                          messages={k: v.message for k, v in r.outcomes.items() if v.message})
            print(f"{e.name} {order} done", flush=True)
        rec.close()


if __name__ == "__main__":
    main()
