# beatcrate architecture

How beatcrate works today. For using it, see [README.md](README.md).

## Overview

beatcrate is a single-user Mac app. It reads the user's Beatport purchases and playlists, builds a taste
profile, looks for new releases in a period, and picks 50 of them. The user browses each selection in the
app's window (a local page served on 127.0.0.1), stars tracks and turns them into private Beatport
playlists.

Everything runs on the user's Mac. There is no remote server, no account of ours and no background job:
a selection is made when the user asks for it.

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Paths and tunable constants |
| `webkit.py` | beatcrate's windows (WebKit through pywebview): the app's own and Beatport's |
| `auth.py` | Gets a Beatport user token from a Beatport window |
| `client.py` | Beatport API v4 client: paging, retries, token renewal, the single `post()` |
| `ingest.py` | Library: playlists + purchases → `library.json` |
| `profile.py` | Taste profile: weighted labels, artists, genres, BPM and key → `profile.json` |
| `discover.py` | Candidates published in the period → `candidates.json` |
| `rank.py` | Scoring, exclusions, genre quotas, diversity → `crates/<code>.json` |
| `playlists.py` | Creates private playlists and edits them: beatcrate's only writes to Beatport |
| `errors.py` | Errors with a code, so the app can show them translated |
| `cli.py` | `login`, `ingest`, `generate`, `app` |
| `app/server.py` | Local HTTP server: routes, security, lifecycle |
| `app/views.py` | The page's HTML |
| `app/i18n.py` | English and Spanish texts, dates and error messages |
| `app/jobs.py` | Long-running work: selections, session check, sign-in, playlist creation |
| `app/state.py` | `state.json` and the process lock |
| `app/marks.py` | Stars and created playlists per selection |
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
  from outside (beatcrate quitting), the job ends as interrupted and the session is not marked expired.
- A token counts as valid only if `/my/account/` answers 200.
- Cocoa needs its event loop on the main thread: the app's window owns it, and the command line runs its
  work inside `webkit.run`. Jobs open, read and close windows from other threads.

## Beatport API (as verified)

Base `https://api.beatport.com/v4`, header `Authorization: Bearer <token>`.

| Use | Request | Notes |
|---|---|---|
| Playlists | `GET /my/playlists/` | `id`, `name`, `updated_date`, … |
| Playlist tracks | `GET /my/playlists/{id}/tracks/` | each item `{id, position, track, tombstoned}` |
| Purchases | `GET /my/downloads/` | each item is the track, with `purchase_date`, without `isrc` |
| Catalog | `GET /catalog/tracks/` | `label_id`, `artist_id` accept comma-separated lists; `publish_date=YYYY-MM-DD:YYYY-MM-DD` |
| Genre charts | `GET /catalog/genres/{id}/top/100/` | the current top 100 |
| Create playlist | `POST /my/playlists/` `{"name"}` | 201; returns the playlist, private by default |
| Add tracks | `POST /my/playlists/{id}/tracks/bulk/` `{"track_ids"}` | 200 |
| Rename | `PATCH /my/playlists/{id}/` `{"name"}` | Leaves `is_public` as it was |
| Remove tracks | `DELETE /my/playlists/{id}/tracks/bulk/` `{"item_ids"}` | Item ids from `/tracks/`, not track ids |

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
2. **Profile** (`profile.py`): each track weighs `decay × origin`, where `decay = 0.5 ** (months / 18)`
   and `origin` is 1.0 for purchases, 0.6 for playlists. Labels, artists (including remixers) and genres
   sum those weights and are normalised to the top one. BPM (weighted p10, median, p90) and key
   frequencies use the same weights.
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
   - Each track keeps its two strongest reasons (`{"kind", "value"}`), shown translated.
5. The selection is saved as `crates/<YYYYMMDD_HHMMSS>.json` and never overwritten.

## Data

All user data lives in `~/Library/Application Support/beatcrate/` (or `$BEATCRATE_DATA`):

| Path | Content |
|---|---|
| `session.json` | Last token, mode 0600 |
| `library.json`, `profile.json`, `candidates.json` | Last library, profile and candidates |
| `crates/<code>.json` | One file per selection. Files named `YYYY-MM` come from an earlier version and are still shown |
| `marks/<code>.json` | `{"starred": [...], "playlists": [{id, name, track_ids, created_at}]}` |
| `state.json` | Running job, last selection result, session status |
| `consent.json` | `{"session": true, "granted_at"}` once the user accepts the notice; deleted when withdrawn |
| `.lock` | Process lock (`flock`) |

Marks live apart from selections and are written atomically under an in-process lock, so two quick
clicks never lose a star.

Deleting a selection (`POST /api/selection/<code>/delete`) moves `crates/<code>.json` and, if any,
`marks/<code>.json` to the Trash (`NSFileManager`, so Finder can put them back). It is local only (no consent),
waits while beatcrate is busy (409) and leaves the playlists on Beatport untouched. Since earlier selections are
read from `crates/`, its tracks may be picked again.

## The local app

- `app/server.py` listens on `127.0.0.1:8765` only. Requests with any other `Host` get 403 (DNS
  rebinding). Every POST needs the `X-Beatcrate-Token` header with a random token created at startup and
  embedded in the page, so no other website can trigger actions.
- Routes: `GET /`, `/crate/<code>`, `/static/*`, `/api/state`, `/api/health`; `POST /api/consent` (`on`),
  `/api/generate` (`since`, `until`), `/api/session/check`, `/api/login/start`, `/api/star/<code>/<track>`
  (`on`), `/api/playlist/<code>` (`name`, `genres`), `/api/playlist/<code>/<id>` (`name`, `remove`, `add`),
  `/api/selection/<code>/delete`.
  Also `GET /crate/<code>/playlist/<id>`, the playlist editor.
- Consent: the routes that read the session (`generate`, `session/check`, `login/start`, `playlist/*`)
  answer 409 `consent_required` until the user accepts the notice in the page, which explains the Beatport
  window, what is read, what beatcrate never does and where the session is kept. The page asks before the
  first such action and then carries it out; **Withdraw permission** deletes `consent.json`, not the
  session. A `consent.json` from version 1.1 (`"chrome": true`) is asked again. The command line does not
  ask.
- Period rules: `until` not after today, `since` not after `until`, at most a year.
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
- Playlists are always private: if Beatport returns one that is not `is_public: false`, beatcrate stops
  before adding tracks and says so. Once a playlist exists it is always recorded, even if adding or
  counting tracks failed, so a retry does not duplicate it.
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

## Packaging

- `beatcrate.spec` (PyInstaller) builds `beatcrate.app`, a regular app with a Dock icon, with Python and
  pywebview inside and the app icon from `assets/`. The entry point
  (`packaging/beatcrate_app.py`) runs `beatcrate app` on a double-click and sends output to
  `~/Library/Logs/beatcrate.log`.
- `scripts/build_dmg.sh` puts the app, a link to Applications and `FIRST-OPEN.txt` in a compressed DMG.
- The app is built for Apple silicon and is not signed with an Apple developer account.

## Tests

`.venv/bin/python -m pytest` runs the suite without network or windows: Beatport, the windows and the clock
are faked, and the `data_dir` fixture points the data files at a temporary folder. Fixtures in
`tests/fixtures/` are real API responses with personal data removed.
