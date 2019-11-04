import hashlib
import os
from typing import Dict

from src.static_badge import make_static_badges
from src.http_client import http_get


def _create_folder(name: str) -> str:
    folder_name = hashlib.md5(name.encode()).hexdigest()
    folder_path = f'{os.environ.get("STORAGE_FOLDER")}/{folder_name}'
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    return folder_path


def _download_avatar(folder_path: str, avatar_url: str) -> None:
    content = http_get(avatar_url)
    f = open(f'{folder_path}/avatar.jpg', 'wb')
    f.write(content)
    f.close()


def make_storage(data: Dict) -> None:
    name = data['name']
    folder_path = _create_folder(name)
    avatar_url = data['avatar_url']
    _download_avatar(folder_path, avatar_url)
    make_static_badges(data, folder_path)
