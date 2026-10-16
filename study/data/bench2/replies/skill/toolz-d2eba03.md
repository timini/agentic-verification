Verdict: gaps, but none from the change. All 4 mutants of the 4 changed lines in `toolz/itertoolz.py` were killed. The runner's only gap is that the suite is not green on a pristine checkout: `toolz/tests/test_package.py::test_has_version` fails there too. It is unrelated to `interpose`. I did not touch or work around it, and it is reported here.

Success criteria and the tests that check them:
- `interpose(el, [])` returns an empty result and does not raise StopIteration. Checked by `test_interpose_empty` (list, iterator, tuple and string inputs).
- The empty result is a real exhausted iterator. Checked by `test_interpose_empty_returns_exhausted_iterator`, which asserts `iter(r) is r` and that `next` raises StopIteration twice.
- The non-empty path is unchanged. Checked by `test_interpose_single_element` plus the existing `test_interpose`.

I confirmed the new tests pass with the change in place. I did not run them against the pre-change code to see them fail.

Other results:
- Changed lines uncovered: none (4 tests cover them).
- Surviving mutants: none.
- Runner note: running verify with path `toolz` gave "no change", so I reran with path `.`.
- Not assessed: the optional fresh-context review (step 5).
- Fast check: `python -m pytest toolz/tests/test_itertoolz.py`
- Report: `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench2/skill/toolz-d2eba03/.test-suite-audit/20261016T093823-9424/report.md`

Only `toolz/tests/test_itertoolz.py` was edited. The runner created the `.test-suite-audit/` directory in the repo.

```json
{"tests_added": ["toolz/tests/test_itertoolz.py::test_interpose_empty", "toolz/tests/test_itertoolz.py::test_interpose_empty_returns_exhausted_iterator", "toolz/tests/test_itertoolz.py::test_interpose_single_element"], "summary": "Added tests for interpose on empty inputs (list, iterator, tuple, string), the exhausted-iterator contract, and a single element. The runner killed 4 of 4 mutants of the changed lines; the verdict is 'gaps' only because the unrelated test_package.py::test_has_version already fails on a pristine checkout."}
```
