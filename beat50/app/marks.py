"""The user's marks per selection: starred tracks and the playlists made from them.

A playlist is recorded in the selection it was created from, or that added tracks to it. One beat50 did not
create (one of the user's own) is marked `external`: beat50 only adds tracks to it.

Kept apart from the selection file. An in-process lock keeps two quick clicks from losing a star.
"""
import json
import os
import tempfile
import threading

from .. import config

_lock = threading.Lock()


def _path(selection):
    return config.MARKS_DIR / f"{selection}.json"


def read(selection):
    path = _path(selection)
    data = json.loads(path.read_text()) if path.exists() else {}
    return {"starred": data.get("starred", []), "playlists": data.get("playlists", [])}


def _write(selection, data):
    config.MARKS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.MARKS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _path(selection))
    except BaseException:
        os.unlink(tmp)
        raise


def set_star(selection, track_id, on):
    with _lock:
        data = read(selection)
        starred = [t for t in data["starred"] if t != track_id]
        if on:
            starred.append(track_id)
        data["starred"] = starred
        _write(selection, data)
        return starred


def add_playlist(selection, playlist):
    with _lock:
        data = read(selection)
        data["playlists"].append(playlist)
        _write(selection, data)


def find_playlist(selection, playlist_id):
    """A playlist recorded in this selection, or None: only those can be opened and edited."""
    return next((p for p in read(selection)["playlists"] if p["id"] == playlist_id), None)


def created_by_beat50(playlist_id):
    """Whether any selection recorded this playlist as created by beat50 (not as `external`)."""
    files = config.MARKS_DIR.glob("*.json") if config.MARKS_DIR.exists() else ()
    return any(p["id"] == playlist_id and not p.get("external")
               for f in files for p in read(f.stem)["playlists"])


def update_playlist(selection, playlist_id, **fields):
    with _lock:
        data = read(selection)
        for p in data["playlists"]:
            if p["id"] == playlist_id:
                p.update(fields)
        _write(selection, data)


def remove_playlist(selection, playlist_id):
    with _lock:
        data = read(selection)
        data["playlists"] = [p for p in data["playlists"] if p["id"] != playlist_id]
        _write(selection, data)
