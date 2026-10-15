# Agentic Verification

Coding agents write a growing share of the code, so the tests that check it carry more of the weight. Agentic Verification is a Claude Code plugin that checks those tests: it audits a Python/pytest suite and reports, with evidence, which behaviour no test would notice if it broke, which tests are slow or depend on test order, and where coverage numbers are misleading. It is report-only: it never edits, skips or deletes tests.

The name comes from Addy Osmani's essay [Agentic Verification](https://addyo.substack.com/p/agentic-verification). Every rule the plugin follows was tested first on eight open-source projects, and the plugin itself was benchmarked against the same agent without it. Both are in the [paper](study/paper/agentic-verification-study.pdf).

## What it reports

- **Untested behaviour.** Mutants are run one at a time in a disposable copy of the project:
  - every function body is replaced with `None` or a type-appropriate constant, and every single call statement is deleted;
  - then a seeded sample of classical mutants from mutmut's operators fills the rest of the budget.

  An activation check confirms the mutated line actually ran, so mocked-out code is not reported as untested.
- **Order dependence and flakiness.** Repeated baseline runs in file order, plus random order when pytest-randomly is installed. Tests that fail only when the order changes are reported separately, and no test is ever called "stable".
- **Cost.** Slowest tests and setup-heavy tests, timed without coverage.
- **Coverage.** Per-test line coverage, uncovered line numbers, and test pairs that run nearly the same lines. Overlap is reported only as something to investigate, never as redundancy.

Every finding is labelled *measured*, *inferred*, *unverified* or *not assessed*, and mutant findings come with a replay command.

## Usage

```text
/plugin marketplace add timini/agentic-verification
/plugin install agentic-verification@agentic-verification
```

Then, in a pytest project:

```text
/test-suite-audit quick
/test-suite-audit deep --budget-minutes 30
```

The project's environment needs Python 3.12+ and `pytest-cov`, and `pytest-randomly` for order checks. The runner also works on its own:

```bash
uvx --from "git+https://github.com/timini/agentic-verification#subdirectory=runner" tsa deep path/to/project --budget-minutes 30
tsa replay --run path/to/project/.test-suite-audit/<run-id> --mutant <id>
```

Output goes to `.test-suite-audit/<run-id>/` in the audited project: `report.md`, `report.json` and the mutant patches. Optional settings live in `test-suite-audit.toml`: `python`, `source`, `tests`, `pytest_args`, `env` and `workers`. Deep audits of projects over about 3,500 executable lines need the 30-minute default or more.

## Evidence

**[Agentic Verification: Do Test-Suite Audit Heuristics Hold? (PDF)](study/paper/agentic-verification-study.pdf)**

### Study: do the rules hold?

The study covered six pre-registered hypotheses on eight Python projects: attrs, more-itertools, dateutil, toolz, marshmallow, click, tomlkit and cachetools, with 8,879 tests in scope.

| | Hypothesis | Result |
|---|---|---|
| H1 | Tests that run the same lines are not necessarily redundant | Supported. 35% of pairs with Jaccard >= 0.9 each catch a mutant the other misses (95% CI 22-48%). |
| H2 | Deletion mutants find untested code more cheaply than classical ones | **Not supported.** They found 0.38x the survivors per CPU-minute (0.24-0.48). |
| H3 | A function whose whole-body deletion is caught can still have unchecked calls | Supported. 71% of unnoticed call deletions sit in such functions (58-80%). |
| H4 | Tests that are removable one at a time are not removable together | Supported. Group removal lost kills in 16 of 16 files. |
| H5 | Per-test coverage contexts add a lot of overhead | Supported. Suites ran 2.48x slower overall (1.74-3.88). |
| H6 | A few reruns miss intermittent tests | 2 intermittent tests in 480 runs. Both were order-dependent, and same-order reruns never showed one of them failing. |

### Benchmark: does the skill help?

An agent following the skill was compared with the same agent (Sonnet) without it, on the same eight projects. Every claim either agent made was checked independently against a clean copy of the project.

| | With the skill | Without |
|---|---|---|
| Untested-behaviour claims verified / refuted | 74 / 0 | 62 / 3 |
| Precision | 100% (95% CI 95-100%) | 95% (87-98%) |
| Verified gaps in code the tests do run | 71 | 23 |
| Verified gaps that only restate uncovered lines | 3 | 39 |
| Test-removal lists given (refuted) | 0 | 2 (1) |
| Runs that mutated source in place | 0 | 3 |
| Median time per run | 12.6 min | 5.9 min |

Precision was similar. The main difference is in the kind of gap found: the skill finds gaps in code the tests already run, which coverage cannot show. It also stays out of the user's working tree, at the cost of a longer run. The benchmark also found a defect in the runner, now fixed: mutant generation took 319 s on one large module.

Everything is in [`study/`](study/), which is evidence only and not part of the plugin:
- the [study pre-registration and its deviations](study/PREREGISTRATION.md);
- the [benchmark pre-registration](study/BENCHMARK.md);
- the pinned [corpus](study/corpus.toml);
- the experiment scripts, the gzipped raw data and the analysis that generates every table.

`make -C study all` rebuilds the analysis and the PDF. A human usefulness review of a sample of H2 survivors is still pending.

## Repository

- [`skills/test-suite-audit/`](skills/test-suite-audit/): the skill Claude follows, with a [reference on why it refuses some conclusions](skills/test-suite-audit/reference/evidence.md).
- [`runner/`](runner/): the `tsa` runner (measurement, mutation, reports) and its tests.
- [`fixtures/known_answers/`](fixtures/known_answers/): a small project with planted gaps that the runner's tests use.
- [`docs/`](docs/): [product requirements](docs/PRD.md), [research notes](docs/RESEARCH.md) and the [behavioural ablation design](docs/BEHAVIOURAL_ABLATION.md).
- [`study/`](study/): the study and the benchmark.

Planned but not built: semantic (LLM-proposed) mutants, LLM-directed null components, test-suite ablation experiments, and JS/TS support.

## Licence

MIT
