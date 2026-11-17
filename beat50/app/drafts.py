"""Drafts: playlists that only exist on this Mac until the user uploads one to Beatport.

A draft keeps its tracks whole (what the page shows: names, BPM, key, preview), taken from a selection or from one
of the user's Beatport playlists, so it is listened to and put in order without asking Beatport for anything.
Uploading creates a new private playlist (jobs.upload_draft); from then on the draft is a record and cannot change.

One file per draft, written atomically under an in-process lock, like the marks.
"""
import json
import os
import re
import tempfile
import threading
import uuid

from .. import config, playlists
from ..errors import Beat50Error
from . import state

ID = re.compile(r"^[0-9a-f]{12}$")
# What a draft keeps of each track; `length` and `length_ms` only come with tracks taken from a Beatport playlist.
TRACK_KEYS = ("id", "name", "mix_name", "artists", "label", "genre", "bpm", "key", "length", "length_ms", "sample_url",
              "image")
_lock = threading.Lock()


def _path(draft_id):
    return config.DRAFTS_DIR / f"{draft_id}.json"


def read(draft_id):
    """The draft, or None if there is none with that id."""
    if not ID.match(draft_id) or not _path(draft_id).exists():
        return None
    return json.loads(_path(draft_id).read_text())


def _write(draft):
    config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.DRAFTS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _path(draft["id"]))
    except BaseException:
        os.unlink(tmp)
        raise


def _open(draft_id):
    """The draft to change: it has to exist and not be uploaded yet."""
    draft = read(draft_id)
    if draft is None:
        raise Beat50Error("not_found", "There is no such draft.")
    if draft.get("uploaded"):
        raise Beat50Error("draft_uploaded", f"“{draft['name']}” was already uploaded to Beatport: it no longer changes.",
                          name=draft["name"])
    return draft


def list_all():
    """Every draft, newest first."""
    files = config.DRAFTS_DIR.glob("*.json") if config.DRAFTS_DIR.exists() else ()
    found = [json.loads(f.read_text()) for f in files if ID.match(f.stem)]
    return sorted(found, key=lambda d: d["created_at"], reverse=True)


def create(name):
    draft = {"id": uuid.uuid4().hex[:12], "name": playlists.valid_name(name), "created_at": state.now(),
             "updated_at": state.now(), "tracks": [], "uploaded": None}
    with _lock:
        _write(draft)
    return draft


def add(draft_id, tracks):
    """Adds these tracks at the end, leaving out the ones already in it. Returns (draft, how many got in)."""
    with _lock:
        draft = _open(draft_id)
        inside = {t["id"] for t in draft["tracks"]}
        new = []
        for t in tracks:
            if t["id"] not in inside:
                inside.add(t["id"])
                new.append({k: t.get(k) for k in TRACK_KEYS})
        if new:
            draft["tracks"] += new
            draft["updated_at"] = state.now()
            _write(draft)
        return draft, len(new)


def save(draft_id, name, track_ids):
    """The draft as the page left it: its name and its tracks in this order (the ones left out are removed)."""
    clean = playlists.valid_name(name)
    with _lock:
        draft = _open(draft_id)
        by_id = {t["id"]: t for t in draft["tracks"]}
        if len(set(track_ids)) != len(track_ids) or not set(track_ids) <= set(by_id):
            raise Beat50Error("bad_request", "\"track_ids\" must be tracks of the draft, each one once.")
        draft.update(name=clean, tracks=[by_id[t] for t in track_ids], updated_at=state.now())
        _write(draft)
        return draft


def set_uploaded(draft_id, playlist_id, name, tracks):
    """Records the Beatport playlist the draft became; from now on the draft does not change."""
    with _lock:
        draft = read(draft_id)
        draft["uploaded"] = {"playlist_id": playlist_id, "name": name, "tracks": tracks, "at": state.now()}
        _write(draft)
        return draft
