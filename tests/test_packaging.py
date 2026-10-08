import runpy
import sys
from pathlib import Path

import pytest

ENTRY = str(Path(__file__).parent.parent / "packaging" / "beat50_app.py")


@pytest.mark.parametrize("argv, expected", [
    ([], ["app"]),
    (["-psn_0_12345"], ["app"]),
    (["generate"], ["generate"]),
])
def test_entry_point_runs_app_on_double_click(monkeypatch, argv, expected):
    import beat50.cli
    calls = []
    monkeypatch.setattr(beat50.cli, "main", lambda args: calls.append(args) or 0)
    monkeypatch.setattr(sys, "argv", ["beat50"] + argv)
    with pytest.raises(SystemExit) as e:
        runpy.run_path(ENTRY, run_name="__main__")
    assert e.value.code == 0
    assert calls == [expected]


def test_entry_point_logs_a_crash_and_exits_with_an_error(monkeypatch, capsys):
    import beat50.cli

    def crash(args):
        raise OSError("[Errno 48] Address already in use")
    monkeypatch.setattr(beat50.cli, "main", crash)
    monkeypatch.setattr(sys, "argv", ["beat50"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(ENTRY, run_name="__main__")
    assert e.value.code == 1
    assert "Address already in use" in capsys.readouterr().err
