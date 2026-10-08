import importlib
from pathlib import Path

from beat50 import config


def test_score_weights_add_up_to_one():
    total = config.W_LABEL + config.W_ARTIST + config.W_GENRE + config.W_BPM + config.W_KEY
    assert abs(total - 1.0) < 1e-9


def test_paths_hang_from_data():
    assert config.SESSION_FILE.parent == config.DATA
    assert config.CRATES_DIR.parent == config.DATA


def _reload(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("BEAT50_DATA", raising=False)
    else:
        monkeypatch.setenv("BEAT50_DATA", value)
    try:
        return importlib.reload(config).DATA
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_data_lives_in_application_support(monkeypatch):
    assert _reload(monkeypatch, None) == Path.home() / "Library" / "Application Support" / "beatcrate"


def test_empty_beat50_data_also_falls_back_to_application_support(monkeypatch):
    assert _reload(monkeypatch, "") == Path.home() / "Library" / "Application Support" / "beatcrate"


def test_beat50_data_moves_the_folder(monkeypatch, tmp_path):
    assert _reload(monkeypatch, str(tmp_path)) == tmp_path
