# Bank Agent Risk Lab

Version 2 of [llm-risk-evaluation](https://github.com/joyleon872/llm-risk-evaluation): a fictional bank's customer service assistant rebuilt as a real system, with retrieval, tools, guardrails, observability and continuous evaluation.

**Status:** Phase 1 of 5 complete (RAG assistant).

| Phase | What | Status |
|---|---|---|
| 1 | RAG assistant: FastAPI service answering from retrieved policy documents | ✅ |
| 2 | Agent with MCP tools, plus tool-misuse testing | ⏳ |
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

## How it works

1. **Knowledge base:** policy documents in `data/kb/`, one file per area.
2. **Retrieval** (`app/retriever.py`): documents are split into one chunk per policy line and ranked with BM25 keyword relevance; the top 4 chunks are returned for each question.
3. **Generation** (`app/bot.py`): Claude Haiku 4.5 answers using only the retrieved chunks, under rules that treat both customer messages and documents as information, never instructions.
4. **API** (`app/main.py`): FastAPI service with `/chat`, `/health` and a simple chat page.

No secrets are placed in the system prompt, following recommendation 3 from project 1.
