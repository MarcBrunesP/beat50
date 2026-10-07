import json
import threading
from datetime import date, datetime
from pathlib import Path

import pytest

from beatcrate import auth, playlists
from beatcrate.app import jobs, marks, state
from beatcrate.errors import BeatcrateError

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 30)
SELECTION = "20260930_074512"


def _res(name):
    return json.loads((FIXTURES / name).read_text())["results"]


class FakeClient:
    """Answers with real fixtures; records in `steps` the step in progress at each call."""
    requests = 0

    def __init__(self, steps=None):
        self.steps = steps

    def paged(self, path, **kw):
        if self.steps is not None:
            self.steps.append((state.read().get("running") or {}).get("step"))
        if path == "/my/playlists/":
            return []
        if path == "/my/downloads/":
            return _res("my_downloads.json")
        return _res("catalog_tracks_sample.json")

    def get(self, path, **kw):
        return {"results": []}


def test_generate_writes_the_crate_and_leaves_the_state_ok(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    path = jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 7, 45, 12))
    assert path == data_dir / "crates" / "20260930_074512.json"
    crate = json.loads(path.read_text())
    assert crate["id"] == "20260930_074512" and crate["tracks"]
    st = state.read()
    assert st["running"] is None
    assert st["last_run"]["ok"] is True
    assert st["last_run"]["trigger"] == "app"
    assert st["last_run"]["id"] == "20260930_074512"
    assert st["session"]["status"] == "active"
    assert state.lock_owner() is None


def test_generate_reports_the_step_in_progress(data_dir, monkeypatch):
    seen = []
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient(seen))
    jobs.generate("app", today=TODAY)
    assert 1 in seen and 2 in seen


def test_running_holds_the_step_the_total_and_the_phase(data_dir, monkeypatch):
    phases = []

    class Watching(FakeClient):
        def paged(self, path, **kw):
            running = state.read().get("running")
            phases.append((running["step"], running["of"], running["phase"], bool(running["since"])))
            return super().paged(path, **kw)

    monkeypatch.setattr(jobs, "_client", lambda: Watching())
    jobs.generate("app", today=TODAY)
    assert (1, 3, "library", True) in phases
    assert (2, 3, "discover", True) in phases


def test_an_expired_session_is_kept_in_the_state_and_leaves_the_crate_alone(data_dir, monkeypatch):
    (data_dir / "crates").mkdir()
    previous = data_dir / "crates" / "20260901_080000.json"
    previous.write_text(json.dumps({"tracks": [{"id": 1}]}))

    def no_session():
        raise auth.SessionExpired("session_expired", "No valid user session in beatcrate.")
    monkeypatch.setattr(jobs, "_client", no_session)
    with pytest.raises(auth.SessionExpired):
        jobs.generate("app", today=TODAY)
    st = state.read()
    assert st["last_run"]["ok"] is False
    assert st["last_run"]["error_code"] == "session_expired"
    assert "user session" in st["last_run"]["error"]
    assert st["session"]["status"] == "expired"
    assert st["running"] is None
    assert json.loads(previous.read_text()) == {"tracks": [{"id": 1}]}
    assert state.lock_owner() is None


def test_a_failure_keeps_its_code_and_params_in_the_state(data_dir, monkeypatch):
    def failing():
        raise BeatcrateError("some_code", "It broke.", name="x")
    monkeypatch.setattr(jobs, "_client", failing)
    with pytest.raises(BeatcrateError):
        jobs.generate("app", today=TODAY)
    last = state.read()["last_run"]
    assert last["ok"] is False
    assert (last["error"], last["error_code"], last["error_params"]) == ("It broke.", "some_code", {"name": "x"})
    assert "session" not in state.read()


def test_a_failure_without_a_code_leaves_it_empty(data_dir, monkeypatch):
    def failing():
        raise RuntimeError("boom")
    monkeypatch.setattr(jobs, "_client", failing)
    with pytest.raises(RuntimeError):
        jobs.generate("app", today=TODAY)
    last = state.read()["last_run"]
    assert (last["error"], last["error_code"], last["error_params"]) == ("boom", None, {})


def test_generate_with_another_process_running_raises_busy(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    with state.lock():
        with pytest.raises(state.Busy) as err:
            jobs.generate("app", today=TODAY)
    assert err.value.code == "busy"


def test_start_generation_works_in_a_thread(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    thread = jobs.start_generation(today=TODAY)
    thread.join(timeout=10)
    assert state.read()["last_run"]["ok"] is True
    assert not jobs.busy()


def test_start_generation_raises_busy_while_a_selection_thread_is_alive(data_dir, monkeypatch):
    release = threading.Event()
    alive = threading.Thread(target=release.wait, daemon=True)
    alive.start()
    monkeypatch.setattr(jobs, "_thread", alive)
    monkeypatch.setattr(jobs, "_client", lambda: pytest.fail("must not start a second selection"))
    try:
        assert jobs.busy()
        with pytest.raises(state.Busy) as err:
            jobs.start_generation(today=TODAY)
        assert err.value.code == "busy"
    finally:
        release.set()
        alive.join(timeout=5)


def test_start_generation_raises_busy_while_the_lock_is_held(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_thread", None)
    monkeypatch.setattr(jobs, "_client", lambda: pytest.fail("must not start a second selection"))
    with state.lock():
        with pytest.raises(state.Busy):
            jobs.start_generation(today=TODAY)


def test_start_generation_passes_the_period_on(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    thread = jobs.start_generation(today=TODAY, since=date(2026, 9, 1), until=date(2026, 9, 15))
    thread.join(timeout=10)
    code = state.read()["last_run"]["id"]
    crate = json.loads((data_dir / "crates" / f"{code}.json").read_text())
    assert crate["window"] == {"from": "2026-09-01", "to": "2026-09-15"}


def test_check_session(data_dir, monkeypatch):
    monkeypatch.setattr(jobs.auth, "get_token", lambda: "tok")
    assert jobs.check_session() is True
    assert state.read()["session"]["status"] == "active"

    def expired():
        raise auth.SessionExpired("session_expired", "x")
    monkeypatch.setattr(jobs.auth, "get_token", expired)
    assert jobs.check_session() is False
    assert state.read()["session"]["status"] == "expired"
    assert state.lock_owner() is None


@pytest.fixture
def login_window(monkeypatch):
    """A sign-in window whose user signs in (returns a token) or closes it (None) when told to."""
    answer, go, closed = {}, threading.Event(), []

    def wait_for_login(window):
        go.wait(5)
        return answer.get("token")
    monkeypatch.setattr(jobs.auth, "login_window", lambda: "W")
    monkeypatch.setattr(jobs.auth, "wait_for_login", wait_for_login)
    monkeypatch.setattr(jobs.webkit, "close", lambda w: closed.append(w) or go.set())

    def finish(token=None):
        answer["token"] = token
        go.set()
    return finish, closed


def test_login_opens_the_window_and_records_the_session_once_signed_in(data_dir, login_window):
    finish, _ = login_window
    thread = jobs.login_start()
    assert jobs.login_pending()
    assert state.lock_owner() is None  # the sign-in does not block selections
    finish("good-token")
    thread.join(5)
    assert not jobs.login_pending()
    assert state.read()["session"]["status"] == "active"


def test_closing_the_login_window_changes_nothing(data_dir, login_window):
    finish, _ = login_window
    state.update(session={"status": "expired"})
    thread = jobs.login_start()
    finish(None)
    thread.join(5)
    assert not jobs.login_pending()
    assert state.read()["session"]["status"] == "expired"


def test_only_one_login_at_a_time(data_dir, login_window):
    finish, _ = login_window
    thread = jobs.login_start()
    with pytest.raises(BeatcrateError) as e:
        jobs.login_start()
    assert e.value.code == "login_already"
    finish(None)
    thread.join(5)


def test_abort_login_closes_the_window(data_dir, login_window):
    _, closed = login_window
    thread = jobs.login_start()
    jobs.abort_login()
    thread.join(5)
    assert closed == ["W"]
    assert not jobs.login_pending()


def test_abort_login_without_a_login_does_nothing(data_dir):
    jobs.abort_login()
    assert not jobs.login_pending()
    assert state.lock_owner() is None


def _crate_with(data_dir, ids):
    (data_dir / "crates").mkdir(exist_ok=True)
    (data_dir / "crates" / f"{SELECTION}.json").write_text(json.dumps({"tracks": [{"id": i} for i in ids]}))


def test_create_playlist_uses_the_stars_in_the_crate_order(data_dir, monkeypatch):
    _crate_with(data_dir, [1, 2, 3])
    marks.set_star(SELECTION, 3, True)
    marks.set_star(SELECTION, 1, True)
    marks.set_star(SELECTION, 99, True)  # no longer in the crate
    requested = []
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "create_playlist", lambda c, n, ids: requested.append(ids) or
                        {"id": 9, "name": n, "track_ids": ids[:1], "requested": len(ids), "warnings": []})
    r = jobs.create_playlist(SELECTION, "202609 Techno")
    assert requested == [[1, 3]]
    assert r["track_ids"] == [1]
    saved = marks.read(SELECTION)["playlists"]
    assert [(p["id"], p["name"], p["track_ids"]) for p in saved] == [(9, "202609 Techno", [1])]
    assert state.read()["session"]["status"] == "active"
    assert state.lock_owner() is None


@pytest.mark.parametrize("name, stars, code", [("", [1], "name_required"), ("ok", [], "no_starred")])
def test_create_playlist_validates_before_opening_chrome(data_dir, monkeypatch, name, stars, code):
    _crate_with(data_dir, [1, 2])
    for i in stars:
        marks.set_star(SELECTION, i, True)

    def must_not_open():
        raise AssertionError("must not open Chrome")
    monkeypatch.setattr(jobs, "_client", must_not_open)
    with pytest.raises(playlists.PlaylistError) as err:
        jobs.create_playlist(SELECTION, name)
    assert err.value.code == code


def test_create_playlist_with_an_expired_session_saves_nothing(data_dir, monkeypatch):
    _crate_with(data_dir, [1])
    marks.set_star(SELECTION, 1, True)

    def no_session():
        raise auth.SessionExpired("session_expired", "No session")
    monkeypatch.setattr(jobs, "_client", no_session)
    with pytest.raises(auth.SessionExpired):
        jobs.create_playlist(SELECTION, "x")
    assert marks.read(SELECTION)["playlists"] == []
    assert state.read()["session"]["status"] == "expired"
    assert state.lock_owner() is None


def _crate_with_genres(data_dir):
    (data_dir / "crates").mkdir(exist_ok=True)
    tracks = [{"id": 1, "genre": "House"}, {"id": 2, "genre": "Techno"}, {"id": 3, "genre": "House"}]
    (data_dir / "crates" / f"{SELECTION}.json").write_text(json.dumps({"tracks": tracks}))
    for i in (1, 2, 3):
        marks.set_star(SELECTION, i, True)


def test_create_playlist_only_with_the_stars_of_the_filtered_genres(data_dir, monkeypatch):
    _crate_with_genres(data_dir)
    requested = []
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "create_playlist", lambda c, n, ids: requested.append(ids) or
                        {"id": 9, "name": n, "track_ids": ids, "requested": len(ids), "warnings": []})
    jobs.create_playlist(SELECTION, "202609 House", genres=["House"])
    assert requested == [[1, 3]]


def test_create_playlist_with_genres_without_stars_does_not_open_chrome(data_dir, monkeypatch):
    _crate_with_genres(data_dir)

    def must_not_open():
        raise AssertionError("must not open Chrome")
    monkeypatch.setattr(jobs, "_client", must_not_open)
    with pytest.raises(playlists.PlaylistError) as err:
        jobs.create_playlist(SELECTION, "x", genres=["Deep House"])
    assert err.value.code == "no_starred"


def test_each_selection_is_saved_apart_and_excludes_the_earlier_ones(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    first = json.loads(jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 7, 0, 0)).read_text())
    second = jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 7, 5, 0))
    assert sorted(p.name for p in (data_dir / "crates").glob("*.json")) == ["20260930_070000.json",
                                                                              "20260930_070500.json"]
    seen = {t["id"] for t in first["tracks"]}
    assert seen and not seen & {t["id"] for t in json.loads(second.read_text())["tracks"]}


def test_generate_with_a_chosen_period(data_dir, monkeypatch):
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    path = jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 8, 0, 0),
                         since=date(2026, 9, 1), until=date(2026, 9, 15))
    assert json.loads(path.read_text())["window"] == {"from": "2026-09-01", "to": "2026-09-15"}


def test_http_errors_do_not_pass_their_status_as_an_error_code():
    import io
    import urllib.error
    e = urllib.error.HTTPError("https://api.beatport.com/v4/x", 404, "Not Found", {}, io.BytesIO(b""))
    saved = jobs._error(e)
    assert saved["error_code"] is None
    assert saved["error_params"] == {}


def test_checking_the_session_counts_as_busy(data_dir, monkeypatch):
    seen = []
    monkeypatch.setattr(jobs.auth, "get_token", lambda: seen.append(jobs.busy()) or "t")
    jobs.check_session()
    assert seen == [True]
    assert not jobs.busy()


def test_creating_a_playlist_counts_as_busy(data_dir, monkeypatch):
    (data_dir / "crates").mkdir()
    (data_dir / "crates" / "2026-09.json").write_text(json.dumps({"tracks": [{"id": 1}]}))
    marks.set_star("2026-09", 1, True)
    seen = []

    def create(client, name, ids):
        seen.append(jobs.busy())
        return {"id": 9, "name": name, "track_ids": ids, "requested": 1, "warnings": []}
    monkeypatch.setattr(jobs, "_client", lambda: None)
    monkeypatch.setattr(jobs.playlists, "create_playlist", create)
    jobs.create_playlist("2026-09", "x")
    assert seen == [True]
    assert not jobs.busy()


def test_an_interrupted_check_does_not_mark_the_session_expired(data_dir, monkeypatch):
    state.update(session={"status": "active"})

    def interrupted():
        raise auth.Interrupted("interrupted", "beatcrate closed before it finished.")
    monkeypatch.setattr(jobs.auth, "get_token", interrupted)
    with pytest.raises(auth.Interrupted):
        jobs.check_session()
    assert state.read()["session"]["status"] == "active"


def _with_playlist(data_dir, crate_ids=(1, 2, 3, 4), in_playlist=(1, 2)):
    _crate_with(data_dir, list(crate_ids))
    marks.add_playlist(SELECTION, {"id": 9, "name": "Old", "track_ids": list(in_playlist), "created_at": "t"})


def test_edit_playlist_applies_the_changes_and_updates_the_record(data_dir, monkeypatch):
    _with_playlist(data_dir)
    calls = []

    def edit(client, pid, name=None, remove=(), add=()):
        calls.append((pid, name, list(remove), list(add)))
        assert jobs.busy()
        return {"id": pid, "name": name, "track_ids": [1, 3], "warnings": []}
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "edit_playlist", edit)
    r = jobs.edit_playlist(SELECTION, 9, "New", remove=[2], add=[3])
    assert calls == [(9, "New", [2], [3])]
    saved = marks.find_playlist(SELECTION, 9)
    assert saved["name"] == "New" and saved["track_ids"] == [1, 3] and saved["edited_at"]
    assert r["track_ids"] == [1, 3]
    assert state.read()["session"]["status"] == "active"
    assert state.lock_owner() is None and not jobs.busy()


def test_edit_playlist_with_the_same_name_does_not_rename(data_dir, monkeypatch):
    _with_playlist(data_dir)
    seen = []
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "edit_playlist", lambda c, pid, name=None, remove=(), add=():
                        seen.append(name) or {"id": pid, "name": None, "track_ids": [1], "warnings": []})
    jobs.edit_playlist(SELECTION, 9, " Old ", remove=[2])
    assert seen == [None]
    assert marks.find_playlist(SELECTION, 9)["name"] == "Old"


def test_edit_playlist_keeps_the_record_when_beatport_could_not_be_reread(data_dir, monkeypatch):
    _with_playlist(data_dir)
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "edit_playlist", lambda c, pid, name=None, remove=(), add=():
                        {"id": pid, "name": None, "track_ids": None, "warnings": [{"code": "count_unknown"}]})
    jobs.edit_playlist(SELECTION, 9, "Old", add=[3])
    assert marks.find_playlist(SELECTION, 9)["track_ids"] == [1, 2]


@pytest.mark.parametrize("pid, name, remove, add, code", [
    (99, "x", [], [3], "not_found"),            # not a playlist beatcrate created
    (9, "Old", [], [], "no_changes"),
    (9, "", [2], [], "name_required"),
    (9, "Old", [], [77], "not_in_selection"),   # only tracks of this selection can be added
])
def test_edit_playlist_checks_everything_before_reading_the_session(data_dir, monkeypatch, pid, name, remove, add,
                                                                     code):
    _with_playlist(data_dir)
    monkeypatch.setattr(jobs, "_client", lambda: pytest.fail("must not read the session"))
    with pytest.raises(BeatcrateError) as e:
        jobs.edit_playlist(SELECTION, pid, name, remove=remove, add=add)
    assert e.value.code == code


def test_edit_playlist_with_an_expired_session_marks_it_expired(data_dir, monkeypatch):
    from beatcrate.client import TokenExpired
    _with_playlist(data_dir)
    state.update(session={"status": "active"})

    def expired(*a, **kw):
        raise TokenExpired("session_expired", "Beatport answered 401: sign in again.")
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "edit_playlist", expired)
    with pytest.raises(TokenExpired):
        jobs.edit_playlist(SELECTION, 9, "New")
    assert state.read()["session"]["status"] == "expired"
    assert marks.find_playlist(SELECTION, 9)["name"] == "Old"


def _live(name="Old", track_ids=(1, 2), extra=None):
    tracks = {t: {"name": f"Song {t}", "mix_name": "Original Mix", "artists": ["A"]} for t in track_ids}
    return {"name": name, "track_ids": list(track_ids), "tracks": dict(tracks, **(extra or {}))}


def test_refresh_brings_the_record_up_to_date_with_beatport(data_dir, monkeypatch):
    _with_playlist(data_dir)
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "read_playlist", lambda c, pid: _live("Renamed", (2, 77)))
    assert jobs.refresh_playlist(SELECTION, 9) == {"changed": True, "gone": False}
    saved = marks.find_playlist(SELECTION, 9)
    assert saved["name"] == "Renamed" and saved["track_ids"] == [2, 77]
    assert saved["outside"] == {"77": {"name": "Song 77", "mix_name": "Original Mix", "artists": ["A"]}}
    assert state.read()["session"]["status"] == "active"
    assert not jobs.busy() and state.lock_owner() is None


def test_refresh_without_changes_says_so(data_dir, monkeypatch):
    _with_playlist(data_dir)
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "read_playlist", lambda c, pid: _live())
    jobs.refresh_playlist(SELECTION, 9)  # the first refresh records `outside`
    assert jobs.refresh_playlist(SELECTION, 9) == {"changed": False, "gone": False}


def test_refresh_of_a_playlist_deleted_on_beatport_marks_it_gone(data_dir, monkeypatch):
    _with_playlist(data_dir)

    def gone(c, pid):
        raise playlists.PlaylistError("playlist_gone", "gone")
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "read_playlist", gone)
    assert jobs.refresh_playlist(SELECTION, 9) == {"changed": True, "gone": True}
    assert marks.find_playlist(SELECTION, 9)["gone"] is True


def test_saving_a_playlist_deleted_on_beatport_marks_it_gone(data_dir, monkeypatch):
    _with_playlist(data_dir)

    def gone(*a, **kw):
        raise playlists.PlaylistError("playlist_gone", "gone")
    monkeypatch.setattr(jobs, "_client", lambda: object())
    monkeypatch.setattr(jobs.playlists, "edit_playlist", gone)
    with pytest.raises(playlists.PlaylistError):
        jobs.edit_playlist(SELECTION, 9, "New")
    assert marks.find_playlist(SELECTION, 9)["gone"] is True


def test_forget_only_drops_playlists_gone_from_beatport(data_dir):
    _with_playlist(data_dir)
    with pytest.raises(BeatcrateError) as e:
        jobs.forget_playlist(SELECTION, 9)
    assert e.value.code == "not_gone"
    marks.update_playlist(SELECTION, 9, gone=True)
    jobs.forget_playlist(SELECTION, 9)
    assert marks.find_playlist(SELECTION, 9) is None


def test_generate_applies_the_genre_preferences_and_records_them(data_dir, monkeypatch):
    # The fixtures: the library has genres 5 and 39; every candidate is Rock (109), outside the profile.
    monkeypatch.setattr(jobs, "_client", lambda: FakeClient())
    first = json.loads(jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 9, 0, 0)).read_text())
    assert first["genre_prefs"] == [] and first["tracks"]
    names = {g["id"]: g["name"] for g in json.loads((data_dir / "profile.json").read_text())["genres"]}
    state.update(genre_prefs={"levels": {"39": 0}, "only": 5})
    second = json.loads(jobs.generate("app", today=TODAY, now=datetime(2026, 9, 30, 9, 5, 0)).read_text())
    assert second["genre_prefs"] == [{"id": 5, "name": names[5], "level": "only"}]
    assert second["tracks"] == [] and second["short"] is True  # only genre 5 may enter, and no candidate is
    # profile.json keeps the library's weights, not the choices
    assert "genre_only" not in json.loads((data_dir / "profile.json").read_text())
