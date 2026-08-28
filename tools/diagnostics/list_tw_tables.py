# -*- coding: utf-8 -*-
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(REPO_ROOT, "dashboard", "redive_tw.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"總共找到 {len(tables)} 個表。表名列表:")
for idx, name in enumerate(sorted(tables)):
    print(f"  [{idx}] {name}")
conn.close()
