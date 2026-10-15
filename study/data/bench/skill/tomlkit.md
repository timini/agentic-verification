Deep run (12 min budget, complete, not partial). Run dir: /Users/timrichardson/Documents/projects/personal/test-suite-auditor/study/work/bench/skill/tomlkit/.test-suite-audit/20261015T235919-4687 (report.md, report.json). No config file needed; auto-discovery looked right.

Baseline/flakiness (measured): 1051 tests passed in all 3 file-order and 3 random-order runs; none varied or failed. Not observed is not proof of stability (95% upper bound ~50% per test from 6 runs).
Coverage: 2951 of 3339 executable lines covered.
Mutation (measured, sample only): deletion mutants (all 818 ran) 590 killed, 85 survived, 117 uncovered, 26 timeout, rate 74.5%. Classical sample (76 of 5381): 55 killed, 10 survived, 11 uncovered, rate 72.4%.

Untested behaviour (candidate gaps from surviving mutants, not proven bugs; equivalence needs human review, cache clears are the likeliest to be equivalent):
- 15 covered functions keep passing with body removed: 13 exception __init__ methods in tomlkit/exceptions.py (messages/fields not asserted), plus Trivia.copy and Container.last_item.
- 48 call deletions with no test failing, including container.py:1222 and 980 (dict.__setitem__ in OutOfOrderTableProxy), items.py:2280 (AoT unwrap append), items.py:2344 (Array list.insert), container.py:363 and 1110 (table validation calls), items.py:1569/1485/1574 (_reindex, _index_map.clear), container.py:104/505/875/219 (_validation_cache).
- Classical survivors: source.py:191 (inc_n exception passthrough), container.py:503 (NonExistentKey(key)), parser.py:476/689 (error messages), items.py:404, 1532, 2179, 2323, 170.
Reproduce: tsa replay --run <run dir> --mutant e3c18d71eed8ffac (exception __init__) or a2e706e343d976bc (deleted call).

Removable tests: none listed. 4770 test pairs have coverage Jaccard >= 0.9 (inferred), but overlap is not evidence of redundancy; kill sets on a frozen mutant sample were not compared.

Not assessed: time savings from deleting tests, the remaining ~5300 classical mutants, the 117 uncovered deletion mutants (mostly in uncovered items.py/container.py ranges), 26 timeouts.

```json
{"untested": [
{"file": "tomlkit/container.py", "line": 1222, "behaviour": "OutOfOrderTableProxy sync of the proxy dict entry (dict.__setitem__) is unasserted; deleting it fails no test"},
{"file": "tomlkit/items.py", "line": 2280, "behaviour": "unwrap() of items in an array of tables is not checked; deleting the t.unwrap() append fails no test"},
{"file": "tomlkit/items.py", "line": 2344, "behaviour": "Array insert's underlying list.insert is not asserted; deleting it fails no test"},
{"file": "tomlkit/container.py", "line": 363, "behaviour": "_validate_table_candidate call during append is unasserted; deleting it fails no test"},
{"file": "tomlkit/container.py", "line": 1110, "behaviour": "_validate_out_of_order_table call is unasserted; deleting it fails no test"},
{"file": "tomlkit/items.py", "line": 1569, "behaviour": "Array _reindex and _index_map.clear after mutation are unasserted; deleting them fails no test"},
{"file": "tomlkit/container.py", "line": 875, "behaviour": "_validation_cache invalidation in _replace_at/remove/clear is unasserted; deleting it fails no test"},
{"file": "tomlkit/exceptions.py", "line": 164, "behaviour": "Exception __init__ methods (message and position fields of parse errors) are not asserted; body removal survives"},
{"file": "tomlkit/source.py", "line": 191, "behaviour": "inc_n does not forward its exception argument to inc; the mutant survived"},
{"file": "tomlkit/container.py", "line": 503, "behaviour": "NonExistentKey raised on remove carries the key; passing None survives"}
],
"removable_tests": [],
"flaky_tests": [],
"notes": "Deep run, 12-minute budget, complete: 1051 tests passed in all 6 baseline runs (3 file-order, 3 random-order), so no flaky tests were observed. Untested items are candidate gaps from surviving mutants and need human review, since I did not judge equivalence; I listed no removable tests because coverage overlap is not evidence of redundancy."}
```
