"""beat50's only writes to the user's Beatport account: creating private playlists, editing them, adding
tracks to the user's own private playlists and putting their tracks in another order.

It only renames or removes tracks from playlists it created (the app checks that against its records). In the
user's other playlists it only adds tracks or reorders them, and only in private ones they own. It never deletes a
playlist and never changes whether a playlist is public.
"""
import urllib.error

from .auth import SessionExpired
from .client import TokenExpired
from .errors import Beat50Error

# An expired session is never turned into a warning: the user has to sign in, and the app has to know.
SESSION_ENDED = (TokenExpired, SessionExpired)

MAX_NAME = 100
CHECK_FIRST = "Check beatport.com before retrying so it is not duplicated."


class PlaylistError(Beat50Error):
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


def _tracks(client, playlist_id, every=False):
    """The playlist's items in order, as Beatport has them now; with every, also the ones whose track Beatport
    withdrew (no `track`), which still hold a position."""
    items = client.paged(f"/my/playlists/{playlist_id}/tracks/")
    return [x for x in sorted(items, key=lambda x: x.get("position") or 0) if every or x.get("track")]


def _read(client, playlist_id, every=False):
    """The playlist record and its items as Beatport has them now, with errors in the user's terms."""
    try:
        return client.get(f"/my/playlists/{playlist_id}/") or {}, _tracks(client, playlist_id, every)
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


def list_playlists(client):
    """The user's own playlists, most recently updated first: [{"id", "name", "track_count", "is_public"}].

    Public ones are listed too, so the user sees them, but add_to_playlist refuses them.
    """
    try:
        items = client.paged("/my/playlists/")
    except SESSION_ENDED:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        raise PlaylistError("list_failed", f"Beatport did not answer properly while listing your playlists: {e}",
                            detail=str(e)) from e
    own = sorted((p for p in items if p.get("is_owner") is True), key=lambda p: p.get("updated_date") or "",
                 reverse=True)
    return [{"id": p["id"], "name": p.get("name") or "", "track_count": p.get("track_count") or 0,
             "is_public": p.get("is_public") is not False, "length_ms": p.get("length_ms") or 0,
             "bpm_range": p.get("bpm_range") or [], "genres": p.get("genres") or [],
             "image": next(iter(p.get("release_images") or []), None)} for p in own]


def _summary(t):
    """A track as the page shows it, with its Camelot key and its length for the manager."""
    key = t.get("key") or {}
    image = ((t.get("release") or {}).get("image") or {}).get("dynamic_uri") or ""
    return {"id": t["id"], "name": t.get("name"), "mix_name": t.get("mix_name"),
            "artists": [a.get("name") for a in t.get("artists") or []],
            "label": ((t.get("release") or {}).get("label") or {}).get("name"),
            "genre": (t.get("genre") or {}).get("name"), "bpm": t.get("bpm"),
            "key": f"{key['camelot_number']}{key['camelot_letter']}" if key.get("camelot_number") and
                   key.get("camelot_letter") else None,
            "length": t.get("length"), "length_ms": t.get("length_ms"), "sample_url": t.get("sample_url"),
            "image": image.replace("{w}x{h}", "120x120") or None}


def _editable(pl, playlist_id, client):
    """Whether beat50 may write in this playlist: the user's (fail closed) and private."""
    owner = pl.get("is_owner")
    if owner is None:  # the playlist's own record may not say: the list of the user's playlists does
        owner = any(p["id"] == playlist_id for p in list_playlists(client))
    return owner is True, pl.get("is_public") is False


def read_items(client, playlist_id):
    """One of the user's playlists for the manager, every item in order (a withdrawn track has `track` None):
    {"id", "name", "owner", "private", "items": [{"item_id", "track"}]}."""
    pl, items = _read(client, playlist_id, every=True)
    owner, private = _editable(pl, playlist_id, client)
    return {"id": playlist_id, "name": pl.get("name"), "owner": owner, "private": private,
            "items": [{"item_id": x["id"], "track": _summary(x["track"]) if x.get("track") else None}
                      for x in items]}


def reorder_playlist(client, playlist_id, item_ids):
    """Puts the items of one of the user's private playlists in this order (all of them, by item id).

    Checks against the playlist as it is on Beatport now: it refuses one that is public or not the user's, and one
    whose items changed since the page read them, so nothing added or removed meanwhile is lost. Returns {"id",
    "name", "warnings"}; "order_unknown" when the order could not be read back as asked.
    """
    pl, items = _read(client, playlist_id, every=True)
    name = pl.get("name")
    owner, private = _editable(pl, playlist_id, client)
    if not owner:
        raise PlaylistError("not_owner_order", f"“{name}” is not one of your playlists: beat50 does not reorder it.",
                            name=name)
    if not private:
        raise PlaylistError("public_order", f"“{name}” is public: beat50 only reorders private playlists.",
                            name=name)
    now = [x["id"] for x in items]
    if len(item_ids) != len(now) or set(item_ids) != set(now):
        raise PlaylistError("playlist_changed", f"“{name}” changed on Beatport since it was opened: open it again.",
                            name=name)
    warnings = []
    if item_ids != now:
        try:
            client.patch(f"/my/playlists/{playlist_id}/tracks/bulk/",
                         {"items": [{"position": n, "item_id": i} for n, i in enumerate(item_ids, 1)]})
        except SESSION_ENDED:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            raise PlaylistError("order_failed", f"Beatport did not save the order of “{name}”: {e}",
                                name=name, detail=str(e)) from e
        try:
            if [x["id"] for x in _tracks(client, playlist_id, every=True)] != list(item_ids):
                warnings.append({"code": "order_unknown", "detail": ""})
        except SESSION_ENDED:
            raise
        except Exception as e:
            warnings.append({"code": "order_unknown", "detail": str(e)})
    return {"id": playlist_id, "name": name, "warnings": warnings}


def add_to_playlist(client, playlist_id, track_ids):
    """Adds to one of the user's private playlists the tracks it does not have yet, at the end, in this order.

    Checks against the playlist as it is on Beatport now, so tracks already in it (added by beat50 or on
    beatport.com) are never added twice. Returns {"id", "name", "track_ids" (as it ends up, or None if it could
    not be read again), "added" (the ones that got in), "already" (how many were in it), "warnings"}.
    """
    if not track_ids:
        raise PlaylistError("no_starred", "No tracks are starred.")
    pl, items = _read(client, playlist_id)
    name = pl.get("name")
    owner, private = _editable(pl, playlist_id, client)
    if not owner:  # fail closed: only a playlist Beatport says is the user's
        raise PlaylistError("not_owner", f"“{name}” is not one of your playlists: beat50 does not add to it.",
                            name=name)
    if not private:
        raise PlaylistError("playlist_public", f"“{name}” is public: beat50 only adds tracks to private "
                            "playlists.", name=name)
    inside = {x["track"]["id"] for x in items}
    wanted = list(dict.fromkeys(track_ids))
    new = [t for t in wanted if t not in inside]
    warnings = []
    track_ids_now = [x["track"]["id"] for x in items]
    if new:
        try:
            client.post(f"/my/playlists/{playlist_id}/tracks/bulk/", {"track_ids": new})
        except SESSION_ENDED:
            raise
        except Exception as e:
            warnings.append({"code": "add_failed", "detail": str(e)})
        try:
            track_ids_now = [x["track"]["id"] for x in _tracks(client, playlist_id)]
        except Exception as e:
            track_ids_now = None
            warnings.append({"code": "count_unknown", "detail": str(e)})
    got = set(track_ids_now or ())
    added = [t for t in new if t in got]
    return {"id": playlist_id, "name": name, "track_ids": track_ids_now, "added": added,
            "already": len(wanted) - len(new), "warnings": warnings}


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
