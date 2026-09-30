"""
``datalens serve`` — the run's report plus a chat panel, on localhost only.

- Binds to 127.0.0.1; rejects requests whose Host isn't localhost (DNS-rebinding guard).
- Every API call needs the per-session token embedded in the served page, so
  other web pages can't drive the local server.
- Serves only the report and two API routes — never arbitrary files.
- The report file on disk is unchanged; the chat panel is injected when served.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from datalens.chat.engine import ChatSession, dumps
from datalens.chat.workspace import RunWorkspace

CHAT_UI = r"""
<style>
#dl-chat-btn { position:fixed; right:22px; bottom:22px; z-index:1000; border:0; border-radius:999px; padding:12px 18px;
  background:var(--accent-gradient); color:#fff; font:600 .95rem var(--font-sans); cursor:pointer; box-shadow:var(--shadow-md); }
#dl-chat { position:fixed; right:22px; bottom:78px; width:min(520px, calc(100vw - 32px)); height:min(680px, calc(100vh - 110px));
  z-index:1000; display:none; flex-direction:column; background:var(--bg-card); color:var(--text-primary);
  border:1px solid var(--border-secondary); border-radius:var(--radius-lg); box-shadow:var(--shadow-md); }
#dl-chat.open { display:flex; }
#dl-chat header { display:flex; align-items:center; gap:8px; padding:10px 14px; border-bottom:1px solid var(--border-primary); }
#dl-chat header b { flex:1; }
#dl-chat .msgs { flex:1; overflow:auto; padding:12px 14px; font-size:.88rem; line-height:1.55; }
#dl-chat .m { margin-bottom:14px; }
#dl-chat .m.user { text-align:right; }
#dl-chat .m.user .b { display:inline-block; background:var(--bg-tertiary); padding:6px 10px; border-radius:10px; }
#dl-chat .m.bot .b { background:var(--bg-secondary); border:1px solid var(--border-primary); padding:8px 10px; border-radius:10px; }
#dl-chat .m.bot table { border-collapse:collapse; margin:6px 0; font-size:.78rem; display:block; overflow-x:auto; }
#dl-chat .m.bot td, #dl-chat .m.bot th { border:1px solid var(--border-primary); padding:2px 6px; }
#dl-chat pre { background:var(--bg-primary); padding:6px 8px; border-radius:6px; white-space:pre-wrap; font-size:.75rem; }
#dl-chat .acts { margin-top:6px; display:flex; flex-wrap:wrap; gap:6px; }
#dl-chat form { display:flex; gap:8px; padding:10px 14px; border-top:1px solid var(--border-primary); }
#dl-chat textarea { flex:1; resize:none; height:46px; background:var(--bg-input); color:var(--text-primary);
  border:1px solid var(--border-primary); border-radius:8px; padding:6px 8px; font:inherit; }
#dl-chat .hint { color:var(--text-tertiary); font-size:.78rem; }
#dl-chat .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
</style>
<button id="dl-chat-btn" type="button" aria-controls="dl-chat">💬 Ask Datalens</button>
<section id="dl-chat" aria-label="Ask Datalens">
  <header><b>Ask Datalens</b><span class="hint" id="dl-chat-provider"></span>
    <button class="dl-btn" type="button" id="dl-chat-export">Export chat</button>
    <button class="dl-btn" type="button" id="dl-chat-close" aria-label="Close">✕</button></header>
  <div class="msgs" id="dl-chat-msgs">
    <div class="m bot"><div class="b">Ask anything about this run — I can read the findings and query a masked sample of the
      data with SQL. Every query I run is shown.<div class="chips" id="dl-chat-chips"></div></div></div>
  </div>
  <form id="dl-chat-form"><textarea id="dl-chat-q" placeholder="e.g. Which teams have the most orphaned bowler ids?"></textarea>
    <button class="dl-btn" type="submit">Send</button></form>
</section>
<script>
(function(){
  var cfg = window.DATALENS_CHAT || {}; var history = []; var transcript = [];
  var panel = document.getElementById('dl-chat'), msgs = document.getElementById('dl-chat-msgs');
  document.getElementById('dl-chat-btn').onclick = function(){ panel.classList.toggle('open'); document.getElementById('dl-chat-q').focus(); };
  document.getElementById('dl-chat-close').onclick = function(){ panel.classList.remove('open'); };
  document.getElementById('dl-chat-provider').textContent = cfg.provider ? '· ' + cfg.provider + (cfg.sql ? ' · SQL on sample' : ' · findings only') : '';
  ['What should I fix first, and why?', 'Explain the biggest drift finding with numbers', 'Show the 10 most frequent values of the field that drifted most']
    .forEach(function(q){ var b = document.createElement('button'); b.type = 'button'; b.className = 'dl-btn'; b.textContent = q;
      b.onclick = function(){ send(q); }; document.getElementById('dl-chat-chips').appendChild(b); });
  function esc(t){ var d = document.createElement('div'); d.textContent = t == null ? '' : String(t); return d.innerHTML; }
  function md(src){
    var blocks = String(src || '').split(/```/); var out = '';
    blocks.forEach(function(chunk, i){
      if (i % 2) { out += '<pre>' + esc(chunk.replace(/^\w*\n/, '')) + '</pre>'; return; }
      var lines = chunk.split('\n'), inList = false, table = [];
      function flushTable(){ if (!table.length) return; var rows = table.filter(function(r){ return !/^\s*\|?\s*-{2,}/.test(r); });
        out += '<table>' + rows.map(function(r, j){ var cells = r.replace(/^\s*\||\|\s*$/g, '').split('|');
          return '<tr>' + cells.map(function(c){ return (j ? '<td>' : '<th>') + inline(c.trim()) + (j ? '</td>' : '</th>'); }).join('') + '</tr>'; }).join('') + '</table>'; table = []; }
      lines.forEach(function(line){
        if (/^\s*\|.*\|\s*$/.test(line)) { table.push(line); return; } flushTable();
        var li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
        if (li) { if (!inList) { out += '<ul>'; inList = true; } out += '<li>' + inline(li[1]) + '</li>'; return; }
        if (inList) { out += '</ul>'; inList = false; }
        var h = line.match(/^#{1,4}\s+(.*)/); if (h) { out += '<p><b>' + inline(h[1]) + '</b></p>'; return; }
        if (line.trim()) out += '<p>' + inline(line) + '</p>';
      });
      flushTable(); if (inList) out += '</ul>';
    });
    return out;
  }
  function inline(t){ return esc(t).replace(/`([^`]+)`/g, '<code class="dl-inline">$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>'); }
  function tableHtml(t){ if (!t) return ''; return '<table><tr>' + t.columns.map(function(c){ return '<th>' + esc(c) + '</th>'; }).join('') + '</tr>' +
    t.rows.slice(0, 20).map(function(r){ return '<tr>' + r.map(function(v){ return '<td>' + esc(v) + '</td>'; }).join('') + '</tr>'; }).join('') + '</table>' +
    (t.rows.length > 20 ? '<div class="hint">' + t.rows.length + ' rows — download for all</div>' : ''); }
  function csv(t){ function c(v){ v = v == null ? '' : String(v); return '"' + v.replace(/"/g, '""') + '"'; }
    return [t.columns.map(c).join(',')].concat(t.rows.map(function(r){ return r.map(c).join(','); })).join('\n'); }
  function download(name, type, text){ var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type: type}));
    a.download = name; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 0); }
  function add(role, html){ var m = document.createElement('div'); m.className = 'm ' + role; m.innerHTML = '<div class="b">' + html + '</div>';
    msgs.appendChild(m); msgs.scrollTop = msgs.scrollHeight; return m; }
  function send(q){
    q = (q || '').trim(); if (!q) return; add('user', esc(q)); document.getElementById('dl-chat-q').value = '';
    var pending = add('bot', '<span class="hint">Thinking… (queries run on a masked sample)</span>');
    fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Datalens-Token': cfg.token},
      body: JSON.stringify({question: q, history: history})})
      .then(function(r){ return r.json(); })
      .then(function(res){
        var b = pending.querySelector('.b');
        if (!res.ok) { b.innerHTML = '<b>Error:</b> ' + esc(res.error || 'unknown'); return; }
        var steps = (res.steps || []).map(function(s){ return '<details><summary class="hint">SQL' + (s.why ? ' — ' + esc(s.why) : '') +
          '</summary><pre>' + esc(s.sql) + '</pre>' + (s.result && s.result.error ? '<div class="hint">' + esc(s.result.error) + '</div>' : '') + '</details>'; }).join('');
        b.innerHTML = md(res.markdown) + tableHtml(res.table) + steps + '<div class="acts"></div>';
        var acts = b.querySelector('.acts');
        function btn(label, fn){ var x = document.createElement('button'); x.type = 'button'; x.className = 'dl-btn'; x.textContent = label; x.onclick = fn; acts.appendChild(x); }
        if (res.table) btn('Download CSV', function(){ download('datalens-answer.csv', 'text/csv', csv(res.table)); });
        btn('Download MD', function(){ download('datalens-answer.md', 'text/markdown', res.export_md || res.markdown); });
        btn('Add to Action Plan', function(){
          var title = q.length > 120 ? q.slice(0, 117) + '…' : q;
          if (window.datalensAddAction) { var id = window.datalensAddAction(title, res.markdown); this.textContent = 'Added as ' + id; }
          else this.textContent = 'Action Plan not available';
          this.disabled = true; });
        history.push({role: 'user', content: q}, {role: 'assistant', content: res.markdown});
        transcript.push(res.export_md || ('## Q: ' + q + '\n\n' + res.markdown));
      })
      .catch(function(e){ pending.querySelector('.b').innerHTML = '<b>Error:</b> ' + esc(e); });
  }
  document.getElementById('dl-chat-form').onsubmit = function(ev){ ev.preventDefault(); send(document.getElementById('dl-chat-q').value); };
  document.getElementById('dl-chat-q').addEventListener('keydown', function(ev){ if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); send(this.value); } });
  document.getElementById('dl-chat-export').onclick = function(){ download('datalens-chat-insights.md', 'text/markdown',
    '# Datalens chat insights\n\n' + transcript.join('\n\n---\n\n')); };
})();
</script>
"""


def build_page(ws: RunWorkspace, token: str, provider_name: str, sql_ready: bool) -> bytes:
    if ws.report_path is None:
        html = "<!doctype html><meta charset='utf-8'><title>Datalens</title><body><p>No report in this run folder.</p>"
    else:
        html = ws.report_path.read_text(encoding="utf-8")
    boot = (f"<script>window.DATALENS_CHAT = {json.dumps({'token': token, 'provider': provider_name, 'sql': sql_ready})};"
            f"</script>")
    marker = "</body>"
    idx = html.rfind(marker)
    injected = boot + CHAT_UI
    html = html[:idx] + injected + html[idx:] if idx >= 0 else html + injected
    return html.encode("utf-8")


def make_handler(ws: RunWorkspace, session: ChatSession, token: str, provider_name: str, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "Datalens"

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: Any) -> None:
            self._send(code, dumps(data).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._send(403, b"forbidden host", "text/plain")
            if self.path in ("/", "/index.html", "/report"):
                return self._send(200, build_page(ws, token, provider_name, bool(ws.connection())),
                                  "text/html; charset=utf-8")
            if self.path == "/api/health":
                return self._json(200, {"ok": True, "provider": provider_name, "sql": bool(ws.connection()),
                                        "tables": list(ws.tables)})
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._send(403, b"forbidden host", "text/plain")
            if self.path != "/api/chat":
                return self._send(404, b"not found", "text/plain")
            if not secrets.compare_digest(self.headers.get("X-Datalens-Token", ""), token):
                return self._json(403, {"ok": False, "error": "bad session token"})
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 200_000)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            question = str(body.get("question", "")).strip()[:4000]
            if not question:
                return self._json(400, {"ok": False, "error": "empty question"})
            with lock:  # one question at a time: CLI providers aren't concurrent-safe
                reply = session.ask(question, body.get("history") or [])
            from datalens.chat.engine import answer_to_markdown

            reply["export_md"] = answer_to_markdown(question, reply)
            self._json(200, reply)

    return Handler


def serve(ws: RunWorkspace, provider: Any, *, port: int = 8765) -> tuple[ThreadingHTTPServer, str]:
    """Create the server (caller runs serve_forever). Returns (server, url)."""
    token = secrets.token_urlsafe(24)
    session = ChatSession(ws, provider)
    handler = make_handler(ws, session, token, provider.name, port)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    return server, f"http://127.0.0.1:{port}/"
