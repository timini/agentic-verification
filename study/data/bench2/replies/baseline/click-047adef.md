I added tests in tests/test_basic.py that check help option names keep their declaration order. They fail on the old set-based code and pass with the change. I confirmed this by stashing core.py: 6 of 7 new tests failed against the old code. The full suite passes (1946 passed, 25 skipped, 1 xfailed). I did not touch production code or commit anything.

- `test_help_option_names_preserve_order` has six cases: declaration order, reversed order, duplicate names removed, a name reserved by a primary option, reserved by both a primary and a secondary option, and reserved by a secondary option of a `--a/--b` flag.
- `test_help_option_names_order_in_help_option` checks that the generated help option's `opts` keep the declared order.
- The `reserved-by-secondary` case still passes on the old code. The old code also removed secondary names, and it returned the survivors in an order that happened to match.
- I dropped a help-output test because the help formatter reorders option names itself, so output order can't show the change.

```json
{"tests_added": ["tests/test_basic.py::test_help_option_names_preserve_order[order]", "tests/test_basic.py::test_help_option_names_preserve_order[reversed-order]", "tests/test_basic.py::test_help_option_names_preserve_order[duplicates]", "tests/test_basic.py::test_help_option_names_preserve_order[reserved-by-opt]", "tests/test_basic.py::test_help_option_names_preserve_order[reserved-by-opt-and-secondary]", "tests/test_basic.py::test_help_option_names_preserve_order[reserved-by-secondary]", "tests/test_basic.py::test_help_option_names_order_in_help_option"], "summary": "Added parametrized tests that get_help_option_names preserves the declared order, drops duplicates, and excludes names reserved by params' opts and secondary_opts, plus a test that the help option's opts keep that order. They fail against the old set-based code (6 of 7) and pass with the change."}
```
