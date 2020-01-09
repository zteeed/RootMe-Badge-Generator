import json
import logging
import os
from typing import Optional

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from lxml import html


class HTTPBadStatusCodeError(RuntimeError):
    def __init__(self, code: int):
        super().__init__(f'bad http status code {code}')


session = Session()


def http_get_url(session: Session, url: str) -> Optional[bytes]:
    """
    Retrieves the HTML from a page via HTTP(s).
    If the page is present on the server (200 status code), returns the html.
    If the server does not host this page (404 status code), returns None.
    Any other HTTP code are considered as unexpected and raise an HTTPBadStatusCodeError.
    :param session: requests session object
    :param url: url to the page
    :return: HTML of the page or None
    """
    r = session.get(url)

    if r.status_code == 200:
        logging.debug(f'http_get_success', status_code=r.status_code, url=url)
        return r.content

    if r.status_code == 404:
        logging.info(f'http_get_error', status_code=r.status_code, url=url)
        return None

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
        account_username = os.environ.get('ROOTME_ACCOUNT_USERNAME')
        account_password = os.environ.get('ROOTME_ACCOUNT_PASSWORD')
        self.authenticate(account_username, account_password)
        self.update_number_rootme_challenges()
        self.update_number_rootme_users()

    def authenticate(self, username: str, password: str) -> None:
        payload = {
            "login": username,
            "password": password,
        }
        r = self.session.post(f'{self.api_url}/login', data=payload)

        if r.status_code != 200:
            logging.debug(f'Authentication failed', status_code=r.status_code, url=self.api_url, payload=payload)
            raise HTTPBadStatusCodeError(r.status_code)

        logging.debug(f'Authentication successful', status_code=r.status_code, url=self.api_url)
        response = json.loads(r.content)[0]
        # Note that domain keyword parameter is the only optional parameter here
        cookie_obj = requests.cookies.create_cookie(
            domain=self.api_url,
            name='spip_session',
            value=str(response["info"]["spip_session"])
        )
        self.session.cookies.set_cookie(cookie_obj)
        logging.debug(f'New cookie added for RM API', cookie_obj=cookie_obj)

    def update_number_rootme_challenges(self) -> None:
        r = self.session.get(f'{self.api_url}/challenges')
        data = json.loads(r.content)
        count = 0
        while data[-1]['rel'] != 'previous':
            count += 50
            r = self.session.get(f'{self.api_url}/challenges?debut_challenges={count}')
            data = json.loads(r.content)
        self.number_challenges = count + len(data[0])

    def update_number_rootme_users(self) -> None:
        r = self.session.get(f'{self.api_url}/auteurs')
        data = json.loads(r.content)
        count = 2860 * 50  # offset
        while data[-1]['rel'] != 'previous':
            count += 50
            r = self.session.get(f'{self.api_url}/auteurs?debut_auteurs={count}')
            data = json.loads(r.content)
        self.number_users = count + len(data[0])

    def http_get(self, url):
        return http_get_url(self.session, url)

    def get_user_info(self, username: str):
        url = f'{self.api_url}/auteurs?nom={username}'
        return self.http_get(url)

    def get_user_data(self, id_user: int):
        url = f'{self.api_url}/auteurs/{id_user}'
        return self.http_get(url)

    def get_score_existing_user(self, id_user: int):
        content = self.get_user_data(id_user)
        if content is None:
            return 0
        data = json.loads(content)
        return int(data['score'])

    def get_avatar_url(self, username: str, id_user: int) -> str:
        url = f'{self.api_url}/{username}-{id_user}'
        content = self.http_get(url)
        if content is None:
            url = f'{self.api_url}/{username}'
            content = self.http_get(url)
        tree = html.fromstring(content)
        result = tree.xpath('//h1/img[@itemprop="image"]/@src')
        return f'{self.api_url}/{result[0]}'

    def get_rank(self, username: str, id_user: int) -> str:
        url = f'{self.api_url}/{username}-{id_user}?inc=score'
        content = self.http_get(url)
        if content is None:
            url = f'{self.api_url}/{username}?inc=score'
            content = self.http_get(url)
        tree = html.fromstring(content)
        div_result = tree.xpath('//div[@class="row text-center"]/div[@class="small-12 medium-4 columns"]')
        if not div_result:
            return 'newbie'
        return div_result[-1].xpath('span[@class="color1 txxl"]/text()')[0].strip()

