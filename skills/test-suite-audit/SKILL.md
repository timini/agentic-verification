---
name: test-suite-audit
description: Audit a Python/pytest test suite for slow tests, intermittent failures, coverage overlap and weak fault detection (mutants and deleted behaviour that no test notices), and report evidence-backed findings. Use when the user asks to audit, review, speed up, prune or strengthen their test suite, or asks which tests are useful. Report-only.
argument-hint: "quick | deep [--budget-minutes N] [--max-mutants N] [path]"
allowed-tools: "Read Glob Grep Bash"
---

# Test suite audit

Arguments: `$ARGUMENTS`. The first word is the mode: `quick` (default) or `deep`. Anything
else is passed to the runner. `semantic`, `ablate-behaviour` and `ablate-tests` are planned
but not available in this version: say so and offer `deep` instead.

## Rules

- The runner measures; you interpret. Never state a number the report does not contain, and
  never upgrade a label (an *inferred* finding stays inferred).
- Report-only. Do not edit, delete, skip or quarantine tests, and do not change source code,
  unless the user asks for a specific change after reading the report.
- Coverage overlap is never evidence that a test is redundant. A surviving mutant is a
  candidate gap, not proof of a bug. Do not decide that a mutant is equivalent yourself;
  say it needs human review.
- When a user pushes for one of these conclusions, explain the measured reason from
  [the study evidence](reference/evidence.md) instead of just declining.
- The runner works in a disposable copy. It writes only to `.test-suite-audit/` in the
  project. Suggest adding that directory to `.gitignore` if it is not ignored already.

## Steps

1. **Check the target.** Confirm it is a pytest project. Look for `test-suite-audit.toml`;
   if absent, the runner discovers source packages, test directories and the interpreter
   (`.venv/bin/python`, then `python3`). If discovery looks wrong (for example a monorepo),
   write a `test-suite-audit.toml` only after asking. Keys: `python`, `source` (list of
   package dirs), `tests`, `pytest_args`, `env`, `workers`, `protected`.
   The target interpreter needs Python 3.12+ and `pytest-cov` for coverage and mutation.
   If `pytest-cov` is missing, say coverage will be "not assessed" and offer the install
   command; do not install anything without asking.
2. **State the budget** before running: quick is 5 minutes (one baseline run, timings,
   coverage, overlap; no mutants); deep is 30 minutes by default (three file-order and,
   if pytest-randomly is installed, three random-order baseline runs; coverage; every
   deletion mutant; then a seeded sample of classical mutants until the budget ends).
3. **Run the runner:**
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/runner" tsa <mode> <path> [options]
   ```
   Use a Bash timeout above the budget (budget + 2 minutes). Progress goes to stderr; the
   last stdout line is JSON with the report paths.
4. **Read `report.json`** (full evidence) and `report.md`. See
   [reading the report](reference/report.md) for statuses, labels and the detection rate.
5. **Summarise for the user:** the top findings in the report's order, each with its label,
   the evidence, and the next validation step. Give the reproduction command for at least
   one mutant finding (`tsa replay --run <dir> --mutant <id>`). List what was not assessed.
   Link `report.md`.
6. **Offer follow-ups**, not changes: replaying a survivor, drafting a test that passes on the
   original and fails on a confirmed mutant, or a deeper run with a larger budget.

If the run is partial (budget or interruption), say so first and explain which steps are missing.
