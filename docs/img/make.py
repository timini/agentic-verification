"""Build the README images from the study's generated numbers.

    python3 docs/img/make.py

Reads study/paper/generated/macros.tex (written by `make -C study analyse`), so the numbers in
the images are the numbers in the paper. Writes hero.svg and verify.svg next to this file.
"""

import re
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
MACROS = HERE.parents[1] / "study" / "paper" / "generated" / "macros.tex"

BG, PANEL, LINE = "#0d1117", "#161b22", "#30363d"
TEXT, MUTED, ACCENT, GOOD, BAD = "#e6edf3", "#9da7b3", "#f0883e", "#3fb950", "#f85149"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def macros() -> dict[str, str]:
    text = MACROS.read_text()
    return {m[0]: m[1].replace("\\%", "%").replace("{,}", ",")
            for m in re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", text)}


def t(x, y, s, size=16, fill=TEXT, weight=400, family=FONT, anchor="start") -> str:
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}" xml:space="preserve">{escape(s)}</text>')


def hero(m: dict) -> str:
    W, H = 1280, 640
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" rx="24" fill="{BG}"/>']
    # Mark: a 3x3 grid of mutants, one survivor, and a check.
    for i in range(3):
        for j in range(3):
            cx, cy = 76 + 22 * j, 78 + 22 * i
            if (i, j) == (1, 2):
                out.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="none" stroke="{ACCENT}" stroke-width="3"/>')
            else:
                out.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{MUTED}"/>')
    out.append(t(150, 100, "Agentic Verification", 44, TEXT, 700))
    out.append(t(150, 136, "Evidence that your tests would catch it, for Claude Code on Python and pytest.", 21, MUTED))

    cards = [
        ("verify", "your change", [
            "Runs every mutant of the lines you changed.",
            "Writes tests until the tests catch them.",
            "Hands back a verdict and evidence, not a diff to read."]),
        ("audit", "your test suite", [
            "Would it notice broken code?",
            "Is it fast and stable enough to run on every change?",
            "Which tests could go? Checked on fresh mutants."]),
    ]
    for k, (cmd, what, lines) in enumerate(cards):
        x = 64 + k * 584
        out.append(f'<rect x="{x}" y="184" width="560" height="196" rx="14" fill="{PANEL}" stroke="{LINE}"/>')
        out.append(t(x + 28, 228, f"/{cmd}", 28, ACCENT, 700, MONO))
        out.append(t(x + 28 + 20 * (len(cmd) + 1), 228, what, 24, TEXT, 600))
        for i, line in enumerate(lines):
            out.append(t(x + 28, 274 + 34 * i, line, 19, TEXT))

    pct0 = lambda k: m.get(k, "?").split(".")[0] + "%" if "." in m.get(k, "") else m.get(k, "?")
    stats = [(pct0("HSevenGapShare"), "of recent commits we could judge", "in mature libraries left mutants", "of the changed lines uncaught"),
             (pct0("HThreeShare"), "of calls no test notices sit in", "functions whose deletion", "the tests do catch"),
             (f'{pct0("VTwoSkillRate")} vs {pct0("VTwoBaseRate")}', "of a change's mutants caught by", "Claude's tests with the skill", f'and without (developers: {pct0("VTwoUpRate")})')]
    for k, (big, *cap) in enumerate(stats):
        x = 64 + k * 392
        out.append(t(x, 470, big, 50, TEXT, 700))
        for i, c in enumerate(cap):
            out.append(t(x, 506 + 25 * i, c, 18, MUTED))
    out.append(t(W - 64, 610, "Pre-registered study on 8 open-source projects. Paper, data and code in the repository.",
                 15, MUTED, anchor="end"))
    out.append("</svg>")
    return "\n".join(out)


def verify_example() -> str:
    """Three real verify runs on a small change to the known-answer fixture (a new tax function)."""
    rows = [
        ("$ agentic-verification verify      # tests: tax(100) == 20, tax(15) == 3, tax(0) == 0", MUTED, 400),
        ("Verdict: gaps   8 of 12 mutants killed, 1 changed line never run", BAD, 700),
        ("  orders.py:54  total * 2 // 10  ->  total * 2 / 10   survived: 20.0 == 20 passes too", ACCENT, 400),
        ("  orders.py:53  raise ValueError(...)                 never run by a test", ACCENT, 400),
        ("", TEXT, 400),
        ("+ assert isinstance(orders.tax(15), int)", GOOD, 400),
        ('+ with pytest.raises(ValueError, match="negative total"): orders.tax(-1)', GOOD, 400),
        ("$ agentic-verification replay --mutant 37c3b60f --all      killed_now: true", MUTED, 400),
        ("", TEXT, 400),
        ("Verdict: gaps   11 of 12 mutants killed", BAD, 700),
        ('  orders.py:53  "negative total"  ->  "XXnegative totalXX"   survived: match= searches', ACCENT, 400),
        ("", TEXT, 400),
        ('+ match="^negative total$"', GOOD, 400),
        ("", TEXT, 400),
        ("Verdict: verified   12 of 12 mutants killed, every changed line run", GOOD, 700),
    ]
    W, H = 1280, 120 + 30 * len(rows)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>',
           f'<rect x="0" y="0" width="{W}" height="44" rx="18" fill="{PANEL}"/>',
           f'<rect x="0" y="26" width="{W}" height="18" fill="{PANEL}"/>']
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        out.append(f'<circle cx="{28 + 22 * i}" cy="22" r="7" fill="{c}"/>')
    out.append(t(W / 2, 28, "verify on a new four-line function: three rounds until the tests catch every mutant", 15, MUTED, anchor="middle"))
    for i, (s, fill, weight) in enumerate(rows):
        out.append(t(40, 92 + 30 * i, s, 19, fill, weight, MONO))
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    m = macros()
    (HERE / "hero.svg").write_text(hero(m))
    (HERE / "verify.svg").write_text(verify_example())
    print("wrote", HERE / "hero.svg", HERE / "verify.svg")
