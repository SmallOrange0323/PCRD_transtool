# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

print("=== 正在查詢日版資料庫中的新形式活動資料 ===")

# 新形式活動通常在 event_story_detail
try:
    # 查詢大於 10000 的活動
    cur.execute("SELECT DISTINCT story_group_id, title FROM event_story_detail WHERE story_group_id >= 10000 ORDER BY story_group_id DESC LIMIT 30")
    rows = cur.fetchall()
    print("日版 event_story_detail 最新活動 ID:")
    for r in rows:
        print(f"  活動 ID: {r[0]} | 名稱: {r[1]}")
except Exception as e:
    print(e)
    
# 也查詢一下 story_detail 
try:
    cur.execute("SELECT DISTINCT story_group_id, title FROM story_detail WHERE story_group_id >= 10200 AND story_group_id < 10300 ORDER BY story_group_id DESC LIMIT 15")
    rows = cur.fetchall()
    print("\n日版 story_detail 故事組 ID:")
    for r in rows:
        print(f"  故事組 ID: {r[0]} | 名稱: {r[1]}")
except Exception as e:
    print(e)

conn.close()
