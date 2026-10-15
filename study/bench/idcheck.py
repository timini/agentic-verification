import time
from harness import corpus
from harness.records import read_all
from experiments.common import mutants
for e in corpus.load():
    t = time.time()
    ids = {m.id for m in mutants(e)}
    dt = time.time() - t
    rec = {r["mutant"]["id"] for r in read_all("e2_budget", e.name) if r["kind"] == "mutant_result"}
    rec = {i for i in rec}
    missing = len(rec - ids)
    print(f"{e.name}: generated {len(ids)} in {dt:.1f}s; study ids {len(rec)}; missing {missing}", flush=True)
