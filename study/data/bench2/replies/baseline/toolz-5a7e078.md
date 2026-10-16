I added two tests to `toolz/tests/test_itertoolz.py`. The full file passes (52 tests); I didn't run the rest of the suite. I made no changes to `toolz/itertoolz.py`.

I also added a small `_BadLen` helper class (an iterable with a settable `__len__`) and an `import pytest` line, if one wasn't already there.

- **`test_partition_all_correct_len`:** accurate `__len__` values still partition correctly, for several `n`.
- **`test_partition_all_invalid_len`:** inaccurate `__len__` values raise `LookupError`. The cases are length too large, too small, claiming no remainder, claiming a remainder longer than the last chunk, and a length that is a multiple of `n` while the data is not.

```json
{"tests_added": ["toolz/tests/test_itertoolz.py::test_partition_all_correct_len", "toolz/tests/test_itertoolz.py::test_partition_all_invalid_len"], "summary": "Added tests that partition_all gives correct output for accurate __len__ and raises LookupError for several kinds of inaccurate __len__ (too large, too small, multiple of n, remainder mismatch). All tests in test_itertoolz.py pass."}
```
