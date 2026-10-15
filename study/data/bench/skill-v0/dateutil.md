**Audit of dateutil (deep mode, 13 min budget): partial run, with no classical mutants and no tests I can recommend deleting.**

**What I did**
- The first run found nothing: pytest could not collect `tests/test_isoparser.py`. The project turns warnings into errors, and `PytestRemovedIn10Warning` fires on a generator passed to `parametrize`.
- I added `test-suite-audit.toml` in the workspace with `pytest_args = ["-W", "ignore::pytest.PytestRemovedIn10Warning"]`. I did not touch any test or source file. The toml is the only change outside `.test-suite-audit/`.
- The second run is the one reported here: `.test-suite-audit/20261015T225846-4bf8` (`report.md` and `report.json` are in that folder).
- I asked for 13 minutes (not the 30-minute deep default) to stay inside my 20 minute limit. The report status is **partial**.

**Missing from the run**
- Deletion mutants stopped at 299 of 430. Of the 299, 21 were invalid and 21 timed out; those 42 are excluded from the rate.
- 0 of 7738 classical mutants ran, so there is no classical detection rate.
- The 40 baseline failures are excluded from mutation scope, so conclusions about the code they cover are weaker.
- Coverage was 3121 of 3594 executable lines.
- No savings or speed-up were measured.

**Findings (all Measured unless noted)**
1. **40 tests fail on the unmodified checkout.**
   - The cause looks like the missing zoneinfo tarball. `src/dateutil/zoneinfo/` has only `__init__.py` and `rebuild.py`, and a rerun shows `UserWarning: I/O error(2): No such file or directory`, which the project's warnings-as-errors setting turns into a failure.
   - Examples: `tests/test_tz.py::TZTest::testGMTOffset` and `tests/test_tz.py::ZoneInfoGettzTest::testFoldIndependence`.
   - This is an environment fault, not a bug in the tests. I did not repair it, because I was not to edit the workspace.
2. **9 functions pass with their body removed (candidate gaps).** Deletion detection rate is 79.6% (238 killed, 21 survived, 40 uncovered); this describes the sample only.
   - `tzoffset.dst` returning `ZERO` (`src/dateutil/tz/tz.py:157`) and `tzutc.is_ambiguous` (`src/dateutil/tz/tz.py`, around line 84 per grep).
   - `tzoffset.is_ambiguous` (`src/dateutil/tz/tz.py:168`) and `_ttinfo.__init__`.
   - `_rrulestr._handle_WKST` (`src/dateutil/rrule.py:1506`), so WKST parsing in `rrulestr` is not asserted.
   - `parserinfo.utczone` (`src/dateutil/parser/_parser.py:351`) and `_timelex.isspace` (`src/dateutil/parser/_parser.py:214`).
   - `_TzOffsetFactory.__init__`, plus one more listed in `report.json`.
   - Reproduce: `tsa replay --run <run dir> --mutant 105a364242c1748f`
3. **12 call statements can be deleted with every test still green.**
   - `src/dateutil/rrule.py:697` and `:1299` (`sort()` of the time set) and `:772` (`new_kwargs.update(self._original_rule)` in `replace()`).
   - `src/dateutil/parser/_parser.py:1436` (`used_idxs.append(i)` after the UTC offset is parsed).
   - Reproduce: `tsa replay --run <run dir> --mutant ef131c69cfe89902`
4. **Flakiness.**
   - `tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoDeprecated` and `tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoMetadataDeprecated` changed outcome across 3 identical runs. The cause is not identified; the same missing-tarball warning is a plausible link.
   - `tests/property/test_tz_prop.py::test_gettz_returns_local[None]` passed all file-order runs and failed in at least one of 3 random-order runs. That points to shared state between tests.
   - No other test varied in 6 runs. An approximate 95% upper bound of 50% on a test's failure rate means other flakiness may exist.
5. **Test overlap (Inferred).** 22097 test pairs have Jaccard similarity of 0.9 or more on executed lines. Overlap is not evidence of redundancy, so I name no tests to delete.

**Assumptions**
- I treated the toml warning filter as a harness workaround.
- I counted the three flaky tests (the two that changed outcome and the one that failed under random order) as flaky. Their causes are not identified.
- The item 4 file and line values come from the report's evidence list plus a quick look at the source.

```json
{"untested": [
{"file": "src/dateutil/rrule.py", "line": 1506, "behaviour": "rrulestr WKST handling (_handle_WKST) can be emptied and no test fails"},
{"file": "src/dateutil/rrule.py", "line": 772, "behaviour": "rrule.replace() copying the original rule via new_kwargs.update(self._original_rule) can be deleted unnoticed"},
{"file": "src/dateutil/parser/_parser.py", "line": 1436, "behaviour": "used_idxs.append(i) after parsing a UTC offset can be removed with no test failing"},
{"file": "src/dateutil/rrule.py", "line": 697, "behaviour": "sorting of the timeset (self._timeset.sort()) is unasserted"},
{"file": "src/dateutil/rrule.py", "line": 1299, "behaviour": "sorting of tset in the iterator is unasserted"},
{"file": "src/dateutil/tz/tz.py", "line": 157, "behaviour": "tzoffset.dst returning ZERO can be replaced with no test failing"},
{"file": "src/dateutil/tz/tz.py", "line": 168, "behaviour": "tzoffset.is_ambiguous result is unasserted"},
{"file": "src/dateutil/tz/tz.py", "line": 84, "behaviour": "tzutc.is_ambiguous result is unasserted"},
{"file": "src/dateutil/parser/_parser.py", "line": 351, "behaviour": "parserinfo.utczone (UTC name matching) is unasserted"},
{"file": "src/dateutil/parser/_parser.py", "line": 214, "behaviour": "_timelex.isspace whitespace test can be replaced with no test failing"}
],
"removable_tests": [],
"flaky_tests": [
"tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoDeprecated",
"tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoMetadataDeprecated",
"tests/property/test_tz_prop.py::test_gettz_returns_local[None]"
],
"notes": "Partial run: collection needed a warning filter in test-suite-audit.toml, 40 tz tests fail on the unmodified copy (zoneinfo tarball missing), and only deletion mutants ran (79.6% on a 299-mutant sample, 0 classical). Untested items are candidate gaps from surviving deletion mutants, not proven bugs; no deletions recommended because overlap is not redundancy."}
```
