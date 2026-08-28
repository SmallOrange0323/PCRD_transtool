# -*- coding: utf-8 -*-
import sys

print(
    "[LEGACY ARCHIVE ONLY] This historical one-off script is disabled. "
    "Use the current Story Map fetch/maintenance workflow instead."
)
sys.exit(1)

import json
import os
import shutil

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在進行冬日換裝角色 tracked_characters.json 更新與美術檔名規範化 ===")

# 1. 更新 tracked_characters.json 登錄 138801 (栞 冬日)
tracked_path = 'dashboard/data/tracked_characters.json'
if os.path.exists(tracked_path):
    with open(tracked_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 檢查是否已收錄 138801
    has_shiori = any(char.get("unit_id") == 138801 for char in data.get("characters", []))
    if not has_shiori:
        data["characters"].append({
            "unit_id": 138801,
            "name": "栞（冬日）",
            "icon_ids": [138801, 138831],
            "card_ids": [138831]
        })
        with open(tracked_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ 已在 tracked_characters.json 中登錄 栞（冬日）！")
    else:
        print("tracked_characters.json 已有 栞（冬日） 的紀錄。")

# 2. 規範化頭像與立繪檔名，使之符合打包腳本的 unit_icon_{id}.webp 與 card_full_{id}.webp 格式
# 我們本地有：
# dashboard/icon/unit/138731.png -> 需要 unit_icon_138731.webp
# dashboard/icon/unit/138831.png -> 需要 unit_icon_138831.webp
# dashboard/card/full/138731.webp -> 需要 card_full_138731.webp
# dashboard/card/full/138831.webp -> 需要 card_full_138831.webp

assets_mapping = {
    # 來源 -> 目標
    "dashboard/card/full/138731.webp": "dashboard/card/full/card_full_138731.webp",
    "dashboard/card/full/138831.webp": "dashboard/card/full/card_full_138831.webp",
    "dashboard/icon/unit/138731.png": "dashboard/icon/unit/unit_icon_138731.webp",
    "dashboard/icon/unit/138831.png": "dashboard/icon/unit/unit_icon_138831.webp",
    # 1星頭像
    "dashboard/icon/unit/138701.png": "dashboard/icon/unit/unit_icon_138701.webp",
    "dashboard/icon/unit/138801.png": "dashboard/icon/unit/unit_icon_138801.webp"
}

for src, dst in assets_mapping.items():
    if os.path.exists(src):
        # 建立目錄
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # 進行拷貝 (如果是 png 拷貝為 webp 也可以在前端顯示，因為網頁瀏覽器會自動識別編碼，
        # 不過為保險起見我們也試著用 PIL 轉換為真 WebP)
        try:
            from PIL import Image
            im = Image.open(src)
            im.save(dst, "WEBP")
            print(f"✅ PIL 轉換成功: {src} -> {dst}")
        except Exception as e:
            # Fallback: 直接拷貝
            shutil.copy2(src, dst)
            print(f"⚠️ PIL 轉換失敗，直接拷貝: {src} -> {dst} | 原因: {e}")
    else:
        print(f"❌ 找不到來源美術檔案: {src}")
