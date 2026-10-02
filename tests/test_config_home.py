"""Config folder lookup (--config-dir / DATALENS_CONFIG_DIR), `init`, `connection-new`, `config-show`."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from datalens.cli import cli
from datalens.config import ConnectionLoader, load_config
from datalens.config.home import ENV_VAR, config_dirs
from datalens.config.scaffold import init_config_dir

CONN = "name: {name}\nsource_type: file\nparams:\n  path: {path}\n"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Run every test from an empty project with an empty home."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delenv("DATALENS_ENV", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    yield
    os.environ.pop(ENV_VAR, None)  # the CLI callback sets it in-process


def _folder(root: Path, *, sample_size: int, conn: str) -> Path:
    (root / "connections").mkdir(parents=True)
    (root / "config.yaml").write_text(f"sample_size: {sample_size}\n")
    (root / "connections" / f"{conn}.yaml").write_text(CONN.format(name=conn, path="/data"))
    return root


def test_default_lookup_is_project_then_home(tmp_path):
    assert config_dirs() == [Path.cwd() / ".datalens", Path.home() / ".datalens"]
    _folder(Path.home() / ".datalens", sample_size=111, conn="home_conn")
    assert load_config().sample_size == 111
    _folder(Path.cwd() / ".datalens", sample_size=222, conn="proj_conn")
    assert load_config().sample_size == 222                      # project-local wins
    names = [n for n, _ in ConnectionLoader().list_connections()]
    assert names == ["home_conn", "proj_conn"]                   # both folders are listed


def test_explicit_config_dir_is_exclusive(tmp_path, monkeypatch):
    _folder(Path.cwd() / ".datalens", sample_size=222, conn="proj_conn")
    ext = _folder(tmp_path / "server" / "conf", sample_size=333, conn="ext_conn")
    monkeypatch.setenv(ENV_VAR, str(ext))
    assert config_dirs() == [ext]
    assert load_config().sample_size == 333
    assert [n for n, _ in ConnectionLoader().list_connections()] == ["ext_conn"]
    with pytest.raises(FileNotFoundError, match="Looked in"):
        ConnectionLoader().load_connection("proj_conn")       # the project's own folder is not used


def test_cc_accepts_a_direct_file_path_without_slash(tmp_path):
    (Path.cwd() / "mine.yaml").write_text(CONN.format(name="other_name", path="/data"))
    cfg = ConnectionLoader().load_connection("mine.yaml")
    assert cfg.name == "other_name"


def test_listing_does_not_need_env_vars(tmp_path):
    d = Path.cwd() / ".datalens" / "connections"
    d.mkdir(parents=True)
    (d / "needs_var.yaml").write_text(CONN.format(name="needs_var", path="${UNSET_DATA_DIR_X}/f.csv"))
    assert ("needs_var", "file") in ConnectionLoader().list_connections()


def test_init_scaffold_is_complete_private_and_idempotent(tmp_path):
    target = tmp_path / "conf"
    results = dict((p.name, st) for p, st in init_config_dir(target))
    assert results == {"config.yaml": "created", "secrets.yaml": "created", ".env": "created",
                       ".gitignore": "created", "my_files.yaml": "created"}
    assert "secrets.yaml" in (target / ".gitignore").read_text()
    if os.name == "posix":
        assert stat.S_IMODE((target / "secrets.yaml").stat().st_mode) == 0o600
    cfg = yaml.safe_load((target / "config.yaml").read_text())
    assert {"sample_size", "sample_strategy", "out_dir"} <= set(cfg)
    conn = yaml.safe_load((target / "connections" / "my_files.yaml").read_text())
    assert conn["name"] == "my_files" and conn["source_type"] == "file"
    (target / "config.yaml").write_text("sample_size: 5\n")
    assert all(st == "kept" for _, st in init_config_dir(target))     # never overwrites without force
    assert (target / "config.yaml").read_text() == "sample_size: 5\n"


def test_cli_init_connection_new_and_config_show(tmp_path, monkeypatch):
    import io

    from rich.console import Console

    buf = io.StringIO()
    monkeypatch.setattr("datalens.cli.console", Console(file=buf, width=200))
    runner = CliRunner()
    conf = tmp_path / "conf"
    assert runner.invoke(cli, ["init", str(conf)]).exit_code == 0
    data = tmp_path / "data"
    data.mkdir()
    r = runner.invoke(cli, ["connection-new", "orders", "--source", "file", "--path", str(data),
                            "--config-dir", str(conf)])
    assert r.exit_code == 0, r.output
    written = yaml.safe_load((conf / "connections" / "orders.yaml").read_text())
    assert written["params"]["path"] == str(data.resolve())
    again = runner.invoke(cli, ["connection-new", "orders", "--source", "file", "--config-dir", str(conf)])
    assert again.exit_code != 0 and "already exists" in again.output   # UsageError goes to click's stderr
    buf.truncate(0)
    show = runner.invoke(cli, ["--config-dir", str(conf), "config-show"])
    assert show.exit_code == 0 and "only this folder" in buf.getvalue() and "orders" in buf.getvalue()


def test_out_dir_comes_from_config_when_flag_omitted(tmp_path):
    from datalens.cli import _resolve_out_dir

    d = Path.cwd() / ".datalens"
    d.mkdir()
    (d / "config.yaml").write_text("out_dir: reports\n")
    assert _resolve_out_dir(None) == "reports"
    assert _resolve_out_dir("explicit") == "explicit"
