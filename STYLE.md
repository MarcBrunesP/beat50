---
title: STYLE
type: note
permalink: marc-vps/beat50/style
---

# beat50 style

The look of the app's page, as `app/static/app.css` implements it. [ARCHITECTURE.md](ARCHITECTURE.md) says how the app works;
this file says how it looks and which rules a new element follows. Every value below is the one in the stylesheet:
change both together.

## Principles

- A Mac window, not a website: the system font, a source-list sidebar, a toolbar, native-looking controls, and the
  a permanent night mode (`color-scheme: dark`), regardless of the Mac's appearance.
- One accent (blue) for selection and the primary action, amber for stars, green for add, red for remove and errors.
  Nothing else is coloured. Green and red never carry meaning alone: they come with an icon (+ / −) and a label.
- Text contrast is AA (4.5:1) on its background in both schemes; icons and controls at least 3:1.
- Every control is a real `<button>`, `<a href>` or `<input>` with a `<label>`. Icon-only buttons carry `aria-label`.
  Toggles carry `aria-pressed`. Nothing is clickable that the Tab key cannot reach.
- Long data (artists, remix names, labels, playlist names) ellipsizes; nothing wraps a row or scrolls the page sideways.

## Colour tokens

The app is night mode only: `:root` carries the Dark column below and `color-scheme: dark`, regardless of the
Mac's appearance. The Light column is kept for reference; it is not in the stylesheet.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | #FFFFFF | #121214 | page |
| `--side` | #F5F5F7 | #1C1C1E | sidebar, notices |
| `--raised` | #FFFFFF | #1F1F22 | cards, inputs, secondary buttons, the dialog, the player |
| `--hover` | #F5F5F7 | #1A1A1E | row hover |
| `--chip` | #F0F0F3 | #2A2A2F | BPM / key chips, cover placeholder, star hover |
| `--line` | #E3E3E8 | #2C2C30 | dividers, progress track, sidebar hover, segmented control |
| `--line-soft` | #EFEFF2 | #1F1F23 | row dividers |
| `--border` | #D6D6DB | #3A3A40 | control borders |
| `--text` | #1D1D1F | #F2F2F4 | text |
| `--soft` | #5C5C61 | #A8A8AE | secondary text (meta, mix, reasons) |
| `--faint` | #6E6E73 | #A8A8AE | section headers, numbers, unstarred star |
| `--off` | #A1A1A6 | #6E6E76 | the "not checked" status dot |
| `--accent` | #0B5FB8 | #0B5FB8 | selected rows, primary button, chip on, progress fill (white text on it); the logo's blue |
| `--accent-ink` | #FFFFFF | #FFFFFF | text on accent |
| `--accent-soft` | #EEF4FC | #17213A | playing row, dialog icon tile |
| `--accent-text` | #0B5FB8 | #8FC1FF | accent used as text: working status, playing title, syncing notice |
| `--tag` / `--tag-ink` | #E6F0FB / #0B4F9C | #0F2B4A / #8FC1FF | "in <playlist>" tag |
| `--star` | #C77700 | #F0B12E | starred |
| `--star-soft` / `--star-ink` | #FFF3D6 / #8A5A00 | #3D2E0A / #F0B12E | the star counter badge |
| `--green` / `--green-soft` | #1E7A3A / #E3F3E7 | #2E9E52 / #15301D | session ok, add toggle on, done phase, row to add |
| `--red` / `--red-soft` | #C8321F / #FBE9E7 | #CF3F30 / #3A1A16 | session expired, sign-in button, remove toggle on, errors |
| `--shadow` | rgba(0,0,0,.12) | rgba(0,0,0,.45) | card and dialog shadows |
| `--overlay` | rgba(0,0,0,.45) | rgba(0,0,0,.5) | the play button over a cover |

Rule of thumb: `--accent` is a fill with white text; as text it is `--accent-text`. Date inputs declare
`color-scheme: dark` so the native picker matches.

## Typography

System stack: `-apple-system, "SF Pro Text", "Helvetica Neue", system-ui, sans-serif`, 13 px / 1.4, antialiased.

| Size / weight | Where |
|---|---|
| 20 / 700, −0.2 px | empty-state title |
| 17 / 700 | dialog title |
| 15 / 700, −0.2 px | brand |
| 15 / 600 | toolbar title, playlist name input |
| 14 / 600 | track name |
| 14 / 400 | empty-state paragraph |
| 13 / 400–600 | body, artists, buttons (600 on primary) |
| 12 / 400 | mix name, meta in the sidebar foot, chips in the filter row, notices, phases |
| 11 / 600 uppercase, +0.4 px | section headers (sidebar and editor) |
| 11 / 400 | reason line, meta chips, dates, counters |

Numbers that line up (BPM, keys, counts, times) use `font-variant-numeric: tabular-nums`.

## Spacing and shape

- Sidebar 240 px; main column padding 20 px; toolbar 52 px; filter row 48 px; track row 72 px.
- Gaps: 14 px between row parts, 12 px in toolbars, 6–8 px between controls and chips, 2 px between sidebar rows.
- Radii: 12–14 px cards and the dialog, 8 px buttons and inputs, 7 px sidebar rows and segmented control, 6 px covers,
  5 px chips, full round for pills, toggles and play.
- Shadows only on floating things: the loading box (`0 8px 24px`), the dialog and the picking card (`0 16px 40px`), the segmented control's
  selected segment (`0 1px 2px`).

## Icons

Inline SVG from the page's sprite (`views.ICONS`): a 24 px grid, 2 px stroke, round caps and joins, `fill: none`.
Default size 18 px; 22 px for play/pause and the star; 16 px in toggles; 14 px for the session dot; 12 px in the
reason line and small buttons; 40 px in a tinted tile for the dialog.

The brand mark (`views.BRAND_MARK`) is the app icon itself, in its own colours in both schemes: 22 px in the
sidebar, 88 px in the empty state.

Filled shapes are the exception and say so in the drawing (play, pause) or in a rule (`.star.on .icon`,
`.count .icon`). An icon never stands alone: a label beside it, or `aria-label` on its button. The moving
icon is the `sync` glyph in the loading overlay, which spins (stopped under `prefers-reduced-motion`).

The help slides are the exception to the sprite: they use Material Symbols (Outlined, Apache 2.0) from
`views.MATERIAL`, filled paths on Google's `0 -960 960 960` grid — a 72 px main icon in `--accent-text`, a 44 px
second one in `--star` and, between them when the slide is a step, a 26 px `--faint` arrow.

## Components

- **Brand** (`.brand`): the 22 px app icon, the name, and on the right a 26 px icon-only Help button (`help` glyph,
  `--soft`, `--line` on hover) that opens the help slides.
- **Sidebar rows** (`.sel`, `.pl`): 32 px, radius 7, name left and count right; hover `--line` except on the selected
  row, which stays `--accent` with white text. A deleted playlist is struck through (the name only, not its tag).
  Each selection row (`.sel-row`) has a 24 px bin (`.sel-del`) that replaces the count on hover or keyboard focus;
  it turns red on a `--chip` tile when pointed at, and is hidden while beat50 is busy.
- **Session foot**: dot-style icon (green / red / grey) + text + a 24 px "Check" button; the sign-in button is red and
  full width; language switch is a segmented control; "Withdraw permission" is an underlined link.
- **Toolbar**: title + one-line detail on the left (on a selection, a 30 px bordered bin button beside it that
  turns red on hover, to delete it), the period group (one bordered box with two date inputs), the secondary
  **Genres** button (`tune` icon; an 18 px `--tag` pill with how many genres are adjusted, hidden at zero) and the
  primary button on the right. The editor's toolbar swaps them for back, name input, "Private on Beatport" and Save.
- **Buttons**: primary `.main` 30 px, accent fill, white 600 text; secondary `.create` 30 px, bordered, raised fill;
  small `.small` 24 px; destructive `.warn` red; link `.link`. Disabled is 45 % opacity.
- **Filter chips** (`.genre`): 26 px pills, bordered; on = accent fill. Counts in `<small>`.
- **Track row**: number · cover with the play button over it (shown on hover, focus and while playing) · name + mix,
  artists, "Picked for …" line with the sparkle icon and the optional "in <playlist>" tag · genre, label, BPM chip,
  key chip, date · 36 px star. Playing row: `--accent-soft` background and the name in `--accent-text`. Below
  1100 px the genre name is dropped from the row (it is already in the filter row).
- **Editor toggles**: 32 px circles; on = red (remove) or green (add) fill with white icon. A row marked to remove
  dims to 60 % and strikes the name; a row marked to add tints `--green-soft`.
- **Picking card** (`#picking` › `#progress`): while a selection runs, an `--overlay` scrim over the whole window
  (the app underneath is `inert`: no navigating or other actions until it ends) with a centred 380 px raised card,
  radius 14, dialog shadow:
  the record (`PICK_DISC`, 52 px) spinning next to the 14 / 600 step line; a 6 px bar with its percentage, which
  app.js moves little by little inside each phase's stretch (`PICK_BANDS`, never backwards); and, under a `--line`
  divider, the three phases as a vertical stepper with 18 px markers — done: green disc with a white check; now:
  a spinning `--accent-text` ring and the label in `--text` 600; next: an empty `--border` ring. The spins stop
  under `prefers-reduced-motion`.
- **Empty state**: the 88 px app icon, 20 px title, one paragraph, three numbered steps.
- **Consent sheet**: 520 px dialog, radius 14, accent icon tile, four points each with an icon, buttons right-aligned.
- **Genres** (`#genres`): a 600 px dialog like the consent sheet (accent icon tile, hint line). One 32 px row per
  genre: the name, its share of the slots "now → with the choices" (the second in `--text` 600), a segmented
  control (`.seg`, the language switch's style: `--line` track, raised pressed segment) with Off · − · = · + · ++,
  and a 24 px bordered **Only** button that fills `--accent` when on. A switched-off genre dims its name to `--off`.
  Reset sits left, Done right.
- **Help** (`#help`): the onboarding, a 460 px dialog with seven slides — Material icons on a 132 px `--side` tile, a
  title and a line of text — plus dots and Back / Next / Got it. All slides share one grid cell (the hidden ones
  invisible), so the dialog always has the tallest slide's size and never jumps. It auto-opens on first launch
  (then `/api/help-seen` records it) and reopens from the Help button beside the app's name.
- **Toast** (`#toast`): a raised box with a 1 px `--line` border and the loading box's shadow, centred at the
  bottom of the content column: a green `check_circle` and a 13 / 500 message. It slides in, stays 4 s and fades
  out; app.js shows "Selection created successfully · N tracks" on arriving at a new selection.
- **Player** (`#player-bar`): the page moves it into the playing row's card, on its own full-width line below
  the track's content (a `--line` divider above it) — the progress bar (click to seek) and the time, nothing
  else. Play / pause is the ▶ on the row's cover; the whole card stays highlighted.
- **Loading overlay** (`.loading`): a fixed `--overlay` scrim over the content column (`left: 240px`, the
  sidebar stays usable) with a centred raised box: the `sync` icon spinning and a status text, the controls
  underneath disabled meanwhile. `#syncing` (server-shown) covers the editor's playlist check; `#action-loading`
  is one element per page whose `.msg` the JS sets per Beatport action — creating a playlist, saving changes,
  or checking the session.

## Adding something new

1. Pick existing tokens; add a token only if both schemes need a new role, and add it to both blocks.
2. Reuse a component's sizes (30 px buttons, 26 px chips, 32 px rows) before inventing a size.
3. Put the markup in `app/views.py` with its text in `app/i18n.py` (en and es), the icon in `views.ICONS`, and the
   rule in `app/static/app.css`; no inline styles.
4. Check it in both schemes and at 960 px wide: nothing clipped without an ellipsis, nothing scrolling sideways.