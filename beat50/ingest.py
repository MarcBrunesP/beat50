"""Builds the taste library from the user's playlists and purchases."""
import json
from datetime import datetime, timezone

from . import config


def _camelot(key):
    if not key:
        return None
    number = key.get("camelot_number")
    letter = key.get("camelot_letter")
    return f"{number}{letter}" if number and letter else None


def normalize_track(raw, origin, acquired_at):
    release = raw.get("release") or {}
    label = release.get("label") or {}
    genre = raw.get("genre") or {}
    sub = raw.get("sub_genre") or {}
    return {
        "id": raw["id"],
        "name": raw.get("name"),
        "mix_name": raw.get("mix_name"),
        "artist_ids": [a["id"] for a in raw.get("artists") or []],
        "artist_names": [a.get("name") for a in raw.get("artists") or []],
        "remixer_ids": [a["id"] for a in raw.get("remixers") or []],
        "label_id": label.get("id"),
        "label_name": label.get("name"),
        "genre_id": genre.get("id"),
        "genre_name": genre.get("name"),
        "sub_genre_id": sub.get("id"),
        "sub_genre_name": sub.get("name"),
        "bpm": raw.get("bpm"),
        "key_camelot": _camelot(raw.get("key")),
        "isrc": raw.get("isrc"),  # /my/downloads/ does not include it
        "publish_date": raw.get("publish_date"),
        "slug": raw.get("slug"),
        "origin": origin,
        "acquired_at": acquired_at,
    }


def _date(value):
    return str(value)[:10] if value else None


def build_library(client):
    by_id = {}

    playlists = client.paged("/my/playlists/")
    for pl in playlists:
        updated = _date(pl.get("updated_date") or pl.get("created_date"))
        for item in client.paged(f"/my/playlists/{pl['id']}/tracks/"):
            if not item.get("track"):  # track withdrawn from the catalog
                continue
            t = normalize_track(item["track"], f"playlist:{pl['id']}", updated)
            by_id.setdefault(t["id"], t)

    # In /my/downloads/ each result already is the track, with its purchase_date.
    purchases = client.paged("/my/downloads/")
    for item in purchases:
        t = normalize_track(item, "purchase", _date(item.get("purchase_date")))
        by_id[t["id"]] = t  # a purchase always wins over a playlist

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"playlists": len(playlists), "purchases": len(purchases)},
        "tracks": list(by_id.values()),
    }


def write_library(lib):
    """Writes a temp file and renames it: never leaves a half-written library."""
    config.DATA.mkdir(parents=True, exist_ok=True)
    tmp = config.LIBRARY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(lib, indent=2, ensure_ascii=False))
    tmp.replace(config.LIBRARY_FILE)
