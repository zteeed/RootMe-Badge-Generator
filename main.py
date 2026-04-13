import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from timeloop import Timeloop
from werkzeug.utils import secure_filename

from logging_config import setup_logging
from src.http_client import HTTPBadStatusCodeError, RMAPI
from src.parser import extract_data, extract_info_username_input
from src.storage import make_storage, make_storage_js

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
URL = os.environ.get("URL")
tl = Timeloop()
api: Optional[RMAPI] = None


def static_url(filename: str) -> str:
    return "/static/" + filename.lstrip("/")


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["static_url"] = static_url


@tl.job(interval=timedelta(days=1))
def update_number_rootme_challenges() -> None:
    api.update_number_rootme_challenges()


@tl.job(interval=timedelta(days=1))
def update_number_rootme_users() -> None:
    api.update_number_rootme_users()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global api
    log.info("Starting RootMe Badge Generator (FastAPI)")
    api = RMAPI()
    app.state.api = api
    tl.start(block=False)
    log.info("Timeloop started (daily Root-Me stats refresh)")
    yield
    log.info("Application shutdown")


app = FastAPI(title="RootMe Badge Generator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def index_get(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "messages": []},
    )


@app.post("/", response_class=HTMLResponse)
async def index_post(request: Request, username: Optional[str] = Form(None)):
    if username is None:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "messages": [("error", "A wrong form has been sent.")],
            },
        )

    username = (username or "").strip()
    if not username:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "messages": [("error", "Username is empty")]},
        )

    rm_api = request.app.state.api
    try:
        username, id_auteur, flash_message, flash_type = extract_info_username_input(
            username, rm_api
        )
        if flash_message is not None and flash_type is not None:
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "messages": [(flash_type, flash_message)]},
            )

        auteurs_url = f"{rm_api.api_url}/auteurs/{id_auteur}"
        content = rm_api.http_get(auteurs_url)
        if content is None:
            data = {
                "nom": username,
                "position": rm_api.number_users,
                "score": 0,
                "validations": [],
            }
        else:
            data = json.loads(content)
        data = extract_data(data, id_auteur, rm_api, URL)

        save_paths, folder_path, avatar_path = make_storage(rm_api, data)
        data["avatar_url"] = f"{URL}/{avatar_path}"
        dynamic_js_badge = templates.env.get_template("dynamic-js-badge.html").render(
            data=data
        )
        js_file_path = make_storage_js(dynamic_js_badge, folder_path)
        return templates.TemplateResponse(
            "badge.html",
            {
                "request": request,
                "data": data,
                "save_paths": save_paths,
                "js_file_path": js_file_path,
                "messages": [],
            },
        )
    except HTTPBadStatusCodeError as err:
        if err.code == 429:
            msg = (
                "Root-Me API rate limit (HTTP 429). Add ROOTME_API_KEY from your account preferences "
                "(see api.www.root-me.org docs), increase ROOTME_MIN_REQUEST_INTERVAL_SEC, or retry later."
            )
        else:
            msg = f"Root-Me API error (HTTP {err.code})."
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "messages": [("error", msg)]},
        )
    except ValueError as err:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "messages": [("error", str(err))]},
        )


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
    media_type = None
    if filename == "badge.js":
        media_type = "text/javascript"
    return FileResponse(path, media_type=media_type)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=80)
