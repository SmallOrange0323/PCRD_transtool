# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢查阿斯特萊亞佩可劇情的 CG/插畫 (still_id) 與背景 (bg_id) ===")

db_path = 'dashboard/redive_jp.db'
if not os.path.exists(db_path):
    print("找不到日版資料庫")
    sys.exit(0)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 查詢 1383001 ~ 1383004 劇情的詳細資訊與劇照 ID
cur.execute("SELECT story_id, title, sub_title, story_group_id FROM story_detail WHERE story_id >= 1000000 AND story_id < 2000000 AND (story_id LIKE '11383%' OR story_id LIKE '1383%')")
rows = cur.fetchall()

if not rows:
    # 搜尋 story_detail 中 story_id 包含 1383 的
    cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE story_id >= 1383000 AND story_id < 1383999")
    rows = cur.fetchall()

print(f"找到 {len(rows)} 筆劇情詳細記錄：")
for r in rows:
    print(r)
