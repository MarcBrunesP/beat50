import json

import pytest

from beat50.app import drafts
from beat50.errors import Beat50Error


def _t(i, **kw):
    return dict({"id": i, "name": f"Song {i}", "artists": ["A"], "bpm": 120 + i, "key": "8A", "reasons": []}, **kw)


def test_a_new_draft_is_empty_listed_and_read_by_its_id(data_dir):
    d = drafts.create("  Friday   set ")
    assert d["name"] == "Friday set" and d["tracks"] == [] and d["uploaded"] is None
    assert drafts.read(d["id"]) == d and [x["id"] for x in drafts.list_all()] == [d["id"]]
    assert drafts.read("nope") is None and drafts.read("../state") is None
    assert not list((data_dir / "drafts").glob("*.tmp"))


@pytest.mark.parametrize("name, code", [("  ", "name_required"), ("x" * 101, "name_too_long")])
def test_a_draft_needs_a_valid_name(data_dir, name, code):
    with pytest.raises(Beat50Error) as err:
        drafts.create(name)
    assert err.value.code == code and drafts.list_all() == []


def test_adding_keeps_what_the_page_shows_and_never_a_track_twice(data_dir):
    d = drafts.create("Set")
    _, added = drafts.add(d["id"], [_t(1), _t(2), _t(1)])
    assert added == 2
    saved, added = drafts.add(d["id"], [_t(2), _t(3, length_ms=1000)])
    assert added == 1 and [t["id"] for t in saved["tracks"]] == [1, 2, 3]
    assert "reasons" not in saved["tracks"][0] and saved["tracks"][2]["length_ms"] == 1000
    assert saved["tracks"][0]["length_ms"] is None


def test_saving_renames_reorders_and_removes(data_dir):
    d = drafts.create("Set")
    drafts.add(d["id"], [_t(1), _t(2), _t(3)])
    saved = drafts.save(d["id"], "Saturday", [3, 1])
    assert saved["name"] == "Saturday" and [t["id"] for t in saved["tracks"]] == [3, 1]
    assert drafts.read(d["id"])["tracks"] == saved["tracks"]


@pytest.mark.parametrize("ids", [[1, 1], [1, 9]])
def test_saving_only_takes_the_drafts_own_tracks_once_each(data_dir, ids):
    d = drafts.create("Set")
    drafts.add(d["id"], [_t(1), _t(2)])
    with pytest.raises(Beat50Error) as err:
        drafts.save(d["id"], "Set", ids)
    assert err.value.code == "bad_request" and [t["id"] for t in drafts.read(d["id"])["tracks"]] == [1, 2]


def test_an_uploaded_draft_no_longer_changes(data_dir):
    d = drafts.create("Set")
    drafts.add(d["id"], [_t(1)])
    up = drafts.set_uploaded(d["id"], 77, "Set", 1)["uploaded"]
    assert (up["playlist_id"], up["name"], up["tracks"]) == (77, "Set", 1) and up["at"]
    for change in (lambda: drafts.add(d["id"], [_t(2)]), lambda: drafts.save(d["id"], "Other", [1])):
        with pytest.raises(Beat50Error) as err:
            change()
        assert err.value.code == "draft_uploaded" and err.value.params == {"name": "Set"}
    assert json.loads((data_dir / "drafts" / f"{d['id']}.json").read_text())["name"] == "Set"


def test_a_draft_that_does_not_exist_cannot_change(data_dir):
    with pytest.raises(Beat50Error) as err:
        drafts.add("0123456789ab", [_t(1)])
    assert err.value.code == "not_found"
