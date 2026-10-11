"""Processing jobs started from the library: up to `parallel` (configs/cfg.yaml, 1..10) run at once, the others
queue in order; at most one per paper.

A job is a list of steps, each a project script (`digest.sh -n PDF`, `annotate.sh -n FOLDER [--only PARTS]`);
the first failing step ends the job. Output lines are kept in memory for the library and written to
<log_dir>/<timestamp>-<action>-<id>.log (the paper's .work/viewer/jobs/, or <out_root>/.paper-jobs/ for a paper not
prepared yet).
The latest job per paper is also saved to a state file (restore(), <out_root>/.paper-jobs/jobs.json), so a job that
was queued or running when the viewer stopped comes back as `interrupted` with its log, ready to be resumed.
Environment: PAPER_VIEWER_JOB_CMD replaces the scripts (tests use a stub; the script name and its arguments are
appended).
"""
import json
import os
import queue
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from functions.prepare import ROOT, load_config

DEFAULT_PARALLEL = 3
MAX_PARALLEL = 10
LOG_TAIL = 200
INTERRUPTED_NOTE = "[job] stopped while running: the viewer was closed. Resume continues where it stopped."
Step = tuple[str, list[str]]     # (script in scripts/, arguments)


def parallel(cfg: dict | None = None) -> int:
    """How many jobs run at once: `parallel` in configs/cfg.yaml, clamped to 1..10."""
    cfg = load_config() if cfg is None else cfg
    try:
        n = int(cfg.get("parallel") or DEFAULT_PARALLEL)
    except (TypeError, ValueError):
        n = DEFAULT_PARALLEL
    return max(1, min(n, MAX_PARALLEL))


def command(script: str, args: list[str]) -> list[str]:
    override = os.environ.get("PAPER_VIEWER_JOB_CMD")
    return shlex.split(override) + [script, *args] if override else [str(ROOT / "scripts" / script), *args]


@dataclass
class Job:
    id: str
    key: str                        # paper: its PDF hash (stable), else its id
    action: str
    steps: list[Step]
    log: Path
    env: dict[str, str] = field(default_factory=dict)   # extra environment for the steps (agent model / effort)
    status: str = "queued"          # queued | running | done | failed | interrupted (the viewer stopped meanwhile)
    lines: list[str] = field(default_factory=list)
    returncode: int | None = None
    proc: subprocess.Popen | None = None
    # epoch seconds, for the library's progress bar and time estimate
    submitted: float = field(default_factory=time.time)
    started: float | None = None
    ended: float | None = None

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed", "interrupted")


class Jobs:
    def __init__(self):
        self._queue: queue.Queue[Job] = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._workers: list[threading.Thread] = []
        self._state: Path | None = None
        self._stopping = False

    def submit(self, key: str, action: str, steps: list[Step], log_dir: Path, env: dict[str, str] | None = None) -> Job:
        """Queue a job for the paper, or return its job that is still queued or running (whatever its action)."""
        with self._lock:
            for job in self._jobs.values():
                if job.key == key and not job.finished:
                    return job
            jid = uuid.uuid4().hex[:12]
            job = Job(id=jid, key=key, action=action, steps=steps, env=env or {},
                      log=log_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{action}-{jid}.log")
            self._jobs[job.id] = job
            self._queue.put(job)
            # workers start on demand; raising `parallel` takes effect without a restart, lowering it after one
            self._workers = [w for w in self._workers if w.is_alive()]
            while len(self._workers) < parallel():
                self._workers.append(threading.Thread(target=self._loop, daemon=True))
                self._workers[-1].start()
        self._save()
        return job

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def busy(self) -> bool:
        return any(not job.finished for job in self.all())

    def restore(self, state: Path) -> None:
        """Load the jobs of the last viewer run from `state` and keep saving there. A job that was still queued or
        running then was cut off: it comes back `interrupted`, with the end of its log."""
        self._state = state
        try:
            saved = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        with self._lock:
            for r in saved.values():
                if r["id"] in self._jobs:
                    continue
                log = Path(r["log"])
                try:
                    lines = log.read_text(encoding="utf-8").splitlines()[-LOG_TAIL:]
                except OSError:
                    lines = []
                status, ended = r["status"], r.get("ended")
                if status in ("queued", "running"):
                    status, ended = "interrupted", time.time()
                    lines.append(INTERRUPTED_NOTE)
                self._jobs[r["id"]] = Job(id=r["id"], key=r["key"], action=r["action"], steps=[], log=log,
                                          env=r.get("env") or {}, status=status, lines=lines,
                                          submitted=r.get("submitted") or 0.0, started=r.get("started"), ended=ended)
        self._save()

    def _save(self) -> None:
        """The latest job per paper, written atomically (several workers save)."""
        if self._state is None:
            return
        latest = {j.key: {"id": j.id, "key": j.key, "action": j.action, "status": j.status, "env": j.env,
                          "log": str(j.log), "submitted": j.submitted, "started": j.started, "ended": j.ended}
                  for j in self.all()}
        with self._save_lock:
            self._state.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state.with_suffix(".tmp")
            tmp.write_text(json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self._state)

    def _loop(self) -> None:
        while True:
            self._run(self._queue.get())

    def _emit(self, job: Job, log, line: str) -> None:
        job.lines.append(line.rstrip("\n"))
        log.write(line if line.endswith("\n") else line + "\n")
        log.flush()

    def _run(self, job: Job) -> None:
        job.log.parent.mkdir(parents=True, exist_ok=True)
        job.status, job.started = "running", time.time()
        self._save()
        with open(job.log, "w", encoding="utf-8") as log:
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
            if job.returncode != 0 and self._stopping:
                self._emit(job, log, INTERRUPTED_NOTE)
        job.ended = time.time()
        job.status = "done" if job.returncode == 0 else "interrupted" if self._stopping else "failed"
        self._save()

    def shutdown(self) -> None:
        """Terminate the running subprocesses (server shutdown); their jobs end as interrupted."""
        self._stopping = True
        for job in self.all():
            if job.proc and job.proc.poll() is None:
                job.proc.terminate()


JOBS = Jobs()
