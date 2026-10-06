"""The user's marks per selection: starred tracks and the playlists created from them.

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
    """A playlist beatcrate created from this selection, or None: only those can be edited."""
    return next((p for p in read(selection)["playlists"] if p["id"] == playlist_id), None)


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
