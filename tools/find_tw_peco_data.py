# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
if not os.path.exists(db_path):
    print("找不到台服資料庫")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 獲取所有 v1_ 開頭的表
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
tables = [row[0] for row in cur.fetchall()]

target_id = 138301
print(f"正在掃描台版混淆資料庫中有關 ID {target_id} 的資料表...")

for table in tables:
    try:
        cur.execute(f"PRAGMA table_info(\"{table}\")")
        columns = [col[1] for col in cur.fetchall()]
        
        # 尋找是否含有該 ID
        for col in columns:
            cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{col}\" = ?", (target_id,))
            count = cur.fetchone()[0]
            if count > 0:
                print(f"🎯 找到匹配資料表: {table} | 欄位: {col} | 筆數: {count}")
                # 順便印出一筆資料範例
                cur.execute(f"SELECT * FROM \"{table}\" WHERE \"{col}\" = ? LIMIT 1", (target_id,))
                print(f"   樣例: {cur.fetchone()}")
    except Exception as e:
        pass

conn.close()
