# -*- coding: utf-8 -*-
import sys

print(
    "[LEGACY ARCHIVE ONLY] This historical one-off script is disabled. "
    "Use the current Story Map fetch/maintenance workflow instead."
)
sys.exit(1)

import urllib.request
import os

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在從 Estertion 鏡像站下載若菜(冬日)與栞(冬日)的高清 3 星立繪 ===")

urls = {
    "dashboard/card/full/138731.webp": "https://redive.estertion.win/card/full/138731.webp",
    "dashboard/card/full/138831.webp": "https://redive.estertion.win/card/full/138831.webp",
    # 也下載她們的 1星/3星 頭像 (以防本地缺失或有損壞)
    "dashboard/icon/unit/138731.png": "https://redive.estertion.win/icon/unit/138731.png",
    "dashboard/icon/unit/138831.png": "https://redive.estertion.win/icon/unit/138831.png"
}

for local_path, url in urls.items():
    # 建立目錄
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            with open(local_path, 'wb') as out_file:
                out_file.write(response.read())
        print(f"✅ 下載成功: {url} -> {local_path} | 大小: {os.path.getsize(local_path)} bytes")
    except Exception as e:
        print(f"❌ 下載失敗: {url} | 原因: {e}")
