#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統計分析所有個人劇情 JSON 檔案中是否含有 still (圖片) 標註。
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
    print("=== 正在統計分析所有個人劇情 JSON 檔案中是否含有 still (圖片) 標註 ===")

    # 個人劇情的 ID 通常是 7 位數，以 1 開頭 (如 1001001.json ~ 1800000.json)
    files = list(STORY_DIR.glob("1*.json"))
    total_files = len(files)

    if total_files == 0:
        print(f"[WARN] 找不到個人劇情檔案: {STORY_DIR}/1*.json")
        return

    files_with_still = 0
    sample_stills = []

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                dialogue = json.load(fp)
            has_still = any(
                "still" in item or ("type" in item and item.get("type") == "still")
                for item in dialogue
            )
            if has_still:
                files_with_still += 1
                if len(sample_stills) < 5:
                    sample_stills.append(f.name)
        except Exception:
            pass

    print(f"\n📊 統計報告：")
    print(f"- 共有 {total_files} 個個人劇情 JSON 檔案")
    print(f"- 其中含有 still (圖片) 標註的檔案有: {files_with_still} 個")
    print(f"- 比例為: {files_with_still / total_files * 100:.2f}%")
    print(f"- 含有 still 標註的樣版檔案: {sample_stills}")

if __name__ == "__main__":
    main()
