import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
c = conn.cursor()

# 1. 查詢最近的活動 (event_data)
print("--- 最近的活動 (event_data) ---")
try:
    c.execute("SELECT event_id, start_time, end_time, title FROM event_data ORDER BY start_time DESC LIMIT 10")
    for r in c.fetchall():
        print(f"ID: {r[0]} | 開始: {r[1]} | 結束: {r[2]} | 名稱: {r[3]}")
except Exception as e:
    print("查詢 event_data 失敗:", e)

# 2. 查詢天賦系統 (talent_data)
print("\n--- 檢查是否有 talent 相關資料表 ---")
try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'talent_data'")
    r = c.fetchone()
    if r:
        print("找到天賦資料表: talent_data")
        c.execute("SELECT * FROM talent_data LIMIT 5")
        print("數據範例:", c.fetchall())
    else:
        print("未找到 talent_data 資料表")
except Exception as e:
    print(e)

# 3. 檢查旅行系統 (travel_quest_data)
print("\n--- 檢查是否有 travel 相關資料表 ---")
try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'travel_quest_data'")
    r = c.fetchone()
    if r:
        print("找到旅行資料表: travel_quest_data")
        c.execute("SELECT * FROM travel_quest_data LIMIT 5")
        print("數據範例:", c.fetchall())
    else:
        print("未找到 travel_quest_data 資料表")
except Exception as e:
    print(e)

conn.close()
