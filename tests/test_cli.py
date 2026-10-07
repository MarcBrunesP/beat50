import pytest

from beatcrate import cli


def test_no_arguments_returns_an_error_without_crashing(capsys):
    assert cli.main([]) == 2


def test_lists_the_subcommands_in_the_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    for sub in ("login", "ingest", "generate", "app"):
        assert sub in out


def test_the_help_is_in_english(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "sign in to Beatport" in out
    assert "make a new selection" in out


def test_the_help_does_not_mention_chrome(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "Chrome" not in capsys.readouterr().out


@pytest.fixture
def window_loop(monkeypatch):
    """Records that a command ran inside beatcrate.webkit.run (the window loop) and runs it there."""
    ran = []

    def run(work):
        ran.append(True)
        return work()
    monkeypatch.setattr(cli.webkit, "run", run)
    return ran


def test_login_runs_inside_the_window_loop(window_loop, monkeypatch):
    called = []
    monkeypatch.setattr(cli.auth, "login", lambda: called.append("login"))
    assert cli.main(["login"]) == 0
    assert window_loop == [True] and called == ["login"]


def test_generate_runs_inside_the_window_loop(window_loop, monkeypatch, tmp_path, capsys):
    crate = tmp_path / "20261001_080000.json"
    crate.write_text('{"id": "20261001_080000", "tracks": [], "short": false, "candidates_seen": 0}')
    monkeypatch.setattr(cli.jobs, "generate", lambda trigger: crate)
    assert cli.main(["generate"]) == 0
    assert window_loop == [True]
    assert "Selection 20261001_080000" in capsys.readouterr().out


def test_ingest_runs_inside_the_window_loop(window_loop, monkeypatch):
    monkeypatch.setattr(cli, "_client", lambda: pytest.fail("stop here"))
    with pytest.raises(pytest.fail.Exception):
        cli.main(["ingest"])
    assert window_loop == [True]


def test_there_is_no_send_command():
    with pytest.raises(SystemExit):
        cli.main(["send"])


def test_there_is_no_run_command():
    with pytest.raises(SystemExit):
        cli.main(["run"])
