#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性檢測若菜(冬日)與栞(冬日)的個人故事 JSON 與美術素材狀態。
"""

import sys
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在檢測若菜(冬日)與栞(冬日)的個人故事 JSON 與美術素材狀態 ===")

    # 若菜(冬日) ID: 138701 -> 對白 story_id: 1387001 ~ 1387004
    # 栞(冬日) ID: 138801 -> 對白 story_id: 1388001 ~ 1388004

    roles = {
        "若菜(冬日) [ID: 138701]": {
            "unit_id": 138701,
            "story_prefix": "13870",
            "icon_path": DASHBOARD_DIR / "icon" / "unit" / "138731.png",
            "card_path": DASHBOARD_DIR / "card" / "full" / "138731.webp"
        },
        "栞(冬日) [ID: 138801]": {
            "unit_id": 138801,
            "story_prefix": "13880",
            "icon_path": DASHBOARD_DIR / "icon" / "unit" / "138831.png",
            "card_path": DASHBOARD_DIR / "card" / "full" / "138831.webp"
        }
    }

    for name, info in roles.items():
        print(f"\n🔍 角色: {name}")
        icon_exist = info["icon_path"].exists()
        card_exist = info["card_path"].exists()
        print(f"  - 頭像是否存在: {icon_exist} ({info['icon_path'].relative_to(PROJECT_ROOT)})")
        print(f"  - 立繪是否存在: {card_exist} ({info['card_path'].relative_to(PROJECT_ROOT)})")
        
        # 檢查對白 JSON
        json_status = []
        for i in range(1, 5):
            json_path = DASHBOARD_DIR / "story" / f"{info['story_prefix']}0{i}.json"
            if json_path.exists():
                json_status.append(f"第 {i} 話: 已下載")
            else:
                json_status.append(f"第 {i} 話: ❌ 缺失")
        print("  - 個人對白故事狀態:", ", ".join(json_status))

if __name__ == "__main__":
    main()
