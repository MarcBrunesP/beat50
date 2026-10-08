import json

import pytest

from beat50 import rank

PROFILE = {
    "labels": [{"id": 100, "name": "Afterlife", "weight": 1.0, "n": 12},
               {"id": 200, "name": "Other", "weight": 0.1, "n": 1}],
    "artists": [{"id": 10, "name": "Tale Of Us", "weight": 1.0, "n": 5}],
    "genres": [{"id": 5, "name": "Melodic House", "weight": 1.0, "n": 30}],
    "bpm": {"p10": 118, "median": 124, "p90": 132},
    "keys": {"10B": 0.5},
}


def _cand(id, label=100, artists=(10,), bpm=124, key="10B", isrc=None, genre=5, name=None, mix="Original Mix"):
    return {"id": id, "name": name or f"t{id}", "mix_name": mix, "slug": f"t{id}",
            "artists": [{"id": a, "name": f"a{a}"} for a in artists],
            "remixers": [], "bpm": bpm, "isrc": isrc,
            "key": {"camelot_number": 10, "camelot_letter": "B"} if key else None,
            "release": {"label": {"id": label, "name": "L"}},
            "genre": {"id": genre, "name": "G"}, "sub_genre": None,
            "publish_date": "2026-09-01"}


def _crate(cands, lib=None, previous=frozenset()):
    return rank.build_crate({"tracks": cands, "window": {}}, lib or {"tracks": []}, PROFILE, set(previous))


def test_the_favorite_label_track_scores_higher():
    good, _ = rank.score_track(_cand(1, label=100), PROFILE)
    bad, _ = rank.score_track(_cand(2, label=200, artists=(999,), genre=999), PROFILE)
    assert good > bad


def test_reasons_name_the_two_main_factors():
    _, reasons = rank.score_track(_cand(1), PROFILE)
    assert reasons == [{"kind": "label", "value": "Afterlife"},
                       {"kind": "artist", "value": "Tale Of Us"}]


def test_genre_scores_and_appears_in_the_reasons():
    with_genre, reasons = rank.score_track(_cand(1, label=999, artists=(999,), genre=5), PROFILE)
    without, _ = rank.score_track(_cand(2, label=999, artists=(999,), genre=999), PROFILE)
    assert with_genre > without
    assert {"kind": "genre", "value": "Melodic House"} in reasons


def test_reasons_are_at_most_two_and_only_for_factors_that_scored():
    _, reasons = rank.score_track(_cand(1, label=999, artists=(999,), genre=999, bpm=None, key=None), PROFILE)
    assert reasons == []
    _, reasons = rank.score_track(_cand(1), PROFILE)
    assert len(reasons) == 2
    assert all(set(r) == {"kind", "value"} for r in reasons)


def test_excludes_ids_already_in_the_library():
    crate = _crate([_cand(1), _cand(2)], lib={"tracks": [{"id": 1, "isrc": None}]})
    assert [t["id"] for t in crate["tracks"]] == [2]


def test_excludes_by_isrc_even_if_the_id_differs():
    crate = _crate([_cand(1, isrc="AAA"), _cand(2)], lib={"tracks": [{"id": 999, "isrc": "AAA"}]})
    assert [t["id"] for t in crate["tracks"]] == [2]


def test_excludes_by_artists_title_and_mix_even_without_an_isrc():
    bought = {"id": 999, "isrc": None, "artist_names": ["a20", "A10 "],
              "name": "Radiate", "mix_name": "Original  Mix"}
    cands = [_cand(1, artists=(10, 20), name="radiate"),
             _cand(2, artists=(10, 20), name="Radiate", mix="Extended Mix")]
    crate = _crate(cands, lib={"tracks": [bought]})
    assert [t["id"] for t in crate["tracks"]] == [2]


def test_excludes_tracks_from_previous_selections():
    crate = _crate([_cand(1), _cand(2)], previous={1})
    assert [t["id"] for t in crate["tracks"]] == [2]


def test_limits_to_three_tracks_per_label():
    crate = _crate([_cand(i, label=100, artists=(i,)) for i in range(1, 8)])
    assert len(crate["tracks"]) == 3


def test_limits_to_two_tracks_per_artist():
    crate = _crate([_cand(i, label=100 + i, artists=(10,)) for i in range(1, 6)])
    assert len(crate["tracks"]) == 2


def test_the_selection_does_not_exceed_fifty():
    crate = _crate([_cand(i, label=1000 + i, artists=(2000 + i,)) for i in range(200)])
    assert len(crate["tracks"]) == 50
    assert crate["short"] is False


def test_a_short_selection_is_flagged():
    assert _crate([_cand(1)])["short"] is True


def test_each_track_carries_a_store_link_a_score_and_reasons():
    t = _crate([_cand(7)])["tracks"][0]
    assert t["buy_url"] == "https://www.beatport.com/track/t7/7"
    assert t["score"] > 0
    assert t["reasons"]
    assert "reason" not in t


def _saved_crate(code="20260930_080000", tracks=None):
    return {"id": code, "generated_at": "2026-09-30T08:00:00+00:00", "window": {"to": "2026-09-30"},
            "tracks": tracks or [{"id": 1}]}


def test_write_crate_saves_it_under_its_code(tmp_path, monkeypatch):
    monkeypatch.setattr(rank.config, "CRATES_DIR", tmp_path)
    path = rank.write_crate(_saved_crate("20260930_080000"))
    assert path == tmp_path / "20260930_080000.json"
    assert json.loads(path.read_text())["tracks"] == [{"id": 1}]


def test_write_crate_creates_the_directory(tmp_path, monkeypatch):
    target = tmp_path / "crates"
    monkeypatch.setattr(rank.config, "CRATES_DIR", target)
    rank.write_crate(_saved_crate())
    assert (target / "20260930_080000.json").exists()


def _two_genre_profile():
    return dict(PROFILE, genres=[{"id": 5, "name": "A", "weight": 1.0}, {"id": 6, "name": "B", "weight": 1.0}])


def test_quotas_are_proportional_to_the_weight_and_add_up_to_the_selection_size():
    profile = dict(PROFILE, genres=[{"id": i, "weight": w} for i, w in
                                    enumerate([1.0, 0.30, 0.21, 0.18, 0.14], start=1)])
    quotas = rank._quotas(profile)
    assert [quotas[i] for i in range(1, 6)] == [27, 8, 6, 5, 4]
    assert sum(quotas.values()) == 50


def test_quotas_are_empty_without_genres():
    assert rank._quotas(dict(PROFILE, genres=[])) == {}


def test_each_genre_stops_at_its_quota():
    # Genre 5 tracks score higher (they have a key); without quotas they would take the whole selection.
    strong = [_cand(i, label=1000 + i, artists=(2000 + i,), genre=5) for i in range(60)]
    weak = [_cand(100 + i, label=3000 + i, artists=(4000 + i,), genre=6, key=None) for i in range(30)]
    crate = rank.build_crate({"tracks": strong + weak, "window": {}}, {"tracks": []}, _two_genre_profile(), set())
    ids = [t["id"] for t in crate["tracks"]]
    assert sum(1 for i in ids if i < 100) == 25
    assert sum(1 for i in ids if i >= 100) == 25


def test_gaps_in_a_short_genre_are_filled_by_score():
    strong = [_cand(i, label=1000 + i, artists=(2000 + i,), genre=5) for i in range(60)]
    weak = [_cand(100 + i, label=3000 + i, artists=(4000 + i,), genre=6, key=None) for i in range(5)]
    crate = rank.build_crate({"tracks": strong + weak, "window": {}}, {"tracks": []}, _two_genre_profile(), set())
    ids = [t["id"] for t in crate["tracks"]]
    assert len(ids) == 50
    assert sum(1 for i in ids if i >= 100) == 5
    scores = [t["score"] for t in crate["tracks"]]
    assert scores == sorted(scores, reverse=True)


def test_previous_track_ids_counts_every_saved_selection_except_the_current_one(tmp_path):
    (tmp_path / "20260701_090000.json").write_text(json.dumps({"tracks": [{"id": 1}]}))
    (tmp_path / "20260801_090000.json").write_text(json.dumps({"tracks": [{"id": 2}]}))
    (tmp_path / "20260901_090000.json").write_text(json.dumps({"tracks": [{"id": 3}]}))
    assert rank.previous_track_ids(tmp_path, "20260901_090000") == {1, 2}


def test_previous_track_ids_is_empty_when_there_are_no_selections(tmp_path):
    assert rank.previous_track_ids(tmp_path / "missing", "20260901_090000") == set()


def test_each_track_carries_a_preview_and_a_cover():
    c = _cand(7)
    c["sample_url"] = "https://geo-samples.beatport.com/track/abc.LOFI.mp3"
    c["release"]["image"] = {"dynamic_uri": "https://geo-media.beatport.com/image_size/{w}x{h}/abc.jpg"}
    t = _crate([c])["tracks"][0]
    assert t["sample_url"] == "https://geo-samples.beatport.com/track/abc.LOFI.mp3"
    assert t["image"] == "https://geo-media.beatport.com/image_size/120x120/abc.jpg"


def test_without_a_preview_or_cover_they_are_none():
    t = _crate([_cand(7)])["tracks"][0]
    assert t["sample_url"] is None
    assert t["image"] is None


def test_write_crate_refuses_to_overwrite_an_existing_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(rank.config, "CRATES_DIR", tmp_path)
    rank.write_crate(_saved_crate("20260930_080000", tracks=[{"id": 1}]))
    with pytest.raises(FileExistsError):
        rank.write_crate(_saved_crate("20260930_080000", tracks=[{"id": 2}]))
    assert json.loads((tmp_path / "20260930_080000.json").read_text())["tracks"] == [{"id": 1}]


def test_a_genre_switched_off_never_enters_not_even_to_fill_the_gaps():
    prof = dict(PROFILE, genres_off=[999])
    crate = rank.build_crate({"tracks": [_cand(1, genre=999), _cand(2)]}, {"tracks": []}, prof, set())
    assert [t["id"] for t in crate["tracks"]] == [2]


def test_with_only_every_other_genre_stays_out():
    prof = dict(PROFILE, genre_only=5)
    cands = [_cand(1, genre=999), _cand(2), _cand(3, genre=7)]
    crate = rank.build_crate({"tracks": cands}, {"tracks": []}, prof, set())
    assert [t["id"] for t in crate["tracks"]] == [2]
    assert crate["short"] is True
