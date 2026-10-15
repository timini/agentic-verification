**Run status: partial.** Deep mode with a budget capped at 11 minutes (the skill's default is 30) to fit the 20-minute limit. The baseline, flakiness, coverage and overlap steps finished. Mutation covered deletion mutants only: 207 killed, 21 survived, 32 uncovered. It stopped before all 430 deletion mutants ran, and 0 of 7738 classical mutants ran.

**Setup assumption:** the first run found 0 tests because pytest turned a deprecation warning into a collection error in `tests/test_isoparser.py` (`PytestRemovedIn10Warning`, generator passed to `parametrize`). I wrote `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/dateutil/test-suite-audit.toml` with `pytest_args = ["-W", "ignore::pytest.PytestRemovedIn10Warning"]`. That one file is the only change I made to the workspace. The run directory is `.test-suite-audit/20261015T234210-ee71`, and `.test-suite-audit/20261015T234140-6bb5` is the failed first run.

**Measured results**
- **Baseline:** 2095 tests over 3 runs. 1989 passed every time, 40 fail on a pristine checkout, 2 varied between runs, 64 were skipped or xfailed.
  - The 40 failures are in `tests/test_tz.py`, e.g. `ZoneInfoGettzTest` and `testGMTOffset`. The ones I looked at fail with `UserWarning: I/O error(2)`, which suggests missing zoneinfo data in this environment. The runner leaves them out of mutation scope, so the tz findings below are weaker.
- **Coverage:** 3119 of 3590 executable source lines are covered. `src/dateutil/tz/win.py` is almost entirely uncovered, which is expected on macOS. `tz/tz.py`, `rrule.py`, `tz/_common.py` and `parser/_parser.py` have scattered uncovered lines.
- **Overlap (inferred):** 22097 test pairs have coverage Jaccard >= 0.9. This is not evidence that any test is redundant, so I list no removable tests. The evidence file reports that removing individually "redundant" tests lost kills in 16 of 16 files.
- **Flakiness:** two tests changed outcome between 3 identical file-order runs: `tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoDeprecated` and `tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoMetadataDeprecated`. No cause was identified. Both sit in the class with the missing-data failures, so I would check warning and data-loading state first. No other test varied in 6 runs (3 file-order, 3 random-order), which does not show the rest are stable.
- **Pseudo-tested functions (9, measured):** every body replacement ran and no covering test failed. Candidate gaps only.
  - `rrule.py::_rrulestr._handle_WKST`
  - `tz.py::_ttinfo.__init__`
  - `tz.py::tzutc.is_ambiguous`
  - `tz.py::tzoffset.dst`
  - `tz.py::tzoffset.is_ambiguous`
  - `_factories.py::_TzOffsetFactory.__init__`
  - `_factories.py::_TzStrFactory.__init__`
  - `_parser.py::_timelex.isspace`
  - `_parser.py::parserinfo.utczone`
  - Reproduce: `tsa replay --run /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/dateutil/.test-suite-audit/20261015T234210-ee71 --mutant 105a364242c1748f`
- **Deleted calls nobody notices (12, measured):**
  - `rrule.py:697` `self._timeset.sort()`
  - `rrule.py:1291` and `rrule.py:1299` `tset.sort()`
  - `rrule.py:718` the `WKST=` part of the rrule string output
  - `rrule.py:772` `new_kwargs.update(self._original_rule)`
  - `tz.py:334` `setattr(self, attr, None)`
  - `_parser.py:1436` `used_idxs.append(i)`
  - Several `super().__init__()` calls
  - Reproduce: the same command with `--mutant ef131c69cfe89902`

**Not assessed:**
- Classical mutants and the rest of the deletion mutants.
- The 20 invalid and 36 timed-out deletion mutants, which are excluded from the rate.
- Timing savings: the report gives only a 4.0s median wall time and a 1.0s sum of test durations, and those cannot show a speed-up.

I did not judge any surviving mutant to be equivalent. All of them need human review.

```json
{"untested": [
{"file": "src/dateutil/rrule.py", "line": 718, "behaviour": "WKST= part of rrule string output (str(rrule)) can be removed with no test failing (call-delete survived)"},
{"file": "src/dateutil/rrule.py", "line": 1506, "behaviour": "_rrulestr._handle_WKST: parsing WKST from an RRULE string; body replacement survives"},
{"file": "src/dateutil/rrule.py", "line": 697, "behaviour": "Sorting of the rrule time-of-day set (self._timeset.sort()); removal not detected"},
{"file": "src/dateutil/rrule.py", "line": 1299, "behaviour": "Sorting of the time set built from BYHOUR/BYMINUTE/BYSECOND (tset.sort()); removal not detected (same for line 1291)"},
{"file": "src/dateutil/rrule.py", "line": 772, "behaviour": "rrule.replace() does not verify that original rule kwargs are carried over (new_kwargs.update(self._original_rule))"},
{"file": "src/dateutil/tz/tz.py", "line": 157, "behaviour": "tzoffset.dst result (should be zero timedelta) is not asserted; body replacement survives"},
{"file": "src/dateutil/tz/tz.py", "line": 168, "behaviour": "tzoffset.is_ambiguous result (should be False) is not asserted; body replacement survives"},
{"file": "src/dateutil/tz/tz.py", "line": 84, "behaviour": "tzutc.is_ambiguous result (should be False) is not asserted; body replacement survives"},
{"file": "src/dateutil/parser/_parser.py", "line": 351, "behaviour": "parserinfo.utczone: recognition of UTC zone names; body replacement survives"},
{"file": "src/dateutil/parser/_parser.py", "line": 1436, "behaviour": "used_idxs.append(i) in parse result handling can be deleted with no test failing"}
],
"removable_tests": [],
"flaky_tests": ["tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoDeprecated", "tests/test_tz.py::ZoneInfoGettzTest::testZoneInfoMetadataDeprecated"],
"notes": "Run was partial (11 min budget, deletion mutants only, no classical mutants); 40 test_tz.py tests fail on a clean checkout, apparently from missing zoneinfo data, so tz findings are weaker. A test-suite-audit.toml was added to work around a pytest deprecation-warning collection error. No removal candidates are given because coverage overlap is not evidence of redundancy."}
```
