The audit was partial and I have no mutation evidence, so all three lists are empty.

The 12-minute budget ran out after the baseline and coverage steps, with 0 of 298 deletion mutants and 0 classical mutants run.

**What was measured**
- **Baseline:** 765 tests passed in each of 3 file-order and 3 random-order runs. Median wall time was 9.1 s.
- **Flakiness:** nothing varied across the 6 runs. The 95% upper bound on any one test's failure rate is about 50%, so not observed does not mean stable.
- **Slowest tests:** `tests/test_recipes.py::PrimeFunctionTests::test_primes` takes 4.85 s, more than half the wall time.
- **Timing-sensitive tests:** `tests/test_more.py::TestConcurrentTee::test_concurrent_consumers` and `tests/test_more.py::TestSynchronized::test_concurrent_calls` use threads. I did not observe them failing.
- **Coverage:** the runner reports 2253 of 2287 lines covered, with 18 uncovered in `recipes.py` and 16 in `more.py`. It gives only counts, not line numbers. My own full-suite pytest-cov run showed 100% line coverage for both files, so I could not locate those lines and did not use them as findings.
- **Overlap:** 347 test pairs have coverage Jaccard of at least 0.9, for example the `ReplaceTests` and `DistinctPermutationsTests` groups. This is inferred, and overlap is not evidence of redundancy, so I am not proposing any deletions.

**Not assessed:** all mutation analysis. Next step is a longer run: `uv run --project /Users/timrichardson/Documents/projects/personal/test-suite-auditor/runner tsa deep . --budget-minutes 30`. The coverage step is the slow part and I could not shorten it.

**Assumptions:** deep mode with a 12-minute budget, and the runner's own discovery (source `more_itertools`, tests `tests`, `.venv` interpreter).

The report is in `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/more-itertools/.test-suite-audit/20261015T224609-30e6/` (`report.md`, `report.json`). My own coverage run wrote a temporary `.coverage` file, which I deleted.

```json
{"untested": [],
 "removable_tests": [],
 "flaky_tests": [],
 "notes": "Partial run: the 12-minute budget ended before any mutant ran, so there is no evidence on untested behaviour or removable tests. All 765 tests passed in 3 file-order and 3 random-order runs, so no flakiness was observed (not proof of stability); 347 high-overlap test pairs are inferred only and not grounds for deletion."}
```
