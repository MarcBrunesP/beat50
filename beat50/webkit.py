"""beat50's windows: WebKit (Safari's engine) through pywebview.

The app's own window shows the local page; other windows load www.beatport.com so the user can sign in
and so beat50 can read the session token. Those are not automated browsers, so Beatport and
Cloudflare treat them like Safari. WebKit keeps the session in the app's own website data on this Mac.

Cocoa needs its event loop on the main thread: run() and show_app() start it there, and the actual
work goes on in other threads, which can open, read and close windows while the loop runs.
"""
import threading

TITLE = "beat50"
SIZE = (1200, 820)

# Asks the site for its NextAuth session. A synchronous request, so evaluate_js gets the value itself and
# not a promise. www.beatport.com refreshes the token when asked; anywhere else (the sign-in pages) the
# request fails and the answer is null.
READ_TOKEN = """
(() => {
  try {
    const x = new XMLHttpRequest();
    x.open('GET', '/api/auth/session', false);
    x.send();
    if (x.status !== 200) return null;
    const s = JSON.parse(x.responseText || 'null');
    return (s && (s.accessToken || (s.token && s.token.accessToken))) || null;
  } catch (e) {
    return null;
  }
})()
"""


def _webview():
    import webview
    return webview


def open_window(url, title=TITLE, hidden=False):
    width, height = SIZE
    return _webview().create_window(title, url, width=width, height=height, hidden=hidden,
                                    background_color="#121214")  # night mode: no white flash before the page paints


def is_open(window):
    return not window.events.closed.is_set()


def read_token(window, timeout=10):
    """The page's current Beatport token, or None (no session, a page still loading, a closed window).

    The script runs in a helper thread: if the window closes at the wrong moment, pywebview may never
    answer, and the caller must not wait forever.
    """
    answer = []

    def ask():
        try:
            answer.append(window.evaluate_js(READ_TOKEN))
        except Exception:
            answer.append(None)

    helper = threading.Thread(target=ask, daemon=True)
    helper.start()
    helper.join(timeout)
    token = answer[0] if answer else None
    return token if isinstance(token, str) and token else None


def load(window, url):
    window.load_url(url)


def close(window):
    if window is not None and is_open(window):
        window.destroy()


def _close_all(windows):
    for w in list(windows):
        try:
            close(w)
        except Exception:  # e.g. a window that never finished opening: close the others anyway
            pass


def run(work):
    """Runs work() with the window loop going and returns its result: for the command line.

    A hidden blank window keeps the loop alive; every window is closed when the work ends.
    """
    webview = _webview()
    webview.create_window(TITLE, html="", hidden=True)
    outcome = {}

    def target():
        try:
            outcome["value"] = work()
        except BaseException as e:
            outcome["error"] = e
        finally:
            _close_all(webview.windows)

    webview.start(target, private_mode=False)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def guard_close(window, busy, texts):
    """While busy() is true, closing the window (or quitting) asks for confirmation first.

    texts() gives the dialog's "message", "quit" and "cancel" in the user's language. pywebview reads them
    before asking the closing handler, so they are set up front and again on every page load (the ES / EN
    switch reloads the page). The closing handler runs on the main thread, so it only sets a flag.
    """
    def set_texts():
        t = texts()
        strings = {"global.quitConfirmation": t["message"], "global.quit": t["quit"], "global.cancel": t["cancel"]}
        # Before the loop starts the window only has localization_override, which pywebview copies in.
        window.localization_override = dict(window.localization_override or {}, **strings)
        if hasattr(window, "localization"):
            window.localization.update(strings)

    def closing():
        window.confirm_close = bool(busy())

    set_texts()
    window.events.loaded += set_texts
    window.events.closing += closing


def show_app(url, busy, texts):
    """Opens the app's window at url and blocks until the user closes it; then closes every other window."""
    webview = _webview()
    window = open_window(url)
    guard_close(window, busy, texts)

    def close_the_rest():
        _close_all(webview.windows)

    window.events.closed += close_the_rest
    webview.start(private_mode=False)
