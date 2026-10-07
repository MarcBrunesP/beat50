from datetime import date

from beatcrate import discover

TODAY = date(2026, 9, 7)

PROFILE = {
    "labels": [{"id": 100, "weight": 1.0}, {"id": 200, "weight": 0.5}],
    "artists": [{"id": 10, "weight": 1.0}],
    "genres": [{"id": 5, "weight": 1.0}, {"id": 6, "weight": 0.4}],
}


class FakeClient:
    """Counts requests like Client: one per page or per get."""

    def __init__(self, chart=None):
        self.calls = []
        self.requests = 0
        self.chart = chart if chart is not None else [{"id": 900, "publish_date": "2026-09-01"}]

    def paged(self, path, **params):
        self.requests += 1
        self.calls.append((path, params))
        return [{"id": len(self.calls), "name": "t"}]

    def get(self, path, **params):
        self.requests += 1
        self.calls.append((path, params))
        return {"results": self.chart}


def test_window_covers_the_previous_31_days():
    since, until = discover.window(TODAY)
    assert until == "2026-09-07"
    assert since == "2026-08-07"


def test_labels_go_in_a_single_call_separated_by_commas():
    c = FakeClient()
    discover.find_candidates(c, PROFILE, TODAY)
    by_label = [p for _, p in c.calls if "label_id" in p]
    assert len(by_label) == 1
    assert by_label[0]["label_id"] == "100,200"
    assert by_label[0]["publish_date"] == "2026-08-07:2026-09-07"


def test_asks_for_the_chart_of_each_profile_genre():
    c = FakeClient()
    discover.find_candidates(c, PROFILE, TODAY)
    charts = [path for path, _ in c.calls if "/top/" in path]
    assert charts == ["/catalog/genres/5/top/100/", "/catalog/genres/6/top/100/"]


def test_only_what_was_published_in_the_window_comes_from_the_chart():
    chart = [{"id": 901, "publish_date": "2026-09-01"},
             {"id": 902, "publish_date": "2026-03-01"},
             {"id": 903, "publish_date": "2026-09-20"}]
    cand = discover.find_candidates(FakeClient(chart=chart), PROFILE, TODAY)
    ids = {t["id"] for t in cand["tracks"]}
    assert 901 in ids
    assert 902 not in ids and 903 not in ids


def test_candidates_are_deduplicated_by_id():
    class Repeated(FakeClient):
        def paged(self, path, **params):
            self.requests += 1
            return [{"id": 7, "name": "same", "publish_date": "2026-09-01"}]

    cand = discover.find_candidates(Repeated(chart=[{"id": 7, "publish_date": "2026-09-01"}]), PROFILE, TODAY)
    assert len(cand["tracks"]) == 1


def test_respects_the_request_cap(monkeypatch):
    monkeypatch.setattr(discover.config, "MAX_REQUESTS", 1)
    c = FakeClient()
    cand = discover.find_candidates(c, PROFILE, TODAY)
    assert len(c.calls) == 1
    assert cand["truncated"] is True


def test_with_a_chosen_period_it_searches_that_period():
    chart = [{"id": 901, "publish_date": "2026-09-02"}, {"id": 902, "publish_date": "2026-08-20"}]
    c = FakeClient(chart=chart)
    cand = discover.find_candidates(c, PROFILE, TODAY, since=date(2026, 9, 1))
    by_label = [p for _, p in c.calls if "label_id" in p]
    assert by_label[0]["publish_date"] == "2026-09-01:2026-09-07"
    assert cand["window"] == {"from": "2026-09-01", "to": "2026-09-07"}
    ids = {t["id"] for t in cand["tracks"]}
    assert 901 in ids and 902 not in ids
