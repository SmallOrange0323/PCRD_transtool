# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

still_tables = [t for t in tables if 'still' in t or 'detail' in t]
print("關聯的資料表:", still_tables)

# 搜尋 story_still 或類似表中有關 1383001 ~ 1383004 的 still_id
# 常見的表如：story_still, chara_story_detail (在 JP db 中)
# 讓我們看看是否有 story_still 表
if 'story_still' in tables:
    cur.execute("SELECT story_id, still_id FROM story_still WHERE story_id >= 1383000 AND story_id < 1383999")
    stills = cur.fetchall()
    print("在 story_still 查到的結果:", stills)
else:
    print("沒有 story_still 表")
