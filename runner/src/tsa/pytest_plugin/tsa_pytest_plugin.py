"""Pytest plugin loaded into the *target* project's interpreter with ``-p tsa_pytest_plugin``.

It has no dependencies beyond the standard library and pytest, because it runs inside the
audited project's virtual environment, not the runner's. Behaviour is driven by env vars:

- ``TSA_RESULTS``: JSONL path; one record per test phase report (nodeid, when, outcome, duration).
- ``TSA_SELECT``: file of node IDs, one per line; other collected items are deselected.
- ``TSA_COLLECT``: JSONL path; collected node IDs are written there.
- ``TSA_ACT_FILE`` / ``TSA_ACT_LINES`` / ``TSA_ACT_OUT``: activation check. Records which of the
  given lines of the given file executed, using ``sys.monitoring`` so the mutant source is not
  altered. Monitoring starts at plugin import, before conftest files import production code.
"""

import json
import os
import sys

_ACT_FILE = os.environ.get("TSA_ACT_FILE")
_ACT_OUT = os.environ.get("TSA_ACT_OUT")
_act_lines = {int(x) for x in os.environ.get("TSA_ACT_LINES", "").split(",") if x}
_act_hits: set[int] = set()
_act_available = False
_TOOL_ID = 4  # sys.monitoring tool IDs 0-5 are free for tools; coverage uses its own.

if _ACT_FILE and _act_lines:
    _act_file_real = os.path.realpath(_ACT_FILE)
    _mon = sys.monitoring

    def _on_line(code, line):
        if line in _act_lines and os.path.realpath(code.co_filename) == _act_file_real:
            _act_hits.add(line)
        return _mon.DISABLE

    try:
        _mon.use_tool_id(_TOOL_ID, "tsa-activation")
        _mon.register_callback(_TOOL_ID, _mon.events.LINE, _on_line)
        _mon.set_events(_TOOL_ID, _mon.events.LINE)
        _act_available = True
    except ValueError:
        # Tool ID already taken: activation is reported as unknown, never as "not hit".
        pass

_results_fh = None


def _results():
    global _results_fh
    path = os.environ.get("TSA_RESULTS")
    if path and _results_fh is None:
        _results_fh = open(path, "a", buffering=1)
    return _results_fh


def pytest_collection_modifyitems(session, config, items):
    select_path = os.environ.get("TSA_SELECT")
    if select_path:
        with open(select_path) as fh:
            wanted = {line.rstrip("\n") for line in fh if line.strip()}
        keep, drop = [], []
        for item in items:
            (keep if item.nodeid in wanted else drop).append(item)
        if drop:
            config.hook.pytest_deselected(items=drop)
        items[:] = keep
    collect_path = os.environ.get("TSA_COLLECT")
    if collect_path:
        with open(collect_path, "w") as fh:
            for item in items:
                markers = sorted({m.name for m in item.iter_markers()})
                fh.write(json.dumps({"nodeid": item.nodeid, "markers": markers}) + "\n")


def pytest_runtest_logreport(report):
    fh = _results()
    if fh is None:
        return
    rec = {
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "duration": report.duration,
    }
    if hasattr(report, "wasxfail"):
        rec["xfail"] = True
    if report.failed and report.longrepr is not None:
        crash = getattr(report.longrepr, "reprcrash", None)
        rec["message"] = (crash.message if crash else str(report.longrepr))[:300]
    fh.write(json.dumps(rec) + "\n")


def pytest_sessionfinish(session, exitstatus):
    if _ACT_FILE and _ACT_OUT:
        with open(_ACT_OUT, "w") as fh:
            json.dump({"hits": sorted(_act_hits) if _act_available else None}, fh)
    if _results_fh is not None:
        _results_fh.close()
