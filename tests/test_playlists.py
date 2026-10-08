import io
import urllib.error

import pytest

from beat50 import playlists
from beat50.errors import Beat50Error


class FakeClient:
    def __init__(self, public=False, bulk_fails=False, inside=None, create_fails=None, reread_fails=False,
                 create_response="normal"):
        self.public, self.bulk_fails = public, bulk_fails
        self.create_fails, self.reread_fails, self.create_response = create_fails, reread_fails, create_response
        self.inside = inside
        self.calls = []

    def post(self, path, body):
        self.calls.append(("POST", path, body))
        if path == "/my/playlists/":
            if self.create_fails:
                raise self.create_fails
            if self.create_response is None:
                return None
            return {"id": 77, "name": body["name"], "is_public": self.public}
        if self.bulk_fails:
            raise RuntimeError("502 Bad Gateway")
        if self.inside is None:
            self.inside = list(body["track_ids"])
        return {"items": [], "playlist": {}}

    def paged(self, path, **kw):
        self.calls.append(("GET", path, None))
        if self.reread_fails:
            raise TimeoutError("timed out")
        return [{"track": {"id": i}} for i in (self.inside or [])] + [{"track": None}]


def test_creates_it_private_and_adds_in_order():
    c = FakeClient()
    r = playlists.create_playlist(c, "202609 Techno", [3, 1, 2])
    assert c.calls == [("POST", "/my/playlists/", {"name": "202609 Techno"}),
                       ("POST", "/my/playlists/77/tracks/bulk/", {"track_ids": [3, 1, 2]}),
                       ("GET", "/my/playlists/77/tracks/", None)]
    assert r == {"id": 77, "name": "202609 Techno", "track_ids": [3, 1, 2], "requested": 3, "warnings": []}


def test_the_name_is_cleaned_of_extra_spaces():
    c = FakeClient()
    assert playlists.create_playlist(c, "  202609   Techno ", [1])["name"] == "202609 Techno"


def test_valid_name_cleans_and_returns_the_name():
    assert playlists.valid_name("  a   b ") == "a b"
    assert playlists.valid_name("x" * playlists.MAX_NAME) == "x" * playlists.MAX_NAME


def test_if_it_comes_out_public_it_stops_without_adding_tracks():
    c = FakeClient(public=True)
    with pytest.raises(playlists.PlaylistPublic) as err:
        playlists.create_playlist(c, "x", [1, 2])
    assert err.value.code == "created_public"
    assert err.value.params == {"name": "x", "id": 77}
    assert isinstance(err.value, playlists.PlaylistError)
    assert [p for m, p, b in c.calls] == ["/my/playlists/"]


def test_counts_only_the_tracks_that_got_in():
    r = playlists.create_playlist(FakeClient(inside=[3, 2]), "x", [3, 1, 2])
    assert r["track_ids"] == [3, 2] and r["requested"] == 3
    assert r["warnings"] == []


def test_if_adding_fails_it_returns_the_playlist_with_a_warning():
    r = playlists.create_playlist(FakeClient(bulk_fails=True, inside=[]), "x", [1, 2])
    assert r["id"] == 77 and r["track_ids"] == []
    assert [w["code"] for w in r["warnings"]] == ["add_failed"]
    assert "502" in r["warnings"][0]["detail"]


@pytest.mark.parametrize("name, ids, code", [("", [1], "name_required"),
                                             ("   ", [1], "name_required"),
                                             ("x" * 101, [1], "name_too_long"),
                                             ("ok", [], "no_starred")])
def test_invalid_data_does_not_call_beatport(name, ids, code):
    c = FakeClient()
    with pytest.raises(playlists.PlaylistError) as err:
        playlists.create_playlist(c, name, ids)
    assert err.value.code == code
    assert c.calls == []


def test_a_too_long_name_reports_the_maximum():
    with pytest.raises(playlists.PlaylistError) as err:
        playlists.valid_name("x" * (playlists.MAX_NAME + 1))
    assert err.value.params == {"max": playlists.MAX_NAME}


def _http(code):
    return urllib.error.HTTPError("https://api", code, "x", {}, io.BytesIO(b""))


def test_if_the_reread_fails_the_playlist_is_still_returned():
    r = playlists.create_playlist(FakeClient(reread_fails=True), "x", [1, 2])
    assert r["id"] == 77 and r["track_ids"] == []
    assert [w["code"] for w in r["warnings"]] == ["count_unknown"]


@pytest.mark.parametrize("failure", [_http(502), urllib.error.URLError("no network"), TimeoutError("timed out")])
def test_an_ambiguous_failure_while_creating_says_to_check_before_retrying(failure):
    c = FakeClient(create_fails=failure)
    with pytest.raises(playlists.PlaylistError) as err:
        playlists.create_playlist(c, "x", [1])
    assert err.value.code == "create_unsure"
    assert err.value.params["name"] == "x"
    assert "Check beatport.com" in str(err.value)
    assert len(c.calls) == 1


def test_a_4xx_rejection_while_creating_just_says_so():
    with pytest.raises(playlists.PlaylistError) as err:
        playlists.create_playlist(FakeClient(create_fails=_http(400)), "x", [1])
    assert err.value.code == "create_rejected"
    assert err.value.params["name"] == "x"


def test_creating_without_a_response_says_to_check():
    with pytest.raises(playlists.PlaylistError) as err:
        playlists.create_playlist(FakeClient(create_response=None), "x", [1])
    assert err.value.code == "create_unsure"
    assert "Check beatport.com" in str(err.value)


def test_playlist_errors_are_beat50_errors():
    assert issubclass(playlists.PlaylistError, Beat50Error)


def _http(code):
    return urllib.error.HTTPError("https://api", code, "x", {}, io.BytesIO(b""))


def _track(t):
    return {"id": t, "name": f"Song {t}", "mix_name": "Original Mix", "artists": [{"id": 1, "name": "Artist"}]}


class FakePlaylist:
    """A Beatport playlist that can be renamed and edited. Items have their own ids, apart from track ids."""

    def __init__(self, tracks, gone=False, fail=()):
        self.items = [{"id": 500 + t, "position": n, "track": _track(t)} for n, t in enumerate(tracks, 1)]
        self.name = "old"
        self.gone, self.fail = gone, set(fail)
        self.calls = []

    def get(self, path, **kw):
        self.calls.append(("GET", path, None))
        if self.gone:
            raise _http(404)
        return {"id": 7, "name": self.name, "is_public": False}

    def paged(self, path, **kw):
        self.calls.append(("GET", path, None))
        if self.gone:
            raise _http(404)
        if "reread" in self.fail and any(c[0] != "GET" for c in self.calls):
            raise TimeoutError("timed out")
        return sorted(self.items, key=lambda x: x["position"])

    def patch(self, path, body):
        self.calls.append(("PATCH", path, body))
        if "rename" in self.fail:
            raise _http(502)
        self.name = body["name"]
        return {"id": 7, "name": self.name, "is_public": False}

    def delete(self, path, body):
        self.calls.append(("DELETE", path, body))
        if "remove" in self.fail:
            raise _http(502)
        self.items = [x for x in self.items if x["id"] not in body["item_ids"]]

    def post(self, path, body):
        self.calls.append(("POST", path, body))
        if "add" in self.fail:
            raise _http(502)
        last = max((x["position"] for x in self.items), default=0)
        self.items += [{"id": 900 + t, "position": last + n, "track": _track(t)}
                       for n, t in enumerate(body["track_ids"], 1)]


def test_edit_renames_removes_and_adds_in_one_go():
    pl = FakePlaylist([1, 2, 3])
    r = playlists.edit_playlist(pl, 7, name="  New   name ", remove=[2], add=[4, 5])
    assert ("PATCH", "/my/playlists/7/", {"name": "New name"}) in pl.calls
    assert ("DELETE", "/my/playlists/7/tracks/bulk/", {"item_ids": [502]}) in pl.calls  # item ids, not track ids
    assert ("POST", "/my/playlists/7/tracks/bulk/", {"track_ids": [4, 5]}) in pl.calls
    assert r == {"id": 7, "name": "New name", "track_ids": [1, 3, 4, 5], "warnings": []}
    assert pl.name == "New name"


def test_edit_without_a_new_name_does_not_rename():
    pl = FakePlaylist([1, 2])
    r = playlists.edit_playlist(pl, 7, name=None, remove=[1])
    assert not any(c[0] == "PATCH" for c in pl.calls)
    assert r["name"] == "old" and r["track_ids"] == [2]  # the name it has on Beatport


def test_edit_reads_the_real_playlist_first():
    # The track was already removed on beatport.com: nothing to delete. The one to add is already there.
    pl = FakePlaylist([1, 4])
    r = playlists.edit_playlist(pl, 7, remove=[2], add=[4])
    assert [c[0] for c in pl.calls] == ["GET", "GET"]  # nothing to change on Beatport: no writes, no re-read
    assert r["track_ids"] == [1, 4]


def test_edit_of_a_playlist_gone_from_beatport():
    with pytest.raises(Beat50Error) as e:
        playlists.edit_playlist(FakePlaylist([1], gone=True), 7, remove=[1])
    assert e.value.code == "playlist_gone"


def test_edit_checks_the_name_before_touching_beatport():
    pl = FakePlaylist([1])
    with pytest.raises(Beat50Error) as e:
        playlists.edit_playlist(pl, 7, name="   ")
    assert e.value.code == "name_required" and pl.calls == []


@pytest.mark.parametrize("fails, code, kept", [("rename", "rename_failed", [1, 3, 4]),
                                               ("remove", "remove_failed", [1, 2, 3, 4]),
                                               ("add", "add_failed", [1, 3])])
def test_edit_reports_what_failed_and_keeps_the_rest(fails, code, kept):
    pl = FakePlaylist([1, 2, 3], fail=[fails])
    r = playlists.edit_playlist(pl, 7, name="New", remove=[2], add=[4])
    assert [w["code"] for w in r["warnings"]] == [code]
    assert r["track_ids"] == kept
    assert r["name"] == ("old" if fails == "rename" else "New")


def test_edit_that_cannot_reread_says_so():
    pl = FakePlaylist([1, 2], fail=["reread"])
    r = playlists.edit_playlist(pl, 7, remove=[2])
    assert [w["code"] for w in r["warnings"]] == ["count_unknown"]
    assert r["track_ids"] is None


def test_edit_that_cannot_read_the_playlist_says_so_in_the_users_terms():
    class Down(FakePlaylist):
        def paged(self, path, **kw):
            raise _http(502)
    with pytest.raises(Beat50Error) as e:
        playlists.edit_playlist(Down([1]), 7, remove=[1])
    assert e.value.code == "edit_failed"


def test_an_expired_session_while_editing_is_not_hidden_as_a_warning():
    from beat50.client import TokenExpired

    class Expired(FakePlaylist):
        def patch(self, path, body):
            raise TokenExpired("session_expired", "Beatport answered 401: sign in again.")
    with pytest.raises(TokenExpired):
        playlists.edit_playlist(Expired([1, 2]), 7, name="New", remove=[2])


def test_read_playlist_gives_its_name_tracks_and_their_titles():
    pl = FakePlaylist([2, 1])
    pl.name = "Renamed on beatport.com"
    r = playlists.read_playlist(pl, 7)
    assert r["name"] == "Renamed on beatport.com" and r["track_ids"] == [2, 1]
    assert r["tracks"][2] == {"name": "Song 2", "mix_name": "Original Mix", "artists": ["Artist"]}


def test_read_playlist_of_one_deleted_on_beatport():
    with pytest.raises(Beat50Error) as e:
        playlists.read_playlist(FakePlaylist([1], gone=True), 7)
    assert e.value.code == "playlist_gone"


def test_edit_compares_the_name_with_the_one_on_beatport():
    # Renamed on beatport.com to "Peak"; renaming it back to "old" must reach Beatport, "Peak" must not.
    pl = FakePlaylist([1])
    pl.name = "Peak"
    assert playlists.edit_playlist(pl, 7, name="old")["name"] == "old"
    assert ("PATCH", "/my/playlists/7/", {"name": "old"}) in pl.calls
    pl2 = FakePlaylist([1])
    pl2.name = "Peak"
    playlists.edit_playlist(pl2, 7, name="Peak", remove=[1])
    assert not any(c[0] == "PATCH" for c in pl2.calls)
