import pytest

from beatcrate import config


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Points every user-data path at a temporary directory."""
    for name, value in {
        "DATA": tmp_path,
        "SESSION_FILE": tmp_path / "session.json",
        "LIBRARY_FILE": tmp_path / "library.json",
        "PROFILE_FILE": tmp_path / "profile.json",
        "CANDIDATES_FILE": tmp_path / "candidates.json",
        "CRATES_DIR": tmp_path / "crates",
        "STATE_FILE": tmp_path / "state.json",
        "LOCK_FILE": tmp_path / ".lock",
        "MARKS_DIR": tmp_path / "marks",
        "CONSENT_FILE": tmp_path / "consent.json",
    }.items():
        monkeypatch.setattr(config, name, value)
    return tmp_path
