"""Audit orchestration for the ``quick``, ``deep`` and ``verify`` commands.

``quick`` and ``deep`` audit the whole suite. ``verify`` checks one change: it runs every
mutant on the lines changed since a git revision and reports whether the tests catch them.
``prune-check`` tests a proposed set of test removals against mutants on the lines those tests
run, and reports any kill or covered line the removal would lose.

Every step records evidence first and derives findings from it afterwards. All execution happens
in a disposable copy of the project; the user's checkout is only read. When the budget runs
out or the user interrupts, the steps completed so far are reported and the rest are marked
"not assessed".
"""

import random
import statistics
import tempfile
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import diff, fingerprint
from .budget import Budget
from .config import AuditConfig
from .evidence import coverage_matrix
from .evidence.overlap import jaccard_pairs, multiplicity
from .mutation import classical, deletion, model
from .mutation.execute import Executor, MutantResult, Task
from .mutation.model import Mutant
from .pytest_run import run_pytest

SCHEMA_VERSION = 1
OVERLAP_THRESHOLD = 0.9
COVERAGE_EXCLUDE = r"#\s*(pragma|PRAGMA)[:\s]?\s*(no|NO)\s*(cover|COVER)"
SLOW_TEST_S = 0.1  # below this a test is not worth a "slow" finding
SEED = 20261015
CLI = "agentic-verification"
LOOP_TARGET_S = 60  # a suite slower than this is too slow to run after every agent edit
NO_KILL_MIN_SCOPE = 5  # a test must run against at least this many valid mutants to be called weak


@dataclass
class Finding:
    id: str
    category: str
    title: str
    label: str  # measured | inferred | unverified | not assessed
    severity: int  # higher sorts first
    detail: str
    action: str
    evidence: list[str] = field(default_factory=list)
    reproduce: str | None = None


@dataclass
class AuditState:
    mode: str
    cfg: AuditConfig
    budget: Budget
    out_dir: Path
    run_id: str = field(default_factory=lambda: time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4])
    run: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    baseline: dict = field(default_factory=dict)
    timing: dict = field(default_factory=dict)
    flakiness: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    overlap: dict = field(default_factory=dict)
    mutation: dict = field(default_factory=dict)
    not_assessed: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    status: str = "complete"
    stable: frozenset[str] = frozenset()
    cov: coverage_matrix.CoverageMatrix | None = None
    durations: dict[str, float] = field(default_factory=dict)
    startup_s: float = 2.0
    markers: dict[str, list[str]] = field(default_factory=dict)
    change: dict = field(default_factory=dict)  # verify mode: the change under test and the verdict
    efficacy: dict = field(default_factory=dict)  # deep mode: weak tests and a jointly removable set
    prune: dict = field(default_factory=dict)  # prune-check mode: the removal set and the verdict
    changed: diff.Change | None = None


def run_audit(cfg: AuditConfig, mode: str, budget_minutes: float, max_mutants: int | None, out_root: Path,
              progress=print, base: str | None = None, removed: list[str] | None = None,
              exclude_ids: frozenset[str] = frozenset(), seed: int = SEED + 1) -> AuditState:
    st = AuditState(mode, cfg, Budget(budget_minutes * 60), out_root)
    if mode == "verify":
        st.changed = diff.changed_lines(cfg.project.root, base or "HEAD")
    st.out_dir = out_root / st.run_id
    st.out_dir.mkdir(parents=True, exist_ok=True)
    st.run = {
        "id": st.run_id, "mode": mode, "budget": st.budget.describe(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "fingerprint": fingerprint.collect(cfg.project.root, cfg.project.python),
        "config": {"root": str(cfg.project.root), "source": list(cfg.project.source), "tests": list(cfg.project.tests),
                   "pytest_args": list(cfg.project.pytest_args), "python": str(cfg.project.python)},
        "discovery": cfg.discovered,
    }
    progress(f"Budget: {st.budget.describe()}. Output: {st.out_dir}")
    with tempfile.TemporaryDirectory(prefix="tsa-audit-") as tmp:
        ws = cfg.project.copy_to(Path(tmp) / "proj")
        steps = [("inventory", _inventory), ("baseline", _baseline), ("coverage", _coverage)]
        if mode == "deep":
            steps.append(("mutation", lambda s, w: _mutation(s, w, max_mutants, progress)))
        elif mode == "verify":
            steps.append(("mutation", lambda s, w: _verify_mutation(s, w, max_mutants, progress)))
        elif mode == "prune-check":
            st.prune = {"tests": sorted(set(removed or [])), "excluded_mutants": len(exclude_ids), "seed": seed}
            steps.append(("mutation", lambda s, w: _prune_mutation(s, w, max_mutants, exclude_ids, progress)))
        try:
            for name, fn in steps:
                if st.budget.exhausted():
                    st.not_assessed[name] = "budget exhausted before this step"
                    st.status = "partial"
                    continue
                progress(f"{name}...")
                fn(st, ws)
        except KeyboardInterrupt:
            st.status = "partial (interrupted)"
            for name, _ in steps:
                if not getattr(st, name, None) and name not in st.not_assessed:
                    st.not_assessed[name] = "interrupted"
    if mode == "quick":
        st.not_assessed["mutation"] = "quick mode runs no mutants; use deep"
        st.not_assessed["flakiness"] = "quick mode runs the suite once; intermittency needs repeats"
    st.run["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    st.run["status"] = st.status
    if mode == "deep" and st.mutation.get("results"):
        _efficacy(st)
    if mode == "verify":
        _verdict(st)
    _derive_findings(st)
    return st


# ---------------------------------------------------------------- steps

def _inventory(st: AuditState, ws) -> None:
    r = run_pytest(ws, collect_only=True, timeout_s=st.budget.remaining())
    items = r.collected or []
    st.markers = {c["nodeid"]: c["markers"] for c in items}
    st.inventory = {"collected": len(items), "returncode": r.returncode,
                    "collection_error": r.collection_error,
                    "markers": dict(sorted(_count(m for c in items for m in c["markers"]).items())),
                    "property_test_files": _property_test_files(ws)}
    if r.collection_error:
        st.inventory["error"] = r.output_tail[-1500:]


def _property_test_files(ws) -> int:
    """Test files that use Hypothesis. Properties check inputs the author did not choose."""
    n = 0
    for t in ws.tests:
        base = ws.root / t
        for f in (sorted(base.rglob("*.py")) if base.is_dir() else [base]):
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            if "hypothesis" in text and ("@given" in text or "@hypothesis.given" in text):
                n += 1
    return n


RANDOM_ORDER_RUNS = {"deep": 3, "verify": 1}


def _random_order_project(ws):
    """The workspace project with pytest-randomly enabled, or None if it is not installed.

    Same-order reruns cannot reveal order dependence, which was the only kind of
    intermittency observed in our study (H6), so deep mode varies order when it can.
    """
    import subprocess
    from dataclasses import replace

    probe = subprocess.run([str(ws.python), "-c", "import pytest_randomly"], capture_output=True)
    if probe.returncode != 0:
        return None
    args, skip = [], False
    for i, a in enumerate(ws.pytest_args):
        if skip:
            skip = False
            continue
        if a == "-p" and i + 1 < len(ws.pytest_args) and ws.pytest_args[i + 1] == "no:randomly":
            skip = True
            continue
        args.append(a)
    return replace(ws, pytest_args=tuple(args))


def _baseline(st: AuditState, ws) -> None:
    runs = 3 if st.mode == "deep" else 1
    outcomes, walls, overheads, durs = [], [], [], defaultdict(list)
    setups = defaultdict(list)
    for _ in range(runs):
        if st.budget.exhausted():
            break
        r = run_pytest(ws, timeout_s=st.budget.remaining())
        outcomes.append({k: v.outcome for k, v in r.outcomes.items()})
        walls.append(r.wall_s)
        overheads.append(r.wall_s - sum(v.duration_s for v in r.outcomes.values()))
        for k, v in r.outcomes.items():
            durs[k].append(v.duration_s)
            setups[k].append(v.setup_s)
        if r.timed_out:
            break
    ids = set().union(*outcomes) if outcomes else set()
    stable = {t for t in ids if all(o.get(t) == "passed" for o in outcomes)}
    # A test missing from some runs has an unstable ID (e.g. parametrized with the current time).
    unstable_ids = sorted(t for t in ids if any(t not in o for o in outcomes))
    varying = sorted(t for t in ids if t not in unstable_ids and len({o.get(t) for o in outcomes}) > 1)
    failing = sorted(t for t in ids if t not in varying and outcomes[0].get(t) in ("failed", "error"))
    st.stable = frozenset(stable)
    st.durations = {k: statistics.median(v) for k, v in durs.items()}
    st.startup_s = max(statistics.median(overheads), 2.0) if overheads else 2.0
    st.baseline = {"runs": len(outcomes), "tests": len(ids), "stable_pass": len(stable), "failing": failing,
                   "varying": varying, "unstable_ids": unstable_ids,
                   "skipped": sorted(t for t in ids if outcomes[0].get(t) in ("skipped", "xfailed"))}
    st.timing = {
        "wall_s": walls, "median_wall_s": statistics.median(walls) if walls else None,
        "samples": len(walls), "sum_of_test_durations_s": sum(st.durations.values()),
        "slowest": sorted(({"test": k, "median_s": v} for k, v in st.durations.items()), key=lambda x: -x["median_s"])[:10],
        "setup_heavy": sorted(
            ({"test": k, "median_setup_s": statistics.median(v), "median_total_s": st.durations[k]}
             for k, v in setups.items() if statistics.median(v) >= 0.1 and statistics.median(v) >= 0.5 * st.durations[k]),
            key=lambda x: -x["median_setup_s"])[:10],
    }
    if st.mode in RANDOM_ORDER_RUNS:
        random_outcomes = []
        rand = _random_order_project(ws)
        if rand is None:
            st.not_assessed["order dependence"] = "pytest-randomly is not installed in the target environment"
        else:
            for seed in range(1, RANDOM_ORDER_RUNS[st.mode] + 1):
                if st.budget.exhausted():
                    break
                r = run_pytest(rand, extra_args=(f"--randomly-seed={seed}",), timeout_s=st.budget.remaining())
                random_outcomes.append({k: v.outcome for k, v in r.outcomes.items()})
        # Passed every file-order run but failed at least once in random order.
        order_dependent = sorted(
            t for t in stable
            if any(o.get(t) in ("failed", "error") for o in random_outcomes)
        )
        n = len(outcomes) + len(random_outcomes)
        st.flakiness = {"runs": n, "file_order_runs": len(outcomes), "random_order_runs": len(random_outcomes),
                        "intermittent": varying, "order_dependent": order_dependent,
                        "note": f"No failure in {n} runs gives an approximate 95% upper bound of {min(1.0, 3 / n):.0%} "
                                "on a test's failure rate (independent-run approximation). Not observed is not stable."}


def _coverage(st: AuditState, ws) -> None:
    try:
        cov = coverage_matrix.measure(ws, timeout_s=st.budget.remaining(), select=sorted(st.stable) or None)
    except RuntimeError as exc:
        st.not_assessed["coverage"] = f"coverage unavailable (is pytest-cov installed?): {str(exc)[:200]}"
        return
    st.cov = cov
    lines = {t: v for t, v in cov.run_lines.items() if t in st.stable}
    mult = multiplicity(lines)
    counts = sorted(mult.values())
    eligible = _executable_lines(ws)
    covered = cov.any_covered()
    st.coverage = {
        "tests_with_coverage": len(lines), "lines_measured": len(eligible),
        "lines_covered": len(covered & eligible),
        "multiplicity_median": statistics.median(counts) if counts else None,
        "multiplicity_p90": counts[int(0.9 * (len(counts) - 1))] if counts else None,
        "hotspots": [{"file": f, "line": n, "tests": c} for (f, n), c in mult.most_common(10)],
        "uncovered_by_file": _uncovered_by_file(eligible, covered),
    }
    pairs = jaccard_pairs(lines, OVERLAP_THRESHOLD)
    pairs.sort(key=lambda p: (-p[2], -p[3]))
    st.overlap = {"threshold": OVERLAP_THRESHOLD, "pairs": len(pairs),
                  "top": [{"a": a, "b": b, "jaccard": round(j, 3), "union_lines": u} for a, b, j, u in pairs[:20]]}


def _executable_lines(ws) -> set:
    from coverage.python import PythonParser

    out = set()
    for f in ws.source_files():
        rel = str(f.relative_to(ws.root))
        try:
            # Same exclusion as coverage.py's default, so counts match pytest-cov's report.
            parser = PythonParser(filename=str(f), exclude=COVERAGE_EXCLUDE)
            parser.parse_source()
            out |= {(rel, n) for n in parser.statements}
        except Exception:
            continue
    return out


def _uncovered_by_file(eligible: set, covered: set) -> list[dict]:
    total = defaultdict(int)
    missing = defaultdict(list)
    for f, n in eligible:
        total[f] += 1
        if (f, n) not in covered:
            missing[f].append(n)
    rows = [{"file": f, "lines": total[f], "uncovered": len(ns), "uncovered_lines": _ranges(sorted(ns))}
            for f, ns in missing.items()]
    return sorted(rows, key=lambda r: -r["uncovered"])[:10]


def _ranges(ns: list[int]) -> str:
    """[1, 2, 3, 7] -> "1-3, 7"."""
    out, start, prev = [], None, None
    for n in ns + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if prev != start else f"{start}")
            start = prev = n
    return ", ".join(out)


def _mutation(st: AuditState, ws, max_mutants: int | None, progress) -> None:
    if st.cov is None:
        st.not_assessed["mutation"] = "needs per-test coverage"
        return
    if st.baseline.get("failing") or st.baseline.get("varying"):
        st.mutation["baseline_caveat"] = "failing or varying tests are excluded from mutant scope"
    covering = st.cov.tests_covering()
    muts: list[Mutant] = []
    for f in ws.source_files():
        rel = str(f.relative_to(ws.root))
        muts += classical.generate(ws.root, rel) + deletion.generate(ws.root, rel)
    rng = random.Random(SEED)
    # Deletion mutants are grouped by function so that a function's replacement set is
    # completed before moving on; the pseudo-tested label needs every replacement.
    by_fn = defaultdict(list)
    for m in muts:
        if m.population == "deletion":
            by_fn[(m.file, m.function)].append(m)
    fns = sorted(by_fn)
    rng.shuffle(fns)
    cls = [m for m in muts if m.population == "classical"]
    rng.shuffle(cls)
    # The deletion population is small and runs in full first; classical mutants are a sample
    # that fills the remaining budget. Our study found deletion is not the cheaper way to find
    # survivors (H2), but it is the direct way to find unchecked effects (H3), and complete
    # replacement sets are what the pseudo-tested label needs.
    order: list[Mutant] = [m for key in fns for m in by_fn[key]] + cls
    n_deletion = sum(len(v) for v in by_fn.values())
    if max_mutants:
        order = order[:max_mutants]

    results = _execute(st, ws, order, covering, progress)
    deletion_run = sum(1 for m, _ in results if m.population == "deletion")
    st.mutation.update({
        "eligible": {"classical": len(cls), "deletion": n_deletion},
        "run": len(results), "not_run": len(order) - len(results),
        "deletion_complete": deletion_run == n_deletion,
        "classical_sampled": sum(1 for m, _ in results if m.population == "classical"),
        "results": [{**m.record(), **r.record()} for m, r in results],
    })
    if deletion_run < n_deletion:
        st.status = "partial"
        st.mutation["note"] = (f"budget ended after {deletion_run} of {n_deletion} deletion mutants; "
                               "pseudo-tested labels cover only functions whose replacements all ran")


def _execute(st: AuditState, ws, order: list[Mutant], covering, progress) -> list[tuple[Mutant, MutantResult]]:
    """Run mutants in order until the budget ends; each runs the stable tests covering its lines."""
    def task(m: Mutant) -> Task:
        sel = sorted({t for ln in m.lines for t in covering.get((m.file, ln), ())} & st.stable)
        expected = sum(st.durations.get(t, 0) for t in sel) + st.startup_s
        return Task(m, tuple(sel), frozenset(sel), 10 * expected + 10)

    results: list[tuple[Mutant, MutantResult]] = []
    patches = st.out_dir / "mutants"
    patches.mkdir(exist_ok=True)

    def on_result(t: Task, r: MutantResult) -> None:
        results.append((t.mutant, r))
        if len(results) % 50 == 0:
            progress(f"  {len(results)} mutants run")

    with Executor(ws, st.cfg.workers) as ex:
        ex.run((task(m) for m in order), on_result, deadline=st.budget.deadline)
    for m, r in results:
        original = (ws.root / m.file).read_text()
        (patches / f"{m.id}.patch").write_text(m.patch(original))
    return results


def _verify_mutation(st: AuditState, ws, max_mutants: int | None, progress) -> None:
    """Every mutant that touches a changed line, deletion first. No sampling: a change is small."""
    ch = st.changed
    src = {str(f.relative_to(ws.root)) for f in ws.source_files()}
    changed_src = {f: ns for f, ns in ch.lines.items() if f in src}
    executable = _executable_lines(ws)
    changed_exec = {(f, n) for f, ns in changed_src.items() for n in ns if (f, n) in executable}
    covered = st.cov.any_covered() if st.cov else set()
    uncovered = sorted(changed_exec - covered)
    test_files = sorted(f for f in ch.lines if f not in src and f.endswith(".py"))
    st.change = {
        "base": ch.base, "base_commit": ch.commit,
        "source_files": {f: _ranges(sorted(ns)) for f, ns in sorted(changed_src.items())},
        "test_files": test_files, "untracked": ch.untracked,
        "changed_executable_lines": len(changed_exec), "uncovered_changed_lines": len(uncovered),
        "uncovered": [{"file": f, "lines": _ranges(sorted(n for g, n in uncovered if g == f))}
                      for f in sorted({f for f, _ in uncovered})],
    }
    if st.cov is None:
        st.not_assessed["mutation"] = "needs per-test coverage"
        return
    covering = st.cov.tests_covering()
    targeted = sorted({t for ln in changed_exec for t in covering.get(ln, ())} & st.stable)
    st.change["targeted_tests"] = len(targeted)
    st.change["targeted_test_files"] = sorted({t.split("::", 1)[0] for t in targeted})
    st.change["targeted_seconds"] = round(sum(st.durations.get(t, 0) for t in targeted), 2)
    muts: list[Mutant] = []
    for f, ns in sorted(changed_src.items()):
        if not (ws.root / f).exists():
            continue
        for m in deletion.generate(ws.root, f) + classical.generate(ws.root, f):
            if any(n in ns for n in m.lines):
                muts.append(m)
    order = sorted(muts, key=lambda m: (m.population != "deletion", m.file, m.start_line, m.operator))
    if max_mutants:
        order = order[:max_mutants]
    results = _execute(st, ws, order, covering, progress)
    st.mutation.update({
        "eligible": {"classical": sum(m.population == "classical" for m in muts),
                     "deletion": sum(m.population == "deletion" for m in muts)},
        "run": len(results), "not_run": len(muts) - len(results),
        "deletion_complete": sum(m.population == "deletion" for m, _ in results) == sum(m.population == "deletion" for m in muts),
        "classical_sampled": sum(m.population == "classical" for m, _ in results),
        "results": [{**m.record(), **r.record()} for m, r in results],
    })
    if len(results) < len(muts):
        st.status = "partial"
        st.mutation["note"] = f"budget ended after {len(results)} of {len(muts)} mutants on the changed lines"


def _prune_mutation(st: AuditState, ws, max_mutants: int | None, exclude_ids, progress) -> None:
    """Mutants on lines the removed tests run, against every covering test; a kill is lost when
    all of a mutant's killers are in the removal set."""
    pr = st.prune
    removed = set(pr["tests"])
    pr["unknown"] = sorted(removed - set(st.durations))
    pr["not_stable"] = sorted((removed & set(st.durations)) - st.stable)
    if st.cov is None:
        st.not_assessed["mutation"] = "needs per-test coverage"
        return
    lines_removed = set().union(*(st.cov.run_lines.get(t, set()) for t in removed)) if removed else set()
    others = set(st.cov.unattributed)
    for t, v in st.cov.run_lines.items():
        if t not in removed:
            others |= v
    for t, v in st.cov.setup_lines.items():
        if t not in removed:
            others |= v
    lost_lines = sorted(lines_removed - others)
    pr["lines_run_by_removed"] = len(lines_removed)
    pr["coverage_lost"] = [{"file": f, "lines": _ranges(sorted(n for g, n in lost_lines if g == f))}
                           for f in sorted({f for f, _ in lost_lines})]
    pr["coverage_lost_lines"] = len(lost_lines)
    covering = st.cov.tests_covering()
    files = sorted({f for f, _ in lines_removed})
    muts = []
    for f in files:
        if not (ws.root / f).exists():
            continue
        for m in deletion.generate(ws.root, f) + classical.generate(ws.root, f):
            if m.id not in exclude_ids and any((f, n) in lines_removed for n in m.lines):
                muts.append(m)
    rng = random.Random(pr["seed"])
    rng.shuffle(muts)
    muts.sort(key=lambda m: m.population != "deletion")
    if max_mutants:
        muts = muts[:max_mutants]
    results = _execute(st, ws, muts, covering, progress)
    lost = [(m, r) for m, r in results if r.status == model.KILLED and set(r.killers) <= removed]
    killed = sum(r.status == model.KILLED for _, r in results)
    pr.update({"mutants_eligible": len(muts), "mutants_run": len(results), "mutants_killed": killed,
               "kills_lost": [{**m.record(), "killers": r.killers} for m, r in lost]})
    st.mutation.update({"run": len(results), "not_run": len(muts) - len(results),
                        "results": [{**m.record(), **r.record()} for m, r in results]})
    if lost or lost_lines:
        pr["verdict"] = "refuted"
    elif killed == 0:
        pr["verdict"] = "not assessed"
    else:
        pr["verdict"] = "not refuted"
        pr["note"] = (f"No kill lost in {killed} killed mutants. Approximate 95% upper bound on the share of kills "
                      f"this removal loses: {min(1.0, 3 / killed):.0%}. Not refuted is not proof of safety.")
    if len(results) < len(muts):
        st.status = "partial"


def _verdict(st: AuditState) -> None:
    """verified | gaps | incomplete | no change. "verified" is relative to these mutants only."""
    ch = st.change
    if not ch.get("source_files"):
        ch["verdict"] = "no change"
        ch["reasons"] = ["no production source lines changed since " + ch.get("base", "base")]
        return
    res = st.mutation.get("results", [])
    surv = [r for r in res if r["status"] == model.SURVIVED]
    reasons = []
    if ch["uncovered_changed_lines"]:
        reasons.append(f"{plural(ch['uncovered_changed_lines'], 'changed line')} not run by any test")
    if surv:
        reasons.append(f"{len(surv)} of {plural(len(res), 'mutant')} on the changed lines survived")
    # Failing, varying and order-dependent tests are left out of mutant scope, so they can only
    # make the verdict more cautious. They are reported as a caveat, not as a gap in the change.
    b = st.baseline
    unsound = len(b.get("failing", [])) + len(b.get("varying", [])) + len((st.flakiness or {}).get("order_dependent", []))
    caveats = [f"{plural(unsound, 'test')} failed, varied or depended on order on this checkout and "
               "did not count; fix them, since they may cover the change"] if unsound else []
    incomplete = st.status != "complete" or "coverage" in st.not_assessed or st.mutation.get("not_run")
    if incomplete:
        reasons.append("not every mutant on the changed lines ran")
    valid = [r for r in res if r["status"] in (model.KILLED, model.SURVIVED)]
    if not valid and ch["changed_executable_lines"]:
        # No evidence either way, so the change cannot be called verified.
        incomplete = True
        reasons.append("no valid mutant applies to the changed lines (decorated functions, generators and "
                       "module-level code are not mutated); check them by reading the tests")
    ch["verdict"] = "gaps" if (surv or ch["uncovered_changed_lines"]) else ("incomplete" if incomplete else "verified")
    if ch["verdict"] == "verified":
        killed = sum(r["status"] == model.KILLED for r in res)
        other = len(res) - killed
        reasons.append(f"all {plural(killed, 'valid mutant')} on the changed lines were killed and every changed line is run"
                       + (f"; {other} more did not count (invalid, timed out or not activated)" if other else ""))
    ch["reasons"] = reasons + caveats
    ch["killed"] = sum(r["status"] == model.KILLED for r in res)
    ch["survived"] = len(surv)
    # Tests added or changed in this change that run changed code but catch none of its mutants.
    in_scope, kills = defaultdict(int), defaultdict(int)
    for r in res:
        if r["status"] in (model.KILLED, model.SURVIVED):
            for t in r["scope"]:
                in_scope[t] += 1
            for t in r["killers"]:
                kills[t] += 1
    ch["changed_tests_without_kills"] = sorted(
        t for t in in_scope if not kills[t] and _test_changed(st, t))


def _test_changed(st: AuditState, nodeid: str) -> bool:
    """True if any line of the test function itself changed (not just its file)."""
    import ast

    rel, _, rest = nodeid.partition("::")
    changed = st.changed.lines.get(rel) if st.changed else None
    if not changed:
        return False
    names = [n.split("[", 1)[0] for n in rest.split("::")]
    try:
        tree = ast.parse((st.cfg.project.root / rel).read_text())
    except (OSError, SyntaxError):
        return True
    body = tree.body
    node = None
    for name in names:
        node = next((n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and n.name == name), None)
        if node is None:
            return True  # cannot locate it; count it rather than hide it
        body = node.body
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return any(first <= n <= node.end_lineno for n in changed)


def _is_protected(st: AuditState, test: str) -> bool:
    return any(test.startswith(p) or p in st.markers.get(test, ()) for p in st.cfg.protected)


def _efficacy(st: AuditState) -> None:
    """Weak tests and a jointly chosen removal set, from the kill matrix and the coverage map.

    Weak: ran against at least NO_KILL_MIN_SCOPE valid, activated mutants and killed none.
    Removal set: a greedy cover keeps, for every killed mutant, one of its killers and, for every
    covered line, one test covering it; the tests left over keep all observed kills and all
    coverage when removed together. Leave-one-out redundancy does not compose (study H4), so the
    set is chosen jointly. It is fitted to this mutant sample, so it is a candidate until
    ``prune-check`` has tried it on mutants it was not chosen from.
    """
    res = st.mutation["results"]
    in_scope, kills = defaultdict(int), defaultdict(set)
    for r in res:
        if r["status"] in (model.KILLED, model.SURVIVED):
            for t in r["scope"]:
                in_scope[t] += 1
            for t in r["killers"]:
                kills[t].add(r["mutant_id"])
    weak = sorted((t for t, n in in_scope.items() if n >= NO_KILL_MIN_SCOPE and not kills[t]),
                  key=lambda t: -in_scope[t])
    lines = {t: v for t, v in st.cov.run_lines.items() if t in st.stable} if st.cov else {}
    tests = sorted(set(lines) | set(kills))
    elements = {t: {("m", m) for m in kills[t]} | {("l", ln) for ln in lines.get(t, ())} for t in tests}
    keep = set(t for t in tests if _is_protected(st, t))
    todo = set().union(*elements.values()) if elements else set()
    for t in keep:
        todo -= elements[t]
    # Greedy set cover, preferring tests that cover more per second of runtime.
    while todo:
        best = max((t for t in tests if t not in keep),
                   key=lambda t: (len(elements[t] & todo) / (st.durations.get(t, 0) + 0.01), t), default=None)
        if best is None or not elements[best] & todo:
            break
        keep.add(best)
        todo -= elements[best]
    removable = sorted(t for t in tests if t not in keep and t in st.stable)
    st.efficacy = {
        "weak_tests": [{"test": t, "mutants_run": in_scope[t]} for t in weak],
        "removal_candidates": removable,
        "removal_seconds": round(sum(st.durations.get(t, 0) for t in removable), 2),
        "suite_seconds": round(sum(st.durations.values()), 2),
        "kills_preserved": len({m for t in keep for m in kills[t]}),
        "note": "Candidates keep every kill in this mutant sample and every covered line when removed together. "
                "Not proven: check with prune-check on mutants they were not chosen from.",
    }
    if removable:
        (st.out_dir / "removal_candidates.txt").write_text("\n".join(removable) + "\n")


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


def _count(it):
    c = defaultdict(int)
    for x in it:
        c[x] += 1
    return c


# ---------------------------------------------------------------- findings

def detection_rate(results: list[dict], population: str) -> dict:
    rs = [r for r in results if r["population"] == population]
    c = _count(r["status"] for r in rs)
    k, s, u = c.get(model.KILLED, 0), c.get(model.SURVIVED, 0), c.get(model.UNCOVERED, 0)
    denom = k + s + u
    return {"population": population, "killed": k, "survived": s, "uncovered": u,
            "excluded": {x: c[x] for x in c if x not in (model.KILLED, model.SURVIVED, model.UNCOVERED)},
            "rate": (k / denom) if denom else None}


def _derive_findings(st: AuditState) -> None:
    F = st.findings
    repro = f"{CLI} replay --run {st.out_dir}"
    b = st.baseline
    if st.inventory.get("collection_error"):
        F.append(Finding("collection-error", "baseline", "Test collection fails", "measured", 100,
                         "pytest could not collect the suite; nothing else can be assessed reliably.",
                         "Fix the collection error first.", reproduce="python -m pytest --collect-only"))
    if b.get("failing"):
        F.append(Finding("baseline-failing", "baseline", f"{len(b['failing'])} tests fail on a pristine checkout",
                         "measured", 90, "These tests are excluded from mutation scope, so conclusions about the code "
                         "they cover are weaker.", "Fix or explicitly mark them; do not hide them with retries.",
                         evidence=b["failing"][:20], reproduce=f"python -m pytest {' '.join(b['failing'][:3])}"))
    if b.get("varying"):
        F.append(Finding("baseline-varying", "flakiness",
                         f"{len(b['varying'])} tests changed outcome across {b['runs']} identical runs",
                         "measured", 85, "An observed intermittent outcome; the cause is not identified.",
                         "Investigate shared state, time, randomness and ordering. Same-order reruns do not reveal "
                         "order dependence; rerun with a random-order plugin to check it.",
                         evidence=b["varying"][:20]))
    od = st.flakiness.get("order_dependent") if st.flakiness else None
    if od:
        F.append(Finding("order-dependent", "flakiness",
                         f"{len(od)} tests fail only when the test order changes", "measured", 84,
                         f"Each passed all {st.flakiness['file_order_runs']} file-order runs and failed in at least one of "
                         f"{st.flakiness['random_order_runs']} random-order runs (pytest-randomly seeds 1 to "
                         f"{st.flakiness['random_order_runs']}). Same-order reruns would not show this.",
                         "Look for state shared between tests: module-level caches, globals, warning filters, "
                         "fixtures with a wide scope.",
                         evidence=od[:20], reproduce="python -m pytest -p randomly --randomly-seed=<seed>"))
    if b.get("unstable_ids"):
        F.append(Finding("unstable-ids", "baseline", f"{len(b['unstable_ids'])} test IDs change between runs",
                         "measured", 50, "These node IDs appeared in some baseline runs and not others, typically "
                         "because a parametrize value includes the current time or a random value. Their results "
                         "cannot be compared across runs, so they are left out of mutation scope.",
                         "Give the parametrized cases fixed IDs (pytest.param(..., id=...)).",
                         evidence=b["unstable_ids"][:20]))
    res = st.mutation.get("results", [])
    if res and st.mode == "deep":
        by_fn = defaultdict(list)
        for r in res:
            if r["population"] == "deletion" and r["operator"].startswith("body:"):
                by_fn[(r["file"], r["function"])].append(r)
        pseudo = [k for k, rs in by_fn.items() if rs and all(r["status"] == model.SURVIVED for r in rs)]
        if pseudo:
            first = by_fn[pseudo[0]][0]["mutant_id"]
            F.append(Finding("pseudo-tested", "fault-detection", f"{len(pseudo)} covered functions keep passing with their body removed",
                             "measured", 80, "Every applicable replacement (None and type-appropriate constants) was run, "
                             "the replaced body executed, and no test failed. Scope: tests that cover the function. "
                             "This is a candidate gap; check the behaviour matters before adding a test.",
                             "Add an assertion on the function's result or effect, or confirm it is optional.",
                             evidence=[f"{f}::{fn}" for f, fn in pseudo[:20]], reproduce=repro + f" --mutant {first}"))
        calls = [r for r in res if r["operator"] == "call-delete" and r["status"] == model.SURVIVED]
        if calls:
            F.append(Finding("removed-calls", "fault-detection", f"{len(calls)} calls can be deleted without any test failing",
                             "measured", 70, "Each deleted call statement executed under covering tests that stayed green. "
                             "Typical causes: unasserted side effects such as logging, events, cache updates.",
                             "Review each call: assert its effect if it is required behaviour.",
                             evidence=[f"{r['file']}:{r['start_line']} {r['original'].strip()[:60]}" for r in calls[:20]],
                             reproduce=repro + f" --mutant {calls[0]['mutant_id']}"))
        surv = [r for r in res if r["population"] == "classical" and r["status"] == model.SURVIVED]
        if surv:
            per_file = _count(r["file"] for r in surv)
            F.append(Finding("classical-survivors", "fault-detection", f"{len(surv)} classical mutants survived",
                             "measured", 60, "Most-affected files: " + ", ".join(f"{f} ({n})" for f, n in sorted(per_file.items(), key=lambda x: -x[1])[:5]),
                             "Review survivors by file; equivalent mutants need human review, not model judgement.",
                             evidence=[f"{r['file']}:{r['start_line']} {r['original'].strip()[:40]!r} -> {r['replacement'].strip()[:40]!r} ({r['mutant_id']})"
                                       for r in surv[:20]], reproduce=repro + f" --mutant {surv[0]['mutant_id']}"))
        st.mutation["detection"] = [detection_rate(res, "classical"), detection_rate(res, "deletion")]
    pr = st.prune
    if pr.get("verdict"):
        if pr["verdict"] == "refuted":
            ev = [f"{k['file']}:{k['start_line']} {k['operator']} killed only by {', '.join(k['killers'][:3])}"
                  for k in pr["kills_lost"][:15]]
            ev += [f"{c['file']} lines {c['lines']} run only by removed tests" for c in pr["coverage_lost"][:5]]
            F.append(Finding("prune-refuted", "bloat", f"Removing these {len(pr['tests'])} tests loses detection",
                             "measured", 96, f"{len(pr['kills_lost'])} mutants are killed only by tests in the set, and "
                             f"{pr['coverage_lost_lines']} lines are run only by them.",
                             "Keep the tests that are the only killers; prune-check the remainder again.",
                             evidence=ev, reproduce=repro + f" --mutant {pr['kills_lost'][0]['id']}" if pr["kills_lost"] else None))
        else:
            F.append(Finding("prune-not-refuted", "bloat",
                             f"Removing these {len(pr['tests'])} tests lost no kill in {pr['mutants_killed']} mutants"
                             if pr["verdict"] == "not refuted" else "No killed mutant to check the removal against",
                             "measured" if pr["verdict"] == "not refuted" else "not assessed", 60,
                             pr.get("note", "None of the mutants on these lines was killed, so the check has no evidence."),
                             "Remove them in a separate commit, run the full suite, and keep tests that document a "
                             "requirement or a past bug.", evidence=pr["tests"][:20]))
    ch = st.change
    if ch.get("verdict") in ("gaps", "incomplete"):
        surv = [r for r in res if r["status"] == model.SURVIVED]
        if surv:
            F.append(Finding("change-survivors", "verification", f"{plural(len(surv), 'mutant')} of the changed code survived",
                             "measured", 95, "Each mutant changed or removed behaviour on a changed line, the line ran "
                             "under the covering tests, and every test still passed. The tests would not notice if "
                             "this part of the change were wrong.",
                             "Write a test that passes on the current code and fails on the mutant; confirm both with "
                             "replay. If the behaviour is optional, say so instead.",
                             evidence=[f"{r['file']}:{r['start_line']} {r['operator']}: {r['original'].strip()[:50]!r} -> "
                                       f"{r['replacement'].strip()[:40]!r} ({r['mutant_id']})" for r in surv[:20]],
                             reproduce=repro + f" --mutant {surv[0]['mutant_id']}"))
        if ch.get("uncovered"):
            F.append(Finding("change-uncovered", "verification", f"{plural(ch['uncovered_changed_lines'], 'changed line')} never run by a test",
                             "measured", 94, "; ".join(f"{u['file']} lines {u['lines']}" for u in ch["uncovered"][:5]),
                             "Add a test that exercises these lines, or remove them if they are dead code.",
                             evidence=[u["file"] for u in ch["uncovered"]]))
    if ch.get("changed_tests_without_kills"):
        F.append(Finding("change-weak-tests", "verification",
                         f"{plural(len(ch['changed_tests_without_kills']), 'new or changed test')} caught none of the change's mutants",
                         "measured", 75, "These tests run the changed code but pass on every mutant of it. They may "
                         "check something else, or assert too little to tell a correct change from a wrong one.",
                         "Strengthen their assertions or check what they are meant to verify.",
                         evidence=ch["changed_tests_without_kills"][:20]))
    ef = st.efficacy
    if ef.get("weak_tests"):
        F.append(Finding("weak-tests", "efficacy", f"{len(ef['weak_tests'])} tests catch none of the mutants they run",
                         "inferred", 55, f"Each ran against at least {NO_KILL_MIN_SCOPE} valid, activated mutants and "
                         "failed on none. They execute code without checking it, or check only what other tests "
                         "do not change. The mutants are a sample, so this is not proof the test is useless.",
                         "Read each test: add assertions on results or effects, or consider it for removal.",
                         evidence=[f"{w['test']} (0 of {w['mutants_run']})" for w in ef["weak_tests"][:20]]))
    if ef.get("removal_candidates"):
        n, sec, tot = len(ef["removal_candidates"]), ef["removal_seconds"], ef["suite_seconds"]
        F.append(Finding("removal-candidates", "bloat", f"Upper bound: {n} tests add no kill and no coverage beyond the rest of the suite",
                         "inferred", 50, f"Removed together, they keep all {ef['kills_preserved']} observed kills and every "
                         f"covered line. Their test durations add up to {sec:.1f}s of {tot:.1f}s (an estimate; only paired "
                         "wall-time runs show the real saving). The set was chosen jointly, "
                         "because removing tests that are each redundant on their own can lose kills (study H4). It is "
                         "fitted to this sample of mutants: in our study (H8) such sets lost 7.8% of kills on held-out "
                         "mutants, and every one was refuted.",
                         "Run prune-check on this set before removing anything; it tries mutants the set was not "
                         "chosen from. Keep tests that document a requirement or a past bug.",
                         evidence=ef["removal_candidates"][:20],
                         reproduce=f"{CLI} prune-check {st.cfg.project.root} --tests-file {st.out_dir}/removal_candidates.txt"))
    wall = st.timing.get("median_wall_s")
    if wall is not None and wall > LOOP_TARGET_S:
        F.append(Finding("slow-loop", "cost", f"The suite takes {wall:.0f}s, too slow to run after every change",
                         "measured", 65, f"An agent that waits {wall:.0f}s per check batches changes and loses track "
                         "of which change broke what. Target: under a minute for the loop run on every edit.",
                         "Run only the tests covering a change (verify lists them), mark slow tests, and keep the "
                         "full suite for before merging.", evidence=[f"median of {st.timing['samples']} run(s)"]))
    if st.mode == "deep" and st.inventory and not st.inventory.get("property_test_files") and res:
        F.append(Finding("no-properties", "efficacy", "No property-based tests", "measured", 20,
                         "No test file uses Hypothesis. Example tests check inputs their author chose; properties "
                         "check inputs nobody chose, which is where an agent's own assumptions go untested.",
                         "Add properties for pure functions with surviving mutants: round trips, invariants, "
                         "agreement with a simple reference implementation."))
    top = [t for t in st.timing.get("slowest", []) if t["median_s"] >= SLOW_TEST_S][:5]
    if top:
        F.append(Finding("slow-tests", "cost", "Slowest tests", "measured" if st.timing["samples"] > 1 else "unverified",
                         40, "; ".join(f"{t['test']} {t['median_s']:.2f}s" for t in top) +
                         f". Sample count: {st.timing['samples']}.",
                         "Profile these first; verify any speed-up with paired full-suite runs.",
                         evidence=[t["test"] for t in top]))
    if st.timing.get("setup_heavy"):
        F.append(Finding("setup-heavy", "cost", f"{len(st.timing['setup_heavy'])} tests spend most of their time in setup",
                         "measured", 45, "Setup time is at least half of these tests' duration.",
                         "Look for fixtures that could be shared at a wider scope without sharing mutable state.",
                         evidence=[t["test"] for t in st.timing["setup_heavy"]]))
    if st.overlap.get("pairs"):
        F.append(Finding("overlap", "redundancy", f"{st.overlap['pairs']} test pairs execute nearly the same lines",
                         "inferred", 30, f"Coverage Jaccard >= {OVERLAP_THRESHOLD}. Overlap alone does not show redundancy: "
                         "tests can cover the same lines and assert different things.",
                         "Investigate only. Compare kill sets on a frozen mutant sample before consolidating anything.",
                         evidence=[f"{p['a']} <> {p['b']}" for p in st.overlap["top"][:10]]))
    unc = st.coverage.get("uncovered_by_file")
    if unc and st.mode != "verify":
        F.append(Finding("uncovered", "coverage", "Files with most uncovered lines", "measured", 35,
                         "; ".join(f"{u['file']} lines {u['uncovered_lines']}" for u in unc[:5]),
                         "Uncovered code cannot be protected by any test; mutants there are reported as uncovered.",
                         evidence=[u["file"] for u in unc]))
    for name, why in st.not_assessed.items():
        F.append(Finding(f"not-assessed-{name}", "scope", f"{name.capitalize()} not assessed", "not assessed", 0, why, "-"))
    F.sort(key=lambda f: -f.severity)
