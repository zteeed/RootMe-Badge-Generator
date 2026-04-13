import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from lxml import html


class ExFormatter(logging.Formatter):
    def_keys = ['name', 'msg', 'args', 'levelname', 'levelno',
                'pathname', 'filename', 'module', 'exc_info',
                'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread',
                'threadName', 'processName', 'process', 'message']

    def format(self, record):
        string = super().format(record)
        extra = {k: v for k, v in record.__dict__.items()
                 if k not in self.def_keys}
        if len(extra) > 0:
            string += " - extra: " + str(extra)
        return string


logging.basicConfig()
#  logging.root.setLevel(logging.NOTSET)
log = logging.getLogger('app')
log.setLevel(logging.INFO)
logger = logging.StreamHandler(sys.stdout)
logger.setFormatter(ExFormatter())
log.addHandler(logger)


class HTTPBadStatusCodeError(RuntimeError):
    def __init__(self, code: int):
        super().__init__(f'bad http status code {code}')


RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _normalize_proxy_entry(entry: str) -> Optional[str]:
    """Build an HTTP(S) proxy URL for requests from one pool entry."""
    entry = entry.strip()
    if not entry:
        return None
    if '://' in entry:
        return entry
    default_port = os.environ.get('PUBLIC_PROXY_DEFAULT_PORT', '8080')
    # host:port (IPv4 or hostname); IPv6 should use a full URL with brackets.
    if entry.count(':') == 1 and '[' not in entry:
        return f'http://{entry}'
    return f'http://{entry}:{default_port}'


def _proxy_urls_from_pool() -> List[str]:
    raw = (os.environ.get('PUBLIC_PROXY_POOL') or '').strip()
    if not raw:
        return []
    urls: List[str] = []
    for part in raw.split(','):
        u = _normalize_proxy_entry(part)
        if u:
            urls.append(u)
    return urls


def _random_session_proxies() -> Optional[Dict[str, str]]:
    """Pick one random proxy from PUBLIC_PROXY_POOL for the whole Session (stable cookies)."""
    urls = _proxy_urls_from_pool()
    if not urls:
        return None
    chosen = random.choice(urls)
    safe = chosen.split('@')[-1] if '@' in chosen else chosen
    log.log(logging.INFO, 'proxy_selected', extra=dict(proxy=safe))
    return {'http': chosen, 'https': chosen}


@dataclass(frozen=True)
class BackoffConfig:
    max_attempts: int
    base_sec: float
    cap_sec: float
    timeout: float


def _load_backoff_config() -> BackoffConfig:
    return BackoffConfig(
        max_attempts=int(os.environ.get('HTTP_MAX_ATTEMPTS', '8')),
        base_sec=float(os.environ.get('HTTP_BACKOFF_BASE_SEC', '1.0')),
        cap_sec=float(os.environ.get('HTTP_BACKOFF_MAX_SEC', '60.0')),
        timeout=float(os.environ.get('HTTP_TIMEOUT_SEC', '60.0')),
    )


def _sleep_backoff(attempt: int, base_sec: float, cap_sec: float) -> None:
    delay = min(cap_sec, base_sec * (2 ** attempt))
    jitter = random.uniform(0, max(delay * 0.1, 0.05))
    time.sleep(delay + jitter)


def session_get_with_backoff(session: Session, url: str) -> requests.Response:
    cfg = _load_backoff_config()
    last_exc: Optional[BaseException] = None
    for attempt in range(cfg.max_attempts):
        try:
            r = session.get(url, timeout=cfg.timeout)
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            log.log(
                logging.WARNING,
                'http_get_retry',
                extra=dict(url=url, attempt=attempt, error=str(exc)),
            )
            if attempt >= cfg.max_attempts - 1:
                raise
            _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)
            continue

        if r.status_code in RETRYABLE_STATUS and attempt < cfg.max_attempts - 1:
            log.log(
                logging.WARNING,
                'http_get_status_retry',
                extra=dict(url=url, attempt=attempt, status_code=r.status_code),
            )
            _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)
            continue
        return r
    if last_exc:
        raise last_exc
    raise RuntimeError('session_get_with_backoff: exhausted attempts without response')


def session_post_with_backoff(session: Session, url: str, data: dict) -> requests.Response:
    cfg = _load_backoff_config()
    last_exc: Optional[BaseException] = None
    for attempt in range(cfg.max_attempts):
        try:
            r = session.post(url, data=data, timeout=cfg.timeout)
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            log.log(
                logging.WARNING,
                'http_post_retry',
                extra=dict(url=url, attempt=attempt, error=str(exc)),
            )
            if attempt >= cfg.max_attempts - 1:
                raise
            _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)
            continue

        if r.status_code in RETRYABLE_STATUS and attempt < cfg.max_attempts - 1:
            log.log(
                logging.WARNING,
                'http_post_status_retry',
                extra=dict(url=url, attempt=attempt, status_code=r.status_code),
            )
            _sleep_backoff(attempt, cfg.base_sec, cfg.cap_sec)
            continue
        return r
    if last_exc:
        raise last_exc
    raise RuntimeError('session_post_with_backoff: exhausted attempts without response')


session = Session()


def http_get_url(session: Session, url: str) -> Tuple[Optional[bytes], int]:
    """
    Retrieves the HTML from a page via HTTP(s).
    If the page is present on the server (200 status code), returns the html.
    If the server does not host this page (404 status code), returns None.
    Any other HTTP code are considered as unexpected and raise an HTTPBadStatusCodeError.
    :param session: requests session object
    :param url: url to the page
    :return: HTML of the page or None
    """
    log.log(logging.INFO, f'http_get', extra=dict(url=url))
    r = session_get_with_backoff(session, url)

    if r.status_code == 200:
        log.log(logging.INFO, f'http_get_success', extra=dict(url=url, status_code=r.status_code))
        return r.content, r.status_code

    if r.status_code == 404:
        log.log(logging.INFO, f'http_get_error', extra=dict(url=url, status_code=r.status_code))
        return None, r.status_code

    if r.status_code == 401:
        log.log(logging.INFO, f'http_get_error', extra=dict(url=url, status_code=r.status_code))
        return None, r.status_code

    raise HTTPBadStatusCodeError(r.status_code)


class RMAPI:
    api_url = os.environ.get('API_URL')

    def __init__(self):
        self.api_url = os.environ.get('API_URL')
        self.web_url = self.api_url.replace('api.', '')
        self.number_challenges = None
        self.number_users = None
        session = Session()
        adapter = HTTPAdapter(max_retries=0, pool_maxsize=100, pool_block=True)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        self.session = session
        proxies = _random_session_proxies()
        if proxies:
            self.session.proxies.update(proxies)
        self.session.headers = {
            "User-Agent": "curl/7.58.0",
        }
        self.account_username = os.environ.get('ROOTME_ACCOUNT_USERNAME')
        self.account_password = os.environ.get('ROOTME_ACCOUNT_PASSWORD')
        self.authenticate(self.account_username, self.account_password)
        self.update_number_rootme_challenges()
        self.update_number_rootme_users()

    def authenticate(self, username: str, password: str) -> None:
        payload = {
            "login": username,
            "password": password,
        }
        url = f'{self.api_url}/login'
        log.log(logging.INFO, f'http_post', extra=dict(url=url, payload=payload))
        r = session_post_with_backoff(self.session, url, payload)

        if r.status_code != 200:
            log.log(logging.INFO, f'Authentication failed',
                    extra=dict(url=url, status_code=r.status_code, payload=payload))
            raise HTTPBadStatusCodeError(r.status_code)

        log.log(logging.INFO, f'Authentication successful', extra=dict(url=url, status_code=r.status_code))
        response = json.loads(r.content)[0]
        # Note that domain keyword parameter is the only optional parameter here
        cookie_obj = requests.cookies.create_cookie(
            domain=self.api_url,
            name='spip_session',
            value=str(response["info"]["spip_session"])
        )
        self.session.cookies.set_cookie(cookie_obj)
        log.log(logging.INFO, f'New cookie added for RM API', extra=dict(cookie_obj=cookie_obj))

    def update_number_rootme_challenges(self) -> None:
        url = f'{self.api_url}/challenges'
        log.log(logging.INFO, f'http_get', extra=dict(url=url))
        r = session_get_with_backoff(self.session, url)
        data = json.loads(r.content)
        count = 0
        while data[-1]['rel'] != 'previous':
            count += 50
            url = f'{self.api_url}/challenges?debut_challenges={count}'
            log.log(logging.INFO, f'http_get', extra=dict(url=url))
            r = session_get_with_backoff(self.session, url)
            data = json.loads(r.content)
        self.number_challenges = count + len(data[0])

    def update_number_rootme_users(self, mini=0, maxi=10 ** 6) -> None:
        count = (mini + maxi) // 2
        count += 1

        url = f'{self.api_url}/auteurs?debut_auteurs={count}'
        log.log(logging.INFO, f'http_get', extra=dict(url=url, count=count, mini=mini, maxi=maxi))
        r = session_get_with_backoff(self.session, url)
        data = json.loads(r.content)

        url = f'{self.api_url}/auteurs?debut_auteurs={count - 1}'
        log.log(logging.INFO, f'http_get', extra=dict(url=url, count=count - 1, mini=mini, maxi=maxi))
        r = session_get_with_backoff(self.session, url)
        data_previous = json.loads(r.content)

        if abs(len(data_previous[0]) - len(data[0])) == 1:
            self.number_users = count + len(data[0])
            return

        if abs(maxi - mini) < 5:
            self.number_users = count + len(data[0])
            return

        if len(data[0]) < 50:
            self.update_number_rootme_users(mini=mini, maxi=count + 1)
        else:
            self.update_number_rootme_users(mini=count - 1, maxi=maxi)

    def http_get(self, url):
        content, status_code = http_get_url(self.session, url)
        if status_code == 401:
            self.authenticate(self.account_username, self.account_password)
        content, status_code = http_get_url(self.session, url)
        return content

    def get_user_info(self, username: str):
        result = {}
        for lang in ['fr', 'en', 'de', 'es']:
            url = f'{self.api_url}/auteurs?nom={username}&lang={lang}'
            content = self.http_get(url)
            if content is None:
                continue
            data = json.loads(content)[0]
            length = len(result)
            for key in data:
                result[str(length + int(key))] = data[key]
        if result == {}:
            return None
        return json.dumps([result])

    def get_user_data(self, id_user: int):
        url = f'{self.api_url}/auteurs/{id_user}'
        return self.http_get(url)

    def get_score_existing_user(self, id_user: int):
        content = self.get_user_data(id_user)
        if content is None:
            return 0
        data = json.loads(content)
        return int(data['score'])

    def get_profile_page_url(self, username: str, id_user: int, score: int) -> Optional[str]:
        url = f'{self.api_url}/{username}-{id_user}'
        content = self.http_get(url)
        if content is not None:
            return url

        if ' ' in username:
            username = username.replace(' ', '-')

        url = f'{self.api_url}/{username}'
        content = self.http_get(url)
        if content is not None:
            return url

        url = f'{self.web_url}/?page=recherche&recherche={username}'
        content = self.http_get(url)
        tree = html.fromstring(content)
        user_profile_urls = tree.xpath(
            f'//div[@class="t-body tb-padding"]/ul/li/a[contains(text(), "{username}")]/@href'
        )
        for url_path in user_profile_urls:
            #  check every pages to check if profile page match score
            pass
        if len(user_profile_urls) == 1:
            url = self.api_url + user_profile_urls[0]
            return url
        raise Exception('Update method to find profile page url')

    def get_avatar_url(self, profile_page_url: str) -> str:
        content = self.http_get(profile_page_url)
        tree = html.fromstring(content)
        result = tree.xpath('//h1/img[@itemprop="image"]/@src')
        return f'{self.api_url}/{result[0]}'

    def get_rank(self, profile_page_url: str) -> str:
        content = self.http_get(profile_page_url)
        tree = html.fromstring(content)
        result = tree.xpath(
            '//img[starts-with(@src, "squelettes/img/rang")]/../../../'
            'tr[@style="border: 1px #2ba6cb solid"]/td/img/@title'
        )[0]
        if not result:
            return 'visitor'
        return result.strip()
