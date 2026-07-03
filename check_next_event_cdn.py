# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在探針檢測 So-net 台服 CDN 上下個月新形式活動 (ID: 10215) 資源 ===")

# 新形式活動 ID: 10215
# 宣傳縮圖 ID 通常為：5215401
# 其個人/活動故事對白檔 ID 通常是 5215001 ~ 5215008 或者是 5215051 ~ 5215058
# 其語音檔命名為 vo_adv_5215001_000.m4a ...

urls = [
    ("10215 活動宣傳圖 (5215401.webp)", "https://redive.estertion.win/card/full/5215401.webp"),
    ("10215 活動對白語音 vo_adv_5215001_000.m4a", "https://redive.estertion.win/sound/story_vo/vo_adv_5215001_000.m4a"),
    ("10215 戰鬥 Spine 動態圖 (10215.atlas)", "https://redive.estertion.win/spine/unit/10215/10215.atlas"),
]

for desc, url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200:
            print(f"✅ [台服 CDN 已實裝] {desc} -> 成功讀取！網址: {url}")
            continue
    except Exception as e:
        pass
    print(f"❌ [台服 CDN 尚未實裝/404] {desc}")
