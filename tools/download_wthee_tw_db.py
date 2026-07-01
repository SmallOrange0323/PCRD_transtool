# -*- coding: utf-8 -*-
import urllib.request
import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

url = "https://wthee.xyz/db/redive_tw.db"
target = "dashboard/redive_tw.db"

HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print("====================================================")
print("📥 開始從 wthee 鏡像站下載解密明文的台服最新資料庫...")
print("====================================================")

try:
    req = urllib.request.Request(url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    
    with open(target, "wb") as f:
        f.write(data)
        
    print(f"✅ 下載完成！儲存至 {target} (大小: {len(data)} 位元組)")
    
    # 進行查核
    conn = sqlite3.connect(target)
    cur = conn.cursor()
    
    # 檢查 unit_data 是否存在且包含 138301
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unit_data'")
    if cur.fetchone():
        print("  - [檢查] unit_data 資料表存在")
        cur.execute("SELECT COUNT(*) FROM unit_data WHERE unit_id = 138301")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print("  - [檢查] 🔥 wthee 資料庫中已包含「阿斯特萊亞佩可 (138301)」的最新數據！")
        else:
            print("  - [檢查] ⚠️ 尚未包含 138301 數據，我們稍後將由網頁進行平穩展示。")
    else:
        print("  - [檢查] ❌ 未能找到 unit_data 資料表，這可能不是明文資料庫。")
        
    conn.close()

except Exception as e:
    print(f"❌ 下載還原失敗: {e}")
print("====================================================")
