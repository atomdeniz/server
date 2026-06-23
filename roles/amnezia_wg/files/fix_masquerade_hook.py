#!/usr/bin/env python3
"""Rewrite wg-easy v15's seeded NAT masquerade hook to a device-agnostic form.

v15 seeds the interface PostUp/PostDown with `-o {{device}}` (eth0), which only
masquerades internet-bound traffic leaving eth0. But VPN clients send DNS to
AdGuard (10.8.4.2) on dns_network, reached via the `myeth` interface, so those
packets are NOT masqueraded -> AdGuard can't route replies back to the VPN
subnet -> client DNS (and thus "the internet") breaks.

There is no env var to override the seeded hook, so this patches the SQLite DB
directly to the device-agnostic `! -o wg0` form the old image used (masquerade
everything from the VPN subnet except what re-enters the tunnel). Idempotent:
prints CHANGED only when it actually rewrites a row, OK otherwise.

Usage: fix_masquerade_hook.py /path/to/wg-easy.db
"""
import sqlite3
import sys
import time

SEARCH = "-o {{device}}"
REPLACE = "! -o wg0"


def main() -> int:
    db = sys.argv[1]
    deadline = time.time() + 60  # wg-easy seeds the hook async on first boot
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
