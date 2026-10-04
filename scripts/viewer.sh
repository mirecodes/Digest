#!/usr/bin/env bash
# Start the Paper Viewer (local only) and open it in the browser.
# Usage: scripts/viewer.sh [--dev] [--port N] [--no-open]
#   default: serve the built frontend (web/dist) at http://<viewer.host>:<viewer.port> (configs/cfg.yaml, 127.0.0.1:8765)
#   --dev:   uvicorn --reload plus the Vite dev server (http://127.0.0.1:5173, proxies /api); Ctrl+C stops both
# A viewer still running on the port (e.g. from a closed terminal) is stopped and replaced; if another program
# holds the port, the next free one is used. Ctrl+C stops the server and frees the port.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/viewer.sh [--dev] [--port N] [--no-open]" >&2; exit 1; }
DEV=0; OPEN=1; PORT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dev) DEV=1 ;;
    --no-open) OPEN=0 ;;
    --port) [ $# -ge 2 ] || usage; PORT="$2"; shift ;;
    *) usage ;;
  esac
  shift
done
read -r HOST CFG_PORT < <("$PY" -c 'from functions.papers import viewer_cfg; c = viewer_cfg(); print(c["host"], c["port"])')
PORT="${PORT:-$CFG_PORT}"
# a leftover viewer on the port is stopped and replaced; another program's port is skipped for the next free one
PORT="$("$PY" -m functions.viewer.port "$HOST" "$PORT")"

open_url() {
  [ "$OPEN" -eq 1 ] || return 0
  (sleep 2; if command -v open >/dev/null; then open "$1"; elif command -v xdg-open >/dev/null; then xdg-open "$1"; fi) >/dev/null 2>&1 &
}

if [ "$DEV" -eq 1 ]; then
  "$PY" -m uvicorn functions.viewer.server:app --host "$HOST" --port "$PORT" --reload &
  API_PID=$!
  (cd web && VIEWER_API_PORT="$PORT" npm run dev -- --host 127.0.0.1 --port 5173) &
  WEB_PID=$!
  # stop both process trees (uvicorn's reloader worker, npm -> vite), so no port stays taken; only our own
  # descendants, never the caller's process group
  kill_tree() { local c; for c in $(pgrep -P "$1"); do kill_tree "$c"; done; kill "$1" 2>/dev/null || true; }
  trap 'trap - EXIT INT TERM; kill_tree $API_PID; kill_tree $WEB_PID' EXIT INT TERM
  open_url "http://127.0.0.1:5173"
  wait
else
  [ -f web/dist/index.html ] || echo "[viewer] WARNING: web/dist not built; run scripts/setup.sh" >&2
  echo "[viewer] http://$HOST:$PORT"
  open_url "http://$HOST:$PORT"
  exec "$PY" -m uvicorn functions.viewer.server:app --host "$HOST" --port "$PORT"
fi
