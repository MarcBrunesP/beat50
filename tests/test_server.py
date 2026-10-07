import http.client
import json
import threading
import urllib.request
from datetime import date, timedelta

import pytest

from beatcrate import auth, playlists
from beatcrate.app import consent, jobs, marks, server, state
from beatcrate.errors import BeatcrateError


@pytest.fixture
def app(data_dir, monkeypatch):
    def no_real_session(*args, **kwargs):
        raise AssertionError("a server test must never reach Beatport or open a window")
    monkeypatch.setattr(auth, "get_token", no_real_session)
    monkeypatch.setattr(auth, "login_window", no_real_session)
    consent.grant()  # most tests are about what happens once the user has accepted
    a = server.App(0)
    threading.Thread(target=a.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    yield a
    a.shutdown()
    a.server_close()


def _request(app, method, path, token=None, host=None, body=None, raw=None, headers=None):
    port = app.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    sent = {"Host": host or f"127.0.0.1:{port}"}
    if token is not None:
        sent["X-Beatcrate-Token"] = token
    sent.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    c.request(method, path, body=data, headers=sent)
    r = c.getresponse()
    return r.status, r.read().decode(), r


def _crate(data_dir, selection, **kw):
    folder = data_dir / "crates"
    folder.mkdir(exist_ok=True)
    crate = {"window": {"from": "2026-08-30", "to": "2026-09-30"}, "candidates_seen": 1,
             "short": True, "tracks": []}
    crate.update(kw)
    (folder / f"{selection}.json").write_text(json.dumps(crate))


def test_health(app):
    code, body, _ = _request(app, "GET", "/api/health")
    assert code == 200 and json.loads(body) == {"app": "beatcrate"}


def test_a_foreign_host_gets_403(app):
    assert _request(app, "GET", "/", host="evil.example:8765")[0] == 403
    assert _request(app, "POST", "/api/consent", token=app.token, host="evil.example:8765", body={"on": True})[0] == 403


def test_post_without_a_token_or_with_a_bad_one_gets_403(app):
    assert _request(app, "POST", "/api/consent", body={"on": False})[0] == 403
    assert _request(app, "POST", "/api/consent", token="other", body={"on": False})[0] == 403
    assert consent.granted() is True


def test_a_body_that_is_not_json_gets_400(app):
    assert _request(app, "POST", "/api/generate", token=app.token, raw=b"not-json")[0] == 400


def test_a_body_that_is_not_an_object_gets_400(app):
    assert _request(app, "POST", "/api/generate", token=app.token, raw=b"[1, 2]")[0] == 400


def test_marking_the_help_as_seen(app, data_dir):
    assert not state.read().get("help_seen")
    assert _request(app, "POST", "/api/help-seen", token=app.token, body={})[0] == 200
    assert state.read().get("help_seen") is True


def test_the_root_redirects_to_the_most_recent_selection(app, data_dir):
    _crate(data_dir, "2026-08")
    _crate(data_dir, "2026-09")
    code, _, r = _request(app, "GET", "/")
    assert code == 302 and r.getheader("Location") == "/crate/2026-09"


def test_the_root_without_crates_shows_the_empty_page(app):
    code, body, _ = _request(app, "GET", "/")
    assert code == 200 and "No selections yet" in body


def test_the_page_follows_the_browser_language(app):
    _, body, _ = _request(app, "GET", "/", headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
    assert "Aún no hay ninguna selección" in body
    _, body, _ = _request(app, "GET", "/", headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    assert "No selections yet" in body


def test_the_language_cookie_beats_the_browser_language(app):
    _, body, _ = _request(app, "GET", "/", headers={"Cookie": "beatcrate_lang=es", "Accept-Language": "en"})
    assert "Aún no hay ninguna selección" in body
    _, body, _ = _request(app, "GET", "/", headers={"Cookie": "beatcrate_lang=en", "Accept-Language": "es"})
    assert "No selections yet" in body


def test_the_selection_page_carries_the_token(app, data_dir):
    _crate(data_dir, "2026-09")
    code, body, _ = _request(app, "GET", "/crate/2026-09")
    assert code == 200 and app.token in body


@pytest.mark.parametrize("path", ["/crate/2026-13x", "/crate/..%2Fstate", "/crate/../state", "/static/../server.py",
                                  "/static/nothing.js", "/static/material-symbols.woff2", "/other"])
def test_missing_or_malformed_routes_get_404(app, data_dir, path):
    assert _request(app, "GET", path)[0] == 404


def test_a_404_answers_with_a_translated_error(app):
    code, body, _ = _request(app, "GET", "/other")
    assert code == 404 and json.loads(body) == {"error": "Not found."}
    _, body, _ = _request(app, "GET", "/other", headers={"Accept-Language": "es"})
    assert json.loads(body) == {"error": "No existe."}


def test_static_files(app):
    code, body, r = _request(app, "GET", "/static/app.css")
    assert code == 200 and "text/css" in r.getheader("Content-Type") and "--text" in body
    code, _, r = _request(app, "GET", "/static/app.js")
    assert code == 200 and "javascript" in r.getheader("Content-Type")


def test_the_stylesheet_is_night_mode_only(app):
    _, css, _ = _request(app, "GET", "/static/app.css")
    assert "color-scheme: dark" in css
    assert "--bg: #121214" in css
    assert "prefers-color-scheme" not in css  # always dark, it never follows the Mac's appearance
    assert "Material" not in css and "woff" not in css


def test_the_stylesheet_fills_the_star_only_when_on(app):
    _, css, _ = _request(app, "GET", "/static/app.css")
    assert ".star .icon { width: 22px; height: 22px; fill: none; stroke-width: 1.8; }" in css
    assert ".star.on .icon { fill: currentColor; }" in css
    assert ".count .icon { width: 11px; height: 11px; fill: currentColor; stroke: none; }" in css


def test_the_selected_sidebar_row_keeps_its_colour_on_hover(app):
    _, css, _ = _request(app, "GET", "/static/app.css")
    assert "a.sel:hover:not(.on), .playlists a.pl:hover:not(.on) { background: var(--line); }" in css


def test_generate_with_the_lock_held_gets_409(app):
    with state.lock():
        code, body, _ = _request(app, "POST", "/api/generate", token=app.token, body={})
    assert code == 409
    assert json.loads(body)["error"] == "beatcrate is already busy. Try again in a moment."


def test_generate_busy_is_translated(app, monkeypatch):
    def busy(**kw):
        raise state.Busy("busy", "A selection is already running.")
    monkeypatch.setattr(server.jobs, "start_generation", busy)
    code, body, _ = _request(app, "POST", "/api/generate", token=app.token, body={},
                             headers={"Accept-Language": "es"})
    assert code == 409
    assert json.loads(body)["error"] == "beatcrate ya está trabajando. Prueba de nuevo en un momento."


def test_login_start_with_a_login_in_progress_gets_409(app, monkeypatch):
    def already():
        raise BeatcrateError("login_already", "A sign-in is already in progress.")
    monkeypatch.setattr(server.jobs, "login_start", already)
    code, body, _ = _request(app, "POST", "/api/login/start", token=app.token, body={})
    assert code == 409
    assert json.loads(body)["error"] == "A sign-in is already in progress."


def test_login_start_opens_the_sign_in_window(app, monkeypatch):
    calls = []
    monkeypatch.setattr(server.jobs, "login_start", lambda: calls.append("start"))
    assert _request(app, "POST", "/api/login/start", token=app.token, body={})[0] == 200
    assert calls == ["start"]


def test_there_is_no_second_sign_in_step(app):
    assert _request(app, "POST", "/api/login/finish", token=app.token, body={})[0] == 404


def test_session_check_answers_active(app, monkeypatch):
    for active in (True, False):
        monkeypatch.setattr(server.jobs, "check_session", lambda active=active: active)
        code, body, _ = _request(app, "POST", "/api/session/check", token=app.token, body={})
        assert code == 200 and json.loads(body) == {"active": active}


def test_an_expired_session_while_checking_gets_409(app, monkeypatch):
    def expired():
        raise auth.SessionExpired("session_expired", "No session")
    monkeypatch.setattr(server.jobs, "check_session", expired)
    code, body, _ = _request(app, "POST", "/api/session/check", token=app.token, body={})
    assert code == 409
    assert json.loads(body)["error"] == "Your Beatport session has expired: click “Sign in”."


def test_an_unexpected_failure_gets_500(app, monkeypatch):
    def boom():
        raise RuntimeError("boom")
    monkeypatch.setattr(server.jobs, "check_session", boom)
    code, body, _ = _request(app, "POST", "/api/session/check", token=app.token, body={})
    assert code == 500 and json.loads(body) == {"error": "boom"}


def test_state_includes_login_pending(app):
    code, body, _ = _request(app, "GET", "/api/state")
    assert code == 200 and json.loads(body)["login_pending"] is False


def test_run_app_with_an_app_already_running_does_not_start_another(monkeypatch, capsys):
    monkeypatch.setattr(server, "_already_open", lambda url: True)

    def must_not_be_created(port):
        raise AssertionError("must not start another server")
    monkeypatch.setattr(server, "App", must_not_be_created)
    monkeypatch.setattr(server.webkit, "show_app", lambda *a, **kw: pytest.fail("must not open a window"))
    server.run_app()
    assert "already running" in capsys.readouterr().out


def test_run_app_serves_while_its_window_is_open_and_stops_when_it_closes(data_dir, monkeypatch):
    monkeypatch.setattr(server, "_already_open", lambda url: False)
    monkeypatch.setattr(server.config, "APP_PORT", 0)
    seen, aborted = {}, []

    def show_app(url, busy, texts):
        seen["url"], seen["busy"] = url, busy
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
            seen["health"] = json.loads(r.read()) == {"app": "beatcrate"}
        seen["texts"] = texts()
    monkeypatch.setattr(server.webkit, "show_app", show_app)
    monkeypatch.setattr(server.jobs, "abort_login", lambda: aborted.append(1))
    server.run_app()
    assert seen["url"].startswith("http://127.0.0.1:")
    assert seen["health"] is True
    assert seen["busy"] is server.jobs.busy
    assert seen["texts"]["quit"] == "Quit"
    assert aborted == [1]
    with pytest.raises(OSError):  # the server is gone once the window closes
        urllib.request.urlopen(f"{seen['url']}/api/health", timeout=2)


def test_quitting_while_a_selection_runs_is_asked_in_the_users_language():
    texts = server._quit_texts("es")
    assert texts == {"message": "beatcrate está haciendo una selección. Si sales ahora, se detendrá. ¿Salir igualmente?",
                     "quit": "Salir", "cancel": "Cancelar"}


def test_already_open_recognises_beatcrate(app):
    port = app.server_address[1]
    assert server._already_open(f"http://127.0.0.1:{port}") is True


def test_already_open_is_false_when_nothing_answers():
    assert server._already_open("http://127.0.0.1:1") is False


def _crate_ids(data_dir, selection, ids):
    _crate(data_dir, selection, tracks=[{"id": i} for i in ids])


def test_star_marks_and_counts_only_those_in_the_crate(app, data_dir):
    _crate_ids(data_dir, "2026-09", [1, 2])
    marks.set_star("2026-09", 99, True)
    code, body, _ = _request(app, "POST", "/api/star/2026-09/2", token=app.token, body={"on": True})
    assert code == 200 and json.loads(body) == {"starred": 1}
    assert 2 in marks.read("2026-09")["starred"]


@pytest.mark.parametrize("path, body, expected", [
    ("/api/star/2026-09/1", {"on": "yes"}, 400),
    ("/api/star/2026-09/3", {"on": True}, 400),
    ("/api/star/2026-08/1", {"on": True}, 404),
    ("/api/star/2026-09/abc", {"on": True}, 404),
])
def test_invalid_star(app, data_dir, path, body, expected):
    _crate_ids(data_dir, "2026-09", [1, 2])
    assert _request(app, "POST", path, token=app.token, body=body)[0] == expected


def test_a_star_for_a_track_outside_the_selection_says_so(app, data_dir):
    _crate_ids(data_dir, "2026-09", [1, 2])
    _, body, _ = _request(app, "POST", "/api/star/2026-09/3", token=app.token, body={"on": True})
    assert json.loads(body) == {"error": "That track is not in this selection."}


def test_playlist_creates_and_returns_the_message(app, data_dir, monkeypatch):
    _crate_ids(data_dir, "2026-09", [1, 2, 3])
    monkeypatch.setattr(server.jobs, "create_playlist", lambda selection, n, genres=None: {
        "id": 9, "name": n, "track_ids": [1, 2], "requested": 3, "warnings": []})
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09", token=app.token,
                             body={"name": "202609 Techno"})
    payload = json.loads(body)
    assert code == 200 and payload["ok"] is True
    assert payload["message"] == ("“202609 Techno” created on Beatport (private) with 2 tracks. "
                                  "Beatport only accepted 2 of 3.")


def test_playlist_message_in_spanish_and_with_warnings(app, data_dir, monkeypatch):
    _crate_ids(data_dir, "2026-09", [1])
    monkeypatch.setattr(server.jobs, "create_playlist", lambda selection, n, genres=None: {
        "id": 9, "name": n, "track_ids": [], "requested": 1,
        "warnings": [{"code": "add_failed", "detail": "502"}, {"code": "count_unknown", "detail": "timed out"}]})
    _, body, _ = _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"},
                          headers={"Accept-Language": "es"})
    message = json.loads(body)["message"]
    assert "«x» creada en Beatport (privada) con 0 tracks." in message
    assert "Beatport solo aceptó 0 de 1." in message
    assert "No se pudieron añadir los tracks: 502" in message
    assert "No se pudo comprobar cuántos tracks entraron" in message


@pytest.mark.parametrize("error, expected, message", [
    (playlists.PlaylistError("name_required", "The playlist needs a name."), 400,
     "The playlist needs a name."),
    (playlists.PlaylistError("name_too_long", "too long", max=100), 400,
     "The name cannot be longer than 100 characters."),
    (playlists.PlaylistPublic("created_public", "created as public", name="x", id=9), 400,
     "Beatport created “x” as public. Nothing was added to it: make it private or delete it on beatport.com."),
    (auth.SessionExpired("session_expired", "No session"), 409,
     "Your Beatport session has expired: click “Sign in”."),
])
def test_playlist_errors(app, data_dir, monkeypatch, error, expected, message):
    _crate_ids(data_dir, "2026-09", [1])

    def fails(selection, n, genres=None):
        raise error
    monkeypatch.setattr(server.jobs, "create_playlist", fails)
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"})
    assert code == expected and json.loads(body)["error"] == message


def test_an_error_with_an_unknown_code_keeps_its_own_text(app, data_dir, monkeypatch):
    _crate_ids(data_dir, "2026-09", [1])

    def fails(selection, n, genres=None):
        raise BeatcrateError("no_such_code", "Plain English text")
    monkeypatch.setattr(server.jobs, "create_playlist", fails)
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"})
    assert code == 400 and json.loads(body)["error"] == "Plain English text"


def test_playlist_without_a_name_or_with_the_lock_held(app, data_dir):
    _crate_ids(data_dir, "2026-09", [1])
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={})
    assert code == 400 and json.loads(body)["error"] == "The playlist needs a name."
    with state.lock():
        assert _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"})[0] == 409


def test_playlist_for_an_unknown_selection_gets_404(app, data_dir):
    assert _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"})[0] == 404


@pytest.mark.parametrize("body", [{"name": "x", "genres": "House"}, {"name": "x", "genres": [1]}])
def test_playlist_with_invalid_genres_gets_400(app, data_dir, body):
    _crate_ids(data_dir, "2026-09", [1])
    assert _request(app, "POST", "/api/playlist/2026-09", token=app.token, body=body)[0] == 400


def test_playlist_passes_on_the_filter_genres(app, data_dir, monkeypatch):
    _crate_ids(data_dir, "2026-09", [1])
    received = []
    monkeypatch.setattr(server.jobs, "create_playlist", lambda selection, n, genres=None: received.append(genres) or {
        "id": 9, "name": n, "track_ids": [1], "requested": 1, "warnings": []})
    _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x", "genres": ["House"]})
    _request(app, "POST", "/api/playlist/2026-09", token=app.token, body={"name": "x"})
    assert received == [["House"], None]


def test_generate_starts_without_confirmation(app, data_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(server.jobs, "start_generation", lambda **kw: calls.append(kw))
    assert _request(app, "POST", "/api/generate", token=app.token, body={})[0] == 202
    assert calls == [{"since": None, "until": None}]


def test_selections_with_a_code(app, data_dir):
    _crate(data_dir, "2026-09")
    _crate(data_dir, "20261001_074512")
    code, _, r = _request(app, "GET", "/")
    assert code == 302 and r.getheader("Location") == "/crate/20261001_074512"
    assert _request(app, "GET", "/crate/20261001_074512")[0] == 200
    assert _request(app, "GET", "/crate/20261001_0745")[0] == 404


def test_selections_lists_newest_first_with_their_track_counts(data_dir):
    _crate_ids(data_dir, "2026-09", [1, 2])
    _crate_ids(data_dir, "20261001_074512", [1])
    (data_dir / "crates" / "notes.json").write_text("{}")
    assert server._selections() == [("20261001_074512", 1), ("2026-09", 2)]


def test_selections_without_a_folder_is_empty(data_dir):
    assert server._selections() == []


def test_generate_with_a_chosen_period(app, monkeypatch):
    received = []
    monkeypatch.setattr(server.jobs, "start_generation", lambda **kw: received.append(kw))
    today = date.today()
    body = {"since": (today - timedelta(days=10)).isoformat(), "until": today.isoformat()}
    assert _request(app, "POST", "/api/generate", token=app.token, body=body)[0] == 202
    assert received == [{"since": today - timedelta(days=10), "until": today}]


@pytest.mark.parametrize("body, message", [
    ({"since": "2026-13-01", "until": "2026-09-01"}, "Dates must be YYYY-MM-DD."),
    ({"since": "2026-09-01"}, "Dates must be YYYY-MM-DD."),
    ({"since": "2026-09-10", "until": "2026-09-01"}, "“From” cannot be later than “To”."),
    ({"since": "2024-01-01", "until": "2026-09-01"}, "The period cannot be longer than a year."),
    ({"since": "2026-09-01", "until": "2999-01-01"}, "“To” cannot be later than today."),
])
def test_generate_with_an_invalid_period_gets_400(app, monkeypatch, body, message):
    monkeypatch.setattr(server.jobs, "start_generation", lambda **kw: None)
    code, response, _ = _request(app, "POST", "/api/generate", token=app.token, body=body)
    assert code == 400 and json.loads(response)["error"] == message


def test_an_invalid_period_error_is_translated(app, monkeypatch):
    monkeypatch.setattr(server.jobs, "start_generation", lambda **kw: None)
    _, response, _ = _request(app, "POST", "/api/generate", token=app.token,
                              body={"since": "nope", "until": "2026-09-01"}, headers={"Accept-Language": "es"})
    assert json.loads(response)["error"] == "Las fechas deben ser AAAA-MM-DD."


def test_period_without_dates_means_the_default_window():
    assert server._period({}) == (None, None)


@pytest.mark.parametrize("body, code", [
    ({"since": "2026-13-01", "until": "2026-09-01"}, "period_format"),
    ({"until": "2026-09-01"}, "period_format"),
    ({"since": "2026-09-10", "until": "2026-09-01"}, "period_order"),
    ({"since": "2024-01-01", "until": "2026-09-01"}, "period_too_long"),
    ({"since": "2026-09-01", "until": "2999-01-01"}, "period_future"),
])
def test_period_error_codes(body, code):
    with pytest.raises(BeatcrateError) as err:
        server._period(body)
    assert err.value.code == code


SESSION_ROUTES = ["/api/generate", "/api/session/check", "/api/login/start", "/api/playlist/2026-09"]


@pytest.mark.parametrize("path", SESSION_ROUTES)
def test_without_consent_nothing_reads_the_session(app, data_dir, monkeypatch, path):
    _crate(data_dir, "2026-09")
    consent.revoke()
    called = []
    for name in ("start_generation", "check_session", "login_start", "create_playlist"):
        monkeypatch.setattr(server.jobs, name, lambda *a, _n=name, **kw: called.append(_n))
    code, body, _ = _request(app, "POST", path, token=app.token, body={"name": "x"},
                             headers={"Accept-Language": "es-ES"})
    assert code == 409
    assert json.loads(body)["error"] == "Falta tu permiso para leer tu sesión de Beatport."
    assert called == []


def test_the_page_can_give_and_withdraw_consent(app, data_dir):
    consent.revoke()
    assert _request(app, "POST", "/api/consent", token=app.token, body={"on": True})[0] == 200
    assert consent.granted() is True
    assert _request(app, "POST", "/api/consent", token=app.token, body={"on": False})[0] == 200
    assert consent.granted() is False


def test_consent_needs_on_true_or_false(app, data_dir):
    consent.revoke()
    assert _request(app, "POST", "/api/consent", token=app.token, body={"on": "yes"})[0] == 400
    assert consent.granted() is False


def test_consent_needs_the_page_token(app, data_dir):
    consent.revoke()
    assert _request(app, "POST", "/api/consent", body={"on": True})[0] == 403
    assert consent.granted() is False


def test_the_page_knows_whether_there_is_consent(app, data_dir):
    _crate(data_dir, "2026-09")
    assert 'data-consent="1"' in _request(app, "GET", "/crate/2026-09")[1]
    consent.revoke()
    assert 'data-consent="0"' in _request(app, "GET", "/crate/2026-09")[1]


def _edit_setup(data_dir):
    _crate_ids(data_dir, "2026-09", [1, 2, 3])
    marks.add_playlist("2026-09", {"id": 9, "name": "Techno", "track_ids": [1, 2], "created_at": "t"})


def test_a_created_playlist_opens_in_its_own_page(app, data_dir):
    _edit_setup(data_dir)
    code, html, _ = _request(app, "GET", "/crate/2026-09/playlist/9")
    assert code == 200 and 'id="pl-name"' in html and 'value="Techno"' in html


@pytest.mark.parametrize("path", ["/crate/2026-09/playlist/99", "/crate/2026-09/playlist/x9",
                                  "/crate/2026-08/playlist/9"])
def test_only_playlists_beatcrate_created_open(app, data_dir, path):
    _edit_setup(data_dir)
    assert _request(app, "GET", path)[0] == 404


def test_saving_a_playlist_edit(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    seen = []
    monkeypatch.setattr(server.jobs, "edit_playlist", lambda sel, pid, name, remove=(), add=(): seen.append(
        (sel, pid, name, remove, add)) or {"id": pid, "name": name, "track_ids": [1, 3], "warnings": []})
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09/9", token=app.token,
                             body={"name": "Peak", "remove": [2], "add": [3]}, headers={"Accept-Language": "es"})
    assert code == 200
    assert json.loads(body)["message"] == "«Peak» guardada en Beatport: 2 tracks."
    assert seen == [("2026-09", 9, "Peak", [2], [3])]


def test_a_partial_save_says_what_failed(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    monkeypatch.setattr(server.jobs, "edit_playlist", lambda sel, pid, name, remove=(), add=(): {
        "id": pid, "name": "Techno", "track_ids": [1, 2], "warnings": [{"code": "rename_failed", "detail": "502"},
                                                                       {"code": "remove_failed", "detail": "502"}]})
    _, body, _ = _request(app, "POST", "/api/playlist/2026-09/9", token=app.token,
                          body={"name": "Peak", "remove": [2], "add": []})
    message = json.loads(body)["message"]
    assert message.startswith("“Techno” saved on Beatport: 2 tracks.")
    assert "The name could not be changed: 502" in message and "Some tracks could not be removed: 502" in message


@pytest.mark.parametrize("body", [{"name": "x", "remove": "2"}, {"name": "x", "add": [True]},
                                  {"name": 3, "remove": [], "add": []}, {"remove": [1]}])
def test_a_playlist_edit_needs_a_name_and_lists_of_track_ids(app, data_dir, monkeypatch, body):
    _edit_setup(data_dir)
    monkeypatch.setattr(server.jobs, "edit_playlist", lambda *a, **kw: pytest.fail("must not save"))
    assert _request(app, "POST", "/api/playlist/2026-09/9", token=app.token, body=body)[0] == 400


def test_editing_a_playlist_needs_consent(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    consent.revoke()
    monkeypatch.setattr(server.jobs, "edit_playlist", lambda *a, **kw: pytest.fail("must not save"))
    assert _request(app, "POST", "/api/playlist/2026-09/9", token=app.token,
                    body={"name": "x", "remove": [], "add": []})[0] == 409


@pytest.mark.parametrize("error, expected", [("playlist_gone", "That playlist no longer exists on Beatport."),
                                             ("no_changes", "There is nothing to save.")])
def test_playlist_edit_errors(app, data_dir, monkeypatch, error, expected):
    _edit_setup(data_dir)

    def fails(*a, **kw):
        raise playlists.PlaylistError(error, "x")
    monkeypatch.setattr(server.jobs, "edit_playlist", fails)
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09/9", token=app.token,
                             body={"name": "x", "remove": [], "add": []})
    assert code == 400 and json.loads(body)["error"] == expected


def test_a_trailing_slash_does_not_create_a_playlist(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    monkeypatch.setattr(server.jobs, "create_playlist", lambda *a, **kw: pytest.fail("must not create"))
    assert _request(app, "POST", "/api/playlist/2026-09/", token=app.token, body={"name": "x"})[0] == 404


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_an_absurdly_long_playlist_id_is_just_not_found(app, data_dir, method):
    _edit_setup(data_dir)
    path = ("/crate/2026-09/playlist/" if method == "GET" else "/api/playlist/2026-09/") + "9" * 5000
    assert _request(app, method, path, token=app.token, body={"name": "x"})[0] == 404


def test_opening_the_editor_can_refresh_it_from_beatport(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    monkeypatch.setattr(server.jobs, "refresh_playlist", lambda sel, pid: {"changed": True, "gone": False})
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09/9/refresh", token=app.token, body={})
    assert code == 200 and json.loads(body) == {"changed": True, "gone": False}


def test_refreshing_needs_consent(app, data_dir, monkeypatch):
    _edit_setup(data_dir)
    consent.revoke()
    monkeypatch.setattr(server.jobs, "refresh_playlist", lambda *a: pytest.fail("must not read the session"))
    assert _request(app, "POST", "/api/playlist/2026-09/9/refresh", token=app.token, body={})[0] == 409


def test_forgetting_a_deleted_playlist_goes_back_to_the_selection(app, data_dir):
    _edit_setup(data_dir)
    marks.update_playlist("2026-09", 9, gone=True)
    consent.revoke()  # only local: no permission needed
    code, body, _ = _request(app, "POST", "/api/playlist/2026-09/9/forget", token=app.token, body={})
    assert code == 200 and json.loads(body)["redirect"] == "/crate/2026-09"
    assert marks.find_playlist("2026-09", 9) is None


def test_a_playlist_that_still_exists_is_not_forgotten(app, data_dir):
    _edit_setup(data_dir)
    assert _request(app, "POST", "/api/playlist/2026-09/9/forget", token=app.token, body={})[0] == 400
    assert marks.find_playlist("2026-09", 9) is not None


@pytest.mark.parametrize("path", ["/api/playlist/2026-09/9/other", "/api/playlist/2026-09/99/refresh",
                                  "/api/playlist/2026-09/9/refresh/x"])
def test_unknown_playlist_actions_are_not_found(app, data_dir, path):
    _edit_setup(data_dir)
    assert _request(app, "POST", path, token=app.token, body={})[0] == 404


def _trash_to(monkeypatch, data_dir):
    """Fakes the Trash with a folder, recording what was moved there."""
    bin_ = data_dir / "Trash"
    bin_.mkdir()
    moved = []

    def move(path):
        moved.append(path.relative_to(data_dir).as_posix())
        path.rename(bin_ / f"{len(moved)}-{path.name}")
    monkeypatch.setattr(server.trash, "move", move)
    return moved


def test_deleting_a_selection_moves_it_and_its_marks_to_the_trash(app, data_dir, monkeypatch):
    moved = _trash_to(monkeypatch, data_dir)
    _crate(data_dir, "20261001_120000")
    _crate(data_dir, "20260915_090000")
    marks.set_star("20261001_120000", 7, True)
    consent.revoke()  # only local: no permission needed
    code, body, _ = _request(app, "POST", "/api/selection/20261001_120000/delete", token=app.token, body={})
    assert code == 200 and json.loads(body) == {"ok": True}
    assert moved == ["crates/20261001_120000.json", "marks/20261001_120000.json"]
    assert server._selections() == [("20260915_090000", 0)]


def test_deleting_a_selection_without_marks_moves_only_the_selection(app, data_dir, monkeypatch):
    moved = _trash_to(monkeypatch, data_dir)
    _crate(data_dir, "2026-09")
    assert _request(app, "POST", "/api/selection/2026-09/delete", token=app.token, body={})[0] == 200
    assert moved == ["crates/2026-09.json"]


def test_deleting_an_unknown_or_odd_selection_gets_404(app, data_dir, monkeypatch):
    moved = _trash_to(monkeypatch, data_dir)
    assert _request(app, "POST", "/api/selection/20261001_120000/delete", token=app.token, body={})[0] == 404
    assert _request(app, "POST", "/api/selection/../state/delete", token=app.token, body={})[0] == 404
    assert moved == []


def test_deleting_a_selection_while_busy_gets_409(app, data_dir, monkeypatch):
    moved = _trash_to(monkeypatch, data_dir)
    _crate(data_dir, "20261001_120000")
    monkeypatch.setattr(server.jobs, "busy", lambda: True)
    assert _request(app, "POST", "/api/selection/20261001_120000/delete", token=app.token, body={})[0] == 409
    assert moved == []


def test_deleting_a_selection_needs_the_token(app, data_dir, monkeypatch):
    moved = _trash_to(monkeypatch, data_dir)
    _crate(data_dir, "20261001_120000")
    assert _request(app, "POST", "/api/selection/20261001_120000/delete", body={})[0] == 403
    assert moved == []


def test_a_trash_failure_is_translated(app, data_dir, monkeypatch):
    _crate(data_dir, "20261001_120000")

    def refuse(path):
        raise BeatcrateError("trash_failed", "Could not move it to the Trash: no", detail="no")
    monkeypatch.setattr(server.trash, "move", refuse)
    code, body, _ = _request(app, "POST", "/api/selection/20261001_120000/delete", token=app.token, body={},
                             headers={"Accept-Language": "es"})
    assert code == 400 and json.loads(body)["error"] == "No se pudo mover la selección a la Papelera: no"


def test_genre_preferences_are_saved_without_consent(app):
    consent.revoke()
    body = {"levels": {"5": 2, "6": 0, "7": 1}, "only": None}
    assert _request(app, "POST", "/api/genres", token=app.token, body=body)[0] == 200
    assert state.read()["genre_prefs"] == {"levels": {"5": 2, "6": 0}, "only": None}
    assert _request(app, "POST", "/api/genres", token=app.token, body={"only": 5})[0] == 200
    assert state.read()["genre_prefs"] == {"levels": {}, "only": 5}


@pytest.mark.parametrize("body", [{"levels": {"5": 3}}, {"levels": {"x": 2}}, {"levels": [5]},
                                  {"levels": {"5": True}}, {"only": "5"}, {"only": True}])
def test_invalid_genre_preferences_get_400(app, body):
    code, response, _ = _request(app, "POST", "/api/genres", token=app.token, body=body)
    assert code == 400 and "error" in json.loads(response)
    assert "genre_prefs" not in state.read()


def test_genre_preferences_wait_while_beatcrate_is_busy(app):
    with state.lock():
        assert _request(app, "POST", "/api/genres", token=app.token, body={"levels": {"5": 2}})[0] == 409


def test_the_page_lists_the_profile_genres_in_the_dialog(app, data_dir):
    (data_dir / "profile.json").write_text(json.dumps({"genres": [{"id": 5, "name": "Techno", "weight": 1.0, "n": 3}]}))
    _, html, _ = _request(app, "GET", "/")
    assert 'id="genres"' in html and '<li class="gp" data-genre="5" data-weight="1.0">' in html
