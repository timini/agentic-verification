# Pre-registration: evidence for the Test Suite Auditor design

Registered 15 October 2026, before any study data was collected. Changes after this commit are listed under "Deviations" with a date and reason. The git history of this file is the record.

## Purpose

The PRD bases several design rules on published research, mostly on Java. This study tests whether those rules hold for mature open-source Python projects. Results decide which PRD requirements stay, change, or are dropped. The study code in `study/` is evidence for the plugin and is not shipped with it.

## Corpus

Eight projects pinned in [`corpus.toml`](corpus.toml) at release commits. Each runs in its own uv virtual environment on CPython 3.12.

Exclusion rule: a project is excluded if its pristine suite does not produce identical pass/fail outcomes in 3 consecutive runs after install, or if its suite takes more than 10 minutes. Individual tests that fail or vary in the baseline are removed from the analysed scope and counted. Excluded projects and tests are reported.

## Instrument and definitions

- **Test**: a pytest node ID, including parameter ID.
- **Coverage set C(t)**: the set of (file, line) pairs in eligible source files recorded for test `t` by coverage.py with `--cov-context=test`. Only the "run" phase context is used; setup/teardown contexts are recorded separately.
- **Mutant**: one patch applied to one copy of pristine source. Never combined with another mutant.
- **Kill**: under the mutant, a test that passed in all baseline runs fails or errors. Collection/import errors make the mutant *invalid*, not killed. A run that exceeds `10 × baseline_duration + 10 s` is a *timeout*.
- **Activation**: a sentinel inserted into the mutated region (only in the disposable copy) records whether it executed during the run. A mutant whose region never executed is *not activated* and is not counted as a survivor.
- **Survivor**: a valid, activated mutant that no test in the evaluated scope kills.
- **Classical population**: mutmut operators (pinned version recorded in `study/uv.lock`).
- **Deletion population**: our deterministic AST operators: whole-function body replacement (`pass` / `return None` / a type-appropriate constant: `0`, `""`, `False`, empty container) and deletion of single expression statements that are calls. Async functions, generators and context managers are excluded from body replacement.
- Seed: `20261015` for all sampling. Sampling is stratified by source file, proportional to eligible sites.

## Hypotheses, metrics and decision rules

Confidence intervals: Wilson 95% for proportions; percentile bootstrap (10,000 resamples, clustered by project) for ratios and pooled shares. "Supported" requires the stated threshold on the CI bound, not the point estimate.

### H1. High coverage overlap does not reliably indicate redundancy

- Sample: pairs of tests in the same project with Jaccard(C(a), C(b)) ≥ 0.9 and |C(a) ∪ C(b)| ≥ 5. Up to 50 pairs per project, chosen at random.
- Mutants: classical and deletion mutants on lines in C(a) ∪ C(b), up to 40 per pair. Each test is run individually against each mutant, so kill sets are complete for the pair (no stop-at-first-kill).
- Primary metric: share of pairs that are *mutually non-dominated*, meaning each test kills at least one mutant the other does not.
- Supported if the pooled share's 95% lower bound exceeds 10%.
- Secondary: Spearman correlation between coverage Jaccard and kill-set Jaccard over all sampled pairs, plus a comparison sample of 50 pairs per project with Jaccard in [0.5, 0.9).

### H2. Deterministic deletion finds pseudo-tested code more cheaply than classical mutation

- Each project gets a fixed 20-minute wall-clock budget per strategy (classical and deletion), run on the same machine, one after another, in randomized order. Each strategy draws mutants in seeded random order until the budget is spent.
- Primary metric: activated, valid survivors per CPU-minute.
- Supported if the deletion/classical ratio of that rate is above 1 in a majority of included projects and the clustered bootstrap lower bound of the pooled ratio exceeds 1.
- Usefulness check: a stratified sample of 50 survivors (25 per strategy, spread across projects) is labelled by a human reviewer as *real gap*, *optional behaviour*, *equivalent* or *unclear*, from code and documentation, blind to strategy where practical. A second pass on 20 of them measures agreement (Cohen's kappa). No model output is used to decide equivalence. Report the real-gap share per strategy. This check is descriptive, not a hypothesis test.

### H3. Killing a whole-function mutant does not mean the function's effects are tested

- Population: functions where every applicable body replacement was valid, activated and killed.
- Experiment: every call-statement deletion inside those functions, each against pristine source (no parent mutation). Capped at 300 per project, seeded sample if more.
- Primary metric: share of activated, valid statement-deletion survivors that lie inside functions whose body replacements were all killed. The Java comparison point is the 48% reported in "Exploring pseudo-testedness" (see docs/BEHAVIOURAL_ABLATION.md); we do not test equality with it.
- Supported if the pooled share's 95% lower bound exceeds 10%.
- Secondary: share of fully-killed functions that contain at least one surviving statement deletion.

### H4. Individually removable tests are not jointly removable

- Units: test files with 10 to 60 tests (after exclusions). Up to 3 files per project, chosen at random.
- Mutants: up to 150 classical plus deletion mutants on lines covered by that file's tests. Full kill matrix for the file's tests, with each test run separately.
- A test is *leave-one-out redundant* if removing it alone loses no kills. Let R be the set of such tests. Remove all of R together and count kills lost.
- Primary metric: share of files with |R| ≥ 2 where removing R loses at least one kill.
- Supported if that share's 95% lower bound exceeds 20%.
- Secondary: total kills lost; the greedy set-cover minimum subset size compared with the size of the remaining suite.

### H5. Per-test coverage contexts add noticeable runtime overhead

- Conditions: no coverage; `--cov`; `--cov --cov-context=test`. Ten runs per condition per project, interleaved as ABC blocks in random order, with one discarded warm-up run.
- Primary metric: median wall-time ratio, contexts over no coverage, per project and pooled.
- Supported if the pooled ratio's 95% lower bound exceeds 1.2.
- Secondary: overhead of contexts over plain coverage.

### H6. A few repeat runs miss intermittent tests

- 30 runs in the default order, plus 30 in random order (`pytest-randomly` with seeds 1 to 30), per project.
- Primary metric: number of tests with both a pass and a fail across the 60 runs, and for each one the earliest run index where it was first observed.
- This hypothesis is descriptive. A result of zero intermittent tests is reported as a null result, with the per-test upper bound on failure rate (about 3/60) stated. We also report how many of the observed intermittent tests a 3-run check would have caught.

## Environment

Primary runs on macOS arm64 (Apple silicon), recorded per run. Replication of H1, H3 and H5 on two projects runs on GitHub Actions `ubuntu-latest`. Machine load is not controlled beyond running one experiment at a time. Every raw record stores the project SHA, runner git SHA, tool versions, Python version, platform and seed.

## Analysis and reporting

Raw observations are append-only JSONL under `study/data/raw`. All tables, figures and numbers in the paper are generated from them by `study/analysis`. Null and negative results are reported. Reviewer labels are stored as data.

## Deviations

All of the following were decided on 15 October 2026, before any mutant, coverage, overlap or flakiness data was collected. Only E0 baseline and H5 timing runs existed at that point.

1. **Kill sets in H1 and H4.** "Each test is run individually" is implemented as one pytest session per mutant that runs every selected test without stopping at the first failure, recording each test's outcome. Kill sets are complete; tests in the same session could in principle affect each other through shared state.
2. **Activation check.** Activation uses `sys.monitoring` line events on the first line of the mutated region instead of a sentinel inserted into the mutant. The mutant source is not altered.
3. **H3 sampling.** Call-statement deletions are sampled from *all* eligible functions (cap 300 per project), not only from fully killed ones, because the primary metric's denominator is all statement-deletion survivors. Each deletion records its parent function's status.
4. **Harness setup errors in E0.** The first baseline attempt for attrs, dateutil, marshmallow and tomlkit failed before any test ran: test dependencies live in dependency groups that `.[tests]` did not install, tomlkit needs a git submodule, and dateutil's warnings-as-errors filter rejects a pytest 9 deprecation. Those failed records were deleted (an exception to the append-only rule) and the projects were re-run after fixing `corpus.toml`. No project was excluded.
5. **Unstable test IDs.** marshmallow parametrizes six tests with the current time, so their node IDs differ on every run. All their outcomes passed. They are counted as varying and excluded from scope; this is not flakiness and does not trigger the project exclusion rule.

The following was found after data collection, on 15 October 2026.

6. **Test files in toolz's mutant population.** toolz keeps its tests inside the package (`toolz/tests`), and the source path `toolz` included them, so H2 and H3 mutated test code: 9,585 classical and 239 deletion mutants in H2, and 239 body and call mutants in H3. H1 and H4 drew mutants from lines covered in the run phase and contained none. Every affected toolz run was exhaustive (no budget or sampling cap was reached), and each mutant runs independently, so the analysis drops these mutants, which is equivalent to never generating them. The runner now excludes test files from mutation.

