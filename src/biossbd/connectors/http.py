"""Minimal HTTP helpers (standard library only) shared by the online connectors."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "bioSSbD-py (https://github.com/; open-source SSbD toolbox)"


class ConnectorError(RuntimeError):
    """A data source could not be reached or returned an unexpected answer."""


class NotFound(ConnectorError):
    """The query returned no result."""


_last_call: dict[str, float] = {}


def _throttle(host: str, min_interval: float) -> None:
    last = _last_call.get(host, 0.0)
    wait = min_interval - (time.monotonic() - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.monotonic()


def get_text(url: str, timeout: float = 20.0, min_interval: float = 0.25) -> str:
    host = urllib.parse.urlparse(url).netloc
    _throttle(host, min_interval)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(url) from e
        raise ConnectorError(f"HTTP {e.code} for {url}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectorError(f"Cannot reach {host}: {e}") from e


def get_json(url: str, timeout: float = 20.0, min_interval: float = 0.25):
    text = get_text(url, timeout, min_interval)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ConnectorError(f"Invalid JSON from {url}") from e


def online(url: str = "https://pubchem.ncbi.nlm.nih.gov", timeout: float = 5.0) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        urllib.request.urlopen(req, timeout=timeout).close()
        return True
    except Exception:
        return False
