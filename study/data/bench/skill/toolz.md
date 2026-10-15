Audit of toolz, deep mode. The run was complete (not partial) and used a 14-minute budget. I assumed the runner's auto-discovery was right, so I wrote no `test-suite-audit.toml`. Run dir: `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/toolz/.test-suite-audit/20261015T234140-4767` (`report.md` and `report.json` are inside it). The runner's stdout and stderr files were overwritten by a concurrent run in the shared scratchpad, so I read the report directly.

**Baseline (Measured):**
- 212 tests over 3 file-order runs and 3 random-order runs. 211 passed every time, 1 was skipped or xfailed, and none failed or varied.
- Coverage is 1266 of 1315 lines.
- The detection rate is K/(K+S+U), so it describes this mutant sample only, not real bugs.

| Population | Killed | Survived | Uncovered | Rate | Excluded |
|---|---|---|---|---|---|
| classical | 1204 | 182 | 88 | 81.7% | invalid 130, timeout 7 |
| deletion | 146 | 3 | 7 | 93.6% | invalid 13 |

**Candidate gaps (Measured; each needs a human look before anyone adds a test):**
1. Removing the body of `TlzLoader.create_module` in `tlz/_build_tlz.py` fails no test.
2. Deleting `obj.__dict__.update(userdict)` at `toolz/functoolz.py:389` fails no test. This is the call that restores a curry object's attributes on unpickling.
3. Deleting `dtemp.update(d)` at `toolz/dicttoolz.py:289` fails no test. The surrounding code is in `update_in`.
4. Some classical mutants survived:
   - The `'Input must be callable'` message text at `functoolz.py:202`.
   - `break` -> `return` at `functoolz.py:364`.
   - `<` -> `<=` at `dicttoolz.py:217`. This is a heuristic threshold in `dissoc`, so it may be equivalent and needs human review.
   - Mutants in `tlz/_build_tlz.py`: `'cytoolz'` -> `'XXcytoolzXX'` at line 58, and `partition` -> `rpartition` at line 48.
   - The `val = self.key(self.item)` mutant in `sandbox/core.py:77`.
   - 96 survivors are in `toolz/functoolz.py` alone.
5. Uncovered code: all of `toolz/compatibility.py`, parts of `functoolz.py` (lines 205, 597-598, 607-610, 631-649, 926) and `tlz/_build_tlz.py` (lines 34-36, 41-45, 70-71, 81).

**Removable tests (Inferred):** none I would stand behind. 100 test pairs have Jaccard >= 0.9 on covered lines, but overlap is not evidence of redundancy.

**Flaky tests:** none observed in 6 runs. With 6 runs without a failure, the approximate 95% upper bound on any one test's failure rate is 50%. Not observed is not stable.

**Slowest tests (Measured, 3 samples):** the slowest is `bench/test_join.py::test_many_to_many_large` at 0.21s. The whole suite takes 1.8s, so there is little to save.

**Reproduce:** `tsa replay --run <run dir above> --mutant 7075b3e4eb915528` (the deleted call in `dicttoolz.py:289`). Mutant `c20a3be42f05977c` reproduces finding 1.

**Not assessed:** whether each survivor is equivalent, the 130 invalid classical mutants, and anything outside the discovered source packages.

```json
{"untested": [
{"file": "toolz/functoolz.py", "line": 389, "behaviour": "curry unpickling restores instance __dict__ (obj.__dict__.update(userdict)); deleting it fails no test"},
{"file": "toolz/dicttoolz.py", "line": 289, "behaviour": "update_in copies the existing nested dict into the new container (dtemp.update(d)); deleting it fails no test"},
{"file": "tlz/_build_tlz.py", "line": 58, "behaviour": "tlz loader's cytoolz name/fallback logic; mutating the string literal fails no test"},
{"file": "tlz/_build_tlz.py", "line": 48, "behaviour": "TlzLoader name splitting (partition vs rpartition) is not checked"},
{"file": "tlz/_build_tlz.py", "line": 30, "behaviour": "TlzLoader.create_module body can be removed with all tests passing"},
{"file": "toolz/functoolz.py", "line": 364, "behaviour": "attribute-walking loop in curry/identity comparison: 'break' replaced by 'return' goes unnoticed"},
{"file": "toolz/functoolz.py", "line": 202, "behaviour": "error message text for non-callable input is not asserted"},
{"file": "toolz/dicttoolz.py", "line": 217, "behaviour": "dissoc 0.6 size-threshold boundary (< vs <=) is not tested; may be equivalent, needs human review"},
{"file": "toolz/sandbox/core.py", "line": 77, "behaviour": "key evaluation in the sandbox core (val = self.key(self.item)) can be replaced by None unnoticed"},
{"file": "toolz/compatibility.py", "line": 11, "behaviour": "compatibility module is almost entirely uncovered (lines 1-2, 8-15, 20-30)"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run completed in budget: classical detection rate 81.7% (1204 killed, 182 survived, 88 uncovered) and deletion rate 93.6%, both measured on samples only; no flaky tests seen in 3 file-order plus 3 random-order runs, and overlap findings are inferred so I am not recommending deletions."}
```
