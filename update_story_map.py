#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map 一鍵自動化更新入口
用法：
  python update_story_map.py --dry-run   # 模擬運行（零副作用）：不寫入檔案、不提交 Git
  python update_story_map.py             # 本地打包與驗證門禁 (預設不部署)
  python update_story_map.py --deploy    # 驗證通過後自動推送到 GitHub Pages
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.update import main

if __name__ == "__main__":
    main()
