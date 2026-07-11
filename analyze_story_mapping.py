# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

# 我們來看看 chara_story_status 或者是故事關聯表的結構
print("=== 查詢 chara_story_status 或其他故事關聯表 ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%chara_story%'")
tables = [r[0] for r in cur.fetchall()]
print("匹配的表名:", tables)

# 如果有 chara_story_status 表，我們查一下它的欄位
if 'chara_story_status' in tables:
    cur.execute("PRAGMA table_info(chara_story_status)")
    cols = [col[1] for col in cur.fetchall()]
    print("chara_story_status 欄位:", cols)
    
    # 查詢 180501 (怜 公主) 或 100501 (怜 原版)
    # 個人劇情通常是用 chara_id (即 1005) 來記錄的。
    # 也就是說：同一個角色的所有換裝 (原版 100501, 公主 180501) 是否共享同一個個人故事組？
    # 不，公主怜有她獨立的個人故事。
    # 讓我們查詢一下與怜公主 180501 或 1005 相關的故事
    cur.execute("SELECT * FROM chara_story_status WHERE chara_id_1 = 180501 OR chara_id_2 = 180501 LIMIT 5")
    rows = cur.fetchall()
    print("chara_story_status 中 180501 的紀錄:", rows)
    
    cur.execute("SELECT * FROM chara_story_status WHERE chara_id_1 = 100501 OR chara_id_2 = 100501 LIMIT 5")
    rows2 = cur.fetchall()
    print("chara_story_status 中 100501 (原版怜) 的紀錄:", rows2)

conn.close()
