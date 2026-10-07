# Changelog

What changed in each version of beatcrate. The format follows [Keep a Changelog](https://keepachangelog.com/)
and versions follow [Semantic Versioning](https://semver.org/). The version lives in `pyproject.toml`.

## 2.13.0 — 2026-10-07

### Added

- A Help slide on how beatcrate picks: it reads all your purchases and playlists with no date limit (newer ones and
  purchases count more), then scores only the releases of the chosen period and skips what you already have.

## 2.12.0 — 2026-10-07

### Added

- A message when a selection is ready: the new selection opens with "Selection created successfully · N tracks".
- A bin on each selection in the sidebar (shown on hover or focus) to delete it, besides the one by its title.
- A Help button (?) beside the app's name in the sidebar; it replaces the Help link at the bottom.

### Changed

- While a selection is being made, the whole window waits under the progress card: no switching selections or
  other actions until it ends.
- The sidebar no longer shows an "In progress…" row.
- The Help slides use Material icons, and the Help window keeps the same size on every slide.

## 2.11.0 — 2026-10-07

### Added

- Delete a selection with the bin next to its title. It goes to the Trash with its stars and the record of its
  playlists; the playlists stay on Beatport and its tracks may show up again in new selections.
- A Help slide on deleting selections.

### Changed

- The sidebar's "In progress…" row is tinted, its icon spins and it shows the same percentage and bar as the card.
- The Help slide on making a selection mentions the progress card.

## 2.10.1 — 2026-10-07

### Changed

- The selection progress is now a centred card over the list instead of taking the whole window: the bar moves on
  little by little with its percentage, and the phases are a vertical list with a check, a spinner or an empty ring.

## 2.10.0 — 2026-10-06

### Changed

- While a selection is being made, the progress now takes over the whole window: the record spins in the centre with the step, the bar and the three phases below it, instead of a card at the top of the list.

## 2.9.0 — 2026-10-06

### Added

- A Help section: graphical slides explaining how the app works. They open automatically on first launch and can be reopened anytime from the Help button in the sidebar.

## 2.8.1 — 2026-10-06

### Added

- A "Checking the Beatport session…" overlay while the Check button runs. The create / save / check overlays
  now share one element whose message the page sets per action.

### Changed

- The playlist-check message now reads "Reading playlist from Beatport…" instead of "Checking it on Beatport…".
- The session row (status icon, message and Check button) now lines up at the same height.

## 2.8.0 — 2026-10-06

### Added

- A centred overlay while an action writes to Beatport: "Creating the playlist on Beatport…" when a playlist is created and "Saving the changes on Beatport…" when playlist edits are saved.

## 2.7.1 — 2026-10-06

### Changed

- The preview player now sits inside the playing track's card, below its content, not as a separate strip.

## 2.7.0 — 2026-10-06

### Changed

- The preview player now opens under the track being played, instead of a fixed card at the bottom.

## 2.6.0 — 2026-10-06

### Added

- A centred loading overlay while a playlist is checked on Beatport, over the (disabled) editor.

## 2.5.0 — 2026-10-06

### Changed

- Night mode only: the app is always dark, regardless of the Mac's appearance.

## 2.4.0 — 2026-10-06

### Added

- `STYLE.md`: the page's style guide (colour tokens in both schemes, type scale, spacing, icons, components).

### Changed

- New app icon: a close-up of a record's grooves, blue on navy with an amber label, on the macOS icon grid.
- The sidebar shows the new app icon next to the name.
- The accent blue now matches the logo (`#0B5FB8`).
- The first-run empty state shows the app icon in place of the old line drawing.

## 2.3.1 — 2026-10-02

### Fixed

- The selected row in the sidebar (a selection or a playlist) keeps its highlight when the pointer is over
  it.

## 2.3.0 — 2026-10-02

### Changed

- Redesigned interface: a source-list sidebar, a toolbar, tracks with the play button on the cover and
  BPM / key chips, a progress panel, the player as a card and an empty state for the first run.
- The page uses the Mac's system font and follows its light or dark appearance.
- Icons are drawn inline as SVG; the Material Symbols font is gone.

### Fixed

- The "in playlist" tag also shows on tracks without pick reasons.
- Rows and the sidebar shrink properly in narrow windows.

## 2.2.1 — 2026-10-01

### Fixed

- Opening a playlist checks it on Beatport first: a name changed there, tracks added there (listed with
  their title and removable) and deletions are picked up.
- A playlist deleted on Beatport is struck through and can be removed from the list.
- Renaming compares with the playlist's name on Beatport, so a name can be set back.

## 2.2.0 — 2026-10-01

### Added

- Edit the playlists beatcrate created: rename them, remove tracks and add tracks of their selection
  (starred first), all saved together.

### Changed

- The permission notice says beatcrate also edits its own playlists, and is asked again.

## 2.1.0 — 2026-10-01

### Added

- Icons on every action.

### Removed

- The Buy button: beatcrate is about making playlists.

## 2.0.0 — 2026-10-01

### Changed

- beatcrate runs in a window of its own (WebKit) instead of a browser tab.
- The Beatport session is read in beatcrate's own windows: a visible one to sign in, which closes by
  itself, and a hidden one for a fresh token.
- The app quits when its window closes and asks first while a selection, a session check or a playlist is
  under way.
- The permission notice is reworded for the new windows and asked again.

### Removed

- Google Chrome and Playwright are no longer needed.
- The background heartbeat, the auto-quit after closing the tab and the "I've signed in" step.

## 1.1.0 — 2026-10-01

### Added

- A notice before the first action that opens Chrome, explaining what is read and asking for permission;
  it can be withdrawn from the sidebar.

## 1.0.0 — 2026-10-01

### Added

- Selections of 50 Beatport new releases for a chosen period, picked from a taste profile built from your
  purchases and playlists, each with its pick reasons and a preview.
- Stars and private Beatport playlists made from them, with a genre filter.
- English and Spanish interface.
- A Mac app delivered as a DMG.
