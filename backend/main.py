"""Strata Week 1 backend.

POST /analyze        -> save upload, kick off a background job, return job_id now
GET  /analyze/{id}   -> poll: "processing" until done, then the full result JSON

Jobs are tracked in an in-memory dict (Week 1; swap for Redis in Week 3+).
"""

import os
import tempfile
import threading
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analyzer import run_analysis

app = FastAPI(title="Strata", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the Vercel origin before deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_EXT = {".mp3", ".wav"}

jobs: dict[str, dict] = {}  # job_id -> {status, result, error}
_jobs_lock = threading.Lock()


@app.get("/")
def health():
    return {"status": "ok", "service": "strata"}


@app.post("/analyze")
async def analyze(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, "Only MP3 or WAV files are accepted.")

    job_id = uuid.uuid4().hex[:12]
    path = os.path.join(tempfile.gettempdir(), f"strata_{job_id}{ext}")

    # Stream to disk with a hard size cap so a huge upload can't exhaust memory.
    size = 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "File exceeds the 20MB limit.")
                out.write(chunk)
    except HTTPException:
        if os.path.exists(path):
            os.remove(path)
        raise

    with _jobs_lock:
        jobs[job_id] = {"status": "processing", "result": None, "error": None}

    background_tasks.add_task(_process, job_id, path)
    return {"job_id": job_id, "status": "processing"}


@app.get("/analyze/{job_id}")
def get_result(job_id: str):
    with _jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job_id.")
    if job["status"] == "processing":
        return {"job_id": job_id, "status": "processing"}
    if job["status"] == "error":
        return {"job_id": job_id, "status": "error", "error": job["error"]}
    return {"job_id": job_id, "status": "complete", **job["result"]}


def _process(job_id: str, path: str):
    """Runs in a threadpool (sync def) so it never blocks the event loop."""
    try:
        result = run_analysis(path)
        with _jobs_lock:
            jobs[job_id] = {"status": "complete", "result": result, "error": None}
    except Exception as exc:  # surface the failure to the poller
        with _jobs_lock:
            jobs[job_id] = {"status": "error", "result": None, "error": str(exc)}
    finally:
        if os.path.exists(path):
            os.remove(path)
