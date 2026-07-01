# -*- coding: utf-8 -*-
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ver = "00500024"
url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/DB/redive_tw.db"
target = "dashboard/redive_tw.db"
backup = "dashboard/redive_tw.db.bak"

headers = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

# 刪除無效的備份，免得後續還原又被覆蓋
if os.path.exists(backup):
    print("🗑️ 刪除無效的舊備份...")
    os.remove(backup)

print(f"📥 正在從 So-net CDN 下載最新的台服資料庫 (Version: {ver})...")
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(target, "wb") as f:
        f.write(data)
    print(f"✅ 下載完成！儲存至 {target} (大小: {len(data)} 字元)")
except Exception as e:
    print(f"❌ 下載失敗: {e}")
