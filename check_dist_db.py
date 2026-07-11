# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dist_story_map/redive_tw.db')
cur = conn.cursor()

print("=== 正在查詢 dist_story_map/redive_tw.db 中三個角色 ID 的真實名稱 ===")

for uid in [180301, 180501, 180801, 150601]:
    cur.execute("SELECT unit_name, rarity FROM unit_data WHERE unit_id = ?", (uid,))
    row = cur.fetchone()
    if row:
        print(f"  - ID {uid} 的名稱為: {row[0]} | 星等: {row[1]}")
    else:
        print(f"  - ❌ ID {uid} 在發佈資料庫中不存在")

conn.close()
