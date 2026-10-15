Audit of toolz: line and branch coverage is 98%, but the suite still misses real behaviour. I found the gaps by mutation probing in a scratch copy, so the workspace is unmodified. I mutated about 15 operators across the production modules and ran the full suite on each, with a 20 s timeout per run.

**Assumptions:** I treated mutants that survived only in docstring text or under `# pragma: no cover` as noise. I excluded the Python 3.14-only code in `functoolz.py` (lines 597-649) because the venv is 3.12, so it cannot run here.

**Untested behaviour (strongest first):**
1. **`test_diff` never checks the `key=` result.** At `toolz/tests/test_itertoolz.py:527` the line is `list(diff(...)) == [...]` with no `assert`. Flipping `vals.count(vals[0]) != N` to `==` in `diff`'s key branch (`itertoolz.py:965`) leaves every test green. The expected value there also looks wrong, since both rows are equal in dollars, so the diff should be empty.
2. **`juxt(single_callable)` is untested.** Changing `len(funcs) == 1 and not callable(funcs[0])` to `or` (`functoolz.py:759`) survives, although it would break `juxt(f)`.
3. **`Compose.__eq__` is only checked loosely.** `other.first == self.first and other.funcs == self.funcs` (`functoolz.py:550`) survives `and` becoming `or`. Composes that share only `first`, or only `funcs`, are never compared.
4. **`merge_sorted` tie-breaking is untested** at `itertoolz.py:155`, `158` and `201`. `<` can become `<=` without a failure, so nothing checks stability or that equal items come out in sequence order.
5. **`curry.__reduce__` pickling of decorated functions is thinly tested.** Mutations to `if modname and qualname` and to `isinstance(obj, curry) and obj.func is func` (`functoolz.py:355`, `366`) survive.
6. **`curry.__call__` default handling is untested.** `cls(func, *args, **(kwargs or {}))` at `functoolz.py:388` survives `or` becoming `and`.
7. **`interleave` exhaustion handling** at `itertoolz.py:232` survives `while True` becoming `while False`, so the restart-after-exhaustion path is not pinned down.
8. **`get` with a tuple index and a missing key** at `itertoolz.py:464`. Removing `not` in the comment-adjacent `except (KeyError, IndexError)` line survives, so that exception path is unchecked.
9. **`memoize` default key** at `functoolz.py:448`: `args or None` becoming `args and None` survives, so the empty-args vs positional-args distinction is not tested.
10. **`_signatures.check_partial`** at `_signatures.py:701`: `<` to `<=` on the positional-only padding survives. `sandbox/parallel.py:61` also survives `chunksize > 1` becoming `>= 1`, so the chunksize guard is untested.

**Removable tests:**
- `toolz/tests/test_signatures.py::test_for_coverage` only exists to hit coverage on private `_sigs` helpers with `None` and trivial inputs.

**Flaky tests:** none. I ran the suite 6 times with pytest-randomly random ordering and once with it disabled. All runs gave 192 passed and 1 skipped (the skip is the 3.14-only annotationlib test). The suite uses no time, sleep, thread or process dependence.

```json
{"untested": [
{"file": "toolz/tests/test_itertoolz.py", "line": 527, "behaviour": "test_diff key= case has no assert; diff(key=) comparison (itertoolz.py:965 count != N) can be inverted undetected"},
{"file": "toolz/functoolz.py", "line": 759, "behaviour": "juxt(single_callable) vs juxt(iterable) argument handling"},
{"file": "toolz/functoolz.py", "line": 550, "behaviour": "Compose.__eq__ requires both first and funcs equal"},
{"file": "toolz/itertoolz.py", "line": 155, "behaviour": "merge_sorted tie handling (equal items, <= vs <), also lines 158 and 201 with key"},
{"file": "toolz/functoolz.py", "line": 366, "behaviour": "curry pickling/reduce for decorated functions (module-qualname lookup, obj.func is func)"},
{"file": "toolz/functoolz.py", "line": 388, "behaviour": "curry.__call__ construction with args/kwargs defaults"},
{"file": "toolz/itertoolz.py", "line": 232, "behaviour": "interleave restart loop after an iterator is exhausted"},
{"file": "toolz/itertoolz.py", "line": 464, "behaviour": "get() with missing key/index and default for non-list index"},
{"file": "toolz/functoolz.py", "line": 448, "behaviour": "memoize default key: empty args vs positional args and kwargs"},
{"file": "toolz/sandbox/parallel.py", "line": 61, "behaviour": "fold chunksize > 1 guard boundary"}],
"removable_tests": ["toolz/tests/test_signatures.py::test_for_coverage"],
"flaky_tests": [],
"notes": "Coverage is 98% but the line-527 missing assert in test_diff and several operator mutants that survive show coverage overstates protection; no flakiness seen in 6 random-order runs. Mutation probing was limited to about 15 simple operator swaps, so more gaps likely exist."}
```
