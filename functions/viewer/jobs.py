"""Preprocessing jobs started from the library: `scripts/annotate.sh -n <folder>`, one at a time, others queue.

Output lines are kept in memory for the SSE log stream and written to <paper>/.work/viewer/jobs/<timestamp>.log.
Environment: PAPER_VIEWER_ANNOTATE_CMD replaces the command (tests use a stub; the folder is appended).
"""
import os
import queue
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from functions.prepare import ROOT
from functions.verify import WORK_DIR


def command() -> list[str]:
    override = os.environ.get("PAPER_VIEWER_ANNOTATE_CMD")
    return shlex.split(override) if override else [str(ROOT / "scripts" / "annotate.sh"), "-n"]


@dataclass
class Job:
    id: str
    folder: Path
    status: str = "queued"          # queued | running | done | failed
    lines: list[str] = field(default_factory=list)
    returncode: int | None = None
    proc: subprocess.Popen | None = None

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed")


class Jobs:
    def __init__(self):
        self._queue: queue.Queue[Job] = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def submit(self, folder: Path) -> Job:
        """Queue a job for the folder, or return its job that is still queued or running."""
        with self._lock:
            for job in self._jobs.values():
                if job.folder == folder and not job.finished:
                    return job
            job = Job(id=uuid.uuid4().hex[:12], folder=folder)
            self._jobs[job.id] = job
            self._queue.put(job)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._loop, daemon=True)
                self._worker.start()
            return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _loop(self) -> None:
        while True:
            self._run(self._queue.get())

    def _run(self, job: Job) -> None:
        log_dir = job.folder / WORK_DIR / "viewer" / "jobs"
        log_dir.mkdir(parents=True, exist_ok=True)
        job.status = "running"
        with open(log_dir / f"{time.strftime('%Y%m%d-%H%M%S')}.log", "w", encoding="utf-8") as log:
            try:
                job.proc = subprocess.Popen(command() + [str(job.folder)], cwd=ROOT, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in job.proc.stdout:
                    job.lines.append(line.rstrip("\n"))
                    log.write(line)
                    log.flush()
                job.returncode = job.proc.wait()
            except OSError as e:
                job.lines.append(f"[job] could not start: {e}")
                job.returncode = -1
        job.status = "done" if job.returncode == 0 else "failed"

    def shutdown(self) -> None:
        """Terminate the running subprocess (server shutdown)."""
        for job in self._jobs.values():
            if job.proc and job.proc.poll() is None:
                job.proc.terminate()


JOBS = Jobs()
