"""Seedbox sync-progress UI backend.

SSH-tails the rclone sync log on the Ultra.cc slot, parses the most
recent script marker (start/sync/done/FAIL) and the most recent rclone
`Transferred:` stats line, and exposes the result as JSON for the
Homepage customapi widget.

Why not run a daemon on the seedbox: Ultra.cc Fair Usage Policy. The
2026-04-23 suspension was for too many parallel rclones on the shared
node; a long-running daemon there carries the same risk. All the
polling overhead stays on the VPS side. The seedbox just sees one
`tail -n N <log>` per poll interval.
"""

import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify

SEEDBOX_HOST = os.environ["SEEDBOX_HOST"]
SEEDBOX_USER = os.environ["SEEDBOX_USER"]
SEEDBOX_SSH_KEY = os.environ.get("SEEDBOX_SSH_KEY", "/run/secrets/seedbox_key")
SEEDBOX_LOG_PATH = os.environ.get("SEEDBOX_LOG_PATH", "~/.local/log/sync-media.log")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
TAIL_LINES = int(os.environ.get("TAIL_LINES", "300"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seedbox_sync_ui")

# Script-emitted lines from scripts/seedbox/sync-media.sh, e.g.:
#   [2026-05-28T12:34:56+00:00] start pid=12345
#   [2026-05-28T12:34:56+00:00] sync /home/user/media/Movies/ -> storagebox:media/movies/
#   [2026-05-28T12:39:00+00:00] FAIL /home/user/media/Movies/ (exit=1)
#   [2026-05-28T12:39:00+00:00] done pid=12345
MARKER_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+(?P<kind>start|sync|FAIL|done|already running|killing)\b(?P<rest>.*)$"
)

# rclone --stats-one-line --stats-log-level=NOTICE, e.g.:
#   2026/05/28 12:35:11 NOTICE: Transferred:   	4.213 GiB / 8.107 GiB, 52%, 28.123 MiB/s, ETA 2m20s
RCLONE_TS_RE = re.compile(r"^(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
TRANSFER_RE = re.compile(
    r"Transferred:\s*"
    r"(?P<done>[\d.]+\s*[KMGTP]?i?B?)\s*/\s*"
    r"(?P<total>[\d.]+\s*[KMGTP]?i?B),\s*"
    r"(?P<percent>-|\d+)%,\s*"
    r"(?P<speed>[\d.]+\s*[KMGTP]?i?B/s),\s*"
    r"ETA\s*(?P<eta>\S+)"
)

INITIAL_STATE = {
    "state": "unknown",
    "percent": 0,
    "progress": "—",
    "speed": "—",
    "eta": "—",
    "transferred": "—",
    "total": "—",
    "current_path": None,
    "last_log_ts": None,
    "last_run_start": None,
    "last_run_end": None,
    "last_run_failed": False,
    "last_poll": None,
    "error": None,
}

_state = dict(INITIAL_STATE)
_state_lock = threading.Lock()


def ssh_tail():
    """Return the last N lines of the seedbox log via SSH.

    Mirrors the media_cleanup role's ssh invocation so both use the
    same key + host-key policy.
    """
    cmd = [
        "ssh",
        "-i", SEEDBOX_SSH_KEY,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/app/.ssh/known_hosts",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=5",
        f"{SEEDBOX_USER}@{SEEDBOX_HOST}",
        f"tail -n {TAIL_LINES} {SEEDBOX_LOG_PATH}",
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=20, check=True)
    return result.stdout.decode("utf-8", "replace")


def parse_log(text):
    last_marker = None
    last_marker_ts = None
    last_sync_path = None
    last_transfer = None
    last_transfer_ts = None
    last_run_failed = False
    last_run_start = None
    last_run_end = None

    for line in text.splitlines():
        m = MARKER_RE.match(line)
        if m:
            ts = m.group("ts")
            kind = m.group("kind")
            rest = m.group("rest")
            last_marker = kind
            last_marker_ts = ts
            if kind == "start":
                last_run_start = ts
                last_run_failed = False
                last_sync_path = None
                # A new run is starting — earlier Transferred lines from
                # the previous run are stale; reset.
                last_transfer = None
                last_transfer_ts = None
            elif kind == "sync":
                # rest looks like " /home/user/media/Movies/ -> storagebox:media/movies/"
                src = rest.strip().split(" -> ", 1)[0]
                last_sync_path = src.rstrip("/").split("/")[-1] or src
            elif kind == "FAIL":
                last_run_failed = True
            elif kind == "done":
                last_run_end = ts
            continue

        if "Transferred:" in line:
            tm = TRANSFER_RE.search(line)
            if not tm:
                continue
            rts_m = RCLONE_TS_RE.match(line)
            percent_raw = tm.group("percent")
            last_transfer = {
                "transferred": tm.group("done").strip(),
                "total": tm.group("total").strip(),
                "percent": 0 if percent_raw == "-" else int(percent_raw),
                "speed": tm.group("speed").strip(),
                "eta": tm.group("eta").strip(),
            }
            if rts_m:
                last_transfer_ts = rts_m.group("ts")

    if last_marker == "done":
        state = "idle"
    elif last_marker in ("start", "sync"):
        state = "syncing"
    else:
        state = "unknown"

    # Display-friendly strings for the Homepage customapi widget. The
    # widget can't compute conditionals on its end, so anything that
    # should read differently when idle vs syncing has to be shaped here.
    if state == "syncing" and last_transfer:
        progress = f"{last_transfer['percent']}%"
        speed = last_transfer["speed"]
        eta = last_transfer["eta"]
    elif state == "idle":
        progress = "idle"
        speed = "—"
        eta = "—"
    else:
        progress = "—"
        speed = "—"
        eta = "—"

    return {
        "state": state,
        "percent": last_transfer["percent"] if last_transfer else 0,
        "progress": progress,
        "speed": speed,
        "eta": eta,
        "transferred": last_transfer["transferred"] if last_transfer else "—",
        "total": last_transfer["total"] if last_transfer else "—",
        "current_path": last_sync_path if state == "syncing" else None,
        "last_log_ts": last_transfer_ts or last_marker_ts,
        "last_run_start": last_run_start,
        "last_run_end": last_run_end,
        "last_run_failed": last_run_failed,
    }


def poll_once():
    try:
        text = ssh_tail()
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", "replace").strip()
        return None, f"ssh exit {e.returncode}: {stderr[:200]}"
    except subprocess.TimeoutExpired:
        return None, "ssh timeout"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    return parse_log(text), None


def poller_loop():
    while True:
        parsed, err = poll_once()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _state_lock:
            if parsed is not None:
                _state.update(parsed)
                _state["error"] = None
            else:
                _state["error"] = err
                log.warning("poll failed: %s", err)
            _state["last_poll"] = now
        time.sleep(POLL_INTERVAL)


def start_poller():
    t = threading.Thread(target=poller_loop, daemon=True, name="poller")
    t.start()


app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/status")
def status():
    with _state_lock:
        return jsonify(dict(_state))


# Start the poller at import time so it runs under gunicorn too. With
# `--workers 1` (configured in the Dockerfile CMD) there is exactly one
# poller thread for the whole process.
start_poller()
