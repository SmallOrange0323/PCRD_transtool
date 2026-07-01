# -*- coding: utf-8 -*-
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

chara_id = 138301
u1 = chara_id
u3 = chara_id + 30

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_DIR = os.path.join(BASE_DIR, "dashboard", "versions", "20260701_00500024")
GLOBAL_ICON_DIR = os.path.join(BASE_DIR, "dashboard", "icon", "unit")
GLOBAL_CARD_DIR = os.path.join(BASE_DIR, "dashboard", "card", "full")

os.makedirs(VERSION_DIR, exist_ok=True)
os.makedirs(GLOBAL_ICON_DIR, exist_ok=True)
os.makedirs(GLOBAL_CARD_DIR, exist_ok=True)

HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 定義下載任務
tasks = [
    # 1. 1星與3星頭像
    {
        "url": f"https://redive.estertion.win/icon/unit/{u1}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"unit_icon_{u1}.webp"),
            os.path.join(GLOBAL_ICON_DIR, f"unit_icon_{u1}.webp")
        ],
        "desc": "1星頭像"
    },
    {
        "url": f"https://redive.estertion.win/icon/unit/{u3}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"unit_icon_{u3}.webp"),
            os.path.join(GLOBAL_ICON_DIR, f"unit_icon_{u3}.webp")
        ],
        "desc": "3星頭像"
    },
    # 2. 3星立繪大圖
    {
        "url": f"https://redive.estertion.win/card/full/{u3}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"card_full_{u3}.webp"),
            os.path.join(GLOBAL_CARD_DIR, f"card_full_{u3}.webp")
        ],
        "desc": "3星立繪大圖"
    }
]

# 3. Spine 大廳/房間骨架 (SDHall)
for ext in [".atlas", ".png", ".skel"]:
    tasks.append({
        "url": f"https://redive.estertion.win/spine/unit/{u3}/{u3}{ext}",
        "targets": [os.path.join(VERSION_DIR, f"sdhall_{u3}{ext}")],
        "desc": f"Spine 大廳骨架 ({ext})"
    })

# 4. Spine 戰鬥骨架 (SDBattle) - 探測可能之路徑
# 戰鬥骨架在 EsterTion 上通常有幾種可能路徑：
# A. https://redive.estertion.win/spine/common/sdbattle_{u1}{ext}
# B. https://redive.estertion.win/spine/unit/{u1}/sdbattle_{u1}{ext} (或是 sdbattle_{u1} 放在 unit 目錄下)
for ext in [".atlas", ".png", ".skel"]:
    # 我們可以放多個可能的 URL，成功一個即可
    tasks.append({
        "urls": [
            f"https://redive.estertion.win/spine/common/sdbattle_{u1}{ext}",
            f"https://redive.estertion.win/spine/unit/{u1}/sdbattle_{u1}{ext}",
            f"https://redive.estertion.win/spine/unit/{u1}/{u1}{ext}" # 備用
        ],
        "targets": [os.path.join(VERSION_DIR, f"sdbattle_{u1}{ext}")],
        "desc": f"Spine 戰鬥骨架 ({ext})"
    })

print("====================================================")
print("📥 開始下載阿斯特萊亞佩可美術與骨架素材 (來源: EsterTion)...")
print("====================================================")

success = 0
failed = 0

for item in tasks:
    urls = item.get("urls", [item.get("url")])
    desc = item["desc"]
    
    data = None
    download_url = None
    
    for url in urls:
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers=HEADER)
            with urllib.request.urlopen(req, timeout=8) as response:
                data = response.read()
                download_url = url
                break
        except Exception:
            pass
            
    if data:
        # 寫入目標檔案
        for target in item["targets"]:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
        print(f"✅ [成功] {desc} 下載完成")
        success += 1
    else:
        print(f"❌ [失敗] 無法下載 {desc}")
        failed += 1

print("====================================================")
print(f"🎉 下載結束！ 成功: {success} 筆, 失敗: {failed} 筆")
print("====================================================")
