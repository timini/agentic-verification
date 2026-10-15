from tsa.audit import detection_rate
from tsa.budget import Budget
from tsa.evidence.overlap import jaccard_pairs, multiplicity
from tsa.pytest_run import _fold


def test_jaccard_pairs_threshold_and_empty_sets():
    lines = {
        "a": {1, 2, 3, 4, 5},
        "b": {1, 2, 3, 4, 5, 6},
        "c": {10, 11, 12, 13, 14},
        "empty": set(),
    }
    pairs = jaccard_pairs(lines, threshold=0.8)
    assert [(a, b) for a, b, _, _ in pairs] == [("a", "b")]
    assert abs(pairs[0][2] - 5 / 6) < 1e-9
    assert jaccard_pairs({"a": {1}, "b": {1}}, threshold=0.5) == []  # union below minimum


def test_multiplicity_counts_distinct_tests():
    assert multiplicity({"a": {1, 2}, "b": {2}})[2] == 2


def test_detection_rate_excludes_invalid_and_reports_na():
    res = [
        {"population": "classical", "status": "killed"},
        {"population": "classical", "status": "survived"},
        {"population": "classical", "status": "uncovered"},
        {"population": "classical", "status": "invalid"},
        {"population": "classical", "status": "timeout"},
    ]
    d = detection_rate(res, "classical")
    assert d["rate"] == 1 / 3
    assert d["excluded"] == {"invalid": 1, "timeout": 1}
    assert detection_rate(res, "deletion")["rate"] is None


def test_budget_reserve():
    b = Budget(total_s=10, reserve_s=10)
    assert b.exhausted()
    assert Budget(total_s=100, reserve_s=10).remaining() > 80


def test_fold_phases():
    out = _fold([
        {"nodeid": "t1", "when": "setup", "outcome": "passed", "duration": 0.1},
        {"nodeid": "t1", "when": "call", "outcome": "failed", "duration": 0.2},
        {"nodeid": "t2", "when": "setup", "outcome": "failed", "duration": 0.1},
        {"nodeid": "t3", "when": "setup", "outcome": "passed", "duration": 0.0},
        {"nodeid": "t3", "when": "call", "outcome": "skipped", "duration": 0.0, "xfail": True},
    ])
    assert out["t1"].outcome == "failed" and abs(out["t1"].duration_s - 0.3) < 1e-9
    assert out["t2"].outcome == "error"
    assert out["t3"].outcome == "xfailed"


def test_test_files_inside_package_are_not_mutated(tmp_path):
    from tsa.project import Project

    for rel in ("pkg/__init__.py", "pkg/core.py", "pkg/tests/test_core.py", "pkg/conftest.py", "pkg/testing.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    p = Project(root=tmp_path, python=tmp_path / "python", source=("pkg",), tests=("pkg/tests",))
    assert sorted(str(f.relative_to(tmp_path)) for f in p.source_files()) == [
        "pkg/__init__.py", "pkg/core.py", "pkg/testing.py"]


def test_line_ranges():
    from tsa.audit import _ranges

    assert _ranges([1, 2, 3, 7, 9, 10]) == "1-3, 7, 9-10"
    assert _ranges([]) == ""
