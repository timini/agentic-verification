Audit of tomlkit: 1051 tests pass, 89% line coverage (branch coverage not measured). I ran the suite once with coverage and ordering fixed, then six more times under pytest-randomly with random order. Every run passed, in about 0.7s. I read the uncovered lines in the source but did not mutate the code, so the untested items below are judged from coverage gaps and the code around them.

Assumptions: "untested" means lines with no coverage, picking the ones where silent breakage would matter most. I only list tests as removable or flaky if I would stand behind it.

Untested behaviour, strongest first:
1. `Container._insert_after` (container.py 516-561) is never run. This is the insert-after-key path, which fixes up the key-index map and the trailing newline. A break would corrupt key order or the map silently.
2. The `Integer` bitwise and arithmetic operators in items.py (about 660-960, e.g. `__and__`) are not exercised. Nothing checks that they return a `tomlkit` Integer type with trivia preserved rather than a plain `int`.
3. `AoT.__delitem__` (items.py 1660-1670) has uncovered branches: slice deletion and the IndexError raised when `_index_map` has no entry.
4. `AoT.insert` (items.py 2316-2335) has uncovered branches: negative and out-of-range index clamping, and the indent-inheritance block. Wrong placement or indentation would pass.
5. `tomlkit.datetime()` raises ValueError for non-datetime strings (api.py 178). It is never tested.
6. `tomlkit.array()` raises ValueError for non-array input (api.py 197). It is never tested.
7. `Container.__setitem__` (container.py 1214-1218) has an untested branch: replacing a value inside a super-table's `_tables`. This is the break-out-of-loop / `else: self._tables[0][key]` fallback.
8. `Source.reset` (source.py 98-101) is never run.
9. The datetime `__sub__` path in items.py (about 2290-2310) is not covered where subtraction yields a datetime and must be re-wrapped.
10. Several `ParseError` subclasses and message formatting in exceptions.py (22, 41-43, 96-98) are not covered. Also uncovered are `_types.py` fallbacks (54-90), which is about 40% of that module.

Removable tests: none I would stand behind. Most of the suite is parametrized and the toml-test conformance cases overlap a lot, but the EOL tests (`test_keep_old_eol`, `test_keep_old_eol_2`, `test_consistent_eol`, `test_consistent_eol_2`) each cover a distinct case. I did not run per-test coverage, so I cannot name tests whose coverage is fully duplicated by others.

Flaky tests: none observed. `tests/test_items.py::test_datetime_unwrap` uses `datetime.now`, but it only checks the type, so it is stable. `tests/test_toml_file.py::test_default_eol_is_os_linesep` depends on the platform's `os.linesep`, which could differ between operating systems but does not vary between runs.

```json
{"untested": [
{"file": "tomlkit/container.py", "line": 516, "behaviour": "Container._insert_after: insert-after-key with index map shifting and trailing newline fixup is never executed"},
{"file": "tomlkit/items.py", "line": 659, "behaviour": "Integer bitwise/arithmetic operators (__and__ and siblings) returning a tomlkit Integer are not exercised"},
{"file": "tomlkit/items.py", "line": 1660, "behaviour": "AoT __delitem__ slice deletion and IndexError when index map has no entry"},
{"file": "tomlkit/items.py", "line": 2316, "behaviour": "AoT.insert negative/out-of-range index clamping and indent inheritance"},
{"file": "tomlkit/api.py", "line": 178, "behaviour": "tomlkit.datetime() raises ValueError for non-datetime strings"},
{"file": "tomlkit/api.py", "line": 197, "behaviour": "tomlkit.array() raises ValueError when the string is not an array"},
{"file": "tomlkit/container.py", "line": 1214, "behaviour": "Container setitem into a super table's _tables with break/fallback to _tables[0]"},
{"file": "tomlkit/source.py", "line": 98, "behaviour": "Source.reset (index and marker reset) never run"},
{"file": "tomlkit/items.py", "line": 2290, "behaviour": "DateTime __sub__ rewrapping the result as a tomlkit DateTime"},
{"file": "tomlkit/exceptions.py", "line": 41, "behaviour": "Some ParseError subclasses and messages are never raised in tests"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Coverage is 89% by line; 6 random-order reruns all passed, so no flakiness found. No test removal is justified without per-test coverage data."}
```
