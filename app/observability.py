"""
Observability: a record of what the agent actually did.

Every request is written as one JSON line to logs/events.jsonl: the question,
retrieved sources, each tool call and whether policy allowed it, anything the
output filter removed, token usage and latency. The /dashboard page summarises
the log so you can see at a glance what the controls caught.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("logs/events.jsonl")


def log_event(event: dict) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(limit: int = 1000) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


def summarise(events: list[dict]) -> dict:
    tool_calls = [t for e in events for t in e.get("tool_calls", [])]
    decisions = Counter(t.get("decision", "allowed") for t in tool_calls)
    by_tool = Counter(t["tool"] for t in tool_calls)
    removed = sum(len(e.get("output_removed", [])) for e in events)
    latencies = [e["latency_ms"] for e in events if "latency_ms" in e]
    flagged = [e for e in events
               if e.get("output_removed") or any(t.get("decision") != "allowed" for t in e.get("tool_calls", []))]
    return {
        "requests": len(events),
        "tool_calls": len(tool_calls),
        "tool_calls_by_tool": dict(by_tool),
        "tool_decisions": dict(decisions),
        "outputs_filtered": removed,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "input_tokens": sum(e.get("usage", {}).get("input_tokens", 0) for e in events),
        "output_tokens": sum(e.get("usage", {}).get("output_tokens", 0) for e in events),
        "flagged": flagged[-20:][::-1],
    }
