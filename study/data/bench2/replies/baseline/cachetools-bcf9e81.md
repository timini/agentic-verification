I added two tests to `tests/test_rr.py`. The full suite passes with the change (339 passed). Both new tests fail against the original `popitem`, which I checked by stashing the `src` change temporarily and then restoring it. I made no production edits and no commits.

- **`test_rr_popitem_empty_choice_not_called`**: uses a choice function that raises `ValueError` on an empty sequence and records its calls. `popitem()` on an empty cache must raise `KeyError` without calling choice. It checks this on a fresh cache, after popping the last item, and after `clear()`.
- **`test_rr_popitem_choice_error_propagates`**: a choice function that raises `IndexError` on a non-empty cache must propagate the error unchanged and leave the item in the cache. The old code turned that `IndexError` into `KeyError`.

```json
{"tests_added": ["tests/test_rr.py::RRCacheTest::test_rr_popitem_empty_choice_not_called", "tests/test_rr.py::RRCacheTest::test_rr_popitem_choice_error_propagates"], "summary": "Added tests that popitem on an empty RRCache raises KeyError without calling a strict choice function (fresh, drained and cleared cache), and that a choice error on a non-empty cache propagates unchanged. Both fail on the pre-change code and pass with the change."}
```
