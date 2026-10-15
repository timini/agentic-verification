"""Mutant records and the normalized statuses used in every report and study table."""

import difflib
import hashlib
from dataclasses import asdict, dataclass

# Normalized statuses (PRD F5). "killed" means a test that passed in every baseline run failed.
KILLED = "killed"
SURVIVED = "survived"  # valid, activated, no killer in the evaluated scope
UNCOVERED = "uncovered"  # no test in scope covers the mutated lines; not executed
NOT_ACTIVATED = "not_activated"  # executed tests never ran the mutated lines
INVALID = "invalid"  # does not compile, or tests cannot be collected/imported
TIMEOUT = "timeout"
INFRA = "infrastructure_failure"
UNKNOWN_ACTIVATION = "activation_unknown"
STATUSES = (KILLED, SURVIVED, UNCOVERED, NOT_ACTIVATED, INVALID, TIMEOUT, INFRA, UNKNOWN_ACTIVATION)


@dataclass(frozen=True)
class Mutant:
    file: str  # relative to project root
    population: str  # "classical" | "deletion"
    operator: str  # e.g. "mutmut", "body:None", "call-delete"
    start_line: int  # first line of the mutated region, in both original and mutant
    end_line: int  # last line of the original region
    original: str  # original source text of the region
    replacement: str  # replacement text
    function: str | None  # qualified name of the enclosing function, if any
    mutated_source: str  # full text of the mutated file

    @property
    def id(self) -> str:
        h = hashlib.sha256()
        for part in (self.file, self.operator, str(self.start_line), self.mutated_source):
            h.update(part.encode())
            h.update(b"\0")
        return h.hexdigest()[:16]

    @property
    def lines(self) -> range:
        return range(self.start_line, self.end_line + 1)

    def patch(self, original_source: str) -> str:
        return "".join(difflib.unified_diff(
            original_source.splitlines(keepends=True), self.mutated_source.splitlines(keepends=True),
            fromfile=f"a/{self.file}", tofile=f"b/{self.file}", n=2,
        ))

    def record(self) -> dict:
        d = asdict(self)
        del d["mutated_source"]
        d["id"] = self.id
        return d
