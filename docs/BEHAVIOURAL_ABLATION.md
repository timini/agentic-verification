# Behavioural ablation: remove capabilities and test the tests

Research and proposed design · 15 October 2026 · Not implemented

## What this means

Behavioural ablation temporarily removes **production behaviour**, while leaving the test suite unchanged. Replace a function with a no-op, substitute an interface-compatible null module, or suppress a specific effect; then ask whether the existing tests detect the loss. This differs from **test-suite ablation**, which removes tests to measure their contribution.

The closest established terms are extreme mutation testing (whole-method replacement), statement-deletion mutation testing, and call-removal mutation. Whole-module null implementations and LLM-directed selection are proposed extensions here, not capabilities established by the cited Java tools.

## Research foundation

| Primary source | Evidence | Design consequence |
| --- | --- | --- |
| [Descartes tool paper](https://arxiv.org/abs/1811.03045) and [implementation](https://github.com/STAMP-project/pitest-descartes) | Descartes implements extreme mutation operators as a PIT engine for Java, targeting pseudo-tested methods. | Start with simple deterministic method-body replacements; an LLM is not needed for every mutation. Reuse the idea, not the Java adapter, for the Python MVP. |
| [A Comprehensive Study of Pseudo-tested Methods](https://arxiv.org/abs/1807.05030) | Studies covered methods whose effects can be suppressed without failing tests. Its manual analysis also shows that developers do not necessarily consider every such finding worth fixing. | Report observed missing protection and review behavioural importance. Survival does not prove a defect or justify deleting the original code. |
| [Extreme mutation testing in practice: An industrial case study](https://arxiv.org/abs/2103.08480) | Compares traditional and extreme mutation testing in an industrial project with over 11,000 unit tests, reporting practical execution/analysis benefits and adoption challenges. | A bounded coarse pass is plausible; its speed and usefulness must still be measured on our Python pilots. |
| [PIT mutation operators](https://pitest.org/quickstart/mutators/) | Documents void-call removal, non-void-call replacement, and null/empty return operators. It warns that some null substitutions readily cause runtime exceptions. | Distinguish replacing a return value from removing a whole body, and record whether detection comes from an assertion or an incidental runtime failure. |
| [Deng, Offutt, and Li: Empirical evaluation of the statement deletion mutation operator](https://researchconnect.suny.edu/en/publications/empirical-evaluation-of-the-statement-deletion-mutation-operator/) | The 2013 study evaluates deletion operators on 40 Java classes, using tests designed against deletion mutants and evaluating them against other mutants. | Statement deletion is an established economical candidate family; do not claim it replaces all operators across languages or repositories. |
| [Exploring pseudo-testedness: empirically evaluating extreme mutation testing at the statement level](https://eprints.whiterose.ac.uk/id/eprint/216881/) | Across 27 Java projects, the study reports 722 pseudo-tested statements, 48% outside pseudo-tested methods. | Test individual effects even inside methods whose whole-body mutants are killed. Coarse detection cannot certify the method's internal behaviours. |

These sources establish related techniques, not the effectiveness of an LLM-driven Python implementation. That is a product hypothesis to evaluate.

## Operator catalogue

| Operator | Example intervention | Interpretation constraint |
| --- | --- | --- |
| Whole-function suppression | Replace body with `pass`, `None`, or an appropriate constant | Record every applicable replacement attempted; one surviving constant does not establish all effects are untested. |
| Call/statement deletion | Omit a notification or persistence call | Record whether argument-evaluation effects were also removed; these are distinct faults. |
| Targeted side-effect suppression | Retain calculation and return value, omit cache invalidation | Confirm the side effect was required and actually absent in the execution. |
| Guard/stage bypass | Skip validation or a processing stage | Preserve enough data shape to exercise downstream behaviour without implementing an alternative algorithm. |
| Null component/module | Preserve public exports, signatures, and lifecycle protocols but suppress a declared capability | Treat as a composite intervention; do not count one module result as independent evidence for every function. |

Use fixed operators for simple deletions and constants. Use the LLM to identify meaningful capabilities, propose structurally compatible substitutes, explain expected missing effects, and choose follow-up experiments. Replacement values come from declared types/protocols and documented contracts; never hard-code expected test answers or silently reproduce the removed capability.

For async functions, generators, context managers, and stateful objects, preserving the callable name is insufficient. Preserve the relevant await/iteration/entry/exit protocol or explicitly reject the proposal as unsupported. A null module preserves imports and required public surface; literally setting a module to `None` is normally just an import or attribute failure probe.

## Worked example

```python
# Original production function
def save_order(order):
    database.save(order)
    publish_order_created(order)
    return order.id

# Mutant: omit event publication, preserve persistence and return value
def save_order(order):
    database.save(order)
    return order.id
```

A test that checks only the returned ID may pass. A test that checks event publication should fail. A stronger integration check may verify the downstream outcome. The audit records which evidence exists rather than assuming that interaction assertions alone establish end-to-end behaviour.

A report might say: “The existing tests executed this path and remained green when order-created publication was removed. The reviewed contract requires publication; no detector was observed in the audited suite.” This is a scoped finding, not proof that every possible test or environment misses it.

## Experiment protocol

1. Establish a clean passing baseline and freeze tests, configuration, dependencies, and source revision. Select a production capability and document the intended contract and intervention.
2. Generate one isolated patch. Check syntax/imports, public interface, and protocol compatibility. Preserve exact artifacts, operator origin, replacement value, and any parent experiment.
3. Verify the baseline path is covered and the patched implementation is loaded. Mocks, alternate imports, cached code, feature flags, and subprocesses may prevent activation. Use observation hooks outside assertions or runner tracing to verify activation without changing the test oracle.
4. Execute selected tests for feedback. Confirm important survivors against the full supported scope, subject to the budget; otherwise label them provisional.
5. Record both mutation status and detection mechanism. Reproducible runtime exceptions caused by a valid mutant are legitimate mutation kills, but weaker evidence of a specific behavioural assertion. Syntax/build/import-invalid replacements are invalid, and unrelated environment failures are infrastructure failures.
6. For survivors, verify a behavioural difference with a witness or reviewed contract. Classify as confirmed gap, intentionally optional behaviour, equivalent in assessed scope, mock-shielded/not activated, or unresolved. Do not silently discard findings or declare equivalence from model opinion.
7. Propose a minimal new test when appropriate. It must pass on baseline and fail on the confirmed ablation. Evaluate on independent faults before claiming general improvement.

## Hierarchical search without false confidence

A module → function → side-effect search can prioritize useful experiments, but it is not binary search and need not be monotonic. A coarse replacement can crash early and conceal an unasserted effect; multiple removals can also interact or cancel out.

Use coarse outcomes to choose the next experiment, then replay each finer intervention against the pristine baseline. Sample targeted effects in **both killed and surviving** parent groups. Reserve a configured portion of the budget for this independent fine-grained sampling. Track parent/child lineage but never infer descendant results from a parent kill.

## Metrics and evaluation

Keep behavioural-ablation outcomes separate from classical operator and adversarial semantic scores. Report eligible targets, attempted replacements, activation-confirmed experiments, killed/survived/invalid/unresolved counts, detection mechanism, and confirmed actionable gaps per compute minute and per review minute.

A “candidate pseudo-tested method” label requires covered execution and no failing tests for all applicable replacements in the declared operator set, with no unresolved attempts. Always show that set and scope. One surviving variant is a surviving ablation, not a blanket pseudo-tested classification. Whole-module results are labelled capability-level experiments.

Compare equal-budget classical-only, deterministic-deletion-only, and LLM-directed strategies on the same revisions. Deduplicate overlapping discoveries; use reviewed contracts and held-out historical faults to assess usefulness. Measure invalid proposals, incidental crashes, unique confirmed gaps, model cost, and reviewer effort. No claimed speedup or detection improvement is established until this evaluation runs.

## Delivery decision

Include deterministic function/call deletion in the initial mutation feasibility spike. Pilot LLM-assisted null modules and targeted capability suppression behind explicit invocation. Keep test-removal ablation as a separate feature with different commands, records, and acceptance cases. See [PRD F6a](PRD.md#f6a-ablate-production-behaviour) for requirements.
