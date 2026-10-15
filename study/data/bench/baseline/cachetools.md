Line coverage is 99% (338 tests pass), so the gaps are in assertions, not in unexecuted code. I ran 106 operator mutants (comparison flips, +/- swaps, `not` removal) over src/cachetools. Eight survived the non-threading tests, and I re-checked two of them against `tests/test_threading.py`. I restored all files and the workspace is clean per `git status`, apart from a `.coverage` file I generated.

Untested behaviour, strongest first:
1. `__init__.py:276` (`LFUCache.__touch`): the new link's count is `link.count + 1`. Changing it to `- 1` still passes, so a wrong frequency count is not caught.
2. `__init__.py:683-684` (`TLRUCache.expire`): the heap cleanup that drops removed items. Inverting the filter (keeping only removed items) passes. Changing the `>` threshold to `>=` also passes.
3. `__init__.py:606` (`TLRUCache._Item.__lt__`): changing it to `<=` passes, so heap ordering for equal expiry times is not checked.
4. `__init__.py:524` (`TTLCache.__iter__`): changing `time < expires` to `<=` passes, so iteration at the exact expiry boundary is not checked.
5. `_cachedmethod.py:418`: `wrapper.cache_lock` is `lock if lock is not None else cond`. Inverting that passes, so the exposed `cache_lock` attribute is not checked.
6. `_cachedmethod.py:135-136, 140-141` (deprecated `__call__` / `cache_clear` on the classmethod descriptor, Python 3.13+ path): never executed on 3.12.
7. `_cachedmethod.py:303-304` (`classmethod_wrapper`): never executed.
8. `__init__.py:524->526` (branch where the `TTLCache.__iter__` expiry check is false) and `92->90` (a `Cache.__setitem__` loop branch): neither branch is exercised.

Flaky tests: none found. I ran the full suite 6 times with pytest-randomly's random ordering and got 338 passed each time. The only wall-clock dependence is the `time.sleep(1.0)` calls in `tests/test_threading.py`. They make those tests slow (about 4 s of the 4.2 s run) but didn't fail.

Removable tests: none I would stand behind. The tests share mixins and run once per cache class, which looks repetitive but gives each class its own coverage. A possible trim is overlap between `test_pickle` and `test_pickle_maxsize` in `tests/test_lru.py` and `tests/test_rr.py`, which I did not verify.

Assumptions and limits: I excluded `tests/test_threading.py` from the mutation runs for speed. Two threading-related mutants (the `cond.wait_for` predicate in `_cached.py` and `_cachedmethod.py`) survived those runs. When I re-ran one of them with the full suite, it hung until I killed it, so I counted it as caught.

```json
{"untested": [
{"file": "src/cachetools/__init__.py", "line": 276, "behaviour": "LFUCache.__touch new link count is link.count + 1; changing to - 1 passes all tests"},
{"file": "src/cachetools/__init__.py", "line": 684, "behaviour": "TLRUCache.expire heap cleanup filter (drop removed items); inverting it passes"},
{"file": "src/cachetools/__init__.py", "line": 683, "behaviour": "TLRUCache.expire heap cleanup threshold (> vs >=) is not checked"},
{"file": "src/cachetools/__init__.py", "line": 606, "behaviour": "TLRUCache._Item.__lt__ ordering for equal expiry (< vs <=) is not checked"},
{"file": "src/cachetools/__init__.py", "line": 524, "behaviour": "TTLCache.__iter__ expiry boundary (time < expires vs <=) is not checked"},
{"file": "src/cachetools/_cachedmethod.py", "line": 418, "behaviour": "wrapper.cache_lock is lock if lock is not None else cond; inverting passes"},
{"file": "src/cachetools/_cachedmethod.py", "line": 135, "behaviour": "Deprecated classmethod descriptor __call__ and cache_clear (Python 3.13+ path) never executed"},
{"file": "src/cachetools/_cachedmethod.py", "line": 303, "behaviour": "classmethod_wrapper never executed"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Coverage is 99%, but 8 of 106 operator mutants survived the non-threading tests, so the gaps are weak assertions in the LFU, TLRU and TTL internals. All tests passed in 6 random-order runs; test_threading.py relies on sleep(1.0) but showed no failures."}
```
