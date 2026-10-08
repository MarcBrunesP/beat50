"""Finds new releases in a period that fit the profile."""
import json
from datetime import datetime, timedelta, timezone

from . import config

CHART_SIZE = 100


def window(today):
    since = today - timedelta(days=config.WINDOW_DAYS)
    return since.isoformat(), today.isoformat()


def _ids(rows, top):
    return ",".join(str(r["id"]) for r in rows[:top] if r.get("id"))


def find_candidates(client, profile, until, since=None):
    """Releases published between since and until (by default, the WINDOW_DAYS before until)."""
    since, until = (since.isoformat(), until.isoformat()) if since else window(until)
    period = f"{since}:{until}"

    # Labels and artists: one query each, with comma-separated ids.
    queries = []
    labels = _ids(profile.get("labels") or [], config.TOP_LABELS)
    if labels:
        queries.append(lambda: client.paged("/catalog/tracks/", label_id=labels, publish_date=period))
    artists = _ids(profile.get("artists") or [], config.TOP_ARTISTS)
    if artists:
        queries.append(lambda: client.paged("/catalog/tracks/", artist_id=artists, publish_date=period))
    # Genres: filtering by genre_id returns tens of thousands of tracks a month; each genre's top-100
    # chart, trimmed to the period, is what is already selling.
    for g in (profile.get("genres") or [])[:config.TOP_GENRES]:
        def chart(gid=g["id"]):
            res = client.get(f"/catalog/genres/{gid}/top/{CHART_SIZE}/", per_page=CHART_SIZE)["results"]
            return [t for t in res if since <= (t.get("publish_date") or "") <= until]
        queries.append(chart)

    by_id, truncated = {}, False
    for query in queries:
        if client.requests >= config.MAX_REQUESTS:  # safety net, not an operating limit
            truncated = True
            break
        for t in query():
            by_id.setdefault(t["id"], t)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"from": since, "to": until},
        "truncated": truncated,
        "tracks": list(by_id.values()),
    }


def write_candidates(cand):
    config.DATA.mkdir(parents=True, exist_ok=True)
    tmp = config.CANDIDATES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cand, indent=2, ensure_ascii=False))
    tmp.replace(config.CANDIDATES_FILE)
