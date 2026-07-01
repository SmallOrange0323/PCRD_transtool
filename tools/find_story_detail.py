# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 獲取所有 v1_ 表
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
tables = [row[0] for row in cur.fetchall()]

# 我們要尋找含有 1001001 (原版佩可第一話) 的表
target_story_id = 1001001

print(f"正在掃描台版資料庫中包含故事 ID {target_story_id} 且含有文字標題的表...")

for table in tables:
    try:
        cur.execute(f"PRAGMA table_info(\"{table}\")")
        columns = [col[1] for col in cur.fetchall()]
        
        # 尋找是否含有該 ID
        for col in columns:
            cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{col}\" = ?", (target_story_id,))
            count = cur.fetchone()[0]
            if count > 0:
                # 檢查是否有文字欄位
                cur.execute(f"SELECT * FROM \"{table}\" WHERE \"{col}\" = ? LIMIT 1", (target_story_id,))
                row = cur.fetchone()
                texts = [val for val in row if isinstance(val, str) and len(val) > 2]
                if texts:
                    print(f"🎯 找到故事詳細表: {table} | 欄位: {col}")
                    print(f"   資料樣例: {row}")
                    break
    except Exception as e:
        pass

conn.close()
