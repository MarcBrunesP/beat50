import io
import json
import urllib.error

import pytest

from beatcrate import client
from beatcrate.client import Client, TokenExpired
from beatcrate.errors import BeatcrateError


class FakeAPI:
    """Stands in for Client._fetch so pagination can be tested without a network."""

    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.pages.pop(0)


def test_paged_walks_until_next_is_null(monkeypatch):
    fake = FakeAPI([
        {"results": [{"id": 1}, {"id": 2}], "next": "something", "count": 3},
        {"results": [{"id": 3}], "next": None, "count": 3},
    ])
    c = Client("tok")
    monkeypatch.setattr(c, "_fetch", fake)
    assert [t["id"] for t in c.paged("/catalog/tracks/")] == [1, 2, 3]
    assert "page=1" in fake.urls[0] and "page=2" in fake.urls[1]


def test_get_builds_the_query_from_the_params(monkeypatch):
    fake = FakeAPI([{"results": [], "next": None}])
    c = Client("tok")
    monkeypatch.setattr(c, "_fetch", fake)
    c.get("/catalog/tracks/", label_id="1,2", publish_date="2026-08-01:2026-09-01")
    assert "label_id=1%2C2" in fake.urls[0]
    assert "publish_date=2026-08-01%3A2026-09-01" in fake.urls[0]


def test_paged_stops_at_the_page_cap(monkeypatch):
    fake = FakeAPI([{"results": [{"id": i}], "next": "more"} for i in range(5)])
    c = Client("tok")
    monkeypatch.setattr(c, "_fetch", fake)
    assert len(c.paged("/catalog/tracks/", max_pages=3)) == 3


def _http_error(code):
    return urllib.error.HTTPError("https://api", code, "x", {}, io.BytesIO(b""))


def test_fetch_turns_a_401_into_token_expired(monkeypatch):
    def urlopen(req, timeout):
        raise _http_error(401)
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    with pytest.raises(TokenExpired) as err:
        Client("tok").get("/my/account/")
    assert err.value.code == "session_expired"
    assert isinstance(err.value, BeatcrateError)


def test_fetch_retries_5xx_errors(monkeypatch):
    responses = [_http_error(503), io.BytesIO(b'{"ok": true}')]

    def urlopen(req, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    c = Client("tok")
    assert c.get("/catalog/tracks/") == {"ok": True}
    assert c.requests == 2


def test_fetch_gives_up_after_the_retry_limit(monkeypatch):
    calls, sleeps = [], []

    def urlopen(req, timeout):
        calls.append(1)
        raise _http_error(503)
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    with pytest.raises(urllib.error.HTTPError):
        Client("tok").get("/catalog/tracks/")
    assert len(calls) == client.RETRIES
    assert sleeps == [client.BACKOFF_BASE ** n for n in range(1, client.RETRIES)]


def test_fetch_renews_the_token_once_on_a_401(monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append(req.get_header("Authorization"))
        if len(sent) == 1:
            raise _http_error(401)
        return io.BytesIO(b'{"ok": true}')
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    renewals = []
    c = Client("old", renew=lambda: renewals.append(1) or "new")
    assert c.get("/my/downloads/") == {"ok": True}
    assert sent == ["Bearer old", "Bearer new"]
    assert len(renewals) == 1


def test_fetch_does_not_renew_twice(monkeypatch):
    def urlopen(req, timeout):
        raise _http_error(401)
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    renewals = []
    c = Client("old", renew=lambda: renewals.append(1) or "new")
    with pytest.raises(TokenExpired):
        c.get("/my/downloads/")
    assert len(renewals) == 1


def test_renewing_does_not_use_up_the_5xx_retries(monkeypatch):
    responses = [_http_error(503), _http_error(503), _http_error(401), io.BytesIO(b'{"ok": true}')]

    def urlopen(req, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    assert Client("old", renew=lambda: "new").get("/my/downloads/") == {"ok": True}


def test_post_sends_json_and_returns_the_response(monkeypatch):
    seen = []

    def urlopen(req, timeout):
        seen.append((req.get_method(), req.full_url, json.loads(req.data)))
        return io.BytesIO(b'{"id": 5}')
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    assert Client("tok").post("/my/playlists/", {"name": "x"}) == {"id": 5}
    assert seen == [("POST", "https://api.beatport.com/v4/my/playlists/", {"name": "x"})]


def test_post_does_not_retry_a_5xx_so_it_does_not_duplicate(monkeypatch):
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise _http_error(502)
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        Client("tok").post("/my/playlists/", {"name": "x"})
    assert len(calls) == 1


def test_post_retries_a_429(monkeypatch):
    responses = [_http_error(429), io.BytesIO(b'{"id": 5}')]

    def urlopen(req, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    assert Client("tok").post("/my/playlists/", {"name": "x"}) == {"id": 5}


def test_post_renews_the_token_on_a_401(monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append(req.get_header("Authorization"))
        if len(sent) == 1:
            raise _http_error(401)
        return io.BytesIO(b'{"id": 5}')
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    assert Client("old", renew=lambda: "new").post("/my/playlists/", {"name": "x"}) == {"id": 5}
    assert sent == ["Bearer old", "Bearer new"]


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_patch_and_delete_send_their_method_and_json_body(monkeypatch, method):
    seen = []

    def urlopen(req, timeout):
        seen.append((req.get_method(), req.full_url, json.loads(req.data)))
        return io.BytesIO(b"")
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    assert getattr(Client("tok"), method)("/my/playlists/7/", {"name": "x"}) is None  # an empty answer is fine
    assert seen == [(method.upper(), "https://api.beatport.com/v4/my/playlists/7/", {"name": "x"})]


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_patch_and_delete_do_not_retry_a_5xx(monkeypatch, method):
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise _http_error(502)
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        getattr(Client("tok"), method)("/my/playlists/7/", {"name": "x"})
    assert len(calls) == 1
