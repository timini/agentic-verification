Audit of marshmallow: complete (deep mode, 12 min cap, assumed to fit the 20 min limit). The run used 3 file-order and 3 random-order baselines, coverage, all 358 deletion mutants, and 1657 of 2794 classical mutants as a seeded sample. Report: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/marshmallow/.test-suite-audit/20261015T234651-6ef6/report.md (and report.json). I changed no source or tests.

**Baseline**
- 1192 tests; 1186 passed in every run and the rest were skipped or xfailed.
- 1813 of 1856 executable lines are covered.

**Untested behaviour (Measured, candidate gaps, not proof of bugs)**
- 4 functions keep passing with their body replaced, and each replacement ran: `utils.is_generator`, `Context.__exit__`, `Validator._repr_args` (validate.py:35), and `Constant._validate_missing` (fields.py:2133).
- 9 call statements can be deleted with every test still passing, including:
  - schema.py:447 `messages.update(self.error_messages or {})`
  - schema.py:941 `self.handle_error(...)`
  - schema.py:153 `super().__init__(name, bases, attrs)`
  - fields.py:724 `self._test_collection(value)`
  - fields.py:791 appending `error.valid_data`
  - fields.py:2044 `super()._bind_to_schema(...)`
  - validate.py:78 `kwargs.update(err.kwargs)`
  - context.py:62 `_CURRENT_CONTEXT.reset(...)`
- 197 classical mutants survived, mostly in fields.py (73), schema.py (69) and validate.py (26). Examples are fields.py:629 (`schema.many or self.many` changed to `and`), fields.py:1663 (`not self.value_field` negation dropped) and schema.py:219. Whether a given survivor matters, or is equivalent, needs human review.
- Detection rate (killed over killed, survived and uncovered; it describes this sample only, not real bugs caught): 81.7% for classical mutants and 94.2% for deletion mutants. They are reported separately.
- Uncovered lines: orderedset.py lines 60-89 (mostly), plus a few in fields.py, schema.py, validate.py and class_registry.py.

**Removable tests:** none. 8217 test pairs have near-identical coverage (Inferred), but overlap is not evidence of redundancy, so I would not delete any on that basis.

**Flaky tests:** none observed. No test varied across the 6 baseline runs. Not observed is not stable: with 6 clean runs, the approximate 95% upper bound on a test's failure rate is 50%.

**Test IDs that change between runs:** `tests/test_deserialization.py::TestFieldDeserialization::test_invalid_datetime_deserialization` has parametrize IDs containing the current time. The IDs differ every run, so these cases are excluded from mutation scope. This is an ID problem, not a failure flake. The fix is fixed `pytest.param(..., id=...)` values.

**Not assessed**
- Any classical mutants outside the sample (1137 of 2794).
- Equivalence of survivors.
- Real speed-up from removing tests (no paired wall-time runs).
- Median wall time was 1.5s.

**Reproduce a finding:** `tsa replay --run /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/marshmallow/.test-suite-audit/20261015T234651-6ef6 --mutant 5cfb44b6f32c59fd` (a deleted call). Mutant `7bbbc686e9ec8ae1` reproduces a classical survivor.

**Possible follow-ups:** add assertions for the 9 deleted calls and 4 pseudo-tested functions, or fix the datetime test IDs.

```json
{"untested": [
{"file": "src/marshmallow/schema.py", "line": 941, "behaviour": "handle_error hook call on validation failure in _do_load can be deleted with no test failing"},
{"file": "src/marshmallow/schema.py", "line": 447, "behaviour": "merging schema-level error_messages into the collected messages is unasserted"},
{"file": "src/marshmallow/fields.py", "line": 629, "behaviour": "Nested schema.many or self.many combination (or changed to and) not caught"},
{"file": "src/marshmallow/fields.py", "line": 724, "behaviour": "List/collection type check (_test_collection) call can be removed without failure"},
{"file": "src/marshmallow/fields.py", "line": 1663, "behaviour": "Mapping with neither key_field nor value_field branch condition (not self.value_field) is unasserted"},
{"file": "src/marshmallow/experimental/context.py", "line": 61, "behaviour": "Context.__exit__ body, including resetting the context var token, is not verified (empty body and deleted reset both survive)"},
{"file": "src/marshmallow/validate.py", "line": 78, "behaviour": "kwargs.update(err.kwargs) when collecting validator error kwargs is unasserted"},
{"file": "src/marshmallow/utils.py", "line": 13, "behaviour": "is_generator can return None/constants without any test failing"},
{"file": "src/marshmallow/fields.py", "line": 2133, "behaviour": "Constant._validate_missing override can be replaced without failure"},
{"file": "src/marshmallow/fields.py", "line": 791, "behaviour": "Appending error.valid_data to partial results in List deserialization is unasserted"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run, 12 min cap: all 358 deletion mutants and a 1657-of-2794 classical sample; no flakiness seen in 6 baseline runs (6 time-based datetime parametrize IDs are unstable, but no test varied in outcome); coverage overlap alone is not grounds to delete tests, so none are listed."}
```
