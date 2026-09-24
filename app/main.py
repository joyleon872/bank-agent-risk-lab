"""
Web service for the Nordvik Bank assistant.

Endpoints:
  GET  /           chat page (renders answers, tool calls and confirmation buttons)
  GET  /dashboard  observability dashboard: what the agent did and what the controls caught
  GET  /health     status check (used by Docker and Azure)
  POST /chat       {"question": "..."} -> answer, tool calls, pending actions, sources
  POST /confirm    {"action_id": "..."} -> runs an action the customer confirmed

Environment:
  KB_DIR=data/kb_poisoned   run against the poisoned knowledge base
  GUARDRAILS=off            disable the code-level controls (for comparison in evals)
"""
import html
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agent import Agent
from app.observability import read_events, summarise

KB_DIR = os.getenv("KB_DIR", "data/kb")
agent = Agent(KB_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent.start()   # launch and connect to the MCP tool server
    yield
    await agent.stop()


app = FastAPI(title="Nordvik Bank Assistant", version="0.3.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ConfirmRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=64)


@app.get("/health")
def health():
    return {"status": "ok", "kb_dir": KB_DIR, "guardrails": agent.guard.enabled,
            "chunks": len(agent.retriever.chunks), "tools": [t["name"] for t in agent.tools]}


@app.post("/chat")
async def chat(req: ChatRequest):
    return await agent.answer(req.question)


@app.post("/confirm")
async def confirm(req: ConfirmRequest):
    return await agent.confirm(req.action_id)


@app.get("/", response_class=HTMLResponse)
def home():
    status = f"Knowledge base: {html.escape(KB_DIR)} · Guardrails: {'ON' if agent.guard.enabled else 'OFF'}"
    return CHAT_PAGE.replace("{{STATUS}}", status)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    s = summarise(read_events())
    esc = lambda v: html.escape(str(v))
    cards = [("Requests", s["requests"]), ("Tool calls", s["tool_calls"]),
             ("Tool calls blocked", s["tool_decisions"].get("blocked", 0)),
             ("Awaiting confirmation", s["tool_decisions"].get("pending_confirmation", 0)),
             ("Links/emails removed", s["outputs_filtered"]), ("Avg latency", f'{s["avg_latency_ms"]} ms'),
             ("Tokens in / out", f'{s["input_tokens"]:,} / {s["output_tokens"]:,}')]
    card_html = "".join(f'<div class="card"><div class="n">{esc(v)}</div><div class="l">{esc(k)}</div></div>'
                        for k, v in cards)
    rows = []
    for e in s["flagged"]:
        issues = [f'{t["tool"]}({esc(t["input"])}) → {t.get("decision")}'
                  for t in e.get("tool_calls", []) if t.get("decision") != "allowed"]
        issues += [f"removed: {esc(r)}" for r in e.get("output_removed", [])]
        rows.append(f'<tr><td>{esc(e.get("timestamp", "")[:19].replace("T", " "))}</td>'
                    f'<td>{esc(e.get("question", e.get("event", "")))}</td><td>{"<br>".join(issues)}</td></tr>')
    table = "".join(rows) or '<tr><td colspan="3">Nothing flagged yet.</td></tr>'
    by_tool = ", ".join(f"{k}: {v}" for k, v in s["tool_calls_by_tool"].items()) or "none"
    return DASHBOARD_PAGE.replace("{{CARDS}}", card_html).replace("{{ROWS}}", table).replace("{{BYTOOL}}", esc(by_tool))


STYLE = """
  body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1b1b1b}
  h1{font-size:22px;margin-bottom:4px} .sub{color:#666;margin-top:0;font-size:14px} a{color:#1f3a5f}
"""

CHAT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nordvik Bank Assistant</title>
<style>""" + STYLE + """
  #log{border:1px solid #ddd;border-radius:10px;padding:12px;min-height:300px;margin:16px 0;overflow-y:auto}
  .q{font-weight:600;margin-top:14px} .a{margin:4px 0} .a p{margin:6px 0} .a ul,.a ol{margin:6px 0;padding-left:22px}
  .src{font-size:12px;color:#777}
  .tool{font-size:12px;border-radius:6px;padding:4px 8px;margin:4px 0;font-family:ui-monospace,monospace}
  .allowed{color:#8a4b00;background:#fff4e5} .blocked{color:#9b1c1c;background:#fde8e8}
  .pending,.confirmed{color:#1f3a5f;background:#e8f0fb} .removed{font-size:12px;color:#9b1c1c}
  .confirm{margin:4px 0;padding:6px 12px;border:0;border-radius:6px;background:#9b1c1c;color:#fff;cursor:pointer}
  form{display:flex;gap:8px}
  input{flex:1;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:15px}
  button.send{padding:10px 16px;border:0;border-radius:8px;background:#1f3a5f;color:#fff;font-size:15px;cursor:pointer}
</style></head><body>
<h1>Nordvik Bank Assistant</h1>
<p class="sub">Fictional bank for AI risk testing. Logged in as Mette Larsen (card ending 4471).<br>{{STATUS}} · <a href="/dashboard">Dashboard</a></p>
<div id="log"></div>
<form id="f"><input id="q" placeholder="Ask about fees, cards, loans..." autocomplete="off"><button class="send">Send</button></form>
<script>
const log=document.getElementById('log'), q=document.getElementById('q');
const esc=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function md(text){ // minimal markdown: bold, bullet and numbered lists, paragraphs
  const lines=esc(text).split('\\n'); let out='', list=null;
  for(const raw of lines){
    const line=raw.replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>');
    const ul=line.match(/^\\s*[-*]\\s+(.*)/), ol=line.match(/^\\s*\\d+\\.\\s+(.*)/);
    const type=ul?'ul':ol?'ol':null;
    if(type!==list){ if(list) out+='</'+list+'>'; if(type) out+='<'+type+'>'; list=type; }
    if(type) out+='<li>'+(ul||ol)[1]+'</li>'; else if(line.trim()) out+='<p>'+line+'</p>';
  }
  return out+(list?'</'+list+'>':'');
}
function add(cls, content, isHtml){const d=document.createElement('div');d.className=cls;
  if(isHtml) d.innerHTML=content; else d.textContent=content; log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
async function post(url, body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();}
document.getElementById('f').onsubmit=async e=>{
  e.preventDefault(); const question=q.value.trim(); if(!question) return;
  add('q', question); q.value=''; const a=add('a','Thinking...');
  try{
    const data=await post('/chat',{question}); a.innerHTML=md(data.answer||JSON.stringify(data));
    const icon={allowed:'🔧',blocked:'⛔',pending_confirmation:'⏸'};
    (data.tool_calls||[]).forEach(t=>add('tool '+(t.decision==='pending_confirmation'?'pending':t.decision),
      (icon[t.decision]||'🔧')+' '+t.tool+'('+JSON.stringify(t.input)+') → '+t.result));
    (data.pending_actions||[]).forEach(p=>{
      const btn=document.createElement('button'); btn.className='confirm';
      btn.textContent='Confirm: permanently block card '+(p.input.card_last4||'');
      const wrap=add('',''); wrap.appendChild(btn);
      btn.onclick=async()=>{btn.disabled=true; const r=await post('/confirm',{action_id:p.id}); add('tool confirmed','✅ '+r.message);};
    });
    if((data.output_removed||[]).length) add('removed','Output filter removed: '+data.output_removed.join(', '));
    if(data.sources&&data.sources.length) add('src','Sources: '+[...new Set(data.sources.map(s=>s.source))].join(', '));
  }catch(err){a.textContent='Error: '+err;}
};
</script></body></html>"""

DASHBOARD_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard · Nordvik Bank Assistant</title>
<style>""" + STYLE + """
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin:16px 0}
  .card{border:1px solid #ddd;border-radius:10px;padding:12px} .n{font-size:22px;font-weight:700} .l{font-size:12px;color:#666}
  table{width:100%;border-collapse:collapse;font-size:13px} td,th{border-bottom:1px solid #eee;padding:6px;text-align:left;vertical-align:top}
</style></head><body>
<h1>Observability dashboard</h1>
<p class="sub">From logs/events.jsonl · <a href="/">Back to chat</a></p>
<div class="grid">{{CARDS}}</div>
<p class="sub">Tool calls by tool: {{BYTOOL}}</p>
<h2 style="font-size:17px">Flagged events (most recent first)</h2>
<table><tr><th>Time (UTC)</th><th>Question</th><th>What the controls caught</th></tr>{{ROWS}}</table>
</body></html>"""
