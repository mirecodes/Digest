"""Pick the port for scripts/viewer.sh: free it if a leftover Paper Viewer holds it, else move to the next free one.

A viewer left running (closed terminal, background run) keeps serving old code and blocks the port with
"[Errno 48] address already in use". It identifies itself at /api/health, so it is stopped and replaced; a port held
by any other program is left alone and the next free port is used instead.

Usage: python -m functions.viewer.port HOST PORT   -> prints the port to use; messages go to stderr.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

SCAN = 20          # ports tried after the configured one
STOP_WAIT = 5.0    # seconds to wait for a stopped viewer to release the port


def is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # SO_REUSEADDR like uvicorn: old connections in TIME_WAIT do not count, only another listening socket does
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def viewer_at(host: str, port: int) -> dict | None:
    """The /api/health answer if a Paper Viewer runs there."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=1.5) as r:
            data = json.load(r)
        return data if data.get("app") == "paper-viewer" else None
    except (OSError, ValueError):
        return None


def _listeners(port: int) -> set[int]:
    """Processes listening on the port (with --reload the socket belongs to uvicorn's supervisor, not the worker)."""
    try:
        out = subprocess.run(["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    except OSError:   # no lsof: the worker pid from /api/health is all we know
        return set()
    return {int(p) for p in out.split()}


def stop_viewer(host: str, port: int, info: dict) -> bool:
    """SIGTERM the viewer: its worker and whatever listens on its port (only called after /api/health confirmed a
    Paper Viewer there). True once the port is free."""
    for pid in {info["pid"]} | _listeners(port):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + STOP_WAIT
    while time.monotonic() < deadline:
        if is_free(host, port):
            return True
        time.sleep(0.2)
    return False


def pick_port(host: str, port: int) -> int:
    if is_free(host, port):
        return port
    info = viewer_at(host, port)
    if info:
        print(f"[viewer] stopping the viewer already running on port {port} (pid {info['pid']})", file=sys.stderr)
        if stop_viewer(host, port, info):
            return port
    for p in range(port + 1, port + 1 + SCAN):
        if is_free(host, p):
            print(f"[viewer] port {port} is used by another program; using {p} instead", file=sys.stderr)
            return p
    raise SystemExit(f"[viewer] ERROR: ports {port}-{port + SCAN} are all in use")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m functions.viewer.port HOST PORT")
    print(pick_port(sys.argv[1], int(sys.argv[2])))
