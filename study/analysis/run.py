"""Regenerate every derived table, figure and number in the paper from data/raw.

Outputs: data/derived/*.csv, paper/generated/macros.tex, paper/generated/*.tex tables and
paper/figures/*.pdf. Nothing here is edited by hand.
"""

import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import spearmanr

from harness import corpus
from harness.records import read_all
from tsa.project import is_test_path

from .stats import cluster_bootstrap, ratio, wilson

STUDY = Path(__file__).resolve().parent.parent
DERIVED = STUDY / "data" / "derived"
GEN = STUDY / "paper" / "generated"
FIG = STUDY / "paper" / "figures"
VALID = ("killed", "survived")
PROJECTS = [e.name for e in corpus.load()]

macros: dict[str, str] = {}


def macro(name: str, value) -> None:
    if isinstance(value, float):
        value = "n/a" if math.isnan(value) else f"{value:.2f}"
    macros[name] = str(value)


def pct(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}\\%"


def latest(experiment: str, project: str) -> list[dict]:
    """Records from the most recent complete run of an experiment for one project."""
    recs = read_all(experiment, project)
    ended = [r["run_id"] for r in recs if r["kind"] == "run_end"]
    if not ended:
        return []
    rid = ended[-1]
    # Deviation 6: toolz keeps its tests inside the source package, and the first runs mutated them.
    # Those mutants are dropped here; every affected run was exhaustive, so this equals excluding them.
    return [r for r in recs if r["run_id"] == rid
            and not (r["kind"] == "mutant_result" and is_test_path(r["mutant"]["file"]))]


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return f"{v:,}"
    text = str(v)
    for a, b in (("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("#", "\\#"), ("_", "\\_")):
        text = text.replace(a, b)
    return text


def table(name: str, df: pd.DataFrame, caption: str, label: str) -> None:
    df.to_csv(DERIVED / f"{name}.csv", index=False)
    cols = list(df.columns)
    lines = ["\\begin{table}[t]", "\\centering\\small",
             *(["\\resizebox{\\linewidth}{!}{%"] if len(cols) > 8 else []),
             "\\begin{tabular}{l" + "r" * (len(cols) - 1) + "}", "\\toprule",
             " & ".join(_cell(c) for c in cols) + " \\\\", "\\midrule"]
    for row in df.itertuples(index=False):
        vals = [None if (isinstance(v, float) and math.isnan(v)) else (v.item() if hasattr(v, "item") else v) for v in row]
        lines.append(" & ".join(_cell(v) for v in vals) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}" + ("}" if len(cols) > 8 else ""), f"\\caption{{{caption}}}", f"\\label{{{label}}}", "\\end{table}", ""]
    (GEN / f"{name}.tex").write_text("\n".join(lines))


# ---------------------------------------------------------------- corpus and baseline

def corpus_table() -> None:
    rows = []
    failing = varying = 0
    for e in corpus.load():
        b = [r for r in read_all("e0_baseline", e.name) if r["kind"] == "baseline_summary"][-1]
        failing += len(b["failing"])
        varying += len(b["varying"])
        runs = [r for r in read_all("e0_baseline", e.name) if r["kind"] == "baseline_run" and r["run_id"] == b["run_id"]]
        muts = [r for r in latest("e3_effects", e.name) if r["kind"] == "populations"]
        e2 = latest("e2_budget", e.name)
        pop = {r["strategy"]: r["population"] for r in e2 if r["kind"] == "strategy_start"}
        for r in e2:
            if r["kind"] == "strategy_end" and r["exhausted"]:
                # Exhaustive runs: count the (test-file filtered) results instead of the recorded size.
                pop[r["strategy"]] = sum(1 for x in e2 if x["kind"] == "mutant_result" and x["label"] == r["strategy"])
        rows.append({
            "Project": e.name, "Version": e.tag,
            "Tests": len(b["stable_pass"]) + len(b["varying"]) + len(b["failing"]) + len(b["skipped"]),
            "In scope": len(b["stable_pass"]),
            "Suite (s)": statistics.median(r["wall_s"] for r in runs),
            "Classical": pop.get("classical"), "Deletion": pop.get("deletion"),
        })
    df = pd.DataFrame(rows)
    table("corpus", df, "Corpus at the pinned release commits. \\emph{In scope}: tests that passed in all three baseline runs. "
          "Mutant columns give the size of each eligible population.", "tab:corpus")
    macro("NProjects", len(df))
    macro("NBaselineFailing", failing)
    macro("NBaselineVarying", varying)
    macro("NTestsInScope", f"{int(df['In scope'].sum()):,}")
    macro("NClassical", f"{int(df['Classical'].fillna(0).sum()):,}")
    macro("NDeletion", f"{int(df['Deletion'].fillna(0).sum()):,}")


# ---------------------------------------------------------------- H1

def h1() -> None:
    pair_rows = []
    for p in PROJECTS:
        recs = latest("e1_overlap", p)
        pairs = {r["pair_id"]: r for r in recs if r["kind"] == "pair"}
        results = defaultdict(list)
        for r in recs:
            if r["kind"] == "mutant_result":
                results[r["label"]].append(r["result"])
        for pid, pr in pairs.items():
            valid = [x for x in results[pid] if x["status"] in VALID]
            ka = {x["mutant_id"] for x in valid if pr["a"] in x["killers"]}
            kb = {x["mutant_id"] for x in valid if pr["b"] in x["killers"]}
            union = ka | kb
            pair_rows.append({
                "project": p, "stratum": pr["stratum"], "jaccard": pr["jaccard"],
                "same_function": pr["same_function"], "mutants_valid": len(valid),
                "kills_union": len(union), "only_a": len(ka - kb), "only_b": len(kb - ka),
                "kill_jaccard": len(ka & kb) / len(union) if union else math.nan,
                "non_dominated": bool(ka - kb) and bool(kb - ka),
                "one_way": bool(ka - kb) != bool(kb - ka),
            })
    df = pd.DataFrame(pair_rows)
    df.to_csv(DERIVED / "h1_pairs.csv", index=False)
    if df.empty:
        return
    high = df[(df.stratum == "high") & (df.mutants_valid > 0)]

    def share(rows):
        rows = [r for c in rows for r in c]
        return sum(r["non_dominated"] for r in rows) / len(rows) if rows else math.nan

    clusters = [high[high.project == p].to_dict("records") for p in PROJECTS if (high.project == p).any()]
    pooled = share(clusters)
    lo, hi = cluster_bootstrap(clusters, share)
    macro("HOneShare", pct(pooled))
    macro("HOneLo", pct(lo))
    macro("HOneHi", pct(hi))
    macro("HOnePairs", len(high))
    macro("HOneSupported", "supported" if lo > 0.10 else "not supported")
    macro("HOneOneWay", pct(high.one_way.mean()))
    macro("HOneAnyDiff", pct((high.non_dominated | high.one_way).mean()))
    sub = high[~high.same_function]
    macro("HOneDistinctFnShare", pct(sub.non_dominated.mean()) if len(sub) else "n/a")
    macro("HOneDistinctFnN", len(sub))
    sub2 = high[high.same_function]
    macro("HOneSameFnShare", pct(sub2.non_dominated.mean()) if len(sub2) else "n/a")
    macro("HOneSameFnN", len(sub2))
    both = df[df.kills_union > 0]
    rho = spearmanr(both.jaccard, both.kill_jaccard).statistic if len(both) > 2 else math.nan
    macro("HOneRho", rho)
    macro("HOneRhoN", len(both))
    shares = high.groupby("project").non_dominated.mean()
    macro("HOneMinShare", pct(shares.min()))
    macro("HOneMinProject", shares.idxmin())
    macro("HOneMaxShare", pct(shares.max()))
    macro("HOneMaxProject", shares.idxmax())
    rows = []
    for p in PROJECTS:
        h = high[high.project == p]
        if not len(h):
            rows.append({"Project": p, "Pairs": 0, "Non-dominated": None, "95% CI": "--", "One-way": None, "Identical": None})
            continue
        k = int(h.non_dominated.sum())
        a, b = wilson(k, len(h))
        rows.append({"Project": p, "Pairs": len(h), "Non-dominated": f"{k} ({100*k/len(h):.0f}%)",
                     "95% CI": f"{100*a:.0f}--{100*b:.0f}%", "One-way": int(h.one_way.sum()),
                     "Identical": int((~h.non_dominated & ~h.one_way).sum())})
    table("h1", pd.DataFrame(rows),
          "H1: test pairs with coverage Jaccard $\\geq 0.9$. \\emph{Non-dominated}: each test kills a mutant the other misses. "
          "\\emph{One-way}: one kill set strictly contains the other. \\emph{Identical}: equal kill sets (including both empty). "
          "Per-project intervals are Wilson 95\\%.", "tab:h1")
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for stratum, marker in (("high", "o"), ("comparison", "x")):
        s = both[both.stratum == stratum]
        ax.scatter(s.jaccard, s.kill_jaccard, s=10, marker=marker, alpha=0.6, label=f"{stratum} ({len(s)})")
    ax.set_xlabel("Coverage Jaccard")
    ax.set_ylabel("Kill-set Jaccard")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "h1_scatter.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- H2

def h2() -> None:
    rows = []
    status_rows = []
    for p in PROJECTS:
        recs = latest("e2_budget", p)
        ends = {r["strategy"]: r for r in recs if r["kind"] == "strategy_end"}
        for strategy in ("classical", "deletion"):
            res = [r["result"] for r in recs if r["kind"] == "mutant_result" and r["label"] == strategy]
            if not res:
                continue
            c = Counter(x["status"] for x in res)
            cpu = sum(x["cpu_s"] for x in res)
            rows.append({"project": p, "strategy": strategy, "completed": len(res), "survivors": c["survived"],
                         "killed": c["killed"], "cpu_min": cpu / 60, "wall_s": ends.get(strategy, {}).get("elapsed_s"),
                         "exhausted": ends.get(strategy, {}).get("exhausted")})
            status_rows.append({"project": p, "strategy": strategy, **c})
    df = pd.DataFrame(rows)
    df.to_csv(DERIVED / "h2_strategies.csv", index=False)
    pd.DataFrame(status_rows).fillna(0).to_csv(DERIVED / "h2_statuses.csv", index=False)
    macro("HTwoAbstract", "The cost comparison of deletion and classical mutants (H2) is still running.")
    if df.empty or set(df.strategy) != {"classical", "deletion"} or df.project.nunique() < len(PROJECTS):
        return
    w = df.pivot(index="project", columns="strategy")
    per = []
    for p in w.index:
        rc = ratio(w.loc[p, ("survivors", "classical")], w.loc[p, ("cpu_min", "classical")])
        rd = ratio(w.loc[p, ("survivors", "deletion")], w.loc[p, ("cpu_min", "deletion")])
        per.append({"Project": p,
                    "Classical surv.": int(w.loc[p, ("survivors", "classical")]),
                    "Classical CPU min": w.loc[p, ("cpu_min", "classical")],
                    "Deletion surv.": int(w.loc[p, ("survivors", "deletion")]),
                    "Deletion CPU min": w.loc[p, ("cpu_min", "deletion")],
                    "Ratio": ratio(rd, rc),
                    "Deletion exhausted": "yes" if w.loc[p, ("exhausted", "deletion")] else "no"})
    per_df = pd.DataFrame(per)
    table("h2", per_df, "H2: activated, valid survivors and CPU minutes under equal 20-minute wall-clock budgets. "
          "\\emph{Ratio}: deletion survivors per CPU-minute divided by classical survivors per CPU-minute. "
          "\\emph{Deletion exhausted}: every eligible deletion mutant ran within the budget.", "tab:h2")
    clusters = [r for r in per]

    def pooled(rows):
        sd = sum(r["Deletion surv."] for r in rows)
        cd = sum(r["Deletion CPU min"] for r in rows)
        sc = sum(r["Classical surv."] for r in rows)
        cc = sum(r["Classical CPU min"] for r in rows)
        return ratio(ratio(sd, cd), ratio(sc, cc))

    est = pooled(clusters)
    lo, hi = cluster_bootstrap(clusters, pooled)
    above = sum(1 for r in per if r["Ratio"] > 1)
    macro("HTwoRatio", est)
    macro("HTwoLo", lo)
    macro("HTwoHi", hi)
    macro("HTwoAbove", above)
    macro("HTwoN", len(per))
    macro("HTwoExhausted", sum(1 for r in per if r["Deletion exhausted"] == "yes"))
    macro("HTwoSupported", "supported" if (above > len(per) / 2 and lo > 1) else "not supported")
    macro("HTwoAbstract", f"Under equal budgets, deletion mutants yielded {est:.2f} times as many activated survivors "
          f"per CPU-minute as mutmut's classical operators (95\\% CI {lo:.2f}--{hi:.2f}).")
    tot = df.groupby("strategy")[["survivors", "killed", "completed", "cpu_min"]].sum()
    for s, key in (("classical", "Cls"), ("deletion", "Del")):
        if s in tot.index:
            macro(f"HTwo{key}Surv", int(tot.loc[s, "survivors"]))
            macro(f"HTwo{key}Done", f"{int(tot.loc[s, 'completed']):,}")
            macro(f"HTwo{key}Rate", tot.loc[s, "survivors"] / tot.loc[s, "cpu_min"])
            macro(f"HTwo{key}SurvShare", pct(tot.loc[s, "survivors"] / tot.loc[s, "completed"]))
            macro(f"HTwo{key}CpuPerMutant", 60 * tot.loc[s, "cpu_min"] / tot.loc[s, "completed"])
            macro(f"HTwo{key}CpuMin", f"{tot.loc[s, 'cpu_min']:,.0f}")
    for strategy, key in (("classical", "Cls"), ("deletion", "Del")):
        res = [r["result"] for p in PROJECTS for r in latest("e2_budget", p)
               if r["kind"] == "mutant_result" and r["label"] == strategy]
        ran = [x for x in res if x["status"] != "uncovered"]
        kills = [x for x in res if x["status"] == "killed"]
        if ran:
            macro(f"HTwo{key}CpuMedian", statistics.median(x["cpu_s"] for x in ran))
            macro(f"HTwo{key}ScopeMedian", int(statistics.median(len(x["scope"]) for x in ran)))
            macro(f"HTwo{key}TimeoutShare", pct(sum(x["status"] == "timeout" for x in res) / len(res)))
        if kills:
            macro(f"HTwo{key}KillersMedian", int(statistics.median(len(x["killers"]) for x in kills)))
    review_sheet(df)


def review_sheet(_df: pd.DataFrame) -> None:
    """Stratified sample of 50 survivors (25 per strategy) for the blind human review."""
    import random

    rng = random.Random("20261015-h2-review")
    pools = {"classical": [], "deletion": []}
    for p in PROJECTS:
        for r in latest("e2_budget", p):
            if r["kind"] == "mutant_result" and r["result"]["status"] == "survived":
                pools[r["label"]].append(r)
    picked = []
    for strategy, pool in pools.items():
        by_proj = defaultdict(list)
        for r in pool:
            by_proj[r["project"]].append(r)
        order = sorted(by_proj)
        i = 0
        while len([x for x in picked if x["label"] == strategy]) < 25 and any(by_proj.values()):
            proj = order[i % len(order)]
            if by_proj[proj]:
                picked.append(by_proj[proj].pop(rng.randrange(len(by_proj[proj]))))
            i += 1
    rng.shuffle(picked)
    review = STUDY / "data" / "review"
    review.mkdir(parents=True, exist_ok=True)
    key_rows, sheet_rows = [], []
    for n, r in enumerate(picked, 1):
        key_rows.append({"item": n, "strategy": r["label"], "mutant_id": r["mutant"]["id"]})
        sheet_rows.append({"item": n, "project": r["project"], "file": r["mutant"]["file"],
                           "line": r["mutant"]["start_line"], "function": r["mutant"]["function"],
                           "patch": r["patch"], "label": "", "notes": ""})
    pd.DataFrame(key_rows).to_csv(review / "h2_review_key.csv", index=False)
    sheet = review / "h2_review_sheet.csv"
    if not sheet.exists():  # never overwrite a sheet that may already hold labels
        pd.DataFrame(sheet_rows).to_csv(sheet, index=False)
    labelled = pd.read_csv(sheet).fillna("")
    key = pd.read_csv(review / "h2_review_key.csv")
    done = labelled[labelled.label != ""].merge(key, on="item")
    macro("HTwoReviewed", len(done))
    for s, k in (("classical", "Cls"), ("deletion", "Del")):
        d = done[done.strategy == s]
        macro(f"HTwo{k}RealGap", pct((d.label == "real gap").mean()) if len(d) else "n/a")


# ---------------------------------------------------------------- H3

def h3() -> None:
    rows = []
    fn_rows = []
    for p in PROJECTS:
        recs = latest("e3_effects", p)
        body = defaultdict(list)
        calls = []
        for r in recs:
            if r["kind"] != "mutant_result":
                continue
            key = (r["mutant"]["file"], r["mutant"]["function"])
            if r["label"] == "body":
                body[key].append(r["result"]["status"])
            else:
                calls.append((key, r["result"]["status"]))
        status = {}
        for key, sts in body.items():
            if all(s == "killed" for s in sts):
                status[key] = "fully killed"
            elif any(s == "survived" for s in sts):
                status[key] = "some survived"
            else:
                status[key] = "not assessed"
        for key, s in status.items():
            fn_rows.append({"project": p, "file": key[0], "function": key[1], "status": s,
                            "call_survivors": sum(1 for k, st in calls if k == key and st == "survived"),
                            "calls_valid": sum(1 for k, st in calls if k == key and st in VALID)})
        for key, st in calls:
            rows.append({"project": p, "file": key[0], "function": key[1], "status": st,
                         "parent": status.get(key, "no body mutant")})
    df = pd.DataFrame(rows)
    fdf = pd.DataFrame(fn_rows)
    df.to_csv(DERIVED / "h3_calls.csv", index=False)
    fdf.to_csv(DERIVED / "h3_functions.csv", index=False)
    if df.empty:
        return
    surv = df[df.status == "survived"]

    def share(cl):
        rows = [r for c in cl for r in c]
        return sum(r["parent"] == "fully killed" for r in rows) / len(rows) if rows else math.nan

    clusters = [surv[surv.project == p].to_dict("records") for p in PROJECTS if (surv.project == p).any()]
    est = share(clusters)
    lo, hi = cluster_bootstrap(clusters, share)
    macro("HThreeShare", pct(est))
    macro("HThreeLo", pct(lo))
    macro("HThreeHi", pct(hi))
    macro("HThreeSurvivors", len(surv))
    macro("HThreeCalls", len(df))
    macro("HThreeSupported", "supported" if lo > 0.10 else "not supported")
    fk = fdf[(fdf.status == "fully killed") & (fdf.calls_valid > 0)]
    macro("HThreeFKFns", len(fk))
    macro("HThreeFKWithSurv", pct((fk.call_survivors > 0).mean()) if len(fk) else "n/a")
    macro("HThreeFnsFullyKilled", int((fdf.status == "fully killed").sum()))
    macro("HThreeFns", len(fdf))
    rows = []
    for p in PROJECTS:
        d = df[df.project == p]
        s = d[d.status == "survived"]
        rows.append({"Project": p, "Call deletions": len(d), "Valid": int(d.status.isin(VALID).sum()),
                     "Survived": len(s), "In fully killed fn": int((s.parent == "fully killed").sum()),
                     "Share": (s.parent == "fully killed").mean() if len(s) else None})
    table("h3", pd.DataFrame(rows), "H3: sampled call-statement deletions. \\emph{In fully killed fn}: survivors whose "
          "enclosing function had every body replacement killed.", "tab:h3")


# ---------------------------------------------------------------- H4

def greedy_cover(kills: dict[str, set]) -> int:
    need = set().union(*kills.values()) if kills else set()
    chosen = 0
    while need:
        t = max(kills, key=lambda t: len(kills[t] & need))
        need -= kills[t]
        chosen += 1
    return chosen


def h4() -> None:
    rows = []
    for p in PROJECTS:
        recs = latest("e4_group", p)
        units = {r["file"]: r for r in recs if r["kind"] == "unit"}
        for f, u in units.items():
            res = [r["result"] for r in recs if r["kind"] == "mutant_result" and r["label"] == f]
            valid = [x for x in res if x["status"] in VALID]
            kills = {t: set() for t in u["tests"]}
            for x in valid:
                for t in x["killers"]:
                    kills.setdefault(t, set()).add(x["mutant_id"])
            killers_of = defaultdict(set)
            for t, ms in kills.items():
                for m in ms:
                    killers_of[m].add(t)
            loo = {t for t, ms in kills.items() if all(len(killers_of[m]) > 1 for m in ms)}
            lost = {m for m, ks in killers_of.items() if ks <= loo}
            rows.append({"project": p, "file": f, "tests": len(u["tests"]), "mutants_valid": len(valid),
                         "killed": len(killers_of), "loo_redundant": len(loo), "group_lost": len(lost),
                         "greedy_cover": greedy_cover({t: m for t, m in kills.items() if m}),
                         "zero_kill_tests": sum(1 for ms in kills.values() if not ms)})
    df = pd.DataFrame(rows)
    df.to_csv(DERIVED / "h4_units.csv", index=False)
    if df.empty:
        return
    elig = df[df.loo_redundant >= 2]
    k = int((elig.group_lost > 0).sum())
    lo, hi = wilson(k, len(elig))
    macro("HFourUnits", len(df))
    macro("HFourEligible", len(elig))
    macro("HFourLosing", k)
    macro("HFourShare", pct(k / len(elig)) if len(elig) else "n/a")
    macro("HFourLo", pct(lo))
    macro("HFourHi", pct(hi))
    macro("HFourSupported", "supported" if lo > 0.20 else "not supported")
    macro("HFourLostTotal", int(elig.group_lost.sum()))
    macro("HFourKilledTotal", int(elig.killed.sum()))
    share_kept = df.greedy_cover / df.tests
    macro("HFourCoverMedian", pct(share_kept.median()))
    macro("HFourCoverMin", pct(share_kept.min()))
    macro("HFourCoverMax", pct(share_kept.max()))
    out = df.rename(columns={"project": "Project", "file": "Test file", "tests": "Tests", "killed": "Killed",
                             "loo_redundant": "LOO-redundant", "group_lost": "Lost by group",
                             "greedy_cover": "Greedy cover", "zero_kill_tests": "No kills"})
    out = out.drop(columns=["mutants_valid"])
    out["Test file"] = out["Test file"].str.replace("tests/", "", regex=False)
    table("h4", out, "H4: kill matrices for sampled test files. \\emph{LOO-redundant}: tests whose removal alone "
          "loses no kill. \\emph{Lost by group}: kills lost when all of them are removed together. "
          "\\emph{Greedy cover}: tests a greedy set cover keeps.", "tab:h4")


# ---------------------------------------------------------------- H5

def h5() -> None:
    rows = []
    for p in PROJECTS:
        for r in latest("e5_overhead", p):
            if r["kind"] == "timing":
                rows.append({"project": p, "block": r["block"], "condition": r["condition"], "wall_s": r["wall_s"],
                             "returncode": r["returncode"]})
    df = pd.DataFrame(rows)
    df.to_csv(DERIVED / "h5_timings.csv", index=False)
    if df.empty:
        return
    w = df.pivot_table(index=["project", "block"], columns="condition", values="wall_s").reset_index()
    w["ctx_none"] = w.contexts / w.none
    w["ctx_cov"] = w.contexts / w.coverage
    w["cov_none"] = w.coverage / w.none
    per = w.groupby("project")[["none", "coverage", "contexts", "cov_none", "ctx_none", "ctx_cov"]].median().reset_index()
    clusters = [w[w.project == p]["ctx_none"].tolist() for p in per.project]

    def pooled(cl):
        meds = [statistics.median(c) for c in cl]
        return math.exp(sum(math.log(m) for m in meds) / len(meds))

    est = pooled(clusters)
    lo, hi = cluster_bootstrap(clusters, pooled)
    macro("HFiveRatio", est)
    macro("HFiveLo", lo)
    macro("HFiveHi", hi)
    macro("HFiveSupported", "supported" if lo > 1.2 else "not supported")
    macro("HFiveMax", per.ctx_none.max())
    macro("HFiveMaxProject", per.loc[per.ctx_none.idxmax(), "project"])
    macro("HFiveMin", per.ctx_none.min())
    macro("HFiveCtxCov", pooled([w[w.project == p]["ctx_cov"].tolist() for p in per.project]))
    out = per.rename(columns={"project": "Project", "none": "None (s)", "coverage": "Coverage (s)",
                              "contexts": "Contexts (s)", "cov_none": "Cov/None", "ctx_none": "Ctx/None",
                              "ctx_cov": "Ctx/Cov"})
    table("h5", out, "H5: median wall time over 10 interleaved blocks, and median per-block ratios.", "tab:h5")


# ---------------------------------------------------------------- H6

def h6() -> None:
    rows = []
    for p in PROJECTS:
        runs = [r for r in latest("e6_flaky", p) if r["kind"] == "flake_run"]
        if not runs:
            continue
        seq = sorted(runs, key=lambda r: (r["order"] != "fixed", r["index"]))
        ids = set().union(*(r["outcomes"].keys() for r in seq))
        flaky = []
        for t in ids:
            outs = [(i, r["outcomes"].get(t)) for i, r in enumerate(seq)]
            passed = [i for i, o in outs if o == "passed"]
            failed = [i for i, o in outs if o in ("failed", "error")]
            if passed and failed:
                flaky.append({"project": p, "test": t, "fails": len(failed), "runs": len(passed) + len(failed),
                              "first_fail_run": min(failed) + 1,
                              "fixed_fails": sum(1 for i in failed if seq[i]["order"] == "fixed"),
                              "random_fails": sum(1 for i in failed if seq[i]["order"] == "random")})
        # A test present in some runs only (unstable ID) is not counted as intermittent.
        rows.append({"project": p, "runs": len(seq), "tests": len(ids), "flaky": flaky})
    flat = [f for r in rows for f in r["flaky"]]
    fdf = pd.DataFrame(flat, columns=["project", "test", "fails", "runs", "first_fail_run", "fixed_fails", "random_fails"])
    fdf.to_csv(DERIVED / "h6_intermittent.csv", index=False)
    macro("HSixProjects", len(rows))
    macro("HSixRuns", rows[0]["runs"] if rows else 0)
    macro("HSixIntermittent", len(fdf))
    macro("HSixProjectsWith", len({f["project"] for f in flat}))
    macro("HSixCaughtByThree", int((fdf.first_fail_run <= 3).sum()) if len(fdf) else 0)
    macro("HSixRandomOnly", int(((fdf.fixed_fails == 0) & (fdf.random_fails > 0)).sum()) if len(fdf) else 0)
    n = rows[0]["runs"] if rows else 60
    macro("HSixUpper", pct(1 - 0.05 ** (1 / n)))
    out = pd.DataFrame([{"Project": r["project"], "Runs": r["runs"], "Tests seen": r["tests"],
                         "Intermittent": len(r["flaky"])} for r in rows])
    table("h6", out, "H6: tests with both a pass and a failure across 30 file-order and 30 random-order runs.", "tab:h6")
    if len(fdf):
        d = fdf.copy()
        d["test"] = d["test"].str.rsplit("::", n=1).str[-1]
        table("h6_detail", d[["project", "test", "fails", "runs", "first_fail_run", "random_fails"]].rename(
            columns={"project": "Project", "test": "Test", "fails": "Fails", "runs": "Runs",
                     "first_fail_run": "First failure (run)", "random_fails": "In random order"}),
            "H6: intermittent tests observed.", "tab:h6detail")


# ---------------------------------------------------------------- skill benchmark

def bench() -> None:
    import json as _json

    vpath = STUDY / "data" / "bench" / "verification.jsonl"
    if not vpath.exists():
        return
    recs = [_json.loads(l) for l in vpath.read_text().splitlines() if l.strip()]
    # Verification is append-only; keep the latest pass for each (arm, project).
    last = {}
    for r in recs:
        last[(r["arm"], r["project"])] = max(last.get((r["arm"], r["project"]), ""), r["vid"])
    keep = [r for r in recs if r["vid"] == last[(r["arm"], r["project"])]]
    ev = STUDY / "data" / "bench" / "events.jsonl"
    times = defaultdict(dict)
    if ev.exists():
        for l in ev.read_text().splitlines():
            e = _json.loads(l)
            if e.get("event") in ("start", "end"):
                times[e["run"]][e["event"]] = e["ts"]  # later records win (reruns)
    rows, per_project = [], defaultdict(dict)
    v0 = [r for r in keep if r["arm"] == "skill-v0" and r["kind"] == "untested"]
    macro("BenchVzeroClaims", len(v0))
    macro("BenchVzeroVerified", sum(r["verdict"] == "verified" for r in v0))
    for arm in ("skill", "baseline"):
        runs = [r for r in keep if r["arm"] == arm and r["kind"] == "run"]
        un = [r for r in keep if r["arm"] == arm and r["kind"] == "untested"]
        rem = [r for r in keep if r["arm"] == arm and r["kind"] == "removal"]
        fl = [r for r in keep if r["arm"] == arm and r["kind"] == "flaky"]
        v = sum(r["verdict"] == "verified" for r in un)
        f = sum(r["verdict"] == "refuted" for r in un)
        u = sum(r["verdict"] == "unverifiable" for r in un)
        lo, hi = wilson(v, v + f)
        recommending = [r for r in rem if r["verdict"] != "none recommended"]
        refuted = [r for r in rem if r["verdict"] == "refuted"]
        mins = [(t["end"] - t["start"]) / 60 for k, t in times.items() if k.startswith(arm + "/") and "end" in t]
        key = "Skill" if arm == "skill" else "Base"
        macro(f"Bench{key}Runs", len(runs))
        macro(f"Bench{key}Claims", len(un))
        macro(f"Bench{key}Verified", v)
        macro(f"Bench{key}Refuted", f)
        macro(f"Bench{key}Unverifiable", u)
        macro(f"Bench{key}Precision", pct(v / (v + f)) if v + f else "n/a")
        macro(f"Bench{key}PrecisionLo", pct(lo))
        macro(f"Bench{key}PrecisionHi", pct(hi))
        macro(f"Bench{key}Recommending", len(recommending))
        macro(f"Bench{key}RemovalRefuted", len(refuted))
        macro(f"Bench{key}Modified", sum(r["modified"] for r in runs))
        macro(f"Bench{key}Unparsed", sum(not r["parsed"] for r in runs))
        macro(f"Bench{key}Flaky", len(fl))
        macro(f"Bench{key}FlakyConfirmed", sum(r["verdict"] == "confirmed" for r in fl))
        macro(f"Bench{key}Minutes", f"{statistics.median(mins):.1f}" if mins else "n/a")
        macro(f"Bench{key}VerifiedMutant", sum(r.get("why") == "a valid, activated mutant survived" for r in un))
        macro(f"Bench{key}VerifiedUncovered", sum(r.get("why") == "executable line that no test covers" for r in un))
        macro(f"Bench{key}RemovalUnverifiable", sum(r["verdict"] == "unverifiable" for r in rem))
        for p in PROJECTS:
            pu = [r for r in un if r["project"] == p]
            pv, pf = sum(r["verdict"] == "verified" for r in pu), sum(r["verdict"] == "refuted" for r in pu)
            per_project[p][arm] = (pv, pf, len(pu), any(r["verdict"] == "refuted" for r in rem if r["project"] == p))
        rows.append({"Arm": arm, "Runs": len(runs), "Claims": len(un), "Verified": v,
                     "by mutant": sum(r.get("why") == "a valid, activated mutant survived" for r in un),
                     "uncovered": sum(r.get("why") == "executable line that no test covers" for r in un),
                     "Refuted": f,
                     "Unverifiable": u, "Precision": f"{100 * v / (v + f):.0f}%" if v + f else "--",
                     "Removal lists": len(recommending), "Refuted lists": len(refuted),
                     "Edited files": sum(r["modified"] for r in runs)})
    table("bench", pd.DataFrame(rows), "Skill benchmark: claims checked independently against pristine projects. "
          "\\emph{by mutant}: verified because a valid, activated mutant on that line survived; \\emph{uncovered}: verified because no test runs the line. "
          "\\emph{Precision}: verified / (verified + refuted) untested-behaviour claims. \\emph{Refuted lists}: "
          "removal recommendations that lose at least one mutant kill when the listed tests are removed together. "
          "\\emph{Edited files}: runs that changed test or source files.", "tab:bench")
    prows = []
    better = worse = 0
    for p in PROJECTS:
        d = per_project[p]
        if "skill" not in d or "baseline" not in d:
            continue
        def prec(t):
            return t[0] / (t[0] + t[1]) if t[0] + t[1] else math.nan
        ps, pb = prec(d["skill"]), prec(d["baseline"])
        if not math.isnan(ps) and not math.isnan(pb):
            better += ps > pb
            worse += ps < pb
        prows.append({"Project": p,
                      "Skill verified/claims": f"{d['skill'][0]}/{d['skill'][2]}",
                      "Skill refuted": d["skill"][1],
                      "Baseline verified/claims": f"{d['baseline'][0]}/{d['baseline'][2]}",
                      "Baseline refuted": d["baseline"][1],
                      "Baseline removal refuted": "yes" if d["baseline"][3] else "no"})
    obs = STUDY / "data" / "bench" / "observations.jsonl"
    in_place = {_json.loads(l)["run"] for l in obs.read_text().splitlines() if l.strip()} if obs.exists() else set()
    macro("BenchBaseInPlace", sum(1 for r in in_place if r.startswith("baseline/")))
    macro("BenchSkillInPlace", sum(1 for r in in_place if r.startswith("skill/")))
    macro("BenchPairedBetter", better)
    macro("BenchPairedWorse", worse)
    if prows:
        table("bench_projects", pd.DataFrame(prows), "Skill benchmark per project.", "tab:benchprojects")


def write_macros() -> None:
    lines = ["% Generated by study/analysis/run.py. Do not edit."]
    for k, v in sorted(macros.items()):
        lines.append(f"\\newcommand{{\\{k}}}{{{v}}}")
    (GEN / "macros.tex").write_text("\n".join(lines) + "\n")


def main() -> None:
    for d in (DERIVED, GEN, FIG):
        d.mkdir(parents=True, exist_ok=True)
    for step in (corpus_table, h1, h2, h3, h4, h5, h6, bench):
        step()
        print(f"{step.__name__}: ok", flush=True)
    write_macros()


if __name__ == "__main__":
    main()
