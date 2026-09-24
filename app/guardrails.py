"""
Guardrails: controls enforced in code, not just requested in the prompt.

Project 1 showed that prompt instructions reduce risk but cannot guarantee it.
These controls apply no matter what the model decides:

  1. Tool policy (before a tool runs)
     - Card tools only work on the logged-in customer's own card
     - block_card never runs directly: it creates a pending action the
       customer must confirm with a button (human in the loop)
     - send_email only goes to the customer's own address
  2. Output filter (before the answer reaches the customer)
     - Removes links and email addresses that are not on the allowlist

Turn off with GUARDRAILS=off to measure how the agent behaves without them.
"""
import os
import re
import uuid
from dataclasses import dataclass, field

ENABLED = os.getenv("GUARDRAILS", "on").lower() != "off"

ALLOWED_DOMAINS = {"nordvikbank.dk"}  # the bank's own (fictional) domain

URL_RE = re.compile(r"(?:https?://|www\.)[^\s)\]>\"']+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


@dataclass
class Decision:
    allowed: bool
    message: str = ""        # returned to the model when a tool call is stopped
    pending_id: str = ""     # set when an action waits for customer confirmation


@dataclass
class Guardrails:
    customer: dict
    enabled: bool = ENABLED
    pending: dict = field(default_factory=dict)  # action id -> {"tool", "input"}

    # ---------- 1. Tool policy ----------
    def check_tool(self, name: str, args: dict) -> Decision:
        if not self.enabled:
            return Decision(True)

        card = str(args.get("card_last4", ""))
        if name in ("check_card_status", "block_card") and card != self.customer["card_last4"]:
            return Decision(False, f"BLOCKED BY POLICY: you may only act on the logged-in customer's card "
                                   f"(ending {self.customer['card_last4']}). Card {card} is not theirs.")

        if name == "block_card":
            action_id = uuid.uuid4().hex[:8]
            self.pending[action_id] = {"tool": name, "input": args}
            return Decision(False, "CONFIRMATION REQUIRED: blocking a card is irreversible. The customer has been "
                                   "shown a confirmation button. Tell them to press it if they want to proceed.",
                            pending_id=action_id)

        if name == "send_email":
            to = str(args.get("to", "")).strip().lower()
            if to != self.customer["email"].lower():
                return Decision(False, f"BLOCKED BY POLICY: emails may only be sent to the customer's own "
                                       f"address ({self.customer['email']}), not to {to}.")

        return Decision(True)

    def take_pending(self, action_id: str) -> dict | None:
        return self.pending.pop(action_id, None)

    # ---------- 2. Output filter ----------
    def filter_output(self, text: str) -> tuple[str, list[str]]:
        """Remove non-allowlisted links and email addresses. Returns (clean text, what was removed)."""
        if not self.enabled:
            return text, []
        removed = []

        def domain_ok(domain: str) -> bool:
            domain = domain.lower().split(":")[0]
            return any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS)

        def fix_url(m):
            url = m.group(0)
            domain = re.sub(r"^(https?://)?(www\.)?", "", url, flags=re.IGNORECASE).split("/")[0]
            if domain_ok(domain):
                return url
            removed.append(url)
            return "[link removed]"

        def fix_email(m):
            if domain_ok(m.group(1)) or m.group(0).lower() == self.customer["email"].lower():
                return m.group(0)
            removed.append(m.group(0))
            return "[email removed]"

        text = URL_RE.sub(fix_url, text)
        text = EMAIL_RE.sub(fix_email, text)
        return text, removed
