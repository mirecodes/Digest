"""Local web server for the Paper Viewer: REST API under /api plus the built frontend (web/dist).

Binds to 127.0.0.1 only (scripts/viewer.sh). Files are served only from paper folders found by scanning the
output root; paths that resolve outside their paper folder are refused. API: docs/viewer-plan.md §9.

Environment: PAPER_VIEWER_OUT and PAPER_VIEWER_SRC override the output root and src/ (tests use temporary ones).
"""
import hashlib
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from functions.build_viewer import ensure_viewer, viewer_root
from functions.papers import MODEL_RE, PaperEntry, agent_cfg, find_pdf, is_evicted, viewer_cfg
from functions.prepare import SRC_DIR
from functions.registry import library
from functions.verify import WORK_DIR
from functions.viewer.jobs import JOBS, PREPARER, Step, parallel

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
    JOBS.restore(viewer_root() / ".paper-jobs" / "jobs.json")     # jobs cut off by the last stop come back
    _rescan()                                                       # starts preparing the new src/ PDFs
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
    """Output folders and new src/ PDFs, via the registry (which this also brings up to date). While no job runs,
    output folders are first moved to mirror src/ (a move under a running job would break it). New PDFs are then
    prepared in the background (PREPARER)."""
    entries = library(viewer_root(), viewer_src(), move=not JOBS.busy() and not PREPARER.state["running"])
    _papers.clear()
    _papers.update({e.id: e for e in entries})
    # prepare.sh writes into cfg.yaml's out_dir: with another root (PAPER_VIEWER_OUT, tests) only a stub may run
    if not os.environ.get("PAPER_VIEWER_OUT") or os.environ.get("PAPER_VIEWER_JOB_CMD"):
        PREPARER.start({e.sha: e.source for e in entries if e.status == "new" and e.sha and e.source})
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


@app.get("/api/health")
def health():
    """Identifies a running viewer, so scripts/viewer.sh can replace a leftover one instead of failing on the port."""
    return {"app": "paper-viewer", "pid": os.getpid()}


@app.get("/api/config")
def config():
    cfg = viewer_cfg()
    agent = agent_cfg()
    return {**{k: cfg[k] for k in ("target_lang", "llm_backend")}, "parallel": parallel(),
            "agent": {k: agent[k] for k in ("backend", "model", "effort", "models", "efforts")}}


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


# library action -> annotate.sh --only parts
ANNOTATE_PARTS = {"translation": "translation", "annotation": "highlights,figures"}


class RunRequest(BaseModel):
    action: Literal["all", "digest", "translation", "annotation"]
    model: str = ""             # "" = agent.model in cfg.yaml
    effort: str = ""            # "" = agent.effort in cfg.yaml
    resume: bool = False        # continue an interrupted or failed run: keep the work already done


def _agent_env(req: RunRequest) -> dict[str, str]:
    """The run's model / effort as the environment scripts/internal/agent.sh reads; both reach a command line."""
    env = {}
    if req.model:
        if not MODEL_RE.match(req.model):
            raise HTTPException(400, f"invalid model name {req.model!r}")
        env["PAPER_AGENT_MODEL"] = req.model
    if req.effort:
        efforts = agent_cfg()["efforts"]
        if req.effort not in efforts:
            raise HTTPException(400, f"effort must be one of {efforts}" if efforts else "this backend has no effort setting")
        env["PAPER_AGENT_EFFORT"] = req.effort
    return env


def _steps(e: PaperEntry, action: str, resume: bool = False) -> list[Step]:
    """Every job starts by preparing the paper (copy the PDF, extract the text, register it; instant when done), so
    each action runs on its own. all: summary (unless it passed), then every missing annotation part.
    resume: the agent steps get --resume (keep what an interrupted run already finished)."""
    pdf = e.source or str(find_pdf(Path(e.folder)))
    steps: list[Step] = [("internal/prepare.sh", ["--ensure", "-n", pdf])]
    # a new paper has no folder yet: annotate.sh finds the one prepare made from the PDF (via the registry)
    target = e.folder or pdf
    more = ["--resume"] if resume else []
    if action in ANNOTATE_PARTS:
        return steps + [("annotate.sh", ["-n", target, "--only", ANNOTATE_PARTS[action], *more])]
    if action == "digest" or e.digest_verify != "PASS":
        steps.append(("digest.sh", ["-n", pdf, *more]))
    if action == "all":
        steps.append(("annotate.sh", ["-n", target, *more]))
    return steps


@app.post("/api/papers/{pid}/run")
def run(pid: str, req: RunRequest):
    e = _entry(pid)
    if e.status != "new":
        _folder(pid)            # refuses evicted papers
    if req.action == "digest" and e.digest_verify == "PASS":
        raise HTTPException(409, "the summary is already done (verify PASS)")
    log_dir = Path(e.folder) / WORK_DIR / "viewer" / "jobs" if e.folder else viewer_root() / ".paper-jobs"
    # keyed by the PDF hash, so the job still finds its paper after the folder is made or moved, or a restart
    job = JOBS.submit(e.sha or pid, req.action, _steps(e, req.action, req.resume), log_dir, _agent_env(req))
    return {"job_id": job.id, "status": job.status, "action": job.action}


JOB_LOG_LINES = 200


@app.get("/api/prepare")
def prepare_state():
    """The background preparing of new src/ PDFs: {running, done, total, current (file name), started (epoch s)}."""
    return PREPARER.state


@app.get("/api/jobs")
def jobs():
    """Every job of this and the last server run (the latest per paper), oldest first, with its last output lines.
    `paper` is the paper's sha (or id); model / effort let the library resume a job as it was started. The library
    polls this: one request for any number of jobs (an SSE stream per job would hit the browser's six connections
    per host)."""
    return [{"id": j.id, "paper": j.key, "action": j.action, "status": j.status, "lines": j.lines[-JOB_LOG_LINES:],
             "model": j.env.get("PAPER_AGENT_MODEL", ""), "effort": j.env.get("PAPER_AGENT_EFFORT", ""),
             "submitted": j.submitted, "started": j.started, "ended": j.ended}
            for j in JOBS.all()]


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
