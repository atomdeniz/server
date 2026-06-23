#!/usr/bin/env python3
"""Apply AmneziaWG 2.0 obfuscation params to wg-easy v15's SQLite DB.

v15 auto-generates only the 1.0 params (Jc/Jmin/Jmax, S1/S2, H1-H4). The 2.0
Custom Signature Packets (I1-I5) and the extra message paddings (S3/S4) are
left empty. This writes them in:

  - I1-I5 on the interface AND every client row. Signature packets do not need
    to match between peers (each side just sends its own), so the same set is
    fine on both ends.
  - S3/S4 on the interface only. wg-easy sources S* from the interface and
    copies them into every client config; they MUST match between peers, so
    every client must re-download its config after a change.

Idempotent: prints CHANGED only when it actually rewrites a row, OK otherwise.

Usage: apply_awg2.py /path/to/wg-easy.db /path/to/awg2.json
"""
import json
import sqlite3
import sys


def main() -> int:
    db, cfg_path = sys.argv[1], sys.argv[2]
    with open(cfg_path) as fh:
        cfg = json.load(fh)
    # Map to exactly i1..i5; unfilled slots are NULL (treated as "not sent").
    ivals = (list(cfg["signature_packets"]) + [None] * 5)[:5]
    s3, s4 = cfg["s3"], cfg["s4"]

    conn = sqlite3.connect(db, timeout=30)
    cur = conn.cursor()
    changed = False

    cur.execute("SELECT rowid, i1, i2, i3, i4, i5, s3, s4 FROM interfaces_table")
    for row in cur.fetchall():
        rowid = row[0]
        if list(row[1:6]) != ivals or row[6] != s3 or row[7] != s4:
            cur.execute(
                "UPDATE interfaces_table "
                "SET i1=?, i2=?, i3=?, i4=?, i5=?, s3=?, s4=? WHERE rowid=?",
                (*ivals, s3, s4, rowid),
            )
            changed = True

    cur.execute("SELECT rowid, i1, i2, i3, i4, i5 FROM clients_table")
    for row in cur.fetchall():
        rowid = row[0]
        if list(row[1:6]) != ivals:
            cur.execute(
                "UPDATE clients_table SET i1=?, i2=?, i3=?, i4=?, i5=? WHERE rowid=?",
                (*ivals, rowid),
            )
            changed = True

    conn.commit()
    conn.close()
    print("CHANGED" if changed else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
