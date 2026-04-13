import base64
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Tuple

import magic

from src.http_client import RMAPI
from src.static_badge import make_static_badges


def _storage_folder() -> Path:
    return Path(os.environ.get("STORAGE_FOLDER", "storage_clients"))


def _create_user_folder(fullname: str) -> Path:
    folder_name = hashlib.md5(fullname.encode()).hexdigest()
    folder_path = _storage_folder() / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def _download_avatar(api: RMAPI, folder_path: Path, avatar_url: str) -> Path:
    content = api.http_get(avatar_url)
    extension = magic.from_buffer(content, mime=True).split("/")[-1]
    avatar_path = folder_path / f"avatar.{extension}"
    avatar_path.write_bytes(content)
    return avatar_path


def make_storage(api: RMAPI, data: Dict) -> Tuple[List[Dict[str, str]], Path, Path]:
    folder_path = _create_user_folder(data["fullname"])
    avatar_path = _download_avatar(api, folder_path, data["avatar_url"])
    save_paths = make_static_badges(data, str(folder_path), str(avatar_path))
    return save_paths, folder_path, avatar_path


def make_storage_js(dynamic_js_badge: str, folder_path: Path) -> Path:
    payload = base64.b64encode(dynamic_js_badge.encode()).decode()
    js_content = f'document.write(window.atob("{payload}"))'
    file_path = folder_path / "badge.js"
    file_path.write_bytes(js_content.encode())
    return file_path
