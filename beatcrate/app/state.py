"""State shared between the app and the command line: state.json and the process lock."""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

from .. import config
from ..errors import BeatcrateError


class Busy(BeatcrateError):
    """Another beatcrate process is reading the session or making a selection."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read():
    if not config.STATE_FILE.exists():
        return {}
    return json.loads(config.STATE_FILE.read_text())


def update(**parts):
    """Merges the top-level keys and writes via a unique temp file plus rename: never half-written."""
    state = read()
    state.update(parts)
    config.DATA.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config.DATA, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, config.STATE_FILE)
    return state


_fd = None  # descriptor holding the lock in this process


def _pid():
    try:
        return int(config.LOCK_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return None


def lock_owner():
    """Pid of the process holding the lock, or None.

    The kernel (flock) decides, not the saved pid: after a restart that pid may belong to another
    process, and the lock of a dead process is released on its own.
    """
    try:
        fd = os.open(config.LOCK_FILE, os.O_RDONLY)
    except FileNotFoundError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return _pid() or -1
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    finally:
        os.close(fd)


def acquire():
    """Takes the lock or raises Busy. Released by release() or when the process dies."""
    global _fd
    config.DATA.mkdir(parents=True, exist_ok=True)
    fd = os.open(config.LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Busy("busy", f"Another beatcrate process is running (pid {_pid()}).") from None
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    _fd = fd


def release():
    global _fd
    if _fd is not None:
        fd, _fd = _fd, None
        os.close(fd)  # closing the descriptor releases the flock


@contextmanager
def lock():
    acquire()
    try:
        yield
    finally:
        release()
