Verdict: verified. The runner killed 9 of 9 mutants on the 4 changed executable lines, and every changed line is covered.

Success criteria for `ichunked`:
- `n == 0` yields no chunks, as `chunked` does, including for non-empty and infinite iterables, and without consuming the input. Checked by `test_zero_nonempty`, `test_zero_infinite` and `test_zero_consumes_nothing`.
- `n < 0` raises `ValueError('n must be at least 0')`, as `chunked` does, including for an empty iterable. Checked by `test_negative_nonempty`, `test_negative_empty_iterable` and `test_negative_matches_chunked`.
- `n == 1` is unchanged. Checked by `test_one`.

Tests were added to `IchunkedTests` in `tests/test_more.py`. All 14 `ichunked` tests pass.

The runner flagged the existing `test_negative` as catching none of the change's mutants. It is not one of my tests, and I left it unchanged. The new negative tests cover those mutants.

I did not check whether the new tests fail on the unchanged code. I ran the runner against the working tree only.

Surviving mutants: none. Not assessed: `n=None`. It raises `TypeError` either way.

Fast check command from the report: `python -m pytest tests/test_more.py`

Report: `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/more-itertools-f89d7a3/.test-suite-audit/20261016T093739-5b5c/report.md`

My first runner call used `more_itertools` as the path and returned "no change". Rerunning with `.` as the path worked. I removed the stray output directory from that first call.

```json
{"tests_added": ["tests/test_more.py::IchunkedTests::test_zero_nonempty", "tests/test_more.py::IchunkedTests::test_zero_infinite", "tests/test_more.py::IchunkedTests::test_zero_consumes_nothing", "tests/test_more.py::IchunkedTests::test_negative_nonempty", "tests/test_more.py::IchunkedTests::test_negative_empty_iterable", "tests/test_more.py::IchunkedTests::test_negative_matches_chunked", "tests/test_more.py::IchunkedTests::test_one"], "summary": "Added 7 ichunked tests covering n=0 (non-empty, infinite, nothing consumed), negative n (message, empty input, parity with chunked) and n=1. The verify runner reports verified, with 9 of 9 mutants killed and all changed lines covered."}
```
