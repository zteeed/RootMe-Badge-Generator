import base64
import hashlib
import os
from typing import Dict, List, Tuple

import magic

from src.http_client import RMAPI
from src.static_badge import make_static_badges


def _create_folder(name: str) -> str:
    storage_folder = os.environ.get('STORAGE_FOLDER')
    folder_name = hashlib.md5(name.encode()).hexdigest()
    folder_path = f'{storage_folder}/{folder_name}'
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    return folder_path


def _download_avatar(api: RMAPI, folder_path: str, avatar_url: str) -> str:
    content = api.http_get(avatar_url)
    file_type = magic.from_buffer(content, mime=True)
    extension = file_type.split('/')[-1]
    avatar_path = f'{folder_path}/avatar.{extension}'
    f = open(avatar_path, 'wb')
    f.write(content)
    f.close()
    return avatar_path


def make_storage(api: RMAPI, data: Dict) -> Tuple[List[Dict[str, str]], str, str]:
    folder_path = _create_folder(data['fullname'])
    avatar_url = data['avatar_url']
    avatar_path = _download_avatar(api, folder_path, avatar_url)
    save_paths = make_static_badges(data, folder_path, avatar_path)
    return save_paths, folder_path, avatar_path


def make_storage_js(dynamic_js_badge: str, folder_path: str) -> str:
    payload = base64.b64encode(dynamic_js_badge.encode()).decode()
    template_string = f'document.write(window.atob("{payload}"))'
    file_path = f'{folder_path}/badge.js'
    f = open(file_path, 'wb')
    f.write(template_string.encode())
    f.close()
    return file_path
