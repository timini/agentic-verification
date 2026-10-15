# Research: evidence-driven test-suite maintenance

Researched 15 October 2026. These are feasibility findings from primary documentation and research, not results from a working prototype. Tool capabilities must be verified against pinned versions during implementation.

## Findings and implications

| Source | What it supports | Product implication / limitation |
| --- | --- | --- |
| [Addy Osmani: Agentic Verification](https://addyo.substack.com/p/agentic-verification) | Verification, properties, differential checks, and deterministic feedback become central to agent-assisted development. | Audit the verification system itself; mutation scores do not replace explicit requirements. |
| [Chad Fowler: Relocating Rigor](https://aicoding.leaflet.pub/3mbrvhyye4k2e) | Generative implementations need explicit invariants and enforceable contracts. | Preserve durable behavioural specifications. This essay is an argument for rigor, not evidence that passing tests makes arbitrary rewrites safe. |
| [Coverage.py measurement contexts](https://coverage.readthedocs.io/en/latest/contexts.html) | Coverage can be attributed to dynamic execution contexts. | Build a test-to-code incidence matrix. Shared setup, import-time execution, and subprocesses need explicit handling. |
| [pytest-cov contexts](https://pytest-cov.readthedocs.io/en/latest/contexts.html) | `--cov-context=test` records individual tests, including parametrization. | Python offers a practical first adapter. Context attribution still needs validation for supported runner configurations. |
| [pytest flaky-test guidance](https://docs.pytest.org/en/stable/explanation/flaky.html) | Uncontrolled state, ordering, and isolation problems can produce intermittent failures. | Record environmental and order metadata; distinguish flaky observations from repeatable defects. |
| [mutmut repository](https://github.com/boxed/mutmut) and [architecture](https://github.com/boxed/mutmut/blob/main/ARCHITECTURE.rst) | Python mutation generation, selective test execution, incremental results, and baseline checks already exist. Fork support is required. | Reuse its operators/execution where practical. Validate export and attribution interfaces in a spike; do not assume a complete test-by-mutant kill matrix is available. Linux is the initial supported execution environment. |
| [StrykerJS configuration](https://stryker-mutator.io/docs/stryker-js/configuration/) and [incremental mode](https://stryker-mutator.io/docs/stryker-js/incremental/) | Coverage-guided execution and reuse of mutation results can reduce work; incremental runs still require a dry run. | Strong later JS/TS adapter. Cache provenance and invalidation matter; changed configuration/dependencies must invalidate this product's cache. |
| [State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/) | Industrial mutation analysis can use diff-based sampling and filtering to manage compute and reviewer attention. | Offer bounded audits and high-value findings rather than requiring exhaustive runs on every change. Sampling results must state their scope. |
| [A Comprehensive Study on Large Language Models for Mutation Testing](https://arxiv.org/abs/2406.09843) | Research evaluates LLM mutations, including effectiveness and validity/equivalence problems. The paper has evolved through revisions. | Agent mutation needs validity filters and comparison with classical operators; plausible edits alone are insufficient evidence. |
| [Beyond Rule-Based Mutation Testing: Test-Aware Mutant Generation Using Large Language Models](https://arxiv.org/abs/2609.35841) | A recent preprint studies mutants deliberately surviving base tests and evaluated against stronger oracles on coding benchmarks. | Promising experimental direction; benchmark findings do not establish production-repository reliability. Keep test-aware results separate from fixed-operator mutation scores. |
| [Mutahunter](https://github.com/codeintegrity-ai/mutahunter) | An existing open-source project already explores language-agnostic, LLM-assisted mutation testing. | Agent mutation alone is not novel. Differentiate through integrated cost analysis, evidence-backed ablation, retention policy, and reproducible maintenance decisions. Integration suitability remains untested. |
| [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/) | Property-based testing generates inputs and reduces failing examples. | Recommend properties where example tests miss input space; humans must validate the properties themselves. |
| [Claude Code skills](https://code.claude.com/docs/en/skills) | Skills use `SKILL.md`, supporting files, and explicit invocation. | Package the workflow as a skill, with repeatable measurement in a separate runner. Expensive experiments should be explicitly invoked. |

## Recommended design decisions

**Build an audit orchestrator, not another general mutation engine.** Existing tools supply much of the low-level work. The useful integration is the connection between execution cost, fault-detection contribution, behavioural intent, and validated recommendations.

**Repeated coverage is not a waste metric on its own.** Two tests can execute identical lines but assert different properties or exercise different values. Setup-heavy tests can also appear similar despite testing different outcomes. Treat overlap as a ranking signal and use mutation evidence plus requirements review before suggesting removal.

**Keep mutation populations separate.** Classical operators provide a more repeatable baseline. Agent-generated semantic faults explore missing behaviours, such as omitted tenant filtering, incorrect retry boundaries, or swallowed errors. Score and cost them independently. The follow-up behavioural-ablation population below is also reported separately. An LLM can also propose valid refactors or uncompilable changes: neither is a confirmed fault.

**Ablation must measure detection loss.** Removing a test from a green suite and observing green tells us very little. Compare which fixed faults the full and reduced suites catch, then confirm the final proposed reduction as a group. Individually redundant tests may be mutually indispensable when removed together.

**The oracle remains a product responsibility.** Independent prompts or models can diversify suggestions but cannot establish intended behaviour. Preserve reviewed contracts, incident regressions, properties, and historical bug reproductions as external checks on the audit. Differential comparison also inherits bugs in the reference implementation.

**Pruning and fast feedback are different decisions.** Move costly, valuable tests to an appropriate execution tier where justified. Retain a complete regression corpus for rewrites and scheduled checks. Database migration compatibility, data preservation, concurrency, and performance require evidence beyond line coverage and unit mutations.

## Unresolved implementation questions

- Can a pinned mutmut release expose stable mutant IDs, patches, and statuses without depending on private internals?
- What instrumentation is needed to distinguish unknown kill-matrix entries from actual non-kills when engines stop at first failure?
- How much do per-test contexts distort runtime, especially with shared fixtures and subprocesses?
- How often do semantic mutants provide useful findings beyond an equal-cost classical mutation budget?
- Which retention policies and minimum mutation populations transfer across repositories? Initial defaults must be treated as hypotheses.

These questions are explicit milestone gates in the [PRD](PRD.md).

## Follow-up: production-behaviour ablation

The clarified feature removes application behaviour rather than tests: no-op functions, null modules, skipped stages, and missing side effects. [Dedicated research and design notes](BEHAVIOURAL_ABLATION.md) cover extreme mutation testing, Descartes, PIT deletion/return operators, pseudo-tested methods, and statement-level evidence.

Design decision: deterministic deletion is the baseline; LLMs add capability selection and interface-compatible replacements. Whole-module substitutions remain an experimental extension. Preserve separate commands and data records for production-behaviour ablation and test-removal ablation. A parent mutation being killed does not establish protection of every child behaviour.
