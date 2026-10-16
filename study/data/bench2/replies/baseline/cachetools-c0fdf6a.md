I added five tests to `tests/test_tlru.py`. The full suite passes with the fix (295 passed). With the fix stashed, three of the five fail on the old code, as they should. The other two pass on the old code too, because they don't depend on the fix. They are edge-case guards: one checks a missing key, the other a key whose old entry had already expired. I restored the fix afterwards and left `src/cachetools/__init__.py` unmodified.

- `test_tlru_setitem_expired_removes_existing`: an expired overwrite evicts the old value. It checks `in`, `len`, `currsize`, iteration, `items`, `get`, `del`, and that other keys are untouched.
- `test_tlru_setitem_expired_missing_key`: an expired assignment to a missing key stores nothing.
- `test_tlru_setitem_expired_then_reinsert`: after the eviction the key can be stored again and then expires normally, so the heap and items stay consistent.
- `test_tlru_setitem_expired_existing_already_expired`: the existing entry has already expired but not yet been purged.
- `test_tlru_setitem_expired_getsizeof`: `currsize` is decremented correctly when `getsizeof` is used.

```json
{"tests_added": ["tests/test_tlru.py::TLRUCacheTest::test_tlru_setitem_expired_removes_existing", "tests/test_tlru.py::TLRUCacheTest::test_tlru_setitem_expired_missing_key", "tests/test_tlru.py::TLRUCacheTest::test_tlru_setitem_expired_then_reinsert", "tests/test_tlru.py::TLRUCacheTest::test_tlru_setitem_expired_existing_already_expired", "tests/test_tlru.py::TLRUCacheTest::test_tlru_setitem_expired_getsizeof"], "summary": "Added five TLRUCache tests for overwriting an existing key with an already-expired value, covering eviction, size accounting, re-insertion and iteration. Three fail on the old code and all pass with the fix."}
```
