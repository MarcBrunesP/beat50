import threading

from beat50.app import marks


def test_without_a_file_it_returns_empty(data_dir):
    assert marks.read("20260901_090000") == {"starred": [], "playlists": []}


def test_star_and_unstar(data_dir):
    marks.set_star("20260901_090000", 1, True)
    marks.set_star("20260901_090000", 2, True)
    marks.set_star("20260901_090000", 1, False)
    assert marks.set_star("20260901_090000", 2, True) == [2]
    assert marks.read("20260901_090000")["starred"] == [2]


def test_two_quick_clicks_do_not_lose_a_star(data_dir):
    threads = [threading.Thread(target=marks.set_star, args=("20260901_090000", i, True)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(marks.read("20260901_090000")["starred"]) == list(range(40))


def test_add_playlist_saves_without_temp_files(data_dir):
    marks.add_playlist("20260901_090000", {"id": 9, "name": "x", "track_ids": [1], "created_at": "t"})
    assert marks.read("20260901_090000")["playlists"] == [
        {"id": 9, "name": "x", "track_ids": [1], "created_at": "t"}]
    assert list((data_dir / "marks").glob("*.tmp")) == []


def test_marks_are_kept_per_selection(data_dir):
    marks.set_star("2026-09", 1, True)
    marks.set_star("20260901_090000", 2, True)
    assert marks.read("2026-09")["starred"] == [1]
    assert marks.read("20260901_090000")["starred"] == [2]


def test_update_playlist_changes_only_that_playlist(data_dir):
    marks.add_playlist("2026-09", {"id": 1, "name": "A", "track_ids": [1], "created_at": "t"})
    marks.add_playlist("2026-09", {"id": 2, "name": "B", "track_ids": [2], "created_at": "t"})
    marks.update_playlist("2026-09", 2, name="B2", track_ids=[2, 3], edited_at="t2")
    assert marks.read("2026-09")["playlists"] == [
        {"id": 1, "name": "A", "track_ids": [1], "created_at": "t"},
        {"id": 2, "name": "B2", "track_ids": [2, 3], "created_at": "t", "edited_at": "t2"}]


def test_find_playlist_only_finds_beat50s_own(data_dir):
    marks.add_playlist("2026-09", {"id": 1, "name": "A", "track_ids": [1], "created_at": "t"})
    assert marks.find_playlist("2026-09", 1)["name"] == "A"
    assert marks.find_playlist("2026-09", 99) is None


def test_remove_playlist_forgets_only_that_one(data_dir):
    marks.add_playlist("2026-09", {"id": 1, "name": "A", "track_ids": [1], "created_at": "t"})
    marks.add_playlist("2026-09", {"id": 2, "name": "B", "track_ids": [2], "created_at": "t"})
    marks.remove_playlist("2026-09", 1)
    assert [p["id"] for p in marks.read("2026-09")["playlists"]] == [2]
