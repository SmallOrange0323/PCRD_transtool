# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

print("=== 正在搜尋與阿斯特萊亞佩可 (138301) 相關的所有 still_id ===")

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

# 搜尋 story_still 表或卡片關聯表
# 讓我們看看是否有跟 still 相關的對照資料
if 'chara_story_still' in tables:
    cur.execute("SELECT * FROM chara_story_still WHERE story_id >= 1383000 AND story_id < 1383999")
    print("chara_story_still 結果:", cur.fetchall())

# 或者是查詢與 still_unit_mapping 相關的
mapping_table = [t for t in tables if 'still' in t]
print("包含 still 的表名:", mapping_table)

for t in mapping_table:
    try:
        cur.execute(f"SELECT * FROM {t} LIMIT 5")
        print(f"表 {t} 的樣本數據:", cur.fetchall())
    except Exception as e:
        print(e)
