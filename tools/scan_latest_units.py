# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在掃描最新 130000~138000 角色 ID 區間的 CDN 上架狀態 ===")

# 測試最新角色的 3 星頭像 (ID 格式 13xx31.webp)
found = []
for cid in range(1300, 1380):
    uid = int(f"{cid}31")
    url = f"https://redive.estertion.win/icon/unit/{uid}.webp"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=1.5)
        if res.status == 200:
            found.append(uid)
    except:
        pass

print(f"掃描完成！在最新區間找到 {len(found)} 個最新角色頭像：", found[-15:] if len(found) > 15 else found)
