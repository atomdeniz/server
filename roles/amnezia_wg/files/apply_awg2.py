#!/usr/bin/env python3
"""Write AmneziaWG 2.0 params (I1-I5, S3/S4) into wg-easy v15's SQLite DB.

v15 only generates the 1.0 set. I1-I5 go on the interface and every client (they
need not match peers); S3/S4 go on the interface (wg-easy copies them into client
configs, where they MUST match). Idempotent: prints CHANGED only on a rewrite.

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

    cur.execute("SELECT rowid, i1, i2, i3, i4, i5, s3, s4 FROM interfaces_table")
    for row in cur.fetchall():
        if list(row[1:6]) != ivals or row[6] != s3 or row[7] != s4:
            cur.execute(
                "UPDATE interfaces_table "
                "SET i1=?, i2=?, i3=?, i4=?, i5=?, s3=?, s4=? WHERE rowid=?",
                (*ivals, s3, s4, row[0]),
            )
            changed = True

    cur.execute("SELECT rowid, i1, i2, i3, i4, i5 FROM clients_table")
    for row in cur.fetchall():
        if list(row[1:6]) != ivals:
            cur.execute(
                "UPDATE clients_table SET i1=?, i2=?, i3=?, i4=?, i5=? WHERE rowid=?",
                (*ivals, row[0]),
            )
            changed = True

    conn.commit()
    conn.close()
    print("CHANGED" if changed else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
