from datetime import date

from beatcrate import profile


def _track(**kw):
    base = {"id": 1, "artist_ids": [10], "remixer_ids": [], "label_id": 100,
            "genre_id": 5, "genre_name": "Deep House", "label_name": "L",
            "artist_names": ["A"], "bpm": 124, "key_camelot": "10B",
            "origin": "purchase", "acquired_at": "2026-09-01"}
    base.update(kw)
    return base


TODAY = date(2026, 9, 7)


def test_decay_is_one_today_and_half_at_the_half_life():
    assert profile.decay("2026-09-07", TODAY) == 1.0
    at_18_months = profile.decay("2025-03-07", TODAY)
    assert 0.45 < at_18_months < 0.55


def test_decay_without_a_date_uses_a_middle_value():
    assert profile.decay(None, TODAY) == 0.5


def test_a_recent_purchase_weighs_more_than_an_old_one():
    lib = {"tracks": [
        _track(id=1, label_id=100, acquired_at="2026-09-01"),
        _track(id=2, label_id=200, acquired_at="2019-01-01"),
    ]}
    weights = {l["id"]: l["weight"] for l in profile.build_profile(lib, TODAY)["labels"]}
    assert weights[100] > weights[200]


def test_a_playlist_weighs_less_than_a_purchase_on_the_same_date():
    lib = {"tracks": [
        _track(id=1, label_id=100, origin="purchase", acquired_at="2026-09-01"),
        _track(id=2, label_id=200, origin="playlist:9", acquired_at="2026-09-01"),
    ]}
    weights = {l["id"]: l["weight"] for l in profile.build_profile(lib, TODAY)["labels"]}
    assert weights[100] > weights[200]


def test_the_top_weight_is_normalized_to_one():
    lib = {"tracks": [_track(id=1), _track(id=2, label_id=200)]}
    assert max(l["weight"] for l in profile.build_profile(lib, TODAY)["labels"]) == 1.0


def test_bpm_summarizes_percentiles_and_keys_frequency():
    lib = {"tracks": [_track(id=i, bpm=b, key_camelot="10B") for i, b in enumerate([118, 124, 130])]}
    prof = profile.build_profile(lib, TODAY)
    assert prof["bpm"]["median"] == 124
    assert prof["bpm"]["p10"] <= 118 and prof["bpm"]["p90"] >= 130
    assert prof["keys"]["10B"] == 1.0


def test_a_remixer_also_counts_as_an_artist():
    lib = {"tracks": [_track(id=1, artist_ids=[10], remixer_ids=[99])]}
    ids = {a["id"] for a in profile.build_profile(lib, TODAY)["artists"]}
    assert 99 in ids


def test_genres_come_from_genre_with_name_and_count():
    lib = {"tracks": [_track(id=1, genre_id=5), _track(id=2, genre_id=5),
                      _track(id=3, genre_id=6, genre_name="Techno (Peak Time / Driving)")]}
    genres = {g["id"]: g for g in profile.build_profile(lib, TODAY)["genres"]}
    assert genres[5]["n"] == 2 and genres[5]["name"] == "Deep House"
    assert genres[5]["weight"] == 1.0
    assert genres[6]["name"] == "Techno (Peak Time / Driving)"


def test_bpm_and_keys_also_decay_with_recency():
    lib = {"tracks": [_track(id=i, bpm=100, key_camelot="1A", acquired_at="2010-01-01") for i in range(3)]
           + [_track(id=9, bpm=130, key_camelot="8A", acquired_at="2026-09-01")]}
    prof = profile.build_profile(lib, TODAY)
    assert prof["bpm"]["median"] == 130
    assert prof["keys"]["8A"] > 0.9


def _prof(*genres):
    return {"genres": [{"id": i, "name": n, "weight": w, "n": 1} for i, n, w in genres], "labels": []}


def test_apply_prefs_without_choices_changes_nothing_and_records_nothing():
    prof = _prof((5, "Techno", 1.0), (6, "House", 0.4))
    adjusted = profile.apply_prefs(prof, {})
    assert adjusted["genres"] == prof["genres"]
    assert adjusted["genres_off"] == [] and adjusted["genre_only"] is None and adjusted["genre_prefs"] == []
    assert prof["genres"][0]["weight"] == 1.0  # the profile itself is untouched


def test_a_level_multiplies_the_weight_and_the_genres_are_normalised_and_reordered_again():
    adjusted = profile.apply_prefs(_prof((5, "Techno", 1.0), (6, "House", 0.4)), {"levels": {"6": 4}})
    assert [(g["id"], g["weight"]) for g in adjusted["genres"]] == [(6, 1.0), (5, 0.625)]
    assert adjusted["genre_prefs"] == [{"id": 6, "name": "House", "level": 4}]


def test_level_zero_leaves_the_genre_out():
    adjusted = profile.apply_prefs(_prof((5, "Techno", 1.0), (6, "House", 0.4)), {"levels": {"6": 0}})
    assert [g["id"] for g in adjusted["genres"]] == [5]
    assert adjusted["genres_off"] == [6]
    assert adjusted["genre_prefs"] == [{"id": 6, "name": "House", "level": 0}]


def test_only_keeps_one_genre_and_ignores_the_levels():
    adjusted = profile.apply_prefs(_prof((5, "Techno", 1.0), (6, "House", 0.4), (7, "Trance", 0.2)),
                                   {"levels": {"5": 4}, "only": 6})
    assert [(g["id"], g["weight"]) for g in adjusted["genres"]] == [(6, 1.0)]
    assert adjusted["genre_only"] == 6 and adjusted["genres_off"] == [5, 7]
    assert adjusted["genre_prefs"] == [{"id": 6, "name": "House", "level": "only"}]


def test_an_only_no_longer_in_the_profile_is_ignored():
    adjusted = profile.apply_prefs(_prof((5, "Techno", 1.0)), {"levels": {"5": 2}, "only": 99})
    assert adjusted["genre_only"] is None
    assert adjusted["genre_prefs"] == [{"id": 5, "name": "Techno", "level": 2}]


def test_read_profile_before_the_first_selection_is_empty(data_dir):
    assert profile.read_profile() == {}
    profile.write_profile({"genres": []})
    assert profile.read_profile() == {"genres": []}
