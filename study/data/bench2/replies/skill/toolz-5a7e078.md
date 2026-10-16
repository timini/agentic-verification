Verdict from the runner: `gaps`. All 11 mutants of the 4 changed lines in `toolz/itertoolz.py` are killed. The only open gap is a failure that already exists. `toolz/tests/test_package.py::test_has_version` fails on a pristine checkout, which makes the runner call the suite "not green". I did not touch it.

**Success criteria and the tests that check them**
- `partition_all` raises `LookupError` when `len(seq)` disagrees with the real item count. The new test covers a claimed length too short (`range(5)` claims 4, 7), and too long (`range(4)` claims 3, 5, 6). Together these reach both branches of the new condition, including the `end == 0` case.
- The error message is the one the change specifies. The test matches it exactly.
- Correct lengths still give the right chunks. The test covers `range(5)` and `range(4)` with n=3, `range(7)` with n=3, and `range(4)` with n=2.

**Mutants**
- The first runner pass killed 7 of 11. The 4 survivors all changed the error message text, or replaced the message with `None`.
- I added an exact-message `pytest.raises(..., match=...)` assertion. A second runner pass killed 11 of 11.
- I did not run `replay --all`. The runner's own rerun is the evidence.
- The message contains the typo "parition_all", which comes from the production code. The test asserts that text as written, so fixing the typo means updating the test too.
- Every changed line is covered. Nothing is left for you to judge as an equivalent mutant.

**Files changed**
- I changed only `toolz/tests/test_itertoolz.py`: a new `test_partition_all_invalid_len` and an `import pytest`.
- `toolz/tests/test_itertoolz.py` now has 51 passing tests.
- The runner wrote its output to `.test-suite-audit/` inside the repo.

**Fast check:** `python -m pytest toolz/tests/test_itertoolz.py`

**Report:** `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/toolz-5a7e078/.test-suite-audit/20261016T093844-e082/report.md`

```json
{"tests_added": ["toolz/tests/test_itertoolz.py::test_partition_all_invalid_len"], "summary": "Added a test that partition_all raises LookupError (with the exact message) for sequences whose __len__ is too short or too long, and still partitions correctly when the length is right. The runner killed 11 of 11 mutants of the changed lines; the verdict stays 'gaps' only because test_package.py::test_has_version already fails on a pristine checkout."}
```
