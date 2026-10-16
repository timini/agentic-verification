"""Append a start or end event for a benchmark run: python -m bench2.event start|end <arm> <task>."""

import json
import sys
import time

from bench2.common import DATA

if __name__ == "__main__":
    event, arm, task = sys.argv[1:4]
    with open(DATA / "events.jsonl", "a") as fh:
        fh.write(json.dumps({"event": event, "arm": arm, "task": task, "ts": time.time()}) + "\n")
