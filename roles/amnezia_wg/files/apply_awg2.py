#!/usr/bin/env python3
"""Write AmneziaWG 2.0 params (I1-I5, S3/S4) into wg-easy v15's SQLite DB.

v15 only generates the 1.0 set. I1-I5 go on the interface, the client-config
defaults (user_configs_table, what new clients inherit) and every existing
client; they need not match peers. S3/S4 go on the interface (wg-easy copies
them into client configs, where they MUST match). Idempotent: prints CHANGED
only on a rewrite.

Usage: apply_awg2.py /path/to/wg-easy.db /path/to/awg2.json
"""
import json
import sqlite3
import sys


def main() -> int:
    db, cfg_path = sys.argv[1], sys.argv[2]
    with open(cfg_path) as fh:
        cfg = json.load(fh)
    ivals = (list(cfg["signature_packets"]) + [None] * 5)[:5]
    s3, s4 = cfg["s3"], cfg["s4"]

    conn = sqlite3.connect(db, timeout=30)
    cur = conn.cursor()
    changed = False

    def sync(table, icols, where_extra=""):
        nonlocal changed
        cur.execute(f"SELECT rowid, {', '.join(icols)} FROM {table}")
        for row in cur.fetchall():
            if list(row[1:6]) != ivals:
                sets = ", ".join(f"{c}=?" for c in icols)
                cur.execute(f"UPDATE {table} SET {sets} WHERE rowid=?", (*ivals, row[0]))
                changed = True

    # interface: I1-I5 + S3/S4
    cur.execute("SELECT rowid, i1, i2, i3, i4, i5, s3, s4 FROM interfaces_table")
    for row in cur.fetchall():
        if list(row[1:6]) != ivals or row[6] != s3 or row[7] != s4:
            cur.execute(
                "UPDATE interfaces_table "
                "SET i1=?, i2=?, i3=?, i4=?, i5=?, s3=?, s4=? WHERE rowid=?",
                (*ivals, s3, s4, row[0]),
            )
            changed = True

    sync("user_configs_table", ["default_i1", "default_i2", "default_i3", "default_i4", "default_i5"])
    sync("clients_table", ["i1", "i2", "i3", "i4", "i5"])

    conn.commit()
    conn.close()
    print("CHANGED" if changed else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
