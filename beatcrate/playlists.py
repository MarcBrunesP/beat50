"""beatcrate's only writes to the user's Beatport account: creating private playlists and editing them.

It only edits playlists it created (the app checks that against its records). It never deletes a playlist,
never touches others and never changes whether a playlist is public.
"""
import urllib.error

from .auth import SessionExpired
from .client import TokenExpired
from .errors import BeatcrateError

# An expired session is never turned into a warning: the user has to sign in, and the app has to know.
SESSION_ENDED = (TokenExpired, SessionExpired)

MAX_NAME = 100
CHECK_FIRST = "Check beatport.com before retrying so it is not duplicated."


class PlaylistError(BeatcrateError):
    """The playlist cannot be created with this data, or Beatport failed."""


class PlaylistPublic(PlaylistError):
    """Beatport created it as public: stop without adding tracks."""


def valid_name(name):
    clean = " ".join((name or "").split())
    if not clean:
        raise PlaylistError("name_required", "The playlist needs a name.")
    if len(clean) > MAX_NAME:
        raise PlaylistError("name_too_long", f"The name cannot be longer than {MAX_NAME} characters.", max=MAX_NAME)
    return clean


def create_playlist(client, name, track_ids):
    """Creates the private playlist with these tracks, in this order, and reports which ones got in.

    Returns {"id", "name", "track_ids" (the ones that got in), "requested", "warnings"}.
    """
    clean = valid_name(name)
    if not track_ids:
        raise PlaylistError("no_starred", "No tracks are starred.")
    try:
        pl = client.post("/my/playlists/", {"name": clean})
    except urllib.error.HTTPError as e:
        if e.code >= 500:  # it may have been applied even though the response failed
            raise PlaylistError("create_unsure", f"Beatport failed while creating “{clean}” ({e}); it may exist. "
                                f"{CHECK_FIRST}", name=clean, detail=str(e)) from e
        raise PlaylistError("create_rejected", f"Beatport rejected creating “{clean}”: {e}",
                            name=clean, detail=str(e)) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise PlaylistError("create_unsure", f"No answer from Beatport while creating “{clean}” ({e}); it may exist. "
                            f"{CHECK_FIRST}", name=clean, detail=str(e)) from e
    if not isinstance(pl, dict) or not pl.get("id"):
        raise PlaylistError("create_unsure", f"Beatport did not return the playlist “{clean}”. {CHECK_FIRST}",
                            name=clean, detail="")
    if pl.get("is_public") is not False:
        raise PlaylistPublic("created_public", f"Beatport created “{clean}” as public (id {pl.get('id')}). Nothing "
                             "was added to it: make it private or delete it on beatport.com.",
                             name=clean, id=pl.get("id"))
    warnings = []
    try:
        client.post(f"/my/playlists/{pl['id']}/tracks/bulk/", {"track_ids": list(track_ids)})
    except Exception as e:  # the playlist exists: it is still returned so a retry does not duplicate it
        warnings.append({"code": "add_failed", "detail": str(e)})
    # From here on the playlist exists: whatever happens it is returned, to be saved and not duplicated.
    try:
        inside = {x["track"]["id"] for x in client.paged(f"/my/playlists/{pl['id']}/tracks/") if x.get("track")}
    except Exception as e:
        inside = set()
        warnings.append({"code": "count_unknown", "detail": str(e)})
    return {"id": pl["id"], "name": clean, "track_ids": [t for t in track_ids if t in inside],
            "requested": len(track_ids), "warnings": warnings}


def _tracks(client, playlist_id):
    """The playlist's items in order, as Beatport has them now."""
    items = client.paged(f"/my/playlists/{playlist_id}/tracks/")
    return [x for x in sorted(items, key=lambda x: x.get("position") or 0) if x.get("track")]


def _read(client, playlist_id):
    """The playlist record and its items as Beatport has them now, with errors in the user's terms."""
    try:
        return client.get(f"/my/playlists/{playlist_id}/") or {}, _tracks(client, playlist_id)
    except SESSION_ENDED:
        raise
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise PlaylistError("playlist_gone", "That playlist no longer exists on Beatport.") from e
        raise PlaylistError("edit_failed", f"Beatport did not answer properly while reading the playlist: {e}",
                            detail=str(e)) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise PlaylistError("edit_failed", f"Beatport did not answer properly while reading the playlist: {e}",
                            detail=str(e)) from e


def read_playlist(client, playlist_id):
    """{"name", "track_ids", "tracks": {id: {"name", "mix_name", "artists"}}} as the playlist is on Beatport."""
    pl, items = _read(client, playlist_id)
    tracks = {x["track"]["id"]: {"name": x["track"].get("name"), "mix_name": x["track"].get("mix_name"),
                                 "artists": [a.get("name") for a in x["track"].get("artists") or []]}
              for x in items}
    return {"name": pl.get("name"), "track_ids": [x["track"]["id"] for x in items], "tracks": tracks}


def edit_playlist(client, playlist_id, name=None, remove=(), add=()):
    """Renames the playlist (when name differs from its name on Beatport), removes and adds tracks.

    Works from the playlist as it is on Beatport now, so edits made on beatport.com are kept. Each step
    that fails becomes a warning and the others still run. Returns {"id", "name" (as it ends up),
    "track_ids" (as it ends up, or None if it could not be read again), "warnings"}.
    """
    clean = valid_name(name) if name is not None else None
    pl, items = _read(client, playlist_id)
    final_name = pl.get("name")
    inside = {x["track"]["id"] for x in items}
    warnings = []
    if clean is not None and clean != final_name:
        try:
            client.patch(f"/my/playlists/{playlist_id}/", {"name": clean})
            final_name = clean
        except SESSION_ENDED:
            raise
        except Exception as e:
            warnings.append({"code": "rename_failed", "detail": str(e)})
    item_ids = [x["id"] for x in items if x["track"]["id"] in set(remove)]
    if item_ids:
        try:
            client.delete(f"/my/playlists/{playlist_id}/tracks/bulk/", {"item_ids": item_ids})
        except SESSION_ENDED:
            raise
        except Exception as e:
            warnings.append({"code": "remove_failed", "detail": str(e)})
    new = [t for t in dict.fromkeys(add) if t not in inside]
    if new:
        try:
            client.post(f"/my/playlists/{playlist_id}/tracks/bulk/", {"track_ids": new})
        except SESSION_ENDED:
            raise
        except Exception as e:
            warnings.append({"code": "add_failed", "detail": str(e)})
    if item_ids or new:
        try:
            track_ids = [x["track"]["id"] for x in _tracks(client, playlist_id)]
        except Exception as e:
            track_ids = None
            warnings.append({"code": "count_unknown", "detail": str(e)})
    else:
        track_ids = [x["track"]["id"] for x in items]
    return {"id": playlist_id, "name": final_name, "track_ids": track_ids, "warnings": warnings}
