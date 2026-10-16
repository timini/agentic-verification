I added four tests to `TestDisableValidators` in `tests/test_validators.py`. They pass with the fix. With `src/attr/validators.py` stashed back to the original code, all four fail. `tests/test_validators.py` passes in full with the fix (166 tests); I didn't run the rest of the suite. The production file is unchanged and nothing is committed.

The tests cover:
- Nested `disabled()` contexts stay disabled until the outermost one exits.
- A `disabled()` entered while validators were already disabled leaves them disabled on exit.
- An error raised in an inner context restores the outer disabled state, and the outer context then restores the original state.
- A real class with `instance_of(int)` skips validation in both the inner and outer contexts, and validates again after they exit.

I also added `changelog.d/1513.change.md` as the news fragment.

```json
{"tests_added": ["tests/test_validators.py::TestDisableValidators::test_disabled_ctx_nested", "tests/test_validators.py::TestDisableValidators::test_disabled_ctx_restores_previous_state", "tests/test_validators.py::TestDisableValidators::test_disabled_ctx_nested_with_errors", "tests/test_validators.py::TestDisableValidators::test_disabled_ctx_nested_validation"], "summary": "Added four tests covering nesting, restoring a previously disabled state, nested error unwinding, and real validation behaviour around nested disabled() contexts. All four fail on the old code and pass with the fix."}
```
