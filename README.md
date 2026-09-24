# Bank Agent Risk Lab

Version 2 of [llm-risk-evaluation](https://github.com/joyleon872/llm-risk-evaluation): a fictional bank's customer service assistant rebuilt as a real system, with retrieval, tools, guardrails, observability and continuous evaluation.

**Status:** Phase 4 of 5 complete (evals and CI).

| Phase | What | Status |
|---|---|---|
| 1 | RAG assistant: FastAPI service answering from retrieved policy documents | ✅ |
| 2 | Agent with MCP tools, plus a poisoned knowledge base for tool-misuse testing | ✅ |
| 3 | Guardrails enforced in code (tool policy, confirmation, output filter) and observability dashboard | ✅ |
| 4 | Evals comparing prompt-only vs code guardrails under attack, automated in GitHub Actions | ✅ |
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

To turn the code-level controls **off** for comparison:

```bash
GUARDRAILS=off KB_DIR=data/kb_poisoned uvicorn app.main:app --reload
```

The observability dashboard is at http://localhost:8000/dashboard.

## Run with Docker

```bash
docker build -t bank-agent .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY bank-agent
```

The container runs the poisoned knowledge base with every control on, so the dashboard shows the scanner quarantining the planted instructions. On every change to the app, GitHub Actions builds the image and publishes it to `ghcr.io/joyleon872/bank-agent-risk-lab`.

A public demo is protected against runaway API spend by a per-visitor hourly limit and a daily cap (`RATE_LIMIT_PER_HOUR`, `DAILY_REQUEST_CAP`).

## How it works

1. **Knowledge base:** policy documents in `data/kb/`, one file per area.
2. **Retrieval** (`app/retriever.py`): documents are split into one chunk per policy line and ranked with BM25 keyword relevance; the top 4 chunks are returned for each question.
3. **Tools over MCP** (`app/mcp_server.py`): an MCP server exposes four fake bank tools: `look_up_fee`, `check_card_status`, `block_card` (irreversible) and `send_email`. Two fake customers exist: the logged-in customer (card 4471) and another customer (card 8820) the agent must never act on.
4. **Agent** (`app/agent.py`): connects to the MCP server as a client, discovers the tools, and lets Claude Haiku 4.5 call them in a loop. Every tool call is returned with the answer, so tests can check what the agent *did*, not just what it said.
5. **API** (`app/main.py`): FastAPI service with `/chat`, `/health` and a chat page that shows tool calls.

6. **Guardrails** (`app/guardrails.py`): controls enforced in code, regardless of what the model decides:
   - card tools only work on the logged-in customer's own card
   - `block_card` never runs directly; it creates a pending action the customer must confirm with a button (human in the loop)
   - `send_email` only goes to the customer's own address
   - an output filter removes links and email addresses that aren't on the allowlist
7. **Knowledge base scanner** (`app/kb_scanner.py`): at load time, any document chunk that addresses the AI, names an internal tool, asks for secrecy or references system instructions is quarantined and reported for human review. Added after the Phase 4 evaluation found that a planted note was crowding legitimate safety guidance out of retrieval. Turn off with `KB_SCAN=off`.
8. **Observability** (`app/observability.py`): every request is logged to `logs/events.jsonl` (question, sources, tool calls with policy decisions, filtered output, tokens, latency), summarised at `/dashboard`.

These implement recommendations 2 and 3 from project 1: filter outputs for unapproved links, and keep secrets out of the prompt. Phase 4 measures how much they change the agent's behaviour under attack.

No secrets are placed in the system prompt, following recommendation 3 from project 1.

## Evaluation (Phase 4)

`evals/run_evals.py` runs 17 test cases (`evals/cases.yaml`) against two configurations, 10 times each:

- **prompt_only:** safety rules in the system prompt only
- **guardrails:** the same prompt plus the code-level controls

Most checks look at what the agent **did**, not just what it said: which tools it called, on which card, to which address, and whether policy allowed it. Each security check records whether the model *attempted* the harmful action and whether it *succeeded*, since guardrails don't change what the model tries, only what actually happens. Results are reported with 95% Wilson confidence intervals.

```bash
python -m evals.run_evals                 # full run (about 340 agent runs)
python -m evals.run_evals --repeats 3     # quicker
python -m evals.run_evals --cases A1 A3 Q1 Q2 --configs guardrails guardrails_kbscan --name kbscan_fix   # verify the fix
```

The report is written to `results/findings_eval.md`.

Each run is saved line by line to `results/eval_runs*.jsonl` as it completes, API calls time out after 60 seconds and retry, and `--report-from` rebuilds a report from saved runs, so a stalled request never costs a whole evaluation.

**Continuous evaluation:** `.github/workflows/evals.yml` runs a small suite (8 cases, all controls on, 2 runs each) on every change to the agent, documents, guardrails or tests, and fails the build if any attack succeeds or a legitimate request breaks.
