"""
AI Review tab — model output made scannable.

Models write dense paragraphs. Each item is turned into a *finding card*:

    title          the bolded lead or first clause ("Coverage complementarity in matches.outcome")
    gist           the first sentence of the explanation, shown always
    key numbers    the figures in the item as coloured chips (45%, 98%, 2,311 …)
    fields         field names mentioned, as monospace chips
    details        the full text, with numbers / fields / arrows highlighted, behind a toggle

so a reader gets the point from the card face and opens details only when needed.
"""

from __future__ import annotations

import html
import re
from typing import Any

_e = html.escape

SECTIONS = [
    # key, title, icon, accent, what it tells you
    ("quality_assessment", "Quality assessment", "✅", "var(--color-success)", "Overall judgement of the data"),
    ("key_domain_fields", "Key & domain fields", "🏷️", "var(--accent-primary)", "The fields that matter most"),
    ("domain_field_assessments", "Field assessments", "🎯", "var(--color-caution)", "Field-by-field concerns"),
    ("unique_id_patterns", "Identifiers", "🔑", "var(--color-info)", "Keys and how reliable they are"),
    ("cross_object_patterns", "Across objects", "🔗", "var(--accent-secondary)", "How objects relate"),
    ("structural_value_patterns", "Structure & values", "📐", "var(--color-info)", "Shapes, sparsity, conventions"),
    ("hidden_value_relationships", "Hidden relationships", "💎", "var(--accent-secondary)", "Rules the data implies"),
]

_NUM = re.compile(
    r"(?<![\w.`])(?:[+\-−]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|pts|pp|×|x\b))?)(?![\w`])"
)
_ARROW = re.compile(r"\s(→|->)\s")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*(\[])")


def _inline(text: str) -> str:
    """Escape, then highlight `code` (fields), **bold**, *italic*, numbers and arrows."""
    out: list[str] = []
    for i, part in enumerate(str(text).split("`")):
        if i % 2:
            out.append(f'<code class="air-field">{_e(part)}</code>')
            continue
        chunk = _e(part)
        chunk = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", chunk)
        chunk = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", chunk)
        chunk = _NUM.sub(lambda m: f'<span class="{_num_class(m.group(0))}">{m.group(0)}</span>', chunk)
        chunk = _ARROW.sub(' <span class="air-arrow">→</span> ', chunk)
        out.append(chunk)
    return "".join(out)


def _num_class(token: str) -> str:
    if "%" in token or "pts" in token or "pp" in token:
        return "air-num air-pct"
    return "air-num"


def _plain(text: str) -> str:
    return re.sub(r"[*`]", "", str(text))


def split_item(item: Any) -> tuple[str, str]:
    """(title, body) from '**Title**: body', 'Title — body', 'Title: body' or a plain sentence."""
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("field") or item.get("name") or next(iter(item.values()), ""))
        body = "; ".join(f"{k}: {v}" for k, v in item.items() if str(v) != title)
        return title, body
    text = re.sub(r"^[-•]\s+", "", str(item).strip())
    m = re.match(r"^\*\*(.+?)\*\*\s*[:—–\-]?\s*(.*)$", text, re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.{3,90}?)\s+[—–]\s+(.*)$", text, re.S) or re.match(r"^([^:.]{3,80}):\s+(.*)$", text, re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    first, _, rest = text.partition(". ")
    if rest and len(first) <= 110:
        return first.strip(), rest.strip()
    if len(text) <= 170:
        return text, ""  # short enough to be its own title
    # Long single sentence: break at a natural pause, else a word boundary; the
    # body continues from there (never repeats the title).
    window = text[:110]
    for mark in (" — ", "; ", ": ", ", so ", ", and ", ", which ", ", "):
        k = window.rfind(mark)
        if k >= 40 and len(text) - k > 60:
            return window[:k].strip() + "…", "…" + text[k + len(mark):].strip()
    k = window.rsplit(" ", 1)[0]
    return k + "…", "…" + text[len(k):].strip()


def split_gist(body: str, limit: int = 220) -> tuple[str, str]:
    """First sentence (the gist) and the remainder."""
    parts = _SENTENCE.split(body.strip(), maxsplit=1)
    gist = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    if len(gist) > limit:
        cut = gist[:limit].rsplit(" ", 1)[0]
        return cut + "…", body
    return gist, rest


def key_numbers(text: str, limit: int = 4) -> list[str]:
    """Distinct figures worth a chip, percentages first."""
    found: list[str] = []
    for token in _NUM.findall(_plain(text)):
        token = token.strip()
        digits = re.sub(r"\D", "", token)
        if not digits or (len(digits) == 4 and digits.startswith(("19", "20")) and "%" not in token):
            continue  # skip bare years
        if token not in found:
            found.append(token)
    found.sort(key=lambda t: ("%" not in t and "pts" not in t))
    return found[:limit]


def fields_in(text: str, limit: int = 4) -> list[str]:
    seen: list[str] = []
    for f in re.findall(r"`([^`]{1,60})`", str(text)):
        if f not in seen and not f.replace(".", "").replace("_", "").isdigit():
            seen.append(f)
    return seen[:limit]


def _card(item: Any, accent: str, idx: str) -> str:
    title, body = split_item(item)
    gist, rest = split_gist(body) if body else ("", "")
    nums = key_numbers(f"{title} {body}")
    fields = [f for f in fields_in(f"{title} {body}") if f not in title]
    chips = "".join(f'<span class="{_num_class(n)} air-chip">{_e(n)}</span>' for n in nums)
    field_chips = "".join(f'<code class="air-field">{_e(f)}</code>' for f in fields)
    details = (f'<details class="air-details"><summary>Details</summary><div>{_inline(body)}</div></details>'
               if rest else "")
    return f"""
      <article class="air-card" style="--accent:{accent}" id="{idx}">
        <h5>{_inline(title)}</h5>
        {f'<p class="air-gist">{_inline(gist)}</p>' if gist else ''}
        {f'<div class="air-chips">{chips}{field_chips}</div>' if chips or field_chips else ''}
        {details}
      </article>"""


def _story(text: Any) -> str:
    body = " ".join(str(p).strip() for p in (text if isinstance(text, list) else [text]) if str(p).strip())
    sentences = _SENTENCE.split(body)
    lead, rest = " ".join(sentences[:2]), " ".join(sentences[2:])
    more = (f'<details class="air-details"><summary>Read the full story</summary><p>{_inline(rest)}</p></details>'
            if rest else "")
    return f"""
    <section class="air-story">
      <div class="air-kicker">📖 Data story</div>
      <p class="air-lead">{_inline(lead)}</p>
      {more}
    </section>"""


def _recommendations(recs: list[Any]) -> str:
    if not recs:
        return ""
    order = {"high": 0, "medium": 1, "low": 2}
    items = sorted((r for r in recs if isinstance(r, dict)), key=lambda r: order.get(str(r.get("severity", "low")).lower(), 3))
    counts = {s: sum(1 for r in items if str(r.get("severity", "")).lower() == s) for s in ("high", "medium", "low")}
    color = {"high": "var(--color-danger)", "medium": "var(--color-warning)", "low": "var(--color-info)"}
    cards = []
    for i, r in enumerate(items):
        sev = str(r.get("severity", "low")).lower()
        title, body = split_item(r.get("action", ""))
        gist, rest = split_gist(body) if body else ("", "")
        details = (f'<details class="air-details"><summary>Details</summary><div>{_inline(body)}</div></details>'
                   if rest else "")
        cards.append(f"""
        <article class="air-rec" style="--accent:{color.get(sev, 'var(--text-tertiary)')}">
          <div class="air-rec-head"><span class="air-sev" style="color:{color.get(sev)};border-color:{color.get(sev)}">{_e(sev)}</span>
            <span class="air-cat">{_e(str(r.get('category', '')))}</span></div>
          <h5>{_inline(title)}</h5>
          {f'<p class="air-gist">{_inline(gist)}</p>' if gist else ''}
          {details}
        </article>""")
    summary = " · ".join(
        f'<b style="color:{color[s]}">{n}</b> {s}' for s, n in counts.items() if n)
    preview = _preview([r.get("action", "") for r in items])
    return f"""
    <details class="air-section" style="--accent:var(--color-danger)">
      <summary class="air-head"><span class="air-caret">▸</span><h4>🛠 Recommendations</h4>
        <span class="air-count">{summary}</span><span class="air-sub">also in Verdict → Action Plan</span>
        {preview}</summary>
      <div class="air-grid">{''.join(cards)}</div>
    </details>"""


def _preview(texts: list[Any], n: int = 2) -> str:
    """First titles of a collapsed section, so it can be scanned without opening it."""
    titles = [_plain(split_item(t)[0]) for t in texts[:n] if t]
    if not titles:
        return ""
    more = f" +{len(texts) - n} more" if len(texts) > n else ""
    shown = " · ".join(_e(t if len(t) <= 70 else t[:67] + "…") for t in titles)
    return f'<span class="air-preview">{shown}{more}</span>'


CSS = """
<style>
.air-wrap { display:flex; flex-direction:column; gap:var(--space-lg); }
.air-banner { display:flex; flex-wrap:wrap; align-items:center; gap:10px; background:var(--bg-card);
  border:1px solid var(--border-primary); border-radius:var(--radius-lg); padding:12px 16px; }
.air-badge { background:var(--accent-gradient); color:#fff; font-weight:600; font-size:.78rem; padding:3px 10px; border-radius:999px; }
.air-meta { color:var(--text-secondary); font-size:.82rem; }
.air-meta code { font-family:var(--font-mono); color:var(--text-primary); }
.air-spacer { flex:1; }
.air-story { background:var(--bg-card); border:1px solid var(--border-primary); border-left:4px solid var(--accent-primary);
  border-radius:var(--radius-lg); padding:18px 20px; }
.air-kicker { font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; color:var(--text-tertiary); margin-bottom:6px; }
.air-lead { font-size:1.02rem; line-height:1.65; color:var(--text-primary); margin:0; }
.air-section { background:var(--bg-card); border:1px solid var(--border-primary); border-left:4px solid var(--accent);
  border-radius:var(--radius-lg); padding:12px 16px; }
.air-head { display:flex; flex-wrap:wrap; align-items:baseline; gap:10px; cursor:pointer; list-style:none; }
.air-head::-webkit-details-marker { display:none; }
details.air-section[open] > .air-head { margin-bottom:12px; }
.air-caret { color:var(--text-tertiary); display:inline-block; transition:transform 150ms; width:10px; }
details.air-section[open] > .air-head .air-caret { transform:rotate(90deg); }
.air-preview { flex-basis:100%; margin-left:20px; font-size:.8rem; color:var(--text-tertiary);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
details.air-section[open] > .air-head .air-preview { display:none; }
.air-head h4 { margin:0; font-size:1rem; color:var(--text-primary); }
.air-count { font-size:.78rem; color:var(--text-secondary); }
.air-sub { font-size:.8rem; color:var(--text-tertiary); }
.air-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:12px; }
.air-card, .air-rec { background:var(--bg-secondary); border:1px solid var(--border-primary); border-top:3px solid var(--accent);
  border-radius:var(--radius-md); padding:12px 14px; display:flex; flex-direction:column; gap:8px; }
.air-card h5, .air-rec h5 { margin:0; font-size:.92rem; line-height:1.4; color:var(--text-primary); font-weight:600; }
.air-gist { margin:0; font-size:.85rem; line-height:1.55; color:var(--text-secondary); }
.air-chips { display:flex; flex-wrap:wrap; gap:6px; }
.air-chip { padding:1px 8px; border-radius:999px; background:var(--bg-tertiary); font-size:.75rem; }
.air-num { font-weight:600; font-variant-numeric:tabular-nums; color:var(--color-warning); }
.air-pct { color:var(--color-info); }
.air-arrow { color:var(--accent-secondary); font-weight:700; }
code.air-field { font-family:var(--font-mono); font-size:.76rem; background:var(--bg-tertiary); color:var(--text-primary);
  padding:1px 6px; border-radius:4px; }
.air-details summary { cursor:pointer; font-size:.78rem; color:var(--accent-primary); list-style:none; }
.air-details summary::-webkit-details-marker { display:none; }
.air-details summary::before { content:'▸ '; }
.air-details[open] summary::before { content:'▾ '; }
.air-details > div, .air-details > p { margin:6px 0 0; font-size:.84rem; line-height:1.6; color:var(--text-secondary); }
.air-rec-head { display:flex; gap:8px; align-items:center; }
.air-sev { text-transform:uppercase; font-size:.68rem; font-weight:700; border:1px solid; border-radius:999px; padding:0 8px; }
.air-cat { font-size:.75rem; color:var(--text-tertiary); }
</style>
"""

JS = """
<script>
(function(){
  var root = document.getElementById('air-root'); if (!root) return;
  root.querySelectorAll('[data-air-toggle]').forEach(function(btn){
    btn.addEventListener('click', function(){
      // Expand all opens every section (card details stay one click away); Collapse all closes everything.
      var open = btn.dataset.airToggle === 'open';
      root.querySelectorAll(open ? 'details.air-section' : 'details').forEach(function(d){ d.open = open; });
    });
  });
})();
</script>
"""


def render_ai_review(ai: dict[str, Any] | None) -> str:
    if not ai or not ai.get("enabled"):
        err = _e(str((ai or {}).get("error", "")))
        return (f'{CSS}<div class="air-section"><h4>AI review not available for this run</h4>'
                f'<p class="dl-muted">{err or "Run with --ai auto (or claude / anthropic / openai …) to add it."}</p></div>')
    sections = ai.get("sections") or {}
    blocks = []
    for key, title, icon, accent, what in SECTIONS:
        body = sections.get(key) or ai.get(key)
        if not body:
            continue
        items = body if isinstance(body, list) else [p for p in re.split(r"\n+(?=- |\* |\*\*)", str(body)) if p.strip()]
        cards = "".join(_card(it, accent, f"air-{key}-{i}") for i, it in enumerate(items))
        blocks.append(f"""
    <details class="air-section" style="--accent:{accent}">
      <summary class="air-head"><span class="air-caret">▸</span><h4>{icon} {_e(title)}</h4>
        <span class="air-count"><b>{len(items)}</b> finding{'s' if len(items) != 1 else ''}</span>
        <span class="air-sub">{_e(what)}</span>{_preview(items)}</summary>
      <div class="air-grid">{cards}</div>
    </details>""")
    model = ai.get("model") or "auto"
    story = sections.get("data_story") or ai.get("data_story")
    return f"""{CSS}
    <div class="air-wrap" id="air-root">
      <div class="air-banner">
        <span class="air-badge">✨ AI review</span>
        <span class="air-meta">Provider <b>{_e(str(ai.get('provider', '')))}</b> · model <code>{_e(str(model))}</code>
          · auth {_e(str(ai.get('auth_mode', '')))}</span>
        <span class="air-spacer"></span>
        <button class="dl-btn" type="button" data-air-toggle="open" title="Open every section">⊞ Expand all</button>
        <button class="dl-btn" type="button" data-air-toggle="close" title="Close every section and detail">⊟ Collapse all</button>
      </div>
      {f'<p class="dl-muted" style="margin:0;color:var(--color-warning)">⚠ {_e(ai["model_note"])}</p>' if ai.get("model_note") else ''}
      <p class="dl-muted" style="margin:0">Model-written review of the profiling results. Numbers are highlighted;
        open <b>Details</b> for the full reasoning. Verify before production or compliance decisions.</p>
      {_story(story) if story else ''}
      {_recommendations(ai.get('recommendations') or [])}
      {''.join(blocks)}
    </div>
    {JS}"""
