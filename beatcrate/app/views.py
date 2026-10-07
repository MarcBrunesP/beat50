"""HTML for the app's page. Everything that comes from Beatport is escaped."""
import json
from datetime import timedelta
from html import escape

from .. import config
from . import i18n

# Inline SVG icons on a 24 px grid, drawn with a 2 px stroke; play, pause and the playlist glyph fill their own
# shapes. The page embeds them once as <symbol>s and every icon is a <use> of one, so the app never loads a font.
# A name missing here renders nothing: add the drawing and its use together.
ICONS = {
    "add": '<path d="M12 6v12M6 12h12"/>',
    "arrow_back": '<path d="M15 5l-7 7 7 7"/>',
    "auto_awesome": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>'
                    '<path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
    "block": '<circle cx="12" cy="12" r="9"/><path d="M5.5 5.5l13 13"/>',
    "check": '<path d="M5 12l5 5L20 7"/>',
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "edit": '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M13.5 6.5l3 3"/>',
    "error": '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16v.5"/>',
    "eye": '<circle cx="12" cy="12" r="3"/><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.5M12 17v.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "login": '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5"/>',
    "mac": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 21v-4h6v4"/>',
    "pause": '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>'
             '<rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>',
    "play_arrow": '<path d="M8 5.5v13l10-6.5z" fill="currentColor" stroke="none"/>',
    "playlist_add": '<path d="M4 6h12M4 12h12M4 18h7"/><path d="M18 14v6M15 17h6"/>',
    "playlist_remove": '<path d="M4 6h12M4 12h12M4 18h7"/><path d="M15 17h6"/>',
    "remove": '<path d="M6 12h12"/>',
    "remove_moderator": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M5 5l14 14"/>',
    "save": '<path d="M5 12l5 5L20 7"/>',
    "star": '<path d="M12 2.5l2.9 6.1 6.7.8-4.9 4.6 1.3 6.6L12 17.4l-6 3.2 1.3-6.6L2.4 9.4l6.7-.8z"/>',
    "sync": '<path d="M20 12a8 8 0 0 1-14 5.3M4 12a8 8 0 0 1 14-5.3"/><path d="M18 3v4h-4M6 21v-4h4"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 12.2a2 2 0 0 0 2 1.8h6a2 2 0 0 0 2-1.8L18 7"/>'
             '<path d="M9 7V4.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 .5.5V7"/>',
    "tune": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "verified_user": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "window": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18"/>',
}


def _icon(name):
    """An icon never carries meaning on its own: it sits next to a label or inside a button with aria-label."""
    return f'<svg class="icon" aria-hidden="true"><use href="#i-{name}"></use></svg>'


def _sprite():
    """Every icon once, as a hidden <symbol>; the icons on the page are <use>s of these."""
    symbols = "".join(f'<symbol id="i-{name}" viewBox="0 0 24 24">{paths}</symbol>' for name, paths in ICONS.items())
    return f'<svg class="sprite" aria-hidden="true">{symbols}</svg>'


# The app icon (scripts/make_icon.py) drawn small for the sidebar: its own colours in both schemes.
BRAND_MARK = ('<svg class="mark" viewBox="0 0 824 824" aria-hidden="true"><clipPath id="brand-clip">'
              '<rect width="824" height="824" rx="184"/></clipPath><g clip-path="url(#brand-clip)">'
              '<rect width="824" height="824" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="620" fill="#0B5FB8"/><circle cx="600" cy="600" r="576" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="532" fill="#0B5FB8"/><circle cx="600" cy="600" r="488" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="444" fill="#0B5FB8"/><circle cx="600" cy="600" r="400" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="356" fill="#0B5FB8"/><circle cx="600" cy="600" r="312" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="268" fill="#0B5FB8"/><circle cx="600" cy="600" r="224" fill="#0A1F44"/>'
              '<circle cx="600" cy="600" r="150" fill="#F0B12E"/><circle cx="600" cy="600" r="16" fill="#0A1F44"/>'
              '</g></svg>')


def _url(u):
    """Only https URLs in src and href: no javascript: or odd schemes."""
    return u if isinstance(u, str) and u.startswith("https://") else None


def _consent(lang):
    """The notice shown before the first action that reads the session; the JS opens it and posts the answer."""
    points = "".join(f'<li>{_icon(icon)}<span>{i18n.t(lang, key)}</span></li>' for key, icon in
                     (("consent_window", "window"), ("consent_reads", "eye"), ("consent_never", "block"),
                      ("consent_where", "mac")))
    return (f'<dialog id="consent" aria-labelledby="consent-title"><h2 id="consent-title">{_icon("verified_user")}'
            f'{i18n.t(lang, "consent_title")}</h2><ul>{points}</ul><div class="buttons">'
            f'<button data-consent-cancel>{_icon("close")}{i18n.t(lang, "consent_cancel")}</button>'
            f'<button class="main" data-consent-ok>{_icon("check")}{i18n.t(lang, "consent_ok")}</button></div></dialog>')


def _player():
    # A thin player the page moves under the row being played: the seek bar and the time, nothing else.
    return ('<div id="player-bar" hidden><div class="player-progress"><div class="bar" id="player-seek"><i></i></div>'
            '<span id="player-time">0:00 / 0:00</span></div></div>')


def _toast():
    # A message the JS shows for a few seconds at the bottom of the content column: "Selection created".
    return ('<div class="toast" id="toast" role="status" aria-live="polite" hidden>'
            f'<span class="box">{_icon("check_circle")}<span class="msg"></span></span></div>')


def _delete_button(selection, lang, off, cls, label_key):
    """The bin that deletes a selection, in its toolbar (`delete`) and on its sidebar row (`sel-del`)."""
    name = i18n.title(selection, lang)
    return (f'<button class="{cls}" data-action="delete-selection" data-selection="{escape(selection)}" '
            f'data-name="{escape(name)}" aria-label="{escape(i18n.t(lang, label_key, name=name))}" '
            f'title="{i18n.t(lang, "delete_selection")}"{off}>{_icon("trash")}</button>')


def _action_loading():
    # A centred overlay the JS shows while an action talks to Beatport; the JS sets its message (creating,
    # saving, checking the session). Rendered once per page, so it is there wherever those actions are.
    return ('<div class="loading" id="action-loading" hidden role="status" aria-live="polite">'
            f'<span class="box">{_icon("sync")}<span class="msg"></span></span></div>')


# Material Symbols (Outlined, 24 px, © Google, Apache License 2.0) for the help slides: filled paths on the
# 0 -960 960 960 grid, drawn in the current colour. Only the help slides use them; the rest of the page uses ICONS.
MATERIAL = {
    "album": "M480-300q75 0 127.5-52.5T660-480q0-75-52.5-127.5T480-660q-75 0-127.5 52.5T300-480q0 75 52.5 127.5T480-300Zm-28.5-151.5Q440-463 440-480t11.5-28.5Q463-520 480-520t28.5 11.5Q520-497 520-480t-11.5 28.5Q497-440 480-440t-28.5-11.5ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z",
    "arrow_forward": "M647-440H160v-80h487L423-744l57-56 320 320-320 320-57-56 224-224Z",
    "auto_awesome": "m760-600-50-110-110-50 110-50 50-110 50 110 110 50-110 50-50 110Zm0 560-50-110-110-50 110-50 50-110 50 110 110 50-110 50-50 110ZM360-160 260-380 40-480l220-100 100-220 100 220 220 100-220 100-100 220Zm0-194 40-86 86-40-86-40-40-86-40 86-86 40 86 40 40 86Zm0-126Z",
    "date_range": "M291.5-411.5Q280-423 280-440t11.5-28.5Q303-480 320-480t28.5 11.5Q360-457 360-440t-11.5 28.5Q337-400 320-400t-28.5-11.5Zm160 0Q440-423 440-440t11.5-28.5Q463-480 480-480t28.5 11.5Q520-457 520-440t-11.5 28.5Q497-400 480-400t-28.5-11.5Zm160 0Q600-423 600-440t11.5-28.5Q623-480 640-480t28.5 11.5Q680-457 680-440t-11.5 28.5Q657-400 640-400t-28.5-11.5ZM200-80q-33 0-56.5-23.5T120-160v-560q0-33 23.5-56.5T200-800h40v-80h80v80h320v-80h80v80h40q33 0 56.5 23.5T840-720v560q0 33-23.5 56.5T760-80H200Zm0-80h560v-400H200v400Zm0-480h560v-80H200v80Zm0 0v-80 80Z",
    "delete": "M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z",
    "filter_alt": "M440-160q-17 0-28.5-11.5T400-200v-240L168-736q-15-20-4.5-42t36.5-22h560q26 0 36.5 22t-4.5 42L560-440v240q0 17-11.5 28.5T520-160h-80Zm40-308 198-252H282l198 252Zm0 0Z",
    "history": "M480-120q-138 0-240.5-91.5T122-440h82q14 104 92.5 172T480-200q117 0 198.5-81.5T760-480q0-117-81.5-198.5T480-760q-69 0-129 32t-101 88h110v80H120v-240h80v94q51-64 124.5-99T480-840q75 0 140.5 28.5t114 77q48.5 48.5 77 114T840-480q0 75-28.5 140.5t-77 114q-48.5 48.5-114 77T480-120Zm112-192L440-464v-216h80v184l128 128-56 56Z",
    "lock": "M240-80q-33 0-56.5-23.5T160-160v-400q0-33 23.5-56.5T240-640h40v-80q0-83 58.5-141.5T480-920q83 0 141.5 58.5T680-720v80h40q33 0 56.5 23.5T800-560v400q0 33-23.5 56.5T720-80H240Zm0-80h480v-400H240v400Zm296.5-143.5Q560-327 560-360t-23.5-56.5Q513-440 480-440t-56.5 23.5Q400-393 400-360t23.5 56.5Q447-280 480-280t56.5-23.5ZM360-640h240v-80q0-50-35-85t-85-35q-50 0-85 35t-35 85v80ZM240-160v-400 400Z",
    "login": "M480-120v-80h280v-560H480v-80h280q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H480Zm-80-160-55-58 102-102H120v-80h327L345-622l55-58 200 200-200 200Z",
    "play_circle": "m380-300 280-180-280-180v360ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z",
    "playlist_add": "M120-320v-80h280v80H120Zm0-160v-80h440v80H120Zm0-160v-80h440v80H120Zm520 480v-160H480v-80h160v-160h80v160h160v80H720v160h-80Z",
    "queue_music": "M640-160q-50 0-85-35t-35-85q0-50 35-85t85-35q11 0 21 1.5t19 6.5v-328h200v80H760v360q0 50-35 85t-85 35ZM120-320v-80h320v80H120Zm0-160v-80h480v80H120Zm0-160v-80h480v80H120Z",
    "star": "m354-287 126-76 126 77-33-144 111-96-146-13-58-136-58 135-146 13 111 97-33 143ZM233-120l65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Zm247-350Z",
    "verified_user": "m438-338 226-226-57-57-169 169-84-84-57 57 141 141Zm42 258q-139-35-229.5-159.5T160-516v-244l320-120 320 120v244q0 152-90.5 276.5T480-80Zm0-84q104-33 172-132t68-220v-189l-240-90-240 90v189q0 121 68 220t172 132Zm0-316Z",
}

# Each help slide's picture: a main icon in the accent and a second one in amber, joined by an arrow when the
# slide is a step from one thing to the other.
HELP_ART = [
    ("album", "auto_awesome"),
    ("verified_user", "login"),
    ("date_range", "arrow_forward", "queue_music"),
    ("history", "arrow_forward", "filter_alt"),
    ("play_circle", "star"),
    ("playlist_add", "lock"),
    ("queue_music", "arrow_forward", "delete"),
]


def _material(name, cls):
    return f'<svg class="mi {cls}" viewBox="0 -960 960 960" aria-hidden="true"><path d="{MATERIAL[name]}"/></svg>'


def _help_art(names):
    main, *rest = names
    return _material(main, "mi-main") + "".join(
        _material(n, "mi-arrow" if n == "arrow_forward" else "mi-amber") for n in rest)


def _help(lang):
    """The onboarding: graphical slides on how the app works. Auto-opened on first launch, reopened with Help."""
    params = {"days": config.WINDOW_DAYS, "months": config.HALFLIFE_MONTHS}  # the slide on how it picks
    slides = "".join(
        f'<section class="help-slide"{" hidden" if n > 1 else ""}><div class="help-art">{_help_art(art)}</div>'
        f'<h2>{i18n.t(lang, f"help_s{n}_t")}</h2><p>{i18n.t(lang, f"help_s{n}_b", **params)}</p></section>'
        for n, art in enumerate(HELP_ART, 1))
    dots = "".join(f'<button class="dot{" on" if k == 0 else ""}" data-help-go="{k}" aria-label="{k + 1}"></button>'
                   for k in range(len(HELP_ART)))
    return (f'<dialog id="help" aria-label="{i18n.t(lang, "help_title")}"><div class="help-slides">{slides}</div>'
            f'<div class="help-nav"><button class="back" data-help-prev hidden>{i18n.t(lang, "help_prev")}</button>'
            f'<div class="help-dots">{dots}</div>'
            f'<button class="main" data-help-next>{i18n.t(lang, "help_next")}</button>'
            f'<button class="main" data-help-done hidden>{i18n.t(lang, "help_done")}</button></div></dialog>')


def _row(i, t, lang, starred=False, in_playlists=(), control=None):
    """One track. `control` (the playlist editor's remove / add) goes first and replaces the star."""
    preview, cover = _url(t.get("sample_url")), _url(t.get("image"))
    artists = escape(", ".join(t.get("artists") or []))
    name = escape((t.get("name") or "").strip())
    play = (f'<button class="play" data-src="{escape(preview)}" '
            f'aria-label="{i18n.t(lang, "listen")}">{_icon("play_arrow")}</button>' if preview else "")
    img = f'<img src="{escape(cover)}" alt="" loading="lazy">' if cover else '<span class="no-cover"></span>'
    mix = f'<span class="mix">{escape(t["mix_name"])}</span>' if t.get("mix_name") else ""
    meta = "".join(f'<span class="{cls}">{escape(str(x))}</span>' for cls, x in
                   (("genre-name", t.get("genre")), ("label", t.get("label")),
                    ("chip", f"{t['bpm']} BPM" if t.get("bpm") else None), ("chip", t.get("key")),
                    ("date", i18n.day(t["publish_date"], lang) if t.get("publish_date") else None)) if x)
    star = "" if control else (f'<button class="star{" on" if starred else ""}" data-star="{t["id"]}" '
                               f'aria-pressed="{"true" if starred else "false"}" aria-label="{i18n.t(lang, "star")}">'
                               f'{_icon("star")}</button>')
    tag = (f'<span class="in">{i18n.t(lang, "in_playlists", names=escape(", ".join(in_playlists)))}</span>'
           if in_playlists else "")
    reasons = escape(i18n.reasons(t, lang))
    picked = f'{_icon("auto_awesome")}<span>{i18n.t(lang, "picked_for", reasons=reasons)}</span>' if reasons else ""
    why = f'<div class="r">{picked}{tag}</div>' if reasons or tag else ""
    return (f'<li class="track" data-genre="{escape(t.get("genre") or "")}"><span class="num">{i}</span>{control or ""}'
            f'<span class="cover">{img}{play}</span><div class="t"><div class="n"><span class="name">{name}</span>{mix}</div>'
            f'<div class="a">{artists}</div>{why}</div><div class="m">{meta}</div>{star}</li>')


def _genres(crate, lang):
    """Genre filter buttons, most tracks first. Several at once; the JS does the filtering."""
    counts = {}
    for t in crate["tracks"]:
        if t.get("genre"):
            counts[t["genre"]] = counts.get(t["genre"], 0) + 1
    buttons = "".join(f'<button class="genre" data-genre="{escape(g)}">{escape(g)} <small>{n}</small></button>'
                      for g, n in sorted(counts.items(), key=lambda x: -x[1]))
    return (f'<nav class="genres"><button class="genre on" data-all>{i18n.t(lang, "all")} '
            f'<small>{len(crate["tracks"])}</small></button>{buttons}</nav>')


def _playlists(marks, lang, selection, current=None):
    """The playlists made from this selection; each one opens its editor."""
    if not marks["playlists"]:
        return ""
    def item(p):
        on = " on" if current and p["id"] == current["id"] else ""
        gone = p.get("gone")
        tag = f'<small>{i18n.t(lang, "gone_tag")}</small>' if gone else f'<small>{len(p["track_ids"])}</small>'
        return (f'<li><a class="pl{on}{" gone" if gone else ""}" href="/crate/{escape(selection)}/playlist/{p["id"]}">'
                f'<span>{escape(p["name"])}</span> {tag}</a></li>')
    items = "".join(item(p) for p in marks["playlists"])
    return f'<section class="playlists"><h2>{i18n.t(lang, "playlists_here")}</h2><ul>{items}</ul></section>'


def _language_switch(lang):
    return ('<div class="langs">' + " ".join(
        f'<a href="#" data-lang="{code}" class="{"on" if code == lang else ""}">{code.upper()}</a>'
        for code in ("es", "en")) + "</div>")


def _toggle(kind, track_id, lang):
    label, icon = {"remove": ("remove_track", "remove"), "add": ("add_track", "add")}[kind]
    return (f'<button class="toggle {kind}" data-{kind}="{track_id}" aria-pressed="false" '
            f'aria-label="{i18n.t(lang, label)}">{_icon(icon)}</button>')


def _outside_row(i, track_id, info, lang):
    """A track added on beatport.com that is not in the selection: only its title, so it can be removed."""
    if info:
        title = f'{escape(", ".join(info.get("artists") or []))} — {escape(info.get("name") or "")}'
    else:
        title = f"Track {track_id}"
    return (f'<li class="track outside"><span class="num">{i}</span>{_toggle("remove", track_id, lang)}'
            f'<span class="cover"><span class="no-cover"></span></span><div class="t"><div class="n"><span class="name">'
            f'{title}</span></div><div class="r"><span>{i18n.t(lang, "outside_note")}</span></div></div></li>')


def _gone(selection, playlist, lang):
    return (f'<header class="head editor"><a class="back" href="/crate/{escape(selection)}" '
            f'aria-label="{i18n.t(lang, "back")}">{_icon("arrow_back")}</a>'
            f'<div class="title"><h1>{escape(playlist["name"])}</h1></div></header>'
            f'<p class="notice">{_icon("info")}{i18n.error(lang, "playlist_gone")}</p>'
            f'<p class="notice"><button class="create" data-action="forget-playlist" data-playlist="{playlist["id"]}">'
            f'{_icon("playlist_remove")}{i18n.t(lang, "forget_playlist")}</button></p>')


def _status(state, lang):
    """The sidebar's foot: the session, the last selection, the sign-in and the permission."""
    session = (state.get("session") or {}).get("status")
    off = " disabled" if state.get("running") or state.get("login_pending") else ""
    check = (f'<button class="small" data-action="check"{off}>{_icon("verified_user")}'
             f'{i18n.t(lang, "check_session")}</button>')
    icon, text, cls = {"active": ("check_circle", "session_active", "ok"),
                       "expired": ("error", "session_expired", "bad")}.get(session, ("help", "session_unchecked", "muted"))
    parts = [f'<p class="session {cls}">{_icon(icon)}<span>{i18n.t(lang, text)}</span>{check}</p>']
    last = state.get("last_run") or {}
    if last.get("finished_at"):
        when = i18n.moment(last["finished_at"], lang)
        if last.get("ok"):
            parts.append(f'<p class="last">{i18n.t(lang, "last_ok", when=when)}</p>')
        else:
            message = i18n.error(lang, last.get("error_code"), last.get("error_params"), last.get("error") or "")
            parts.append(f'<p class="last bad">{i18n.t(lang, "last_failed", when=when)}<br>'
                         f'<span class="error">{escape(message)}</span></p>')
    if state.get("login_pending"):
        parts.append(f'<p class="working">{i18n.t(lang, "login_hint")}</p>')
    elif session != "active":
        parts.append(f'<button class="warn" data-action="login-start"{off}>{_icon("login")}{i18n.t(lang, "login")}</button>')
    revoke = (f'<button class="link" data-action="revoke">{_icon("remove_moderator")}{i18n.t(lang, "consent_revoke")}</button>'
              if state.get("consent") else "")
    parts.append(f'<div class="side-foot">{_language_switch(lang)}{revoke}</div>')
    return f'<section class="status">{"".join(parts)}</section>'


def _toolbar(title, detail, state, today, lang, selection=None):
    """The top of the main column: the title (with a delete button on a selection), the period, the Genres button
    (with how many genres are adjusted) and the action that makes a new selection."""
    off = " disabled" if state.get("running") or state.get("login_pending") else ""
    since = (today - timedelta(days=config.WINDOW_DAYS)).isoformat()
    delete = _delete_button(selection, lang, off, "delete", "delete_selection") if selection else ""
    prefs = state.get("genre_prefs") or {}
    adjusted = 1 if prefs.get("only") is not None else len(prefs.get("levels") or {})
    return (f'<header class="head"><div class="title"><h1>{title}</h1><span class="detail">{detail}</span></div>{delete}'
            f'<div class="period"><label>{i18n.t(lang, "since")} '
            f'<input type="date" id="since" value="{since}" max="{today}"></label>'
            f'<label>{i18n.t(lang, "until")} <input type="date" id="until" value="{today}" max="{today}"></label></div>'
            f'<button class="create" data-genres-open aria-haspopup="dialog"{off}>{_icon("tune")}'
            f'{i18n.t(lang, "genres_open")}<span class="n"{"" if adjusted else " hidden"}>{adjusted}</span></button>'
            f'<button class="main" data-action="generate"{off}>{_icon("auto_awesome")}{i18n.t(lang, "new_selection")}'
            '</button></header>')


# How a level reads next to a genre's name in the selection's heading; 0 and "only" have their own sentence.
LEVEL_MARKS = {0.5: "−", 2: "+", 4: "++"}


def _prefs_detail(prefs, lang):
    """The genre preferences a selection was made with, for its heading: "only Techno" or "Techno ++ · House −"."""
    parts = []
    for p in prefs or []:
        name = escape(p.get("name") or "")
        if p["level"] == "only":
            parts.append(i18n.t(lang, "only_genre", name=name))
        elif p["level"] == 0:
            parts.append(i18n.t(lang, "genre_off", name=name))
        else:
            parts.append(f"{name} {LEVEL_MARKS[p['level']]}")
    return " · ".join(parts)


def _genres_dialog(profile, state, lang):
    """The Genres dialog: the profile's top genres, each with its share of the slots now and with the choices made
    (the JS keeps the second one up to date), a segmented level control and an "Only" button. Every change is
    saved at once (POST /api/genres); the choices apply to the next selection."""
    prefs = state.get("genre_prefs") or {}
    levels, only = prefs.get("levels") or {}, prefs.get("only")
    top = (profile.get("genres") or [])[:config.TOP_GENRES]
    total = sum(g["weight"] for g in top) or 1
    shares = {g["id"]: round(100 * g["weight"] / total) for g in top}
    rows = []
    for g in (profile.get("genres") or [])[:config.GENRES_SHOWN]:
        level = levels.get(str(g["id"]), 1)
        seg = "".join(
            f'<button data-level="{lv:g}" aria-pressed="{"true" if lv == level else "false"}">'
            f'{i18n.t(lang, "genre_level_0") if lv == 0 else {0.5: "−", 1: "=", 2: "+", 4: "++"}[lv]}</button>'
            for lv in config.GENRE_LEVELS)
        name = escape(g.get("name") or "")
        rows.append(
            f'<li class="gp" data-genre="{g["id"]}" data-weight="{g["weight"]}"><span class="gp-name">{name}</span>'
            f'<span class="gp-share"><span class="now">{shares.get(g["id"], 0)} %</span> → <span class="then"></span></span>'
            f'<div class="seg" role="group" aria-label="{name}">{seg}</div>'
            f'<button class="only" data-only aria-pressed="{"true" if g["id"] == only else "false"}">'
            f'{i18n.t(lang, "genre_only")}</button></li>')
    body = f'<ul class="gps">{"".join(rows)}</ul>' if rows else f'<p class="hint">{i18n.t(lang, "genres_none")}</p>'
    return (f'<dialog id="genres" aria-labelledby="genres-title" data-top="{config.TOP_GENRES}">'
            f'<h2 id="genres-title">{_icon("tune")}{i18n.t(lang, "genres_title")}</h2>'
            f'<p class="hint">{i18n.t(lang, "genres_hint")}</p>{body}<div class="buttons">'
            f'<button class="reset" data-genres-reset{"" if rows else " hidden"}>{i18n.t(lang, "genres_reset")}</button>'
            f'<button class="main" data-genres-done>{i18n.t(lang, "genres_done")}</button></div></dialog>')


# The record drawn as a spinning vinyl for the picking card: navy disc, blue grooves, amber label and a
# light highlight arc so the rotation reads. Echoes the brand mark's colours; it spins through CSS only.
PICK_DISC = ('<svg class="disc" viewBox="0 0 120 120" aria-hidden="true">'
             '<circle cx="60" cy="60" r="59" fill="#0A1F44"/>'
             '<circle cx="60" cy="60" r="52" fill="none" stroke="#0B5FB8" stroke-width="2"/>'
             '<circle cx="60" cy="60" r="45" fill="none" stroke="#0B5FB8" stroke-width="2"/>'
             '<circle cx="60" cy="60" r="38" fill="none" stroke="#0B5FB8" stroke-width="2"/>'
             '<circle cx="60" cy="60" r="31" fill="none" stroke="#0B5FB8" stroke-width="2"/>'
             '<path d="M60 4 A56 56 0 0 1 112 40" fill="none" stroke="#FFFFFF" stroke-opacity=".16" stroke-width="7"/>'
             '<circle cx="60" cy="60" r="22" fill="#F0B12E"/>'
             '<circle cx="60" cy="60" r="11" fill="none" stroke="#0A1F44" stroke-width="1.5"/>'
             '<circle cx="60" cy="60" r="3.5" fill="#0A1F44"/></svg>')


# Where the bar starts in each phase (%); app.js (PICK_BANDS) creeps it from there towards the next phase.
_PICK_FROM = (2, 35, 85)


def _progress(state, lang):
    """The selection under way: a centred card over the whole window with the record spinning, the step, a bar
    and the three phases. app.js moves the bar little by little, updates the phases and, at the end, opens the
    new selection with a "created" message."""
    running = state.get("running")
    if not running:
        return ""
    step = running["step"]
    pct = _PICK_FROM[min(max(step, 1), len(_PICK_FROM)) - 1]
    phase = i18n.t(lang, f"phase_{running.get('phase', 'library')}")
    phases = "".join(
        f'<li class="{"done" if n < step else "now" if n == step else "next"}">'
        f'{i18n.t(lang, f"phase_{p}")}</li>' for n, p in enumerate(("library", "discover", "rank"), 1))
    return (f'<div id="picking" role="status" aria-live="polite">'
            f'<section id="progress" data-step="{step}" data-since="{escape(running.get("since") or "")}">'
            f'<div class="pick-head">{PICK_DISC}<p class="working step">'
            f'{escape(i18n.t(lang, "making", step=step, of=running["of"], phase=phase))}</p></div>'
            f'<div class="pick-bar"><div class="prog"><i style="width:{pct}%"></i></div>'
            f'<span class="pct">{pct}%</span></div><ol class="phases">{phases}</ol></section></div>')


def _empty(lang):
    steps = "".join(f'<li><span class="step-n">{n}</span>{i18n.t(lang, key)}</li>'
                    for n, key in enumerate(("step_consent", "step_login", "step_wait"), 1))
    return (f'<div class="empty">{BRAND_MARK}<h2>{i18n.t(lang, "empty_title")}</h2><p>{i18n.t(lang, "empty")}</p>'
            f'<ol class="steps">{steps}</ol></div>')


def _editor(selection, crate, playlist, starred, lang, refresh):
    """A created playlist: its name, its tracks to remove and the selection's other tracks to add.

    The page only marks the changes; "Save changes" sends them together. With refresh, the page first asks
    the server to check the playlist on Beatport and reloads if it changed there.
    """
    by_id = {t["id"]: t for t in crate["tracks"]}
    outside = playlist.get("outside") or {}
    rows_in = "".join(
        _row(i, by_id[t], lang, control=_toggle("remove", t, lang)) if t in by_id
        else _outside_row(i, t, outside.get(str(t)), lang)
        for i, t in enumerate(playlist["track_ids"], 1))
    others = [t for t in crate["tracks"] if t["id"] not in set(playlist["track_ids"])]
    others.sort(key=lambda t: t["id"] not in starred)  # starred first, then selection order
    rows_add = "".join(_row(i, t, lang, control=_toggle("add", t["id"], lang)) for i, t in enumerate(others, 1))
    sync = (f'<div class="loading" id="syncing" role="status" aria-live="polite">'
            f'<span class="box">{_icon("sync")}{i18n.t(lang, "syncing")}</span></div>'
            if refresh else "")
    return (f'<header class="head editor"><a class="back" href="/crate/{escape(selection)}" '
            f'aria-label="{i18n.t(lang, "back")}">{_icon("arrow_back")}</a>'
            f'<label class="pl-name">{_icon("edit")}<input id="pl-name" value="{escape(playlist["name"])}" '
            f'maxlength="100" aria-label="{i18n.t(lang, "playlist_name")}"></label>'
            f'<span class="private">{_icon("lock")}{i18n.t(lang, "private_tag")}</span>'
            f'<button class="main" data-action="save-playlist" data-playlist="{playlist["id"]}" disabled>'
            f'{_icon("save")}{i18n.t(lang, "save_changes")}</button></header>'
            f'{sync}<p class="notice">{_icon("info")}{i18n.t(lang, "edit_hint")}</p>'
            f'<h2 class="section">{i18n.t(lang, "in_playlist", n=len(playlist["track_ids"]))}</h2>'
            f'<ol class="tracks">{rows_in}</ol>'
            f'<h2 class="section">{i18n.t(lang, "add_from_selection")}</h2><ol class="tracks">{rows_add}</ol>'
            '<audio id="player" preload="none"></audio>')


def render_page(selection, crate, selections, state, token, today, marks=None, lang="en", playlist=None,
                profile=None):
    marks = marks or {"starred": [], "playlists": []}
    off = " disabled" if state.get("running") or state.get("login_pending") else ""
    links = "".join(
        f'<div class="sel-row"><a class="sel{" on" if s == selection else ""}" href="/crate/{escape(s)}">'
        f'{i18n.short_title(s, lang)} <small>{n}</small></a>'
        f'{_delete_button(s, lang, off, "sel-del", "delete_named")}</div>'
        for s, n in selections)
    help_btn = (f'<button class="brand-help" data-help-open aria-label="{i18n.t(lang, "help_open")}" '
                f'title="{i18n.t(lang, "help_open")}">{_icon("help")}</button>')
    side = (f'<aside class="side"><div class="brand">{BRAND_MARK}<span>beatcrate</span>{help_btn}</div>'
            f'<h2 class="side-h">{i18n.t(lang, "selections")}</h2><nav class="sels">{links}</nav>'
            f'{_playlists(marks, lang, selection, playlist)}{_status(state, lang)}</aside>')
    marker = player = ""
    if playlist is not None:
        page_title = f"beatcrate · {playlist['name']}"
        if playlist.get("gone"):
            inner = _gone(selection, playlist, lang)
        else:
            refresh = bool(state.get("consent"))
            marker = ' data-refresh="1"' if refresh else ""
            inner = _editor(selection, crate, playlist, set(marks["starred"]), lang, refresh)
            player = _player()
    elif crate is None:
        page_title = "beatcrate"
        inner = _toolbar("beatcrate", i18n.t(lang, "tagline"), state, today, lang) + _empty(lang)
    else:
        page_title = f"beatcrate · {i18n.title(selection, lang)}"
        w = crate.get("window") or {}
        detail = i18n.t(lang, "tracks", n=len(crate["tracks"]))
        if i18n.CODE.match(selection):
            detail = f'{escape(selection)} · {detail}'
        if w.get("from") and w.get("to"):
            detail += " · " + i18n.t(lang, "period", start=i18n.day(w["from"], lang), end=i18n.day(w["to"], lang))
        if crate.get("candidates_seen"):
            detail += " · " + i18n.t(lang, "candidates", n=crate["candidates_seen"])
        if crate.get("genre_prefs"):
            detail += " · " + _prefs_detail(crate["genre_prefs"], lang)
        notice = (f'<p class="notice">{_icon("info")}{i18n.t(lang, "short", n=len(crate["tracks"]))}</p>'
                  if crate.get("short") else "")
        ids = {t["id"] for t in crate["tracks"]}
        starred = set(marks["starred"]) & ids
        in_playlists = {}
        for p in marks["playlists"]:
            for tid in p["track_ids"]:
                in_playlists.setdefault(tid, []).append(p["name"])
        suggested = escape(selection) if i18n.CODE.match(selection) else selection.replace("-", "")
        count = f'<span class="count"><span id="n-star">{len(starred)}</span>{_icon("star")}</span>'
        create = (f'<button class="create" data-action="playlist" data-suggested="{suggested} "'
                  f'{"" if starred else " disabled"}>{_icon("playlist_add")}'
                  f'{i18n.t(lang, "create_playlist", count=count)}</button>')
        rows = "".join(_row(i, t, lang, t["id"] in starred, in_playlists.get(t["id"], ()))
                       for i, t in enumerate(crate["tracks"], 1))
        inner = (_toolbar(i18n.title(selection, lang), detail, state, today, lang, selection)
                 + f'<div class="filters">{_genres(crate, lang)}{create}</div>{notice}<ol class="tracks">{rows}</ol>'
                 '<audio id="player" preload="none"></audio>')
        player = _player()
    main = f'<main class="list"{marker}>{inner}</main>{player}'
    # While a selection is made the whole window waits: the app underneath is inert and the card sits on top.
    inert = " inert" if state.get("running") else ""
    texts = json.dumps(i18n.js_texts(lang), ensure_ascii=False).replace("</", "<\\/")
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="bc-token" content="{escape(token)}"><title>{escape(page_title)}</title>'
            '<link rel="stylesheet" href="/static/app.css"></head>'
            f'<body data-selection="{escape(selection or "")}" data-running="{"1" if state.get("running") else "0"}"'
            f' data-consent="{"1" if state.get("consent") else "0"}" data-login="{"1" if state.get("login_pending") else "0"}"'
            f' data-help="{"0" if state.get("help_seen") else "1"}">'
            f'{_sprite()}<div class="app"{inert}>{side}{main}</div>{_progress(state, lang)}{_action_loading()}{_toast()}'
            f'{_help(lang)}{_consent(lang)}{_genres_dialog(profile or {}, state, lang)}'
            f'<script id="texts" type="application/json">{texts}</script>'
            '<script src="/static/app.js"></script></body></html>')
