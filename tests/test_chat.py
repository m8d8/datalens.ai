"""Chat: read-only SQL workspace, PII masking, provider-agnostic loop, localhost server guards."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner

from datalens.chat import ChatSession, RunWorkspace, answer_to_markdown
from datalens.chat.server import serve
from datalens.cli import cli


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("chat")
    data = tmp / "data"
    data.mkdir()
    (data / "users.jsonl").write_text("".join(
        json.dumps({"user_id": f"u{i}", "email": f"person{i}@example.com", "plan": "pro" if i % 3 else "free",
                    "address": {"city": "Pune" if i % 2 else "Delhi"}, "tags": ["a", "b"][: i % 3]}) + "\n"
        for i in range(120)))
    out = tmp / "out"
    result = CliRunner().invoke(cli, ["analyze", "-s", "file", "-p", str(data), "-o", str(out), "--version-tag", "r1"])
    assert result.exit_code == 0, result.output
    return next(p for p in out.iterdir() if p.is_dir() and not p.name.startswith("."))


class ScriptedProvider:
    """Replays canned model replies; records prompts."""

    name = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, prompt, **_):
        self.prompts.append(prompt)
        return True, self.replies.pop(0)


def test_workspace_builds_flattened_masked_tables(run_dir):
    ws = RunWorkspace(run_dir)
    assert ws.connection() is not None, ws.load_error
    assert set(ws.tables) == {"users"}
    assert "address.city" in ws.tables["users"] and "tags" in ws.tables["users"]
    res = ws.query('SELECT "address.city" AS city, COUNT(*) AS n FROM users GROUP BY 1 ORDER BY 1')
    assert res["rows"] == [["Delhi", 60], ["Pune", 60]]
    emails = ws.query("SELECT email FROM users")["rows"]
    assert all("***@" in r[0] for r in emails), "PII must be masked in the SQL sample"


@pytest.mark.parametrize("sql", [
    "DELETE FROM users",
    "SELECT 1; DROP TABLE users",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "PRAGMA table_info(users)",
    "WITH x AS (SELECT 1) INSERT INTO users(user_id) SELECT * FROM x",
])
def test_sql_guard_blocks_anything_but_reads(run_dir, sql):
    assert "error" in RunWorkspace(run_dir).query(sql)


def test_chat_loop_runs_sql_then_answers(run_dir):
    ws = RunWorkspace(run_dir)
    provider = ScriptedProvider([
        '{"action":"sql","query":"SELECT plan, COUNT(*) AS n FROM users GROUP BY 1 ORDER BY 2 DESC","why":"plan mix"}',
        '```json\n{"action":"answer","markdown":"**pro** is the most common plan (80 of 120).","use_table":true}\n```',
    ])
    reply = ChatSession(ws, provider).ask("Which plan is most common?")
    assert reply["ok"] and "pro" in reply["markdown"]
    assert reply["table"]["rows"][0] == ["pro", 80]
    assert reply["steps"][0]["sql"].startswith("SELECT plan")
    assert "[you ran]" in provider.prompts[1]  # the result was fed back
    assert "person1@example.com" not in provider.prompts[0]  # context is masked
    md = answer_to_markdown("Which plan is most common?", reply)
    assert "| plan | n |" in md and "```sql" in md


def test_chat_accepts_plain_text_from_models_that_ignore_the_protocol(run_dir):
    reply = ChatSession(RunWorkspace(run_dir), ScriptedProvider(["Just a plain answer."])).ask("hi")
    assert reply["ok"] and reply["markdown"] == "Just a plain answer."


def test_server_requires_token_and_localhost(run_dir):
    ws = RunWorkspace(run_dir)
    provider = ScriptedProvider(['{"action":"answer","markdown":"ok"}'])
    server, url = serve(ws, provider, port=18765)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        page = urllib.request.urlopen(url).read().decode()
        assert "Ask Datalens" in page and "DATALENS_CHAT" in page
        token = page.split('"token": "')[1].split('"')[0]

        def post(tok):
            req = urllib.request.Request(url + "api/chat", data=json.dumps({"question": "q"}).encode(),
                                         headers={"Content-Type": "application/json", "X-Datalens-Token": tok})
            return json.loads(urllib.request.urlopen(req).read())

        with pytest.raises(urllib.error.HTTPError) as err:
            post("wrong")
        assert err.value.code == 403
        assert post(token)["markdown"] == "ok"

        bad_host = urllib.request.Request(url, headers={"Host": "evil.example:18765"})
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(bad_host)
        assert err.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
