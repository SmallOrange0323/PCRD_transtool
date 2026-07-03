# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在查詢最新台版資料庫中的新形式活動資料 ===")

# 我們在本地剛剛更新的 redive_tw.db 中查詢
db_path = 'dashboard/redive_tw.db'
if not os.path.exists(db_path):
    # 也檢查專案根目錄下
    db_path = 'redive_tw.db'

print(f"使用的資料庫路徑: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 新形式活動通常在 event_story_data 或是 story_detail (story_group_id)
# 讓我們看看與 story_group_id >= 10200 相關的數據
try:
    cur.execute("""
        SELECT story_group_id, MIN(story_id), MAX(story_id)
        FROM story_detail
        WHERE story_group_id >= 10200 AND story_group_id < 10300
        GROUP BY story_group_id
        ORDER BY story_group_id DESC
    """)
    rows = cur.fetchall()
    print("在 story_detail 查到 >= 10200 的活動組:")
    for r in rows:
        print(f"  活動 ID: {r[0]} | 劇情 ID 範圍: {r[1]} ~ {r[2]}")
except Exception as e:
    print("查詢 story_detail 出錯:", e)

# 也去 event_story_data / event_story_detail / event_data 查詢
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%event%'")
    tables = [r[0] for r in cur.fetchall()]
    print("包含 event 的資料表:", tables)
    
    # 查詢 event_story_detail 中最新的活動資訊
    if 'event_story_detail' in tables:
        cur.execute("SELECT story_group_id, title FROM event_story_detail WHERE story_group_id >= 10200 ORDER BY story_group_id DESC LIMIT 5")
        print("event_story_detail 最新活動:")
        for r in cur.fetchall():
            print(f"  活動 ID: {r[0]} | 名稱: {r[1]}")
except Exception as e:
    print("查詢 event 表出錯:", e)
conn.close()
