#!/usr/bin/env python3
"""Rewrite wg-easy v15's seeded NAT masquerade hook to a device-agnostic form.

v15 seeds `-o {{device}}` (eth0), which doesn't NAT VPN-client DNS to AdGuard
(that leaves via myeth) -> client DNS breaks. There's no env to override it, so
patch the SQLite DB to `! -o wg0`. Idempotent: prints CHANGED only on a rewrite.

Usage: fix_masquerade_hook.py /path/to/wg-easy.db
"""
import sqlite3
import sys
import time

SEARCH = "-o {{device}}"
REPLACE = "! -o wg0"


def main() -> int:
    db = sys.argv[1]
    deadline = time.time() + 60  # hook is seeded async on first boot
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
        new_up = post_up.replace(SEARCH, REPLACE)
        new_down = post_down.replace(SEARCH, REPLACE)
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
