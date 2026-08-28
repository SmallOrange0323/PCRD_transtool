# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(REPO_ROOT, "dashboard", "redive_tw.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 取得包含 story 的所有表名
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%story%'")
tables = [r[0] for r in cur.fetchall()]
print("含有 story 的所有表名:", tables)

# 分別查詢這些表，看看裡面最新的資料 ID 是多少
for t in tables:
    try:
        # 有些表可能有 story_group_id 或 story_id，我們看最大值
        cur.execute(f"PRAGMA table_info({t})")
        cols = [col[1] for col in cur.fetchall()]
        
        id_col = None
        for c in ['story_group_id', 'story_id', 'event_id', 'id']:
            if c in cols:
                id_col = c
                break
                
        if id_col:
            cur.execute(f"SELECT MAX({id_col}) FROM {t}")
            max_val = cur.fetchone()[0]
            print(f"  表 {t} 的最大 {id_col} 為: {max_val}")
    except Exception as e:
        print(f"  查詢表 {t} 出錯:", e)
conn.close()
