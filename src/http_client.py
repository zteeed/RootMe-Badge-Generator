import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from lxml import html
from requests import Response, Session
from requests.adapters import HTTPAdapter

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class HTTPBadStatusCodeError(RuntimeError):
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"bad http status code {code}")


# ---------------------------------------------------------------------------
# Backoff / pacing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BackoffConfig:
    max_attempts: int
    base_sec: float
    cap_sec: float
    timeout: float


def _load_backoff_config() -> BackoffConfig:
    return BackoffConfig(
        max_attempts=int(os.environ.get("HTTP_MAX_ATTEMPTS", "12")),
        base_sec=float(os.environ.get("HTTP_BACKOFF_BASE_SEC", "1.0")),
        cap_sec=float(os.environ.get("HTTP_BACKOFF_MAX_SEC", "120.0")),
        timeout=float(os.environ.get("HTTP_TIMEOUT_SEC", "60.0")),
    )


def _sleep_backoff(attempt: int, base_sec: float, cap_sec: float) -> None:
    delay = min(cap_sec, base_sec * (2 ** attempt))
    jitter = random.uniform(0, max(delay * 0.1, 0.05))
    time.sleep(delay + jitter)


def _parse_retry_after(value: str, cap_sec: float) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return min(cap_sec, max(0.0, float(value)))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delay = (dt - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            return min(cap_sec, delay)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _sleep_for_retryable(response: Response, attempt: int, cfg: BackoffConfig) -> None:
    if response.status_code == 429:
        ra = response.headers.get("Retry-After")
        parsed = _parse_retry_after(ra, cfg.cap_sec) if ra else None
        if parsed is not None:
            log.warning("http_retry_after", extra=dict(seconds=parsed, source="header"))
            time.sleep(parsed)
            return
        base_429 = float(os.environ.get("HTTP_429_BACKOFF_BASE_SEC", "8.0"))
        delay = min(cfg.cap_sec, base_429 * (2 ** attempt) + random.uniform(0, 2.0))
        log.warning("http_429_backoff", extra=dict(seconds=delay, attempt=attempt))
        time.sleep(delay)
        return
    _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)


# ---------------------------------------------------------------------------
# Request pacing (thread-safe via lock on instance)
# ---------------------------------------------------------------------------

class _RequestPacer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_mono = 0.0

    def wait(self) -> None:
        interval = float(os.environ.get("ROOTME_MIN_REQUEST_INTERVAL_SEC", "0.35") or 0)
        if interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = interval - (now - self._last_request_mono)
            if wait > 0:
                time.sleep(wait)
            self._last_request_mono = time.monotonic()


_pacer = _RequestPacer()


# ---------------------------------------------------------------------------
# Unified HTTP request with backoff
# ---------------------------------------------------------------------------

def _request_with_backoff(session: Session, method: str, url: str, **kwargs) -> Response:
    cfg = _load_backoff_config()
    kwargs.setdefault("timeout", cfg.timeout)
    last_exc: Optional[BaseException] = None

    for attempt in range(cfg.max_attempts):
        try:
            _pacer.wait()
            r = session.request(method, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            log.warning("http_request_retry", extra=dict(url=url, method=method, attempt=attempt, error=str(exc)))
            if attempt >= cfg.max_attempts - 1:
                raise
            _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)
            continue

        if r.status_code in RETRYABLE_STATUS and attempt < cfg.max_attempts - 1:
            log.warning("http_status_retry", extra=dict(url=url, method=method, attempt=attempt, status_code=r.status_code))
            _sleep_for_retryable(r, attempt, cfg)
            continue
        return r

    if last_exc:
        raise last_exc
    raise RuntimeError("_request_with_backoff: exhausted attempts without response")


# ---------------------------------------------------------------------------
# Proxy helpers
# ---------------------------------------------------------------------------

def _normalize_proxy_entry(entry: str) -> Optional[str]:
    entry = entry.strip()
    if not entry:
        return None
    if "://" in entry:
        return entry
    default_port = os.environ.get("PUBLIC_PROXY_DEFAULT_PORT", "8080")
    if entry.count(":") == 1 and "[" not in entry:
        return f"http://{entry}"
    return f"http://{entry}:{default_port}"


def _load_proxy_pool() -> List[str]:
    raw = (os.environ.get("PUBLIC_PROXY_POOL") or "").strip()
    if not raw:
        return []
    return [u for part in raw.split(",") if (u := _normalize_proxy_entry(part))]


def _pick_random_proxy() -> Optional[Dict[str, str]]:
    urls = _load_proxy_pool()
    if not urls:
        return None
    chosen = random.choice(urls)
    safe = chosen.split("@")[-1] if "@" in chosen else chosen
    log.info("proxy_selected", extra=dict(proxy=safe))
    return {"http": chosen, "https": chosen}


# ---------------------------------------------------------------------------
# Session / cookie helpers
# ---------------------------------------------------------------------------

def _api_hostname(api_url: str) -> str:
    host = urlparse(api_url).hostname
    if not host:
        raise ValueError("API_URL must include a hostname, e.g. https://api.www.root-me.org")
    return host


def _set_cookie(session: Session, api_url: str, name: str, value: str) -> None:
    if not value:
        return
    host = _api_hostname(api_url)
    secure = api_url.lower().startswith("https")
    session.cookies.set_cookie(
        requests.cookies.create_cookie(domain=host, name=name, value=value, path="/", secure=secure)
    )
    log.info(f"{name}_cookie_set", extra=dict(host=host))


def _build_api_session(api_url: str) -> Session:
    session = Session()
    adapter = HTTPAdapter(max_retries=0, pool_maxsize=100, pool_block=True)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "curl/7.58.0"
    proxies = _pick_random_proxy()
    if proxies:
        session.proxies.update(proxies)
    api_key = (os.environ.get("ROOTME_API_KEY") or "").strip()
    _set_cookie(session, api_url, "api_key", api_key)
    return session


def _author_api_langs() -> List[str]:
    raw = os.environ.get("ROOTME_API_LANGS", "fr,en")
    return [x.strip() for x in raw.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# Low-level HTTP GET (returns bytes + status code)
# ---------------------------------------------------------------------------

def _http_get_raw(session: Session, url: str) -> Tuple[Optional[bytes], int]:
    log.info("http_get", extra=dict(url=url))
    r = _request_with_backoff(session, "GET", url)

    if r.status_code in (200, 404, 401):
        level = "http_get_success" if r.status_code == 200 else "http_get_error"
        log.info(level, extra=dict(url=url, status_code=r.status_code))
        return (r.content if r.status_code == 200 else None), r.status_code

    raise HTTPBadStatusCodeError(r.status_code)


# ---------------------------------------------------------------------------
# RMAPI — Root-Me API client
# ---------------------------------------------------------------------------

class RMAPI:
    def __init__(self) -> None:
        self.api_url: str = os.environ["API_URL"]
        self.web_url: str = self.api_url.replace("api.", "")
        self.number_challenges: Optional[int] = None
        self.number_users: Optional[int] = None
        self.session = _build_api_session(self.api_url)
        self._username = os.environ.get("ROOTME_ACCOUNT_USERNAME")
        self._password = os.environ.get("ROOTME_ACCOUNT_PASSWORD")
        self._authenticate()
        self.update_number_rootme_challenges()
        self.update_number_rootme_users()

    # -- Authentication -----------------------------------------------------

    def _authenticate(self) -> None:
        url = f"{self.api_url}/login"
        payload = {"login": self._username, "password": self._password}
        log.info("http_post", extra=dict(url=url))
        r = _request_with_backoff(self.session, "POST", url, data=payload)

        if r.status_code != 200:
            log.info("authentication_failed", extra=dict(url=url, status_code=r.status_code))
            raise HTTPBadStatusCodeError(r.status_code)

        log.info("authentication_successful", extra=dict(url=url))
        spip_session = json.loads(r.content)[0]["info"]["spip_session"]
        _set_cookie(self.session, self.api_url, "spip_session", str(spip_session))

    # -- Core HTTP ----------------------------------------------------------

    def http_get(self, url: str) -> Optional[bytes]:
        content, status_code = _http_get_raw(self.session, url)
        if status_code == 401:
            self._authenticate()
            content, _ = _http_get_raw(self.session, url)
        return content

    def _get_json(self, url: str) -> Optional[dict]:
        content = self.http_get(url)
        if content is None:
            return None
        return json.loads(content)

    # -- Stats refresh ------------------------------------------------------

    def update_number_rootme_challenges(self) -> None:
        count = 0
        while True:
            url = f"{self.api_url}/challenges" + (f"?debut_challenges={count}" if count else "")
            data = self._get_json(url)
            if data[-1]["rel"] == "previous":
                break
            count += 50
        self.number_challenges = count + len(data[0])

    def update_number_rootme_users(self, mini: int = 0, maxi: int = 10 ** 6) -> None:
        count = (mini + maxi) // 2 + 1

        data = self._get_json(f"{self.api_url}/auteurs?debut_auteurs={count}")
        data_prev = self._get_json(f"{self.api_url}/auteurs?debut_auteurs={count - 1}")

        if abs(len(data_prev[0]) - len(data[0])) == 1 or abs(maxi - mini) < 5:
            self.number_users = count + len(data[0])
            return

        if len(data[0]) < 50:
            self.update_number_rootme_users(mini=mini, maxi=count + 1)
        else:
            self.update_number_rootme_users(mini=count - 1, maxi=maxi)

    # -- User data ----------------------------------------------------------

    def get_user_info(self, username: str) -> Optional[dict]:
        result = {}
        for lang in _author_api_langs():
            url = f"{self.api_url}/auteurs?nom={username}&lang={lang}"
            content = self.http_get(url)
            if content is None:
                continue
            data = json.loads(content)[0]
            offset = len(result)
            for key in data:
                result[str(offset + int(key))] = data[key]
        return result or None

    def get_user_data(self, id_user: int) -> Optional[dict]:
        return self._get_json(f"{self.api_url}/auteurs/{id_user}")

    def get_score(self, id_user: int) -> int:
        data = self.get_user_data(id_user)
        if data is None:
            return 0
        return int(data["score"])

    # -- Profile page scraping ----------------------------------------------

    def get_profile_page_url(self, username: str, id_user: int) -> Optional[str]:
        url = f"{self.api_url}/{username}-{id_user}"
        if self.http_get(url) is not None:
            return url

        normalized = username.replace(" ", "-") if " " in username else username
        url = f"{self.api_url}/{normalized}"
        if self.http_get(url) is not None:
            return url

        return self._search_profile_page(username)

    def _search_profile_page(self, username: str) -> str:
        url = f"{self.web_url}/?page=recherche&recherche={username}"
        content = self.http_get(url)
        tree = html.fromstring(content)
        urls = tree.xpath(
            f'//div[@class="t-body tb-padding"]/ul/li/a[contains(text(), "{username}")]/@href'
        )
        if len(urls) == 1:
            return self.api_url + urls[0]
        raise Exception("Update method to find profile page url")

    def get_avatar_url(self, profile_page_url: str) -> str:
        content = self.http_get(profile_page_url)
        tree = html.fromstring(content)
        for xpath in (
            '//h1/img[@itemprop="image"]/@src',
            '//img[starts-with(@src, "IMG/logo/auton")]/@src',
        ):
            result = tree.xpath(xpath)
            if result:
                return f"{self.api_url}/{result[0]}"
        raise ValueError(f"Avatar not found on {profile_page_url}")

    def get_rank(self, profile_page_url: str) -> str:
        content = self.http_get(profile_page_url)
        tree = html.fromstring(content)
        results = tree.xpath('//img[starts-with(@src, "squelettes/img/rang")]/@title')
        if not results or not results[0].strip():
            return "visitor"
        return results[0].strip()
