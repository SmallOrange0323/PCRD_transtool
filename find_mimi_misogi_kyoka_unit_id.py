# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

print("=== 正在查詢 禊＆美美＆鏡華 角色在 unit_data 表中的真實 unit_id ===")

cur.execute("SELECT unit_id, unit_name, rarity FROM unit_data WHERE unit_name LIKE '%禊%' AND unit_name LIKE '%美美%'")
for r in cur.fetchall():
    print(r)

conn.close()
