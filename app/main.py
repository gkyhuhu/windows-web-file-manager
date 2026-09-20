"""FastAPI entrypoint for the Windows-local web file manager."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import files as fm

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Windows Web File Manager",
    description="Single-user local file manager. Bind to 127.0.0.1 only.",
    version="1.0.0",
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RenameBody(BaseModel):
    path: str
    new_name: str = Field(..., min_length=1)


class CopyMoveBody(BaseModel):
    source: str
    dest_dir: str = ""


class MkdirBody(BaseModel):
    parent: str = ""
    name: str = Field(..., min_length=1)


class DeleteBody(BaseModel):
    path: str


class WriteBody(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, FileExistsError):
        return HTTPException(409, str(exc))
    if isinstance(exc, (NotADirectoryError, IsADirectoryError, PermissionError)):
        return HTTPException(400, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(500, "static/index.html missing")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/api/info")
def api_info() -> dict:
    root = fm.get_root()
    return {
        "root": str(root),
        "bind_hint": "127.0.0.1",
        "env": "FILE_MANAGER_ROOT",
    }


@app.get("/api/list")
def api_list(path: str = Query("", description="Relative path under root")) -> dict:
    try:
        return fm.list_dir(path)
    except Exception as e:
        raise _http(e) from e


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1),
    path: str = Query("", description="Search under this relative dir"),
) -> dict:
    try:
        return {"query": q, "results": fm.search_files(q, path)}
    except Exception as e:
        raise _http(e) from e


@app.post("/api/rename")
def api_rename(body: RenameBody) -> dict:
    try:
        return {"ok": True, "entry": fm.rename_item(body.path, body.new_name)}
    except Exception as e:
        raise _http(e) from e


@app.post("/api/copy")
def api_copy(body: CopyMoveBody) -> dict:
    try:
        return {"ok": True, "entry": fm.copy_item(body.source, body.dest_dir)}
    except Exception as e:
        raise _http(e) from e


@app.post("/api/move")
def api_move(body: CopyMoveBody) -> dict:
    try:
        return {"ok": True, "entry": fm.move_item(body.source, body.dest_dir)}
    except Exception as e:
        raise _http(e) from e


@app.post("/api/mkdir")
def api_mkdir(body: MkdirBody) -> dict:
    try:
        return {"ok": True, "entry": fm.mkdir(body.parent, body.name)}
    except Exception as e:
        raise _http(e) from e


@app.post("/api/delete")
def api_delete(body: DeleteBody) -> dict:
    try:
        fm.delete_item(body.path)
        return {"ok": True}
    except Exception as e:
        raise _http(e) from e


@app.get("/api/download")
def api_download(path: str = Query(...)) -> FileResponse:
    try:
        target = fm.safe_resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return FileResponse(
            path=str(target),
            filename=target.name,
            media_type="application/octet-stream",
        )
    except Exception as e:
        raise _http(e) from e


@app.post("/api/upload")
async def api_upload(
    path: str = Query("", description="Destination directory (relative)"),
    file: UploadFile = File(...),
) -> dict:
    try:
        data = await file.read()
        name = file.filename or "upload.bin"
        entry = fm.save_upload(path, name, data)
        return {"ok": True, "entry": entry}
    except Exception as e:
        raise _http(e) from e


@app.get("/api/read")
def api_read(path: str = Query(...)) -> dict:
    try:
        return fm.read_text(path)
    except Exception as e:
        raise _http(e) from e


@app.post("/api/write")
def api_write(body: WriteBody) -> dict:
    try:
        return {"ok": True, "entry": fm.write_text(body.path, body.content, body.encoding)}
    except Exception as e:
        raise _http(e) from e


def main() -> None:
    import uvicorn

    host = os.environ.get("FILE_MANAGER_HOST", "127.0.0.1")
    port = int(os.environ.get("FILE_MANAGER_PORT", "8765"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
