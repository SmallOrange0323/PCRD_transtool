# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

# 取得 story_detail 的欄位名稱
cur.execute("PRAGMA table_info(story_detail)")
columns = [r[1] for r in cur.fetchall()]
print("story_detail 欄位:", columns)

# 查詢 1383001 的詳細資料
cur.execute("SELECT * FROM story_detail WHERE story_id = 1383001")
row = cur.fetchone()
if row:
    for col, val in zip(columns, row):
        print(f"  {col}: {val}")
