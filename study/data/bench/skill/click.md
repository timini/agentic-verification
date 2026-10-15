**The run was partial.** I ran deep mode with a 12-minute budget instead of the default 30 so it fit the 20-minute limit. The runner auto-discovered `src/click` and `tests` and used `.venv`. Baseline runs and coverage finished. Of 1019 deletion mutants, 668 ran. The classical-mutant sample never started (0 of 7850). Nothing was edited. The report is in `/Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/click/.test-suite-audit/20261015T235419-00c3/` (`report.md`, `report.json`).

**Measured results**
- Baseline: 2016 tests, 1990 passed in every run, 26 skipped or xfailed. Median wall time was 4.2s.
- Flakiness: 3 file-order runs and 3 random-order runs showed 0 varying tests. I list none as flaky. Six runs without a failure only bound a test's failure rate at about 50% (95%), so "not observed" does not mean stable.
- Coverage: 4287 of 5012 executable lines. The biggest uncovered areas are `_winconsole.py`, `_termui_impl.py` and `core.py`.
- Deletion mutants: 516 killed, 50 survived, 102 uncovered, giving a 77.2% detection rate for this sample only. A further 11 were invalid and 17 timed out.

**Untested behaviour (Measured, candidate gaps)**
These deletion mutants ran and executed, and the covering tests still passed. They need human review. I have not judged any of them equivalent.
1. `parser.py:213`: deleting `state.order.append(self.obj)` survives, so the order of parsed options is not asserted.
2. `core.py:2810`: deleting `ctx.set_parameter_source(...)` survives.
3. `Command.format_epilog` (`core.py:1319`) can have its body removed with no failure. Deleting its call at `core.py:1275` also survives.
4. `_check_nested_chain` (`core.py:82`) can have its body removed with no failure. Deleting its call at `core.py:1788` also survives.
5. `core.py:1594` and `core.py:1562`: deleting the "Aborted!" echo and the `ctx.exit()` call on that path survives.
6. `decorators.py:554-556` and `596-598`: deleting the `setdefault` calls for `expose_value`, `is_eager` and `help` survives for the version and help options. Deleting `ctx.exit()` at lines 548 and 590 also survives.
7. `formatting.py:319`: deleting `rv.sort(...)` survives, so the ordering of the rows is not asserted.
8. `_termui_impl.py:344` (`ProgressBar.finish`) can have its body removed with no failure.
9. `_termui_impl.py:414` (`_PagerWriter.close`) can have its body removed with no failure.
10. `_compat.py:143` (`_FixupStream.seekable`) can have its body removed, and so can `_NonClosingTextIOWrapper.__del__` at `_compat.py:74`.

To reproduce, run the `tsa replay` commands from the report:
- Pseudo-tested functions: `tsa replay --run <run dir> --mutant 833145ca84033f94`
- Removed calls: `tsa replay --run <run dir> --mutant d89104e3c27c5ba2`

**Removable tests:** none. The only redundancy signal is coverage overlap, for example the `test_choice_usage_rendering[...]` parametrisations. Coverage overlap is not evidence that tests are redundant, and I did not run the kill-set comparison that would be needed.

**Not assessed:** classical mutants, kill-set comparison between tests, and any paired timing that would show a speed-up. The slowest tests, in `test_termui.py` (pager detection), take only about 0.12s each.

```json
{"untested": [
 {"file": "src/click/parser.py", "line": 213, "behaviour": "state.order.append(self.obj): order of parsed options is not asserted (deleting the call survives)"},
 {"file": "src/click/core.py", "line": 2810, "behaviour": "ctx.set_parameter_source call can be deleted with no test failing"},
 {"file": "src/click/core.py", "line": 1319, "behaviour": "Command.format_epilog body can be removed, and its call at line 1275 deleted, with no test failing"},
 {"file": "src/click/core.py", "line": 82, "behaviour": "_check_nested_chain body can be removed, and its call at line 1788 deleted, with no test failing"},
 {"file": "src/click/core.py", "line": 1594, "behaviour": "Abort handling: the 'Aborted!' echo to stderr can be deleted with no test failing (ctx.exit() at line 1562 also survives deletion)"},
 {"file": "src/click/decorators.py", "line": 554, "behaviour": "version_option defaults (expose_value, is_eager, help) and ctx.exit() can be deleted with no test failing; same for help_option at lines 596-598"},
 {"file": "src/click/formatting.py", "line": 319, "behaviour": "rv.sort(...) can be deleted: row ordering is not asserted"},
 {"file": "src/click/_termui_impl.py", "line": 344, "behaviour": "ProgressBar.finish body can be removed with no test failing"},
 {"file": "src/click/_termui_impl.py", "line": 414, "behaviour": "_PagerWriter.close body can be removed with no test failing"},
 {"file": "src/click/_compat.py", "line": 143, "behaviour": "_FixupStream.seekable body can be removed with no test failing (_NonClosingTextIOWrapper.__del__ at line 74 likewise)"}
],
 "removable_tests": [],
 "flaky_tests": [],
 "notes": "Partial deep run (12 min budget): 668 of 1019 deletion mutants ran and no classical mutants; the 77.2% detection rate applies to that sample only. No flakiness was observed in 6 runs, which does not prove stability, and coverage overlap alone gave no basis to recommend deleting tests."}
```
