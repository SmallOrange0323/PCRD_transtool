#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性檢測 1808001 (禊＆美美＆鏡華) 本地對白與語音存在狀態。
"""

import sys
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
STORY_DIR = DASHBOARD_DIR / "story"
SOUND_DIR = DASHBOARD_DIR / "sound" / "story_vo"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在檢測 1808001 (禊＆美美＆鏡華) 本地對白與語音存在狀態 ===")

    for i in range(1, 5):
        p = STORY_DIR / f"180800{i}.json"
        print(f"  - 故事 JSON {p.name} 是否存在: {p.exists()}")
        
    # 檢測語音
    if SOUND_DIR.exists():
        files = [f.name for f in SOUND_DIR.iterdir() if f.is_file() and '180800' in f.name]
        print(f"  - 本地語音檔案數量: {len(files)} 個")
    else:
        print(f"  - [WARN] 找不到本地語音資料夾: {SOUND_DIR}")

if __name__ == "__main__":
    main()
