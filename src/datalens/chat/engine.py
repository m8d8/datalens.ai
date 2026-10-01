"""
Chat engine — answer questions about a run, using SQL on its (masked) data when needed.

Provider-agnostic: every provider only needs ``complete(prompt)``. The model is
asked to reply with one JSON object per turn:

    {"action": "sql", "query": "SELECT …", "why": "what this checks"}
    {"action": "answer", "markdown": "…", "use_table": true}

Up to MAX_STEPS SQL calls are allowed per question; each result (or error) is
fed back. The final answer carries the last successful table so the UI can
offer it as CSV, and every SQL step is shown to the user — no hidden work.
"""

from __future__ import annotations

import json
from typing import Any

from datalens.ai.response import extract_json_from_text
from datalens.chat.workspace import RunWorkspace

MAX_STEPS = 4

SYSTEM = """You are Datalens, a careful data analyst answering questions about ONE profiling run.
You know: the run summary, field profiles, drift findings, expected-schema checks and actions below.
You can also query a sample of the data with SQLite (read-only).

Rules:
- Reply with exactly ONE JSON object, nothing else.
- To look at data: {"action":"sql","query":"SELECT ...","why":"..."}  (SQLite dialect; quote dotted column names
  like "runs.batter"; arrays are JSON text — use json_each / json_extract; always LIMIT large results to <= 50 rows)
- To answer: {"action":"answer","markdown":"...","use_table":true|false}
  Answer in concise markdown. Cite numbers you saw. Say when a number comes from a sample.
  Set use_table true when the last query result is the answer's table.
- Fields marked [PII] are masked; never try to reconstruct personal data.
- If the question can't be answered from what you have, say so and suggest the Datalens command or check that would.
"""


def _render_result(result: dict[str, Any], limit: int = 30) -> str:
    if "error" in result:
        return f"ERROR: {result['error']}"
    cols, rows = result["columns"], result["rows"]
    lines = [" | ".join(cols)] + [" | ".join("" if v is None else str(v) for v in r) for r in rows[:limit]]
    more = f"\n(… {len(rows) - limit} more rows)" if len(rows) > limit else ""
    trunc = "\n(result truncated at the row cap)" if result.get("truncated") else ""
    return "\n".join(lines) + more + trunc


class ChatSession:
    def __init__(self, workspace: RunWorkspace, provider: Any) -> None:
        self.ws = workspace
        self.provider = provider

    def ask(self, question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Answer one question (history = earlier [{role, content}] turns). Never raises."""
        transcript = []
        for turn in (history or [])[-8:]:
            role = "User" if turn.get("role") == "user" else "Datalens"
            transcript.append(f"{role}: {turn.get('content', '')[:2000]}")
        steps: list[dict[str, Any]] = []
        last_table: dict[str, Any] | None = None
        base = (f"{SYSTEM}\n\n=== RUN CONTEXT ===\n{self.ws.context_text()}\n\n=== SQL TABLES (sample) ===\n"
                f"{self.ws.tables_text()}\n\n=== CONVERSATION ===\n" + "\n".join(transcript)
                + f"\nUser: {question}\n")

        for _ in range(MAX_STEPS + 1):
            tool_log = "".join(
                f"\n[you ran] {s['sql']}\n[result]\n{_render_result(s['result'])}\n" for s in steps)
            prompt = base + tool_log + ("\nReply with the next JSON action." if steps else "\nReply with a JSON action.")
            ok, text = self.provider.complete(prompt)
            if not ok:
                return {"ok": False, "error": text, "steps": steps}
            action = extract_json_from_text(text) or {}
            kind = str(action.get("action", "")).lower()
            if kind == "sql" and len(steps) < MAX_STEPS:
                sql = str(action.get("query", ""))
                result = self.ws.query(sql)
                steps.append({"sql": sql, "why": action.get("why", ""), "result": result})
                if "error" not in result:
                    last_table = result
                continue
            if kind == "answer" or action.get("markdown"):
                table = last_table if action.get("use_table") and last_table else None
                return {"ok": True, "markdown": str(action.get("markdown", "")), "table": table, "steps": steps}
            # Model didn't follow the protocol: treat its text as the answer.
            return {"ok": True, "markdown": text.strip(), "table": None, "steps": steps}
        return {"ok": True, "markdown": "I ran out of query steps; here is what I found so far.",
                "table": last_table, "steps": steps}


def answer_to_markdown(question: str, reply: dict[str, Any]) -> str:
    """Markdown export of one Q&A, including the SQL that was run."""
    out = [f"## Q: {question}", ""]
    if not reply.get("ok"):
        return "\n".join(out + [f"_Error: {reply.get('error')}_", ""])
    out += [reply.get("markdown", ""), ""]
    table = reply.get("table")
    if table:
        out.append("| " + " | ".join(table["columns"]) + " |")
        out.append("|" + "---|" * len(table["columns"]))
        out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in table["rows"][:50]]
        out.append("")
    for s in reply.get("steps", []):
        out += ["<details><summary>SQL</summary>", "", "```sql", s["sql"], "```", "</details>", ""]
    return "\n".join(out)


def json_default(value: Any) -> Any:
    return str(value)


def dumps(data: Any) -> str:
    return json.dumps(data, default=json_default)
