"""beat50's long-running jobs: making a selection, checking the session, signing in, playlists.

Used by the app (selections and the sign-in wait run in threads) and by the command line. Selections,
session checks and playlists run under the state lock, so the app and the command line never overlap.
"""
import json
import threading
from datetime import datetime

from .. import auth, config, discover, ingest, playlists, profile, rank, webkit
from ..client import Client, TokenExpired
from ..errors import Beat50Error
from . import marks, state

STEPS = 3
_thread = None
_thread_lock = threading.Lock()
_login_window = None
_working = 0  # session checks and playlists running in request threads


def _client():
    # The token lasts 10 minutes: always a fresh one; if it expires midway, the client asks for another.
    return Client(auth.get_token(), renew=auth.get_token)


def _step(n, phase):
    state.update(running={"step": n, "of": STEPS, "phase": phase, "since": state.now()})


def _session(status):
    state.update(session={"status": status, "checked_at": state.now()})


def _error(e):
    """How a failure is kept in state.json: the English text plus the code to translate it."""
    if not isinstance(e, Beat50Error):
        return {"error": str(e), "error_code": None, "error_params": {}}
    return {"error": str(e), "error_code": e.code, "error_params": e.params}


def generate(trigger, today=None, now=None, since=None, until=None):
    """A new selection with its code YYYYMMDD_HHMMSS, leaving progress in state.json.

    Looks at releases between since and until (by default, the last 31 days) and leaves out the tracks
    of every earlier selection.
    """
    now = now or datetime.now()
    today = today or now.date()
    code = now.strftime("%Y%m%d_%H%M%S")
    with state.lock():
        started = state.now()
        try:
            _step(1, "library")
            client = _client()
            _session("active")
            lib = ingest.build_library(client)
            ingest.write_library(lib)
            prof = profile.build_profile(lib, today)
            profile.write_profile(prof)
            # The Genres dialog's choices shape this selection only; profile.json stays as the library says.
            prof = profile.apply_prefs(prof, state.read().get("genre_prefs") or {})
            _step(2, "discover")
            cand = discover.find_candidates(client, prof, until or today, since)
            discover.write_candidates(cand)
            _step(3, "rank")
            crate = rank.build_crate(cand, lib, prof, rank.previous_track_ids(config.CRATES_DIR, code))
            crate["id"] = code
            crate["genre_prefs"] = prof["genre_prefs"]
            path = rank.write_crate(crate)
        except Exception as e:
            if isinstance(e, (auth.SessionExpired, TokenExpired)):
                _session("expired")
            state.update(running=None, last_run={
                "trigger": trigger, "started_at": started, "finished_at": state.now(), "ok": False, **_error(e)})
            raise
        state.update(running=None, last_run={
            "trigger": trigger, "started_at": started, "finished_at": state.now(), "ok": True, "id": code})
        return path


def start_generation(today=None, since=None, until=None):
    """Runs a selection in a thread so the app answers at once. The result lands in state.json."""
    global _thread

    def work():
        try:
            generate("app", today=today, since=since, until=until)
        except Exception:
            pass  # already recorded in state.json by generate

    with _thread_lock:  # two quick requests must not start two selections
        if busy() or state.lock_owner():
            raise state.Busy("busy", "A selection is already running.")
        _thread = threading.Thread(target=work, daemon=True)
        _thread.start()
    return _thread


def busy():
    """Work is going on in this process (a selection, a session check, a playlist): quitting asks first."""
    return (_thread is not None and _thread.is_alive()) or _working > 0


class _Working:
    def __enter__(self):
        global _working
        with _thread_lock:
            _working += 1

    def __exit__(self, *exc):
        global _working
        with _thread_lock:
            _working -= 1


def check_session():
    """Asks for a token (in a hidden window) and records the result in the state."""
    with _Working(), state.lock():
        try:
            auth.get_token()
        except auth.SessionExpired:
            _session("expired")
            return False
        _session("active")
    return True


def login_start():
    """Opens Beatport's sign-in window; a thread waits for the user and records the session."""
    global _login_window
    with _thread_lock:
        if login_pending():
            raise Beat50Error("login_already", "A sign-in is already in progress.")
        window = _login_window = auth.login_window()

    def wait():
        global _login_window
        try:
            if auth.wait_for_login(window):
                _session("active")
        finally:
            _login_window = None

    thread = threading.Thread(target=wait, daemon=True)
    thread.start()
    return thread


def login_pending():
    return _login_window is not None


def abort_login():
    """Closes a sign-in window left open; called when the app quits."""
    window = _login_window
    if window is not None:
        webkit.close(window)


def create_playlist(selection, name, genres=None):
    """Creates the private Beatport playlist with the selection's starred tracks, in selection order.

    With genres (the app's filter), only the starred tracks of those genres.
    """
    crate = json.loads((config.CRATES_DIR / f"{selection}.json").read_text())
    starred = set(marks.read(selection)["starred"])
    ids = [t["id"] for t in crate["tracks"]
           if t["id"] in starred and (not genres or t.get("genre") in genres)]
    playlists.valid_name(name)  # name and selection are checked before reading the session
    if not ids:
        raise playlists.PlaylistError("no_starred", "No tracks are starred.")
    with _Working(), state.lock():
        try:
            result = playlists.create_playlist(_client(), name, ids)
        except (auth.SessionExpired, TokenExpired):
            _session("expired")
            raise
        _session("active")
    marks.add_playlist(selection, {"id": result["id"], "name": result["name"],
                                   "track_ids": result["track_ids"], "created_at": state.now()})
    return result


def edit_playlist(selection, playlist_id, name, remove=(), add=()):
    """Renames a playlist beat50 created and removes / adds tracks of its selection, all in one save."""
    playlist = marks.find_playlist(selection, playlist_id)
    if playlist is None:
        raise Beat50Error("not_found", "beat50 did not create that playlist.")
    crate = json.loads((config.CRATES_DIR / f"{selection}.json").read_text())
    if not set(add) <= {t["id"] for t in crate["tracks"]}:
        raise Beat50Error("not_in_selection", "That track is not in this selection.")
    clean = playlists.valid_name(name)
    new_name = clean if clean != playlist["name"] else None
    if new_name is None and not remove and not add:
        raise playlists.PlaylistError("no_changes", "There is nothing to save.")
    with _Working(), state.lock():
        try:
            result = playlists.edit_playlist(_client(), playlist_id, name=new_name, remove=remove, add=add)
        except (auth.SessionExpired, TokenExpired):
            _session("expired")
            raise
        except playlists.PlaylistError as e:
            if e.code == "playlist_gone":
                marks.update_playlist(selection, playlist_id, gone=True)
            raise
        _session("active")
    fields = {"edited_at": state.now()}
    if result["name"]:
        fields["name"] = result["name"]
    if result["track_ids"] is not None:
        fields["track_ids"] = result["track_ids"]
    marks.update_playlist(selection, playlist_id, **fields)
    return dict(result, name=result["name"] or playlist["name"])


def refresh_playlist(selection, playlist_id):
    """Brings the record of a created playlist up to date with Beatport: its name, its tracks (with the
    titles of those added outside the selection) or the fact that it was deleted there.

    Returns {"changed", "gone"}; the page reloads when something changed.
    """
    playlist = marks.find_playlist(selection, playlist_id)
    if playlist is None:
        raise Beat50Error("not_found", "beat50 did not create that playlist.")
    with _Working(), state.lock():
        try:
            live = playlists.read_playlist(_client(), playlist_id)
        except (auth.SessionExpired, TokenExpired):
            _session("expired")
            raise
        except playlists.PlaylistError as e:
            if e.code != "playlist_gone":
                raise
            marks.update_playlist(selection, playlist_id, gone=True)
            return {"changed": not playlist.get("gone"), "gone": True}
        _session("active")
    crate = json.loads((config.CRATES_DIR / f"{selection}.json").read_text())
    in_crate = {t["id"] for t in crate["tracks"]}
    fields = {"name": live["name"] or playlist["name"], "track_ids": live["track_ids"],
              "outside": {str(t): live["tracks"][t] for t in live["track_ids"] if t not in in_crate},
              "gone": False}
    changed = any(playlist.get(k, {} if k == "outside" else None) != v for k, v in fields.items()
                  if k != "gone") or bool(playlist.get("gone"))
    marks.update_playlist(selection, playlist_id, **fields)
    return {"changed": changed, "gone": False}


def forget_playlist(selection, playlist_id):
    """Drops beat50's record of a playlist deleted on Beatport. Only local: Beatport is not touched."""
    playlist = marks.find_playlist(selection, playlist_id)
    if playlist is None:
        raise Beat50Error("not_found", "beat50 did not create that playlist.")
    if not playlist.get("gone"):
        raise Beat50Error("not_gone", "That playlist still exists on Beatport.")
    marks.remove_playlist(selection, playlist_id)
