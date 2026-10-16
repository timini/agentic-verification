I added four tests to tests/test_items.py, covering both new `ValueError` checks (`Item.comment` and `Array.add_line`). All 94 tests in that file pass. I did not run the new tests against the pre-change `items.py`, so I haven't confirmed that the rejection tests fail without the production change.

- **`add_line`:** it raises `ValueError` (message contains "line breaks") for comments containing `\n`, `\r`, `\r\n`, a bare `\n`, or `# a\nkey = 1`. After the failure the array is still empty and renders as `[]`. A single-line comment still works.
- **`Item.comment`:** it rejects the same inputs on an int, a string, an array and an inline table. The trivia comment stays empty after the failure. Single-line comments, with and without a leading `#`, still work, and a comment on a parsed document item still appears in the output.

```json
{"tests_added": ["tests/test_items.py::test_array_add_line_rejects_line_breaks_in_comment", "tests/test_items.py::test_array_add_line_accepts_single_line_comment", "tests/test_items.py::test_item_comment_rejects_line_breaks", "tests/test_items.py::test_item_comment_single_line_still_works"], "summary": "Added parametrized tests that Item.comment and Array.add_line raise ValueError for comments containing \\n or \\r (with state left unchanged), plus tests that single-line comments still work. All tests in tests/test_items.py pass."}
```
