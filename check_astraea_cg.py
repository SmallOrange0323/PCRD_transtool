# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在探針檢測阿斯特萊亞佩可劇照 CG (still_id: 91002) 圖片資源 ===")

# 測試多種可能的大圖網址
urls = [
    ("91002.webp (story)", "https://redive.estertion.win/card/story/91002.webp"),
    ("91002.png (story)", "https://redive.estertion.win/card/story/91002.png"),
    ("91002.webp (full)", "https://redive.estertion.win/card/full/91002.webp"),
    ("1383004.webp (story)", "https://redive.estertion.win/card/story/1383004.webp"),
]

for desc, url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200:
            print(f"✅ [已實裝] {desc} -> 成功獲取！網址: {url}")
            continue
    except:
        pass
    print(f"❌ [未實裝] {desc}")
