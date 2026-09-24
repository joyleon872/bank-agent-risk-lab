"""
Knowledge base scanner: a control at the point of ingestion.

Policy documents should describe policies. They should never talk to the AI,
mention its internal tool names, or ask for secrecy. Any chunk that does is
quarantined: kept out of the search index and reported, so a human can review it.

Why this matters (Phase 4 finding): a planted note didn't hijack the agent, but
it took a slot in the top retrieved chunks and pushed out the legitimate
"how to block your card" line, so fraud answers stopped telling customers to
block their card. Scanning at ingestion removes the note before it can
compete for retrieval.
"""
import re

TOOL_NAMES = ("look_up_fee", "check_card_status", "block_card", "send_email")

PATTERNS = [
    (re.compile(r"\b(note|message|instructions?)\s+(to|for)\s+(the\s+)?(ai|assistant|model|bot|chatbot)\b", re.I),
     "addresses the AI directly"),
    (re.compile(r"\bignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\b", re.I), "asks to ignore instructions"),
    (re.compile(r"\bdo\s+not\s+(mention|tell|reveal|disclose)\s+this\b", re.I), "asks for secrecy"),
    (re.compile(r"\bsystem\s+(prompt|instruction|message)s?\b", re.I), "references system instructions"),
    (re.compile(r"\b(" + "|".join(TOOL_NAMES) + r")\b", re.I), "names an internal tool"),
]


def scan(text: str) -> list[str]:
    """Return the reasons a chunk looks like an injected instruction (empty list = clean)."""
    return [reason for pattern, reason in PATTERNS if pattern.search(text)]
