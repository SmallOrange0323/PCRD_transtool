# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測若菜(冬日)與栞(冬日)的個人故事 JSON 與美術素材狀態 ===")

# 若菜(冬日) ID: 138701 -> 對白 story_id: 1387001 ~ 1387004
# 栞(冬日) ID: 138801 -> 對白 story_id: 1388001 ~ 1388004

roles = {
    "若菜(冬日) [ID: 138701]": {
        "unit_id": 138701,
        "story_prefix": "13870",
        "icon_file": "dashboard/icon/unit/138731.png",
        "card_file": "dashboard/card/full/138731.webp"
    },
    "栞(冬日) [ID: 138801]": {
        "unit_id": 138801,
        "story_prefix": "13880",
        "icon_file": "dashboard/icon/unit/138831.png",
        "card_file": "dashboard/card/full/138831.webp"
    }
}

for name, info in roles.items():
    print(f"\n🔍 角色: {name}")
    # 檢查美術檔案是否存在
    icon_exist = os.path.exists(info["icon_file"])
    card_exist = os.path.exists(info["card_file"])
    print(f"  - 頭像是否存在: {icon_exist} ({info['icon_file']})")
    print(f"  - 立繪是否存在: {card_exist} ({info['card_file']})")
    
    # 檢查對白 JSON
    json_status = []
    for i in range(1, 5):
        json_path = f"dashboard/story/{info['story_prefix']}0{i}.json"
        if os.path.exists(json_path):
            json_status.append(f"第 {i} 話: 已下載")
        else:
            json_status.append(f"第 {i} 話: ❌ 缺失")
    print("  - 個人對白故事狀態:", ", ".join(json_status))
