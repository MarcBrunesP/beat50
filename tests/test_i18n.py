import pytest

from beatcrate.app import i18n


def test_every_text_exists_in_both_languages():
    assert set(i18n.TEXTS["en"]) == set(i18n.TEXTS["es"])


@pytest.mark.parametrize("cookie, accept, lang", [
    ("beatcrate_lang=es", "en-US,en;q=0.9", "es"),
    ("other=1; beatcrate_lang=en", "es-ES,es;q=0.9", "en"),
    (None, "es-ES,es;q=0.9", "es"),
    (None, "en-GB,en;q=0.8", "en"),
    ("beatcrate_lang=fr", "es", "es"),
    (None, None, "en"),
])
def test_language_comes_from_the_switch_or_the_browser(cookie, accept, lang):
    assert i18n.pick(cookie, accept) == lang


@pytest.mark.parametrize("lang, title, short", [
    ("en", "1 October 2026, 07:45", "1 Oct · 07:45"),
    ("es", "1 de octubre de 2026, 07:45", "1 oct · 07:45"),
])
def test_selection_titles(lang, title, short):
    assert i18n.title("20261001_074512", lang) == title
    assert i18n.short_title("20261001_074512", lang) == short


@pytest.mark.parametrize("lang, title, short", [("en", "September 2026", "Sep 2026"), ("es", "Septiembre 2026", "Sep 2026")])
def test_old_monthly_selections_keep_their_month_title(lang, title, short):
    assert i18n.title("2026-09", lang) == title
    assert i18n.short_title("2026-09", lang) == short


def test_days():
    assert i18n.day("2026-09-09", "en") == "9 Sep"
    assert i18n.day("2026-09-09", "es") == "9 sep"


def test_reasons_are_translated():
    track = {"reasons": [{"kind": "label", "value": "Hardgroove"}, {"kind": "bpm", "value": 140}]}
    assert i18n.reasons(track, "en") == "label Hardgroove · 140 BPM"
    assert i18n.reasons(track, "es") == "sello Hardgroove · 140 BPM"


@pytest.mark.parametrize("old, en, es", [
    ("sello Hardgroove · genero Techno (Raw / Deep / Hypnotic)",
     "label Hardgroove · genre Techno (Raw / Deep / Hypnotic)",
     "sello Hardgroove · género Techno (Raw / Deep / Hypnotic)"),
    ("artista Tale Of Us · 124 BPM", "artist Tale Of Us · 124 BPM", "artista Tale Of Us · 124 BPM"),
    ("genero House · 8A", "genre House · 8A", "género House · 8A"),
    ("género House", "genre House", "género House"),
    ("", "", ""),
])
def test_reasons_of_older_selections_are_translated_too(old, en, es):
    assert i18n.reasons({"reason": old}, "en") == en
    assert i18n.reasons({"reason": old}, "es") == es


def test_errors_are_translated_with_their_params():
    assert i18n.error("en", "name_too_long", {"max": 100}) == "The name cannot be longer than 100 characters."
    assert i18n.error("es", "name_too_long", {"max": 100}) == "El nombre no puede pasar de 100 caracteres."
    assert i18n.error("es", "session_expired") == "Tu sesión de Beatport ha caducado: pulsa «Iniciar sesión»."


def test_unknown_error_codes_keep_the_original_message():
    assert i18n.error("es", "something_new", {}, "Original text") == "Original text"
    assert i18n.error("es", None, {}, "Plain failure") == "Plain failure"


def test_texts_for_the_page_script():
    texts = i18n.js_texts("es")
    assert texts["js_closed"] == "beatcrate se ha cerrado. Vuelve a abrirla desde Aplicaciones."
    assert set(texts) == set(i18n.JS_KEYS)
