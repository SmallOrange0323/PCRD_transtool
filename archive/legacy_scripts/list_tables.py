# -*- coding: utf-8 -*-
import sys

print(
    "[LEGACY ARCHIVE ONLY] This legacy table-listing script is disabled. "
    "Use tools/diagnostics/list_tw_tables.py instead."
)
sys.exit(1)

import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('redive_tw.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"總共找到 {len(tables)} 個表。前 50 個表名:")
print(tables[:50])
conn.close()
