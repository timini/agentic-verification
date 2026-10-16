# Pre-registration: change verification and removal checks (H7, H8 and the verify benchmark)

Registered 16 October 2026, before any commit was selected or any run made. Deviations are added at the end with a date.

The plugin's `verify` function claims to help an agent leave a change properly tested. This document tests three things:

- whether real changes in mature libraries leave changed code unchecked (H7, about the problem);
- whether an agent following the `verify` skill writes tests that catch more than the same agent without it (V1 to V4, about the skill);
- whether the removal sets the deep audit proposes keep their detection on mutants they were not chosen from (H8, about the audit's bloat finding).

One pilot run was made before registration: a 12-minute deep audit of toolz while developing the feature. It proposed 84 of 188 tests for removal. No prune-check was run on it, and it is not part of H8.

## Commit selection

`study/bench2/select.py`, deterministic, run once. For each corpus project, walk the history back from the pinned commit (`git rev-list --no-merges`, at most 300 commits). The parent of a commit is its first parent.

- **Change commits (for H7):** commits that change at least one executable line in the production source. The 3 most recent per project.
- **Fault commits (for the benchmark):** commits that also meet all of these conditions:
  - they change both production source and test files;
  - every changed source line lies inside a function or method that exists under the same qualified name in the parent, so the commit changes existing behaviour and adds no new names;
  - they change between 2 and 60 executable source lines;
  - at least one test from the commit's changed test files passes on the commit's source and fails on the parent's source, with the commit's tests in both cases. That test is the evidence that the commit changed observable behaviour.

  The 2 most recent per project.

Environments are the study's existing per-project virtual environments. A commit whose tests cannot be collected in that environment is skipped, and every skip is recorded.

## H7: real changes leave changed code unchecked

For each change commit, run `verify --base <parent>` on the commit with the project's own tests at that commit, with a 20-minute budget.

- **Primary metric:** share of commits with verdict `gaps` (a surviving mutant or an uncovered line among the changed lines).
- **Expected:** at least half.
- Also reported: changed-line detection rate K/(K+S+U), uncovered changed lines, and runtime.

## H8: jointly chosen removal sets hold on held-out mutants

For each corpus project, run `deep` with a 20-minute budget, then `prune-check` on its removal candidates with `--from-run` (so the audit's own mutants are excluded) and a 20-minute budget.

- **Primary metric:** pooled share of held-out killed mutants whose kill would be lost, that is, all killers are in the removal set.
- **Expected:** below 2%.
- Also reported:
  - per-project verdicts, with the number of projects refuted (descriptive; a single lost kill refutes);
  - covered lines lost;
  - the share of tests and of summed test time in each set.

## Benchmark: does the verify skill help?

- **Task workspace:** a git repository whose `HEAD` is the parent commit and whose working tree holds the commit's source changes but not its test changes. The upstream developers' tests for the change are therefore absent. The workspace has its own virtual environment, with the same tooling as the study.
- **Arms:** *skill* and *baseline*, Claude Code subagents on the same model (Sonnet), same task text. The skill arm also gets the full text of `plugin/skills/verify/SKILL.md` and a runner command pinned to the commit that registers this document. The baseline arm may use any tool.
- **Task text, for both arms:**
  - The repository has an uncommitted change to production code; `git diff` shows it. The commit message is given as the description of the change.
  - Make sure the change is properly verified by the test suite, adding or changing tests as needed.
  - Do not modify production source files and do not commit. Aim for about 20 minutes.
  - End with a JSON block listing the tests added.
- **Execution:** 2 arms times up to 16 tasks, up to 4 runs at a time; both arms of a task start together.

## Outcomes, measured by `study/bench2/measure.py` on copies of the final workspaces

- **V1 (primary, real fault):** the agent's tests detect the real change if at least one test in a test file the agent created or modified passes on the commit's source and fails on the parent's source. Reported as tasks detected per arm, and as a paired count (skill only, baseline only, both, neither). Expected: skill at least as many, more in the paired count.
- **V2:** changed-line detection rate of the final suite, K/(K+S+U), from a `verify` run with no mutant cap and a 30-minute budget. The skill arm optimises against this measure, so V2 is supporting evidence only. V1 is the held-out test. The upstream developers' own tests are measured the same way, as a human reference.
- **V3 (safety):** runs that modified production source, or removed existing test node IDs. Expected: zero for the skill arm.
- **V4:** the final suite passes on the commit's source, so no test the agent wrote is left failing.
- **Descriptive:** tests added and wall-clock time per run.

With at most 16 tasks, results are counts with Wilson intervals and paired counts, not significance tests.

## Deviations
1. 16 October 2026, during the runs: the workspace builder used `git archive`, which leaves submodules empty, so tomlkit's `tests/toml-test` conformance fixtures were missing and `tests/test_toml_tests.py` could not be collected. Both tomlkit baseline runs had already finished (they ran the other test files); the two tomlkit skill runs were in progress. The fixtures, at the commit each parent pins, were then added to all four tomlkit workspaces, untracked and ignored by git. The builder now fills submodules, so measurement copies, the upstream reference and H7 have them. H7 runs for tomlkit made before the fix are repeated.
2. 16 October 2026, during the runs: the benchmark exposed three defects in how `verify` words its verdict. None changes which mutants are generated or how they are run.
   - With no valid mutant on the changed lines (for example a decorated function), it said `verified`. It now says `incomplete`.
   - A test failing on the pristine checkout, unrelated to the change, made the verdict `gaps`. Such tests are already left out of mutant scope, so they are now a caveat in the reasons.
   - Timed-out and invalid mutants were counted among the killed in the summary sentence.

   A fourth issue: the "changed tests that catch nothing" finding counted every test in an edited file. It now counts only tests whose own lines changed. The skill arm used the runner pinned at registration, so its agents saw the old wording, and the replies record what they saw. H7 was started before the fixes. Its verdicts are recomputed from the raw results by the definition registered above (a surviving mutant or uncovered line among the changed lines), so they do not depend on the wording. The runner also now resolves a package directory passed as the path to the project root: 6 of the 14 skill runs first passed a package directory and got `no change`.
