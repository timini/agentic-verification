Audit of click's test suite. Default run: 1990 passed, 25 skipped, 1 xfailed, about 4s, 85% line coverage.

Assumptions: I judged "untested" from the coverage report, with line-level spot checks and greps of the tests. I did not run mutation testing. I could not verify which tests are removable without a mutation tool, so I list none.

**Untested behaviour (strongest first)**
- `CommandCollection.add_source` and `get_command` source lookup, including the chain nested-check (core.py 2143-2174). No test references `CommandCollection`. `list_commands` merging of sources is also unchecked.
- `get_app_dir` (utils.py 515-527) is not exercised at all. This covers the Windows, `force_posix`, darwin and XDG branches.
- `_PacifyFlushWrapper`, used on EPIPE in `main` (core.py 1572-1577, utils.py 547-556) is untested. Broken-pipe handling, exit code 1 and swallowing EPIPE on flush are all unchecked.
- `BashComplete._check_version` (shell_completion.py 397-423) is untested. This is the warning for Bash older than 4.4 or when the version can't be detected.
- The `Parser` error branches are untested: two nargs<0 arguments (parser.py 96), an unknown action (parser.py 181), and `BadOptionUsage` (parser.py 381).
- Windows argument expansion in `main` (core.py 1536-1539, via `_expand_args`) is untested.
- The bool-flag branch for an UNSET value (issue 3069) runs the callback on `False` (core.py 3652-3657). It is untested.
- `Group.add_command` raising "Command has no name." (core.py 3745-3747) is untested.
- The `version_option` fallback that derives `package_name` from the caller's frame globals (decorators.py 485-499) is untested. The explicit `package_name` cases are tested, but not the auto-detect path, including the `__main__` case.
- `hidden_prompt_func`, the getpass wrapper (termui.py 80-82), is untested.

**Removable tests:** none I would stand behind.

**Flaky tests:** none. Four random-order runs with pytest-randomly all passed. The stress tests marked `stress` (tests/test_stream_lifecycle.py, lines 493 onward) are deselected by default via addopts. I ran them once serially and they were still going when I killed them after about 400s, so the suite has slow, race-hunting tests that are never exercised in the normal run. I can't call them flaky from this evidence.

```json
{"untested": [
{"file": "src/click/core.py", "line": 2143, "behaviour": "CommandCollection.add_source / get_command lookup across sources and list_commands merge (no test references CommandCollection)"},
{"file": "src/click/utils.py", "line": 515, "behaviour": "get_app_dir platform branches (Windows APPDATA, force_posix, darwin, XDG) never executed"},
{"file": "src/click/core.py", "line": 1572, "behaviour": "EPIPE handling in main(): wraps stdout/stderr in _PacifyFlushWrapper and exits 1; other OSErrors re-raised"},
{"file": "src/click/utils.py", "line": 547, "behaviour": "_PacifyFlushWrapper.flush swallows only EPIPE errors"},
{"file": "src/click/shell_completion.py", "line": 397, "behaviour": "BashComplete._check_version warns on Bash < 4.4 or undetectable version"},
{"file": "src/click/parser.py", "line": 96, "behaviour": "TypeError when two arguments have nargs < 0"},
{"file": "src/click/core.py", "line": 3652, "behaviour": "Unset non-required bool flag becomes False and still runs its callback (issue 3069)"},
{"file": "src/click/core.py", "line": 1536, "behaviour": "Windows glob expansion of argv via _expand_args in main()"},
{"file": "src/click/decorators.py", "line": 485, "behaviour": "version_option auto-detects package_name from caller frame globals (incl. __main__ case)"},
{"file": "src/click/core.py", "line": 3745, "behaviour": "Group.add_command raises TypeError when command has no name"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Coverage-based judgement only, no mutation testing; default suite passed 5 times (once in fixed order, four times in random order) with no flakiness. Stress tests are deselected by default and one serial run did not finish in about 400s, so I did not assess them."}
```
