
# beat50 architecture

How beat50 works today. For using it, see [README.md](README.md).

## Overview

beat50 is a single-user Mac app. It reads the user's Beatport purchases and playlists, builds a taste
profile, looks for new releases in a period, and picks 50 of them. The user browses each selection in the
app's window (a local page served on 127.0.0.1), stars tracks and turns them into private Beatport
playlists. **My playlists** shows the user's own playlists, plays their previews and puts their tracks in order.
**Drafts** are playlists put together on the Mac first and uploaded to Beatport when ready.

Everything runs on the user's Mac. There is no remote server, no account of ours and no background job:
a selection is made when the user asks for it.

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Paths and tunable constants |
| `webkit.py` | beat50's windows (WebKit through pywebview): the app's own and Beatport's |
| `auth.py` | Gets a Beatport user token from a Beatport window |
| `client.py` | Beatport API v4 client: paging, retries, token renewal, the single `post()` |
| `ingest.py` | Library: playlists + purchases → `library.json` |
| `profile.py` | Taste profile: weighted labels, artists, genres, BPM and key → `profile.json`; `apply_prefs` applies the Genres choices |
| `discover.py` | Candidates published in the period → `candidates.json` |
| `rank.py` | Scoring, exclusions, genre quotas, diversity → `crates/<code>.json` |
| `playlists.py` | Creates private playlists, edits them, adds tracks to the user's private ones and reorders them: beat50's only writes to Beatport |
| `errors.py` | Errors with a code, so the app can show them translated |
| `cli.py` | `login`, `ingest`, `generate`, `app` |
| `app/server.py` | Local HTTP server: routes, security, lifecycle |
| `app/views.py` | The page's HTML |
| `app/i18n.py` | English and Spanish texts, dates and error messages |
| `app/jobs.py` | Long-running work: selections, session check, sign-in, playlists (create, list, add, edit, read, reorder), drafts (add tracks, upload) |
| `app/state.py` | `state.json` and the process lock |
| `app/marks.py` | Stars and the playlists made or added to from each selection |
| `app/drafts.py` | Drafts: playlists kept on the Mac until one is uploaded |
| `app/consent.py` | The user's permission to read the Beatport session |
| `app/trash.py` | Moves a deleted selection's files to the Mac's Trash |
| `app/static/` | CSS and JavaScript of the page |
| `packaging/` | Entry point of the packaged app and the DMG notes |

## Getting a Beatport token

`api.beatport.com/v4` is not behind Cloudflare, but every token comes from `www.beatport.com`, which is.
A script cannot get one, and Beatport does not let you sign in inside an automated browser. So:

- `webkit.py` opens `www.beatport.com` in a WebKit window (Safari's engine, through pywebview). It is not
  automated, so the site treats it like Safari. The site keeps its session in the app's own website data
  (`~/Library/WebKit/<bundle id>`), not shared with any browser.
- To sign in, the window is visible; `auth.py` polls it every 2 s and closes it once it holds a valid
  token, or stops when the user closes it (15 minutes at most).
- For a fresh token, the window is hidden. The token is read with a synchronous request to NextAuth's
  `/api/auth/session` (`token.accessToken`), which the site refreshes when asked.
- The user token (scope `openid user:dj app:prostore`) lasts **10 minutes**. Every job asks for a fresh
  one; `client.py` renews it once if it expires midway.
- After hours without use, NextAuth needs a silent re-login that only happens when a page loads. If no
  valid token shows up within 15 s, `auth.py` reloads the store page and keeps polling for 30 s more.
  Each read gives up after 10 s, so a window that never answers cannot block a job. If the window closes
  from outside (beat50 quitting), the job ends as interrupted and the session is not marked expired.
- A token counts as valid only if `/my/account/` answers 200.
- Cocoa needs its event loop on the main thread: the app's window owns it, and the command line runs its
  work inside `webkit.run`. Jobs open, read and close windows from other threads.

## Beatport API (as verified)

Base `https://api.beatport.com/v4`, header `Authorization: Bearer <token>`.

| Use | Request | Notes |
|---|---|---|
| Playlists | `GET /my/playlists/` | `id`, `name`, `updated_date`, `track_count`, `is_public`, `is_owner`, … |
| Playlist tracks | `GET /my/playlists/{id}/tracks/` | each item `{id, position, track, tombstoned}` |
| Purchases | `GET /my/downloads/` | each item is the track, with `purchase_date`, without `isrc` |
| Catalog | `GET /catalog/tracks/` | `label_id`, `artist_id` accept comma-separated lists; `publish_date=YYYY-MM-DD:YYYY-MM-DD` |
| Genre charts | `GET /catalog/genres/{id}/top/100/` | the current top 100 |
| Create playlist | `POST /my/playlists/` `{"name"}` | 201; returns the playlist, private by default |
| Add tracks | `POST /my/playlists/{id}/tracks/bulk/` `{"track_ids"}` | 200 |
| Rename | `PATCH /my/playlists/{id}/` `{"name"}` | Leaves `is_public` as it was |
| Remove tracks | `DELETE /my/playlists/{id}/tracks/bulk/` `{"item_ids"}` | Item ids from `/tracks/`, not track ids |
| Reorder | `PATCH /my/playlists/{id}/tracks/bulk/` `{"items": [{"position", "item_id"}]}` | 200, returns the playlist. Not documented: found in beatport.com's own code and checked on a real private playlist (2026-11-17). beat50 sends every item, positions from 1; the item ids and `is_public` stay as they were |

- `per_page` goes up to 1000; `count` saturates at 10000. Listing a genre with `genre_id` returns tens
  of thousands of tracks a month, so genres are covered through their charts instead.
- `sub_genre` is almost always null; the fine-grained `genre` (e.g. "Techno (Raw / Deep / Hypnotic)") is
  what the profile uses.
- Retries: GET retries 429 and 5xx; writes (POST, PATCH, DELETE) retry only 429, because a write that got a
  5xx may have been applied and repeating it could duplicate a playlist or its tracks.

## Making a selection

1. **Library** (`ingest.py`): every playlist track (`origin: playlist:<id>`, dated by the playlist's last
   update) and every purchase (`origin: purchase`, dated by `purchase_date`). A purchase wins over a
   playlist for the same track.
2. **Profile** (`profile.py`): each track weighs `decay = 0.5 ** (months / 18)`, the same for a purchase
   and a playlist track. Labels, artists (including remixers) and genres
   sum those weights and are normalised to the top one. BPM (weighted p10, median, p90) and key
   frequencies use the same weights. `profile.json` is that profile as the library says; the selection then
   works on `apply_prefs(profile, state.genre_prefs)`: each genre's weight times its level (0, 0.5, 1, 2 or
   4; `config.GENRE_LEVELS`), or only one genre with `only`, normalised and ordered again, so the charts,
   the score and the slots below all follow. Genres at level 0 (`genres_off`), or every other one under
   `only` (`genre_only`), never enter the selection. An `only` no longer in the profile is ignored.
3. **Candidates** (`discover.py`): in the chosen period (by default the last 31 days), releases from the
   top 50 labels and top 100 artists, plus each of the top 5 genres' current chart trimmed to the period.
   At most 60 requests, as a safety net.
4. **Ranking** (`rank.py`):
   - `score = 0.35 label + 0.30 best artist + 0.20 genre + 0.10 BPM fit + 0.05 key frequency`. BPM fit is
     1 inside p10–p90 and fades to 0 at 15 BPM outside.
   - Left out: tracks in the library (by id, by ISRC, and by artists + title + mix, which catches
     purchases since they come without ISRC) and tracks in any earlier selection.
   - Each top-5 genre gets slots proportional to its weight (largest remainder); a second pass fills the
     slots of genres without enough candidates. At most 3 tracks per label and 2 per artist.
   - The selection records the genre choices it was made with (`genre_prefs`: `[{id, name, level}]`, level
     `"only"` for the one kept), shown in its heading.
   - Each track keeps its two strongest reasons (`{"kind", "value"}`), shown translated.
5. The selection is saved as `crates/<YYYYMMDD_HHMMSS>.json` and never overwritten.

## Data

All user data lives in `~/Library/Application Support/beatcrate/` (or `$BEAT50_DATA`). The folder, the bundle id
(`com.beatcrate.app`, under which macOS keeps the Beatport session) and the `beatcrate_lang` cookie keep the app's
name before 3.0, so renaming it to beat50 did not lose any data or sign anyone out:

| Path | Content |
|---|---|
| `session.json` | Last token, mode 0600 |
| `library.json`, `profile.json`, `candidates.json` | Last library, profile and candidates |
| `crates/<code>.json` | One file per selection. Files named `YYYY-MM` come from an earlier version and are still shown |
| `drafts/<id>.json` | One file per draft: `{"id" (12 hex), "name", "created_at", "updated_at", "tracks": [what the page shows of each], "uploaded": null or {"playlist_id", "name", "tracks", "at"}}` |
| `marks/<code>.json` | `{"starred": [...], "playlists": [{id, name, track_ids, created_at or added_at, external?}]}` |
| `state.json` | Running job, last selection result, session status, `genre_prefs` (`{"levels": {"<genre id>": level}, "only": id or null}`) |
| `consent.json` | `{"session": true, "granted_at"}` once the user accepts the notice; deleted when withdrawn |
| `.lock` | Process lock (`flock`) |

Marks live apart from selections and are written atomically under an in-process lock, so two quick
clicks never lose a star.

Deleting a selection (`POST /api/selection/<code>/delete`) moves `crates/<code>.json` and, if any,
`marks/<code>.json` to the Trash (`NSFileManager`, so Finder can put them back). It is local only (no consent),
waits while beat50 is busy (409) and leaves the playlists on Beatport untouched. The page then goes home if it
was showing that selection, or reloads. Since earlier selections are
read from `crates/`, its tracks may be picked again.

## The local app

- `app/server.py` listens on `127.0.0.1:8765` only. Requests with any other `Host` get 403 (DNS
  rebinding). Every POST needs the `X-Beat50-Token` header with a random token created at startup and
  embedded in the page, so no other website can trigger actions.
- Routes: `GET /`, `/crate/<code>`, `/static/*`, `/api/state`, `/api/health`; `POST /api/consent` (`on`),
  `/api/generate` (`since`, `until`), `/api/session/check`, `/api/login/start`, `/api/star/<code>/<track>`
  (`on`), `/api/playlist/<code>` (`name` or `into`, `genres`), `/api/playlists` (the user's own playlists),
  `/api/playlist/<code>/<id>` (`name`, `remove`, `add`),
  `/api/selection/<code>/delete`, `/api/genres` (`levels`, `only`: the Genres dialog's choices, saved whole on
  every change; local only, 409 while busy), `/api/my/playlists`, `/api/my/playlist/<id>` and
  `/api/my/playlist/<id>/order` (`item_ids`), the playlist manager's; `/api/drafts/add` (`track_ids`, `selection` or
  `playlist`, `draft` or `name`), `/api/draft/<id>` (`name`, `track_ids`), `/api/draft/<id>/upload` and
  `/api/draft/<id>/delete`, the drafts'.
  Also `GET /crate/<code>/playlist/<id>`, the playlist editor, `GET /playlists`, `/playlists/<id>`, the manager, and
  `GET /drafts/<id>`, a draft.
- Consent: the routes that read the session (`generate`, `session/check`, `login/start`, `playlist/*`, `playlists`, `my/*`, `draft/<id>/upload`)
  answer 409 `consent_required` until the user accepts the notice in the page, which explains the Beatport
  window, what is read, what beat50 never does and where the session is kept. The page asks before the
  first such action and then carries it out; **Withdraw permission** deletes `consent.json`, not the
  session. A `consent.json` from version 1.1 (`"chrome": true`) is asked again. The command line does not
  ask.
- Period rules: `until` not after today, `since` not after `until`, at most a year.
- While a selection runs, every page renders the app `inert` under the picking card, so nothing can be clicked
  or reached with the keyboard; the page polls `/api/state` and, when it ends well, opens `/crate/<id>?created=1`,
  which shows a "created" message once and drops the query. If it failed, the page reloads and the sidebar says why.
- Lifecycle: `run_app` serves in a thread and shows the page in the app's window (`webkit.show_app`);
  when the window closes, the server stops and any sign-in window closes. Closing it (or quitting) while
  a selection, a session check or a playlist is under way asks for confirmation first. While the sign-in
  window is open, the other session actions wait, and the page polls `/api/state` and reloads once it
  closes.
- Selections, session checks and playlists run under a process lock (`flock` on `.lock`), so the app and
  the command line never overlap. The kernel releases the lock if the process dies.
- Icons: inline SVG, drawn in `views.ICONS` on a 24 px grid and embedded once per page as a `<symbol>`
  sprite; every icon on the page is a `<use>` of one. A name missing from `ICONS` renders nothing, so a
  drawing and its use change together. Icons always sit next to a label or inside a button with
  `aria-label`. The stylesheet uses the system font (SF Pro) and is night mode only (always dark);
  its tokens, type scale and components are described in [STYLE.md](STYLE.md).
- Language: the `beatcrate_lang` cookie (the ES / EN switch) or else the Mac's language (sent by the window as `Accept-Language`). Errors from
  the core carry a code that `app/i18n.py` turns into the user's language.
- Playlists are always private: if Beatport returns one that is not `is_public: false`, beat50 stops
  before adding tracks and says so. Once a playlist exists it is always recorded, even if adding or
  counting tracks failed, so a retry does not duplicate it.
- Adding to an existing playlist: the dialog behind **Create Beatport playlist** lists the user's own playlists
  (`POST /api/playlists`, `playlists.list_playlists`: `is_owner` true, newest first; public ones listed but not
  selectable). The page filters that list by name as the user types (every word, ignoring case and accents);
  a chosen playlist the filter hides is unchosen. `POST /api/playlist/<code>` with `{into}` runs `playlists.add_to_playlist`: it reads the playlist on
  Beatport, refuses one that is public (`is_public` not false) or not the user's (`is_owner` not true; when the record
  leaves it out, the list of the user's playlists decides) before writing,
  and adds at the end only the starred tracks not already in it, by track id and in selection order. If they are
  all there, nothing is written. The playlist is then recorded in that selection's `marks/`; one that no
  selection recorded as created by beat50 is `external`, and its editor only adds (name read-only, no remove;
  `jobs.edit_playlist` refuses a rename or a removal with `add_only` and adds through `add_to_playlist`, so the
  same checks run again). Consent version 3 says so.
- Editing (`/crate/<code>/playlist/<id>`, saved with `POST /api/playlist/<code>/<id>` `{name, remove, add}`):
  only playlists recorded in `marks/` can be opened or saved. The page marks changes and sends them
  together. `playlists.edit_playlist` first reads the playlist as it is on Beatport, renames it if the name
  changed, removes the items of the tracks to remove, adds the tracks not already in it, and reads it again;
  a step that fails becomes a warning while the others still run. The record in `marks/` takes the result.
  Only tracks of the selection can be added.
- Opening the editor (with consent) posts `/api/playlist/<code>/<id>/refresh`: `playlists.read_playlist`
  reads the playlist on Beatport and `marks/` takes its name, its tracks and the titles of tracks added
  outside the selection (`outside`); if it changed, the page reloads. Meanwhile the editor waits. A playlist
  that answers 404 is marked `gone`: the sidebar strikes it through and the editor offers
  `/api/playlist/<code>/<id>/forget`, which drops the local record only (no consent needed). Renaming
  compares with the name on Beatport, not with the record.

## Managing playlists

**My playlists** (`/playlists`, linked at the top of the sidebar) works on the user's own playlists as they are on
Beatport, with nothing kept locally: the page holds a place that app.js fills, after consent, with the HTML the
server answers (`views.my_list`, `views.my_tracks`), so everything from Beatport is escaped on the server.

- The list is `playlists.list_playlists` (`is_owner` true, newest first), each with its track count, length, BPM
  range, genres and first cover. Public ones are listed too.
- A playlist (`/playlists/<id>`) is read with `playlists.read_items`: every item in position order, including those
  whose track Beatport withdrew (`track` null), which keep their place. Each track shows its preview, BPM, Camelot
  key and length; the previews play one after another.
- Only a playlist that is the user's (`is_owner` true; when the record leaves it out, the list of the user's
  playlists decides) and private (`is_public` false) can be reordered. Its rows can be dragged, moved with ↑ ↓ on
  their handle, or sorted by BPM or key (Camelot wheel order, unknowns last); **Save order** posts every item id in
  the new order.
- `playlists.reorder_playlist` reads the playlist again, refuses (before writing) one that is public or not the
  user's, and one whose items are not exactly the ones sent (`playlist_changed`, 409: something was added or removed
  on Beatport since the page read it). Then it sends the PATCH with every item and reads the order back; if it does
  not match, the message warns. If the order did not change, nothing is written.
- Any other playlist (public, or not the user's) is shown without handles, sort buttons or Save.

## Drafts

A draft is a playlist that lives only in `drafts/<id>.json` until the user uploads it. Everything but the upload is
local: no consent, no session, no request to Beatport.

- **Adding tracks** (`POST /api/drafts/add`, `jobs.add_to_draft`): the page sends track ids and where they come from,
  never the tracks themselves. The server takes them from the selection's file or, for a playlist in the manager,
  from the last playlist it read for the page (`jobs._my_last`, in memory; any other playlist is refused with
  `not_loaded`). With `draft` they go to that draft, with `name` to a new one. `drafts.add` keeps of each track what
  the page shows (`TRACK_KEYS`) and leaves out the ones already in the draft. The dialog offers the drafts not
  uploaded yet, the last one changed chosen.
- **The draft's page** (`GET /drafts/<id>`) is rendered from the file, with the manager's rows: preview, BPM, key,
  drag, ↑ ↓, sort by BPM or key, plus a remove button per track and the name. Each change posts the whole draft
  (`POST /api/draft/<id>` `{name, track_ids}`): `drafts.save` accepts only the draft's own tracks, each once, in the
  order sent; the ones left out are removed. Tracks from a selection carry no length, so the total minutes show
  only when every track has one.
- **Uploading** (`POST /api/draft/<id>/upload`, with consent, 409 while busy): `jobs.upload_draft` refuses an empty or
  already uploaded draft, then calls `playlists.create_playlist` with the draft's name and track ids in order (the
  same call a selection's stars use: private or nothing is added). Once the playlist exists it is recorded in the
  draft (`uploaded`), even with warnings, so a retry cannot duplicate it. An uploaded draft is a record:
  `drafts.add` and `drafts.save` refuse it (`draft_uploaded`), its page shows no controls and links to
  `/playlists/<playlist id>`.
- **Deleting** (`POST /api/draft/<id>/delete`) moves the file to the Trash; the playlist of an uploaded draft stays
  on Beatport.

## Packaging

- `beat50.spec` (PyInstaller) builds `beat50.app`, a regular app with a Dock icon, with Python and
  pywebview inside and the app icon from `assets/`. The entry point
  (`packaging/beat50_app.py`) runs `beat50 app` on a double-click and sends output to
  `~/Library/Logs/beat50.log`.
- `scripts/build_dmg.sh` puts the app, a link to Applications and `FIRST-OPEN.txt` in a compressed DMG.
- The app is built for Apple silicon and is not signed with an Apple developer account.

## Tests

`.venv/bin/python -m pytest` runs the suite without network or windows: Beatport, the windows and the clock
are faked, and the `data_dir` fixture points the data files at a temporary folder. Fixtures in
`tests/fixtures/` are real API responses with personal data removed.
