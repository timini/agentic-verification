"""Mutant records and the normalized statuses used in every report and study table."""

import difflib
import hashlib
from dataclasses import dataclass, field
from functools import cached_property

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
    # The mutant is stored as an edit of the original file text: base[edit_start:edit_end] is
    # replaced by edit_text. All mutants of a file share one base string, so a large module's
    # thousands of mutants do not each hold a full copy of it.
    base: str = field(repr=False, compare=False)
    edit_start: int = 0
    edit_end: int = 0
    edit_text: str = ""

    @property
    def mutated_source(self) -> str:
        return self.base[: self.edit_start] + self.edit_text + self.base[self.edit_end :]

    @cached_property
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
        d = {k: getattr(self, k) for k in ("file", "population", "operator", "start_line", "end_line",
                                           "original", "replacement", "function")}
        d["id"] = self.id
        return d
