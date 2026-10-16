"""Task prompts for the verify benchmark. Both arms get the same task; the skill arm also gets
the skill text with its runner pinned to the commit that registered the benchmark."""

import json
import subprocess
import sys
from pathlib import Path

from bench2.common import DATA

REPO = Path(__file__).resolve().parents[2]
PIN = "4ad81ab0621cf327df921042cf203bd383abcf16"  # 51a17eb before the history rewrite (study/COMMIT_MAP.md)

TASK = """You are working in the Python repository at {ws}. Use its virtual environment, {ws}/.venv/bin/python, which has pytest installed; the tests are in {tests}.

The working tree has an uncommitted change to production code; `git diff` shows it. The change is described by its commit message:

<commit-message>
{message}
</commit-message>

Your task: make sure this change is properly verified by the test suite. Add or change tests as you see fit. Do not modify production source files ({source}). Do not commit, and do not change anything outside {ws}. Aim for about 20 minutes of work.

When you are done, end your reply with a JSON block:
```json
{{"tests_added": ["<pytest node id>", "..."], "summary": "<one or two sentences>"}}
```"""

SKILL = """

A skill is installed for this task. Follow it. Its runner command works as written; the report reference it links is at {ref}.

<skill>
{skill}
</skill>"""


def prompt(w: dict) -> str:
    from bench2.common import entry
    e = entry(w["project"])
    text = TASK.format(ws=w["workspace"], tests=", ".join(e.tests), message=w["message"],
                       source=", ".join(w["source_files"]))
    if w["arm"] == "skill":
        # The skill as registered, not as it may have changed since.
        skill = subprocess.run(["git", "show", f"{PIN}:plugin/skills/verify/SKILL.md"], cwd=REPO, check=True,
                               capture_output=True, text=True).stdout.replace("@v0.3.0", f"@{PIN}")
        text += SKILL.format(skill=skill, ref=REPO / "plugin/skills/audit/reference/report.md")
    return text


if __name__ == "__main__":
    wss = json.loads((DATA / "workspaces.json").read_text())
    arm, task = sys.argv[1], sys.argv[2]
    print(prompt(next(w for w in wss if w["arm"] == arm and w["task"] == task)))
