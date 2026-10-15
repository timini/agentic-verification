"""report.json (versioned, complete evidence) and report.md (top findings first)."""

import json
from dataclasses import asdict
from pathlib import Path

from ..audit import SCHEMA_VERSION, AuditState

LABEL_TEXT = {"measured": "Measured", "inferred": "Inferred", "unverified": "Unverified", "not assessed": "Not assessed"}


def write(st: AuditState) -> tuple[Path, Path]:
    data = {
        "schema_version": SCHEMA_VERSION, "run": st.run, "inventory": st.inventory, "baseline": st.baseline,
        "timing": st.timing, "flakiness": st.flakiness or None, "coverage": st.coverage, "overlap": st.overlap,
        "mutation": st.mutation, "not_assessed": st.not_assessed, "findings": [asdict(f) for f in st.findings],
    }
    jp = st.out_dir / "report.json"
    jp.write_text(json.dumps(data, indent=2, default=str))
    mp = st.out_dir / "report.md"
    mp.write_text(markdown(st))
    return jp, mp


def markdown(st: AuditState) -> str:
    r = st.run
    out = [f"# Test suite audit ({r['mode']})", "",
           f"Run `{r['id']}`, status **{r['status']}**. Commit `{(r['fingerprint'].get('commit') or 'none')[:12]}`"
           + (" with uncommitted changes" if r["fingerprint"].get("dirty") else "") + f". Budget: {r['budget']}.", ""]
    actionable = [f for f in st.findings if f.label != "not assessed"]
    out += ["## Top findings", ""]
    if not actionable:
        out.append("No findings. Check the sections below for what was and was not assessed.")
    for i, f in enumerate(actionable[:5], 1):
        out += [f"### {i}. {f.title}", "", f"*{LABEL_TEXT[f.label]}* · {f.category}", "", f.detail, "",
                f"Next step: {f.action}"]
        if f.evidence:
            out += ["", "Evidence:", *[f"- `{e}`" for e in f.evidence[:8]]]
            if len(f.evidence) > 8:
                out.append(f"- ... {len(f.evidence) - 8} more in report.json")
        if f.reproduce:
            out += ["", f"Reproduce: `{f.reproduce}`"]
        out.append("")
    if len(actionable) > 5:
        out += ["## Other findings", "", *[f"- {f.title} (*{LABEL_TEXT[f.label]}*)" for f in actionable[5:]], ""]

    b, t = st.baseline, st.timing
    if b:
        out += ["## Baseline", "",
                f"{b['tests']} tests over {b['runs']} run(s): {b['stable_pass']} passed every time, "
                f"{len(b['failing'])} failed, {len(b['varying'])} varied, {len(b['skipped'])} skipped or xfailed.", ""]
    if t.get("median_wall_s") is not None:
        out += [f"Median wall time {t['median_wall_s']:.1f}s from {t['samples']} run(s). The sum of individual test "
                f"durations ({t['sum_of_test_durations_s']:.1f}s) is not wall time and is shown only for comparison.", ""]
    if st.flakiness:
        out += ["## Flakiness", "", f"{len(st.flakiness['intermittent'])} tests varied in {st.flakiness['runs']} runs. "
                + st.flakiness["note"], ""]
    c = st.coverage
    if c:
        out += ["## Coverage and overlap", "",
                f"{c['lines_covered']} of {c['lines_measured']} executable source lines covered. "
                f"Median tests per covered line: {c['multiplicity_median']}; 90th percentile: {c['multiplicity_p90']}.",
                f"{st.overlap.get('pairs', 0)} test pairs have coverage Jaccard >= {st.overlap.get('threshold')}. "
                "Overlap is a reason to look, not evidence of redundancy.", ""]
    det = st.mutation.get("detection")
    if det:
        out += ["## Mutation", "", "Observed detection rate is K/(K+S+U): killed over killed, survived and uncovered. "
                "Invalid, timed-out, infrastructure-failure, not-activated and unknown-activation mutants are excluded "
                "and counted separately. The rate applies to this sample only.", "",
                "| Population | Killed | Survived | Uncovered | Rate | Excluded |", "|---|---|---|---|---|---|"]
        for d in det:
            rate = "n/a" if d["rate"] is None else f"{100 * d['rate']:.1f}%"
            excl = ", ".join(f"{k} {v}" for k, v in d["excluded"].items()) or "none"
            out.append(f"| {d['population']} | {d['killed']} | {d['survived']} | {d['uncovered']} | {rate} | {excl} |")
        out += ["", f"{st.mutation['run']} mutants run, {st.mutation['not_run']} sampled but not run. "
                "Patches are in `mutants/`.", ""]
    if st.not_assessed:
        out += ["## Not assessed", "", *[f"- {k}: {v}" for k, v in st.not_assessed.items()], ""]
    out += ["## Labels", "", "*Measured*: observed in this run. *Inferred*: derived from measurements, needs review. "
            "*Unverified*: single sample or incomplete evidence. *Not assessed*: no evidence collected.", ""]
    return "\n".join(out)
