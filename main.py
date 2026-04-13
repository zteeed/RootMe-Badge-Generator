import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from werkzeug.utils import secure_filename

from logging_config import setup_logging
from src.http_client import HTTPBadStatusCodeError, RMAPI
from src.parser import extract_data, extract_info_username_input
from src.storage import make_storage, make_storage_js

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DAILY_REFRESH_INTERVAL = 24 * 60 * 60

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["static_url"] = lambda f: "/static/" + f.lstrip("/")


# ---------------------------------------------------------------------------
# Scheduled background tasks (pure asyncio, no threads)
# ---------------------------------------------------------------------------

async def _daily_refresh(app_instance: FastAPI) -> None:
    while True:
        await asyncio.sleep(DAILY_REFRESH_INTERVAL)
        rm_api = app_instance.state.api
        if rm_api is None:
            continue
        try:
            await asyncio.to_thread(rm_api.update_number_rootme_challenges)
            await asyncio.to_thread(rm_api.update_number_rootme_users)
            log.info("Daily stats refresh completed")
        except Exception:
            log.exception("Daily stats refresh failed")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting RootMe Badge Generator")
    app.state.api = None
    app.state.api_error = None

    try:
        rm_api = await asyncio.to_thread(RMAPI)
        app.state.api = rm_api
        log.info("Root-Me API client initialized")
    except Exception as exc:
        log.exception("Root-Me API client init failed")
        app.state.api_error = str(exc)

    refresh_task = asyncio.create_task(_daily_refresh(app))
    yield
    refresh_task.cancel()
    log.info("Application shutdown")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="RootMe Badge Generator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _render_index(request: Request, messages: Optional[list] = None):
    return templates.TemplateResponse(request, "index.html", {"messages": messages or []})


def _render_error(request: Request, message: str):
    return _render_index(request, [("error", message)])


def _get_api_or_error(request: Request):
    rm_api = request.app.state.api
    if rm_api is not None:
        return rm_api, None
    details = request.app.state.api_error
    msg = "Service is starting and connecting to Root-Me API. Please retry in a few seconds."
    if details:
        msg = f"{msg} Last error: {details}"
    return None, _render_error(request, msg)


# ---------------------------------------------------------------------------
# Badge generation logic
# ---------------------------------------------------------------------------

def _fetch_user_data(rm_api: RMAPI, username: str, id_auteur: int) -> dict:
    auteurs_url = f"{rm_api.api_url}/auteurs/{id_auteur}"
    content = rm_api.http_get(auteurs_url)
    if content is None:
        return {
            "nom": username,
            "position": rm_api.number_users,
            "score": 0,
            "validations": [],
        }
    return json.loads(content)


def _render_badge(request: Request, data: dict, save_paths: list, js_file_path):
    return templates.TemplateResponse(
        request,
        "badge.html",
        {
            "data": data,
            "save_paths": save_paths,
            "js_file_path": js_file_path,
            "messages": [],
        },
    )


def _handle_badge_request(request: Request, rm_api: RMAPI, username: str):
    url = os.environ.get("URL")

    username, id_auteur, flash_message, flash_type = extract_info_username_input(username, rm_api)
    if flash_message is not None:
        return _render_index(request, [(flash_type, flash_message)])

    raw_data = _fetch_user_data(rm_api, username, id_auteur)
    data = extract_data(raw_data, id_auteur, rm_api, url)

    save_paths, folder_path, avatar_path = make_storage(rm_api, data)
    data["avatar_url"] = f"{url}/{avatar_path}"

    dynamic_js_badge = templates.env.get_template("dynamic-js-badge.html").render(data=data)
    js_file_path = make_storage_js(dynamic_js_badge, folder_path)

    return _render_badge(request, data, save_paths, js_file_path)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index_get(request: Request):
    return _render_index(request)


@app.post("/", response_class=HTMLResponse)
async def index_post(request: Request, username: Optional[str] = Form(None)):
    if username is None:
        return _render_error(request, "A wrong form has been sent.")

    username = username.strip()
    if not username:
        return _render_error(request, "Username is empty")

    rm_api, error_response = _get_api_or_error(request)
    if error_response:
        return error_response

    try:
        return _handle_badge_request(request, rm_api, username)
    except HTTPBadStatusCodeError as err:
        if err.code == 429:
            msg = (
                "Root-Me API rate limit (HTTP 429). Add ROOTME_API_KEY from your account preferences "
                "(see api.www.root-me.org docs), increase ROOTME_MIN_REQUEST_INTERVAL_SEC, or retry later."
            )
        else:
            msg = f"Root-Me API error (HTTP {err.code})."
        return _render_error(request, msg)
    except ValueError as err:
        return _render_error(request, str(err))


@app.get("/storage_server/{filename}")
async def serve_files(filename: str):
    filename = secure_filename(filename)
    path = BASE_DIR / "storage_server" / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/storage_clients/{folder}/{filename}")
async def serve_files_clients(folder: str, filename: str):
    folder = secure_filename(folder)
    filename = secure_filename(filename)
    path = BASE_DIR / "storage_clients" / folder / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    media_type = "text/javascript" if filename == "badge.js" else None
    return FileResponse(path, media_type=media_type)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=80)
