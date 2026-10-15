Deep audit of more-itertools finished and complete, with 12 minutes of budget. There was no test-suite-audit.toml, so the runner's discovery was used, and it looked right (765 tests). I assumed the 12-minute budget was acceptable inside the 20-minute limit. Nothing was edited. Run directory: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/more-itertools/.test-suite-audit/20261015T234141-92f1 (report.md, report.json).

**Baseline (Measured):** 765 tests passed in all 6 runs (3 file-order, 3 random-order). Median wall time was 9.1s. Coverage is 2229 of 2229 executable lines, so line coverage hides the gaps below.

**Mutation (Measured):**
- Deletion mutants: all 298 ran. 261 killed, 4 survived, 2 uncovered, 29 timed out, 2 invalid (observed rate 97.8%).
- Classical mutants: a seeded sample of 137 of 4439. 112 killed, 12 survived, 2 uncovered, 10 timed out, 1 invalid (observed rate 88.9%). This is a sample, not a measure of real bugs caught.

**Top findings, in report order:**
1. **Four deleted calls that no test noticed (Measured).**
   - `more.py:4215` `q.join()` (callback_iter._reader). Reproduce with `tsa replay --run <run dir> --mutant 2e4730d78e9d9498`.
   - `more.py:5547` `result.append(_concurrent_tee(iterator))` (concurrent_tee).
   - `more.py:2780` `cache.popleft()` (_islice_helper).
   - `more.py:877` `indices.sort()` (distinct_permutations).
   - Next step: assert the effect of each call if it is required behaviour.
2. **12 classical mutants survived, all in `more.py` (Measured).**
   - Examples: the error message in `product_index` (4468) and `combination_with_replacement_index` (4545), `side_effect` (1525), `padded` (1811), `numeric_range.__init__` (2326), `numeric_range.index` (2476), `_extract_monotonic` (5390) and `set_partitions` (3610).
   - These are candidate gaps, not proven bugs. Equivalent mutants need human review, and I did not judge any of them.
   - Reproduce with `tsa replay --run <run dir> --mutant 877c1d1ca97d2d3e`.
3. **Four uncovered mutants in `recipes.py`.** Two are call deletions in `_running_median_minheap_and_maxheap`, one is a string in `_flatten_tensor`, and one is a string in `_factor_pollard`. These came from `report.json`; I did not list them as untested items because the report gives no line numbers for them.
4. **Slowest tests (Measured).** `test_recipes.py::PrimeFunctionTests::test_primes` takes 4.96s, about half of the 9.1s wall time. Verify any speed-up with paired full-suite runs, because summed durations are not wall time.
5. **347 test pairs with coverage Jaccard >= 0.9 (Inferred).** For example, `ReplaceTests::test_basic` against five other ReplaceTests tests. Overlap is not evidence of redundancy, and the report does not show that any test is safe to delete.

**Flaky tests:** none observed in 6 runs (0 varied in file order, 0 failed only in random order). Not observed is not the same as stable: the approximate 95% upper bound on a test's failure rate is 50%.

**Not assessed:** the remaining 4302 classical mutants, and the 29 deletion and 10 classical timeouts. Mutation scope was `more_itertools/` only.

**Follow-ups I can offer:** replay the survivors, or draft assertions for the four deleted calls. I made no changes.

```json
{"untested": [
{"file": "more_itertools/more.py", "line": 4215, "behaviour": "callback_iter._reader q.join() can be deleted with no test failing"},
{"file": "more_itertools/more.py", "line": 5547, "behaviour": "concurrent_tee: appending _concurrent_tee(iterator) to result can be deleted with no test failing"},
{"file": "more_itertools/more.py", "line": 2780, "behaviour": "_islice_helper cache.popleft() can be deleted with no test failing"},
{"file": "more_itertools/more.py", "line": 877, "behaviour": "distinct_permutations indices.sort() can be deleted with no test failing"},
{"file": "more_itertools/more.py", "line": 2476, "behaviour": "numeric_range.index boundary check '> self._stop' changed to '>=' survives"},
{"file": "more_itertools/more.py", "line": 2326, "behaviour": "numeric_range.__init__ 'self._stop - self._start' changed to '+' survives"},
{"file": "more_itertools/more.py", "line": 3610, "behaviour": "set_partitions comparison '<= len(bk)' changed to '< len(bk)' survives"},
{"file": "more_itertools/more.py", "line": 1525, "behaviour": "side_effect with chunk_size: func(chunk) replaced by func(None) survives"},
{"file": "more_itertools/more.py", "line": 5390, "behaviour": "_extract_monotonic constant 0 changed to 1 survives"},
{"file": "more_itertools/more.py", "line": 4468, "behaviour": "product_index ValueError message text is never asserted"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run complete (all 298 deletion mutants, 137 of 4439 classical sampled); survivors are candidate gaps needing human review for equivalence. No flakiness observed in 6 runs and no test is supported as safely removable, since coverage overlap alone is not redundancy evidence."}
```
