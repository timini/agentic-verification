I added six tests to `SeekableTest` in tests/test_more.py. All 22 seekable tests pass with the change. With the production change stashed, only `test_maxlen_zero_many_peeks_bounded` fails. The other five pass on both versions, so they only pin behaviour that the change must not break. I did not touch `more.py` and did not commit.

- **`test_maxlen_zero_many_peeks_bounded`:** runs 20000 peek-then-next cycles with `maxlen=0` and checks that `_source` is the same object throughout and `_cache` stays empty. On the old code the source gets wrapped in a new `chain` on every peek, so this fails there.
- **`test_maxlen_zero_peek_default`:** checks the default value and `StopIteration` on an empty source, and after the source is exhausted.
- **`test_maxlen_zero_interleaved_peek_next`:** mixes peeks and nexts and checks the order and that `elements()` is empty.
- **`test_maxlen_zero_peek_keeps_cache_empty`:** checks `elements()`, `_cache` and `_index` after a peek.
- **`test_maxlen_zero_peek_lazy`:** checks that peeking twice consumes only one item from the source.
- **`test_maxlen_nonzero_peek_unchanged`:** guards the `maxlen=2` peek path.

```json
{"tests_added": ["tests/test_more.py::SeekableTest::test_maxlen_zero_many_peeks_bounded", "tests/test_more.py::SeekableTest::test_maxlen_zero_peek_default", "tests/test_more.py::SeekableTest::test_maxlen_zero_interleaved_peek_next", "tests/test_more.py::SeekableTest::test_maxlen_zero_peek_keeps_cache_empty", "tests/test_more.py::SeekableTest::test_maxlen_zero_peek_lazy", "tests/test_more.py::SeekableTest::test_maxlen_nonzero_peek_unchanged"], "summary": "Added six seekable tests covering maxlen=0 peek: default and exhaustion, interleaved peek and next, an empty cache, lazy consumption, and a non-zero maxlen guard. One test (many peeks keep the source object stable and the cache empty) fails on the pre-change code and passes with the change."}
```
