#!/usr/bin/env bash
# Pulls free public blocklists and imports them into CrowdSec LAPI.
# Uses --duration 25h so entries self-expire if the cron skips a day.

set -euo pipefail

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

log() { echo "[blocklist-update] $*"; }

fetch() {
  local url="$1" out="$2"
  if curl -fsSL --max-time 60 --retry 2 "$url" -o "$out"; then
    log "fetched $(wc -l <"$out" | tr -d ' ') lines from $url"
    return 0
  fi
  log "WARN: failed to fetch $url"
  return 1
}

import() {
  local file="$1" reason="$2"
  # Strip comments, blank lines, and any inline notes after whitespace.
  # Keeps IPs and CIDRs (both accepted by `cscli decisions import`).
  grep -Ev '^\s*(#|$)' "$file" | awk '{print $1}' >"$TMP/import.tmp"
  local count
  count=$(wc -l <"$TMP/import.tmp" | tr -d ' ')
  if [ "$count" -eq 0 ]; then
    log "WARN: $reason empty after filtering, skipping"
    return
  fi
  log "importing $count entries as $reason"
  docker exec -i crowdsec cscli decisions import \
    --input /dev/stdin \
    --format values \
    --duration 25h \
    --reason "$reason" \
    --type ban <"$TMP/import.tmp"
}

# Firehol Level 1 — conservative, high-confidence malicious IPs (CIDR ranges)
if fetch "https://iplists.firehol.org/files/firehol_level1.netset" "$TMP/firehol.txt"; then
  import "$TMP/firehol.txt" "firehol_level1"
fi

# Stamparm IPsum level 5 — IPs reported by 5+ independent sources (high precision)
if fetch "https://raw.githubusercontent.com/stamparm/ipsum/master/levels/5.txt" "$TMP/ipsum.txt"; then
  import "$TMP/ipsum.txt" "ipsum_level5"
fi

log "done"
