# -*- coding: utf-8 -*-
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

ver = "00500024"
chara_id = 138301
u1 = chara_id
u3 = chara_id + 30

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_DIR = os.path.join(BASE_DIR, "dashboard", "versions", f"20260701_{ver}")
GLOBAL_ICON_DIR = os.path.join(BASE_DIR, "dashboard", "icon", "unit")
GLOBAL_CARD_DIR = os.path.join(BASE_DIR, "dashboard", "card", "full")
GLOBAL_STILL_DIR = os.path.join(BASE_DIR, "dashboard", "still")

# 確保所有目錄存在
os.makedirs(VERSION_DIR, exist_ok=True)
os.makedirs(GLOBAL_ICON_DIR, exist_ok=True)
os.makedirs(GLOBAL_CARD_DIR, exist_ok=True)
os.makedirs(GLOBAL_STILL_DIR, exist_ok=True)

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

# 下載清單與多目的地儲存定義
assets_to_download = [
    # 1. 1星與3星頭像
    {
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{u1}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"unit_icon_{u1}.webp"),
            os.path.join(GLOBAL_ICON_DIR, f"unit_icon_{u1}.webp")
        ],
        "desc": "1星頭像"
    },
    {
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{u3}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"unit_icon_{u3}.webp"),
            os.path.join(GLOBAL_ICON_DIR, f"unit_icon_{u3}.webp")
        ],
        "desc": "3星頭像"
    },
    # 2. 3星卡面大圖立繪
    {
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Card/Full/card_full_{u3}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"card_full_{u3}.webp"),
            os.path.join(GLOBAL_CARD_DIR, f"card_full_{u3}.webp")
        ],
        "desc": "3星立繪大圖"
    },
    # 3. 劇情靜態 CG (嘗試下載可能的名稱)
    {
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Still/Unit/still_unit_{u3}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"still_unit_{u3}.webp"),
            os.path.join(GLOBAL_STILL_DIR, f"still_unit_{u3}.webp")
        ],
        "desc": "個人劇情 CG (3星)"
    },
    {
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Still/Unit/still_unit_{u1}.webp",
        "targets": [
            os.path.join(VERSION_DIR, f"still_unit_{u1}.webp"),
            os.path.join(GLOBAL_STILL_DIR, f"still_unit_{u1}.webp")
        ],
        "desc": "個人劇情 CG (1星)"
    }
]

# 4. Spine 戰鬥與大廳骨架資源 (sdbattle & sdhall)
for ext in [".atlas", ".png", ".skel"]:
    # 戰鬥骨架
    assets_to_download.append({
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Spine/SDBattle/sdbattle_{u1}{ext}",
        "targets": [os.path.join(VERSION_DIR, f"sdbattle_{u1}{ext}")],
        "desc": f"Spine 戰鬥骨架 ({ext})"
    })
    # 房間/大廳骨架
    assets_to_download.append({
        "url": f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Spine/SDHall/sdhall_{u3}{ext}",
        "targets": [os.path.join(VERSION_DIR, f"sdhall_{u3}{ext}")],
        "desc": f"Spine 大廳骨架 ({ext})"
    })

print("====================================================")
print("📥 開始從 So-net CDN 下載阿斯特萊亞佩可美術與骨架素材...")
print("====================================================")

success = 0
failed = 0

for item in assets_to_download:
    url = item["url"]
    desc = item["desc"]
    
    # 嘗試下載
    try:
        req = urllib.request.Request(url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = response.read()
            
        # 寫入多個目的地
        for target in item["targets"]:
            # 建立父目錄以防萬一
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
                
        print(f"✅ [成功] 下載 {desc} -> {os.path.basename(item['targets'][0])}")
        success += 1
    except Exception as e:
        # 有些非必備素材 (如劇情CG) 若不存在 (404) 則正常跳過
        if "404" in str(e):
            print(f"⚠️ [跳過/CDN未實裝] {desc}")
        else:
            print(f"❌ [失敗] {desc} 下載失敗: {e}")
            failed += 1

print("====================================================")
print(f"🎉 素材下載完成！ 成功: {success} 筆, 失敗: {failed} 筆")
print(f"📁 素材儲存目錄: {VERSION_DIR}")
print("====================================================")
