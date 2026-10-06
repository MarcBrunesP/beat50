"""The user's permission for the app to read their Beatport session in a window of its own.

Asked once in the page and kept in consent.json until the user withdraws it. The command line does not
ask: running `beatcrate login` or `generate` is already a deliberate choice.
"""
import json
import os
import tempfile

from .. import config
from ..errors import BeatcrateError
from . import state

# Raised whenever the notice says something new, so a consent given to older wording is asked again.
# 2: beatcrate also edits the playlists it created.
VERSION = 2


def granted():
    try:
        data = json.loads(config.CONSENT_FILE.read_text())
        return data.get("session") is True and data.get("version") == VERSION
    except (OSError, ValueError, AttributeError):
        return False


def grant():
    config.DATA.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.DATA, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump({"session": True, "version": VERSION, "granted_at": state.now()}, f)
    os.replace(tmp, config.CONSENT_FILE)


def revoke():
    config.CONSENT_FILE.unlink(missing_ok=True)


def require():
    if not granted():
        raise BeatcrateError("consent_required", "beatcrate needs your permission to read your Beatport session.")
