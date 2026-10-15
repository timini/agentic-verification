# Pre-registration: skill benchmark

Registered 16 October 2026, before any benchmark run. Deviations are added at the end with a date.

## Question

Does an agent that follows the test-suite-audit skill, with the `tsa` runner, give maintainers better evidence than the same agent without it? "Better" means its claims hold up when we check them independently.

## Design

- **Projects:** the eight study projects at the same pinned commits (`corpus.toml`).
- **Arms:** *skill* and *baseline*. Both are Claude Code subagents on the same model (Sonnet), given the same task text. The skill arm also gets the full text of `SKILL.md`, the paths of its reference files, and the runner command. The baseline arm may use any tool it likes, including installing packages.
- **Workspace:** each run gets a fresh copy of the project with its own virtual environment (same tooling as the study, including pytest-randomly and pytest-cov).
- **Task:** find (1) production behaviour the tests would not catch if broken or removed, (2) tests that can be deleted to cut maintenance, and (3) flaky tests. End with a JSON block: `untested` (up to 10 items of file, line, behaviour), `removable_tests` (node IDs), `flaky_tests` (node IDs). Guidance: about 20 minutes of tool time; do not commit.
- **Execution:** 16 runs, up to 4 at a time; skill and baseline runs of the same project start together.

Why subagents: launching headless Claude Code with permissions bypassed was blocked by the local safety policy. Subagents test the skill's instructions and runner, not whether Claude Code would trigger the skill on its own.

## Independent verification

Done by `study/bench/verify.py` against pristine copies, never by the agents.

- **Untested-behaviour claims.** For each claimed (file, line) in production source: generate every classical and deletion mutant whose region starts on that line, plus body replacements of a function whose first body line it is (up to 6, seeded), and run each against the tests covering it.
  - *Verified*: at least one valid, activated mutant survives, or the line is executable and no test covers it.
  - *Refuted*: every valid mutant is killed.
  - *Unverifiable*: not a production source line, not executable, or no mutant can be generated there.
- **Removal recommendations.** The recommended tests are removed as a group. Up to 100 mutants on lines they cover run against all covering tests (full outcome per test). The recommendation is *refuted* if any mutant killed only by removed tests exists. An empty list is not a recommendation.
- **Flaky claims.** Compared with the 60 study runs per project (H6): *confirmed* if the test was intermittent there; otherwise *not observed*.
- **Safety.** A hash of every `.py` file under the project's tests and source paths, before and after the run.

## Outcomes

- **B1 (primary):** precision of untested-behaviour claims, verified / (verified + refuted), pooled per arm, and paired per project. Expected: higher for the skill arm.
- **B2:** share of runs with at least one refuted removal recommendation. Expected: lower for the skill arm.
- **B3:** runs that modified or deleted test or source files. Expected: zero for the skill arm.
- **Descriptive:** verified claims per run, unverifiable claims, flaky claims confirmed, wall-clock time per run.

With 8 projects per arm, results are reported as counts with Wilson intervals and a paired sign count, not as significance tests.
