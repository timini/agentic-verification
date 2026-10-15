"""Audit orchestration for ``tsa quick`` and ``tsa deep``.

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

from . import fingerprint
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
SLOW_TEST_S = 0.1  # below this a test is not worth a "slow" finding
SEED = 20261015


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


def run_audit(cfg: AuditConfig, mode: str, budget_minutes: float, max_mutants: int | None, out_root: Path,
              progress=print) -> AuditState:
    st = AuditState(mode, cfg, Budget(budget_minutes * 60), out_root)
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
    _derive_findings(st)
    return st


# ---------------------------------------------------------------- steps

def _inventory(st: AuditState, ws) -> None:
    r = run_pytest(ws, collect_only=True, timeout_s=st.budget.remaining())
    items = r.collected or []
    st.inventory = {"collected": len(items), "returncode": r.returncode,
                    "collection_error": r.collection_error,
                    "markers": dict(sorted(_count(m for c in items for m in c["markers"]).items()))}
    if r.collection_error:
        st.inventory["error"] = r.output_tail[-1500:]


def _baseline(st: AuditState, ws) -> None:
    runs = 1 if st.mode == "quick" else 3
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
    if runs > 1:
        n = len(outcomes)
        st.flakiness = {"runs": n, "intermittent": varying,
                        "note": f"No failure in {n} runs gives an approximate 95% upper bound of {min(1.0, 3 / n):.0%} "
                                "on a test's failure rate (independent-run approximation)."}


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
            parser = PythonParser(filename=str(f))
            parser.parse_source()
            out |= {(rel, n) for n in parser.statements}
        except Exception:
            continue
    return out


def _uncovered_by_file(eligible: set, covered: set) -> list[dict]:
    per = defaultdict(lambda: [0, 0])
    for f, n in eligible:
        per[f][0] += 1
        if (f, n) not in covered:
            per[f][1] += 1
    rows = [{"file": f, "lines": t, "uncovered": u} for f, (t, u) in per.items() if u]
    return sorted(rows, key=lambda r: -r["uncovered"])[:10]


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
    order: list[Mutant] = []
    ci = 0
    for key in fns:
        order += by_fn[key]
        order += cls[ci : ci + len(by_fn[key])]
        ci += len(by_fn[key])
    order += cls[ci:]
    if max_mutants:
        order = order[:max_mutants]

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
    st.mutation.update({
        "eligible": {"classical": len(cls), "deletion": sum(len(v) for v in by_fn.values())},
        "run": len(results), "not_run": len(order) - len(results),
        "results": [{**m.record(), **r.record()} for m, r in results],
    })
    if len(results) < len(order):
        st.status = "partial"
        st.mutation["note"] = "budget ended before every sampled mutant ran; unrun mutants are 'not run'"


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
    repro = f"tsa replay --run {st.out_dir}"
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
    if b.get("unstable_ids"):
        F.append(Finding("unstable-ids", "baseline", f"{len(b['unstable_ids'])} test IDs change between runs",
                         "measured", 50, "These node IDs appeared in some baseline runs and not others, typically "
                         "because a parametrize value includes the current time or a random value. Their results "
                         "cannot be compared across runs, so they are left out of mutation scope.",
                         "Give the parametrized cases fixed IDs (pytest.param(..., id=...)).",
                         evidence=b["unstable_ids"][:20]))
    res = st.mutation.get("results", [])
    if res:
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
    if unc:
        F.append(Finding("uncovered", "coverage", "Files with most uncovered lines", "measured", 35,
                         ", ".join(f"{u['file']} ({u['uncovered']}/{u['lines']})" for u in unc[:5]),
                         "Uncovered code cannot be protected by any test; mutants there are reported as uncovered.",
                         evidence=[u["file"] for u in unc]))
    for name, why in st.not_assessed.items():
        F.append(Finding(f"not-assessed-{name}", "scope", f"{name.capitalize()} not assessed", "not assessed", 0, why, "-"))
    F.sort(key=lambda f: -f.severity)
