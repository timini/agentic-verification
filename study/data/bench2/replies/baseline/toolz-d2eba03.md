I added two tests to toolz/tests/test_itertoolz.py. `test_interpose_empty` fails on the original code with StopIteration and passes with the fix. `test_interpose_single` passes both ways, so it only guards the one- and two-element cases against regression.

- **`test_interpose_empty`:** `interpose` on an empty list, iterator, tuple and string returns an empty result. The result is itself an iterator and is exhausted immediately.
- **`test_interpose_single`:** one-element and two-element inputs give `[1]` and `[1, 'a', 2]`.

I checked the first by stashing the production change and rerunning the interpose tests. With the fix restored, all three interpose tests pass. I did not touch toolz/itertoolz.py and did not commit.

```json
{"tests_added": ["toolz/tests/test_itertoolz.py::test_interpose_empty", "toolz/tests/test_itertoolz.py::test_interpose_single"], "summary": "Added tests for interpose on empty inputs (list, iterator, tuple, string) that fail with StopIteration without the fix and pass with it, plus single and two-element regression tests."}
```
