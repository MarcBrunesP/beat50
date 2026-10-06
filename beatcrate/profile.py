"""Summarises the library as label, artist and genre weights, plus BPM and key."""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from . import config

DAYS_PER_MONTH = 30.44


def decay(acquired_at, today):
    """Recency weight: halves every HALFLIFE_MONTHS."""
    if not acquired_at:
        return 0.5
    try:
        d = date.fromisoformat(acquired_at[:10])
    except ValueError:
        return 0.5
    months = max((today - d).days, 0) / DAYS_PER_MONTH
    return 0.5 ** (months / config.HALFLIFE_MONTHS)


def _percentile(pairs, q):
    """Weighted percentile of (value, weight): the first value that accumulates fraction q of the weight."""
    if not pairs:
        return None
    ordered = sorted(pairs)
    target = q * sum(weight for _, weight in ordered)
    accumulated = 0.0
    for value, weight in ordered:
        accumulated += weight
        if accumulated >= target:
            return value
    return ordered[-1][0]


def _normalize(raw, names, counts):
    if not raw:
        return []
    top = max(raw.values())
    rows = [{"id": k, "name": names.get(k), "weight": round(v / top, 4), "n": counts[k]}
            for k, v in raw.items()]
    return sorted(rows, key=lambda r: r["weight"], reverse=True)


def build_profile(library, today):
    labels, artists, genres = defaultdict(float), defaultdict(float), defaultdict(float)
    counts = defaultdict(Counter)
    label_names, artist_names, genre_names = {}, {}, {}
    bpms, keys = [], defaultdict(float)  # weighted with the same decay

    for t in library["tracks"]:
        factor = config.ORIGIN_PURCHASE if t.get("origin") == "purchase" else config.ORIGIN_PLAYLIST
        weight = decay(t.get("acquired_at"), today) * factor

        if t.get("label_id"):
            labels[t["label_id"]] += weight
            counts["label"][t["label_id"]] += 1
            label_names[t["label_id"]] = t.get("label_name")
        # Names only come for artists, not for remixers.
        names = t.get("artist_names") or []
        for i, aid in enumerate(t.get("artist_ids") or []):
            artists[aid] += weight
            counts["artist"][aid] += 1
            if i < len(names):
                artist_names.setdefault(aid, names[i])
        for aid in t.get("remixer_ids") or []:
            artists[aid] += weight
            counts["artist"][aid] += 1
        # Beatport's fine-grained genre (e.g. "Techno (Peak Time / Driving)"); sub_genre is almost always null.
        if t.get("genre_id"):
            genres[t["genre_id"]] += weight
            counts["genre"][t["genre_id"]] += 1
            genre_names[t["genre_id"]] = t.get("genre_name")
        if t.get("bpm"):
            bpms.append((t["bpm"], weight))
        if t.get("key_camelot"):
            keys[t["key_camelot"]] += weight

    total_keys = sum(keys.values()) or 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "labels": _normalize(labels, label_names, counts["label"]),
        "artists": _normalize(artists, artist_names, counts["artist"]),
        "genres": _normalize(genres, genre_names, counts["genre"]),
        "bpm": {"p10": _percentile(bpms, 0.10),
                "median": _percentile(bpms, 0.50),
                "p90": _percentile(bpms, 0.90)},
        "keys": {k: round(v / total_keys, 4) for k, v in keys.items()},
        "totals": {"tracks": len(library["tracks"])},
    }


def write_profile(prof):
    config.DATA.mkdir(parents=True, exist_ok=True)
    tmp = config.PROFILE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(prof, indent=2, ensure_ascii=False))
    tmp.replace(config.PROFILE_FILE)
