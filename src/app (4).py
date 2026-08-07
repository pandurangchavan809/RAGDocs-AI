"""
Chatbot UI for the RAG system

Save as  app.py   and run from the PROJECT ROOT:  python app.py
    
Then open  http://127.0.0.1:5000  in your browser.

Importing rag loads the generation model + wires up retrieval ONCE at startup;
every message reuses them. No internet, no CDN, no web fonts -- all CSS/JS inline.

Requires: flask   (pip install flask)
"""

from flask import Flask, request, jsonify, Response, g
from config import settings
from src.rag import answer_ex  # importing this loads the model ONCE
from src.session_report import SessionReport
from src.session_memory import SessionMemoryStore
from src.acronym_db import AcronymDB
from src.acronym_resolver import AcronymResolver
from src.hitl_acronym_flow import hitl_flow
from src.feedback import add_feedback                                       # NEW: like/dislike persistence
from src.feedback_report import render_html as render_feedback_report_html  # NEW: feedback HTML report
import logging
import os
import uuid

# Without this, llm_client.py's "task=X: answered by route 'Y'" logs are
# silently dropped -- the root logger defaults to WARNING, so INFO-level
# logs (which is everything telling you which model actually answered)
# never reach the terminal.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

report = SessionReport()                  # one session per server process
app = Flask(__name__)

# In-memory session cache (cleared when the app restarts)
_session_store = SessionMemoryStore(ttl_seconds=1800)

SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@app.before_request
def _ensure_session_id():
    """Reads the session cookie if present; otherwise generates one and
    stashes it on `g` so `_persist_session_cookie` can set it on the way
    out. This REPLACES the old _get_or_create_session_id() helper, which
    generated an id but never actually called set_cookie() -- meaning
    every single request got a brand-new random session, and
    session_memory.py's "remember the last 4 turns" feature has likely
    never once fired in real use."""
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if sid:
        g.session_id = sid
        g.new_session_id = None
    else:
        g.session_id = uuid.uuid4().hex
        g.new_session_id = g.session_id

    # Opportunistic housekeeping -- no background scheduler in this
    # single-process app, so pending HITL tokens are swept here instead.
    # HitlAcronymFlow.assume_best_if_timeout() existed but was never
    # called from anywhere before this.
    try:
        for token in list(getattr(hitl_flow, "_pending", {}).keys()):
            hitl_flow.assume_best_if_timeout(token)
    except Exception:
        logger.exception("HITL timeout sweep failed")


@app.after_request
def _persist_session_cookie(response):
    if getattr(g, "new_session_id", None):
        response.set_cookie(
            SESSION_COOKIE_NAME,
            g.new_session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )
    return response


UI_VERSION = "2.2"
try:                                    # Flask 2.3+ removed flask.__version__
    from importlib.metadata import version as _pkg_version
    FLASK_VERSION = _pkg_version("flask")
except Exception:
    FLASK_VERSION = "?"

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Documentation Assistant</title>
<style>
  :root{
    --bg:#f6f7f9; --surface:#ffffff; --ink:#15161a; --muted:#6b7280;
    --border:#e7e8ec; --accent:#4f46e5; --accent2:#6d5bd0; --accent-soft:#eef0ff;
    --accent-bd:#dfe2ff; --cite-bg:#e3f3f6; --cite-ink:#0e6b78;
  }
  *{box-sizing:border-box;}
  html,body{height:100%;}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-size:15px; line-height:1.55; display:flex; flex-direction:column; height:100vh;
  }

  /* ---- header ---- */
  header{
    background:var(--surface); border-bottom:1px solid var(--border);
    padding:12px 20px; display:flex; align-items:center; gap:12px;
    box-shadow:0 1px 0 rgba(15,22,42,.02);
  }
  .logo{
    width:34px; height:34px; border-radius:10px; flex:none;
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 4px 12px rgba(79,70,229,.28);
  }
  .htext{display:flex; flex-direction:column; line-height:1.2;}
  .htext .t{font-weight:650; font-size:15px; letter-spacing:-.01em;}
  .htext .s{font-size:11.5px; color:var(--muted);}
  .status{
    margin-left:auto; display:flex; align-items:center; gap:7px;
    font-size:12px; color:var(--muted);
    background:#f1f5f0; border:1px solid #e2ece0; padding:5px 11px; border-radius:20px;
  }
  .dot{width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 0 3px rgba(34,197,94,.16);}
  .savebtn{
    display:flex; align-items:center; gap:6px; font-size:12px; font-weight:600;
    color:var(--accent); background:var(--accent-soft); border:1px solid var(--accent-bd);
    padding:6px 12px; border-radius:9px; cursor:pointer; text-decoration:none;
    transition:background .15s, transform .1s;
  }
  .savebtn:hover{background:#e6e9ff; transform:translateY(-1px);}
  .savebtn:active{transform:translateY(0);}

  /* ---- messages ---- */
  #scroll{flex:1; overflow-y:auto; padding:24px 20px 8px; scroll-behavior:smooth;}
  .wrap{max-width:780px; margin:0 auto;}
  .row{display:flex; gap:12px; margin:18px 0; align-items:flex-start; animation:rise .28s ease both;}
  .row.user{flex-direction:row-reverse;}
  @keyframes rise{from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:none;}}
  .av{
    width:30px; height:30px; border-radius:9px; flex:none; margin-top:2px;
    display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600;
  }
  .bot .av{background:linear-gradient(135deg,var(--accent),var(--accent2));}
  .user .av{background:#e9eaee; color:#4b5563;}
  .bubble{
    max-width:78%; padding:12px 15px; border-radius:14px;
    white-space:normal; word-wrap:break-word; overflow-wrap:anywhere;
  }
  .bot .bubble{
    background:var(--surface); border:1px solid var(--border);
    border-top-left-radius:5px; box-shadow:0 2px 8px rgba(15,22,42,.04);
  }
  .user .bubble{
    background:var(--accent-soft); border:1px solid var(--accent-bd);
    border-top-right-radius:5px; color:#23223a;
  }
  .bubble code{
    font-family:ui-monospace,Consolas,monospace; font-size:.86em;
    background:#f1f1f4; padding:1px 5px; border-radius:5px;
  }
  .bubble .cite{
    display:inline-block; font-family:ui-monospace,Consolas,monospace; font-size:.78em;
    background:var(--cite-bg); color:var(--cite-ink); padding:1px 7px; border-radius:6px;
    margin:1px 2px; vertical-align:baseline;
  }

  /* ---- answer tables (NEW) ---- */
  .ans-table-wrap{overflow-x:auto; margin:10px 0; border-radius:10px; border:1px solid var(--border);}
  .ans-table{border-collapse:collapse; width:100%; font-size:13px; line-height:1.4;}
  .ans-table th, .ans-table td{
    border-bottom:1px solid var(--border); border-right:1px solid var(--border);
    padding:7px 12px; text-align:left; vertical-align:top; white-space:normal;
  }
  .ans-table th:last-child, .ans-table td:last-child{border-right:none;}
  .ans-table tr:last-child td{border-bottom:none;}
  .ans-table thead th{
    background:#f8fafc; font-weight:650; color:#334155;
    font-size:11.5px; text-transform:uppercase; letter-spacing:.03em;
  }
  .ans-table tbody tr:nth-child(even) td{background:#fbfbfc;}
  .ans-table td code{font-size:.92em;}

  /* ---- sources panel ---- */
  .src{margin-top:11px; border-top:1px dashed var(--border); padding-top:9px;}
  .src>summary{
    cursor:pointer; list-style:none; font-size:12px; font-weight:600; color:var(--muted);
    display:flex; align-items:center; gap:6px; user-select:none;
  }
  .src>summary::-webkit-details-marker{display:none;}
  .src>summary .chev{transition:transform .15s; font-size:10px;}
  .src[open]>summary .chev{transform:rotate(90deg);}
  .srcitem{border:1px solid var(--border); border-radius:10px; margin-top:8px; overflow:hidden; background:#fbfbfc;}
  .srchead{display:flex; align-items:center; gap:8px; padding:7px 11px; flex-wrap:wrap; font-size:11px; color:var(--muted); border-bottom:1px solid var(--border);}
  .srchead .rk{font-weight:700; color:var(--accent);}
  .srchead .sc{font-family:ui-monospace,Consolas,monospace; background:var(--accent-soft); color:var(--accent); padding:1px 7px; border-radius:5px; font-weight:600;}
  .srchead .pg{white-space:nowrap;}
  .srchead .dc{margin-left:auto; color:#9aa0ab; font-size:10px; text-align:right; overflow-wrap:anywhere;}
  .bdg{font-size:10px; padding:1px 6px; border-radius:4px; font-weight:600; white-space:nowrap;}
  .b-text{background:#e6f1fb; color:#185fa5;} .b-table{background:#eaf3de; color:#3b6d11;} .b-row{background:#e4f4f6; color:#0e6b78;}
  .srctext{white-space:pre-wrap; word-break:break-word; font-family:ui-monospace,Consolas,monospace; font-size:10.5px; color:#374151; padding:9px 11px; margin:0; max-height:190px; overflow:auto; line-height:1.55;}

  /* ---- feedback buttons (NEW) ---- */
  .fbrow{display:flex; gap:8px; margin-top:10px;}
  .fbbtn{
    border:1px solid var(--border); background:#fff; border-radius:8px;
    padding:4px 10px; font-size:14px; cursor:pointer; line-height:1;
  }
  .fbbtn:hover:not(:disabled){border-color:var(--accent-bd);}
  .fbbtn.like.active{background:#eafaf0; border-color:#1a8a4a;}
  .fbbtn.dislike.active{background:#fdecea; border-color:#c0392b;}
  .fbbtn:disabled{cursor:default; opacity:.85;}

  /* typing dots */
  .typing{display:flex; gap:5px; padding:4px 2px;}
  .typing i{width:7px; height:7px; border-radius:50%; background:#c4c7d0; display:inline-block; animation:bounce 1.2s infinite ease-in-out;}
  .typing i:nth-child(2){animation-delay:.18s;} .typing i:nth-child(3){animation-delay:.36s;}
  @keyframes bounce{0%,80%,100%{transform:translateY(0); opacity:.5;} 40%{transform:translateY(-5px); opacity:1;}}

  /* ---- empty state ---- */
  #empty{max-width:640px; margin:8vh auto 0; text-align:center; padding:0 16px;}
  #empty .badge{
    width:54px; height:54px; border-radius:16px; margin:0 auto 18px;
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 10px 26px rgba(79,70,229,.28);
  }
  #empty h1{font-size:22px; margin:0 0 6px; letter-spacing:-.02em;}
  #empty p{color:var(--muted); margin:0 0 22px; font-size:14px;}
  .chips{display:flex; flex-wrap:wrap; gap:9px; justify-content:center;}
  .chip{
    background:var(--surface); border:1px solid var(--border); border-radius:11px;
    padding:10px 14px; font-size:13px; color:#374151; cursor:pointer; text-align:left;
    max-width:300px; transition:border-color .15s, transform .15s, box-shadow .15s;
  }
  .chip:hover{border-color:var(--accent-bd); box-shadow:0 4px 14px rgba(79,70,229,.08); transform:translateY(-1px);}

  /* ---- composer ---- */
  footer{padding:12px 20px 16px; background:linear-gradient(to top,var(--bg) 70%,transparent);}
  .composer{max-width:780px; margin:0 auto;}
  .field{
    display:flex; align-items:flex-end; gap:8px; background:var(--surface);
    border:1px solid var(--border); border-radius:16px; padding:8px 8px 8px 16px;
    box-shadow:0 2px 10px rgba(15,22,42,.05); transition:border-color .15s, box-shadow .15s;
  }
  .field:focus-within{border-color:var(--accent-bd); box-shadow:0 4px 18px rgba(79,70,229,.12);}
  #q{
    flex:1; border:none; outline:none; resize:none; background:transparent;
    font:inherit; color:var(--ink); line-height:1.5; max-height:160px; padding:6px 0;
  }
  #send{
    flex:none; width:38px; height:38px; border:none; border-radius:11px; cursor:pointer;
    background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff;
    display:flex; align-items:center; justify-content:center; transition:opacity .15s, transform .1s;
  }
  #send:hover:not(:disabled){transform:translateY(-1px);}
  #send:disabled{background:#c8cad2; cursor:default;}
  .hint{max-width:780px; margin:8px auto 0; font-size:11px; color:var(--muted); text-align:center;}

  /* ---- model picker (NEW) ---- */
  .modelpick{position:relative; flex:none;}
  .modelbtn{
    display:flex; align-items:center; gap:4px; font-size:11.5px; font-weight:600;
    color:var(--muted); background:transparent; border:1px solid var(--border);
    padding:6px 9px; border-radius:9px; cursor:pointer; white-space:nowrap;
    transition:border-color .15s, color .15s;
  }
  .modelbtn:hover{border-color:var(--accent-bd); color:var(--accent);}
  .modelmenu{
    position:absolute; bottom:calc(100% + 6px); right:0; min-width:130px;
    background:var(--surface); border:1px solid var(--border); border-radius:10px;
    box-shadow:0 8px 24px rgba(15,22,42,.12); overflow:hidden; z-index:10;
  }
  .modelmenu button{
    display:block; width:100%; text-align:left; padding:8px 12px; font-size:12.5px;
    background:none; border:none; cursor:pointer; color:var(--ink);
  }
  .modelmenu button:hover{background:var(--accent-soft); color:var(--accent);}
  .modelmenu button.active{color:var(--accent); font-weight:600;}
</style>
</head>
<body>
  <header>
    <div class="logo">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>
      </svg>
    </div>
    <div class="htext">
      <span class="t">Documentation Assistant</span>
      <span class="s">Local RAG &middot; BGE-M3 + reranker &middot; Qdrant &middot; UI v__UI_VERSION__ &middot; Flask __FLASK_VERSION__</span>
    </div>
    <div class="status"><span class="dot"></span>Running locally</div>
    <a class="savebtn" href="/save_report" download title="Download an HTML report of this session">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
      Save report
    </a>
    <a class="savebtn" href="/save_feedback_report" download title="Download the like/dislike feedback report">
      Feedback report
    </a>
  </header>

  <div id="scroll">
    <div id="empty">
      <div class="badge">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <h1>Ask anything about your documents</h1>
      <p>Answers are grounded only in the indexed PDFs, and every answer shows the source chunks it used.</p>
      
    </div>
    <div class="wrap" id="wrap"></div>
  </div>

  <footer>
    <div class="composer">
      <div class="field">
        <textarea id="q" rows="1" placeholder="Ask a question about the documents..." autocomplete="off"></textarea>
        <div class="modelpick" id="modelPick">
          <button type="button" id="modelBtn" class="modelbtn" title="Model used for the final answer only">
            <span id="modelLabel">__DEFAULT_MODEL_LABEL__</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          </button>
          <div id="modelMenu" class="modelmenu" style="display:none;"></div>
        </div>
        <button id="send" title="Send">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="hint">Enter to send &middot; Shift+Enter for a new line &middot; answers cite their source page</div>
  </footer>

<script>
  const scroll = document.getElementById('scroll');
  const wrap   = document.getElementById('wrap');
  const empty  = document.getElementById('empty');
  const input  = document.getElementById('q');
  const send   = document.getElementById('send');

  const SPARK = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/></svg>';
  const BDG = {text:['b-text','text'], table_full:['b-table','table'], table_row:['b-row','table row']};

  const SEND_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  const STOP_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2" fill="currentColor"/></svg>';

  let abortController = null;
  let isGenerating = false;

  // ---- model picker (NEW): affects the final-answer generation call
  // only -- the sufficiency-eval calls always use their own configured
  // fast/cheap chain regardless of this choice.
  const MODEL_OPTIONS = __MODEL_OPTIONS_JSON__;
  let selectedModel = MODEL_OPTIONS[0] || null;

  function modelLabel(route){
    return route.replace(/^LLM_/i, '').split('_').map(function(w){
      return w.charAt(0) + w.slice(1).toLowerCase();
    }).join(' ');
  }

  function renderModelMenu(){
    const menu = document.getElementById('modelMenu');
    menu.innerHTML = MODEL_OPTIONS.map(function(route){
      const cls = route === selectedModel ? 'active' : '';
      return '<button type="button" class="' + cls + '" data-route="' + esc(route) + '">' + esc(modelLabel(route)) + '</button>';
    }).join('');
    menu.querySelectorAll('button').forEach(function(btn){
      btn.addEventListener('click', function(){
        selectedModel = btn.getAttribute('data-route');
        document.getElementById('modelLabel').textContent = modelLabel(selectedModel);
        menu.style.display = 'none';
      });
    });
  }

  (function initModelPicker(){
    if (!MODEL_OPTIONS.length) { document.getElementById('modelPick').style.display = 'none'; return; }
    document.getElementById('modelLabel').textContent = modelLabel(selectedModel);
    const btn = document.getElementById('modelBtn');
    const menu = document.getElementById('modelMenu');
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      if (menu.style.display === 'none') { renderModelMenu(); menu.style.display = 'block'; }
      else { menu.style.display = 'none'; }
    });
    document.addEventListener('click', function(){ menu.style.display = 'none'; });
  })();

  function esc(t){ return String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function escCell(t){ return esc(t).trim(); }

  function isTableSeparatorRow(line){
    const trimmed = (line || '').trim();
    if (!trimmed.includes('|') && !trimmed.includes('-')) return false;
    const cells = trimmed.replace(/^\||\|$/g, '').split('|');
    if (!cells.length) return false;
    return cells.every(function(c){ return /^:?-{2,}:?$/.test(c.trim()); });
  }

  function parseTableRow(line){
    let l = (line || '').trim();
    if (l.startsWith('|')) l = l.slice(1);
    if (l.endsWith('|')) l = l.slice(0, -1);
    return l.split('|').map(function(c){ return c.trim(); });
  }

  function inlineFmt(raw){
    let t = esc(raw);
    t = t.replace(/\[[^\]]+\]/g, function (m) {
      return /source|doc|p\.|page/i.test(m) ? '<span class="cite">' + m + '</span>' : m;
    });
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return t;
  }

  function renderTable(lines){
    const header = parseTableRow(lines[0]);
    const rows = lines.slice(2).map(parseTableRow);
    let html = '<div class="ans-table-wrap"><table class="ans-table"><thead><tr>';
    html += header.map(function(h){ return '<th>' + inlineFmt(h) + '</th>'; }).join('');
    html += '</tr></thead><tbody>';
    for (const row of rows) {
      html += '<tr>' + row.map(function(c){ return '<td>' + inlineFmt(c) + '</td>'; }).join('') + '</tr>';
    }
    html += '</tbody></table></div>';
    return html;
  }

  function fmt(raw) {
    const lines = String(raw == null ? '' : raw).split('\n');
    let html = '';
    let paragraphLines = [];
    let i = 0;

    function flushParagraph(){
      if (paragraphLines.length) {
        html += inlineFmt(paragraphLines.join('\n')).replace(/\n/g, '<br>') + '<br>';
        paragraphLines = [];
      }
    }

    while (i < lines.length) {
      const line = lines[i];
      const next = lines[i + 1];
      // A markdown table: a pipe-row immediately followed by a
      // |---|---| separator row.
      if (line.trim().includes('|') && next !== undefined && isTableSeparatorRow(next)) {
        flushParagraph();
        const tableLines = [line, next];
        let j = i + 2;
        while (j < lines.length && lines[j].trim().includes('|')) {
          tableLines.push(lines[j]);
          j++;
        }
        html += renderTable(tableLines);
        i = j;
        continue;
      }
      paragraphLines.push(line);
      i++;
    }
    flushParagraph();
    return html;
  }

  function setGenerating(state) {
    isGenerating = state;
    if (state) {
      send.innerHTML = STOP_ICON;
      send.title = "Stop generation";
      send.disabled = false;
      input.disabled = true;
    } else {
      send.innerHTML = SEND_ICON;
      send.title = "Send";
      send.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  function handleSendClick() {
    if (isGenerating) {
      if (abortController) {
        abortController.abort();
      }
    } else {
      ask();
    }
  }

  function sourcesHtml(sources){
    if (!sources || !sources.length) return '';
    const items = sources.map(function(s){
      const b = BDG[s.kind] || ['b-text', (s.kind||'?')];
      return '<div class="srcitem"><div class="srchead">'
        + '<span class="rk">#'+esc(s.rank)+'</span>'
        + '<span class="sc">'+esc(s.score)+'</span>'
        + '<span class="bdg '+b[0]+'">'+esc(b[1])+'</span>'
        + '<span class="pg">'+esc(s.pages)+'</span>'
        + '<span class="dc">'+esc(s.doc_id)+'</span>'
        + '</div><pre class="srctext">'+esc(s.text)+'</pre></div>';
    }).join('');
    return '<details class="src"><summary><span class="chev">&#9656;</span>Sources ('
      + sources.length + ')</summary>' + items + '</details>';
  }

  // ---- feedback (NEW) ----
  function feedbackHtml(){
    return '<div class="fbrow">'
      + '<button type="button" class="fbbtn like" title="Good answer">&#128077;</button>'
      + '<button type="button" class="fbbtn dislike" title="Needs improvement">&#128078;</button>'
      + '</div>';
  }

  function wireFeedback(root, question, answerText, sources){
    const likeBtn = root.querySelector('.fbbtn.like');
    const dislikeBtn = root.querySelector('.fbbtn.dislike');
    if (!likeBtn || !dislikeBtn) return;
    function send(liked){
      likeBtn.disabled = true; dislikeBtn.disabled = true;
      likeBtn.classList.toggle('active', liked === true);
      dislikeBtn.classList.toggle('active', liked === false);
      fetch('/feedback', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({question: question, answer: answerText, sources: sources || [], liked: liked})
      }).catch(function(){});
    }
    likeBtn.addEventListener('click', function(){ send(true); });
    dislikeBtn.addEventListener('click', function(){ send(false); });
  }

  function addRow(role, html){
    empty.style.display = 'none';
    const row = document.createElement('div');
    row.className = 'row ' + role;
    const av = document.createElement('div');
    av.className = 'av';
    av.innerHTML = role === 'bot' ? SPARK : 'You';
    const bub = document.createElement('div');
    bub.className = 'bubble';
    bub.innerHTML = html;
    row.appendChild(av); row.appendChild(bub);
    wrap.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
    return bub;
  }

  function autosize(){
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  }

  function useChip(el){
    input.value = el.textContent.trim();
    autosize();
    ask();
  }

  function hitlButtons(hitl){
    const acronym = hitl.acronym || '';
    const status = hitl.status || '';
    const policy = hitl.policy || '';
    
    let html = '<div style="margin-top:4px;" class="hitl-block" data-token="'+esc(hitl.pending_token)+'" data-acronym="'+esc(acronym)+'">'
      + '<div style="font-weight:700; margin-bottom:6px;">Resolve Acronym: <code>'+esc(acronym)+'</code></div>'
      + '<div style="font-size:11px; color:var(--muted); margin-bottom:10px;">Policy: '+esc(policy)+'</div>';

    if (status === 'needs_user_choice') {
      const options = (hitl.top2 || []).map(function(item, idx){
        const full = item.meaning && item.meaning.fullForm ? item.meaning.fullForm : '';
        const desc = item.meaning && item.meaning.description ? item.meaning.description : '';
        const label = (idx+1) + '. ' + full + (desc ? (' — ' + desc) : '');
        return '<button type="button" class="chip" style="display:block; width:100%; margin:8px 0; text-align:left;" data-idx="'+idx+'">'+esc(label)+'</button>';
      }).join('');
      
      html += options
        + '<div style="font-size:12.5px; font-weight:bold; color:var(--accent); margin:10px 0;" class="countdown-timer">Auto-selecting Option #1 in __HITL_COUNTDOWN_SECONDS__ seconds...</div>'
        + '<button type="button" class="savebtn custom-toggle-btn" style="margin-top:8px;">Provide custom definition instead</button>';
    }

    const formStyle = status === 'needs_user_provide' ? 'display:block;' : 'display:none;';
    html += '<div class="custom-acronym-form" style="margin-top:14px; border-top:1px dashed var(--border); padding-top:12px; ' + formStyle + '">'
      + '<div style="font-weight:600; font-size:12.5px; margin-bottom:8px;">Provide custom meaning:</div>'
      + '<input type="text" class="custom-fullform" placeholder="Full Form (e.g. Snapdragon Automotive)" style="width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:8px; margin-bottom:8px; outline:none; font:inherit; font-size:13px; background:#fff; color:var(--ink);">'
      + '<input type="text" class="custom-description" placeholder="Description (Optional)" style="width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:8px; margin-bottom:10px; outline:none; font:inherit; font-size:13px; background:#fff; color:var(--ink);">'
      + '<button type="button" class="savebtn submit-custom-btn">Submit Custom Meaning</button>'
      + '</div>';

    html += '</div>';
    return html;
  }

  async function resolveHitl(pending_token, choice_index){
    const payload = { pending_token: pending_token, choice_index: choice_index };
    const res = await fetch('/acronym_feedback', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error("Server returned " + res.status + ": " + txt);
    }
    const data = await res.json();
    if (!data || data.status !== 'resolved'){
      throw new Error(data && data.error ? data.error : 'HITL resolution failed');
    }
    return data;
  }

  function bindHitlEvents(bub, hitl, originalQuery) {
    const token = hitl.pending_token;
    const acronym = hitl.acronym;
    const status = hitl.status;
    
    let interval = null;
    let timerEl = bub.querySelector('.countdown-timer');
    
    if (status === 'needs_user_choice') {
      let secondsLeft = __HITL_COUNTDOWN_SECONDS__;
      interval = setInterval(async function(){
        secondsLeft--;
        if (timerEl) {
          timerEl.textContent = 'Auto-selecting Option #1 in ' + secondsLeft + ' seconds...';
        }
        if (secondsLeft <= 0) {
          clearInterval(interval);
          bub.innerHTML = '<div class="typing"><i></i><i></i><i></i></div>';
          try {
            const resolved = await resolveHitl(token, 0);
            await finalizeHitlResolution(acronym, resolved, originalQuery, bub);
          } catch(e) {
            bub.innerHTML = 'Auto-resolution failed: ' + esc(String(e));
            setGenerating(false);
          }
        }
      }, 1000);
    }

    const btns = bub.querySelectorAll('button[data-idx]');
    btns.forEach(function(btn){
      btn.addEventListener('click', async function(){
        if (interval) clearInterval(interval);
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        bub.innerHTML = '<div class="typing"><i></i><i></i><i></i></div>';
        try{
          const resolved = await resolveHitl(token, idx);
          await finalizeHitlResolution(acronym, resolved, originalQuery, bub);
        } catch (e){
          bub.innerHTML = 'Something went wrong saving HITL feedback: ' + esc(String(e));
          setGenerating(false);
        }
      });
    });

    const toggleBtn = bub.querySelector('.custom-toggle-btn');
    const formEl = bub.querySelector('.custom-acronym-form');
    if (toggleBtn && formEl) {
      toggleBtn.addEventListener('click', function(){
        if (interval) clearInterval(interval);
        if (timerEl) timerEl.remove();
        toggleBtn.remove();
        formEl.style.display = 'block';
      });
    }

    const submitBtn = bub.querySelector('.submit-custom-btn');
    const fullInput = bub.querySelector('.custom-fullform');
    const descInput = bub.querySelector('.custom-description');
    if (submitBtn) {
      submitBtn.addEventListener('click', async function(){
        const ffVal = fullInput.value.trim();
        const descVal = descInput.value.trim();
        if (!ffVal) {
          alert('Please provide a Full Form.');
          return;
        }
        if (interval) clearInterval(interval);
        bub.innerHTML = '<div class="typing"><i></i><i></i><i></i></div>';
        try {
          const payload = { pending_token: token, fullForm: ffVal, description: descVal };
          const feedRes = await fetch('/acronym_feedback', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(payload)
          });
          if (!feedRes.ok) {
            const txt = await feedRes.text();
            throw new Error("Server returned " + feedRes.status + ": " + txt);
          }
          const resolved = await feedRes.json();
          if (resolved.status !== 'resolved') throw new Error(resolved.error || 'Failed');
          await finalizeHitlResolution(acronym, resolved, originalQuery, bub);
        } catch(e) {
          bub.innerHTML = 'Failed submitting custom acronym: ' + esc(String(e));
          setGenerating(false);
        }
      });
    }
  }

  async function readChatStream(res, bub, originalQuery) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    
    bub.innerHTML = '<div class="agent-status-box" style="font-size:12.5px; color:var(--muted); margin-bottom:12px; background:#f8fafc; border:1px solid #e2e8f0; padding:10px 14px; border-radius:10px; display:flex; flex-direction:column; gap:6px; animation:rise 0.2s ease both;">'
                  + '<div style="font-weight:700; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:#64748b; margin-bottom:4px; display:flex; align-items:center; gap:6px;">'
                  + '<span style="width:6px; height:6px; border-radius:50%; background:var(--accent); display:inline-block; animation: bounce 1s infinite;"></span>Agent Reasoning Steps'
                  + '</div>'
                  + '<div class="agent-steps-list" style="display:flex; flex-direction:column; gap:5px;"></div>'
                  + '</div>'
                  + '<div class="typing" style="margin-top:8px;"><i></i><i></i><i></i></div>';
    
    const stepsList = bub.querySelector('.agent-steps-list');
    const statusBox = bub.querySelector('.agent-status-box');
    const typingIndicator = bub.querySelector('.typing');
    
    function addStep(msg) {
      const existing = Array.from(stepsList.children).find(el => el.textContent.includes(msg));
      if (existing) return;
      
      const step = document.createElement('div');
      step.style.cssText = 'display:flex; align-items:center; gap:8px; font-size:12.5px; line-height:1.4; animation:rise 0.25s ease both;';
      step.innerHTML = '<svg class="step-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="flex:none; display:none;"><polyline points="20 6 9 17 4 12"/></svg>'
                     + '<span class="step-dot" style="width:6px; height:6px; border-radius:50%; background:#94a3b8; flex:none;"></span>'
                     + '<span style="color:#475569;">' + esc(msg) + '</span>';
      
      Array.from(stepsList.children).forEach(el => {
        const dot = el.querySelector('.step-dot');
        const check = el.querySelector('.step-check');
        if (dot && dot.style.display !== 'none') {
          dot.style.display = 'none';
          check.style.display = 'inline';
          el.querySelector('span:last-child').style.color = '#64748b';
        }
      });
      
      stepsList.appendChild(step);
      scroll.scrollTop = scroll.scrollHeight;
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        
        for (const line of lines) {
          if (!line.trim()) continue;
          
          let data;
          try {
            data = JSON.parse(line);
          } catch(e) {
            console.error("JSON parse error: ", line);
            continue;
          }
          
          if (data.error) {
            throw new Error(data.error);
          }
          
          if (data.status) {
            addStep(data.status);
          } else if (data.acronym_hitl) {
            bub.innerHTML = hitlButtons(data.acronym_hitl);
            bindHitlEvents(bub, data.acronym_hitl, originalQuery);
            return;
          } else if (data.answer !== undefined) {
            Array.from(stepsList.children).forEach(el => {
              const dot = el.querySelector('.step-dot');
              const check = el.querySelector('.step-check');
              if (dot) dot.style.display = 'none';
              if (check) check.style.display = 'inline';
              el.querySelector('span:last-child').style.color = '#64748b';
            });
            
            const answerText = data.answer || '';
            const html = fmt(answerText) + sourcesHtml(data.sources) + feedbackHtml();

            if (typingIndicator) typingIndicator.remove();

            statusBox.style.padding = '6px 12px';
            statusBox.style.background = '#f1f5f9';
            statusBox.style.border = '1px solid #e2e8f0';
            statusBox.querySelector('div').innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-right:4px;"><polyline points="20 6 9 17 4 12"/></svg><span style="vertical-align:middle;">Agent Search Completed</span>';
            stepsList.style.display = 'none';

            const contentDiv = document.createElement('div');
            contentDiv.innerHTML = html;
            bub.appendChild(contentDiv);
            wireFeedback(contentDiv, originalQuery, answerText, data.sources || []);
          }
        }
      }
    } catch(err) {
      if (err.name === 'AbortError') {
        throw err;
      }
      bub.innerHTML = '<div style="color:#ef4444; font-weight:600; padding:10px; background:#fef2f2; border:1px solid #fca5a5; border-radius:8px;">Error: ' + esc(String(err.message || err)) + '</div>';
    }
  }

  async function finalizeHitlResolution(acronym, resolved, originalQuery, oldBub){
    // BUGFIX: oldBub is the acronym-choice bubble that was just set to a typing
    // indicator by the caller. We create two brand-new rows below and never touch
    // oldBub again, so without this it's left behind forever showing "...".
    // Removing its whole row (avatar + bubble) here prevents that orphaned bubble.
    if (oldBub && oldBub.parentElement) {
      oldBub.parentElement.remove();
    }

    addRow('bot', '<div style="font-size:13.5px; color:#185fa5; background:#e6f1fb; padding:10px 14px; border-radius:8px; border:1px solid #bce0fd;">'
      + '<strong>Resolved acronym:</strong> ' + esc(resolved.expanded)
      + '</div>');
    
    const finalBub = addRow('bot', '<div class="typing"><i></i><i></i><i></i></div>');
    
    abortController = new AbortController();
    setGenerating(true);
    
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          message: originalQuery,
          skip_acronym: true,
          resolved_expansion: resolved.expanded,
          model: selectedModel
        }),
        signal: abortController.signal
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error("Server returned " + res.status + ": " + txt);
      }
      await readChatStream(res, finalBub, originalQuery);
    } catch(e) {
      if (e.name === 'AbortError') {
        const typing = finalBub.querySelector('.typing');
        if (typing) typing.remove();
        const statusBox = finalBub.querySelector('.agent-status-box');
        if (statusBox) {
          statusBox.style.background = '#f1f5f9';
          statusBox.style.border = '1px solid #e2e8f0';
          statusBox.querySelector('div').innerHTML = '<span style="vertical-align:middle; color:var(--muted); font-style:italic;">[Generation stopped by user]</span>';
          finalBub.querySelector('.agent-steps-list').style.display = 'none';
        } else {
          finalBub.innerHTML = '<div style="color:var(--muted); font-style:italic;">[Generation stopped by user]</div>';
        }
      } else {
        finalBub.innerHTML = '<div style="color:#ef4444; font-weight:600; padding:10px; background:#fef2f2; border:1px solid #fca5a5; border-radius:8px;">Error running RAG: ' + esc(String(e)) + '</div>';
      }
    } finally {
      setGenerating(false);
      abortController = null;
    }
  }

  async function ask(){
    const q = input.value.trim();
    if (!q) return;
    
    const oldSugs = document.getElementById('suggestions-container');
    if (oldSugs) oldSugs.remove();
    
    addRow('user', esc(q));
    input.value = ''; autosize();
    
    abortController = new AbortController();
    setGenerating(true);
    
    const bub = addRow('bot', '<div class="typing"><i></i><i></i><i></i></div>');
    try {
      const res  = await fetch('/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({message:q, model: selectedModel}),
        signal: abortController.signal
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error("Server returned " + res.status + ": " + txt);
      }
      await readChatStream(res, bub, q);
    } catch (e) {
      if (e.name === 'AbortError') {
        const typing = bub.querySelector('.typing');
        if (typing) typing.remove();
        const statusBox = bub.querySelector('.agent-status-box');
        if (statusBox) {
          statusBox.style.background = '#f1f5f9';
          statusBox.style.border = '1px solid #e2e8f0';
          statusBox.querySelector('div').innerHTML = '<span style="vertical-align:middle; color:var(--muted); font-style:italic;">[Generation stopped by user]</span>';
          bub.querySelector('.agent-steps-list').style.display = 'none';
        } else {
          bub.innerHTML = '<div style="color:var(--muted); font-style:italic;">[Generation stopped by user]</div>';
        }
      } else {
        bub.innerHTML = '<div style="color:#ef4444; font-weight:600; padding:10px; background:#fef2f2; border:1px solid #fca5a5; border-radius:8px;">Something went wrong reaching the server: ' + esc(String(e)) + '</div>';
      }
    } finally {
      setGenerating(false);
      abortController = null;
    }
  }

  send.addEventListener('click', handleSendClick);
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', function(e){
    if (e.key === 'Enter' && !e.shiftKey){ 
      e.preventDefault(); 
      if (!isGenerating) ask(); 
    }
  });
  input.focus();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    model_routes = settings.rag_answer_route_names()
    default_label = model_routes[0].replace("LLM_", "").title() if model_routes else "Model"
    html = (PAGE.replace("__UI_VERSION__", UI_VERSION)
                .replace("__FLASK_VERSION__", FLASK_VERSION)
                .replace("__HITL_COUNTDOWN_SECONDS__", str(settings.hitl_countdown_seconds))
                .replace("__MODEL_OPTIONS_JSON__", __import__("json").dumps(model_routes))
                .replace("__DEFAULT_MODEL_LABEL__", default_label))
    return Response(html, mimetype="text/html")


def _extract_exact_acronym_tokens(q: str, db: AcronymDB):
    # Exact match mode: token must equal an entry's acronym.
    # We still normalize by stripping punctuation around the token.
    import re

    tokens = re.findall(r"[A-Za-z0-9+\-]{2,}", q)
    acc_set = {str(e.get("acronym") or "").strip() for e in db.all()}
    found = []
    seen = set()
    for t in tokens:
        t2 = str(t).strip()
        if t2 in acc_set and t2 not in seen:
            found.append(t2)
            seen.add(t2)
    return found


@app.route("/resolve_acronym", methods=["POST"])
def resolve_acronym():
    data = request.get_json(silent=True) or {}
    msg = data.get("message") or ""
    context = data.get("context") or ""
    acronym = (data.get("acronym") or "").strip()

    if not acronym:
        return jsonify({"status": "error", "error": "missing acronym"}), 400

    acr_db = AcronymDB()
    resolver = AcronymResolver(acr_db)
    flow = hitl_flow

    res = resolver.resolve(acronym=acronym, context=context or msg)
    if res.get("status") == "auto_selected":
        meaning = res.get("selected", {}).get("meaning") or {}
        expanded = f"{acronym} = {meaning.get('fullForm','')}".strip()
        if meaning.get("description"):
            expanded += f" — {meaning.get('description','')}"
        return jsonify({"status": "resolved", "acronym": acronym, "expanded": expanded, "meaning": meaning})

    # For HITL statuses, create pending token
    pending = flow.create(
        acronym=acronym,
        context=context or msg,
        top2=res.get("top2") or [],
        status=("needs_user_choice" if res.get("status") == "needs_user_choice" else "needs_user_provide"),
    )

    return jsonify({
        "status": "needs_user",
        "acronym": acronym,
        "policy": res.get("policy"),
        "pending_token": pending.token,
        "top2": pending.top2,
    })


@app.route("/acronym_feedback", methods=["POST"])
def acronym_feedback():
    data = request.get_json(silent=True) or {}
    token = (data.get("pending_token") or "").strip()
    choice_index = data.get("choice_index")
    user_fullForm = (data.get("fullForm") or "").strip()
    user_description = (data.get("description") or "").strip()

    if not token:
        return jsonify({"status": "error", "error": "missing pending_token"}), 400

    # Use module-level singleton so pending tokens created in /chat can be resolved.
    flow = hitl_flow

    if choice_index is not None:
        resolved = flow.resolve_choice(token=token, choice_index=int(choice_index))
    else:
        if not user_fullForm:
            return jsonify({"status": "error", "error": "missing fullForm"}), 400
        resolved = flow.resolve_user_provided(token=token, fullForm=user_fullForm, description=user_description)
        # Upsert user custom acronym definition into database (acc.json)
        acr_db = AcronymDB()
        acr_db.upsert({
            "acronym": resolved["acronym"],
            "fullForm": user_fullForm,
            "description": user_description,
            "category": "User Provided"
        })

    meaning = resolved.get("meaning") or {}
    acronym = resolved.get("acronym") or ""
    expanded = f"{acronym} = {meaning.get('fullForm','')}".strip()
    if meaning.get("description"):
        expanded += f" — {meaning.get('description','')}"

    return jsonify({"status": "resolved", "expanded": expanded, "meaning": meaning})



@app.route("/chat", methods=["POST"])
def chat():
    from flask import Response, stream_with_context
    import json
    import traceback

    def generate_stream():
        try:
            data = request.get_json(silent=True) or {}
            q = (data.get("message") or "").strip()
            if not q:
                yield json.dumps({"answer": "", "sources": []}) + "\n"
                return

            mem = _session_store.get(g.session_id, create=True)
            assert mem is not None

            resolved_expansion = data.get("resolved_expansion", "")
            preferred_model = (data.get("model") or "").strip() or None

            history_context = mem.build_memory_text() if mem else None
            from src.agent import AgenticSearch
            agent = AgenticSearch()
            
            ans = ""
            srcs = []
            for step in agent.run_yield(q, history_context=history_context, resolved_expansion=resolved_expansion,
                                         preferred_model=preferred_model):
                if "status" in step:
                    yield json.dumps({"status": step["status"]}) + "\n"
                elif "acronym_hitl" in step:
                    yield json.dumps({"acronym_hitl": step["acronym_hitl"]}) + "\n"
                    return
                elif "answer" in step:
                    ans = step["answer"]
                    srcs = step["sources"]

            report.add_turn(q, ans, srcs)
            mem.remember(user_msg=q, assistant_msg=ans)
            yield json.dumps({"answer": ans, "sources": srcs}) + "\n"
            
        except Exception as e:
            traceback.print_exc()
            yield json.dumps({"error": str(e), "answer": f"ERROR: {str(e)}", "sources": []}) + "\n"

    return Response(stream_with_context(generate_stream()), content_type="application/x-ndjson")



@app.route("/save_report")
def save_report():
    return Response(
        report.render_html(),
        mimetype="text/html",
        headers={"Content-Disposition": "attachment; filename=session_report.html"},
    )


# ---- NEW: like/dislike feedback endpoints ----

@app.route("/feedback", methods=["POST"])
def feedback_route():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    answer_text = data.get("answer") or ""
    sources = data.get("sources") or []
    liked = data.get("liked")

    if not question:
        return jsonify({"status": "error", "error": "missing question"}), 400

    entry = add_feedback(question, answer_text, sources, liked)
    return jsonify({"status": "ok", "feedback": entry.get("feedback")})


@app.route("/save_feedback_report")
def save_feedback_report():
    return Response(
        render_feedback_report_html(),
        mimetype="text/html",
        headers={"Content-Disposition": "attachment; filename=feedback_report.html"},
    )


if __name__ == "__main__":
    print("UI ready -> open http://127.0.0.1:5000 in your browser")
    # threaded=False so GPU generations run one at a time (no overlap on the 8GB card)
    app.run(host="127.0.0.1", port=5000, threaded=False)
