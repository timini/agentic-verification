"""Known-answer cases for ``verify``, ``prune-check`` and the removal-set analysis.

``verify`` needs a git history, so each test works on a committed copy of the fixture.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from tsa.audit import AuditState, _efficacy, run_audit
from tsa.budget import Budget
from tsa.config import AuditConfig
from tsa.evidence.coverage_matrix import CoverageMatrix
from tsa.project import COPY_IGNORE, Project

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "known_answers"

NEW_CODE = '''

def tax(total: int) -> int:
    if total < 0:
        raise ValueError("negative total")
    return total * 2 // 10
'''

WEAK_TEST = '''

def test_tax_runs():
    assert orders.tax(100) >= 0
'''

STRONG_TEST = '''

def test_tax_values():
    assert orders.tax(100) == 20
    assert orders.tax(15) == 3
    assert orders.tax(0) == 0


def test_tax_rejects_negative():
    import pytest
    with pytest.raises(ValueError):
        orders.tax(-1)
'''


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    venv = FIXTURE / ".venv"
    if not venv.exists():
        pytest.skip("run test_known_answers.py first to build the fixture venv")
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE, root, ignore=COPY_IGNORE)
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    proj = Project(root=root, python=venv / "bin/python", source=("src/known",), tests=("tests",),
                   pytest_args=("-p", "no:cacheprovider", "-p", "no:randomly"))
    return AuditConfig(proj)


def _append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def _verify(cfg, tmp_path, name):
    return run_audit(cfg, "verify", 5, None, tmp_path / name, progress=lambda m: None, base="HEAD")


def test_no_change(repo, tmp_path):
    st = _verify(repo, tmp_path, "none")
    assert st.change["verdict"] == "no change"


def test_weakly_tested_change_has_gaps(repo, tmp_path):
    root = repo.project.root
    _append(root / "src/known/orders.py", NEW_CODE)
    _append(root / "tests/test_orders.py", WEAK_TEST)
    st = _verify(repo, tmp_path, "weak")
    ch = st.change
    assert ch["verdict"] == "gaps"
    assert list(ch["source_files"]) == ["src/known/orders.py"]
    assert ch["test_files"] == ["tests/test_orders.py"]
    # The raise branch never runs, and returning 0 passes ">= 0".
    assert ch["uncovered_changed_lines"] >= 1
    assert ch["survived"] >= 1
    assert {f.id for f in st.findings} >= {"change-survivors", "change-uncovered"}
    assert ch["targeted_test_files"] == ["tests/test_orders.py"]


def test_well_tested_change_is_verified(repo, tmp_path):
    root = repo.project.root
    _append(root / "src/known/orders.py", NEW_CODE)
    _append(root / "tests/test_orders.py", STRONG_TEST)
    st = _verify(repo, tmp_path, "strong")
    ch = st.change
    survivors = [r for r in st.mutation["results"] if r["status"] == "survived"]
    assert ch["uncovered_changed_lines"] == 0
    assert ch["verdict"] == ("verified" if not survivors else "gaps"), survivors
    assert ch["killed"] >= 4
    assert not ch["changed_tests_without_kills"]


def test_changed_test_that_kills_nothing(repo, tmp_path):
    root = repo.project.root
    _append(root / "src/known/orders.py", NEW_CODE)
    _append(root / "tests/test_orders.py", STRONG_TEST + "\n\ndef test_tax_smoke():\n    orders.tax(5)\n")
    st = _verify(repo, tmp_path, "smoke")
    assert "tests/test_orders.py::test_tax_smoke" in st.change["changed_tests_without_kills"]


def test_prune_check_refutes_removing_the_only_killer(repo, tmp_path):
    st = run_audit(repo, "prune-check", 5, None, tmp_path / "p1", progress=lambda m: None,
                   removed=["tests/test_orders.py::test_save_returns_id_again"])
    # Only this test asserts DB[8] == "pen", so a mutant of the DB write is killed by it alone.
    assert st.prune["verdict"] == "refuted"
    assert st.prune["kills_lost"]


def test_prune_check_refutes_lost_coverage(repo, tmp_path):
    st = run_audit(repo, "prune-check", 5, None, tmp_path / "p2", progress=lambda m: None,
                   removed=["tests/test_orders.py::test_audit_log_runs"])
    assert st.prune["verdict"] == "refuted"
    assert st.prune["coverage_lost_lines"] >= 1


def test_prune_check_does_not_refute_a_subsumed_test(repo, tmp_path):
    st = run_audit(repo, "prune-check", 5, None, tmp_path / "p3", progress=lambda m: None,
                   removed=["tests/test_orders.py::test_save_returns_id"])
    assert st.prune["verdict"] == "not refuted", st.prune


def test_removal_set_is_chosen_jointly(tmp_path):
    """Two tests each redundant with the other: only one of them may be removed (H4)."""
    proj = Project(root=tmp_path, python=Path("python3"), source=("src",))
    st = AuditState("deep", AuditConfig(proj), Budget(60), tmp_path)
    st.out_dir = tmp_path
    a, b, c, w = "t.py::a", "t.py::b", "t.py::c", "t.py::weak"
    st.stable = frozenset({a, b, c, w})
    st.durations = {a: 0.1, b: 0.2, c: 0.1, w: 0.1}
    st.cov = CoverageMatrix({a: {("m.py", 1)}, b: {("m.py", 1)}, c: {("m.py", 2)}, w: {("m.py", 2)}})
    results = [{"mutant_id": "m1", "status": "killed", "scope": [a, b], "killers": [a, b]},
               {"mutant_id": "m2", "status": "killed", "scope": [c, w], "killers": [c]}]
    results += [{"mutant_id": f"s{i}", "status": "survived", "scope": [w], "killers": []} for i in range(5)]
    st.mutation = {"results": results}
    _efficacy(st)
    removable = set(st.efficacy["removal_candidates"])
    assert len(removable & {a, b}) == 1  # the slower one, b
    assert b in removable and c not in removable
    assert w in removable
    assert [x["test"] for x in st.efficacy["weak_tests"]] == [w]


def test_change_without_mutants_is_not_verified(repo, tmp_path):
    root = repo.project.root
    _append(root / "src/known/orders.py", "\n\nimport functools\n\n\n@functools.cache\ndef rate() -> int:\n    return 3\n")
    _append(root / "tests/test_orders.py", "\n\ndef test_rate():\n    assert orders.rate() == 3\n")
    st = _verify(repo, tmp_path, "decorated")
    assert st.change["verdict"] == "incomplete"
    assert any("no valid mutant" in r for r in st.change["reasons"])
