# Test Suite Auditor

A Claude Code plugin that audits a Python/pytest test suite and reports evidence about its cost, intermittent failures, coverage overlap and fault detection. It is report-only: it never edits, skips or deletes tests.

**Status:** audit MVP (`quick` and `deep` modes) implemented. The design rules it relies on were tested in our own study; see [Study](#study).

## What it reports

- Baseline: tests that fail, vary, or change ID between identical runs.
- Cost: slowest tests and setup-heavy tests, from uninstrumented runs.
- Coverage: per-test line coverage, line multiplicity, and test pairs that execute nearly the same lines (an *investigate* signal, never a redundancy claim).
- Fault detection (`deep`): a seeded sample of mutants from two populations, reported separately:
  - classical mutants from mutmut's operators;
  - deletion mutants: function bodies replaced with `None` or a type-appropriate constant, and single call statements removed.
  It flags functions that keep passing with every body replacement, calls that can be deleted without any test failing, and surviving classical mutants.

Every finding is labelled *measured*, *inferred*, *unverified* or *not assessed*, and mutant findings come with a replay command. Each mutant runs in a disposable copy of the project, and an activation check confirms the mutated line actually executed, so mocked-out code is not reported as untested.

## Usage

Install the plugin from this repository:

```text
/plugin marketplace add timini/test-suite-auditor
/plugin install test-suite-auditor@test-suite-auditor
```

Then, in a pytest project:

```text
/test-suite-audit quick
/test-suite-audit deep --budget-minutes 30
```

The target environment needs Python 3.12+ and `pytest-cov`. The runner can also be used directly:

```bash
uv run --project runner tsa deep path/to/project --budget-minutes 30
uv run --project runner tsa replay --run path/to/project/.test-suite-audit/<run-id> --mutant <id>
```

Output goes to `.test-suite-audit/<run-id>/` in the audited project: `report.md`, `report.json` and the mutant patches. Optional configuration lives in `test-suite-audit.toml` (`python`, `source`, `tests`, `pytest_args`, `env`, `workers`).

## Study

**[Coverage Overlap, Deleted Behaviour and Redundant Tests (PDF)](study/paper/test-suite-auditor-study.pdf)**

Before building the plugin on rules taken from mostly Java research, we tested six pre-registered hypotheses on eight Python projects (attrs, more-itertools, dateutil, toolz, marshmallow, click, tomlkit, cachetools; 8,879 tests in scope), using the plugin's own runner.

| | Hypothesis | Result |
|---|---|---|
| H1 | High coverage overlap does not mean redundancy | Supported: 35% of pairs with Jaccard >= 0.9 are complementary (95% CI 22-48%) |
| H2 | Deletion mutants find untested code more cheaply than classical ones | **Not supported**: 0.38x the survivors per CPU-minute (0.24-0.48) |
| H3 | A killed whole-function mutant does not mean the function's calls are tested | Supported: 71% of unnoticed call deletions sit in fully killed functions (58-80%) |
| H4 | Individually removable tests are not jointly removable | Supported: group removal lost kills in 16 of 16 files |
| H5 | Per-test coverage contexts add large overhead | Supported: 2.48x slower pooled (1.74-3.88) |
| H6 | A few reruns miss intermittent tests | 2 intermittent tests in 480 runs, both order-dependent |

The study lives in [`study/`](study/) and is not part of the plugin: [pre-registration and deviations](study/PREREGISTRATION.md), pinned [corpus](study/corpus.toml), experiment scripts, gzipped raw data and the analysis that generates every table and figure. `make -C study all` rebuilds the analysis and the PDF from the raw data. The usefulness review of H2 survivors is still pending.

## Repository

- [`skills/test-suite-audit/`](skills/test-suite-audit/): the skill Claude follows.
- [`runner/`](runner/): the `tsa` runner (measurement, mutation, reports) and its tests.
- [`fixtures/known_answers/`](fixtures/known_answers/): a small project with planted gaps used by the runner's tests.
- [`docs/`](docs/): [product requirements](docs/PRD.md), [research notes](docs/RESEARCH.md), [behavioural ablation design](docs/BEHAVIOURAL_ABLATION.md).
- [`study/`](study/): the empirical study.

Planned, not yet implemented: semantic (LLM-proposed) mutants, LLM-directed null components, test-suite ablation experiments, and JS/TS support.

## Licence

MIT
