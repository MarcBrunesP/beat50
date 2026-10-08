"""The app's texts in Spanish and English, and how dates, reasons and errors are written in each.

The language comes from the `beatcrate_lang` cookie (the ES / EN switch) or else from the browser:
Spanish if it prefers Spanish, English otherwise.
"""
import re
from datetime import date, datetime

LANGS = ("en", "es")
COOKIE = "beatcrate_lang"  # named before 3.0 (beatcrate); kept so the choice survives the rename
CODE = re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})\d{2}$")

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"],
}

TEXTS = {
    "en": {
        "session_active": "Beatport session active",
        "session_expired": "Beatport session expired",
        "session_unchecked": "Session not checked",
        "last_ok": "Last selection: {when} ✓",
        "last_failed": "Last selection: {when} ✗",
        "making": "Making a selection… {step}/{of} · {phase}",
        "phase_library": "reading your library",
        "phase_discover": "looking for new releases",
        "phase_rank": "picking the 50",
        "since": "From",
        "until": "To",
        "new_selection": "New selection",
        "check_session": "Check",
        "help_open": "Help",
        "help_title": "How beat50 works",
        "help_prev": "Back",
        "help_next": "Next",
        "help_done": "Got it",
        "help_s1_t": "50 new releases, for your taste",
        "help_s1_b": "beat50 reads your Beatport purchases and playlists and picks 50 new tracks you are likely to want.",
        "help_s2_t": "Permission and sign in",
        "help_s2_b": "The first time, beat50 asks permission to read your Beatport session and opens a window to sign in. Nothing is shared.",
        "help_s3_t": "Make a selection",
        "help_s3_b": "Choose a period and click New selection. A card shows how it goes, step by step; in about a minute you get 50 tracks, each with the reason it was picked.",
        "help_s4_t": "How it picks",
        "help_s4_b": "Your taste comes from all your purchases and playlists, with no date limit: the newer, the more "
                     "they count (half every {months} months), and purchases more than playlists. Then it scores the "
                     "releases of the chosen period (the last {days} days by default, up to a year) by label, artist, "
                     "genre, BPM and key, and skips what you already have or were already shown. With Genres you "
                     "give each genre more or less room, or keep only one.",
        "genres_open": "Genres",
        "genres_title": "Genres of the next selection",
        "genres_hint": "Give each genre more or less room. The share is an estimate of the 50 slots; “Only” leaves "
                       "the others out, and the selection may then be shorter.",
        "genres_none": "Your genres appear here after your first selection.",
        "genre_level_0": "Off",
        "genre_only": "Only",
        "genres_reset": "Reset",
        "genres_done": "Done",
        "only_genre": "only {name}",
        "genre_off": "{name} off",
        "help_s5_t": "Listen and star",
        "help_s5_b": "Play the previews (▶) and star (★) the ones you like. Filter by genre to focus.",
        "help_s6_t": "Create a private playlist",
        "help_s6_b": "Turn your starred tracks into an always-private Beatport playlist, and edit it whenever you want.",
        "help_s7_t": "Tidy up your selections",
        "help_s7_b": "Delete a selection you no longer need with its bin, in the sidebar or next to its title. It goes to the Trash, its playlists stay on Beatport and its tracks may come back in new selections.",
        "login": "Sign in",
        "login_hint": "Sign in to Beatport in the window that opened. It closes by itself once you are in.",
        "playlists_here": "Playlists from this selection",
        "empty": "Click “New selection”: beat50 reads your Beatport purchases and playlists and picks 50 new "
                 "releases of the period, each with its reason.",
        "empty_title": "No selections yet",
        "step_consent": "Allow reading your session",
        "step_login": "Sign in to Beatport",
        "step_wait": "About a minute and it is ready",
        "tagline": "Beatport new releases picked for your taste",
        "selections": "Selections",
        "delete_selection": "Delete selection",
        "delete_named": "Delete the selection of {name}",
        "created": "Selection created successfully · {n} tracks",
        "js_delete": "Delete the selection of {name}?\n\nIt goes to the Trash with its stars and the record of its "
                     "playlists. The playlists stay on Beatport, and its tracks may show up again in new selections.",
        "picked_for": "Picked for {reasons}",
        "private_tag": "Private on Beatport",
        "tracks": "{n} tracks",
        "period": "releases from {start} to {end}",
        "candidates": "{n} candidates",
        "short": "Only {n} new releases match your profile in this period.",
        "create_playlist": "Create Beatport playlist {count}",
        "all": "All",
        "listen": "Listen",
        "pause": "Pause",
        "star": "Star",
        "in_playlists": "in {names}",
        "reason_label": "label {v}",
        "reason_artist": "artist {v}",
        "reason_genre": "genre {v}",
        "reason_bpm": "{v} BPM",
        "reason_key": "{v}",
        "js_closed": "beat50 has closed. Open it again from Applications.",
        "js_prompt": "Name of the private Beatport playlist:",
        "js_error": "Error {status}",
        "playlist_created": "“{name}” created on Beatport (private) with {n} tracks.",
        "playlist_partial": " Beatport only accepted {n} of {total}.",
        "warn_add_failed": " The tracks could not be added: {detail}",
        "warn_count_unknown": " Could not check how many tracks were added; check it on beatport.com.",
        "playlist_saved": "“{name}” saved on Beatport: {n} tracks.",
        "warn_rename_failed": " The name could not be changed: {detail}",
        "warn_remove_failed": " Some tracks could not be removed: {detail}",
        "error_playlist_gone": "That playlist no longer exists on Beatport.",
        "error_no_changes": "There is nothing to save.",
        "error_not_gone": "That playlist still exists on Beatport.",
        "forget_playlist": "Remove from this list",
        "gone_tag": "deleted on Beatport",
        "outside_note": "Added on beatport.com; not in this selection",
        "syncing": "Reading playlist from Beatport…",
        "creating": "Creating the playlist on Beatport…",
        "saving": "Saving the changes on Beatport…",
        "checking": "Checking the Beatport session…",
        "error_edit_failed": "Beatport did not answer properly while reading the playlist: {detail}",
        "back": "Back to the selection",
        "playlist_name": "Playlist name",
        "save_changes": "Save changes",
        "in_playlist": "In the playlist ({n})",
        "add_from_selection": "Add from the selection",
        "remove_track": "Remove from the playlist",
        "add_track": "Add to the playlist",
        "edit_hint": "Mark what to remove or add, then save. Nothing changes on Beatport until you save.",
        "error_busy": "beat50 is already busy. Try again in a moment.",
        "error_session_expired": "Your Beatport session has expired: click “Sign in”.",
        "error_name_required": "The playlist needs a name.",
        "error_name_too_long": "The name cannot be longer than {max} characters.",
        "error_no_starred": "No visible tracks are starred.",
        "error_create_unsure": "Beatport did not answer properly while creating “{name}”; it may have been created. "
                               "Check beatport.com before trying again.",
        "error_create_rejected": "Beatport refused to create “{name}”: {detail}",
        "error_created_public": "Beatport created “{name}” as public. Nothing was added to it: make it private or "
                                "delete it on beatport.com.",
        "error_period_format": "Dates must be YYYY-MM-DD.",
        "error_period_future": "“To” cannot be later than today.",
        "error_period_order": "“From” cannot be later than “To”.",
        "error_period_too_long": "The period cannot be longer than a year.",
        "error_not_in_selection": "That track is not in this selection.",
        "error_bad_request": "Invalid request.",
        "error_login_already": "A sign-in is already in progress.",
        "error_not_found": "Not found.",
        "error_consent_required": "beat50 needs your permission to read your Beatport session.",
        "error_interrupted": "beat50 closed before it finished.",
        "error_trash_failed": "The selection could not be moved to the Trash: {detail}",
        "consent_title": "Before reading your Beatport session",
        "consent_window": "beat50 opens Beatport in a window of its own, hidden except when you sign in, "
                          "and closes it when done.",
        "consent_reads": "It only reads your Beatport session (the access token), to read your purchases and "
                         "playlists, create private playlists and edit the ones it created.",
        "consent_never": "It never buys, never deletes a playlist, never touches the ones it did not create, "
                         "never makes one public, and sends nothing anywhere except to Beatport.",
        "consent_where": "Your session stays on this Mac, in beat50's own data: it is not shared with Safari "
                         "or your other browsers.",
        "consent_ok": "Accept and continue",
        "consent_cancel": "Cancel",
        "consent_revoke": "Withdraw permission",
        "quit_busy": "beat50 is making a selection. If you quit now, it stops. Quit anyway?",
        "quit": "Quit",
    },
    "es": {
        "session_active": "Sesión de Beatport activa",
        "session_expired": "Sesión de Beatport caducada",
        "session_unchecked": "Sesión sin comprobar",
        "last_ok": "Última selección: {when} ✓",
        "last_failed": "Última selección: {when} ✗",
        "making": "Haciendo la selección… {step}/{of} · {phase}",
        "phase_library": "leyendo tu librería",
        "phase_discover": "buscando novedades",
        "phase_rank": "eligiendo los 50",
        "since": "Desde",
        "until": "Hasta",
        "new_selection": "Nueva selección",
        "check_session": "Comprobar",
        "help_open": "Ayuda",
        "help_title": "Cómo funciona beat50",
        "help_prev": "Atrás",
        "help_next": "Siguiente",
        "help_done": "Entendido",
        "help_s1_t": "50 novedades, a tu gusto",
        "help_s1_b": "beat50 lee tus compras y playlists de Beatport y elige 50 novedades que probablemente te interesen.",
        "help_s2_t": "Permiso e inicio de sesión",
        "help_s2_b": "La primera vez, beat50 te pide permiso para leer tu sesión de Beatport y abre una ventana para iniciar sesión. No se comparte nada.",
        "help_s3_t": "Haz una selección",
        "help_s3_b": "Elige un periodo y pulsa Nueva selección. Una tarjeta te muestra el avance paso a paso; en aproximadamente un minuto tienes 50 temas, cada uno con su motivo.",
        "help_s4_t": "Cómo elige",
        "help_s4_b": "Tu gusto sale de todas tus compras y playlists, sin límite de fechas: cuanto más recientes, más "
                     "cuentan (la mitad cada {months} meses), y las compras más que las playlists. Luego puntúa las "
                     "novedades del periodo elegido (por defecto los últimos {days} días, hasta un año) por sello, "
                     "artista, género, BPM y tonalidad, y descarta lo que ya tienes o ya te salió. En Géneros le "
                     "das más o menos sitio a cada género, o te quedas solo con uno.",
        "genres_open": "Géneros",
        "genres_title": "Géneros de la próxima selección",
        "genres_hint": "Dale más o menos sitio a cada género. El reparto es una estimación de los 50 huecos; «Solo» "
                       "deja fuera a los demás, y la selección puede salir más corta.",
        "genres_none": "Tus géneros aparecerán aquí tras tu primera selección.",
        "genre_level_0": "Apagado",
        "genre_only": "Solo",
        "genres_reset": "Restablecer",
        "genres_done": "Listo",
        "only_genre": "solo {name}",
        "genre_off": "{name} apagado",
        "help_s5_t": "Escucha y marca",
        "help_s5_b": "Escucha las previews (▶) y marca (★) las que te gusten. Filtra por género para centrarte.",
        "help_s6_t": "Crea una playlist privada",
        "help_s6_b": "Convierte tus favoritos en una playlist de Beatport siempre privada, y edítala cuando quieras.",
        "help_s7_t": "Ordena tus selecciones",
        "help_s7_b": "Elimina una selección que ya no necesites con su papelera, en la barra lateral o junto a su título. Va a la Papelera, sus playlists siguen en Beatport y sus temas podrán volver a salir en nuevas selecciones.",
        "login": "Iniciar sesión",
        "login_hint": "Inicia sesión en Beatport en la ventana que se ha abierto. Se cierra sola cuando entras.",
        "playlists_here": "Playlists de esta selección",
        "empty": "Pulsa «Nueva selección»: beat50 lee tus compras y playlists de Beatport y elige 50 novedades "
                 "del periodo, cada una con su motivo.",
        "empty_title": "Aún no hay ninguna selección",
        "step_consent": "Permiso para leer la sesión",
        "step_login": "Iniciar sesión en Beatport",
        "step_wait": "Un minuto y lista",
        "tagline": "Novedades de Beatport elegidas para tu gusto",
        "selections": "Selecciones",
        "delete_selection": "Eliminar selección",
        "delete_named": "Eliminar la selección del {name}",
        "created": "Selección creada con éxito · {n} temas",
        "js_delete": "¿Eliminar la selección del {name}?\n\nVa a la Papelera con sus estrellas y el registro de sus "
                     "playlists. Las playlists siguen en Beatport y sus tracks podrán volver a salir en nuevas selecciones.",
        "picked_for": "Elegido por {reasons}",
        "private_tag": "Privada en Beatport",
        "tracks": "{n} tracks",
        "period": "novedades del {start} al {end}",
        "candidates": "{n} candidatos",
        "short": "En este periodo solo hay {n} novedades que encajen con tu perfil.",
        "create_playlist": "Crear playlist en Beatport {count}",
        "all": "Todos",
        "listen": "Escuchar",
        "pause": "Pausar",
        "star": "Marcar",
        "in_playlists": "en {names}",
        "reason_label": "sello {v}",
        "reason_artist": "artista {v}",
        "reason_genre": "género {v}",
        "reason_bpm": "{v} BPM",
        "reason_key": "{v}",
        "js_closed": "beat50 se ha cerrado. Vuelve a abrirla desde Aplicaciones.",
        "js_prompt": "Nombre de la playlist privada en Beatport:",
        "js_error": "Error {status}",
        "playlist_created": "«{name}» creada en Beatport (privada) con {n} tracks.",
        "playlist_partial": " Beatport solo aceptó {n} de {total}.",
        "warn_add_failed": " No se pudieron añadir los tracks: {detail}",
        "warn_count_unknown": " No se pudo comprobar cuántos tracks entraron; revísalo en beatport.com.",
        "playlist_saved": "«{name}» guardada en Beatport: {n} tracks.",
        "warn_rename_failed": " No se pudo cambiar el nombre: {detail}",
        "warn_remove_failed": " No se pudieron quitar algunos tracks: {detail}",
        "error_playlist_gone": "Esa playlist ya no existe en Beatport.",
        "error_no_changes": "No hay cambios que guardar.",
        "error_not_gone": "Esa playlist todavía existe en Beatport.",
        "forget_playlist": "Quitar de la lista",
        "gone_tag": "borrada en Beatport",
        "outside_note": "Añadido en beatport.com; no está en esta selección",
        "syncing": "Leyendo la playlist en Beatport…",
        "creating": "Creando la playlist en Beatport…",
        "saving": "Guardando los cambios en Beatport…",
        "checking": "Comprobando la sesión de Beatport…",
        "error_edit_failed": "Beatport no respondió bien al leer la playlist: {detail}",
        "back": "Volver a la selección",
        "playlist_name": "Nombre de la playlist",
        "save_changes": "Guardar cambios",
        "in_playlist": "En la playlist ({n})",
        "add_from_selection": "Añadir de la selección",
        "remove_track": "Quitar de la playlist",
        "add_track": "Añadir a la playlist",
        "edit_hint": "Marca lo que quieras quitar o añadir y guarda. Nada cambia en Beatport hasta que guardes.",
        "error_busy": "beat50 ya está trabajando. Prueba de nuevo en un momento.",
        "error_session_expired": "Tu sesión de Beatport ha caducado: pulsa «Iniciar sesión».",
        "error_name_required": "La playlist necesita un nombre.",
        "error_name_too_long": "El nombre no puede pasar de {max} caracteres.",
        "error_no_starred": "No hay tracks marcados con ★ a la vista.",
        "error_create_unsure": "Beatport no respondió bien al crear «{name}»; puede que se haya creado. "
                               "Revisa beatport.com antes de reintentar.",
        "error_create_rejected": "Beatport rechazó crear «{name}»: {detail}",
        "error_created_public": "Beatport creó «{name}» como pública. No se le ha añadido nada: hazla privada o "
                                "bórrala en beatport.com.",
        "error_period_format": "Las fechas deben ser AAAA-MM-DD.",
        "error_period_future": "«Hasta» no puede ser posterior a hoy.",
        "error_period_order": "«Desde» no puede ser posterior a «Hasta».",
        "error_period_too_long": "El periodo no puede pasar de un año.",
        "error_not_in_selection": "Ese track no está en esta selección.",
        "error_bad_request": "Petición no válida.",
        "error_login_already": "Ya hay un inicio de sesión en curso.",
        "error_not_found": "No existe.",
        "error_consent_required": "Falta tu permiso para leer tu sesión de Beatport.",
        "error_interrupted": "beat50 se cerró antes de terminar.",
        "error_trash_failed": "No se pudo mover la selección a la Papelera: {detail}",
        "consent_title": "Antes de leer tu sesión de Beatport",
        "consent_window": "beat50 abre Beatport en una ventana propia, oculta salvo al iniciar sesión, "
                          "y la cierra al terminar.",
        "consent_reads": "Solo lee tu sesión de Beatport (el token de acceso), para leer tus compras y "
                         "playlists, crear playlists privadas y editar las que creó.",
        "consent_never": "Nunca compra, nunca borra una playlist, no toca las que no creó, nunca hace pública "
                         "ninguna y no envía nada a ningún sitio que no sea Beatport.",
        "consent_where": "Tu sesión se queda en este Mac, en los datos propios de beat50: no se comparte con "
                         "Safari ni con tus otros navegadores.",
        "consent_ok": "Aceptar y continuar",
        "consent_cancel": "Cancelar",
        "consent_revoke": "Retirar permiso",
        "quit_busy": "beat50 está haciendo una selección. Si sales ahora, se detendrá. ¿Salir igualmente?",
        "quit": "Salir",
    },
}

JS_KEYS = ("making", "phase_library", "phase_discover", "phase_rank", "js_closed", "js_prompt", "js_error",
           "listen", "pause", "creating", "saving", "checking", "js_delete", "created")


def pick(cookie_header, accept_language):
    """The language for a request: the switch's cookie, else the browser's preference."""
    for part in (cookie_header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE and value in LANGS:
            return value
    first = (accept_language or "").split(",")[0].strip().lower()
    return "es" if first.startswith("es") else "en"


def t(lang, key, **params):
    text = TEXTS.get(lang, TEXTS["en"]).get(key) or TEXTS["en"][key]
    return text.format(**params) if params else text


def error(lang, code, params=None, fallback=""):
    """The message for an error code; unknown codes keep their original text."""
    key = f"error_{code}"
    if code and key in TEXTS["en"]:
        return t(lang, key, **{k: v for k, v in (params or {}).items()})
    return fallback or t(lang, "error_bad_request")


def _month(lang, n, short=False):
    name = MONTHS[lang][n - 1]
    return name[:3].capitalize() if short and lang == "en" else name[:3] if short else name


def title(selection, lang):
    """'1 October 2026, 07:45' for a coded selection; 'September 2026' for an old monthly one."""
    m = CODE.match(selection)
    if not m:
        year, month = selection.split("-")
        return f"{MONTHS[lang][int(month) - 1].capitalize()} {year}"
    year, month, day, h, mi = m.groups()
    if lang == "es":
        return f"{int(day)} de {MONTHS['es'][int(month) - 1]} de {year}, {h}:{mi}"
    return f"{int(day)} {MONTHS['en'][int(month) - 1]} {year}, {h}:{mi}"


def short_title(selection, lang):
    m = CODE.match(selection)
    if not m:
        year, month = selection.split("-")
        return f"{_month(lang, int(month), short=True).capitalize()} {year}"
    year, month, day, h, mi = m.groups()
    return f"{int(day)} {_month(lang, int(month), short=True)} · {h}:{mi}"


def day(iso, lang):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {_month(lang, d.month, short=True)}"


def moment(iso, lang):
    d = datetime.fromisoformat(iso).astimezone()
    return f"{d.day} {_month(lang, d.month, short=True)} {d:%H:%M}"


OLD_REASON_PREFIXES = {"sello ": "label", "artista ": "artist", "genero ": "genre", "género ": "genre"}


def _old_reasons(sentence):
    """Older selections stored a ready-made Spanish sentence such as "sello X · 124 BPM"."""
    found = []
    for part in filter(None, sentence.split(" · ")):
        prefix = next((p for p in OLD_REASON_PREFIXES if part.startswith(p)), None)
        if prefix:
            found.append({"kind": OLD_REASON_PREFIXES[prefix], "value": part[len(prefix):]})
        elif part.endswith(" BPM"):
            found.append({"kind": "bpm", "value": part[:-len(" BPM")]})
        else:
            found.append({"kind": "key", "value": part})
    return found


def reasons(track, lang):
    """Why a track was picked, in the user's language."""
    found = track["reasons"] if "reasons" in track else _old_reasons(track.get("reason") or "")
    return " · ".join(t(lang, f"reason_{r['kind']}", v=r["value"]) for r in found)


def js_texts(lang):
    return {k: t(lang, k) for k in JS_KEYS}
