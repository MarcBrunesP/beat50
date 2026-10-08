import threading

import pytest

from beat50 import webkit


class FakeEvent:
    def __init__(self):
        self.handlers = []
        self._set = False

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def is_set(self):
        return self._set

    def set(self):
        self._set = True


class FakeEvents:
    def __init__(self):
        self.closed = FakeEvent()
        self.closing = FakeEvent()
        self.loaded = FakeEvent()


class FakeWindow:
    def __init__(self, evaluate=None, **kw):
        self.kw = kw
        self.events = FakeEvents()
        self.evaluate = evaluate
        self.loaded_urls = []
        self.destroyed = False
        self.confirm_close = False
        self.localization_override = None  # as pywebview's Window: set from create_window(localization=)
        self.localization = {}

    def evaluate_js(self, script):
        if isinstance(self.evaluate, Exception):
            raise self.evaluate
        return self.evaluate

    def load_url(self, url):
        self.loaded_urls.append(url)

    def destroy(self):
        self.destroyed = True
        self.events.closed.set()


class FakeWebview:
    """Stands in for pywebview: start() runs the function in a thread, as the real one does."""

    def __init__(self):
        self.windows = []
        self.started_with = None

    def create_window(self, title, url=None, **kw):
        w = FakeWindow(title=title, url=url, **kw)
        self.windows.append(w)
        return w

    def start(self, func=None, **kw):
        self.started_with = kw
        if func:
            t = threading.Thread(target=func)
            t.start()
            t.join()


@pytest.fixture
def fake(monkeypatch):
    wv = FakeWebview()
    monkeypatch.setattr(webkit, "_webview", lambda: wv)
    return wv


@pytest.mark.parametrize("answer, token", [("abc.def", "abc.def"), (None, None), ("", None), (42, None),
                                           (RuntimeError("page navigating"), None)])
def test_read_token_only_returns_a_real_token(answer, token):
    assert webkit.read_token(FakeWindow(evaluate=answer)) == token


def test_is_open_follows_the_closed_event():
    w = FakeWindow()
    assert webkit.is_open(w)
    w.destroy()
    assert not webkit.is_open(w)


def test_open_window_keeps_the_session_and_can_hide_it(fake):
    w = webkit.open_window("https://www.beatport.com", hidden=True)
    assert w.kw["url"] == "https://www.beatport.com" and w.kw["hidden"] is True


def test_close_tolerates_a_window_already_closed():
    w = FakeWindow()
    w.destroy()
    webkit.close(w)
    webkit.close(None)


def test_run_does_the_work_with_the_window_loop_going_and_returns_its_result(fake):
    assert webkit.run(lambda: 7) == 7
    assert fake.started_with["private_mode"] is False  # the Beatport session must survive between runs
    assert all(w.destroyed for w in fake.windows)


def test_run_raises_what_the_work_raised(fake):
    def fail():
        raise ValueError("boom")
    with pytest.raises(ValueError, match="boom"):
        webkit.run(fail)
    assert all(w.destroyed for w in fake.windows)


def test_closing_the_app_while_busy_asks_first():
    w = FakeWindow()
    webkit.guard_close(w, busy=lambda: True, texts=lambda: {"message": "Still busy. Quit?", "quit": "Quit",
                                                             "cancel": "Cancel"})
    (handler,) = w.events.closing.handlers
    assert handler() is None  # never cancels by itself: it only turns on the confirmation
    assert w.confirm_close is True
    assert w.localization["global.quitConfirmation"] == "Still busy. Quit?"
    assert w.localization["global.cancel"] == "Cancel"


def test_closing_the_app_when_idle_does_not_ask():
    w = FakeWindow()
    webkit.guard_close(w, busy=lambda: False, texts=lambda: {"message": "m", "quit": "q", "cancel": "c"})
    w.events.closing.handlers[0]()
    assert w.confirm_close is False


def test_read_token_gives_up_when_the_window_never_answers():
    class Stuck(FakeWindow):
        def evaluate_js(self, script):
            threading.Event().wait(5)
    assert webkit.read_token(Stuck(), timeout=0.2) is None


def test_run_closes_every_window_even_if_one_fails_to_close(fake):
    class Broken(FakeWindow):
        def destroy(self):
            raise RuntimeError("window never shown")

    def work():
        fake.windows.insert(0, Broken())
        return 1
    assert webkit.run(work) == 1
    assert fake.windows[1].destroyed  # the blank window that keeps the loop alive


def test_the_quit_texts_are_ready_before_the_first_close_and_follow_the_page_language():
    w = FakeWindow()
    lang = ["en"]
    texts = {"en": {"message": "Busy. Quit?", "quit": "Quit", "cancel": "Cancel"},
             "es": {"message": "Ocupada. ¿Salir?", "quit": "Salir", "cancel": "Cancelar"}}
    webkit.guard_close(w, busy=lambda: True, texts=lambda: texts[lang[0]])
    assert w.localization["global.quitConfirmation"] == "Busy. Quit?"
    lang[0] = "es"
    for handler in w.events.loaded.handlers:  # a page load (the ES / EN switch reloads the page)
        handler()
    assert w.localization["global.quit"] == "Salir"


def test_the_quit_texts_survive_the_window_being_set_up():
    # Before webview.start a window has no `localization` yet; pywebview builds it from
    # `localization_override` when the loop starts.
    class NotStarted(FakeWindow):
        def __init__(self):
            super().__init__()
            del self.localization
    w = NotStarted()
    webkit.guard_close(w, busy=lambda: True, texts=lambda: {"message": "Busy. Quit?", "quit": "Quit",
                                                             "cancel": "Cancel"})
    assert w.localization_override["global.quitConfirmation"] == "Busy. Quit?"
