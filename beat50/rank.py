"""Scores the candidates, drops what the user already has and trims to a varied selection."""
import json
from datetime import datetime, timezone

from . import config


def previous_track_ids(crates_dir, current):
    """Ids already shown: every saved selection except `current`."""
    ids = set()
    if not crates_dir.exists():
        return ids
    for f in crates_dir.glob("*.json"):
        if f.stem == current:
            continue
        ids.update(t["id"] for t in json.loads(f.read_text()).get("tracks", []))
    return ids


def _weight(rows, wanted_id):
    for r in rows or []:
        if r["id"] == wanted_id:
            return r["weight"], r.get("name")
    return 0.0, None


def _bpm_fit(bpm, span):
    p10, p90 = span.get("p10"), span.get("p90")
    if not bpm or p10 is None or p90 is None:
        return 0.0
    if p10 <= bpm <= p90:
        return 1.0
    outside = p10 - bpm if bpm < p10 else bpm - p90
    return max(0.0, 1.0 - outside / 15.0)


def _camelot(key):
    if not key:
        return None
    n, l = key.get("camelot_number"), key.get("camelot_letter")
    return f"{n}{l}" if n and l else None


def _norm(text):
    return " ".join((text or "").lower().split())


def _same_song_key(artists, name, mix):
    """The same song on another release: artists + title + mix, ignoring case and extra spaces."""
    return tuple(sorted(_norm(a) for a in artists)), _norm(name), _norm(mix)


def score_track(track, profile):
    """Returns the score and the two strongest reasons, as {"kind", "value"} for the app to translate."""
    release = track.get("release") or {}
    label = release.get("label") or {}
    genre = track.get("genre") or {}

    w_label, label_name = _weight(profile.get("labels"), label.get("id"))
    artist_ids = [a["id"] for a in (track.get("artists") or []) + (track.get("remixers") or [])]
    best_artist, artist_name = 0.0, None
    for aid in artist_ids:
        w, name = _weight(profile.get("artists"), aid)
        if w > best_artist:
            best_artist, artist_name = w, name
    w_genre, genre_name = _weight(profile.get("genres"), genre.get("id"))
    bpm_fit = _bpm_fit(track.get("bpm"), profile.get("bpm") or {})
    key_fit = (profile.get("keys") or {}).get(_camelot(track.get("key")), 0.0)

    parts = [
        (config.W_LABEL * w_label, "label", label_name),
        (config.W_ARTIST * best_artist, "artist", artist_name),
        (config.W_GENRE * w_genre, "genre", genre_name),
        (config.W_BPM * bpm_fit, "bpm", track.get("bpm")),
        (config.W_KEY * key_fit, "key", _camelot(track.get("key"))),
    ]
    total = sum(p for p, _, _ in parts)
    reasons = [{"kind": kind, "value": value}
               for points, kind, value in sorted(parts, key=lambda x: x[0], reverse=True)
               if value and points > 0][:2]
    return round(total, 4), reasons


def _quotas(profile):
    """Slots per genre, proportional to its weight among the TOP_GENRES (largest remainder method)."""
    top = (profile.get("genres") or [])[:config.TOP_GENRES]
    total = sum(g["weight"] for g in top)
    if not total:
        return {}
    exact = {g["id"]: config.CRATE_SIZE * g["weight"] / total for g in top}
    quotas = {gid: int(v) for gid, v in exact.items()}
    left = config.CRATE_SIZE - sum(quotas.values())
    for gid in sorted(exact, key=lambda k: exact[k] - quotas[k], reverse=True)[:left]:
        quotas[gid] += 1
    return quotas


def _genre_allowed(profile, genre_id):
    """The user's genre preferences (profile.apply_prefs): a genre at level 0, or any other than the one chosen
    with "Only", never enters the selection, not even to fill the slots left over."""
    only = profile.get("genre_only")
    if only is not None:
        return genre_id == only
    return genre_id not in (profile.get("genres_off") or ())


def build_crate(candidates, library, profile, previous_ids):
    library_tracks = library.get("tracks", [])
    library_ids = {t["id"] for t in library_tracks}
    library_isrcs = {t["isrc"] for t in library_tracks if t.get("isrc")}
    # Purchases come without isrc: this key is what catches them.
    library_keys = {_same_song_key(t.get("artist_names") or [], t.get("name"), t.get("mix_name"))
                    for t in library_tracks}

    scored = []
    for t in candidates.get("tracks", []):
        if t["id"] in library_ids or t["id"] in previous_ids:
            continue
        if not _genre_allowed(profile, (t.get("genre") or {}).get("id")):
            continue
        if t.get("isrc") and t["isrc"] in library_isrcs:
            continue
        names = [a.get("name") for a in t.get("artists") or []]
        if _same_song_key(names, t.get("name"), t.get("mix_name")) in library_keys:
            continue
        score, reasons = score_track(t, profile)
        scored.append((score, reasons, t))
    scored.sort(key=lambda x: x[0], reverse=True)

    picked, per_label, per_artist, per_genre = [], {}, {}, {}
    quotas = _quotas(profile)

    def fits(t):
        label_id = ((t.get("release") or {}).get("label") or {}).get("id")
        if label_id and per_label.get(label_id, 0) >= config.MAX_PER_LABEL:
            return False
        return not any(per_artist.get(a["id"], 0) >= config.MAX_PER_ARTIST for a in t.get("artists") or [])

    def take(score, reasons, t):
        label_id = ((t.get("release") or {}).get("label") or {}).get("id")
        per_label[label_id] = per_label.get(label_id, 0) + 1
        for a in t.get("artists") or []:
            per_artist[a["id"]] = per_artist.get(a["id"], 0) + 1
        gid = (t.get("genre") or {}).get("id")
        per_genre[gid] = per_genre.get(gid, 0) + 1
        picked.append({
            "id": t["id"],
            "name": t.get("name"),
            "mix_name": t.get("mix_name"),
            "artists": [a.get("name") for a in t.get("artists") or []],
            "label": ((t.get("release") or {}).get("label") or {}).get("name"),
            "genre": (t.get("genre") or {}).get("name"),
            "bpm": t.get("bpm"),
            "key": _camelot(t.get("key")),
            "publish_date": t.get("publish_date"),
            "buy_url": f"{config.STORE}/track/{t.get('slug')}/{t['id']}",
            "sample_url": t.get("sample_url"),
            "image": (((t.get("release") or {}).get("image") or {}).get("dynamic_uri") or "")
                     .replace("{w}x{h}", "120x120") or None,
            "score": score,
            "reasons": reasons,
        })

    # First pass: each profile genre up to its quota, so the main one does not take everything.
    for score, reasons, t in scored:
        gid = (t.get("genre") or {}).get("id")
        if per_genre.get(gid, 0) < quotas.get(gid, 0) and fits(t):
            take(score, reasons, t)
    # Second pass: fill the slots left by genres without enough candidates, by score.
    picked_ids = {p["id"] for p in picked}
    for score, reasons, t in scored:
        if len(picked) >= config.CRATE_SIZE:
            break
        if t["id"] not in picked_ids and fits(t):
            take(score, reasons, t)
    picked.sort(key=lambda p: p["score"], reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": candidates.get("window", {}),
        "candidates_seen": len(candidates.get("tracks", [])),
        "short": len(picked) < config.CRATE_SIZE,
        "tracks": picked,
    }


def write_crate(crate):
    """Saves the selection under its code (YYYYMMDD_HHMMSS). Never overwrites an existing one."""
    config.CRATES_DIR.mkdir(parents=True, exist_ok=True)
    target = config.CRATES_DIR / f"{crate['id']}.json"
    with open(target, "x") as f:  # a repeated code (e.g. the clock went back) must not erase a selection
        f.write(json.dumps(crate, indent=2, ensure_ascii=False))
    return target
