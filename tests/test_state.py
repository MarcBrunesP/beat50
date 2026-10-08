import os
import subprocess
import sys

import pytest

from beat50.app import state


def test_read_without_a_file_returns_empty(data_dir):
    assert state.read() == {}


def test_update_merges_and_leaves_no_temp_files(data_dir):
    state.update(session={"status": "active"})
    state.update(running=None)
    assert state.read() == {"session": {"status": "active"}, "running": None}
    assert list(data_dir.glob("*.tmp")) == []


def test_update_returns_the_merged_state(data_dir):
    state.update(a=1)
    assert state.update(b=2) == {"a": 1, "b": 2}


def test_lock_is_taken_and_released(data_dir):
    with state.lock():
        assert state.lock_owner() == os.getpid()
    assert state.lock_owner() is None


def test_lock_held_by_a_live_process(data_dir):
    with state.lock():
        with pytest.raises(state.Busy) as err:
            with state.lock():
                pass
        assert err.value.code == "busy"
        assert state.lock_owner() == os.getpid()


def test_lock_of_a_dead_process_is_ignored(data_dir):
    (data_dir / ".lock").write_text("999999")
    with state.lock():
        assert state.lock_owner() == os.getpid()


def test_orphan_lock_with_the_pid_of_another_live_process_is_ignored(data_dir):
    # After a restart the saved pid may already belong to another process (here, pid 1).
    (data_dir / ".lock").write_text("1")
    with state.lock():
        assert state.lock_owner() == os.getpid()


def test_lock_held_by_another_process(data_dir):
    code = ("import fcntl, os, time\n"
            f"fd = os.open({str(data_dir / '.lock')!r}, os.O_RDWR | os.O_CREAT)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "os.write(fd, str(os.getpid()).encode())\n"
            "print('ok', flush=True)\n"
            "time.sleep(30)\n")
    other = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert other.stdout.readline().strip() == "ok"
        assert state.lock_owner() == other.pid
        with pytest.raises(state.Busy):
            state.acquire()
    finally:
        other.kill()
        other.wait()
    with state.lock():
        assert state.lock_owner() == os.getpid()


def test_lock_with_corrupt_content_is_ignored(data_dir):
    (data_dir / ".lock").write_text("garbage")
    with state.lock():
        assert state.lock_owner() == os.getpid()
