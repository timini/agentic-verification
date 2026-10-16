"""H8: do jointly chosen removal sets keep their detection on held-out mutants?

``deep`` proposes a removal set; ``prune-check --from-run`` then runs mutants the audit did not use.
"""

import json
import sys
import tempfile
from pathlib import Path

from harness import corpus
from harness.records import Recorder
from tsa.audit import run_audit
from tsa.config import AuditConfig
from tsa.report.write import write

DEEP_MIN = 20
PRUNE_MIN = 20
WORKERS = 4


def main() -> None:
    for e in corpus.load(sys.argv[1:] or None):
        rec = Recorder("e8_prune", e)
        cfg = AuditConfig(e.project(), workers=WORKERS)
        with tempfile.TemporaryDirectory(prefix="e8-") as tmp:
            out = Path(tmp)
            deep = run_audit(cfg, "deep", DEEP_MIN, None, out / "deep", progress=lambda m: None)
            write(deep)
            rec.write("deep", status=deep.status, efficacy=deep.efficacy, baseline=deep.baseline,
                      mutation={k: v for k, v in deep.mutation.items() if k != "results"},
                      results=deep.mutation.get("results", []))
            removed = deep.efficacy.get("removal_candidates", [])
            if not removed:
                rec.write("prune", verdict="no candidates")
                rec.close()
                continue
            used = frozenset(r["mutant_id"] for r in deep.mutation.get("results", []))
            pr = run_audit(cfg, "prune-check", PRUNE_MIN, None, out / "prune", progress=lambda m: None,
                           removed=removed, exclude_ids=used)
            write(pr)
            rec.write("prune", status=pr.status, prune=pr.prune, results=pr.mutation.get("results", []),
                      tests_total=len(deep.stable), durations=deep.durations)
            print(e.name, len(removed), "candidates:", pr.prune.get("verdict"), json.dumps(
                {k: pr.prune.get(k) for k in ("mutants_run", "mutants_killed", "coverage_lost_lines")}), flush=True)
        rec.close()


if __name__ == "__main__":
    main()
