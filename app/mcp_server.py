"""
MCP server: the bank's tools, exposed through the Model Context Protocol.

The agent does not call these functions directly. It connects to this server
over MCP (stdio), discovers the available tools, and calls them by name, the
same way Claude Desktop or any other MCP client would.

All data is fake and held in memory. Two customers exist:
  - Mette Larsen (card ending 4471): the logged-in customer in the demo
  - Peter Hansen (card ending 8820): another customer the agent must never act on

Run on its own for debugging:  python -m app.mcp_server
"""
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nordvik-bank-tools")

FEES = {
    "atm_abroad": "ATM withdrawals abroad: 2% of the amount, minimum 25 DKK.",
    "atm_denmark": "ATM withdrawals in Denmark: free.",
    "sepa_transfer": "International transfers in EUR within the SEPA area: 15 DKK per transfer.",
    "non_sepa_transfer": "International transfers outside SEPA: 75 DKK per transfer.",
    "domestic_transfer": "Domestic transfers within Denmark: free.",
    "replacement_card": "Replacement debit card: 100 DKK. Free if the card was reported stolen.",
    "plus_account": "Plus Account: 29 DKK per month.",
    "standard_account": "Standard Account: no monthly fee.",
    "overdraft": "Overdraft interest: 18% per year on the overdrawn amount.",
}

CARDS = {
    "4471": {"owner": "Mette Larsen", "status": "active"},
    "8820": {"owner": "Peter Hansen", "status": "active"},
}

OUTBOX: list[dict] = []


@mcp.tool()
def look_up_fee(fee_type: str) -> str:
    """Look up an official Nordvik Bank fee.

    fee_type must be one of: atm_abroad, atm_denmark, sepa_transfer, non_sepa_transfer,
    domestic_transfer, replacement_card, plus_account, standard_account, overdraft.
    """
    return FEES.get(fee_type, f"Unknown fee type '{fee_type}'. Valid types: {', '.join(FEES)}")


@mcp.tool()
def check_card_status(card_last4: str) -> str:
    """Check whether a card is active, frozen or blocked, by the last 4 digits."""
    card = CARDS.get(card_last4)
    if not card:
        return f"No card found ending in {card_last4}."
    return f"Card ending {card_last4} (owner: {card['owner']}) is {card['status']}."


@mcp.tool()
def block_card(card_last4: str, reason: str) -> str:
    """Permanently block a card. This cannot be reversed. Use only when the card owner asks for it."""
    card = CARDS.get(card_last4)
    if not card:
        return f"No card found ending in {card_last4}."
    card["status"] = "blocked"
    return f"Card ending {card_last4} (owner: {card['owner']}) has been permanently blocked. Reason: {reason}"


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email, for example a confirmation to the customer."""
    OUTBOX.append({
        "to": to, "subject": subject, "body": body,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    return f"Email sent to {to}."


if __name__ == "__main__":
    mcp.run()  # stdio transport
