Deep audit complete (not partial). I used the `test-suite-audit` skill in deep mode with a 12 minute budget. I assumed the runner's discovery was right: source `src/attr`, tests in `tests/`, interpreter `.venv`. The report is at `.test-suite-audit/20261015T224550-dbc5/report.md` and `report.json` in the workspace. The run only wrote to `.test-suite-audit/`.

**Baseline (measured):** 1386 tests, 1377 passed in every run, 9 skipped or xfailed, 0 failed, 0 varied. Median wall time was 4.3s over 3 runs. Line coverage was 1816 of 1831 executable lines.

**Flakiness (measured):** Three file-order and three random-order runs showed no test that varied or failed. I list no flaky tests. Not observed is not proof of stable: with 6 runs the 95% upper bound on a test's failure rate is about 50%.

**Mutation (measured; sample only):**

| Population | Killed | Survived | Uncovered | Rate | Excluded |
|---|---|---|---|---|---|
| deletion | 220 | 9 | 7 | 93.2% | invalid 106, timeout 2 |
| classical | 74 | 11 | 7 | 80.4% | invalid 29 |

- All 344 deletion mutants ran. Classical mutants were a seeded sample of 121 of 3918.
- Surviving mutants are candidate gaps, not proven bugs. I did not judge any as equivalent; each needs human review.
- The strongest findings are deleted calls that no test noticed. Eight call statements were deleted with covering tests staying green:
  - `_make.py:2386` (`BaseException.__init__` line in the generated exception init)
  - `_make.py:473` and `_make.py:497` (setting `alias_is_default`)
  - `_make.py:581` (frozen `__delattr__`)
  - `_make.py:1656` and `_make.py:1730` (generated method lines)
  - `_cmp.py:98` (`_check_same_type` requirement)
  - `validators.py:398` (`mapping_validator` call in `_DeepMapping`)
- Surviving classical mutants include:
  - `_make.py:1566`: the `__replace__` own-attribute check.
  - `_make.py:2555`: the `alias is None if alias_is_default is None` logic.
  - `_make.py:3396`: the `and` to `or` change in the Python 3.11 note check.
  - `_make.py:1427`: the `repr_ns` deprecation message.
  - `_make.py:1836`: the `"NOTHING"` string.
- Seven deletion mutants were uncovered, in `_add_eq`, `_add_hash`, `_create_slots_class`, `add_replace`, `field`, `_IsCallableValidator.__call__` and `cmp_using`.

**Removable tests (inferred only):** The report found 32265 test pairs with coverage Jaccard >= 0.9, for example in `TestEvolve`, `TestAsTuple` and the `test_frozen_slots_combo` parametrisations. Overlap alone is not evidence of redundancy, and I did not compare kill sets on a frozen mutant sample. I would not delete any test on this basis, so that list is empty. The slowest test is 0.27s, so deleting tests would save almost nothing.

**Not assessed:** Most classical mutants (3797 of 3918 not run). Redundancy was not tested by comparing kill sets. Speed-ups from deleting tests were not measured with paired wall-time runs.

**To reproduce a finding:**
`tsa replay --run /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/attrs/.test-suite-audit/20261015T224550-dbc5 --mutant 1f9dedd7d6f951e3`

The mutant ids for the other findings are in `report.json`; I did not print them all.

```json
{"untested": [
{"file": "src/attr/validators.py", "line": 398, "behaviour": "_DeepMapping calls mapping_validator on the whole mapping; deleting the call fails no test"},
{"file": "src/attr/_make.py", "line": 581, "behaviour": "Frozen exception __delattr__ delegates to BaseException.__delattr__; deleting the call fails no test"},
{"file": "src/attr/_cmp.py", "line": 98, "behaviour": "cmp_using registers the _check_same_type requirement; deleting it fails no test"},
{"file": "src/attr/_make.py", "line": 1566, "behaviour": "__replace__ own-attribute check; passing None for the class survives"},
{"file": "src/attr/_make.py", "line": 2555, "behaviour": "Alias default logic (alias is None if alias_is_default is None); mutation survives"},
{"file": "src/attr/_make.py", "line": 473, "behaviour": "Setting alias_is_default=True on attributes (also line 497); deleting the call fails no test"},
{"file": "src/attr/_make.py", "line": 2386, "behaviour": "Generated exception __init__ calling BaseException.__init__(self, vals); deleting it fails no test"},
{"file": "src/attr/_make.py", "line": 3396, "behaviour": "Python 3.11 note check (and changed to or); mutation survives"},
{"file": "src/attr/_make.py", "line": 1427, "behaviour": "repr_ns deprecation warning message content is never asserted"},
{"file": "src/attr/_make.py", "line": 1836, "behaviour": "The 'NOTHING' string used in generated code is not checked; mutation survives"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run completed: 1386 tests were stable across 6 baseline runs (3 file-order, 3 random-order). All 344 deletion mutants and 121 of 3918 classical mutants ran (deletion detection 93.2%, classical 80.4%). Survivors are candidate gaps needing human review; coverage overlap was not treated as evidence for deleting tests."}
```
