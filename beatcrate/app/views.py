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


def _action_loading():
    # A centred overlay the JS shows while an action talks to Beatport; the JS sets its message (creating,
    # saving, checking the session). Rendered once per page, so it is there wherever those actions are.
    return ('<div class="loading" id="action-loading" hidden role="status" aria-live="polite">'
            f'<span class="box">{_icon("sync")}<span class="msg"></span></span></div>')


# One line drawing per help slide, 2 px stroke in the accent colour; `.amber` parts take the star colour.
_SVG = ('<svg viewBox="0 0 120 72" fill="none" stroke="currentColor" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round">')
HELP_ART = [
    _SVG + '<circle cx="46" cy="36" r="24"/><circle cx="46" cy="36" r="13"/>'
           '<circle cx="46" cy="36" r="3" fill="currentColor" stroke="none"/>'
           '<path class="amber" d="M88 20 l3.2 7.8 7.8 3.2 -7.8 3.2 -3.2 7.8 -3.2 -7.8 -7.8 -3.2 7.8 -3.2 z"/></svg>',
    _SVG + '<rect x="16" y="18" width="50" height="36" rx="4"/><line x1="16" y1="28" x2="66" y2="28"/>'
           '<rect x="80" y="34" width="24" height="18" rx="3"/><path d="M85 34 v-5 a7 7 0 0 1 14 0 v5"/>'
           '<circle cx="92" cy="43" r="2.5"/></svg>',
    _SVG + '<rect x="14" y="20" width="32" height="32" rx="4"/><line x1="14" y1="29" x2="46" y2="29"/>'
           '<line x1="22" y1="15" x2="22" y2="24"/><line x1="38" y1="15" x2="38" y2="24"/>'
           '<path d="M52 36 h14"/><path d="M61 31 l5 5 -5 5"/>'
           '<line x1="74" y1="26" x2="104" y2="26"/><line x1="74" y1="36" x2="104" y2="36"/>'
           '<line x1="74" y1="46" x2="96" y2="46"/></svg>',
    _SVG + '<circle cx="40" cy="36" r="18"/><path d="M35 27 l13 9 -13 9 z" fill="currentColor" stroke="none"/>'
           '<path class="amber" d="M86 22 l3.5 8.5 9 0.6 -7 5.8 2.3 8.7 -7.8 -4.8 -7.8 4.8 2.3 -8.7 -7 -5.8 9 -0.6 z"/></svg>',
    _SVG + '<rect x="20" y="16" width="52" height="40" rx="4"/><line x1="28" y1="27" x2="64" y2="27"/>'
           '<line x1="28" y1="36" x2="64" y2="36"/><line x1="28" y1="45" x2="52" y2="45"/>'
           '<rect x="82" y="22" width="18" height="13" rx="2"/><path d="M85.5 22 v-3 a5.5 5.5 0 0 1 11 0 v3"/>'
           '<path class="amber" d="M91 44 v12 M85 50 h12"/></svg>',
]


def _help(lang):
    """The onboarding: graphical slides on how the app works. Auto-opened on first launch, reopened with Help."""
    slides = "".join(
        f'<section class="help-slide"{" hidden" if n > 1 else ""}><div class="help-art">{art}</div>'
        f'<h2>{i18n.t(lang, f"help_s{n}_t")}</h2><p>{i18n.t(lang, f"help_s{n}_b")}</p></section>'
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
    help_btn = f'<button class="link" data-help-open>{_icon("help")}{i18n.t(lang, "help_open")}</button>'
    parts.append(f'<div class="side-foot">{_language_switch(lang)}{help_btn}{revoke}</div>')
    return f'<section class="status">{"".join(parts)}</section>'


def _toolbar(title, detail, state, today, lang):
    """The top of the main column: the title, the period and the action that makes a new selection."""
    off = " disabled" if state.get("running") or state.get("login_pending") else ""
    since = (today - timedelta(days=config.WINDOW_DAYS)).isoformat()
    return (f'<header class="head"><div class="title"><h1>{title}</h1><span class="detail">{detail}</span></div>'
            f'<div class="period"><label>{i18n.t(lang, "since")} '
            f'<input type="date" id="since" value="{since}" max="{today}"></label>'
            f'<label>{i18n.t(lang, "until")} <input type="date" id="until" value="{today}" max="{today}"></label></div>'
            f'<button class="main" data-action="generate"{off}>{_icon("auto_awesome")}{i18n.t(lang, "new_selection")}'
            '</button></header>')


# The record drawn as a spinning vinyl for the picking overlay: navy disc, blue grooves, amber label and a
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


def _progress(state, lang):
    """The selection under way: a full-screen overlay with the record spinning in the centre, the phase and a
    bar. app.js keeps the text, bar and phases up to date and reloads when it ends."""
    running = state.get("running")
    if not running:
        return ""
    pct = round(100 * running["step"] / (running["of"] + 1))
    phase = i18n.t(lang, f"phase_{running.get('phase', 'library')}")
    phases = "".join(
        f'<li class="{"done" if n < running["step"] else "now" if n == running["step"] else "next"}">'
        f'{i18n.t(lang, f"phase_{p}")}</li>' for n, p in enumerate(("library", "discover", "rank"), 1))
    return (f'<div id="picking" role="status" aria-live="polite">{PICK_DISC}'
            f'<section id="progress"><p class="working step">'
            f'{escape(i18n.t(lang, "making", step=running["step"], of=running["of"], phase=phase))}</p>'
            f'<div class="prog"><i style="width:{pct}%"></i></div><ol class="phases">{phases}</ol></section></div>')


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


def render_page(selection, crate, selections, state, token, today, marks=None, lang="en", playlist=None):
    marks = marks or {"starred": [], "playlists": []}
    running = f'<span class="sel running">{_icon("sync")}{i18n.t(lang, "running")}</span>' if state.get("running") else ""
    links = "".join(
        f'<a class="sel{" on" if s == selection else ""}" href="/crate/{escape(s)}">'
        f'{i18n.short_title(s, lang)} <small>{n}</small></a>'
        for s, n in selections)
    side = (f'<aside class="side"><div class="brand">{BRAND_MARK}beatcrate</div>'
            f'<h2 class="side-h">{i18n.t(lang, "selections")}</h2><nav class="sels">{running}{links}</nav>'
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
        inner = (_toolbar(i18n.title(selection, lang), detail, state, today, lang)
                 + f'<div class="filters">{_genres(crate, lang)}{create}</div>{notice}<ol class="tracks">{rows}</ol>'
                 '<audio id="player" preload="none"></audio>')
        player = _player()
    main = f'<main class="list"{marker}>{_progress(state, lang)}{inner}</main>{player}'
    texts = json.dumps(i18n.js_texts(lang), ensure_ascii=False).replace("</", "<\\/")
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="bc-token" content="{escape(token)}"><title>{escape(page_title)}</title>'
            '<link rel="stylesheet" href="/static/app.css"></head>'
            f'<body data-selection="{escape(selection or "")}" data-running="{"1" if state.get("running") else "0"}"'
            f' data-consent="{"1" if state.get("consent") else "0"}" data-login="{"1" if state.get("login_pending") else "0"}"'
            f' data-help="{"0" if state.get("help_seen") else "1"}">'
            f'{_sprite()}<div class="app">{side}{main}</div>{_action_loading()}{_help(lang)}{_consent(lang)}'
            f'<script id="texts" type="application/json">{texts}</script>'
            '<script src="/static/app.js"></script></body></html>')
