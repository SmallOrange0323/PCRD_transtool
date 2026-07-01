# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
if not os.path.exists(db_path):
    db_path = 'dashboard/redive_jp.db'

print(f"=== 檢查資料庫 {db_path} 中的實裝角色數量 ===")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("包含的資料表:", tables)

if 'unit_data' in tables:
    # 玩家可實裝角色的 ID 規則通常是 100000 <= unit_id < 200000 且 unit_id % 100 == 1
    cur.execute("SELECT COUNT(DISTINCT unit_name) FROM unit_data WHERE unit_id >= 100000 AND unit_id < 200000")
    total_names = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM unit_data WHERE unit_id >= 100000 AND unit_id < 200000 AND unit_id % 100 = 1")
    playable_count = cur.fetchone()[0]

    print(f"\n📊 統計數據：")
    print(f"- 登場角色總名稱數: {total_names} 位")
    print(f"- 獨立實裝角色版本數 (含換裝): {playable_count} 位")
else:
    print("此資料庫未包含 unit_data 表。")
