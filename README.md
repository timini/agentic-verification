# Test Suite Auditor

A proposed Claude Code skill for keeping test suites fast, reliable, and effective at detecting faults.

**Status: research and product specification. No executable skill or audit runner has been implemented.**

The idea: measure test cost, coverage overlap, flakiness, and mutation detection; then remove production behaviours to check whether tests notice, and separately evaluate test-removal experiments to identify useful improvements. Repeated line coverage is a discovery signal, not proof that a test should be deleted.

- [Product requirements document](docs/PRD.md)
- [Research and source notes](docs/RESEARCH.md)
- [Behavioural ablation: null functions, modules, and removed side effects](docs/BEHAVIOURAL_ABLATION.md)

The proposed first implementation targets Python/pytest, with existing mutation tooling and an experimental agent-generated mutation layer. Reports distinguish measured results, inferred recommendations, and missing evidence.
