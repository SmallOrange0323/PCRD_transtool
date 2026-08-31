#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map 一鍵自動化更新入口
用法：
  python update_story_map.py --dry-run                        # 模擬運行（零副作用）：不寫入檔案、不提交 Git
  python update_story_map.py                                  # 本地增量同步、打包與全量驗證 (預設不部署)
  python update_story_map.py --coverage                       # 僅輸出唯讀劇本覆蓋率分析報告
  python update_story_map.py --deploy                         # 本地更新、新鮮度與全量驗證通過後自動推送到 GitHub Pages
  python update_story_map.py --deploy --allow-unconfirmed-freshness  # 緊急模式：覆蓋新鮮度門禁進行發布
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.update import main

if __name__ == "__main__":
    main()
