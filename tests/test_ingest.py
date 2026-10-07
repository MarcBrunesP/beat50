import json
from pathlib import Path

from beatcrate import ingest

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text())["results"]


def _one_track():
    return _fixture("catalog_tracks_sample.json")[0]


class FakeClient:
    """Answers with the real /my/ fixtures captured earlier."""

    def __init__(self, purchases=None):
        self.purchases = purchases if purchases is not None else _fixture("my_downloads.json")

    def paged(self, path, **kw):
        if path == "/my/playlists/":
            return _fixture("my_playlists.json")[:1]
        if path == "/my/playlists/1000001/tracks/":
            return _fixture("my_playlist_tracks.json")
        if path == "/my/downloads/":
            return self.purchases
        raise AssertionError(path)


def test_normalize_track_flattens_the_fields_the_profile_uses():
    t = ingest.normalize_track(_one_track(), origin="purchase", acquired_at="2026-01-15")
    assert t["id"] == 30501529
    assert t["label_id"] == 78787
    assert t["label_name"] == "Concord Records"
    assert t["artist_ids"] == [1374454]
    assert t["genre_id"] == 109
    assert t["bpm"] == 72
    assert t["key_camelot"] == "10B"
    assert t["isrc"] == "USC4R1906941"
    assert t["origin"] == "purchase"
    assert t["acquired_at"] == "2026-01-15"


def test_normalize_track_tolerates_a_null_sub_genre():
    t = ingest.normalize_track(_one_track(), origin="purchase", acquired_at=None)
    assert t["sub_genre_id"] is None
    assert t["sub_genre_name"] is None


def test_write_library_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
    target = tmp_path / "library.json"
    monkeypatch.setattr(ingest.config, "LIBRARY_FILE", target)
    monkeypatch.setattr(ingest.config, "DATA", tmp_path)
    ingest.write_library({"tracks": [{"id": 1}]})
    assert json.loads(target.read_text())["tracks"] == [{"id": 1}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_build_library_reads_real_purchases_and_playlists():
    lib = ingest.build_library(FakeClient())
    by_id = {t["id"]: t for t in lib["tracks"]}
    assert lib["source"] == {"playlists": 1, "purchases": 2}
    purchase = by_id[11618948]
    assert purchase["origin"] == "purchase"
    assert purchase["acquired_at"] == "2024-01-15"
    assert purchase["isrc"] is None
    assert purchase["label_name"] == "Creature Records"
    from_playlist = by_id[29727487]
    assert from_playlist["origin"] == "playlist:1000001"
    assert from_playlist["acquired_at"] == "2026-08-20"
    assert from_playlist["isrc"] == "GX3Q92639180"


def test_build_library_prefers_a_purchase_over_a_playlist():
    bought = dict(_fixture("my_playlist_tracks.json")[0]["track"], purchase_date="2026-09-10T10:00:00-06:00")
    lib = ingest.build_library(FakeClient(purchases=[bought]))
    t = next(t for t in lib["tracks"] if t["id"] == bought["id"])
    assert t["origin"] == "purchase"
    assert t["acquired_at"] == "2026-09-10"


def test_build_library_skips_playlist_items_without_a_track():
    class NoTrack(FakeClient):
        def paged(self, path, **kw):
            if path == "/my/playlists/1000001/tracks/":
                return [{"id": 1, "position": 1, "track": None, "tombstoned": True}]
            return super().paged(path, **kw)

    lib = ingest.build_library(NoTrack(purchases=[]))
    assert lib["tracks"] == []
