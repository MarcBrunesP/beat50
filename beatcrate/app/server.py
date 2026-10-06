"""The local app's server: routes, security (Host and token) and lifecycle (it lives as long as its window)."""
import json
import re
import secrets
import threading
import urllib.request
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import config, webkit
from ..errors import BeatcrateError
from . import consent, i18n, jobs, marks, state, trash, views

STATIC = Path(__file__).parent / "static"
STATIC_FILES = {"app.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8"}
# Selection id: YYYYMMDD_HHMMSS; the first ones, from before on-demand selections, are YYYY-MM.
SELECTION = re.compile(r"^(\d{8}_\d{6}|\d{4}-\d{2})$")
MAX_PERIOD_DAYS = 366
# Errors whose cause is not the request itself: a retry later or a sign-in may fix them.
CONFLICTS = {"busy", "session_expired", "login_already", "consent_required"}
# Routes that read the Beatport session (in a window of beatcrate's): only with the user's consent.
SESSION_ROUTES = ("/api/generate", "/api/session/check", "/api/login/start", "/api/playlist/")


def _period(body):
    """The since/until chosen in the app, validated; (None, None) when none were chosen."""
    if not body.get("since") and not body.get("until"):
        return None, None
    try:
        since, until = date.fromisoformat(body["since"]), date.fromisoformat(body["until"])
    except (KeyError, TypeError, ValueError):
        raise BeatcrateError("period_format", "Dates must be YYYY-MM-DD.") from None
    if until > date.today():
        raise BeatcrateError("period_future", "'until' cannot be later than today.")
    if since > until:
        raise BeatcrateError("period_order", "'since' cannot be later than 'until'.")
    if (until - since).days > MAX_PERIOD_DAYS:
        raise BeatcrateError("period_too_long", "The period cannot be longer than a year.")
    return since, until


def _selections():
    if not config.CRATES_DIR.exists():
        return []
    return [(f.stem, len(json.loads(f.read_text()).get("tracks", [])))
            for f in sorted(config.CRATES_DIR.glob("*.json"), reverse=True) if SELECTION.match(f.stem)]


def _crate(selection):
    path = config.CRATES_DIR / f"{selection}.json"
    return json.loads(path.read_text()) if SELECTION.match(selection) and path.exists() else None


def _delete(selection):
    """Moves a selection and its marks (stars, record of its playlists) to the Trash. Its tracks may then show up
    in new selections again; the playlists on Beatport are left as they are."""
    trash.move(config.CRATES_DIR / f"{selection}.json")
    marks_file = config.MARKS_DIR / f"{selection}.json"
    if marks_file.exists():
        trash.move(marks_file)


class App(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port):
        super().__init__((config.APP_HOST, port), Handler)
        bound = self.server_address[1]
        self.token = secrets.token_urlsafe(24)
        self.lang = "en"  # the language of the last page shown, for the quit dialog
        # Only these Host values: a site pointing its domain at 127.0.0.1 (DNS rebinding) gets a 403.
        self.hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the log for real errors

    def _lang(self):
        return i18n.pick(self.headers.get("Cookie"), self.headers.get("Accept-Language"))

    def _send(self, status, body, content_type, extra=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _fail(self, status, code, params=None, fallback=""):
        self._json(status, {"error": i18n.error(self._lang(), code, params, fallback)})

    def _state(self):
        st = dict(state.read(), login_pending=jobs.login_pending())
        # A `running` with nobody working comes from a process that died halfway (Mac switched off).
        if st.get("running") and not jobs.busy() and not state.lock_owner():
            st["running"] = None
        return st

    def do_GET(self):
        if self.headers.get("Host") not in self.server.hosts:
            return self._json(403, {"error": "host not allowed"})
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._json(200, {"app": "beatcrate"})
        if path == "/api/state":
            return self._json(200, self._state())
        if path.startswith("/static/") and path[len("/static/"):] in STATIC_FILES:
            name = path[len("/static/"):]
            return self._send(200, (STATIC / name).read_bytes(), STATIC_FILES[name])
        if path == "/":
            selections = _selections()
            if selections:
                return self._send(302, "", "text/plain", {"Location": f"/crate/{selections[0][0]}"})
            return self._page(None, None)
        if path.startswith("/crate/"):
            selection, _, rest = path[len("/crate/"):].partition("/playlist/")
            crate = _crate(selection)
            if crate is not None and not rest:
                return self._page(selection, crate)
            playlist = marks.find_playlist(selection, int(rest)) if crate and _digits(rest) else None
            if playlist is not None:
                return self._page(selection, crate, playlist)
        return self._fail(404, "not_found")

    def _page(self, selection, crate, playlist=None):
        st = dict(self._state(), consent=consent.granted())
        self.server.lang = self._lang()
        html = views.render_page(selection, crate, _selections(), st, self.server.token, date.today(),
                                 marks.read(selection) if selection else None, self.server.lang, playlist)
        self._send(200, html, "text/html; charset=utf-8")

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else {}
        if not isinstance(body, dict):
            raise ValueError("the body must be a JSON object")
        return body

    def do_POST(self):
        if self.headers.get("Host") not in self.server.hosts:
            return self._json(403, {"error": "host not allowed"})
        path = self.path.split("?")[0]
        try:
            body = self._body()
        except ValueError as e:
            return self._fail(400, "bad_request", fallback=str(e))
        sent = self.headers.get("X-Beatcrate-Token", "").encode()
        if not secrets.compare_digest(sent, self.server.token.encode()):
            return self._json(403, {"error": "invalid token"})
        try:
            return self._action(path, body)
        except BeatcrateError as e:
            return self._fail(409 if e.code in CONFLICTS else 400, e.code, e.params, str(e))
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def _action(self, path, body):
        if path == "/api/consent":
            if not isinstance(body.get("on"), bool):
                raise BeatcrateError("bad_request", "Missing \"on\" (true or false).")
            consent.grant() if body["on"] else consent.revoke()
            return self._json(200, {"ok": True})
        if path == "/api/help-seen":  # the onboarding has been shown; local only, reads nothing from Beatport
            state.update(help_seen=True)
            return self._json(200, {"ok": True})
        if path.startswith(SESSION_ROUTES) and not path.endswith("/forget"):  # forgetting is only local
            consent.require()
        if path == "/api/generate":
            since, until = _period(body)
            jobs.start_generation(since=since, until=until)
            return self._json(202, {"ok": True})
        if path == "/api/session/check":
            return self._json(200, {"active": jobs.check_session()})
        if path == "/api/login/start":
            jobs.login_start()
            return self._json(200, {"ok": True})
        if path.startswith("/api/star/"):
            parts = path[len("/api/star/"):].split("/")
            crate = _crate(parts[0]) if len(parts) == 2 else None
            if crate is None or not _digits(parts[1]):
                return self._fail(404, "not_found")
            ids = {t["id"] for t in crate["tracks"]}
            if int(parts[1]) not in ids:
                raise BeatcrateError("not_in_selection", "That track is not in this selection.")
            if not isinstance(body.get("on"), bool):
                raise BeatcrateError("bad_request", "Missing \"on\" (true or false).")
            starred = marks.set_star(parts[0], int(parts[1]), body["on"])
            return self._json(200, {"starred": len([t for t in starred if t in ids])})
        if path.startswith("/api/playlist/"):
            selection, slash, rest = path[len("/api/playlist/"):].partition("/")
            playlist_id, _, action = rest.partition("/")
            if _crate(selection) is None or (slash and not _digits(playlist_id)):
                return self._fail(404, "not_found")
            if slash:
                return self._playlist_action(selection, int(playlist_id), action, body)
            if jobs.busy() or state.lock_owner():
                raise state.Busy("busy", "beatcrate is already busy.")
            if not isinstance(body.get("name"), str):
                raise BeatcrateError("name_required", "The playlist needs a name.")
            genres = body.get("genres")
            if genres is not None and not (isinstance(genres, list) and all(isinstance(g, str) for g in genres)):
                raise BeatcrateError("bad_request", "\"genres\" must be a list of strings.")
            r = jobs.create_playlist(selection, body["name"], genres=genres or None)
            return self._json(200, {"ok": True, "message": _playlist_message(self._lang(), r)})
        if path.startswith("/api/selection/") and path.endswith("/delete"):  # only local: no permission needed
            selection = path[len("/api/selection/"):-len("/delete")]
            if _crate(selection) is None:
                return self._fail(404, "not_found")
            if jobs.busy() or state.lock_owner():
                raise state.Busy("busy", "beatcrate is already busy.")
            _delete(selection)
            return self._json(200, {"ok": True})  # the page knows where to go: home if it was showing it
        return self._fail(404, "not_found")

    def _playlist_action(self, selection, playlist_id, action, body):
        """Saving (no action), refreshing from Beatport or forgetting one of beatcrate's playlists."""
        if marks.find_playlist(selection, playlist_id) is None or action not in ("", "refresh", "forget"):
            return self._fail(404, "not_found")
        if action == "forget":
            jobs.forget_playlist(selection, playlist_id)
            return self._json(200, {"ok": True, "redirect": f"/crate/{selection}"})
        if jobs.busy() or state.lock_owner():
            raise state.Busy("busy", "beatcrate is already busy.")
        if action == "refresh":
            return self._json(200, jobs.refresh_playlist(selection, playlist_id))
        if not isinstance(body.get("name"), str):
            raise BeatcrateError("name_required", "The playlist needs a name.")
        if not (_ids(body.get("remove", [])) and _ids(body.get("add", []))):
            raise BeatcrateError("bad_request", "\"remove\" and \"add\" must be lists of track ids.")
        r = jobs.edit_playlist(selection, playlist_id, body["name"], remove=body.get("remove", []),
                               add=body.get("add", []))
        return self._json(200, {"ok": True, "message": _saved_message(self._lang(), r)})


def _digits(text):
    return text.isascii() and text.isdigit() and len(text) <= 18


def _ids(value):
    return isinstance(value, list) and all(isinstance(i, int) and not isinstance(i, bool) for i in value)


def _saved_message(lang, r):
    count = len(r["track_ids"]) if r["track_ids"] is not None else "?"
    message = i18n.t(lang, "playlist_saved", name=r["name"], n=count)
    for w in r.get("warnings", []):
        message += i18n.t(lang, f"warn_{w['code']}", detail=w.get("detail", ""))
    return message


def _playlist_message(lang, r):
    message = i18n.t(lang, "playlist_created", name=r["name"], n=len(r["track_ids"]))
    if len(r["track_ids"]) < r["requested"]:
        message += i18n.t(lang, "playlist_partial", n=len(r["track_ids"]), total=r["requested"])
    for w in r.get("warnings", []):
        message += i18n.t(lang, f"warn_{w['code']}", detail=w.get("detail", ""))
    return message


def _quit_texts(lang):
    return {"message": i18n.t(lang, "quit_busy"), "quit": i18n.t(lang, "quit"), "cancel": i18n.t(lang, "consent_cancel")}


def _already_open(url):
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
            return json.loads(r.read()).get("app") == "beatcrate"
    except (OSError, ValueError):
        return False


def run_app():
    """Serves the app on 127.0.0.1 and shows it in its own window; quits when the window closes."""
    url = f"http://{config.APP_HOST}:{config.APP_PORT}"
    if _already_open(url):  # e.g. `beatcrate app` from the terminal while the app is open
        print("beatcrate is already running.")
        return
    app = App(config.APP_PORT)
    threading.Thread(target=app.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    try:
        webkit.show_app(f"http://{config.APP_HOST}:{app.server_address[1]}", busy=jobs.busy,
                        texts=lambda: _quit_texts(app.lang))
    finally:
        jobs.abort_login()
        app.shutdown()
        app.server_close()
