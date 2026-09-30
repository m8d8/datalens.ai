"""
Report sections for the decision, drift and BYOS features.

- ⓘ tooltips (``tip``) driven by ``datalens.glossary``
- Action Plan tab (Verdict chapter): every next step with evidence, fix, export
- How scores work (Verdict chapter): this run's health and DQI breakdown + glossary
- Drift report (top of Trends & Drift): findings with the rule that fired, the
  learned band, and per-run sparklines
- Expected Schema tab (Health chapter): BYOS conformance and every check

CSS/JS are plain strings (not f-strings) so braces need no escaping; all data
values are HTML-escaped, and embedded JSON is made safe for <script>.
"""

from __future__ import annotations

import html
import json
from typing import Any

from datalens.glossary import GLOSSARY, tip as glossary_tip
from datalens.profiling.quality import DIMENSION_WEIGHTS

_e = html.escape

SEVERITY_META = {
    "fail": ("var(--color-danger)", "Breach"),
    "high": ("var(--color-danger)", "High"),
    "warn": ("var(--color-warning)", "Warning"),
    "medium": ("var(--color-warning)", "Medium"),
    "info": ("var(--color-info)", "Info"),
    "low": ("var(--color-info)", "Low"),
    "pass": ("var(--color-success)", "Pass"),
    "ok": ("var(--color-success)", "OK"),
}

SOURCE_LABELS = {
    "drift": "Drift", "contract": "Expected schema", "pii": "Privacy", "integrity": "Integrity",
    "quality": "Quality", "ai": "AI", "rule": "Rule", "rolling": "Learned band",
}


def _json_for_script(data: Any) -> str:
    return json.dumps(data, default=str).replace("</", "<\\/")


def tip(key: str, text: str | None = None) -> str:
    """ⓘ icon with an accessible hover/focus tooltip (glossary text unless `text` is given)."""
    body = text if text is not None else glossary_tip(key)
    if not body:
        return ""
    more = f' data-term="{_e(key)}"' if key in GLOSSARY else ""
    return (f'<span class="dl-tip" tabindex="0" role="note" aria-label="{_e(body)}" '
            f'data-tip="{_e(body)}"{more}>ⓘ</span>')


_ICON_PATHS = {
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7l10-5z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "plus-square": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 8v8M8 12h8"/>',
    "trash": '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
    "plus-circle": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    "minus-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
    "shuffle": '<path d="M16 3h5v5"/><path d="M4 20 21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/>',
    "trending-down": '<path d="m23 18-9.5-9.5-5 5L1 6"/><path d="M17 18h6v-6"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m16.2 7.8-2.1 6.3-6.3 2.1 2.1-6.3z"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
}


def icon(name: str, color: str = "var(--text-secondary)") -> str:
    """Small colour-coded line icon in a tinted tile (section headers)."""
    paths = _ICON_PATHS.get(name, _ICON_PATHS["list"])
    return (f'<span class="dl-icon" style="color:{color}" aria-hidden="true"><svg viewBox="0 0 24 24" width="17" '
            f'height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{paths}</svg></span>')


def _chip(severity: str, label: str | None = None) -> str:
    color, default = SEVERITY_META.get(severity, ("var(--text-tertiary)", severity.title()))
    return (f'<span class="dl-chip" style="color:{color};border-color:{color}">'
            f'{_e(label or default)}</span>')


SHARED_CSS = """
<style>
.dl-tip { display:inline-flex; align-items:center; justify-content:center; width:1.05em; height:1.05em;
  margin-left:.3em; font-size:.8em; line-height:1; border-radius:50%; color:var(--text-tertiary);
  cursor:help; position:relative; vertical-align:middle; font-style:normal; }
.dl-tip:hover, .dl-tip:focus { color:var(--accent-primary); outline:none; }
.dl-tip::after { content:attr(data-tip); position:absolute; left:50%; bottom:calc(100% + 8px);
  transform:translateX(-50%); width:max-content; max-width:min(340px, 80vw); white-space:normal;
  background:var(--bg-primary); color:var(--text-primary); border:1px solid var(--border-secondary);
  border-radius:var(--radius-md); padding:8px 10px; font-size:.78rem; font-weight:400; line-height:1.45;
  text-align:left; box-shadow:var(--shadow-md); opacity:0; pointer-events:none; transition:opacity 120ms;
  z-index:50; }
.dl-tip:hover::after, .dl-tip:focus::after { opacity:1; }
.dl-chip { display:inline-block; padding:1px 8px; border:1px solid; border-radius:999px; font-size:.72rem;
  font-weight:600; white-space:nowrap; }
.dl-src { display:inline-block; padding:1px 8px; border-radius:999px; font-size:.72rem;
  background:var(--bg-tertiary); color:var(--text-secondary); white-space:nowrap; }
.dl-section { background:var(--bg-card); border:1px solid var(--border-primary); border-radius:var(--radius-lg);
  padding:var(--space-lg); margin-bottom:var(--space-lg); }
.dl-section h3 { margin:0 0 var(--space-sm); color:var(--text-primary); font-size:1.05rem; }
details.dl-fold > summary { cursor:pointer; list-style:none; }
details.dl-fold > summary::-webkit-details-marker { display:none; }
details.dl-fold > summary h3 { display:flex; align-items:center; gap:10px; }
details.dl-fold:not([open]) > summary h3 { margin:0; }
.dl-caret { display:inline-block; width:10px; color:var(--text-tertiary); transition:transform 150ms; font-size:.8em; }
details.dl-fold[open] > summary .dl-caret { transform:rotate(90deg); }
.dl-icon { display:inline-flex; align-items:center; justify-content:center; flex:0 0 30px; width:30px; height:30px;
  border-radius:8px; background:color-mix(in srgb, currentColor 14%, transparent); }
details.dl-fold:not([open]) > summary h3 { border-bottom:0; padding-bottom:0; }
.dl-muted { color:var(--text-tertiary); font-size:.85rem; }
.dl-toolbar { display:flex; flex-wrap:wrap; gap:var(--space-sm); align-items:center; margin:var(--space-md) 0; }
.dl-btn { background:var(--bg-secondary); color:var(--text-secondary); border:1px solid var(--border-primary);
  border-radius:var(--radius-md); padding:4px 10px; font:inherit; font-size:.8rem; cursor:pointer; }
.dl-btn:hover { color:var(--text-primary); border-color:var(--border-secondary); }
.dl-btn[aria-pressed="true"] { color:var(--text-primary); border-color:var(--accent-primary); }
.dl-kpis { display:flex; flex-wrap:wrap; gap:var(--space-md); }
.dl-kpi { background:var(--bg-secondary); border:1px solid var(--border-primary); border-radius:var(--radius-md);
  padding:var(--space-sm) var(--space-md); min-width:120px; }
.dl-kpi .v { font-size:1.35rem; font-weight:700; color:var(--text-primary); font-variant-numeric:tabular-nums; }
.dl-kpi .l { font-size:.75rem; color:var(--text-secondary); }
.dl-table { width:100%; border-collapse:collapse; font-size:.85rem; }
.dl-table th, .dl-table td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border-primary);
  vertical-align:top; }
.dl-table th { color:var(--text-secondary); font-weight:600; font-size:.78rem; }
.dl-table td.num, .dl-table th.num { text-align:right; font-variant-numeric:tabular-nums; }
.dl-scroll { overflow-x:auto; }
.dl-code { position:relative; }
.dl-code pre { background:var(--bg-primary); border:1px solid var(--border-primary); border-radius:var(--radius-md);
  padding:8px 10px; margin:6px 0 0; font-family:var(--font-mono); font-size:.76rem; white-space:pre-wrap;
  color:var(--text-primary); }
.dl-code .dl-copy { position:absolute; top:4px; right:4px; }
code.dl-inline { font-family:var(--font-mono); font-size:.85em; background:var(--bg-tertiary);
  padding:0 4px; border-radius:3px; }
</style>
"""


def _md(text: str) -> str:
    """Escape, then render `code` spans."""
    parts = str(text).split("`")
    return "".join(f'<code class="dl-inline">{_e(p)}</code>' if i % 2 else _e(p) for i, p in enumerate(parts))


# ── Action plan ─────────────────────────────────────────────────────────────

ACTION_CSS = """
<style>
.ap-card { border:1px solid var(--border-primary); border-left:4px solid var(--sev); border-radius:var(--radius-md);
  padding:var(--space-md); margin-bottom:var(--space-sm); background:var(--bg-secondary); }
.ap-card.done { opacity:.55; }
.ap-card.done .ap-title { text-decoration:line-through; }
.ap-head { display:flex; gap:var(--space-sm); align-items:flex-start; }
.ap-head input { margin-top:3px; }
.ap-title { font-weight:600; color:var(--text-primary); flex:1; }
.ap-meta { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 0 24px; align-items:center; }
.ap-body { margin:8px 0 0 24px; font-size:.86rem; color:var(--text-secondary); line-height:1.55; }
.ap-body b { color:var(--text-primary); font-weight:600; }
.ap-empty { padding:var(--space-lg); text-align:center; }
</style>
"""

ACTION_JS = """
<script>
(function(){
  var root = document.getElementById('dl-action-plan'); if (!root) return;
  var steps = []; try { steps = JSON.parse(document.getElementById('dl-steps-data').textContent || '[]'); } catch (e) {}
  var runKey = 'datalens-done:' + (root.getAttribute('data-run') || '');
  var done = {}; try { done = JSON.parse(localStorage.getItem(runKey) || '{}'); } catch (e) {}
  function save(){ try { localStorage.setItem(runKey, JSON.stringify(done)); } catch (e) {} }
  var filters = {severity:'all', source:'all'};
  function apply(){
    var shown = 0;
    root.querySelectorAll('.ap-card').forEach(function(card){
      var ok = (filters.severity==='all' || card.dataset.severity===filters.severity) &&
               (filters.source==='all' || card.dataset.source===filters.source);
      card.style.display = ok ? '' : 'none'; if (ok) shown++;
      var id = card.dataset.id; var box = card.querySelector('input[type=checkbox]');
      if (box) { box.checked = !!done[id]; card.classList.toggle('done', !!done[id]); }
    });
    var c = root.querySelector('.ap-count'); if (c) c.textContent = shown + ' of ' + steps.length + ' shown';
  }
  root.querySelectorAll('[data-filter]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var kind = btn.dataset.filter; filters[kind] = btn.dataset.value;
      root.querySelectorAll('[data-filter="'+kind+'"]').forEach(function(b){ b.setAttribute('aria-pressed', b===btn); });
      apply();
    });
  });
  root.addEventListener('change', function(ev){
    var box = ev.target; if (!box.matches('input[type=checkbox]')) return;
    var id = box.closest('.ap-card').dataset.id; if (box.checked) done[id] = true; else delete done[id];
    save(); apply();
  });
  root.addEventListener('click', function(ev){
    var btn = ev.target.closest('.dl-copy'); if (!btn) return;
    var text = btn.parentElement.querySelector('pre').textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function(){
      btn.textContent = 'Copied'; setTimeout(function(){ btn.textContent = 'Copy'; }, 1200);
    }, function(){ btn.textContent = 'Select & copy'; });
  });
  function download(name, type, text){
    var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type:type}));
    a.download = name; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  function rows(){ return steps.map(function(s){ return Object.assign({}, s, {done: !!done[s.id]}); }); }
  function csvCell(v){ v = (v===undefined||v===null) ? '' : (Array.isArray(v) ? v.join('; ') : String(v)); return '"' + v.replace(/"/g,'""') + '"'; }
  root.querySelectorAll('[data-export]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var fmt = btn.dataset.export, r = rows(), stem = 'datalens-action-plan';
      if (fmt==='json') download(stem+'.json','application/json', JSON.stringify(r, null, 2));
      if (fmt==='csv') {
        var cols = ['id','priority','severity','source','category','title','fields','why','impact','fix','effort','done'];
        download(stem+'.csv','text/csv', [cols.join(',')].concat(r.map(function(s){ return cols.map(function(c){ return csvCell(s[c]); }).join(','); })).join('\\n'));
      }
      if (fmt==='md') {
        var md = ['# Datalens action plan', ''];
        r.forEach(function(s){
          md.push('## ' + (s.done ? '~~' : '') + s.id + ' · ' + s.title + (s.done ? '~~' : ''));
          md.push('', '*' + s.severity + ' · ' + s.source + ' · effort ' + s.effort + '*', '', s.why || '', '');
          if (s.impact) md.push('**Why it matters:** ' + s.impact, '');
          if (s.fix) md.push('```', s.fix, '```', '');
        });
        download(stem+'.md','text/markdown', md.join('\\n'));
      }
    });
  });
  // Items added from chat (datalens serve) are kept per run in this browser.
  var customKey = 'datalens-custom:' + (root.getAttribute('data-run') || '');
  function loadCustom(){ try { return JSON.parse(localStorage.getItem(customKey) || '[]'); } catch (e) { return []; } }
  function esc(t){ var d = document.createElement('div'); d.textContent = t == null ? '' : String(t); return d.innerHTML; }
  function renderCustom(item){
    var card = document.createElement('div');
    card.className = 'ap-card'; card.style.setProperty('--sev', 'var(--accent-secondary)');
    card.dataset.id = item.id; card.dataset.severity = item.severity || 'medium'; card.dataset.source = 'chat';
    card.innerHTML = '<div class="ap-head"><input type="checkbox" aria-label="Mark done"><div class="ap-title">' +
      esc(item.id) + ' · ' + esc(item.title) + '</div></div><div class="ap-meta"><span class="dl-src">Chat</span>' +
      '<span class="dl-muted">added ' + esc(item.added || '') + '</span></div><div class="ap-body">' + esc(item.why) + '</div>';
    var first = root.querySelector('.ap-card'); if (first) first.parentNode.insertBefore(card, first); else root.appendChild(card);
    steps.push(item);
  }
  loadCustom().forEach(renderCustom);
  window.datalensAddAction = function(title, why){
    var items = loadCustom(); var item = {id: 'C' + String(items.length + 1).padStart(2, '0'), title: title, why: why,
      severity: 'medium', source: 'chat', category: 'Chat', added: new Date().toISOString().slice(0, 16).replace('T', ' ')};
    items.push(item); try { localStorage.setItem(customKey, JSON.stringify(items)); } catch (e) {}
    renderCustom(item); apply(); return item.id;
  };
  apply();
})();
</script>
"""


def render_action_plan(decision: dict[str, Any] | None, version_tag: str) -> str:
    steps = (decision or {}).get("next_steps") or []
    if not steps:
        return SHARED_CSS + ('<div class="dl-section ap-empty"><h3>No actions needed</h3>'
                             '<p class="dl-muted">No drift, schema, privacy, integrity or quality issue '
                             'crossed a threshold in this run.</p></div>')
    sev_counts = {s: sum(1 for a in steps if a["severity"] == s) for s in ("high", "medium", "low")}
    sources = sorted({a["source"] for a in steps})

    cards = []
    for a in steps:
        color = SEVERITY_META.get(a["severity"], ("var(--text-tertiary)", ""))[0]
        fields = "".join(f'<code class="dl-inline">{_e(f)}</code> ' for f in a.get("fields", [])[:8])
        fix = (f'<div class="dl-code"><button class="dl-btn dl-copy" type="button">Copy</button>'
               f'<pre>{_e(a["fix"])}</pre></div>') if a.get("fix") else ""
        cards.append(f"""
        <div class="ap-card" style="--sev:{color}" data-id="{_e(a['id'])}" data-severity="{_e(a['severity'])}"
             data-source="{_e(a['source'])}">
          <div class="ap-head">
            <input type="checkbox" aria-label="Mark {_e(a['id'])} done">
            <div class="ap-title">{_e(a['id'])} · {_md(a['title'])}</div>
          </div>
          <div class="ap-meta">
            {_chip(a['severity'])}
            {''.join(f'<span class="dl-src">{_e(SOURCE_LABELS.get(src, src))}</span>' for src in a.get('sources', [a['source']]))}
            <span class="dl-src">{_e(a.get('category', ''))}</span>
            <span class="dl-src">effort: {_e(a.get('effort', ''))} {tip('', 'Effort is an estimate: consumer/config changes are low, upstream data fixes medium, data-model changes high.')}</span>
            <span class="dl-src">for: {_e(a.get('persona', ''))}</span>
            <span class="dl-muted">priority {a['priority']}</span>
          </div>
          <div class="ap-body">
            <div><b>Evidence:</b> {_md(a.get('why', ''))}</div>
            {f"<div><b>Why it matters:</b> {_md(a['impact'])}</div>" if a.get('impact') else ''}
            {f"<div><b>Affects:</b> {fields}</div>" if fields else ''}
            {fix}
          </div>
        </div>""")

    sev_buttons = "".join(
        f'<button class="dl-btn" type="button" data-filter="severity" data-value="{s}" aria-pressed="false">'
        f'{s.title()} ({n})</button>' for s, n in sev_counts.items() if n)
    src_buttons = "".join(
        f'<button class="dl-btn" type="button" data-filter="source" data-value="{s}" aria-pressed="false">'
        f'{_e(SOURCE_LABELS.get(s, s))}</button>' for s in sources)
    return f"""{SHARED_CSS}{ACTION_CSS}
    <div id="dl-action-plan" data-run="{_e(version_tag)}">
      <div class="dl-section">
        <h3>What to do next {tip('', 'Every finding of this run turned into one action, highest priority first. Priority = severity × 10 + breadth (share of rows/fields affected). Tick items off — progress is kept in this browser only.')}</h3>
        <div class="dl-kpis">
          <div class="dl-kpi"><div class="v">{len(steps)}</div><div class="l">actions</div></div>
          <div class="dl-kpi"><div class="v" style="color:var(--color-danger)">{sev_counts['high']}</div><div class="l">high</div></div>
          <div class="dl-kpi"><div class="v" style="color:var(--color-warning)">{sev_counts['medium']}</div><div class="l">medium</div></div>
          <div class="dl-kpi"><div class="v" style="color:var(--color-info)">{sev_counts['low']}</div><div class="l">low</div></div>
        </div>
        <p class="dl-muted">Have a question about this data? Run <code class="dl-inline">datalens serve &lt;this run's folder&gt;</code>
          to chat with it (answers can be added here), or <code class="dl-inline">datalens ask "…" &lt;folder&gt;</code>.</p>
        <div class="dl-toolbar">
          <button class="dl-btn" type="button" data-filter="severity" data-value="all" aria-pressed="true">All severities</button>
          {sev_buttons}
        </div>
        <div class="dl-toolbar">
          <button class="dl-btn" type="button" data-filter="source" data-value="all" aria-pressed="true">All sources</button>
          {src_buttons}
          <span style="flex:1"></span>
          <span class="dl-muted ap-count"></span>
          <button class="dl-btn" type="button" data-export="csv">Export CSV</button>
          <button class="dl-btn" type="button" data-export="md">Export Markdown</button>
          <button class="dl-btn" type="button" data-export="json">Export JSON</button>
        </div>
      </div>
      {''.join(cards)}
      <script type="application/json" id="dl-steps-data">{_json_for_script(steps)}</script>
    </div>
    {ACTION_JS}"""


# ── How scores work ─────────────────────────────────────────────────────────

def render_how_scored(decision: dict[str, Any] | None, quality: dict[str, Any] | None) -> str:
    verdict = (decision or {}).get("health_verdict") or {}
    pen = verdict.get("penalties") or {}
    rows = [("Starting point: overall DQI", verdict.get("base_dqi"), "dqi")]
    labels = {"pii": ("High-risk PII fields", "exposure"), "drift": ("Drift vs the reference run", "rolling"),
              "contract": ("Expected-schema failures", "conformance"), "mixed_types": ("Mixed-type fields", "consistency")}
    for key, (label, term) in labels.items():
        rows.append((label, -pen.get(key, 0.0) if pen.get(key) else 0.0, term))
    health_rows = "".join(
        f'<tr><td>{_e(label)} {tip(term)}</td><td class="num">{"" if v is None else f"{v:+.1f}" if i else f"{v:.1f}"}</td></tr>'
        for i, (label, v, term) in enumerate(rows))
    health_rows += (f'<tr><th>Health score {tip("health")}</th><th class="num">{verdict.get("score", 0):.1f}</th></tr>')

    objects = (quality or {}).get("objects") or []
    dims = list(DIMENSION_WEIGHTS)
    head = "".join(f'<th class="num">{_e(d.title())} {tip(d)}<div class="dl-muted">w {DIMENSION_WEIGHTS[d]:.2f}</div></th>'
                   for d in dims)
    body = []
    for obj in objects:
        cells = []
        for d in dims:
            dim = (obj.get("dimensions") or {}).get(d)
            if not dim:
                cells.append('<td class="num dl-muted">—</td>')
            elif dim.get("weight", 1) == 0:
                note = (dim.get("details") or {}).get("not_scored", "not scored")
                cells.append(f'<td class="num dl-muted">n/a {tip("", note)}</td>')
            else:
                cells.append(f'<td class="num">{dim["score"]:.0f}</td>')
        body.append(f'<tr><td>{_e(obj["object"])}</td>{"".join(cells)}<td class="num"><b>{obj["dqi"]:.1f}</b></td></tr>')
    dqi_table = (f'<div class="dl-scroll"><table class="dl-table"><thead><tr><th>Object</th>{head}'
                 f'<th class="num">DQI {tip("dqi")}</th></tr></thead><tbody>{"".join(body)}</tbody>'
                 f'<tfoot><tr><th>Overall (mean of objects)</th>{"<td></td>" * len(dims)}'
                 f'<th class="num">{(quality or {}).get("overall_dqi", 0):.1f}</th></tr></tfoot></table></div>')

    glossary = render_glossary()
    return f"""{SHARED_CSS}
    <div class="dl-section">
      <h3>This run's health score, step by step</h3>
      <p class="dl-muted">Health = DQI minus penalties. Every number links to how it is computed (hover ⓘ).</p>
      <table class="dl-table" style="max-width:560px">{health_rows}</table>
    </div>
    <div class="dl-section">
      <h3>DQI by object and dimension</h3>
      <p class="dl-muted">Object DQI = Σ(score × weight) / Σ(weights of scored dimensions). "n/a" dimensions
        couldn't be scored for that object and are left out.</p>
      {dqi_table}
    </div>
    {glossary}"""


# ── Glossary ────────────────────────────────────────────────────────────────

GLOSSARY_GROUPS = [
    ("Headline scores", "What the verdict is built from", ["health", "dqi", "fitness"]),
    ("Quality dimensions", "The parts of the DQI and their weights",
     ["completeness", "consistency", "uniqueness", "validity", "timeliness", "granularity", "accuracy", "field_score"]),
    ("Change & drift", "How runs are compared", ["coverage", "row_count", "psi", "rolling", "orphan_pct"]),
    ("Privacy & contract", "PII risk and your expected schema", ["exposure", "conformance"]),
]

GLOSSARY_CSS = """
<style>
.gl-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:6px; }
.gl-head h3 { margin:0; flex:1; }
.gl-search { background:var(--bg-input); color:var(--text-primary); border:1px solid var(--border-primary);
  border-radius:var(--radius-md); padding:5px 10px; font:inherit; font-size:.82rem; width:220px; }
.gl-icon-btn { display:inline-flex; align-items:center; gap:6px; }
.gl-icon-btn svg { width:14px; height:14px; }
.gl-group { margin-top:18px; }
.gl-group-title { display:flex; align-items:baseline; gap:10px; margin:0 0 8px; }
.gl-group-title span:first-child { font-size:.72rem; letter-spacing:.07em; text-transform:uppercase; font-weight:700;
  color:var(--text-secondary); }
.gl-group-title span:last-child { font-size:.78rem; color:var(--text-tertiary); }
.gl-item { border:1px solid var(--border-primary); border-radius:var(--radius-md); background:var(--bg-secondary);
  margin-bottom:6px; }
.gl-item > summary { display:grid; grid-template-columns:minmax(150px, 220px) 1fr auto; gap:14px; align-items:center;
  padding:9px 12px; cursor:pointer; list-style:none; }
.gl-item > summary::-webkit-details-marker { display:none; }
.gl-name { font-weight:600; color:var(--text-primary); font-size:.88rem; }
.gl-short { color:var(--text-secondary); font-size:.82rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.gl-item[open] .gl-short { white-space:normal; }
.gl-meta { display:flex; gap:6px; align-items:center; }
.gl-weight { font-size:.7rem; font-weight:600; color:var(--accent-primary); border:1px solid var(--accent-primary);
  border-radius:999px; padding:0 7px; }
.gl-caret { color:var(--text-tertiary); transition:transform 150ms; }
.gl-item[open] .gl-caret { transform:rotate(90deg); }
.gl-body { display:grid; grid-template-columns:minmax(150px, 220px) 1fr; gap:6px 14px; padding:2px 12px 12px;
  border-top:1px solid var(--border-primary); font-size:.83rem; }
.gl-body dt { color:var(--text-tertiary); font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; padding-top:9px; }
.gl-body dd { margin:0; padding-top:8px; color:var(--text-secondary); line-height:1.55; }
.gl-steps { margin:0; padding-left:18px; }
.gl-steps li { margin:2px 0; }
.gl-formula { font-family:var(--font-mono); font-size:.78rem; color:var(--text-primary); background:var(--bg-primary);
  border-radius:4px; padding:1px 6px; }
@media (max-width: 720px) { .gl-item > summary, .gl-body { grid-template-columns:1fr; } .gl-short { white-space:normal; } }
</style>
"""

GLOSSARY_JS = """
<script>
(function(){
  var root = document.getElementById('dl-glossary'); if (!root) return;
  root.querySelectorAll('[data-gl]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var open = btn.dataset.gl === 'open';
      root.querySelectorAll('details.gl-item').forEach(function(d){ if (d.style.display !== 'none') d.open = open; });
    });
  });
  var box = root.querySelector('.gl-search');
  if (box) box.addEventListener('input', function(){
    var q = box.value.trim().toLowerCase();
    root.querySelectorAll('details.gl-item').forEach(function(d){
      d.style.display = !q || d.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    });
    root.querySelectorAll('.gl-group').forEach(function(g){
      g.style.display = g.querySelector('details.gl-item:not([style*="none"])') ? '' : 'none';
    });
  });
})();
</script>
"""

_EXPAND_SVG = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
               '<path d="M3 6l5 5 5-5"/><path d="M3 2h10"/></svg>')
_COLLAPSE_SVG = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
                 '<path d="M3 10l5-5 5 5"/><path d="M3 14h10"/></svg>')


def _step_html(step: str) -> str:
    """A calculation step; the formula part (with =, ×, ·, Σ or /) is set in monospace."""
    text = _e(step)
    if any(ch in step for ch in ("=", "×", "·", "Σ", "√", "±")):
        head, sep, tail = step.partition(": ")
        if sep and len(head) < 40 and not any(ch in head for ch in ("=", "×", "·")):
            return f"{_e(head)}: <span class=\"gl-formula\">{_e(tail)}</span>"
        return f'<span class="gl-formula">{text}</span>'
    return text


def render_glossary() -> str:
    groups = []
    for title, sub, keys in GLOSSARY_GROUPS:
        items = []
        for key in keys:
            entry = GLOSSARY.get(key)
            if not entry:
                continue
            weight = DIMENSION_WEIGHTS.get(key)
            weight_chip = f'<span class="gl-weight">weight {weight:.2f}</span>' if weight is not None else ""
            steps = "".join(f"<li>{_step_html(step)}</li>" for step in entry["how"])
            items.append(f"""
          <details class="gl-item" id="gl-{_e(key)}">
            <summary><span class="gl-name">{_e(entry['title'])}</span><span class="gl-short">{_e(entry['short'])}</span>
              <span class="gl-meta">{weight_chip}<span class="gl-caret">▸</span></span></summary>
            <dl class="gl-body">
              <dt>What it means</dt><dd>{_e(entry['short'])}</dd>
              <dt>When</dt><dd>{_e(entry['when'])}</dd>
              <dt>How it's calculated</dt><dd><ol class="gl-steps">{steps}</ol></dd>
            </dl>
          </details>""")
        groups.append(f"""
        <div class="gl-group"><div class="gl-group-title"><span>{_e(title)}</span><span>{_e(sub)}</span></div>
          {''.join(items)}</div>""")
    return f"""{GLOSSARY_CSS}
    <div class="dl-section" id="dl-glossary">
      <div class="gl-head">
        <h3>Glossary</h3>
        <input class="gl-search" type="search" placeholder="Filter terms…" aria-label="Filter glossary">
        <button class="dl-btn gl-icon-btn" type="button" data-gl="open" title="Expand all" aria-label="Expand all">{_EXPAND_SVG} Expand all</button>
        <button class="dl-btn gl-icon-btn" type="button" data-gl="close" title="Collapse all" aria-label="Collapse all">{_COLLAPSE_SVG} Collapse all</button>
      </div>
      <p class="dl-muted" style="margin:0">Every metric in this report: what it means, when it applies and how it's
        calculated. Same text offline: <code class="dl-inline">datalens glossary &lt;term&gt;</code> · docs/METRICS.md.</p>
      {''.join(groups)}
    </div>
    {GLOSSARY_JS}"""


# ── Drift report ────────────────────────────────────────────────────────────

DRIFT_JS = """
<script>
(function(){
  var root = document.getElementById('dl-drift'); if (!root) return;
  // A search hit inside a folded section would be invisible: searching unfolds the drift sections.
  var search = document.getElementById('globalSearch');
  if (search) search.addEventListener('input', function(){
    if (search.value.trim()) document.querySelectorAll('#trends details.drift-card, #trends details.dl-fold')
      .forEach(function(d){ d.open = true; });
  });
  root.querySelectorAll('[data-dfilter]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var v = btn.dataset.dfilter;
      root.querySelectorAll('[data-dfilter]').forEach(function(b){ b.setAttribute('aria-pressed', b===btn); });
      root.querySelectorAll('tr[data-sev]').forEach(function(tr){
        tr.style.display = (v==='all' || tr.dataset.sev===v) ? '' : 'none';
      });
    });
  });
})();
</script>
"""


def _sparkline(values: list[float], *, width: int = 150, height: int = 30, highlight_last: bool = True,
               band: dict[str, float] | None = None) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if band:
        lo, hi = min(lo, band["lower"]), max(hi, band["upper"])
    span = (hi - lo) or 1.0
    step = width / max(1, len(values) - 1)

    def y(v: float) -> float:
        return height - 3 - (v - lo) / span * (height - 6)

    pts = " ".join(f"{i * step:.1f},{y(v):.1f}" for i, v in enumerate(values))
    band_rect = ""
    if band:
        top, bottom = y(band["upper"]), y(band["lower"])
        band_rect = (f'<rect x="0" y="{top:.1f}" width="{width}" height="{max(1.0, bottom - top):.1f}" '
                     f'fill="var(--color-success)" opacity="0.12"/>')
    last = values[-1]
    dot = (f'<circle cx="{(len(values) - 1) * step:.1f}" cy="{y(last):.1f}" r="3" fill="var(--accent-primary)"/>'
           if highlight_last else "")
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="trend of {len(values)} runs">{band_rect}'
            f'<polyline points="{pts}" fill="none" stroke="var(--text-secondary)" stroke-width="1.5"/>{dot}</svg>')


def render_drift_report(
    drift: dict[str, Any] | None,
    history_runs: list[dict[str, Any]] | None = None,
    current_metrics: dict[str, float] | None = None,
    run_date: str | None = None,
) -> str:
    if not drift:
        return ""
    summ = drift.get("summary") or {}
    ref = drift.get("reference") or {}
    mode = str(drift.get("mode", "previous"))
    mode_text = {
        "previous": f"the previous run <b>{_e(str(ref.get('tag')))}</b>",
        "rolling": f"a baseline learned from up to {(ref.get('rolling') or {}).get('window', '?')} recent runs",
    }.get(mode.split(":")[0], f"the fixed baseline <b>{_e(str(ref.get('tag')))}</b>")
    rolling = ref.get("rolling") or {}
    rolling_note = ""
    if rolling:
        rolling_note = (f'<p class="dl-muted">Learned band scored {rolling.get("metrics_scored", 0)} metric(s); '
                        f'{rolling.get("metrics_cold_start", 0)} had fewer than {rolling.get("min_history")} earlier '
                        f'values and used the fixed rules (cold start). {tip("rolling")}</p>')

    rows = []
    for f in drift.get("findings", []):
        where = f"{f.get('object') or 'dataset'}{'.' + f['field'] if f.get('field') else ''}"
        rule = f.get("rule") or {}
        src = SOURCE_LABELS.get(rule.get("source", "rule"), rule.get("source", ""))
        band = f.get("band")
        band_txt = f'<div class="dl-muted">band {band["lower"]:.4g} … {band["upper"]:.4g}, n={band["n"]}</div>' if band else ""
        rows.append(
            f'<tr data-sev="{_e(f["severity"])}"><td>{_chip(f["severity"])}</td>'
            f'<td><code class="dl-inline">{_e(where)}</code><div class="dl-muted">{_e(f["kind"].replace("_", " "))}</div></td>'
            f'<td>{_md(f["message"])} {tip("", f.get("how", ""))}</td>'
            f'<td><span class="dl-src">{_e(src)}</span> <span class="dl-muted">{_e(str(rule.get("scope", "")))}</span>'
            f'<div class="dl-muted">{_e(str(rule.get("threshold", "")))}</div>{band_txt}</td></tr>')
    table = ('<div class="dl-scroll"><table class="dl-table"><thead><tr><th>Severity</th><th>Where</th>'
             '<th>What changed</th><th>Rule that fired</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
             ) if rows else '<p class="dl-muted">No change crossed a rule or left its learned range.</p>'

    notes = "".join(f'<li>{_e(n)}</li>' for n in drift.get("notes", []))
    timeline = _render_timeline(history_runs or [], current_metrics or {}, run_date)
    buttons = "".join(
        f'<button class="dl-btn" type="button" data-dfilter="{s}" aria-pressed="false">{label} ({summ.get(s, 0)})</button>'
        for s, label in (("fail", "Breaches"), ("warn", "Warnings"), ("info", "Info")) if summ.get(s))
    status_color = {"fail": "var(--color-danger)", "warn": "var(--color-warning)"}.get(drift.get("status"), "var(--color-success)")
    return f"""{SHARED_CSS}
    <div id="dl-drift">
      <details class="dl-section dl-fold" open style="border-left:5px solid {status_color}">
        <summary><h3><span class="dl-caret">▸</span>{icon("compass", "var(--accent-primary)")}Drift report — compared with {mode_text}</h3></summary>
        <div class="dl-kpis">
          <div class="dl-kpi"><div class="v" style="color:var(--color-danger)">{summ.get('fail', 0)}</div><div class="l">breaches</div></div>
          <div class="dl-kpi"><div class="v" style="color:var(--color-warning)">{summ.get('warn', 0)}</div><div class="l">warnings</div></div>
          <div class="dl-kpi"><div class="v">{summ.get('info', 0)}</div><div class="l">info</div></div>
          <div class="dl-kpi"><div class="v">{ref.get('runs_in_history', 0)}</div><div class="l">earlier runs in history</div></div>
        </div>
        {rolling_note}
        {f'<ul class="dl-muted">{notes}</ul>' if notes else ''}
        <div class="dl-toolbar"><button class="dl-btn" type="button" data-dfilter="all" aria-pressed="true">All</button>{buttons}</div>
        {table}
        <p class="dl-muted">Thresholds come from drift rules (built-in defaults, your config, or x-datalens in an expected
          schema) or from the learned rolling band. CLI: <code class="dl-inline">datalens drift --compare-to rolling</code>.</p>
      </details>
      {timeline}
    </div>
    {DRIFT_JS}"""


def _num(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}"


DELTA_WINDOWS = [(1, "1 day"), (7, "7 days"), (30, "1 month")]


def _parse_date(value: Any):
    import datetime as _dt

    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return _dt.datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None


def delta_references(history_runs: list[dict[str, Any]], run_date: str | None) -> list[tuple[str, dict[str, Any]]]:
    """
    For each window (1 day, 7 days, 1 month): the newest earlier run dated at least
    that many days before this run. Windows with no such run are left out.
    """
    import datetime as _dt

    now = _parse_date(run_date) or _dt.datetime.now()
    dated = [(d, r) for r in history_runs if (d := _parse_date(r.get("run_date") or r.get("timestamp")))]
    dated.sort(key=lambda x: x[0], reverse=True)
    refs = []
    for days, label in DELTA_WINDOWS:
        cutoff = now.date() - _dt.timedelta(days=days)
        match = next((r for d, r in dated if d.date() <= cutoff), None)
        if match is not None:
            refs.append((label, {**match, "_date": next(d for d, r in dated if r is match)}))
    return refs


def _delta_cell(metric: str, old: float | None, new: float, ref: dict[str, Any]) -> str:
    if old is None:
        return '<td class="num dl-muted">—</td>'
    diff = new - old
    when = f"vs {ref.get('tag')} ({ref['_date']:%Y-%m-%d}): {_num(old) if metric != 'row_count' else f'{old:,.0f}'}"
    if abs(diff) < 1e-9:
        return f'<td class="num dl-muted" title="{_e(when)}">0</td>'
    arrow = "▲" if diff > 0 else "▼"
    # Direction colours: rise green, drop red (no change stays grey, above).
    color = "var(--color-success)" if diff > 0 else "var(--color-danger)"
    if metric == "row_count":
        pct = f" ({diff / old * 100:+.1f}%)" if old else ""
        text = f"{arrow} {diff:+,.0f}{pct}"
    else:
        text = f"{arrow} {diff:+.1f} pts"
    return f'<td class="num" style="color:{color}" title="{_e(when)}">{_e(text)}</td>'


def _render_timeline(history_runs: list[dict[str, Any]], current: dict[str, float],
                     run_date: str | None = None) -> str:
    runs = list(reversed(history_runs))  # oldest → newest
    if not runs or not current:
        return ""
    refs = delta_references(history_runs, run_date)
    # Headline series: health, overall DQI, and each object's row count.
    keys = [k for k in current if k in ("health||", "dqi||") or k.startswith("row_count|")]
    keys.sort(key=lambda k: (not k.startswith("health"), not k.startswith("dqi"), k))
    rows = []
    for key in keys[:12]:
        series = [float(r["metrics"][key]) for r in runs if key in (r.get("metrics") or {})] + [float(current[key])]
        if len(series) < 2:
            continue
        metric, obj, _ = (key.split("|") + ["", ""])[:3]
        label = {"row_count": f"{obj} rows", "health": "Health", "dqi": "DQI"}.get(metric, key)
        prev = series[:-1]
        fmt = (lambda v: f"{v:,.0f}") if metric == "row_count" else _num
        deltas = "".join(
            _delta_cell(metric, (ref.get("metrics") or {}).get(key), float(current[key]), ref) for _, ref in refs)
        rows.append(f'<tr><td>{_e(label)}</td><td>{_sparkline(series[-30:])}</td>'
                    f'<td class="num">{fmt(min(prev))}–{fmt(max(prev))}</td>{deltas}'
                    f'<td class="num"><b>{fmt(series[-1])}</b></td></tr>')
    if not rows:
        return ""
    heads = []
    for label, ref in refs:
        explain = (f"Change vs the newest run at least {label} before this one: {ref.get('tag')} "
                   f"({ref['_date']:%Y-%m-%d}). Hover a cell for the earlier value.")
        heads.append(f'<th class="num">Δ {_e(label)} {tip("", explain)}</th>')
    delta_heads = "".join(heads)
    missing = [label for _, label in DELTA_WINDOWS if label not in {lbl for lbl, _ in refs}]
    note = (f' Not enough history yet for: {", ".join(missing)}.' if missing else "")
    return ('<details class="dl-section dl-fold" open><summary><h3><span class="dl-caret">▸</span>'
            + icon("activity", "var(--color-info)") + 'Timeline — this run vs earlier runs</h3></summary>'
            '<p class="dl-muted">Each line is one metric across saved runs (oldest → newest; the dot is this run). '
            'Δ columns compare this run with the newest run at least that long before it.' + _e(note) + '</p>'
            '<div class="dl-scroll"><table class="dl-table" style="max-width:980px"><thead><tr><th>Metric</th><th>Trend</th>'
            '<th class="num">Earlier range</th>' + delta_heads + '<th class="num">This run</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div></details>')


# ── Expected schema (BYOS) ──────────────────────────────────────────────────

def render_contract(contract: dict[str, Any] | None) -> str:
    if not contract:
        return ""
    blocks = []
    for obj in contract.get("objects", []):
        rows = "".join(
            f'<tr data-sev="{_e(c["status"])}"><td>{_chip(c["status"])}</td><td><code class="dl-inline">{_e(c["field"] or "—")}</code></td>'
            f'<td>{_e(c["check"])}</td><td>{_md(c["message"])}</td>'
            f'<td class="dl-muted">{_e(str(c["expected"]))[:120]}</td><td class="dl-muted">{_e(str(c["observed"]))[:120]}</td></tr>'
            for c in sorted(obj["checks"], key=lambda c: {"fail": 0, "warn": 1, "info": 2, "pass": 3}[c["status"]]))
        blocks.append(f"""
        <div class="dl-section">
          <h3>{_e(obj['object'])} — {obj['conformance_pct']}% conformant {_chip(obj['status'], obj['status'].title())}</h3>
          <p class="dl-muted">Schema: {_e(obj['schema'])} · matched by {_e(obj['matched_by'])}</p>
          <div class="dl-scroll"><table class="dl-table"><thead><tr><th>Status</th><th>Field</th><th>Check</th>
            <th>Result</th><th>Expected</th><th>Observed</th></tr></thead><tbody>{rows}</tbody></table></div>
        </div>""")
    s = contract.get("summary") or {}
    return f"""{SHARED_CSS}
    <div class="dl-section">
      <h3>Expected schema (BYOS) — {contract.get('conformance_pct')}% conformant {tip('conformance')}</h3>
      <div class="dl-kpis">
        <div class="dl-kpi"><div class="v" style="color:var(--color-danger)">{s.get('fail', 0)}</div><div class="l">failed checks</div></div>
        <div class="dl-kpi"><div class="v" style="color:var(--color-warning)">{s.get('warn', 0)}</div><div class="l">warnings</div></div>
        <div class="dl-kpi"><div class="v" style="color:var(--color-success)">{s.get('pass', 0)}</div><div class="l">passed</div></div>
      </div>
      <p class="dl-muted">Checks every declared field for required, type, format, enum, range and pattern. Bootstrap a schema
        with <code class="dl-inline">datalens schema infer</code>, edit it, then pass it with <code class="dl-inline">--schema</code>.</p>
    </div>
    {''.join(blocks)}"""
