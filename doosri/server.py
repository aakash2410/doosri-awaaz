"""Web app: Prepare (Claude drafts and scores a pack), Review (a person edits
and approves it), the classroom simulator (runs offline in the browser), and
the next-day note (Claude, from a session log).

  uvicorn doosri.server:app --reload
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import store
from .audio import render_pack_audio
from .checks import check_pack
from .claude import ClaudeError
from .prepare import LANGUAGES, prepare
from .report import check_note, write_note
from .schema import Pack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
WEB = Path(__file__).resolve().parent.parent / "web"
# Claude calls per client IP per hour on a public demo.
CLAUDE_CALLS_PER_HOUR = int(os.environ.get("DOOSRI_CLAUDE_CALLS_PER_HOUR", "6"))
# Sample packs that visitors to a public demo can run but not edit or re-approve.
LOCKED = set(filter(None, os.environ.get("DOOSRI_LOCKED_PACKS", "").split(",")))

app = FastAPI(title="Doosri Awaaz")
_calls: dict = defaultdict(deque)
_lock = threading.Lock()


def _limit(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    now = time.time()
    with _lock:
        q = _calls[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= CLAUDE_CALLS_PER_HOUR:
            raise HTTPException(429, "Demo limit reached for this hour. The sample packs still work.")
        q.append(now)


def _findings(pack: Pack) -> list:
    return [f.__dict__ for f in check_pack(pack)]


@app.exception_handler(ClaudeError)
def _claude_error(_, exc: ClaudeError):
    return JSONResponse({"detail": str(exc)}, status_code=502)


class PrepareIn(BaseModel):
    source_text: str = Field(min_length=40, max_length=12000)
    grade: int = Field(ge=1, le=3)
    subject: str = Field(min_length=2, max_length=60)
    source_ref: str = Field(min_length=2, max_length=200)
    home_language: str = "mr"
    n_items: int = Field(default=5, ge=3, le=6)


@app.post("/api/prepare")
def api_prepare(body: PrepareIn, request: Request):
    if body.home_language not in LANGUAGES:
        raise HTTPException(400, "unknown home language")
    _limit(request)
    pack, findings = prepare(body.source_text, grade=body.grade, subject=body.subject,
                             source_ref=body.source_ref, home_language=body.home_language,
                             n_items=body.n_items)
    store.save(pack)
    (store.pack_dir(pack.id) / "source.txt").write_text(body.source_text)
    return {"pack": pack.model_dump(), "findings": [f.__dict__ for f in findings]}


@app.get("/api/packs")
def api_packs():
    return [
        {"id": p.id, "title": p.title, "grade": p.grade, "subject": p.subject, "status": p.status,
         "home_language": p.home_language, "reviewer": p.review.reviewer if p.review else None}
        for p in store.list_packs()
    ]


def _editable(pack_id: str) -> None:
    if pack_id in LOCKED:
        raise HTTPException(403, "This sample pack is locked on the public demo. Prepare a new pack to try review.")


def _load(pack_id: str) -> Pack:
    try:
        return store.load(pack_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "no such pack")


@app.get("/api/packs/{pack_id}")
def api_pack(pack_id: str):
    pack = _load(pack_id)
    return {"pack": pack.model_dump(), "findings": _findings(pack)}


@app.put("/api/packs/{pack_id}")
def api_edit(pack_id: str, body: Pack):
    _editable(pack_id)
    old = _load(pack_id)
    if body.id != old.id:
        raise HTTPException(400, "pack id cannot change")
    # Any edit sends the pack back to draft; the rubric stays as Claude's score of its own draft.
    body.status, body.review, body.rubric = "draft", None, old.rubric
    store.save(body)
    return {"pack": body.model_dump(), "findings": _findings(body)}


class ApproveIn(BaseModel):
    reviewer: str = Field(max_length=80)
    role: str = Field(max_length=80)
    notes: str = Field(default="", max_length=2000)


@app.post("/api/packs/{pack_id}/approve")
def api_approve(pack_id: str, body: ApproveIn):
    _editable(pack_id)
    pack = _load(pack_id)
    try:
        store.approve(pack, reviewer=body.reviewer, role=body.role, notes=body.notes)
    except store.ApprovalError as e:
        raise HTTPException(400, str(e))
    render_pack_audio(pack)
    store.save(pack)
    return {"pack": pack.model_dump(), "findings": _findings(pack)}


class NoteIn(BaseModel):
    pack_id: str
    log: dict
    language: str = "Hindi"


@app.post("/api/note")
def api_note(body: NoteIn, request: Request):
    pack = _load(body.pack_id)
    if not isinstance(body.log.get("items"), list):
        raise HTTPException(400, "log has no items")
    _limit(request)
    note = write_note(body.log, pack, body.language)
    return {"note": note.model_dump(), "problems": check_note(note, body.log)}


@app.get("/packs/{pack_id}/{path:path}")
def pack_file(pack_id: str, path: str):
    base = store.pack_dir(pack_id).resolve()
    target = (base / path).resolve()
    if base not in target.parents or not target.is_file() or target.name == "source.txt":
        raise HTTPException(404)
    return FileResponse(target)


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
