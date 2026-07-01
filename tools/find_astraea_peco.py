# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在搜尋是否存在『貪吃佩可（阿斯特萊亞）』或相關 Astraea 角色 ===")

dbs = ['dashboard/redive_tw.db', 'dashboard/redive_jp.db']

for db_path in dbs:
    if os.path.exists(db_path):
        print(f"\n--- 檢查資料庫 {db_path} ---")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # 1. 搜尋包含阿斯特萊亞 / Astraea / アストレア 的角色
        cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_name LIKE '%阿斯特%' OR unit_name LIKE '%アストレア%' OR unit_name LIKE '%Astraea%' GROUP BY unit_name")
        rows = cur.fetchall()
        print(f"找到 {len(rows)} 個 Astraea 相關角色名稱：", rows)
        
        # 2. 搜尋所有佩可莉姆 / 佩可 相關名稱
        cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_name LIKE '%佩可%' OR unit_name LIKE '%ペコ%' GROUP BY unit_name")
        peco_rows = cur.fetchall()
        print(f"\n目前資料庫記錄的所有佩可型態：")
        for u in peco_rows:
            print(f"  - ID: {u[0]} | 名稱: {u[1]}")
