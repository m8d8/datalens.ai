# Persona Views in Datalens Reports

The Datalens HTML report includes a **persona toggle** that adapts the report content and language for different audiences. A single report serves both business stakeholders and technical users without overwhelming either.

There are **two views**: **Business** and **Technical** (the default). They differ in which tabs are shown and the wording of a few summaries — all data is always available by switching views.

> **History:** earlier builds had three personas (Business / Analyst / Engineer), but Analyst and Engineer rendered identically (the Engineer-only extras were never implemented). They were merged into a single **Technical** view. Legacy `analyst`/`engineer` selections saved in a browser are automatically migrated to `technical`.

## Quick Reference

| Feature | 🧑‍💼 Business | 🛠️ Technical (default) |
|---------|-------------|------------------------|
| **Target audience** | Product managers, executives, compliance, content producers | Data analysts, BI developers, data engineers |
| **Focus** | What does this data mean for the business? | What patterns, quality issues, and structure exist? |
| **Language** | Plain English, business metrics | Full technical detail (coverage %, distinct counts, raw values) |
| **Hidden tabs** | Field Explorer, Type Warnings | None |

---

## 🧑‍💼 Business

**Who it's for:** Product managers, business analysts, executives, compliance officers, content producers.

**What they see:**
- ✅ **Overview** — Executive summary: health verdict, score, risk level, top actions
- ✅ **Insights** — Data story (plain English), SWOT, recommendations
- ✅ **Data Quality** — DQI grade and quality-dimension summary
- ✅ **PII Detection** — High-risk fields, compliance concerns
- ✅ **Coverage** — Heat map of which fields are populated
- ✅ **Relationships / Cross-Object** — ER diagram, keys, join candidates
- ✅ **Distributions / Patterns** — Value distributions, detected patterns
- ✅ **Trends & Drift** — Schema changes over time

**What's hidden:**
- ❌ **Field Explorer** — field-level detail (types, cardinality, null counts)
- ❌ **Type Warnings** — multi-type field warnings (a developer concern)

**Language adaptations:**
- Cover subtitle: *"Analysis of your data structure, quality, and relationships"*

---

## 🛠️ Technical (default)

**Who it's for:** Data analysts, BI developers, analytics engineers, data scientists, data engineers, ETL/schema developers.

**What they see:**
- ✅ **Everything the Business view shows**, plus:
- ✅ **Field Explorer** — full field inventory (coverage %, null/empty %, types, cardinality)
- ✅ **Type Warnings** — multi-type fields that may cause parsing issues

**Language adaptations:**
- Cover subtitle: *"Profiling N collections with N fields across N sampled records"*
- Technical metrics shown (coverage percentages, distinct counts, raw values)

This is the **default** view.

---

## Tab Visibility Matrix

| Tab | Business | Technical |
|-----|:--------:|:---------:|
| Overview | ✅ | ✅ |
| Insights | ✅ | ✅ |
| Coverage | ✅ | ✅ |
| Data Quality | ✅ | ✅ |
| PII Detection | ✅ | ✅ |
| **Field Explorer** | ❌ | ✅ |
| **Type Warnings** | ❌ | ✅ |
| Relationships | ✅ | ✅ |
| Cross-Object | ✅ | ✅ |
| Distributions | ✅ | ✅ |
| Patterns | ✅ | ✅ |
| Trends & Drift | ✅ | ✅ |

---

## Chapter Organization

Tabs are grouped into 5 narrative chapters (independent of the persona view):

| Chapter | Icon | Tabs | Purpose |
|---------|------|------|---------|
| **Verdict** | 📊 | Overview | Executive summary, health score, actions |
| **Shape** | 💡 | Insights, Coverage | What the data looks like, content mix |
| **Health** | ✅ | Data Quality, PII, Type Warnings | Where it's broken or risky |
| **Structure** | 🔗 | Field Explorer, Relationships, Cross-Object | How data connects, keys |
| **Fingerprint** | 🔬 | Distributions, Patterns, Trends | Domain patterns, drift |

---

## How It Works

### HTML attributes

Tabs/sections hidden from a persona use `data-persona-hide` (space-separated persona names):

```html
<button class="tab" data-tab="field-explorer" data-persona-hide="business">
    Field Explorer
</button>
```

Content sections can also be tagged:

```html
<div class="tech-only">
    <!-- Hidden from the Business view -->
</div>
```

### Language switching

Dual-language spans render different text per view:

```html
<span class="biz-lang">Analysis of your data</span>
<span class="tech-lang">Profiling 6 collections with 220 fields</span>
```

### CSS rules

```css
/* Hide from Business */
[data-persona="business"] [data-persona-hide~="business"],
[data-persona="business"] .tech-only { display: none !important; }

/* Hide from Technical (reserved; nothing tagged today) */
[data-persona="technical"] [data-persona-hide~="technical"] { display: none !important; }

/* Language switching */
[data-persona="business"] .tech-lang { display: none; }
[data-persona="business"] .biz-lang { display: inline; }
.biz-lang { display: none; }
[data-persona="technical"] .biz-lang { display: none; }
```

### Persistence

The selected view is saved to `localStorage` and persists across sessions (legacy `analyst`/`engineer` values are migrated to `technical` on load):

```javascript
function setPersona(persona) {
    document.body.setAttribute('data-persona', persona);
    localStorage.setItem('datalens-persona', persona);
}
```

---

## Extending persona differences

- **Hide a tab from Business:** add `"business"` to the tab's `persona_hide` slot in `_build_tabs()`.
- **Hide a section from Business:** add `class="tech-only"` or `data-persona-hide="business"`.
- **Switch language:** use `<span class="biz-lang">` and `<span class="tech-lang">`.

The `technical` persona-hide hook exists but nothing is tagged with it today — add it only if a future need arises (e.g. a Business-only simplification that should also hide from Technical).

---

## Design principles

1. **No data loss** — both views can reach all data by switching.
2. **Progressive disclosure** — Business starts simple; Technical reveals full detail.
3. **Language adaptation** — use the audience's vocabulary.
4. **One report, two views** — a single artifact serves multiple stakeholders.
5. **Persistence** — remember the user's preference.
