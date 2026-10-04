"""Local web server for the Paper Viewer: REST API under /api plus the built frontend (web/dist).

Binds to 127.0.0.1 only (scripts/viewer.sh). Files are served only from paper folders found by scanning the
output root; paths that resolve outside their paper folder are refused. API: docs/viewer-plan.md §9.

Environment: PAPER_VIEWER_OUT and PAPER_VIEWER_SRC override the output root and src/ (tests use temporary ones).
"""
import hashlib
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from functions.build_viewer import ensure_viewer, viewer_root
from functions.papers import PaperEntry, find_pdf, is_evicted, viewer_cfg
from functions.prepare import SRC_DIR
from functions.registry import library
from functions.verify import WORK_DIR
from functions.viewer.jobs import JOBS, Step

DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
PDFJS = Path(__file__).resolve().parents[2] / "web" / "node_modules" / "pdfjs-dist"
PDFJS_KINDS = {"standard_fonts", "cmaps", "wasm", "iccs"}
PDFJS_NAME_RE = re.compile(r"^[\w.\-]+$")
FIG_ID_RE = re.compile(r"^fig-p\d+-u?\d+$")
MAX_DPI = 300
NO_BUILD_HTML = """<!doctype html><meta charset="utf-8"><title>Paper Viewer</title>
<p style="font-family:sans-serif">The viewer frontend is not built yet. Run <code>scripts/setup.sh</code> (needs Node &ge; 20).</p>"""

@asynccontextmanager
async def _lifespan(_: FastAPI):
    yield
    JOBS.shutdown()


app = FastAPI(title="Paper Viewer", docs_url=None, redoc_url=None, lifespan=_lifespan)
_papers: dict[str, PaperEntry] = {}


@app.exception_handler(HTTPException)
async def _error(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail, "detail": None}, status_code=exc.status_code)


def viewer_src() -> Path:
    return Path(os.environ.get("PAPER_VIEWER_SRC") or SRC_DIR).resolve()


def _rescan() -> list[PaperEntry]:
    """Output folders and new src/ PDFs, via the registry (which this also brings up to date)."""
    entries = library(viewer_root(), viewer_src())
    _papers.clear()
    _papers.update({e.id: e for e in entries})
    return entries


def _entry(pid: str) -> PaperEntry:
    if pid not in _papers:
        _rescan()
    if pid not in _papers:
        raise HTTPException(404, "unknown paper")
    return _papers[pid]


def _folder(pid: str) -> Path:
    e = _entry(pid)
    if e.status == "new":
        raise HTTPException(409, "the paper is not prepared yet; run the summary first")
    folder = Path(e.folder)
    if is_evicted(folder):
        raise HTTPException(409, "the PDF is not downloaded from iCloud (evicted)")
    return folder


def _inside(path: Path | None, folder: Path) -> Path:
    """The resolved path, if it exists and stays inside the paper folder (no symlink or '..' escape)."""
    if path is None:
        raise HTTPException(404, "not found")
    real = path.resolve()
    if not real.is_file() or folder.resolve() not in real.parents:
        raise HTTPException(404, "not found")
    return real


@app.get("/api/papers")
def papers():
    return [e.to_dict() for e in _rescan()]


@app.get("/api/config")
def config():
    cfg = viewer_cfg()
    return {k: cfg[k] for k in ("target_lang", "llm_backend")}


@app.get("/api/papers/{pid}/viewer.json")
def viewer_json(pid: str):
    folder = _folder(pid)
    return FileResponse(ensure_viewer(folder, viewer_root()), media_type="application/json")


@app.get("/api/papers/{pid}/pdf")
def pdf(pid: str):
    folder = _folder(pid)
    return FileResponse(_inside(find_pdf(folder), folder), media_type="application/pdf")   # Range requests -> 206


@app.get("/api/papers/{pid}/figures/{fid}.png")
def figure(pid: str, fid: str):
    folder = _folder(pid)
    if not FIG_ID_RE.match(fid):
        raise HTTPException(404, "not found")
    return FileResponse(_inside(folder / WORK_DIR / "layout" / "figures" / f"{fid}.png", folder), media_type="image/png")


@app.get("/api/papers/{pid}/crop")
def crop(pid: str, page: int, bbox: str, dpi: int = 200):
    folder = _folder(pid)
    try:
        rect = pymupdf.Rect([float(v) for v in bbox.split(",")])
    except ValueError:
        raise HTTPException(400, "bbox must be x0,y0,x1,y1")
    if not 36 <= dpi <= MAX_DPI:
        raise HTTPException(400, f"dpi must be 36..{MAX_DPI}")
    doc = pymupdf.open(_inside(find_pdf(folder), folder))
    if not 1 <= page <= len(doc):
        raise HTTPException(400, "page out of range")
    bounds = doc[page - 1].rect + (-0.5, -0.5, 0.5, 0.5)
    if rect.is_empty or not bounds.contains(rect):
        raise HTTPException(400, "bbox outside the page")
    key = hashlib.sha1(f"{page}|{','.join(f'{v:.2f}' for v in rect)}|{dpi}".encode()).hexdigest()[:16]
    out = folder / WORK_DIR / "layout" / "crops" / f"{key}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        doc[page - 1].get_pixmap(clip=rect & doc[page - 1].rect, dpi=dpi).save(out)
    return FileResponse(out, media_type="image/png")


ANNOTATE_PARTS = ("translation", "highlights", "figures")


class RunRequest(BaseModel):
    action: Literal["all", "digest", "translation", "highlights", "figures"]


def _steps(e: PaperEntry, action: str) -> list[Step]:
    """all: summary (unless it passed) then every missing annotation part; otherwise the one script it names."""
    if action in ANNOTATE_PARTS:
        return [("annotate.sh", ["-n", e.folder, "--only", action])]
    digest = ("digest.sh", ["-n", e.source or str(find_pdf(Path(e.folder)))])
    if action == "digest":
        return [digest]
    # a new paper has no folder yet: annotate.sh finds the one the digest made from the PDF (via the registry)
    return ([digest] if e.digest_verify != "PASS" else []) + [("annotate.sh", ["-n", e.folder or e.source])]


@app.post("/api/papers/{pid}/run")
def run(pid: str, req: RunRequest):
    e = _entry(pid)
    if e.status != "new":
        _folder(pid)            # refuses evicted papers
    if req.action in ANNOTATE_PARTS and e.status == "new":
        raise HTTPException(409, "the paper is not prepared yet; run the summary first")
    if req.action == "digest" and e.digest_verify == "PASS":
        raise HTTPException(409, "the summary is already done (verify PASS)")
    log_dir = Path(e.folder) / WORK_DIR / "viewer" / "jobs" if e.folder else viewer_root() / ".paper-jobs"
    job = JOBS.submit(pid, req.action, _steps(e, req.action), log_dir)
    return {"job_id": job.id, "status": job.status, "action": job.action}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: str):
    """SSE: `log` per output line, `status` on changes, `done` at the end."""
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")

    def stream():
        sent, status = 0, None
        while True:
            finished = job.finished       # read before the lines so no line is missed at the end
            lines = job.lines[sent:]
            for line in lines:
                yield _sse("log", {"text": line})
            sent += len(lines)
            if job.status != status:
                status = job.status
                yield _sse("status", {"status": status})
            if finished:
                yield _sse("done", {"status": job.status, "returncode": job.returncode})
                return
            time.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---- frontend (single-page app: / and /r/<id> both serve index.html)
@app.get("/pdfjs/{kind}/{name}", include_in_schema=False)
def pdfjs_data(kind: str, name: str):
    """pdf.js data files (standard fonts, CMaps, wasm decoders, ICC profiles) from the installed pdfjs-dist."""
    if kind not in PDFJS_KINDS or not PDFJS_NAME_RE.match(name):
        raise HTTPException(404, "not found")
    path = PDFJS / kind / name
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path)


if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "not found")
    index = DIST / "index.html"
    return FileResponse(index) if index.is_file() else HTMLResponse(NO_BUILD_HTML)
