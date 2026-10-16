"""report.json (versioned, complete evidence) and report.md (top findings first)."""

import json
from dataclasses import asdict
from pathlib import Path

from ..audit import SCHEMA_VERSION, AuditState, plural

TITLES = {"quick": "Test suite audit (quick)", "deep": "Test suite audit (deep)",
          "verify": "Change verification", "prune-check": "Removal check"}
LABEL_TEXT = {"measured": "Measured", "inferred": "Inferred", "unverified": "Unverified", "not assessed": "Not assessed"}


def write(st: AuditState) -> tuple[Path, Path]:
    data = {
        "schema_version": SCHEMA_VERSION, "run": st.run, "inventory": st.inventory, "baseline": st.baseline,
        "timing": st.timing, "flakiness": st.flakiness or None, "coverage": st.coverage, "overlap": st.overlap,
        "mutation": st.mutation, "change": st.change or None, "efficacy": st.efficacy or None,
        "prune": st.prune or None, "not_assessed": st.not_assessed, "findings": [asdict(f) for f in st.findings],
    }
    jp = st.out_dir / "report.json"
    jp.write_text(json.dumps(data, indent=2, default=str))
    mp = st.out_dir / "report.md"
    mp.write_text(markdown(st))
    return jp, mp


def markdown(st: AuditState) -> str:
    r = st.run
    out = [f"# {TITLES[r['mode']]}", "",
           f"Run `{r['id']}`, status **{r['status']}**. Commit `{(r['fingerprint'].get('commit') or 'none')[:12]}`"
           + (" with uncommitted changes" if r["fingerprint"].get("dirty") else "") + f". Budget: {r['budget']}.", ""]
    ch, pr = st.change, st.prune
    if ch.get("verdict"):
        out += [f"## Verdict: {ch['verdict']}", "",
                f"Change since `{ch['base']}` (`{(ch.get('base_commit') or '')[:12]}`): "
                f"{plural(ch['changed_executable_lines'], 'changed executable line')} in {plural(len(ch['source_files']), 'source file')}"
                + (f", {ch.get('killed', 0)} of {st.mutation.get('run', 0)} mutants killed" if st.mutation.get("run") else "")
                + ".", "", *[f"- {x}" for x in ch.get("reasons", [])], ""]
        if ch.get("targeted_tests"):
            files = " ".join(ch["targeted_test_files"][:12])
            out += [f"Fast check: {plural(ch['targeted_tests'], 'test')} {'covers' if ch['targeted_tests'] == 1 else 'cover'} the changed lines, about "
                    f"{ch['targeted_seconds']:.1f}s in total: `python -m pytest {files}`", ""]
    if pr.get("verdict"):
        out += [f"## Verdict: {pr['verdict']}", "",
                f"{len(pr['tests'])} tests proposed for removal. They run {pr.get('lines_run_by_removed', 0)} lines; "
                f"{pr.get('mutants_run', 0)} mutants on those lines ran against the whole suite"
                + (f", none of them from the audit that proposed the set ({pr['excluded_mutants']} excluded)"
                   if pr["excluded_mutants"] else "") + ".", ""]
        if pr.get("note"):
            out += [pr["note"], ""]
        if pr.get("unknown"):
            out += [f"{len(pr['unknown'])} listed tests were not found in the suite: "
                    + ", ".join(f"`{t}`" for t in pr["unknown"][:5]), ""]
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
        fl = st.flakiness
        out += ["## Flakiness", "",
                f"{fl['file_order_runs']} file-order and {fl['random_order_runs']} random-order runs. "
                f"{len(fl['intermittent'])} tests varied between file-order runs; "
                f"{len(fl['order_dependent'])} passed every file-order run but failed in random order. " + fl["note"], ""]
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
        m = st.mutation
        done = "all" if m["deletion_complete"] else "not all"
        out += ["", f"Deletion mutants run first and in full ({done} {m['eligible']['deletion']} ran); classical mutants "
                f"are a seeded sample filling the rest of the budget ({m['classical_sampled']} of "
                f"{m['eligible']['classical']}). Patches are in `mutants/`.", ""]
    ef = st.efficacy
    if ef:
        out += ["## Efficacy and bloat", "",
                f"{len(ef['weak_tests'])} tests ran against valid mutants and caught none. "
                f"{len(ef['removal_candidates'])} tests could be removed together without losing any of the "
                f"{ef['kills_preserved']} observed kills or any covered line ({ef['removal_seconds']:.1f}s of "
                f"{ef['suite_seconds']:.1f}s). {ef['note']}", ""]
    if st.not_assessed:
        out += ["## Not assessed", "", *[f"- {k}: {v}" for k, v in st.not_assessed.items()], ""]
    out += ["## Labels", "", "*Measured*: observed in this run. *Inferred*: derived from measurements, needs review. "
            "*Unverified*: single sample or incomplete evidence. *Not assessed*: no evidence collected.", ""]
    return "\n".join(out)
