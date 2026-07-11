# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

# 1. 查詢前 10 筆資料，看看 chara_id_1 是什麼
cur.execute("SELECT story_id, chara_id_1, chara_id_2, chara_id_3, unlock_story_name FROM chara_story_status LIMIT 20")
for r in cur.fetchall():
    print(r)
    
print("\n=== 模糊搜尋包含 100501 或 180501 或者是含有 怜(公主) 故事名稱的行 ===")
cur.execute("SELECT story_id, chara_id_1, unlock_story_name FROM chara_story_status WHERE unlock_story_name LIKE '%怜%' LIMIT 20")
for r in cur.fetchall():
    print(r)

conn.close()
