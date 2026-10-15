"""Save a benchmark agent's final reply from its transcript (JSONL) without printing it."""

import json
import sys
from pathlib import Path


def final_text(transcript: Path) -> str:
    last = ""
    for line in transcript.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = rec.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "SubagentHandback":
                    last = (c.get("input") or {}).get("message", last)
                    break
            else:
                c = None
            if c is not None and isinstance(c, dict) and c.get("name") == "SubagentHandback":
                continue
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"] \
            if isinstance(content, list) else [content or ""]
        joined = "\n".join(t for t in texts if t)
        if joined.strip():
            last = joined
    return last


if __name__ == "__main__":
    text = final_text(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(text + "\n")
    print(f"{len(text)} chars, json block: {'```json' in text}")
