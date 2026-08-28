#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜尋指定劇情 JSON (如 1383001.json) 中的特殊節點 (插畫、背景、影片、特效)。
"""

import sys
import json
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
STORY_DIR = DASHBOARD_DIR / "story"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    target_file = STORY_DIR / "1383001.json"
    if not target_file.exists():
        print(f"[ERROR] 找不到劇情檔案: {target_file}")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        dialogue = json.load(f)

    print("=== 正在搜尋 1383001.json 中的特殊節點 (插畫、背景、影片) ===")
    special_nodes = [
        item for item in dialogue
        if "type" in item or "stillId" in item or "bg" in item or "still" in item
    ]
    print(f"找到 {len(special_nodes)} 個特殊節點：")
    for idx, node in enumerate(special_nodes[:15]):
        print(f"  [{idx}]", node)

if __name__ == "__main__":
    main()
