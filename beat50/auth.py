"""Gets a Beatport user token from beat50's own WebKit windows.

www.beatport.com sits behind Cloudflare and only hands tokens to a real browser, and the API needs a
user token. beat50 loads the site in a WebKit window (beat50.webkit): visible when the user signs
in, hidden when it only needs a fresh token. The site keeps the session in the app's website data.
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import config, webkit
from .errors import Beat50Error

TOKEN_WAIT_S = 45  # how long a hidden window may take to hand out a valid token
RELOGIN_AFTER_S = 15  # with no valid token by then, reload to force NextAuth's silent re-login
LOGIN_WAIT_S = 15 * 60  # how long the sign-in window waits for the user
POLL_S = 1
LOGIN_POLL_S = 2


class SessionExpired(Beat50Error):
    """There is no Beatport user session in beat50's windows: the user has to sign in."""


class Interrupted(Beat50Error):
    """The window closed before handing out a token (beat50 is quitting): says nothing about the session."""


def save_session(token):
    """Writes the token into a file created with 0600 permissions, never readable by others."""
    config.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(config.SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"access_token": token, "saved_at": int(time.time())}, f)
    config.SESSION_FILE.chmod(0o600)  # in case it already existed with other permissions


def load_session():
    if not config.SESSION_FILE.exists():
        return None
    return json.loads(config.SESSION_FILE.read_text())


def token_is_valid(token):
    """A token is good if /my/account/ answers 200. That is the only test that counts."""
    req = urllib.request.Request(f"{config.API}/my/account/",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False


def _poll(window, seconds, every=POLL_S):
    """Asks the page for its token until a valid one shows up, the window closes or time runs out."""
    until = time.time() + seconds
    while time.time() < until and webkit.is_open(window):
        token = webkit.read_token(window)
        if token and token_is_valid(token):
            return token
        time.sleep(every)
    return None


def get_token():
    """A valid token, read in a hidden window with the saved session; saved for the record."""
    window = webkit.open_window(config.STORE, hidden=True)
    try:
        token = _poll(window, RELOGIN_AFTER_S)
        if not token:
            # After hours without use the session needs a re-login that only happens when a page loads.
            webkit.load(window, config.STORE)
            token = _poll(window, TOKEN_WAIT_S - RELOGIN_AFTER_S)
        closed = not webkit.is_open(window)
    finally:
        webkit.close(window)
    if not token and closed:
        raise Interrupted("interrupted", "beat50 closed before it finished.")
    if not token:
        raise SessionExpired("session_expired", "No valid Beatport session in beat50: sign in again.")
    save_session(token)
    return token


def login_window():
    """Opens Beatport in a visible window for the user to sign in."""
    return webkit.open_window(config.STORE, title="beat50 · Beatport")


def wait_for_login(window):
    """Waits until the user has signed in (then saves the token) or closes the window; closes it either way."""
    try:
        token = _poll(window, LOGIN_WAIT_S, every=LOGIN_POLL_S)
    finally:
        webkit.close(window)
    if token:
        save_session(token)
    return token


def login():
    """Sign-in from the terminal: opens the window and waits for the user."""
    window = login_window()
    print("Sign in to Beatport in the window that opened. It closes by itself once you are in.")
    if not wait_for_login(window):
        raise SessionExpired("session_expired", "No Beatport session: the window closed before signing in.")
    print("Session saved.")
