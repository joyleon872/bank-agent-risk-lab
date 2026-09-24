"""
Web service for the Nordvik Bank assistant.

Endpoints:
  GET  /        simple chat page for demos
  GET  /health  status check (used later by Docker and Azure)
  POST /chat    {"question": "..."} -> {"answer": "...", "sources": [...]}
"""
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.bot import Bot

KB_DIR = os.getenv("KB_DIR", "data/kb")

app = FastAPI(title="Nordvik Bank Assistant", version="0.1.0")
bot = Bot(KB_DIR)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok", "kb_dir": KB_DIR, "chunks": len(bot.retriever.chunks)}


@app.post("/chat")
def chat(req: ChatRequest):
    return bot.answer(req.question)


@app.get("/", response_class=HTMLResponse)
def home():
    return CHAT_PAGE


CHAT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nordvik Bank Assistant</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1b1b1b}
  h1{font-size:22px;margin-bottom:4px} .sub{color:#666;margin-top:0;font-size:14px}
  #log{border:1px solid #ddd;border-radius:10px;padding:12px;min-height:300px;margin:16px 0;overflow-y:auto}
  .q{font-weight:600;margin-top:12px} .a{white-space:pre-wrap;margin:4px 0 4px}
  .src{font-size:12px;color:#777} form{display:flex;gap:8px}
  input{flex:1;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:15px}
  button{padding:10px 16px;border:0;border-radius:8px;background:#1f3a5f;color:#fff;font-size:15px;cursor:pointer}
</style></head><body>
<h1>Nordvik Bank Assistant</h1>
<p class="sub">Fictional bank for AI risk testing. Answers come only from retrieved policy documents.</p>
<div id="log"></div>
<form id="f"><input id="q" placeholder="Ask about fees, cards, loans..." autocomplete="off"><button>Send</button></form>
<script>
const log=document.getElementById('log'), q=document.getElementById('q');
function add(cls, text){const d=document.createElement('div');d.className=cls;d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
document.getElementById('f').onsubmit=async e=>{
  e.preventDefault(); const question=q.value.trim(); if(!question) return;
  add('q', question); q.value=''; const a=add('a','Thinking...');
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
    const data=await r.json(); a.textContent=data.answer || JSON.stringify(data);
    if(data.sources&&data.sources.length) add('src','Sources: '+[...new Set(data.sources.map(s=>s.source))].join(', '));
  }catch(err){a.textContent='Error: '+err;}
};
</script></body></html>"""
