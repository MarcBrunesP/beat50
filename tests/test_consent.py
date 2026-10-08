import json

import pytest

from beat50.app import consent
from beat50.errors import Beat50Error


def test_there_is_no_consent_until_the_user_gives_it(data_dir):
    assert consent.granted() is False


def test_giving_consent_is_remembered_with_its_date(data_dir):
    consent.grant()
    assert consent.granted() is True
    saved = json.loads((data_dir / "consent.json").read_text())
    assert saved["session"] is True and saved["granted_at"]


def test_a_consent_given_for_chrome_is_asked_again(data_dir):
    # beat50 1.1 asked to open Chrome; reading the session in its own window is a different request.
    (data_dir / "consent.json").write_text('{"chrome": true, "version": 2, "granted_at": "2026-10-01T12:00:00+00:00"}')
    assert consent.granted() is False


def test_withdrawing_consent_forgets_it(data_dir):
    consent.grant()
    consent.revoke()
    assert consent.granted() is False
    consent.revoke()  # withdrawing twice is fine


def test_a_damaged_consent_file_counts_as_no_consent(data_dir):
    (data_dir / "consent.json").write_text("{not json")
    assert consent.granted() is False


def test_require_stops_without_consent(data_dir):
    with pytest.raises(Beat50Error) as e:
        consent.require()
    assert e.value.code == "consent_required"
    consent.grant()
    consent.require()


def test_a_consent_given_to_an_older_notice_is_asked_again(data_dir):
    # 2.2 can also edit the playlists beat50 created: the notice says so and is asked again.
    (data_dir / "consent.json").write_text('{"session": true, "granted_at": "2026-10-01T12:00:00+00:00"}')
    assert consent.granted() is False
    consent.grant()
    assert json.loads((data_dir / "consent.json").read_text())["version"] == consent.VERSION
    assert consent.granted() is True
