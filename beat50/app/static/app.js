// beat50/app/static/app.js — actions, consent, progress, genre filter, stars, playlist dialog and editor, playlist
// manager, drafts, player.
const token = document.querySelector('meta[name="bc-token"]').content;
const TEXTS = JSON.parse(document.getElementById('texts').textContent);

function text(key, params) {
  return TEXTS[key].replace(/\{(\w+)\}/g, (_, k) => params[k]);
}

function post(path, body) {
  return fetch(path, {method: 'POST', body: JSON.stringify(body || {}),
                      headers: {'X-Beat50-Token': token, 'Content-Type': 'application/json'}});
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
  'save-order': (b) => '/api/my/playlist/' + b.dataset.playlist + '/order',
  'upload-draft': (b) => '/api/draft/' + b.dataset.draft + '/upload',
  'delete-draft': (b) => '/api/draft/' + b.dataset.draft + '/delete',
};

// Actions that read the Beatport session: the first time, the user has to accept.
const SESSION_ACTIONS = new Set(['generate', 'check', 'login-start', 'playlist', 'save-playlist', 'my-load',
                                 'save-order', 'upload-draft']);
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
const LOCKABLE = '[data-action], button.toggle, #pl-name, button.handle, [data-sort], [data-order-reset], ' +
                 '[data-draft-remove], #draft-name';

// Actions that talk to Beatport show a centred overlay while they run; the message depends on the action.
const LOADING_TEXT = {'playlist': 'creating', 'save-playlist': 'saving', 'check': 'checking', 'save-order': 'saving',
                      'upload-draft': 'creating'};

// `next`: where to go once it worked, when the server does not say (by default, reload the page).
async function act(button, body, next) {
  const locked = [...document.querySelectorAll(LOCKABLE)].filter((el) => !el.disabled);
  locked.forEach((el) => { el.disabled = true; });
  const key = body && body.into ? 'adding' : LOADING_TEXT[button.dataset.action];
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
    if (button.dataset.action === 'save-playlist' || button.dataset.action === 'save-order') {
      locked.forEach((el) => { el.disabled = false; });  // keep what the user marked, so they can try again
      return button.dataset.action === 'save-order' ? updateOrder() : updateSave();
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
  document.querySelector('[data-draft-stars]').disabled = n === 0;
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

// Playlist dialog: a new private playlist (its name) or one of the user's own, listed from Beatport the first time
// that tab opens. The server leaves out the tracks already in it.
const plDialog = document.getElementById('pl-dialog');
let plMode = 'new';
let plInto = null;
let plListed = false;
const plSearch = document.getElementById('pl-search');

// For matching names: lower case and without accents, so "tecno" or "PEAK" find "Peak Técno".
const plain = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

// Shows only the playlists whose name has every word typed. A chosen one that gets hidden is unchosen, so the
// tracks never go to a playlist out of sight.
function filterPlaylists() {
  const words = plain(plSearch.value).split(/\s+/).filter(Boolean);
  let shown = 0;
  document.querySelectorAll('#pl-list li').forEach((li) => {
    const name = plain(li.querySelector('.pl-n').textContent);
    li.hidden = !words.every((w) => name.includes(w));
    if (!li.hidden) shown += 1;
    if (li.hidden && li.querySelector('[aria-pressed="true"]')) {
      li.querySelector('[data-into]').setAttribute('aria-pressed', 'false');
      plInto = null;
    }
  });
  const status = document.getElementById('pl-list-status');
  status.textContent = shown || !document.querySelector('#pl-list li') ? '' : text('pl_no_match', {q: tidy(plSearch.value)});
  updatePlaylistOk();
}

function setPlaylistMode(mode) {
  plMode = mode;
  plDialog.querySelectorAll('[data-pl-mode]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.plMode === mode)));
  plDialog.querySelectorAll('[data-pl-pane]').forEach((p) => { p.hidden = p.dataset.plPane !== mode; });
  plDialog.querySelector('[data-pl-ok]').textContent = TEXTS[mode === 'new' ? 'pl_ok_new' : 'pl_ok_into'];
  if (mode === 'into' && !plListed) listPlaylists();
  updatePlaylistOk();
}

function updatePlaylistOk() {
  const ok = plDialog.querySelector('[data-pl-ok]');
  ok.disabled = plMode === 'new' ? !tidy(document.getElementById('pl-new-name').value) : plInto === null;
}

async function listPlaylists() {
  const status = document.getElementById('pl-list-status');
  const list = document.getElementById('pl-list');
  status.textContent = TEXTS.pl_listing;
  list.replaceChildren();
  let r;
  try {
    r = await post('/api/playlists');
  } catch (e) {
    plDialog.close();
    return closed();
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    status.textContent = data.error || text('js_error', {status: r.status});
    return;
  }
  plListed = true;
  status.textContent = data.playlists.length ? '' : TEXTS.pl_none;
  plSearch.closest('label').hidden = !data.playlists.length;
  data.playlists.forEach((pl) => {  // built with textContent: names come from Beatport
    const b = document.createElement('button');
    b.dataset.into = pl.id;
    b.setAttribute('aria-pressed', 'false');
    b.disabled = pl.is_public;
    const n = document.createElement('span');
    n.className = 'pl-n';
    n.textContent = pl.name;
    const count = document.createElement('small');
    count.textContent = pl.track_count;
    b.append(n, count);
    if (pl.is_public) {
      const pub = document.createElement('span');
      pub.className = 'pl-pub';
      pub.textContent = TEXTS.pl_public;
      b.append(pub);
    }
    const li = document.createElement('li');
    li.append(b);
    list.append(li);
  });
  if (data.playlists.length) {
    filterPlaylists();  // what was typed while the list was loading
    plSearch.focus();
  }
}

function openPlaylistDialog(button) {
  plInto = null;
  plListed = false;
  plSearch.value = '';
  plSearch.closest('label').hidden = true;
  document.getElementById('pl-new-name').value = button.dataset.suggested;
  setPlaylistMode('new');
  plDialog.showModal();
}

if (plDialog) {
  plDialog.addEventListener('click', (e) => {
    const mode = e.target.closest('[data-pl-mode]');
    if (mode) return setPlaylistMode(mode.dataset.plMode);
    const pick = e.target.closest('[data-into]');
    if (pick) {
      plInto = Number(pick.dataset.into);
      plDialog.querySelectorAll('[data-into]').forEach((b) => b.setAttribute('aria-pressed', String(b === pick)));
      return updatePlaylistOk();
    }
    if (e.target.closest('[data-pl-cancel]')) return plDialog.close();
    if (!e.target.closest('[data-pl-ok]')) return;
    const genres = filter.size ? [...filter] : undefined;
    const body = plMode === 'new' ? {name: document.getElementById('pl-new-name').value, genres} : {into: plInto, genres};
    plDialog.close();
    act(document.querySelector('[data-action="playlist"]'), body);
  });
  document.getElementById('pl-new-name').addEventListener('input', updatePlaylistOk);
  plSearch.addEventListener('input', filterPlaylists);
  plSearch.addEventListener('keydown', (e) => {  // Enter picks the only playlist left that can be chosen
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const left = [...document.querySelectorAll('#pl-list li:not([hidden]) [data-into]:not(:disabled)')];
    if (left.length === 1) left[0].click();
  });
  document.getElementById('pl-new-name').addEventListener('keydown', (e) => {
    const ok = plDialog.querySelector('[data-pl-ok]');
    if (e.key === 'Enter' && !ok.disabled) ok.click();
  });
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

// Playlist manager: the user's playlists and each one's tracks come from Beatport, so the page asks the server for
// them (after consent) and shows the HTML it answers. In a private playlist of the user's the tracks can be dragged,
// moved with ↑ ↓ on their handle or sorted by BPM or key; "Save order" sends the whole order at once.
const my = document.getElementById('my');
const draftList = document.querySelector('#order[data-draft]');
let baseline = [];

const order = () => [...document.querySelectorAll('#order > li')].map((li) => Number(li.dataset.item));

function updateOrder() {
  if (draftList) return saveDraft();  // a draft has no "Save": every change is kept at once
  const changed = order().join() !== baseline.join();
  const save = document.querySelector('[data-action="save-order"]');
  if (save) save.disabled = !changed;
  const reset = document.querySelector('[data-order-reset]');
  if (reset) reset.disabled = !changed;
}

function moved() {
  document.querySelectorAll('#order > li .num').forEach((n, i) => { n.textContent = i + 1; });
  updateOrder();
}

function arrange(lis) {
  const list = document.getElementById('order');
  lis.forEach((li) => list.append(li));
  moved();
}

async function loadMy() {
  const button = my.querySelector('[data-action="my-load"]');
  if (button) button.disabled = true;
  const overlay = document.getElementById('action-loading');
  overlay.querySelector('.msg').textContent = TEXTS.my_loading;
  overlay.hidden = false;
  let r;
  try {
    r = await post(my.dataset.my === 'list' ? '/api/my/playlists' : '/api/my/playlist/' + my.dataset.my);
  } catch (e) {
    overlay.hidden = true;
    return closed();
  }
  const data = await r.json().catch(() => ({}));
  overlay.hidden = true;
  if (!r.ok) {
    if (button) button.disabled = false;
    return alert(data.error || text('js_error', {status: r.status}));
  }
  my.innerHTML = data.html;  // built by the server, which escapes everything that comes from Beatport
  document.querySelectorAll('#order[data-editable] > li').forEach((li) => { li.draggable = true; });
  baseline = order();
}

if (my && document.body.dataset.consent === '1') loadMy();

// Drafts: playlists kept on this Mac. Any track of a selection or of a playlist in the manager goes to one through
// the dialog (an existing draft, the last one used by default, or a new one by its name). On a draft's page every
// change (order, a track removed, the name) is saved at once; "Upload to Beatport" makes it a private playlist.
const draftDialog = document.getElementById('draft-dialog');
const draftName = document.getElementById('draft-name');
const draftNew = document.getElementById('draft-new-name');
let draftIds = [];

function updateDraftOk() {
  draftDialog.querySelector('[data-draft-ok]').disabled =
    !tidy(draftNew.value) && !draftDialog.querySelector('[data-draft-pick][aria-pressed="true"]');
}

function pickDraft(id) {
  draftDialog.querySelectorAll('[data-draft-pick]').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.draftPick === id));
  });
  updateDraftOk();
}

function openDraftDialog(ids) {
  draftIds = ids;
  draftNew.value = '';
  updateDraftOk();
  draftDialog.showModal();
  if (!draftDialog.querySelector('[data-draft-pick]')) draftNew.focus();
}

// The draft's row in the dialog and in the sidebar, with its new count; both are made when the draft is new.
function showDraft(d) {
  let pick = draftDialog.querySelector('[data-draft-pick="' + d.id + '"]');
  if (!pick) {  // built with textContent: the name is the user's
    pick = document.createElement('button');
    pick.dataset.draftPick = d.id;
    const n = document.createElement('span');
    n.className = 'pl-n';
    n.textContent = d.name;
    pick.append(n, document.createElement('small'));
    const li = document.createElement('li');
    li.append(pick);
    document.getElementById('draft-list').prepend(li);
    const a = document.createElement('a');
    a.className = 'pl';
    a.href = '/drafts/' + d.id;
    a.dataset.draft = d.id;
    const name = document.createElement('span');
    name.textContent = d.name;
    a.append(name, ' ', document.createElement('small'));
    const item = document.createElement('li');
    item.append(a);
    document.querySelector('.drafts ul').prepend(item);
    const none = document.querySelector('.drafts p');
    if (none) none.remove();
  }
  pick.querySelector('small').textContent = d.n;
  document.querySelector('.drafts a[data-draft="' + d.id + '"] small').textContent = d.n;
  pickDraft(d.id);
}

async function addToDraft() {
  const picked = draftDialog.querySelector('[data-draft-pick][aria-pressed="true"]');
  const body = {track_ids: draftIds};
  if (tidy(draftNew.value)) body.name = draftNew.value;
  else body.draft = picked.dataset.draftPick;
  if (my) body.playlist = Number(my.dataset.my);
  else body.selection = document.body.dataset.selection;
  draftDialog.close();
  let r;
  try {
    r = await post('/api/drafts/add', body);
  } catch (e) {
    return closed();
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) return alert(data.error || text('js_error', {status: r.status}));
  showDraft(data.draft);
  toast(data.message);
}

if (draftDialog) {
  draftDialog.addEventListener('click', (e) => {
    const pick = e.target.closest('[data-draft-pick]');
    if (pick) {
      draftNew.value = '';
      return pickDraft(pick.dataset.draftPick);
    }
    if (e.target.closest('[data-draft-cancel]')) return draftDialog.close();
    if (e.target.closest('[data-draft-ok]')) addToDraft();
  });
  draftNew.addEventListener('input', () => {  // a name typed means a new draft: no existing one stays chosen
    if (tidy(draftNew.value)) return pickDraft(null);
    updateDraftOk();
  });
  draftNew.addEventListener('keydown', (e) => {
    const ok = draftDialog.querySelector('[data-draft-ok]');
    if (e.key === 'Enter' && !ok.disabled) ok.click();
  });
  document.addEventListener('click', (e) => {
    const one = e.target.closest('[data-draft-add]');
    if (one) return openDraftDialog([Number(one.dataset.draftAdd)]);
    if (e.target.closest('[data-draft-stars]')) {
      openDraftDialog([...document.querySelectorAll('.track:not([hidden]) button.star.on')]
        .map((b) => Number(b.dataset.star)));
    }
  });
}

// Saves the draft as it is on screen; answers whether it worked. The count and the name follow in the sidebar.
async function saveDraft() {
  let r;
  try {
    r = await post('/api/draft/' + draftList.dataset.draft, {name: draftName.value, track_ids: order()});
  } catch (e) {
    closed();
    return false;
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    alert(data.error || text('js_error', {status: r.status}));
    return false;
  }
  document.getElementById('draft-detail').textContent = data.detail;
  const link = document.querySelector('.drafts a[data-draft="' + draftList.dataset.draft + '"]');
  link.querySelector('span').textContent = data.name;
  link.querySelector('small').textContent = data.n;
  document.querySelector('[data-action="upload-draft"]').disabled = data.n === 0;
  return true;
}

if (draftList && draftList.hasAttribute('data-editable')) {
  draftName.addEventListener('change', saveDraft);
  draftList.addEventListener('click', (e) => {
    const remove = e.target.closest('[data-draft-remove]');
    if (!remove) return;
    const li = remove.closest('li');
    if (li.contains(bar)) {  // the player sits in the row it plays: stop it and keep it for the next one
      player.pause();
      bar.hidden = true;
      document.querySelector('main').append(bar);
      current = null;
    }
    li.remove();
    moved();
  });
}

// Camelot keys in wheel order (1A, 1B, 2A…); a track without BPM or key goes last.
const camelot = (k) => {
  const m = /^(\d+)([AB])$/.exec(k || '');
  return m ? Number(m[1]) * 2 + (m[2] === 'B' ? 1 : 0) : Infinity;
};
const SORTS = {bpm: (li) => Number(li.dataset.bpm) || Infinity, key: (li) => camelot(li.dataset.key)};

let dragged = null;
document.addEventListener('dragstart', (e) => {
  const li = e.target.closest && e.target.closest('#order[data-editable] > li');
  if (!li) return;
  dragged = li;
  li.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', li.dataset.item);
});
document.addEventListener('dragover', (e) => {
  const li = dragged && e.target.closest && e.target.closest('#order > li');
  if (!li) return;
  e.preventDefault();
  if (li === dragged) return;
  const r = li.getBoundingClientRect();
  li.parentNode.insertBefore(dragged, e.clientY < r.top + r.height / 2 ? li : li.nextSibling);
});
document.addEventListener('drop', (e) => { if (dragged) e.preventDefault(); });
document.addEventListener('dragend', () => {
  if (!dragged) return;
  dragged.classList.remove('dragging');
  dragged = null;
  moved();
});
document.addEventListener('keydown', (e) => {
  const handle = e.target.closest && e.target.closest('#order button.handle');
  if (!handle || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
  e.preventDefault();
  const li = handle.closest('li');
  const to = e.key === 'ArrowUp' ? li.previousElementSibling : li.nextElementSibling;
  if (!to) return;
  li.parentNode.insertBefore(li, e.key === 'ArrowUp' ? to : to.nextSibling);
  handle.focus();
  moved();
});
document.addEventListener('click', (e) => {
  const sort = e.target.closest('[data-sort]');
  if (sort) {
    const by = SORTS[sort.dataset.sort];
    return arrange([...document.querySelectorAll('#order > li')].sort((a, b) => by(a) - by(b)));
  }
  if (e.target.closest('[data-order-reset]')) {
    const lis = new Map([...document.querySelectorAll('#order > li')].map((li) => [Number(li.dataset.item), li]));
    arrange(baseline.map((id) => lis.get(id)));
  }
});

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
  if (action === 'playlist') return openPlaylistDialog(button);
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
  if (action === 'my-load') return loadMy();
  if (action === 'upload-draft') {  // what is on screen is saved first, so the playlist gets this name and order
    const sure = text('js_upload_draft', {name: tidy(draftName.value), n: order().length});
    return saveDraft().then((ok) => { if (ok && confirm(sure)) act(button); });
  }
  if (action === 'delete-draft') {
    if (confirm(text('js_delete_draft', {name: button.dataset.name}))) act(button);
    return;
  }
  if (action === 'save-order') return act(button, {item_ids: order()});
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
  player.addEventListener('ended', () => {  // in the manager the previews follow the playlist's order
    if (!document.getElementById('order') || !current) return;
    let li = current.closest('.track').nextElementSibling;
    while (li && !li.querySelector('button.play[data-src]')) li = li.nextElementSibling;
    if (li) play(li.querySelector('button.play[data-src]'));
  });
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

// Genres: more or less room for each genre in the next selection. Every change is saved at once; the share each
// genre would get is estimated here the way rank.py splits the slots (among the top genres, by weight).
const genres = document.getElementById('genres');
if (genres) {
  const rows = [...genres.querySelectorAll('.gp')];
  const top = Number(genres.dataset.top);
  function prefs() {
    const levels = {};
    let only = null;
    rows.forEach((r) => {
      const level = Number(r.querySelector('.seg [aria-pressed="true"]').dataset.level);
      if (level !== 1) levels[r.dataset.genre] = level;
      if (r.querySelector('[data-only]').getAttribute('aria-pressed') === 'true') only = Number(r.dataset.genre);
    });
    return {levels, only};
  }
  function shares() {
    const p = prefs();
    const weights = rows.map((r) => {
      const m = p.only !== null ? (Number(r.dataset.genre) === p.only ? 1 : 0) : (p.levels[r.dataset.genre] ?? 1);
      return Number(r.dataset.weight) * m;
    });
    const kept = weights.map((w, i) => [w, i]).filter(([w]) => w > 0).sort((a, b) => b[0] - a[0]).slice(0, top);
    const total = kept.reduce((s, [w]) => s + w, 0);
    rows.forEach((r, i) => {
      const got = kept.find(([, k]) => k === i);
      r.querySelector('.then').textContent = Math.round(got && total ? 100 * got[0] / total : 0) + ' %';
      r.classList.toggle('off', weights[i] === 0);
    });
    const n = p.only !== null ? 1 : Object.keys(p.levels).length;
    const badge = document.querySelector('[data-genres-open] .n');  // not on the playlist editor
    if (badge) {
      badge.textContent = n;
      badge.hidden = n === 0;
    }
  }
  async function save() {
    shares();
    let r;
    try {
      r = await post('/api/genres', prefs());
    } catch (e) {
      return closed();
    }
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      alert(data.error || text('js_error', {status: r.status}));
    }
  }
  function press(group, on) {
    group.forEach((b) => b.setAttribute('aria-pressed', String(b === on)));
  }
  shares();
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-genres-open]')) return genres.showModal();
    if (e.target.closest('[data-genres-done]')) return genres.close();
    const level = e.target.closest('#genres .seg button');
    if (level) {
      press([...level.parentNode.children], level);
      return save();
    }
    const only = e.target.closest('#genres [data-only]');
    if (only) {
      const was = only.getAttribute('aria-pressed') === 'true';
      rows.forEach((r) => r.querySelector('[data-only]').setAttribute('aria-pressed', 'false'));
      only.setAttribute('aria-pressed', String(!was));
      return save();
    }
    if (e.target.closest('[data-genres-reset]')) {
      rows.forEach((r) => {
        press([...r.querySelectorAll('.seg button')], r.querySelector('.seg [data-level="1"]'));
        r.querySelector('[data-only]').setAttribute('aria-pressed', 'false');
      });
      return save();
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
