# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

# 1. 查詢 event_story_detail 中的所有 story_group_id
cur.execute("SELECT story_group_id, title FROM event_story_detail ORDER BY story_group_id DESC LIMIT 15")
rows = cur.fetchall()
print("=== event_story_detail 最新活動 ID 與標題 ===")
for r in rows:
    print(f"  活動 ID: {r[0]} | 標題: {r[1]}")

# 2. 查詢 story_detail 裡最大的一些 ID
cur.execute("SELECT story_group_id, title FROM story_detail ORDER BY story_group_id DESC LIMIT 15")
rows2 = cur.fetchall()
print("\n=== story_detail 最新故事組 ID 與標題 ===")
for r in rows2:
    print(f"  故事組 ID: {r[0]} | 標題: {r[1]}")

conn.close()
