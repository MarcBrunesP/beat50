"""Client for Beatport's API v4. Reads everything; the writes (post, patch, delete) are used only by playlists.py."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config
from .errors import Beat50Error

RETRIES = 3
BACKOFF_BASE = 2


class TokenExpired(Beat50Error):
    """The token is no longer valid: the browser session must be linked again."""


class Client:
    def __init__(self, token, renew=None):
        self.token = token
        self.renew = renew  # returns a fresh token; auth.get_token in production
        self.requests = 0

    def _fetch(self, url, body=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        method = method or ("POST" if data is not None else "GET")
        retries, renewed = 0, False
        while True:
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            try:
                self.requests += 1
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                # The token may arrive with little life left: if it expires midway, get a new one and retry.
                if e.code == 401 and self.renew and not renewed:
                    self.token = self.renew()
                    renewed = True
                    continue
                if e.code in (401, 403):
                    raise TokenExpired("session_expired", f"Beatport answered {e.code}: sign in again.") from e
                # A write that got a 5xx may have been applied: repeating it could duplicate a playlist or
                # its tracks. A 429 was not applied.
                retryable = e.code == 429 or (e.code >= 500 and method == "GET")
                if retryable and retries < RETRIES - 1:
                    retries += 1
                    time.sleep(BACKOFF_BASE ** retries)
                    continue
                raise

    def get(self, path, **params):
        url = f"{config.API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self._fetch(url)

    def post(self, path, body):
        return self._fetch(f"{config.API}{path}", body)

    def patch(self, path, body):
        return self._fetch(f"{config.API}{path}", body, method="PATCH")

    def delete(self, path, body):
        return self._fetch(f"{config.API}{path}", body, method="DELETE")

    def paged(self, path, max_pages=100, **params):
        """Returns every `results` item. Beatport pages with `page` and marks the end with a null `next`."""
        params.setdefault("per_page", config.PER_PAGE)
        out = []
        for page in range(1, max_pages + 1):
            body = self.get(path, page=page, **params)
            out.extend(body.get("results", []))
            if not body.get("next"):
                break
        return out
