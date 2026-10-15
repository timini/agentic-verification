"""Append-only raw records. Every record carries the provenance needed to interpret it."""

import gzip
import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .corpus import STUDY, Entry, freeze

RAW = STUDY / "data" / "raw"
SEED = 20261015


def _runner_sha() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=STUDY, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "../runner"], cwd=STUDY,
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except OSError:
        return "unknown"


RUN_ID = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
RUNNER_SHA = _runner_sha()
PLATFORM = f"{platform.system()}-{platform.machine()}-{platform.release()}"


class Recorder:
    def __init__(self, experiment: str, entry: Entry):
        self.entry = entry
        self.experiment = experiment
        d = RAW / entry.name / experiment
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{RUN_ID}.jsonl"
        self.fh = open(self.path, "a", buffering=1)
        env_hash = hashlib.sha256(freeze(entry).encode()).hexdigest()[:12]
        self.prov = {
            "run_id": RUN_ID, "experiment": experiment, "project": entry.name,
            "project_sha": entry.sha, "runner_sha": RUNNER_SHA, "platform": PLATFORM,
            "python": sys.version.split()[0], "env_hash": env_hash, "seed": SEED,
        }
        self.write("run_start", freeze=freeze(entry).splitlines())

    def write(self, kind: str, **data) -> None:
        rec = {"kind": kind, "ts": time.time(), **self.prov, **data}
        self.fh.write(json.dumps(rec, default=str) + "\n")

    def close(self) -> None:
        self.write("run_end")
        self.fh.close()


def read_all(experiment: str, project: str | None = None) -> list[dict]:
    """All records of an experiment. Finished runs are stored gzipped (see compress_finished)."""
    out = []
    paths = list(RAW.glob(f"{project or '*'}/{experiment}/*.jsonl")) + list(RAW.glob(f"{project or '*'}/{experiment}/*.jsonl.gz"))
    for p in sorted(paths, key=lambda p: p.name):
        text = gzip.decompress(p.read_bytes()).decode() if p.suffix == ".gz" else p.read_text()
        out.extend(json.loads(line) for line in text.splitlines() if line.strip())
    return out


def compress_finished() -> None:
    """Gzip every raw JSONL file whose run has ended. Content is unchanged; only the encoding."""
    for p in RAW.glob("*/*/*.jsonl"):
        lines = p.read_text().splitlines()
        if lines and json.loads(lines[-1]).get("kind") == "run_end":
            p.with_suffix(".jsonl.gz").write_bytes(gzip.compress(p.read_bytes(), mtime=0))
            p.unlink()
