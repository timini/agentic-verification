Audit of attrs: the suite is strong, with 99% line and branch coverage and no flaky tests. I found only a few small gaps and nothing I would delete.

**Method**
- Baseline run (Python 3.12): 1377 passed, 8 skipped, 1 xfailed.
- Coverage: the only unexecuted lines are version-specific: `_compat.py` 21-27 (older Pythons), `_make.py` 869 (`sys._clear_type_descriptors`, 3.14 only), 1107-1108 and 1567 (`add_replace` / `__replace__`, 3.13+ only), and 3397 (pre-3.11 converter path).
- Mutation check: I made about 190 one-line changes (`==` to `!=`, `and` to `or`, `True` to `False`, `is None` to `is not None`) across `_make.py`, `_funcs.py`, `validators.py`, `converters.py`, `filters.py`, `setters.py`, `_cmp.py` and `_next_gen.py`, and ran the suite on each. The source is restored; `git status` is clean. Most survivors were docstring text or equivalent changes, such as unused signature defaults and a break that is only an early exit.
- Flakiness: the suite passed 3 runs with random ordering plus 6 more with fixed seeds 1 to 6. It uses no sleeps or timing. The only randomness is Hypothesis.

**Untested behaviour (survived mutation)**
- `src/attr/_funcs.py` lines 192 and 207: when `asdict`/`astuple`-style conversion recurses into a collection inside a dict key, it passes `is_key` to the nested calls. Flipping either value does not fail any test, so nested collections inside keys are not checked.
- `src/attr/_make.py` line 726: `_wrote_own_setattr = True` for frozen classes is not asserted. Setting it to `False` does not fail.
- `src/attr/_make.py` line 704: `_pre_init_has_args` is not asserted. Setting it to `True` does not fail.
- `src/attr/_make.py` lines 1566 and 3396 (guards `PY_3_13_PLUS and not _has_own_attribute(...)` and `not PY_3_11_PLUS and isinstance(...)`): the `and` to `or` flip survives on 3.12. This is mostly version-gated, because the code only runs on 3.13+ or before 3.11. The `__replace__` and `pipe` return-type paths are only exercised on other Python versions.
- `src/attr/_make.py` line 2555: the default-alias logic `alias is None if alias_is_default is None else alias_is_default` has a mutant that survives.

**Removable tests:** none. I found no redundant tests I would stand behind. The suite is heavy on parametrization and Hypothesis, but I did not measure per-test marginal coverage.

**Flaky tests:** none observed.

**Assumptions**
- I counted tests skipped for Python 3.13+, pyright and PyPy as environment gaps, not defects.
- I treated mutations in docstrings and in unused signature defaults as equivalent and ignored them.
- I did not run a full mutation tool, only about 190 sampled mutants, so the untested list is a sample, not exhaustive.

```json
{"untested": [{"file": "src/attr/_funcs.py", "line": 192, "behaviour": "is_key=False passed when recursing into a list/tuple element inside asdict conversion; flipping it is not caught"}, {"file": "src/attr/_funcs.py", "line": 207, "behaviour": "is_key=True passed when converting dict keys; flipping it is not caught, so collections nested inside dict keys are not verified"}, {"file": "src/attr/_make.py", "line": 726, "behaviour": "_wrote_own_setattr set True for frozen classes is never asserted"}, {"file": "src/attr/_make.py", "line": 704, "behaviour": "_pre_init_has_args flag default is not asserted"}, {"file": "src/attr/_make.py", "line": 2555, "behaviour": "alias_is_default computation (alias is None if alias_is_default is None else ...) can be inverted without a test failing"}, {"file": "src/attr/_make.py", "line": 1566, "behaviour": "__replace__ is added only when on 3.13+ and not already defined; the guard is untested on 3.12 and the 3.13 tests are skipped"}, {"file": "src/attr/_make.py", "line": 3396, "behaviour": "pipe() return-type handling for Converter on Python before 3.11 is never run on 3.12"}, {"file": "src/attr/_make.py", "line": 869, "behaviour": "sys._clear_type_descriptors call for Python 3.14 is never run"}], "removable_tests": [], "flaky_tests": [], "notes": "Coverage is 99% and 190 sampled mutants were mostly caught; the survivors are version-gated code, equivalent mutants, and a few unasserted internal flags. Nine runs with random order and fixed seeds were all green, so no flakiness was seen."}
```
