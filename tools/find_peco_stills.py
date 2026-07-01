# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 獲取所有 v1_ 表
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
tables = [row[0] for row in cur.fetchall()]

# 尋找含有 1001001 且欄位數較少的表 (通常 story_still 只有 2 欄：story_id, still_id)
still_table = None
story_col = None
still_col = None

for table in tables:
    try:
        cur.execute(f"PRAGMA table_info(\"{table}\")")
        cols = [col[1] for col in cur.fetchall()]
        for c in cols:
            cur.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{c}\" = 1383001")
            if cur.fetchone()[0] > 0:
                still_table = table
                story_col = c
                # 找出含有 7 位數或 8 位數 CG ID 的欄位
                cur.execute(f"SELECT * FROM \"{table}\" WHERE \"{c}\" = 1383001 LIMIT 5")
                rows = cur.fetchall()
                for r in rows:
                    for idx, val in enumerate(r):
                        if isinstance(val, int) and (10000000 <= val <= 99999999) and val != 1383001:
                            still_col = cols[idx]
                            break
                if still_col:
                    break
        if still_table and still_col:
            break
    except Exception:
        pass

if still_table:
    print(f"🎯 找到故事與 CG 關聯表: {still_table}")
    # 查詢 1383001 ~ 1383004 關聯的 CG
    cur.execute(f"SELECT \"{story_col}\", \"{still_col}\" FROM \"{still_table}\" WHERE \"{story_col}\" >= 1383000 AND \"{story_col}\" < 1383100")
    rows = cur.fetchall()
    
    # 建立下載目錄
    still_dir = "dashboard/still"
    os.makedirs(still_dir, exist_ok=True)
    version_dir = "dashboard/versions/20260701_00500024"
    os.makedirs(version_dir, exist_ok=True)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for r in rows:
        story_id, still_id = r[0], r[1]
        print(f"  - 故事 ID: {story_id} | 關聯 CG ID: {still_id}")
        
        # 測試並下載 EsterTion 的 CG 網址
        url = f"https://redive.estertion.win/card/still/{still_id}.webp"
        target_path_global = os.path.join(still_dir, f"{still_id}.webp")
        target_path_ver = os.path.join(version_dir, f"still_{still_id}.webp")
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            with open(target_path_global, "wb") as f:
                f.write(data)
            with open(target_path_ver, "wb") as f:
                f.write(data)
            print(f"    ✅ 成功下載劇情 CG: {still_id}.webp")
        except Exception as e:
            print(f"    ❌ 下載劇情 CG 失敗: {e}")
else:
    print("❌ 未能定位故事與 CG 關聯表")

conn.close()
