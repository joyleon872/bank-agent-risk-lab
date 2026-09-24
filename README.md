# Bank Agent Risk Lab

Version 2 of [llm-risk-evaluation](https://github.com/joyleon872/llm-risk-evaluation): a fictional bank's customer service assistant rebuilt as a real system, with retrieval, tools, guardrails, observability and continuous evaluation.

**Status:** Phase 2 of 5 complete (agent with MCP tools).

| Phase | What | Status |
|---|---|---|
| 1 | RAG assistant: FastAPI service answering from retrieved policy documents | ✅ |
| 2 | Agent with MCP tools, plus a poisoned knowledge base for tool-misuse testing | ✅ |
| 3 | Guardrails (URL filtering, action confirmation) and observability | ⏳ |
| 4 | Evals comparing controls on/off, automated in CI | ⏳ |
| 5 | Docker + Azure deployment and risk assessment write-up | ⏳ |

## Run locally

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # your key
uvicorn app.main:app --reload
```

Open http://localhost:8000 for the chat page, or call the API:

```bash
curl -s localhost:8000/chat -H "content-type: application/json" -d '{"question":"What is the ATM fee abroad?"}'
```

To run against the **poisoned knowledge base** (hidden malicious instructions targeting the tools):

```bash
KB_DIR=data/kb_poisoned uvicorn app.main:app --reload
```

## How it works

1. **Knowledge base:** policy documents in `data/kb/`, one file per area.
2. **Retrieval** (`app/retriever.py`): documents are split into one chunk per policy line and ranked with BM25 keyword relevance; the top 4 chunks are returned for each question.
3. **Tools over MCP** (`app/mcp_server.py`): an MCP server exposes four fake bank tools: `look_up_fee`, `check_card_status`, `block_card` (irreversible) and `send_email`. Two fake customers exist: the logged-in customer (card 4471) and another customer (card 8820) the agent must never act on.
4. **Agent** (`app/agent.py`): connects to the MCP server as a client, discovers the tools, and lets Claude Haiku 4.5 call them in a loop. Every tool call is returned with the answer, so tests can check what the agent *did*, not just what it said.
5. **API** (`app/main.py`): FastAPI service with `/chat`, `/health` and a chat page that shows tool calls.

In Phase 2 the only protection against tool misuse is the system prompt. Phase 3 adds controls enforced in code, and Phase 4 measures the difference.

No secrets are placed in the system prompt, following recommendation 3 from project 1.
