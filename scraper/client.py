import time

import requests

from .config import USER_AGENT


class MediaWikiClient:
    def __init__(self, api_url, min_interval, maxlag=5, max_retries=6, timeout=60):
        self.api_url = api_url
        self.min_interval = min_interval
        self.maxlag = maxlag
        self.max_retries = max_retries
        self.timeout = timeout
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})

    def _wait(self):
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)

    def get(self, params):
        p = {"format": "json", "formatversion": "2", "maxlag": self.maxlag}
        p.update(params)
        for attempt in range(self.max_retries):
            self._wait()
            backoff = min(2 ** attempt * 2, 120)
            try:
                r = self.session.get(self.api_url, params=p, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError):
                self._last = time.monotonic()
                time.sleep(backoff)
                continue
            self._last = time.monotonic()
            if r.status_code == 429 or r.status_code >= 500:
                try:
                    backoff = max(backoff, float(r.headers.get("Retry-After", 0)))
                except ValueError:
                    pass
                time.sleep(backoff)
                continue
            r.raise_for_status()
            data = r.json()
            err = data.get("error")
            if isinstance(err, dict) and err.get("code") == "maxlag":
                try:
                    ra = float(r.headers.get("Retry-After", 5))
                except ValueError:
                    ra = 5
                time.sleep(max(backoff, ra))
                continue
            return data
        raise RuntimeError(f"Echec apres {self.max_retries} tentatives: {params}")

    def query_all(self, params):
        """Generateur sur les reponses successives (jeton `continue` MediaWiki)."""
        params = dict(params)
        params.setdefault("action", "query")
        cont = {}
        while True:
            data = self.get({**params, **cont})
            yield data
            if "continue" not in data:
                return
            cont = data["continue"]
