# beatcrate

A Mac app that picks 50 Beatport new releases for your taste, based on your purchases and playlists,
each with the reason it was picked and a preview. The tracks you like (★) become private playlists in
your Beatport account.

The app speaks English and Spanish. How it works inside: [ARCHITECTURE.md](ARCHITECTURE.md); how it looks: [STYLE.md](STYLE.md). What changed
in each version: [CHANGELOG.md](CHANGELOG.md).

## Requirements

- A Mac with Apple silicon (M1 or later).
- A Beatport account (email and password).

## Install

1. Open `beatcrate-<version>.dmg` and drag **beatcrate** to **Applications**.
2. Open beatcrate. The first time, macOS blocks it because it is not signed with an Apple developer
   account: go to **System Settings → Privacy & Security**, click **Open Anyway**, and open it again.

To update, replace the app with the one from the new DMG. Your data is kept.

## Use

beatcrate opens in a window of its own and quits when you close it. The first time, a few slides explain how
it works; you can reopen them anytime with **Help** in the sidebar.

1. **Allow reading your session** (the first time): before anything that reads your Beatport session,
   beatcrate explains what it does and asks for your permission. It is remembered until you click
   **Withdraw permission**.
2. **Sign in** (the first time, or when the session expires): a Beatport window opens; sign in and it
   closes by itself.
3. Choose the period (**From / To**, the last 31 days by default) and click **New selection**. It takes
   about a minute.
4. Each selection is saved with a code `YYYYMMDD_HHMMSS` and listed in the sidebar. Play the previews (▶ on
   the cover; the player with the progress bar opens under the track) and filter by genre.
5. Star (★) what you like and click **Create Beatport playlist**: it creates an **always private**
   playlist with the starred tracks in view (with a genre filter on, only those genres).
6. Click a playlist under **Playlists from this selection** to edit it: change its name, mark tracks to
   remove and tracks of the selection to add (starred ones first), then **Save changes**. Nothing changes
   on Beatport until you save. When it opens, beatcrate checks the playlist on Beatport first, so a new
   name, tracks added on beatport.com (shown with their title, and removable) and edits made there are
   kept. A playlist deleted on Beatport shows as such and can be removed from the list.

Creating and editing its own playlists is all beatcrate writes to your account. It never deletes a
playlist, never touches the others and never makes one public.

Switch the language with **ES / EN** in the sidebar. Closing the window while a selection is being made
asks first, because it would stop it.

## How it picks

- **Your profile:** labels, artists, genres, BPM and key from your purchases and playlists, with more
  weight for recent ones (18-month half-life). New playlists join the profile on the next selection.
- **Candidates in the period:** releases from your top 50 labels and top 100 artists, plus the current
  charts of your top 5 genres.
- **The 50:** each candidate is scored; what you already own and what earlier selections showed are left
  out; slots are split by genre according to your profile, with at most 3 tracks per label and 2 per
  artist.

## Data

- `~/Library/Application Support/beatcrate/`: your library and profile, the selections (`crates/`), your
  stars and playlists (`marks/`), the last token (`session.json`) and your permission (`consent.json`).
- beatcrate's own website data, where Beatport keeps your session: `~/Library/WebKit/com.beatcrate.app`
  and `~/Library/HTTPStorages/com.beatcrate.app*`. It is not shared with Safari or other browsers.
- The app log: `~/Library/Logs/beatcrate.log`.

To uninstall, delete the app and those folders.

## Troubleshooting

- **"Beatport session expired":** click **Sign in**.
- **"beatcrate needs your permission to read your Beatport session":** click the action again and accept
  the notice.
- **Nothing opens:** look at `~/Library/Logs/beatcrate.log` (for example, another program using port
  8765).

beatcrate uses Beatport's unofficial API with your own session, for personal use. If Beatport changes
it, beatcrate may stop working.

## Development

Needs Python 3.13 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,build]'
.venv/bin/python -m pytest
```

- `BEATCRATE_DATA=/some/folder` keeps the data out of Application Support.
- `.venv/bin/beatcrate app` runs the app from source; `login`, `ingest` and `generate` also work from the
  terminal. Run from source, the website data belongs to Python (`org.python.python`), so it needs its own
  sign-in.
- `./scripts/build_dmg.sh` builds `dist/beatcrate-<version>.dmg`; the version comes from
  `pyproject.toml`. `scripts/make_icon.py` regenerates the icon.
- Changes go under **Unreleased** in `CHANGELOG.md`; a release turns that section into the new version
  with its date, together with the version in `pyproject.toml`.
