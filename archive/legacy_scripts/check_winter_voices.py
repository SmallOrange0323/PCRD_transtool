#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性檢測冬日角色語音在本地 (dashboard/sound/story_vo) 的收錄狀態。
"""

import sys
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
SOUND_DIR = DASHBOARD_DIR / "sound" / "story_vo"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在檢測冬日角色語音在本地 (GitHub 準備區) 的收錄狀態 ===")

    # 若菜(冬日) story_id 1387001 ~ 1387004 -> 語音檔 vo_adv_1387001_xxx.m4a
    # 栞(冬日) story_id 1388001 ~ 1388004 -> 語音檔 vo_adv_1388001_xxx.m4a

    if not SOUND_DIR.exists():
        print(f"[WARN] 找不到本地語音資料夾: {SOUND_DIR}")
        return

    all_files = [f.name for f in SOUND_DIR.iterdir() if f.is_file()]

    wakana_voices = [f for f in all_files if '138700' in f]
    shiori_voices = [f for f in all_files if '138800' in f]

    print(f"- 若菜（冬日）[138700] 本地語音檔案數量: {len(wakana_voices)} 個")
    if len(wakana_voices) > 0:
        print(f"  樣本: {wakana_voices[:5]}")
        
    print(f"- 栞（冬日）[138800] 本地語音檔案數量: {len(shiori_voices)} 個")
    if len(shiori_voices) > 0:
        print(f"  樣本: {shiori_voices[:5]}")

if __name__ == "__main__":
    main()
