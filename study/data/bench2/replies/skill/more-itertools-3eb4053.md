The change is not fully verified. Verify's verdict is `gaps`: 18 of 19 mutants on the changed lines were killed, and I judge the one survivor to be behaviourally equivalent. All 3 changed executable lines are covered. The full suite (770 tests) passed on both baseline runs, one in file order and one in random order, with no flaky tests.

**Success criteria and the tests that check them**
- With `seekable(maxlen=0)`, `peek()` must not drop items, and `bool()` must still work. Existing tests `test_maxlen_zero_peek_does_not_drop_items` and `test_maxlen_zero_bool_does_not_drop_items` cover this.
- Repeated peeks must not grow storage, because the old code re-wrapped the source in a new `chain` on every peek. `test_maxlen_zero_repeated_peek_is_bounded` does 20,000 peeks and then iterates the rest.
- `peek(default)` and `peek()` on an empty or exhausted source must return the default or raise `StopIteration`. `test_maxlen_zero_peek_default_and_empty` covers this.
- Peeks interleaved with `next()` must leave the cache empty. `test_maxlen_zero_peek_interleaved_and_nothing_cached` covers this.
- `seek()` after a peek must work. `test_maxlen_zero_seek_after_peek` covers this.
- A plain iterator source must still work. `test_maxlen_zero_non_iterator_source` covers this.

I did not confirm that `test_maxlen_zero_repeated_peek_is_bounded` fails on the old code, since that would mean changing `more.py`. Its design relies on deeply nested `chain` wrappers failing; that is unconfirmed.

**What is left**
- The surviving mutant is `c7185a828317f468` at `more.py:3096`. It changes `maxlen == 0` to `(maxlen == 0) or True`, so every `seekable` wraps its source in `peekable`.
- I did not write a test for it. For `maxlen` of `None` or above 0, the extra wrapper does not change any result a caller can see, so I left it and did not try to kill it. This is my reasoning, not the runner's verdict.

**Fast check:** `python -m pytest tests/test_more.py` (22 tests cover the changed lines, about 0.1s).

**Report:** `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/more-itertools-3eb4053/.test-suite-audit/20261016T094503-d5fe/report.md`

The first run with the path `more_itertools` returned "no change", so I deleted its stray output and reran with `.`. I added the tests only to `tests/test_more.py`, did not touch `more.py`, and did not commit.

```json
{"tests_added": ["tests/test_more.py::SeekableTest::test_maxlen_zero_peek_default_and_empty", "tests/test_more.py::SeekableTest::test_maxlen_zero_repeated_peek_is_bounded", "tests/test_more.py::SeekableTest::test_maxlen_zero_peek_interleaved_and_nothing_cached", "tests/test_more.py::SeekableTest::test_maxlen_zero_seek_after_peek", "tests/test_more.py::SeekableTest::test_maxlen_zero_non_iterator_source"], "summary": "Added 5 SeekableTest tests for maxlen=0 peek behaviour (defaults, repeated peeks, interleaving, empty cache, seek). Verify killed 18 of 19 mutants; the survivor (always wrapping the source in peekable) has no caller-visible effect, so I left it."}
```
