"""End-to-end known-answer cases from PRD section 8, run against fixtures/known_answers."""

import hashlib
import subprocess
from pathlib import Path

import pytest

from tsa.evidence import coverage_matrix
from tsa.mutation import classical, deletion, model
from tsa.mutation.execute import Task, execute_one
from tsa.project import Project
from tsa.pytest_run import run_pytest

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "known_answers"


def _tree_hash() -> str:
    h = hashlib.sha256()
    for f in sorted((FIXTURE / "src").rglob("*.py")) + sorted((FIXTURE / "tests").rglob("*.py")):
        h.update(str(f).encode() + f.read_bytes())
    return h.hexdigest()


BEFORE = _tree_hash()


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    venv = FIXTURE / ".venv"
    if not venv.exists():
        subprocess.run(["uv", "venv", "-q", "-p", "3.12", str(venv)], check=True)
        subprocess.run(["uv", "pip", "install", "-q", "-p", str(venv / "bin/python"), "-e", str(FIXTURE),
                        "pytest", "pytest-cov"], check=True)
    proj = Project(root=FIXTURE, python=venv / "bin/python", source=("src/known",), tests=("tests",))
    ws = proj.copy_to(tmp_path_factory.mktemp("ws") / "proj")
    return proj, ws


@pytest.fixture(scope="module")
def evidence(project):
    proj, ws = project
    base = run_pytest(proj)
    stable = frozenset(n for n, o in base.outcomes.items() if o.outcome == "passed")
    cov = coverage_matrix.measure(proj)
    muts = classical.generate(FIXTURE, "src/known/orders.py") + deletion.generate(FIXTURE, "src/known/orders.py")
    return stable, cov.tests_covering(), cov, muts


def _run(project, evidence, function, operator, select=None):
    _, ws = project
    stable, covering, _, muts = evidence
    m = next(m for m in muts if m.function == function and m.operator == operator)
    if select is None:
        select = sorted({t for ln in m.lines for t in covering.get((m.file, ln), ())} & stable)
    return execute_one(ws, Task(m, tuple(select), stable & frozenset(select), 60))


def test_pseudo_tested_function_survives_every_replacement(project, evidence):
    assert _run(project, evidence, "audit_log", "body:None").status == model.SURVIVED


def test_one_constant_survives_another_killed(project, evidence):
    assert _run(project, evidence, "discount", "body:0").status == model.SURVIVED
    assert _run(project, evidence, "discount", "body:1").status == model.KILLED


def test_removed_side_effect_survives_while_body_killed(project, evidence):
    assert _run(project, evidence, "save_order", "body:None").status == model.KILLED
    assert _run(project, evidence, "save_order", "call-delete").status == model.SURVIVED


def test_mocked_component_is_not_activated(project, evidence):
    stable = evidence[0]
    r = _run(project, evidence, "Mailer.send", "body:False", select=sorted(stable))
    assert r.status == model.NOT_ACTIVATED


def test_uncovered_mutant_has_own_status(project, evidence):
    assert _run(project, evidence, "never_called", "body:0").status == model.UNCOVERED


def test_invalid_mutant_is_not_a_kill(project, evidence):
    _, ws = project
    stable, _, _, muts = evidence
    m = next(m for m in muts if m.function == "is_adult")
    bad = model.Mutant(**{**m.__dict__, "operator": "broken", "mutated_source": "def (:\n"})
    assert execute_one(ws, Task(bad, tuple(stable), stable, 60)).status == model.INVALID


def test_overlap_without_redundancy(evidence):
    _, _, cov, _ = evidence
    a = cov.run_lines["tests/test_orders.py::test_save_returns_id"]
    b = cov.run_lines["tests/test_orders.py::test_save_returns_id_again"]
    assert len(a & b) / len(a | b) >= 0.9


def test_budget_exhaustion_gives_partial_report(project, tmp_path):
    from tsa.audit import run_audit
    from tsa.config import AuditConfig
    from tsa.report.write import write

    proj, _ = project
    st = run_audit(AuditConfig(proj), "deep", budget_minutes=0.4, max_mutants=None, out_root=tmp_path,
                   progress=lambda m: None)
    jp, mp = write(st)
    assert st.status == "partial"
    assert set(st.not_assessed) >= {"inventory", "baseline", "coverage", "mutation"}
    assert "Not assessed" in mp.read_text()


def test_quick_audit_end_to_end(project, tmp_path):
    from tsa.audit import run_audit
    from tsa.config import AuditConfig

    proj, _ = project
    st = run_audit(AuditConfig(proj), "quick", budget_minutes=3, max_mutants=None, out_root=tmp_path,
                   progress=lambda m: None)
    assert st.status == "complete"
    assert st.baseline["stable_pass"] == 6
    assert "mutation" in st.not_assessed and not st.mutation


def test_original_tree_unchanged(project, evidence):
    # Defined last so it runs after every mutant in this module has been executed.
    assert _tree_hash() == BEFORE
