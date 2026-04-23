#!/usr/bin/env bash
# Single-instance rclone sync: seedbox -> Hetzner Storage Box (WebDAV)
#
# Ultra.cc Fair Usage Policy hard guarantees (do NOT weaken):
#   - Only ONE instance runs at a time (flock -n, non-blocking)
#   - Bandwidth-capped at 30 MB/s (--bwlimit=30M)
#   - At most 2 concurrent transfers per rclone (--transfers=2)
#
# Canonical source: scripts/seedbox/sync-media.sh in the ansible repo.
# Deploy: see scripts/seedbox/README.md.
#
# Optional runtime config (~/.config/sync-media.env):
#   NTFY_URL=https://ntfy.example.com/<topic>
#   NTFY_TOKEN=tk_...
# Sources that file if present so failures push a notification.

set -euo pipefail

LOCK=/tmp/rclone-sync.lock
LOG_DIR="$HOME/.local/log"
LOG="$LOG_DIR/sync-media.log"
ENV_FILE="$HOME/.config/sync-media.env"

mkdir -p "$LOG_DIR"

# Optional env (ntfy credentials). 'set -a' exports everything the file sets.
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

notify() {
  # notify <title> <body> [priority] [tags]
  [ -n "${NTFY_URL:-}" ] && [ -n "${NTFY_TOKEN:-}" ] || return 0
  curl -sf --max-time 10 \
    -H "Title: $1" \
    -H "Priority: ${3:-default}" \
    -H "Tags: ${4:-}" \
    -H "Authorization: Bearer $NTFY_TOKEN" \
    -d "$2" \
    "$NTFY_URL" >/dev/null 2>&1 || true
}

# Non-blocking lock: if another instance holds it, log and exit clean.
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$(date -Is)] already running, skip" >> "$LOG"
  exit 0
fi

echo "[$(date -Is)] start pid=$$" >> "$LOG"

RCLONE_OPTS=(
  --bwlimit=30M
  --transfers=2
  --checkers=4
  --size-only
  --retries=3
  --low-level-retries=5
  -q
)

FAILED=()

sync_pair() {
  local src="$1" dst="$2"
  echo "[$(date -Is)] sync $src -> $dst" >> "$LOG"
  if ! rclone sync "$src" "$dst" "${RCLONE_OPTS[@]}" >> "$LOG" 2>&1; then
    local ec=$?
    echo "[$(date -Is)] FAIL $src (exit=$ec)" >> "$LOG"
    FAILED+=("$src")
  fi
}

sync_pair "$HOME/media/Movies/"   "storagebox-webdav:media/movies/"
sync_pair "$HOME/media/TV Shows/" "storagebox-webdav:media/tv/"
sync_pair "$HOME/media/Anime/"    "storagebox-webdav:media/anime/"

echo "[$(date -Is)] done pid=$$" >> "$LOG"

if [ ${#FAILED[@]} -gt 0 ]; then
  notify "Seedbox sync failed" "Failed paths: ${FAILED[*]}" high warning
fi
