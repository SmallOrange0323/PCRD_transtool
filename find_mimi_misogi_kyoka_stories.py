# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

print("=== 正在檢索 禊、美美、鏡華 相關的所有個人劇情 ===")

# 我們在 story_detail 查詢所有含有 "禊"、"美美" 或 "鏡華" 的個人故事 (story_id 在 1000000 到 2000000 之間)
cur.execute("""
    SELECT story_id, title, sub_title, story_group_id 
    FROM story_detail 
    WHERE story_id >= 1000000 AND story_id < 2000000 
      AND (title LIKE '%禊%' OR title LIKE '%美美%' OR title LIKE '%鏡華%')
    ORDER BY story_id DESC
""")
rows = cur.fetchall()
print(f"共找到 {len(rows)} 筆記錄：")
for r in rows[:40]:
    print(f"  story_id: {r[0]} | 標題: {r[1]} | {r[2]} | story_group_id: {r[3]}")

conn.close()
