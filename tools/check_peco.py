# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('redive_tw.db')
cur = conn.cursor()

print("=== 資料庫中現有的佩可 (Pecorine) 相關角色 ===")
cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_name LIKE '%佩可%' GROUP BY unit_name")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {r[0]}, Name: {r[1]}")

print("\n=== 檢查日版/台版潛在最新佩可換裝角色 ID (100101 ~ 100115) 資源狀況 ===")
# 佩可的核心編號區間為 1001xx (100101: 原版, 100102: 夏日, 100103: 公主, 100104: 超載/OVERLOAD, 100105: 新年, 等)
base_ids = [100101, 100102, 100103, 100104, 100105, 100106, 100107, 100108, 100109, 100110]

for uid in base_ids:
    url = f"https://redive.estertion.win/icon/unit/{uid}31.webp"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200:
            print(f"[Exist] Unit ID {uid} (3星頭像: {uid}31.webp) 在鏡像站可讀取！")
    except Exception:
        print(f"[Missing] Unit ID {uid} 尚無 3 星頭像資源")
