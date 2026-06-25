#!/usr/bin/env python3
"""Seed a TCP MSS-clamp rule into wg-easy v15's PostUp/PostDown hooks (no env for
it), so it survives restarts. Idempotent: prints CHANGED only on edit.

Usage: ensure_mss_clamp.py /path/to/wg-easy.db <mss>
"""
import re
import sqlite3
import sys
import time

RULE = "iptables -t mangle {op} FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss {mss}"
# Strip any prior clamp (any value) first, so a changed mss rewrites without stacking.
EXISTING = re.compile(
    r"\s*iptables -t mangle -[AD] FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss \d+;?"
)


def patch(hook: str, op: str, mss: int) -> str:
    cleaned = EXISTING.sub("", hook).rstrip()
    rule = RULE.format(op=op, mss=mss)
    return f"{cleaned} {rule};" if cleaned else f"{rule};"


def main() -> int:
    db, mss = sys.argv[1], int(sys.argv[2])
    deadline = time.time() + 60  # hooks are seeded async on first boot
    rows = []
    while True:
        try:
            conn = sqlite3.connect(db, timeout=30)
            cur = conn.cursor()
            cur.execute("SELECT rowid, post_up, post_down FROM hooks_table")
            rows = cur.fetchall()
            if rows:
                break
        except sqlite3.OperationalError:
            rows = []
        if time.time() > deadline:
            print("hooks_table not ready after 60s; skipping")
            return 0
        time.sleep(2)

    changed = False
    for rowid, post_up, post_down in rows:
        new_up = patch(post_up, "-A", mss)
        new_down = patch(post_down, "-D", mss)
        if new_up != post_up or new_down != post_down:
            cur.execute(
                "UPDATE hooks_table SET post_up = ?, post_down = ? WHERE rowid = ?",
                (new_up, new_down, rowid),
            )
            changed = True
    conn.commit()
    conn.close()
    print("CHANGED" if changed else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
