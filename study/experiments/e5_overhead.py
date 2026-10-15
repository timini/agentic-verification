"""H5: runtime overhead of per-test coverage contexts.

Conditions: no coverage (A), --cov (B), --cov --cov-context=test (C). One discarded warm-up run,
then 10 blocks; each block runs A, B and C once in a seeded random order. Run this alone on
the machine: concurrent experiments would distort the timings.
"""

import argparse
import random
import tempfile
from pathlib import Path

from harness import corpus
from harness.records import SEED, Recorder
from tsa.pytest_run import run_pytest

BLOCKS = 10


def condition_args(cond: str, project, tmp: Path) -> tuple[tuple[str, ...], dict]:
    if cond == "none":
        return (), {}
    args = [f"--cov={project.root / s}" for s in project.source] + ["--cov-report="]
    if cond == "contexts":
        args.append("--cov-context=test")
    return tuple(args), {"COVERAGE_FILE": str(tmp / ".coverage")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--blocks", type=int, default=BLOCKS)
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        p = e.project()
        rng = random.Random(f"{SEED}-{e.name}-h5")
        rec = Recorder("e5_overhead", e)
        with tempfile.TemporaryDirectory() as tmp:
            run_pytest(p, timeout_s=900)  # warm-up, discarded
            for b in range(args.blocks):
                order = ["none", "coverage", "contexts"]
                rng.shuffle(order)
                for cond in order:
                    extra, env = condition_args(cond, p, Path(tmp))
                    r = run_pytest(p, extra_args=extra, env=env, timeout_s=900)
                    rec.write("timing", block=b, condition=cond, wall_s=r.wall_s, cpu_s=r.cpu_s,
                              returncode=r.returncode, tests=len(r.outcomes),
                              sum_test_s=sum(o.duration_s for o in r.outcomes.values()))
                    for f in Path(tmp).glob(".coverage*"):
                        f.unlink()
                print(f"{e.name} block {b} done", flush=True)
        rec.close()


if __name__ == "__main__":
    main()
