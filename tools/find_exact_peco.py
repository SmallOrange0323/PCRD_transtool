# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
if not os.path.exists(db_path):
    db_path = 'dashboard/redive_jp.db'

print(f"=== 在資料庫 {db_path} 搜尋所有佩可 (Pecorine) 相關角色資料 ===")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_name LIKE '%佩可%' OR unit_name LIKE '%ペコ%' ORDER BY unit_id ASC")
rows = cur.fetchall()

print(f"找到 {len(rows)} 個佩可相關條目：")
for uid, name in rows:
    # 測試 CDN 資源
    url_3 = f"https://redive.estertion.win/icon/unit/{uid}.webp"
    cdn_ok = False
    try:
        res = urllib.request.urlopen(urllib.request.Request(url_3, headers={'User-Agent': 'Mozilla/5.0'}), timeout=2)
        if res.status == 200: cdn_ok = True
    except: pass
    
    print(f"ID: {uid:6d} | 名稱: {name:20s} | CDN 3星頭像: {'✅ 已上架' if cdn_ok else '❌ 未獲取'}")
