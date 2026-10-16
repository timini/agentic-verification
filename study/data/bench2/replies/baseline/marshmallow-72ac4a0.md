I added tests for the boolean rejection in `from_timestamp_ms`. They pass with the change applied. With the production change stashed, the four `timestamp_ms` boolean tests fail, so they do catch the regression. I restored the change afterwards (`git diff --stat` shows `utils.py` modified again).

Edits in `tests/test_deserialization.py` and `tests/test_utils.py`; `src/marshmallow/utils.py` is untouched:
- **`test_deserialization.py`:** I added `True` and `False` to the `in_value` parametrization of `test_invalid_timestamp_field_deserialization`. That covers both the `timestamp` and `timestamp_ms` formats through `DateTime`.
- **`test_utils.py`:** I added `test_from_timestamp_rejects_booleans`, `test_from_timestamp_ms` and `test_from_timestamp_ms_rejects_booleans`. `test_from_timestamp_ms` has int, float and string happy-path cases.

The `-k timestamp` run gave 39 passed with the change. I did not run the full suite.

```json
{"tests_added": ["tests/test_deserialization.py::TestFieldDeserialization::test_invalid_timestamp_field_deserialization[True-timestamp_ms]", "tests/test_deserialization.py::TestFieldDeserialization::test_invalid_timestamp_field_deserialization[False-timestamp_ms]", "tests/test_deserialization.py::TestFieldDeserialization::test_invalid_timestamp_field_deserialization[True-timestamp]", "tests/test_deserialization.py::TestFieldDeserialization::test_invalid_timestamp_field_deserialization[False-timestamp]", "tests/test_utils.py::test_from_timestamp_rejects_booleans", "tests/test_utils.py::test_from_timestamp_ms", "tests/test_utils.py::test_from_timestamp_ms_rejects_booleans"], "summary": "Added boolean rejection tests for from_timestamp_ms at both the utils level and the DateTime field level, plus happy-path coverage for from_timestamp_ms. The four timestamp_ms boolean tests fail without the production change and pass with it."}
```
