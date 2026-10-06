// beatcrate/app/static/app.js — actions, consent, progress, genre filter, stars, playlist editor and player.
const token = document.querySelector('meta[name="bc-token"]').content;
const TEXTS = JSON.parse(document.getElementById('texts').textContent);

function text(key, params) {
  return TEXTS[key].replace(/\{(\w+)\}/g, (_, k) => params[k]);
}

function post(path, body) {
  return fetch(path, {method: 'POST', body: JSON.stringify(body || {}),
                      headers: {'X-Beatcrate-Token': token, 'Content-Type': 'application/json'}});
}

// If the server is gone (the app closed), say so instead of leaving dead buttons.
function closed() {
  if (!document.getElementById('closed')) {
    const banner = document.createElement('div');
    banner.id = 'closed';
    banner.textContent = TEXTS.js_closed;
    document.body.prepend(banner);
  }
  document.querySelectorAll('[data-action]').forEach((b) => { b.disabled = true; });
}

// Language switch: remembered in a cookie the server reads.
document.querySelectorAll('[data-lang]').forEach((a) => a.addEventListener('click', (e) => {
  e.preventDefault();
  document.cookie = 'beatcrate_lang=' + a.dataset.lang + '; path=/; max-age=31536000; samesite=strict';
  location.reload();
}));

const ROUTES = {
  'generate': () => '/api/generate',
  'check': () => '/api/session/check',
  'login-start': () => '/api/login/start',
  'playlist': () => '/api/playlist/' + document.body.dataset.selection,
  'revoke': () => '/api/consent',
  'save-playlist': (b) => '/api/playlist/' + document.body.dataset.selection + '/' + b.dataset.playlist,
  'forget-playlist': (b) => ROUTES['save-playlist'](b) + '/forget',
  'delete-selection': (b) => '/api/selection/' + b.dataset.selection + '/delete',
};

// Actions that read the Beatport session: the first time, the user has to accept.
const SESSION_ACTIONS = new Set(['generate', 'check', 'login-start', 'playlist', 'save-playlist']);
const consent = document.getElementById('consent');
let afterConsent = null;

function withConsent(run) {
  if (document.body.dataset.consent === '1') return run();
  afterConsent = run;
  consent.showModal();
}

consent.addEventListener('close', () => { afterConsent = null; });
consent.querySelector('[data-consent-cancel]').addEventListener('click', () => consent.close());
consent.querySelector('[data-consent-ok]').addEventListener('click', async () => {
  const run = afterConsent;
  let r;
  try {
    r = await post('/api/consent', {on: true});
  } catch (e) {
    consent.close();
    return closed();
  }
  consent.close();
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    return alert(data.error || text('js_error', {status: r.status}));
  }
  document.body.dataset.consent = '1';
  if (run) run();
});

// While an action runs, every action button (and the playlist editor's controls) waits.
const LOCKABLE = '[data-action], button.toggle, #pl-name';

// Actions that talk to Beatport show a centred overlay while they run; the message depends on the action.
const LOADING_TEXT = {'playlist': 'creating', 'save-playlist': 'saving', 'check': 'checking'};

// `next`: where to go once it worked, when the server does not say (by default, reload the page).
async function act(button, body, next) {
  const locked = [...document.querySelectorAll(LOCKABLE)].filter((el) => !el.disabled);
  locked.forEach((el) => { el.disabled = true; });
  const key = LOADING_TEXT[button.dataset.action];
  const overlay = key ? document.getElementById('action-loading') : null;
  if (overlay) {
    overlay.querySelector('.msg').textContent = TEXTS[key] || '';
    overlay.hidden = false;
  }
  let r;
  try {
    r = await post(ROUTES[button.dataset.action](button), body);
  } catch (e) {
    return closed();
  }
  const data = await r.json().catch(() => ({}));
  if (overlay) overlay.hidden = true;
  if (!r.ok) {
    alert(data.error || text('js_error', {status: r.status}));
    if (button.dataset.action === 'save-playlist') {  // keep what the user marked, so they can try again
      locked.forEach((el) => { el.disabled = false; });
      return updateSave();
    }
  } else if (data.message) {
    alert(data.message);
  }
  if (r.ok && (data.redirect || next)) return location.assign(data.redirect || next);
  location.reload();
}

async function toggleStar(button) {
  const on = button.getAttribute('aria-pressed') !== 'true';
  let r;
  try {
    r = await post('/api/star/' + document.body.dataset.selection + '/' + button.dataset.star, {on});
  } catch (e) {
    return closed();
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) return alert(data.error || text('js_error', {status: r.status}));
  button.setAttribute('aria-pressed', String(on));
  button.classList.toggle('on', on);
  updateCreate();
}

// Genre filter: several at once; the playlist is made from the stars in view.
const filter = new Set();

function updateCreate() {
  const create = document.querySelector('[data-action="playlist"]');
  if (!create) return;
  const n = document.querySelectorAll('.track:not([hidden]) button.star.on').length;
  document.getElementById('n-star').textContent = n;
  create.disabled = n === 0;
  const base = document.body.dataset.selection.replace('-', '') + ' ';
  create.dataset.suggested = filter.size === 1 ? base + [...filter][0] : base;
}

function applyFilter() {
  document.querySelectorAll('.track').forEach((li) => {
    li.hidden = filter.size > 0 && !filter.has(li.dataset.genre);
  });
  document.querySelectorAll('.genre[data-genre]').forEach((b) => {
    b.classList.toggle('on', filter.has(b.dataset.genre));
  });
  const all = document.querySelector('.genre[data-all]');
  if (all) all.classList.toggle('on', filter.size === 0);
  updateCreate();
  history.replaceState(null, '', filter.size
    ? '#genre=' + [...filter].map(encodeURIComponent).join(',') : location.pathname);
}

if (location.hash.startsWith('#genre=')) {
  location.hash.slice('#genre='.length).split(',').forEach((g) => filter.add(decodeURIComponent(g)));
  applyFilter();
}

// Playlist editor: the remove / add buttons only mark tracks; "Save changes" sends everything at once.
const plName = document.getElementById('pl-name');
const tidy = (s) => s.trim().replace(/\s+/g, ' ');

function marked(kind) {
  return [...document.querySelectorAll('button.toggle.' + kind + '[aria-pressed="true"]')]
    .map((b) => Number(b.dataset[kind]));
}

function updateSave() {
  const save = document.querySelector('[data-action="save-playlist"]');
  const renamed = tidy(plName.value) !== tidy(plName.defaultValue);
  save.disabled = !tidy(plName.value) || !(renamed || marked('remove').length || marked('add').length);
}

if (plName) {
  plName.addEventListener('input', updateSave);
  document.addEventListener('click', (e) => {
    const toggle = e.target.closest('button.toggle');
    if (!toggle) return;
    const on = toggle.getAttribute('aria-pressed') !== 'true';
    toggle.setAttribute('aria-pressed', String(on));
    toggle.classList.toggle('on', on);
    toggle.closest('.track').classList.toggle('pending', on);
    updateSave();
  });
}

// On opening, the server checks the playlist on Beatport (renamed, tracks added there, deleted) and the page
// reloads if anything changed. Meanwhile the editor waits, so no marks are lost to that reload.
async function refreshPlaylist() {
  const save = document.querySelector('[data-action="save-playlist"]');
  const locked = [...document.querySelectorAll(LOCKABLE)].filter((el) => !el.disabled);
  locked.forEach((el) => { el.disabled = true; });
  let data = null;
  try {
    const r = await post(ROUTES['save-playlist'](save) + '/refresh');
    data = r.ok ? await r.json() : null;
  } catch (e) {
    data = null;
  }
  if (data && data.changed) return location.reload();
  locked.forEach((el) => { el.disabled = false; });
  updateSave();
  document.getElementById('syncing').hidden = true;
}

if (document.querySelector('main[data-refresh]')) refreshPlaylist();

// Progress: while a selection runs, the bar creeps on little by little and the phases follow the server; when it
// ends, reload to show it. The same when the sign-in window closes.
// Per phase: where the bar starts and where it heads (%), and the seconds to cover about two thirds of that
// stretch. It slows down as it nears the end, so it never stalls nor passes the next phase (views._PICK_FROM).
const PICK_BANDS = [[2, 35, 10], [35, 85, 20], [85, 97, 3]];
const progress = document.getElementById('progress');
let pick = progress ? {step: Number(progress.dataset.step), since: progress.dataset.since} : null;
let shown = 0;

function tickPick() {
  if (!pick || !progress) return;
  const [from, to, tau] = PICK_BANDS[Math.min(Math.max(pick.step, 1), PICK_BANDS.length) - 1];
  const t = Math.max(0, (Date.now() - Date.parse(pick.since)) / 1000) || 0;
  shown = Math.max(shown, from + (to - from) * (1 - Math.exp(-t / tau)));  // never backwards
  progress.querySelector('.prog i').style.width = shown.toFixed(1) + '%';
  progress.querySelector('.pct').textContent = Math.floor(shown) + '%';
}

if (progress) {
  tickPick();
  setInterval(tickPick, 250);
}

let running = document.body.dataset.running === '1';
async function poll() {
  const st = await fetch('/api/state').then((r) => r.json()).catch(() => null);
  if (!st) return closed();
  if (document.body.dataset.login === '1' && !st.login_pending) return location.reload();
  if (st.running) {
    if (!progress) return location.reload();
    running = true;
    pick = {step: st.running.step, since: st.running.since};
    const phase = TEXTS['phase_' + st.running.phase] || '';
    progress.querySelector('.step').textContent = text('making', {step: st.running.step, of: st.running.of, phase});
    progress.querySelectorAll('.phases li').forEach((li, i) => {
      li.className = i + 1 < st.running.step ? 'done' : i + 1 === st.running.step ? 'now' : 'next';
    });
  } else if (running) {
    // Done: open the new selection with a message; if it failed, the reloaded sidebar says why.
    const last = st.last_run || {};
    if (last.ok && last.id) return location.assign('/crate/' + encodeURIComponent(last.id) + '?created=1');
    location.reload();
  }
}
setInterval(poll, 2000);

// "Selection created": shown once on arriving at the new selection, then the address loses its ?created=1.
function toast(message) {
  const el = document.getElementById('toast');
  el.querySelector('.msg').textContent = message;
  el.classList.remove('out');
  el.hidden = false;
  setTimeout(() => el.classList.add('out'), 4000);
  setTimeout(() => { el.hidden = true; }, 4400);
}

if (new URLSearchParams(location.search).has('created')) {
  toast(text('created', {n: document.querySelectorAll('.track').length}));
  history.replaceState(null, '', location.pathname + location.hash);
}

// Player: one preview at a time, with the fixed progress bar at the bottom.
const player = document.getElementById('player');
const bar = document.getElementById('player-bar');
let current = null;

function mmss(s) {
  if (!isFinite(s)) return '0:00';
  return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
}

// The play buttons hold an SVG icon from the page's sprite; pointing the <use> at another symbol swaps the glyph.
function setIcon(button, name) {
  button.querySelector('use').setAttribute('href', '#i-' + name);
}

function mark(playing) {
  if (current) {
    setIcon(current, playing ? 'pause' : 'play_arrow');
    current.closest('.track').classList.toggle('playing', playing);
  }
}

function play(button) {
  if (current) {
    setIcon(current, 'play_arrow');
    current.closest('.track').classList.remove('playing');
  }
  current = button;
  player.src = button.dataset.src;
  button.closest('.track').appendChild(bar);  // the player sits inside the card of the row it plays
  bar.hidden = false;
  player.play().catch(() => mark(false));
}

function run(button) {
  const action = button.dataset.action;
  if (action === 'playlist') {
    const name = prompt(TEXTS.js_prompt, button.dataset.suggested);
    if (name !== null) act(button, {name, genres: filter.size ? [...filter] : undefined});
    return;
  }
  if (action === 'generate') {
    return act(button, {since: document.getElementById('since').value,
                        until: document.getElementById('until').value});
  }
  if (action === 'revoke') return act(button, {on: false});
  if (action === 'delete-selection') {
    // Deleting the selection on screen goes home (the newest one left); any other just reloads this page.
    const home = button.dataset.selection === document.body.dataset.selection ? '/' : null;
    if (confirm(text('js_delete', {name: button.dataset.name}))) act(button, undefined, home);
    return;
  }
  if (action === 'save-playlist') {
    return act(button, {name: document.getElementById('pl-name').value, remove: marked('remove'),
                        add: marked('add')});
  }
  return act(button);
}

document.addEventListener('click', (e) => {
  const button = e.target.closest('[data-action]');
  if (button && SESSION_ACTIONS.has(button.dataset.action)) return withConsent(() => run(button));
  if (button) return run(button);
  const genre = e.target.closest('button.genre');
  if (genre) {
    if (genre.hasAttribute('data-all')) filter.clear();
    else if (filter.has(genre.dataset.genre)) filter.delete(genre.dataset.genre);
    else filter.add(genre.dataset.genre);
    return applyFilter();
  }
  const star = e.target.closest('button.star');
  if (star) return toggleStar(star);
  const preview = e.target.closest('button.play[data-src]');
  if (!preview || !player) return;
  if (current === preview) return player.paused ? player.play() : player.pause();
  play(preview);
});

if (player) {
  player.addEventListener('play', () => mark(true));
  player.addEventListener('pause', () => mark(false));
  player.addEventListener('timeupdate', () => {
    const d = player.duration;
    document.querySelector('#player-seek i').style.width =
      (isFinite(d) && d > 0 ? 100 * player.currentTime / d : 0) + '%';
    document.getElementById('player-time').textContent = mmss(player.currentTime) + ' / ' + mmss(d);
  });
  document.getElementById('player-seek').addEventListener('click', (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    if (isFinite(player.duration)) {
      player.currentTime = player.duration * Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    }
  });
}

// Help: graphical onboarding slides. Auto-opens on first launch (then marks itself seen) and reopens on Help.
const help = document.getElementById('help');
if (help) {
  const slides = [...help.querySelectorAll('.help-slide')];
  const dots = [...help.querySelectorAll('.help-dots .dot')];
  let at = 0;
  function showHelp(i) {
    at = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((s, k) => { s.hidden = k !== at; });
    dots.forEach((d, k) => d.classList.toggle('on', k === at));
    help.querySelector('[data-help-prev]').hidden = at === 0;
    const last = at === slides.length - 1;
    help.querySelector('[data-help-next]').hidden = last;
    help.querySelector('[data-help-done]').hidden = !last;
  }
  function openHelp() { showHelp(0); help.showModal(); }
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-help-open]')) { e.preventDefault(); return openHelp(); }
    if (e.target.closest('[data-help-prev]')) return showHelp(at - 1);
    if (e.target.closest('[data-help-next]')) return showHelp(at + 1);
    if (e.target.closest('[data-help-done]')) return help.close();
    const dot = e.target.closest('.help-dots .dot');
    if (dot) return showHelp(Number(dot.dataset.helpGo));
  });
  if (document.body.dataset.help === '1') { openHelp(); post('/api/help-seen').catch(() => {}); }
}
