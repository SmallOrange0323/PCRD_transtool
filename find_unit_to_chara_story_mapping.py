# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

# 1. 檢索所有表，看看有沒有與 chara_id 相關的表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

# 2. 我們查詢 unit_data 或者是 chara_identity 或者是 unit_comments 等表
# 看看 180301 (怜公主) 或者是 150601 裡面有沒有 1803 或 1808 這樣的數值
# 提示: 怜(公主) 180301 真正的基礎角色是 怜 (100501 / chara_id 1003)。
# 公主換裝的 chara_id_1 是 1803。
# 讓我們來看看 unit_data 的欄位
cur.execute("PRAGMA table_info(unit_data)")
cols = [col[1] for col in cur.fetchall()]
print("unit_data 欄位:", cols)

# 查詢 unit_data 中 180301 的所有數值
cur.execute("SELECT * FROM unit_data WHERE unit_id = 180301")
print("180301 欄位數值:", cur.fetchone())

# 查詢 unit_data 中 180501 的所有數值
cur.execute("SELECT * FROM unit_data WHERE unit_id = 180501")
print("180501 欄位數值:", cur.fetchone())

# 我們也查一下有沒有一個表叫 chara_identity
if 'chara_identity' in tables:
    cur.execute("SELECT * FROM chara_identity LIMIT 5")
    print("chara_identity 範例:", cur.fetchall())

conn.close()
