import hashlib
import os
from typing import Dict
import magic

from src.static_badge import make_static_badges
from src.http_client import http_get


def _create_folder(name: str) -> str:
    folder_name = hashlib.md5(name.encode()).hexdigest()
    folder_path = f'{os.environ.get("STORAGE_FOLDER")}/{folder_name}'
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    return folder_path


def _download_avatar(folder_path: str, avatar_url: str) -> str:
    content = http_get(avatar_url)
    file_type = magic.from_buffer(content, mime=True)
    extension = file_type.split('/')[-1]
    avatar_path = f'{folder_path}/avatar.{extension}'
    f = open(avatar_path, 'wb')
    f.write(content)
    f.close()
    return avatar_path


def make_storage(data: Dict) -> None:
    name = data['name']
    folder_path = _create_folder(name)
    avatar_url = data['avatar_url']
    avatar_path = _download_avatar(folder_path, avatar_url)
    make_static_badges(data, folder_path, avatar_path)
