import json
import logging
import os
import sys
from typing import Optional, Tuple

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import Retry
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
    r = session.get(url)

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
        self.number_challenges = None
        self.number_users = None
        session = Session()
        retry = Retry(
            total=10,
            backoff_factor=1,
            status_forcelist=[429],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=100, pool_block=True)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        self.session = session
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
        r = self.session.post(url, data=payload)

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
        r = self.session.get(url)
        data = json.loads(r.content)
        count = 0
        while data[-1]['rel'] != 'previous':
            count += 50
            url = f'{self.api_url}/challenges?debut_challenges={count}'
            log.log(logging.INFO, f'http_get', extra=dict(url=url))
            r = self.session.get(url)
            data = json.loads(r.content)
        self.number_challenges = count + len(data[0])

    def update_number_rootme_users(self, mini=0, maxi=10 ** 6) -> None:
        count = (mini + maxi) // 2
        count += 1

        url = f'{self.api_url}/auteurs?debut_auteurs={count}'
        log.log(logging.INFO, f'http_get', extra=dict(url=url, count=count, mini=mini, maxi=maxi))
        r = self.session.get(url)
        data = json.loads(r.content)

        url = f'{self.api_url}/auteurs?debut_auteurs={count - 1}'
        log.log(logging.INFO, f'http_get', extra=dict(url=url, count=count - 1, mini=mini, maxi=maxi))
        r = self.session.get(url)
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

        url = f'{self.api_url}/?page=recherche&recherche={username}'
        content = self.http_get(url)
        tree = html.fromstring(content)
        user_profile_urls = tree.xpath(
            f'//div[@class="t-body tb-padding"]/ul/li/a[contains(@text, "{username}")]/@href'
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
