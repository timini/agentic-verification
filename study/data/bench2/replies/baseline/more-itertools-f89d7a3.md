I added six tests to `IchunkedTests` in tests/test_more.py (in the work directory, nothing committed). All pass with the change. With the production change stashed, 10 tests in the class fail, covering all six new tests. The only change to more_itertools/more.py is the original uncommitted diff, which I restored after the stash.

The existing tests only covered n=0 on an empty iterable and n=-1 on an infinite one, so they missed these cases:
- **n=0 on non-empty and infinite input:** the result is empty and the call doesn't hang.
- **n=0 and the source iterator:** nothing is consumed from it.
- **n=0 versus `chunked`:** the results match.
- **Negative n:** it raises `ValueError('n must be at least 0')`, and does so even for an empty iterable, which previously yielded nothing.
- **Negative n versus `chunked`:** the error messages match.

```json
{"tests_added": ["tests/test_more.py::IchunkedTests::test_zero_nonempty", "tests/test_more.py::IchunkedTests::test_zero_matches_chunked", "tests/test_more.py::IchunkedTests::test_zero_does_not_consume", "tests/test_more.py::IchunkedTests::test_negative_message", "tests/test_more.py::IchunkedTests::test_negative_empty_iterable", "tests/test_more.py::IchunkedTests::test_negative_matches_chunked"], "summary": "Added six tests covering ichunked with n=0 on non-empty, infinite and partly consumed iterators, and with negative n on empty and non-empty input, including the error message and parity with chunked. All pass with the change, and 10 ichunked tests fail when it is reverted."}
```
