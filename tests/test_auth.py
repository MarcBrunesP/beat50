import json
import stat

import pytest

from beat50 import auth


def test_save_session_writes_with_0600_permissions(tmp_path, monkeypatch):
    target = tmp_path / "session.json"
    monkeypatch.setattr(auth.config, "SESSION_FILE", target)
    auth.save_session("test-token")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert json.loads(target.read_text())["access_token"] == "test-token"


def test_load_session_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.config, "SESSION_FILE", tmp_path / "missing.json")
    assert auth.load_session() is None


def test_load_session_reads_what_save_wrote(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.config, "SESSION_FILE", tmp_path / "session.json")
    auth.save_session("abc")
    assert auth.load_session()["access_token"] == "abc"


class Clock:
    """Fake time: sleeping moves the clock forward instantly."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s


class FakeWindows:
    """Stands in for beat50.webkit. `tokens` is what the page answers on each read."""

    def __init__(self, tokens=(), closes_after=None):
        self.tokens = list(tokens)
        self.reads = 0
        self.closes_after = closes_after
        self.opened = []
        self.loads = []
        self.closed = []

    def open_window(self, url, title="beat50", hidden=False):
        self.opened.append({"url": url, "title": title, "hidden": hidden})
        return "W"

    def read_token(self, window):
        self.reads += 1
        return self.tokens.pop(0) if self.tokens else None

    def is_open(self, window):
        return window not in self.closed and (self.closes_after is None or self.reads < self.closes_after)

    def load(self, window, url):
        self.loads.append(url)

    def close(self, window):
        self.closed.append(window)


@pytest.fixture
def windows(monkeypatch, data_dir):
    clock = Clock()
    monkeypatch.setattr(auth.time, "time", clock.time)
    monkeypatch.setattr(auth.time, "sleep", clock.sleep)
    monkeypatch.setattr(auth, "token_is_valid", lambda t: t.startswith("good"))

    def install(**kw):
        fake = FakeWindows(**kw)
        for name in ("open_window", "read_token", "is_open", "load", "close"):
            monkeypatch.setattr(auth.webkit, name, getattr(fake, name))
        return fake
    return install


def test_get_token_reads_it_in_a_hidden_window_and_saves_it(windows):
    w = windows(tokens=[None, "good-1"])
    assert auth.get_token() == "good-1"
    assert w.opened == [{"url": "https://www.beatport.com", "title": "beat50", "hidden": True}]
    assert w.closed == ["W"]
    assert auth.load_session()["access_token"] == "good-1"


def test_get_token_skips_a_stale_token(windows):
    windows(tokens=["stale", "good-2"])
    assert auth.get_token() == "good-2"


def test_with_a_dormant_session_it_reloads_the_store_to_force_the_relogin(windows):
    w = windows(tokens=[None] * 15 + ["good-3"])
    assert auth.get_token() == "good-3"
    assert w.loads == ["https://www.beatport.com"]


def test_when_the_token_comes_at_once_it_does_not_reload(windows):
    w = windows(tokens=["good-4"])
    auth.get_token()
    assert w.loads == []


def test_without_a_session_get_token_raises_session_expired_and_closes_the_window(windows):
    w = windows()
    with pytest.raises(auth.SessionExpired) as e:
        auth.get_token()
    assert e.value.code == "session_expired"
    assert w.closed == ["W"]
    assert auth.load_session() is None


def test_wait_for_login_saves_the_token_and_closes_the_window(windows):
    w = windows(tokens=[None, None, "good-5"])
    window = auth.login_window()
    assert w.opened[0]["hidden"] is False
    assert auth.wait_for_login(window) == "good-5"
    assert w.closed == ["W"]
    assert auth.load_session()["access_token"] == "good-5"


def test_wait_for_login_ends_when_the_user_closes_the_window(windows):
    w = windows(closes_after=3)
    window = auth.login_window()
    assert auth.wait_for_login(window) is None
    assert w.reads == 3
    assert auth.load_session() is None


def test_wait_for_login_gives_up_after_its_time(windows):
    w = windows()
    assert auth.wait_for_login(auth.login_window()) is None
    assert w.closed == ["W"]


def test_login_from_the_terminal_without_signing_in_raises_session_expired(windows, capsys):
    windows()
    with pytest.raises(auth.SessionExpired):
        auth.login()
    assert "Sign in to Beatport in the window" in capsys.readouterr().out


def test_a_window_closed_from_outside_is_not_an_expired_session(windows):
    windows(closes_after=2)  # the app quit while the token was being read
    with pytest.raises(auth.Interrupted) as e:
        auth.get_token()
    assert e.value.code == "interrupted"
    assert not isinstance(e.value, auth.SessionExpired)
