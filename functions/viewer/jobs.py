"""Processing jobs started from the library, one at a time (others queue), at most one per paper.

A job is a list of steps, each a project script (`digest.sh -n PDF`, `annotate.sh -n FOLDER [--only PART]`);
the first failing step ends the job. Output lines are kept in memory for the SSE log stream and written to
<log_dir>/<timestamp>.log (the paper's .work/viewer/jobs/, or <out_root>/.paper-jobs/ for a paper not prepared yet).
Environment: PAPER_VIEWER_JOB_CMD replaces the scripts (tests use a stub; the script name and its arguments are
appended).
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

Step = tuple[str, list[str]]     # (script in scripts/, arguments)


def command(script: str, args: list[str]) -> list[str]:
    override = os.environ.get("PAPER_VIEWER_JOB_CMD")
    return shlex.split(override) + [script, *args] if override else [str(ROOT / "scripts" / script), *args]


@dataclass
class Job:
    id: str
    key: str                        # paper id
    action: str
    steps: list[Step]
    log_dir: Path
    env: dict[str, str] = field(default_factory=dict)   # extra environment for the steps (agent model / effort)
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

    def submit(self, key: str, action: str, steps: list[Step], log_dir: Path, env: dict[str, str] | None = None) -> Job:
        """Queue a job for the paper, or return its job that is still queued or running (whatever its action)."""
        with self._lock:
            for job in self._jobs.values():
                if job.key == key and not job.finished:
                    return job
            job = Job(id=uuid.uuid4().hex[:12], key=key, action=action, steps=steps, log_dir=log_dir, env=env or {})
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

    def _emit(self, job: Job, log, line: str) -> None:
        job.lines.append(line.rstrip("\n"))
        log.write(line if line.endswith("\n") else line + "\n")
        log.flush()

    def _run(self, job: Job) -> None:
        job.log_dir.mkdir(parents=True, exist_ok=True)
        job.status = "running"
        with open(job.log_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{job.action}.log", "w", encoding="utf-8") as log:
            if job.env:
                self._emit(job, log, "[job] " + "  ".join(f"{k}={v}" for k, v in sorted(job.env.items())))
            for i, (script, args) in enumerate(job.steps, 1):
                self._emit(job, log, f"[job] step {i}/{len(job.steps)}: {script} {shlex.join(args)}")
                try:
                    job.proc = subprocess.Popen(command(script, args), cwd=ROOT, env={**os.environ, **job.env},
                                                stdin=subprocess.DEVNULL,
                                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    for line in job.proc.stdout:
                        self._emit(job, log, line)
                    job.returncode = job.proc.wait()
                except OSError as e:
                    self._emit(job, log, f"[job] could not start: {e}")
                    job.returncode = -1
                if job.returncode != 0:
                    break
        job.status = "done" if job.returncode == 0 else "failed"

    def shutdown(self) -> None:
        """Terminate the running subprocess (server shutdown)."""
        for job in self._jobs.values():
            if job.proc and job.proc.poll() is None:
                job.proc.terminate()


JOBS = Jobs()
