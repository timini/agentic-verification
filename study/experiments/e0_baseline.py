"""E0: baseline and exclusion rule. Three pristine runs per project; record stable passing tests.

Pre-registered rule: a project is excluded if outcomes differ across the 3 runs (for the
project as a whole we only exclude when the suite cannot run or takes > 10 minutes); tests
that fail or vary are removed from the analysed scope and counted.
"""

import argparse

from harness import corpus
from harness.records import Recorder
from tsa.pytest_run import run_pytest

RUNS = 3
SUITE_LIMIT_S = 600


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*")
    args = ap.parse_args()
    for e in corpus.load(args.projects or None):
        p = e.project()
        rec = Recorder("e0_baseline", e)
        collected = run_pytest(p, collect_only=True, timeout_s=SUITE_LIMIT_S).collected or []
        rec.write("collected", tests=[c["nodeid"] for c in collected],
                  markers={c["nodeid"]: c["markers"] for c in collected if c["markers"]})
        outcomes = []
        for i in range(RUNS):
            r = run_pytest(p, timeout_s=SUITE_LIMIT_S)
            outcomes.append({k: v.outcome for k, v in r.outcomes.items()})
            rec.write("baseline_run", index=i, returncode=r.returncode, timed_out=r.timed_out,
                      wall_s=r.wall_s, cpu_s=r.cpu_s,
                      outcomes=outcomes[-1],
                      durations={k: v.duration_s for k, v in r.outcomes.items()},
                      tail=r.output_tail[-1500:] if r.returncode not in (0, 1) else None)
            print(f"{e.name} run {i}: rc={r.returncode} wall={r.wall_s:.1f}s tests={len(r.outcomes)}", flush=True)
        ids = set().union(*(o.keys() for o in outcomes))
        stable = sorted(t for t in ids if all(o.get(t) == "passed" for o in outcomes))
        varying = sorted(t for t in ids if len({o.get(t) for o in outcomes}) > 1)
        failing = sorted(t for t in ids if t not in varying and outcomes[0].get(t) in ("failed", "error"))
        excluded = any(o == {} for o in outcomes)
        rec.write("baseline_summary", stable_pass=stable, varying=varying, failing=failing,
                  skipped=sorted(t for t in ids if outcomes[0].get(t) in ("skipped", "xfailed")),
                  project_excluded=excluded)
        print(f"{e.name}: stable={len(stable)} varying={len(varying)} failing={len(failing)} excluded={excluded}", flush=True)
        rec.close()


if __name__ == "__main__":
    main()
