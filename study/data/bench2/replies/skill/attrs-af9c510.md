Verdict: verified, but the runner generated 0 mutants for the changed lines, so "all killed" is vacuous. I did not assess mutants by hand.

Success criteria and the tests that check them:
- Nesting keeps validators disabled until the outermost `disabled()` exits: `test_disabled_ctx_nested`.
- A previously disabled state is restored on exit, including when an error is raised: `test_disabled_ctx_restores_previous_disabled_state`.
- An error in an inner context restores the outer context's disabled state: `test_disabled_ctx_nested_with_errors`.

The 3 new tests pass with the change. With `src/attr/validators.py` stashed (original code), all 3 fail. The 6 other `disabled` tests passed in both runs. The change is restored, and I did not edit production code.

Verify run: 2 changed executable lines, all run under tests. 5 tests cover them (fast check: `python -m pytest tests/test_validators.py`). The report's other two findings are about slow tests and overlapping tests, not this change.

Not done: I did not add a changelog fragment, and no mutants were available to replay. The runner needs a project directory as its path, not a file.

Files:
- Report: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/attrs-af9c510/.test-suite-audit/20261016T093735-d640/report.md
- Tests: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/attrs-af9c510/tests/test_validators.py

```json
{"tests_added": ["tests/test_validators.py::TestDisableValidators::test_disabled_ctx_nested", "tests/test_validators.py::TestDisableValidators::test_disabled_ctx_restores_previous_disabled_state", "tests/test_validators.py::TestDisableValidators::test_disabled_ctx_nested_with_errors"], "summary": "Added three tests for nested and pre-disabled validators.disabled() contexts, including error paths. All three fail on the original code and pass with the change; verify reports 'verified' with 0 mutants generated on the changed lines."}
```
