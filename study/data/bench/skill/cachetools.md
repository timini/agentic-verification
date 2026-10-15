Audit of cachetools, deep mode with a 14-minute budget (below the 30-minute default, to fit the 20-minute limit). The run completed in full, with no partial steps. I assumed the runner's auto-discovery was correct and wrote no config. Full report: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/cachetools/.test-suite-audit/20261016T000221-1f0b/report.md (and report.json in the same folder).

**Baseline and flakiness (Measured)**
- 338 tests passed in all 6 runs (3 in file order, 3 in random order), with 0 failures and 0 varying.
- A clean result from 6 runs only bounds a test's failure rate at about 50% (95% upper bound). Not observed is not the same as stable.
- The 4 slowest tests, at about 1.0s each, are in tests/test_threading.py (`test_cachedmethod_locked`, `test_cached_locked`, `test_cached_stampede`, `test_cachedmethod_stampede`). They are slow but did not vary, so I do not list them as flaky.

**Coverage (Measured)**
- 1092 of 1098 executable lines are covered.
- The uncovered lines are in src/cachetools/_cachedmethod.py: 135-136, 140-141 and 303-304.

**Mutation results (Measured)**

| Population | Killed | Survived | Uncovered | Detection rate |
|---|---|---|---|---|
| Deletion (all 223 ran) | 163 | 14 | 4 | 90.1% |
| Classical (1531 sampled) | 1187 | 193 | 109 | 79.7% |

- The rate applies to these samples only, not to real bugs caught.
- Survivors are candidate gaps, not proven bugs. I have not judged whether any is an equivalent mutant; those need human review.

**Findings, in report order**
1. Candidate pseudo-tested function: `_HashedTuple.__getstate__` in src/cachetools/keys.py. Every body replacement ran and survived.
   - Reproduce: `tsa replay --run <run dir> --mutant c52cff947c1c87b0`
2. 13 deletable calls whose removal no test catches (details in the JSON below). These include `self.expire(time)` at several points in `TTLCache` and `TLRUCache`, `link.unlink()`, the `.clear()` calls and `pending.remove(k)`.
   - Reproduce: `tsa replay --run <run dir> --mutant 66121c8bddc9e146`
3. 193 surviving classical mutants, mostly in `__init__.py` (79) and `_cachedmethod.py` (74).
   - Examples: `func(*args, **kwargs)` changed to `func(*args, )` in `_cached.py` lines 136 and 160, and `RRCache(maxsize, choice)` changed to `RRCache(maxsize, None)` in `func.py:88`.
   - Reproduce: `tsa replay --run <run dir> --mutant 2688c07f30f3e80d`
4. 167 test pairs have near-identical line coverage (Inferred). Overlap is not evidence that a test is redundant, so I name no tests as removable.

**Not assessed or not supported**
- The report gives no evidence for deleting any test. I list none, and I did not time a paired suite run.
- Flakiness beyond 6 runs is not assessed.
- Whether the surviving mutants are equivalent is not assessed.

**Follow-ups I can offer, not done:**
- Write assertions for the `expire` calls and the `clear` side effects.
- Re-run flakiness with more repeats on the threading tests.

```json
{"untested": [
{"file": "src/cachetools/__init__.py", "line": 703, "behaviour": "TTLCache.popitem calls self.expire(time) first; removing it keeps all tests green (expired items could be returned)"},
{"file": "src/cachetools/__init__.py", "line": 636, "behaviour": "expire(time) call in TTLCache lookup/item access path can be deleted without any test failing"},
{"file": "src/cachetools/__init__.py", "line": 505, "behaviour": "link.unlink() when a TTLCache key is re-set; skipping it leaves stale link ordering unchecked"},
{"file": "src/cachetools/__init__.py", "line": 685, "behaviour": "heapq.heapify(order) after TLRUCache heap cleanup is not checked; heap order after cleanup is untested"},
{"file": "src/cachetools/__init__.py", "line": 368, "behaviour": "self.__index.clear() in LFUCache/RRCache clear() is not verified"},
{"file": "src/cachetools/__init__.py", "line": 266, "behaviour": "LRUCache.clear() resetting self.__links is not verified"},
{"file": "src/cachetools/_cached.py", "line": 169, "behaviour": "pending.remove(k) in the stampede-protection finally block of @cached is not verified (stale pending keys)"},
{"file": "src/cachetools/_cachedmethod.py", "line": 294, "behaviour": "pending.remove(k) in the @cachedmethod stampede-protection path is not verified"},
{"file": "src/cachetools/_cachedmethod.py", "line": 135, "behaviour": "Python 3.13 classmethod __call__/cache_clear compatibility wrappers (lines 135-136, 140-141) are never executed"},
{"file": "src/cachetools/func.py", "line": 88, "behaviour": "rr_cache passes the choice argument to RRCache; replacing it with None is not detected"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run completed (14 min budget): 338 tests passed in 6 runs with no variation, so no flaky tests were observed (bound is only about 50%). The report gives no evidence for deleting tests, since coverage overlap is not redundancy, and the untested items are candidate gaps from surviving deletion mutants plus uncovered lines."}
```
