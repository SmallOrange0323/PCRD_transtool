# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測 禊&美美&鏡華(1506) 與 怜(公主)(1805) 的故事數據就緒度 ===")

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

for gid in [1506, 1805]:
    print(f"\n🔍 檢查故事組 ID: {gid}")
    cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE story_group_id = ?", (gid,))
    rows = cur.fetchall()
    print(f"  - 資料庫中收錄的章節數量: {len(rows)}")
    for r in rows:
        print(f"    - [{r[0]}] {r[1]} | {r[2]}")
        
    # 檢查本地對白檔案
    for i in range(1, 5):
        json_path = f"dashboard/story/{gid}00{i}.json"
        exist = os.path.exists(json_path)
        print(f"    - 檔案 story/{gid}00{i}.json 是否存在: {exist}")
        
conn.close()
