# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

print("=== 正在查詢 可可蘿(公主) 與 怜(公主) 的真實故事 ID 映射 ===")

# 查詢 chara_story_status
cur.execute("SELECT story_id, chara_id_1, unlock_story_name FROM chara_story_status WHERE unlock_story_name LIKE '%可可蘿（公主）%' OR unlock_story_name LIKE '%怜（公主）%'")
for r in cur.fetchall():
    print("chara_story_status:", r)

# 也去 story_detail 中查詢
cur.execute("SELECT story_id, title, sub_title, story_group_id FROM story_detail WHERE title LIKE '%可可蘿（公主）%' OR title LIKE '%怜（公主）%'")
for r in cur.fetchall():
    print("story_detail:", r)

conn.close()
