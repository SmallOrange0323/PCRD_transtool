# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

print("=== 正在日版資料庫中搜尋新形式活動的真實數據 ===")

# 我們在所有的資料表中搜尋 "SPLASH" 或 "若葉" (Wakana) 或 "栞" (Shiori) 相關的活動標題
# 日版名: "爆熱！ピーチバンプチャンピオンシップ" 或是 "ワカナ" (Wakana) / "シオリ" (Shiori)
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

for t in tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [col[1] for col in cur.fetchall()]
        
        # 尋找有 title 或 sub_title 或 name 的欄位
        text_cols = [c for c in cols if 'title' in c or 'name' in c]
        if text_cols:
            for col in text_cols:
                # 模糊搜尋
                cur.execute(f"SELECT * FROM {t} WHERE {col} LIKE '%ピーチバンプ%' OR {col} LIKE '%バンプ%' LIMIT 3")
                res = cur.fetchall()
                if res:
                    print(f"在表 {t} 的欄位 {col} 中找到相關資料:")
                    for r in res:
                        print("  ", r)
    except Exception as e:
        pass

conn.close()
