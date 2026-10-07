import re
from datetime import date

import pytest

from beatcrate.app import views

TRACK = {"id": 1, "name": "Doublespeak ", "mix_name": "Original Mix", "artists": ["Commodore 69"],
         "label": "Urban Kickz Recordings", "genre": "Techno (Raw / Deep / Hypnotic)", "bpm": 140,
         "key": "2A", "publish_date": "2026-09-09",
         "buy_url": "https://www.beatport.com/track/doublespeak/1",
         "sample_url": "https://geo-samples.beatport.com/track/abc.LOFI.mp3",
         "image": "https://geo-media.beatport.com/image_size/120x120/abc.jpg",
         "score": 0.66, "reasons": [{"kind": "label", "value": "Urban Kickz Recordings"}]}


def _crate(track=None, **kw):
    base = {"window": {"from": "2026-08-30", "to": "2026-09-30"}, "candidates_seen": 628,
            "short": False, "tracks": [dict(track or TRACK)]}
    base.update(kw)
    return base


def _page(crate="default", state=None, login_pending=False, selection="2026-09", marks=None, lang="en"):
    crate = _crate() if crate == "default" else crate
    selections = [("2026-09", 1), ("2026-08", 50)] if crate else []
    return views.render_page(selection if crate else None, crate, selections,
                             dict(state or {}, login_pending=login_pending), "TOKEN123", date(2026, 9, 30),
                             marks, lang)


def test_the_row_shows_data_preview_and_purchase():
    html = _page()
    assert ">Doublespeak<" in html and ">Commodore 69<" in html
    assert "Urban Kickz Recordings" in html and "140 BPM" in html and "2A" in html and "9 Sep" in html
    assert "label Urban Kickz Recordings" in html
    assert "Picked for label Urban Kickz Recordings" in html
    assert 'data-src="https://geo-samples.beatport.com/track/abc.LOFI.mp3"' in html
    assert 'src="https://geo-media.beatport.com/image_size/120x120/abc.jpg"' in html
    assert 'content="TOKEN123"' in html
    assert "September 2026" in html and "628 candidates" in html
    assert 'href="/crate/2026-08"' in html
    assert 'class="buy"' not in html and "www.beatport.com/track" not in html  # beatcrate is about playlists


def test_the_row_in_spanish():
    html = _page(lang="es")
    assert "sello Urban Kickz Recordings" in html
    assert "Elegido por sello Urban Kickz Recordings" in html
    assert "9 sep" in html
    assert "Septiembre 2026" in html and "628 candidatos" in html
    assert "Comprar" not in html


def test_the_reasons_come_from_the_kinds_and_are_translated():
    reasons = [{"kind": "artist", "value": "Tale Of Us"}, {"kind": "bpm", "value": 124}]
    assert "artist Tale Of Us · 124 BPM" in _page(_crate(dict(TRACK, reasons=reasons)))
    assert "artista Tale Of Us · 124 BPM" in _page(_crate(dict(TRACK, reasons=reasons)), lang="es")


def test_an_old_crate_with_a_stored_spanish_reason_renders_translated():
    old = {k: v for k, v in TRACK.items() if k != "reasons"}
    old["reason"] = "sello Urban Kickz Recordings · genero Techno"
    assert "label Urban Kickz Recordings · genre Techno" in _page(_crate(old), lang="en")
    assert "sello Urban Kickz Recordings · género Techno" in _page(_crate(old), lang="es")


def test_escapes_beatport_text():
    html = _page(_crate(dict(TRACK, name='</script><b>"x" & y')))
    assert "&lt;/script&gt;&lt;b&gt;&quot;x&quot; &amp; y" in html
    assert "</script><b>" not in html


def test_old_crate_without_preview_or_cover():
    old = {k: v for k, v in TRACK.items() if k not in ("sample_url", "image")}
    html = _page(_crate(old))
    assert '<div class="a">Commodore 69</div>' in html and '<span class="name">Doublespeak</span>' in html
    assert "data-src" not in html
    assert "<img src=" not in html  # the player's <img> has no src until something plays
    assert 'class="no-cover"' in html
    assert '<span class="cover"><span class="no-cover"></span></span>' in html


def test_non_https_urls_are_dropped():
    html = _page(_crate(dict(TRACK, sample_url="javascript:alert(1)", image="http://x/y.jpg")))
    assert "javascript:" not in html
    assert "http://x/y.jpg" not in html


def test_without_crates_it_invites_to_generate():
    html = _page(crate=None)
    assert "No selections yet" in html
    assert "Beatport new releases picked for your taste" in html and "Allow reading your session" in html
    assert 'data-action="generate"' in html


def test_without_crates_in_spanish():
    html = _page(crate=None, lang="es")
    assert "Aún no hay ninguna selección" in html
    assert 'data-action="generate"' in html


def test_a_short_crate_says_so():
    assert "Only 1 new releases match your profile" in _page(_crate(short=True))
    assert "solo hay 1 novedades" in _page(_crate(short=True), lang="es")


def test_generating_shows_the_step_and_disables_buttons():
    html = _page(state={"running": {"step": 2, "of": 3, "phase": "discover", "since": "x"}})
    assert 'id="progress"' in html
    assert '<p class="working step">' in html
    assert "2/3" in html and "looking for new releases" in html
    assert '<ol class="phases"><li class="done">reading your library</li><li class="now">looking for new releases</li>' \
           '<li class="next">picking the 50</li></ol>' in html
    assert 'data-action="generate" disabled' in html
    assert 'data-running="1"' in html


def test_generating_in_spanish():
    html = _page(state={"running": {"step": 1, "of": 3, "phase": "library", "since": "x"}}, lang="es")
    assert "Haciendo la selección… 1/3 · leyendo tu librería" in html


def test_not_generating_leaves_the_buttons_enabled():
    html = _page()
    assert 'data-action="generate" disabled' not in html
    assert 'data-running="0"' in html
    assert 'id="progress"' not in html


def test_an_expired_session_offers_login():
    html = _page(state={"session": {"status": "expired"}})
    assert "Beatport session expired" in html
    assert 'class="session bad"' in html
    assert 'data-action="login-start"' in html
    assert "Sesión de Beatport caducada" in _page(state={"session": {"status": "expired"}}, lang="es")


def test_an_active_session_is_marked_ok_and_offers_no_login():
    html = _page(state={"session": {"status": "active"}})
    assert 'class="session ok"' in html and "Beatport session active" in html
    assert 'data-action="login-start"' not in html
    assert "Sesión de Beatport activa" in _page(state={"session": {"status": "active"}}, lang="es")


def test_an_unchecked_session_is_muted():
    html = _page()
    assert 'class="session muted"' in html and "Session not checked" in html
    assert "Sesión sin comprobar" in _page(lang="es")


def test_a_pending_login_says_where_to_sign_in():
    html = _page(state={"session": {"status": "expired"}}, login_pending=True)
    assert "Sign in to Beatport in the window that opened" in html
    assert 'data-login="1"' in html  # the page reloads once the window closes
    assert 'data-action="login-start"' not in html and 'data-action="login-finish"' not in html
    assert "Inicia sesión en Beatport en la ventana" in _page(login_pending=True, lang="es")


def test_last_run_succeeded_shows_the_last_selection():
    state = {"last_run": {"finished_at": "2026-09-30T07:00:00+00:00", "ok": True}}
    assert "Last selection:" in _page(state=state) and "✓" in _page(state=state)
    assert "Última selección:" in _page(state=state, lang="es")


def test_last_run_failed_shows_the_error():
    html = _page(state={"last_run": {"finished_at": "2026-09-30T07:00:00+00:00", "ok": False,
                                     "error": "No user <session>"}})
    assert "No user &lt;session&gt;" in html
    assert 'class="error"' in html
    assert '<p class="last bad">' in html


def test_last_run_failed_with_a_code_is_translated():
    last = {"finished_at": "2026-09-30T07:00:00+00:00", "ok": False, "error": "English fallback",
            "error_code": "session_expired", "error_params": {}}
    assert "Your Beatport session has expired" in _page(state={"last_run": last})
    assert "Tu sesión de Beatport ha caducado" in _page(state={"last_run": last}, lang="es")
    assert "English fallback" not in _page(state={"last_run": last})


def test_last_run_failed_with_an_unknown_code_keeps_its_text():
    last = {"finished_at": "2026-09-30T07:00:00+00:00", "ok": False, "error": "Something <odd>",
            "error_code": "no_such_code", "error_params": {}}
    assert "Something &lt;odd&gt;" in _page(state={"last_run": last})


def test_there_is_an_inline_player_hidden_until_something_plays():
    html = _page()
    assert '<div id="player-bar" hidden>' in html
    assert 'id="player-seek"' in html and 'id="player-time"' in html
    # The inline player carries no title or cover: the row above it already shows them.
    assert 'id="player-img"' not in html and 'id="player-title"' not in html and 'id="player-play"' not in html


def test_without_a_crate_there_is_no_player():
    assert 'id="player-bar"' not in _page(crate=None)


def test_star_marked_and_unmarked():
    assert 'class="star on" data-star="1" aria-pressed="true"' in _page(marks={"starred": [1], "playlists": []})
    assert 'class="star" data-star="1" aria-pressed="false"' in _page()


def test_create_button_disabled_without_stars_and_with_a_counter():
    html = _page()
    assert f'<span class="count"><span id="n-star">0</span>{ICON.format("star")}</span>' in html
    assert 'data-suggested="202609 " disabled>' in html
    assert 'class="create"' in html
    html = _page(marks={"starred": [1], "playlists": []})
    assert f'<span class="count"><span id="n-star">1</span>{ICON.format("star")}</span>' in html
    assert 'data-suggested="202609 ">' in html


def test_the_create_button_in_spanish():
    assert "Crear playlist en Beatport" in _page(lang="es")


def test_stars_of_tracks_no_longer_there_are_ignored():
    assert f'<span class="count"><span id="n-star">0</span>{ICON.format("star")}</span>' in _page(marks={"starred": [99], "playlists": []})


def test_playlist_tags_and_list_are_escaped():
    html = _page(marks={"starred": [], "playlists": [{"id": 9, "name": '<b>"Techno"</b>', "track_ids": [1]}]})
    assert '<span class="in">in &lt;b&gt;&quot;Techno&quot;&lt;/b&gt;</span>' in html
    assert "Playlists from this selection" in html
    assert '<b>"Techno"</b>' not in html
    assert "Playlists de esta selección" in _page(
        marks={"starred": [], "playlists": [{"id": 9, "name": "x", "track_ids": [1]}]}, lang="es")


def test_body_carries_the_selection():
    assert 'data-selection="2026-09"' in _page()


def test_the_selection_links_are_marked():
    html = _page()
    assert '<div class="sel-row"><a class="sel on" href="/crate/2026-09">Sep 2026 <small>1</small></a>' in html
    assert '<div class="sel-row"><a class="sel" href="/crate/2026-08">Aug 2026 <small>50</small></a>' in html


def test_genre_filter_with_counts_and_genre_on_each_row():
    other = dict(TRACK, id=2, genre="House & <Garage>")
    html = _page(_crate(tracks=[TRACK, other, dict(TRACK, id=3)]))
    assert '<button class="genre on" data-all>All <small>3</small></button>' in html
    techno = ('<button class="genre" data-genre="Techno (Raw / Deep / Hypnotic)">'
              'Techno (Raw / Deep / Hypnotic) <small>2</small></button>')
    house = ('<button class="genre" data-genre="House &amp; &lt;Garage&gt;">'
             'House &amp; &lt;Garage&gt; <small>1</small></button>')
    assert techno in html and house in html
    assert html.index(techno) < html.index(house)
    assert '<li class="track" data-genre="House &amp; &lt;Garage&gt;">' in html
    assert '<nav class="genres">' in html
    assert "Todos <small>3</small>" in _page(_crate(tracks=[TRACK, other, dict(TRACK, id=3)]), lang="es")


def test_chrome_is_not_needed():
    html = _page(state={"session": {"status": "expired"}})
    assert "Chrome" not in html
    assert 'data-action="generate"' in html and 'data-action="login-start"' in html


def test_selection_with_a_code():
    html = views.render_page("20261001_074512", _crate(), [("20261001_074512", 1), ("2026-09", 50)],
                             {"login_pending": False}, "T", date(2026, 10, 1))
    assert "<h1>1 October 2026, 07:45</h1>" in html
    assert '<span class="detail">20261001_074512 · 1 tracks' in html
    assert 'href="/crate/20261001_074512">1 Oct · 07:45' in html
    assert 'data-suggested="20261001_074512 "' in html
    assert ">New selection</button>" in html


def test_selection_with_a_code_in_spanish():
    html = views.render_page("20261001_074512", _crate(), [("20261001_074512", 1), ("2026-09", 50)],
                             {"login_pending": False}, "T", date(2026, 10, 1), lang="es")
    assert "<h1>1 de octubre de 2026, 07:45</h1>" in html
    assert 'href="/crate/20261001_074512">1 oct · 07:45' in html
    assert ">Nueva selección</button>" in html


def test_period_fields_with_the_last_31_days():
    html = _page()
    assert 'id="since" value="2026-08-30" max="2026-09-30"' in html
    assert 'id="until" value="2026-09-30" max="2026-09-30"' in html


def test_the_crate_period_is_shown():
    assert "releases from 30 Aug to 30 Sep" in _page()
    assert "novedades del 30 ago al 30 sep" in _page(lang="es")


def test_the_page_language_and_switch():
    html = _page()
    assert '<html lang="en">' in html
    assert 'data-lang="es"' in html and 'data-lang="en"' in html
    assert '<a href="#" data-lang="en" class="on">EN</a>' in html
    assert '<html lang="es">' in _page(lang="es")


def test_the_page_embeds_the_texts_for_the_script_in_its_language():
    assert '<script id="texts" type="application/json">' in _page()
    assert "beatcrate has closed" in _page()
    assert "beatcrate se ha cerrado" in _page(lang="es")


def test_without_consent_the_page_carries_the_session_notice():
    html = _page(state={"consent": False})
    assert 'data-consent="0"' in html
    assert '<dialog id="consent"' in html
    assert "Before reading your Beatport session" in html
    assert "in a window of its own" in html
    assert "only reads your Beatport session" in html
    assert "never buys" in html
    assert "not shared with Safari" in html
    assert 'data-consent-ok' in html and 'data-consent-cancel' in html
    assert 'data-action="revoke"' not in html


def test_the_session_notice_in_spanish():
    html = _page(state={"consent": False}, lang="es")
    assert "Antes de leer tu sesión de Beatport" in html and "Aceptar y continuar" in html and "Cancelar" in html


def test_with_consent_it_can_be_withdrawn():
    html = _page(state={"consent": True})
    assert 'data-consent="1"' in html
    assert 'data-action="revoke"' in html and "Withdraw permission" in html
    assert "Retirar permiso" in _page(state={"consent": True}, lang="es")


def test_while_signing_in_the_other_session_actions_wait():
    html = _page(state={"session": {"status": "expired"}}, login_pending=True)
    assert 'data-action="generate" disabled' in html
    assert 'data-action="check" disabled' in html


ICON = '<svg class="icon" aria-hidden="true"><use href="#i-{}"></use></svg>'


def _icons(html):
    return re.findall(r'<svg class="icon" aria-hidden="true"><use href="#i-(\w+)"></use></svg>', html)


def test_each_action_has_its_icon():
    html = _page(state={"session": {"status": "expired"}, "consent": True})
    for action, icon in (("generate", "auto_awesome"), ("check", "verified_user"), ("login-start", "login"),
                         ("revoke", "remove_moderator"), ("playlist", "playlist_add")):
        assert re.search(rf'data-action="{action}"[^>]*>{re.escape(ICON.format(icon))}', html), action
    assert re.search(rf'class="star" data-star="1"[^>]*>{re.escape(ICON.format("star"))}', html)
    assert re.search(rf'class="play" data-src="[^"]+"[^>]*>{re.escape(ICON.format("play_arrow"))}', html)
    assert f'data-consent-cancel>{ICON.format("close")}' in html
    assert f'data-consent-ok>{ICON.format("check")}' in html


@pytest.mark.parametrize("status, icon", [("active", "check_circle"), ("expired", "error"), (None, "help")])
def test_the_session_status_has_an_icon(status, icon):
    html = _page(state={"session": {"status": status}} if status else {})
    assert re.search(rf'<p class="session \w+">{re.escape(ICON.format(icon))}', html)
    assert "●" not in html


def test_every_icon_used_is_in_the_sprite():
    pages = [_page(state={"session": {"status": s}, "consent": c}, login_pending=p, lang=lang)
             for s in ("active", "expired", None) for c in (True, False) for p in (True, False) for lang in ("en", "es")]
    pages += [_edit_page(lang=lang) for lang in ("en", "es")]
    used = {name for html in pages for name in _icons(html)} | {"play_arrow", "pause"}  # app.js swaps these two
    assert used <= set(views.ICONS)
    for html in pages:
        assert html.index('<svg class="sprite" aria-hidden="true">') < html.index('<div class="app">')
        for name in used:
            assert f'<symbol id="i-{name}" viewBox="0 0 24 24">' in html


def _three():
    return _crate(tracks=[dict(TRACK, id=1, name="One"), dict(TRACK, id=2, name="Two"), dict(TRACK, id=3, name="Three")])


PL = {"id": 9, "name": 'Peak <"time">', "track_ids": [2, 1], "created_at": "t"}


def _edit_page(lang="en", starred=()):
    return views.render_page("2026-09", _three(), [("2026-09", 3)], {"login_pending": False, "consent": True},
                             "T", date(2026, 9, 30), {"starred": list(starred), "playlists": [PL]}, lang, PL)


def test_created_playlists_link_to_their_edit_page():
    html = _page(marks={"starred": [], "playlists": [PL]})
    assert 'href="/crate/2026-09/playlist/9"' in html


def test_the_edit_page_shows_the_name_to_change_and_a_save_button():
    html = _edit_page()
    assert '<input id="pl-name" value="Peak &lt;&quot;time&quot;&gt;"' in html
    assert f'data-action="save-playlist" data-playlist="9" disabled>{ICON.format("save")}Save changes' in html
    assert f'<a class="back" href="/crate/2026-09" aria-label="Back to the selection">{ICON.format("arrow_back")}</a>' in html
    assert "Private on Beatport" in html
    assert "Nothing changes on Beatport until you save." in html
    assert 'class="pl on" href="/crate/2026-09/playlist/9"' in html


def test_the_edit_page_lists_the_playlist_in_its_order_then_what_can_be_added():
    html = _edit_page(starred=[3])
    assert "In the playlist (2)" in html and "Add from the selection" in html
    assert html.index('data-remove="2"') < html.index('data-remove="1"') < html.index('data-add="3"')
    assert 'data-add="1"' not in html and 'data-remove="3"' not in html
    assert f'data-remove="2" aria-pressed="false" aria-label="Remove from the playlist">{ICON.format("remove")}' in html
    assert f'data-add="3" aria-pressed="false" aria-label="Add to the playlist">{ICON.format("add")}' in html


def test_starred_tracks_come_first_among_those_to_add():
    page = views.render_page("2026-09", _crate(tracks=[dict(TRACK, id=i) for i in (1, 2, 3, 4)]), [("2026-09", 4)],
                             {"consent": True}, "T", date(2026, 9, 30),
                             {"starred": [4], "playlists": [dict(PL, track_ids=[1])]}, "en", dict(PL, track_ids=[1]))
    assert page.index('data-add="4"') < page.index('data-add="2"') < page.index('data-add="3"')


def test_the_edit_page_has_no_stars_and_no_create_button():
    html = _edit_page()
    assert 'class="star' not in html and 'data-action="playlist"' not in html


def test_the_edit_page_in_spanish():
    html = _edit_page(lang="es")
    assert "Guardar cambios" in html and "Volver a la selección" in html and "En la playlist (2)" in html
    assert "Añadir de la selección" in html and 'aria-label="Quitar de la playlist"' in html


def test_the_notice_says_beatcrate_edits_only_its_own_playlists():
    html = _page(state={"consent": False})
    assert "edit the ones it created" in html
    assert "never deletes a playlist, never touches the ones it did not create" in html
    assert "changes your playlists" not in html
    es = _page(state={"consent": False}, lang="es")
    assert "editar las que creó" in es and "no modifica tus playlists" not in es


def test_a_playlist_deleted_on_beatport_is_shown_as_such():
    gone = dict(PL, gone=True)
    html = views.render_page("2026-09", _three(), [("2026-09", 3)], {"consent": True}, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [gone]}, "en", gone)
    assert 'class="pl on gone"' in html and "deleted on Beatport" in html
    assert "That playlist no longer exists on Beatport." in html
    assert f'data-action="forget-playlist" data-playlist="9">{ICON.format("playlist_remove")}Remove from this list' in html
    assert 'data-action="save-playlist"' not in html and "data-remove=" not in html
    assert "data-refresh" not in html


def test_tracks_added_outside_the_selection_can_be_removed():
    pl = dict(PL, track_ids=[2, 77], outside={"77": {"name": "Elsewhere", "mix_name": "Dub", "artists": ["X & Y"]}})
    html = views.render_page("2026-09", _three(), [("2026-09", 3)], {"consent": True}, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [pl]}, "en", pl)
    assert "In the playlist (2)" in html
    assert "X &amp; Y — Elsewhere" in html and "Added on beatport.com; not in this selection" in html
    assert 'data-remove="77"' in html
    assert 'data-add="1"' in html and 'data-add="77"' not in html


def test_an_outside_track_without_its_title_still_shows():
    pl = dict(PL, track_ids=[88])
    html = views.render_page("2026-09", _three(), [("2026-09", 3)], {"consent": True}, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [pl]}, "en", pl)
    assert 'data-remove="88"' in html and "Track 88" in html


def test_the_editor_checks_beatport_when_it_opens_if_allowed():
    assert 'data-refresh="1"' in _edit_page()
    assert "Reading playlist from Beatport…" in _edit_page()
    page = views.render_page("2026-09", _three(), [("2026-09", 3)], {"consent": False}, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [PL]}, "en", PL)
    assert "data-refresh" not in page


def test_every_page_has_the_action_loading_overlay():
    # One overlay per page (the JS fills its message), so it is there wherever a Beatport action is.
    for html in (_page(), _edit_page(), _page(crate=None)):
        assert html.count('<div class="loading" id="action-loading" hidden') == 1
        assert '<span class="msg"></span>' in html


def test_the_help_slides_are_on_the_page_and_show_on_first_launch():
    first = _page(state={})  # no help_seen yet
    assert 'data-help="1"' in first and 'id="help"' in first and "data-help-open" in first
    assert first.count('class="help-slide"') == 7
    assert 'aria-label="How beatcrate works"' in first
    assert "50 new releases, for your taste" in first and "Create a private playlist" in first
    assert 'data-help="0"' in _page(state={"help_seen": True})


def test_the_help_explains_how_it_picks_with_the_real_settings():
    html = _page(state={})
    assert "How it picks" in html and "half every 18 months" in html and "the last 31 days by default" in html
    es = _page(state={}, lang="es")
    assert "Cómo elige" in es and "la mitad cada 18 meses" in es and "los últimos 31 días" in es


def test_the_action_messages_reach_the_js():
    from beatcrate.app import i18n
    for lang, creating, checking in (("en", "Creating the playlist on Beatport…", "Checking the Beatport session…"),
                                     ("es", "Creando la playlist en Beatport…", "Comprobando la sesión de Beatport…")):
        texts = i18n.js_texts(lang)
        assert texts["creating"] == creating and texts["checking"] == checking and "saving" in texts


def test_the_editor_also_shows_the_progress_while_a_selection_runs():
    running = {"login_pending": False, "consent": True, "running": {"step": 1, "of": 3, "phase": "library", "since": "x"}}
    html = views.render_page("2026-09", _three(), [("2026-09", 3)], running, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [PL]}, "en", PL)
    assert 'id="progress"' in html and 'data-action="save-playlist"' in html
    assert '<div class="app" inert>' in html and "sel running" not in html


def test_the_sidebar_has_its_sections_and_the_toolbar_the_period():
    html = _page()
    assert '<h2 class="side-h">Selections</h2><nav class="sels">' in html
    assert html.index('<nav class="sels">') < html.index('<section class="status">')
    assert '<header class="head"><div class="title"><h1>September 2026</h1><span class="detail">' in html
    assert html.index('<div class="period">') < html.index('data-action="generate"') < html.index('<div class="filters">')
    assert '<div class="side-foot"><div class="langs">' in html


def test_the_row_has_cover_play_text_and_meta_in_order():
    html = _page(marks={"starred": [1], "playlists": []})
    start = html.index('<li class="track"')
    row = html[start:html.index("</li>", start)]
    assert row.index('<span class="num">1</span>') < row.index('<span class="cover">') < row.index('<button class="play"')
    assert row.index('<div class="t"><div class="n"><span class="name">Doublespeak</span><span class="mix">Original Mix</span></div>') \
        < row.index('<div class="a">Commodore 69</div>') < row.index('<div class="r">')
    assert '<div class="m"><span class="genre-name">Techno (Raw / Deep / Hypnotic)</span><span class="label">Urban Kickz Recordings</span>' \
           '<span class="chip">140 BPM</span><span class="chip">2A</span><span class="date">9 Sep</span></div>' in row
    assert row.endswith('aria-label="Star"><svg class="icon" aria-hidden="true"><use href="#i-star"></use></svg></button>')


def test_the_editor_rows_put_the_toggle_first_and_have_no_star():
    html = _edit_page()
    start = html.index('<li class="track"')  # the sidebar's playlist list has an earlier </li>
    row = html[start:html.index("</li>", start)]
    assert row.index('<span class="num">1</span>') < row.index('<button class="toggle remove"') < row.index('<span class="cover">')
    assert 'class="star' not in row


def test_a_track_without_reasons_still_shows_its_playlist_tag():
    html = _page(_crate(dict(TRACK, reasons=[])), marks={"starred": [], "playlists": [{"id": 9, "name": "Peak", "track_ids": [1]}]})
    assert '<div class="r"><span class="in">in Peak</span></div>' in html
    assert "Picked for" not in html


def test_the_progress_is_on_every_page_while_a_selection_runs():
    running = {"login_pending": False, "consent": True, "running": {"step": 1, "of": 3, "phase": "library", "since": "x"}}
    assert 'id="progress"' in views.render_page(None, None, [], running, "T", date(2026, 9, 30))
    gone = dict(PL, gone=True)
    html = views.render_page("2026-09", _three(), [("2026-09", 3)], running, "T", date(2026, 9, 30),
                             {"starred": [], "playlists": [gone]}, "en", gone)
    assert 'id="progress"' in html and 'data-action="forget-playlist"' in html


def test_a_selection_can_be_deleted_from_its_toolbar():
    html = _page(selection="20261001_120000")
    assert ('<button class="delete" data-action="delete-selection" data-selection="20261001_120000" '
            'data-name="1 October 2026, 12:00" aria-label="Delete selection" title="Delete selection">') in html
    assert '<use href="#i-trash">' in html and '<symbol id="i-trash"' in html
    assert 'aria-label="Eliminar selección"' in _page(selection="20261001_120000", lang="es")


def test_every_selection_in_the_sidebar_has_its_bin():
    html = _page()
    assert ('<small>50</small></a><button class="sel-del" data-action="delete-selection" data-selection="2026-08" '
            'data-name="August 2026" aria-label="Delete the selection of August 2026" title="Delete selection">'
            ) in html
    assert html.count('class="sel-del"') == 2
    assert 'aria-label="Eliminar la selección del Agosto 2026"' in _page(lang="es")


def test_the_empty_page_and_the_editor_have_no_toolbar_bin():
    assert 'data-action="delete-selection"' not in _page(crate=None)
    assert 'class="delete"' not in _edit_page()


def test_while_a_selection_runs_the_whole_app_waits():
    html = _page(state={"running": {"step": 1, "of": 3, "phase": "library", "since": "x"}})
    assert '<div class="app" inert>' in html
    assert html.index('<div class="app" inert>') < html.index('</main>') < html.index('<div id="picking"')
    assert 'title="Delete selection" disabled>' in html and "sel running" not in html
    assert '<div class="app">' in _page()


def test_the_page_has_the_created_message_ready():
    html = _page()
    assert '<div class="toast" id="toast" role="status" aria-live="polite" hidden>' in html
    assert '"created": "Selection created successfully · {n} tracks"' in html
    assert "Selección creada con éxito · {n} temas" in _page(lang="es")


def test_the_picking_card_starts_the_bar_at_its_phase():
    html = _page(state={"running": {"step": 3, "of": 3, "phase": "rank", "since": "2026-10-07T10:00:00+00:00"}})
    assert '<section id="progress" data-step="3" data-since="2026-10-07T10:00:00+00:00">' in html
    assert '<i style="width:85%"></i></div><span class="pct">85%</span>' in html


def test_help_opens_from_a_button_beside_the_app_name():
    html = _page()
    assert ('<div class="brand">' in html and '<span>beatcrate</span><button class="brand-help" data-help-open '
            'aria-label="Help" title="Help"><svg class="icon" aria-hidden="true"><use href="#i-help"></use></svg>'
            '</button></div>') in html
    assert html.count("data-help-open") == 1  # no longer in the sidebar's foot
    assert 'aria-label="Ayuda"' in _page(lang="es")


def test_the_help_slides_use_material_icons():
    html = _page(state={})
    assert html.count('<svg class="mi mi-main" viewBox="0 -960 960 960"') == 7
    assert html.count('<svg class="mi mi-arrow"') == 3 and html.count('<svg class="mi mi-amber"') == 7
    assert '<path d="' + views.MATERIAL["delete"] + '"/>' in html


PROFILE = {"genres": [{"id": 5, "name": "Techno <Raw>", "weight": 1.0, "n": 9},
                      {"id": 6, "name": "House", "weight": 0.5, "n": 4}] +
                     [{"id": i, "name": f"G{i}", "weight": 0.1, "n": 1} for i in range(10, 22)]}


def _genres(state=None, lang="en", profile=PROFILE):
    return views.render_page("2026-09", _crate(), [("2026-09", 1)], dict(state or {}, login_pending=False),
                             "T", date(2026, 9, 30), None, lang, None, profile)


def test_the_toolbar_has_a_genres_button_with_how_many_are_adjusted():
    assert ('<button class="create" data-genres-open aria-haspopup="dialog">'
            '<svg class="icon" aria-hidden="true"><use href="#i-tune"></use></svg>Genres<span class="n" hidden>0</span>'
            '</button>') in _genres()
    assert 'Genres<span class="n">2</span>' in _genres(state={"genre_prefs": {"levels": {"5": 2, "6": 0}, "only": None}})
    assert 'Genres<span class="n">1</span>' in _genres(state={"genre_prefs": {"levels": {"5": 2, "6": 0}, "only": 6}})
    assert 'Géneros<span class="n" hidden>0</span>' in _genres(lang="es")
    assert 'data-genres-open aria-haspopup="dialog" disabled' in _genres(state={"running": {"step": 1, "of": 3}})


def test_the_genres_dialog_lists_the_top_ten_with_their_share_levels_and_only():
    html = _genres(state={"genre_prefs": {"levels": {"6": 4}, "only": 5}})
    assert '<dialog id="genres" aria-labelledby="genres-title" data-top="5">' in html
    assert html.count('<li class="gp"') == 10
    assert "G21" not in html
    row = html[html.index('<li class="gp" data-genre="5"'):html.index('<li class="gp" data-genre="6"')]
    assert 'data-weight="1.0"' in row and '<span class="gp-name">Techno &lt;Raw&gt;</span>' in row
    assert '<span class="now">56 %</span> → <span class="then"></span>' in row
    assert '<button data-level="0" aria-pressed="false">Off</button>' in row
    assert '<button data-level="0.5" aria-pressed="false">−</button>' in row
    assert '<button data-level="1" aria-pressed="true">=</button>' in row
    assert '<button data-level="4" aria-pressed="false">++</button>' in row
    assert '<button class="only" data-only aria-pressed="true">Only</button>' in row
    house = html[html.index('<li class="gp" data-genre="6"'):html.index('<li class="gp" data-genre="10"')]
    assert '<button data-level="4" aria-pressed="true">++</button>' in house
    assert '<button class="only" data-only aria-pressed="false">Only</button>' in house
    assert "<small>28 %</small>" not in html and '<span class="now">28 %</span>' in house
    assert 'data-genres-reset>Reset</button>' in html and 'data-genres-done>Done</button>' in html


def test_the_genres_dialog_in_spanish():
    html = _genres(lang="es")
    assert "Géneros de la próxima selección" in html and ">Apagado</button>" in html and ">Solo</button>" in html
    assert "Restablecer" in html and ">Listo</button>" in html


def test_without_a_profile_the_dialog_says_so():
    html = _genres(profile={})
    assert "Your genres appear here after your first selection." in html and '<li class="gp"' not in html
    assert 'data-genres-reset hidden>' in html
    assert "Tus géneros aparecerán aquí tras tu primera selección." in _genres(profile=None, lang="es")


def test_the_selection_heading_says_which_genre_choices_it_was_made_with():
    prefs = [{"id": 5, "name": "Techno <Raw>", "level": 4}, {"id": 6, "name": "House", "level": 0.5},
             {"id": 7, "name": "Trance", "level": 0}]
    html = _page(_crate(genre_prefs=prefs))
    assert "628 candidates · Techno &lt;Raw&gt; ++ · House − · Trance off" in html
    assert "628 candidatos · Techno &lt;Raw&gt; ++ · House − · Trance apagado" in _page(_crate(genre_prefs=prefs), lang="es")
    only = [{"id": 5, "name": "Techno", "level": "only"}]
    assert "628 candidates · only Techno" in _page(_crate(genre_prefs=only))
    assert "628 candidatos · solo Techno" in _page(_crate(genre_prefs=only), lang="es")
    assert "628 candidates<" in _page(_crate(genre_prefs=[])) and "628 candidates<" in _page()
