# -*- coding: utf-8 -*-
"""
[DEPRECATED] dashboard/scripts/bundle_story_map.py
此腳本已廢棄。為了維持 100% 決定性封裝與體積防護，本腳本已轉為相容包裝器，
直接委派至專案唯一權威打包器: pipeline.bundle (bundle_story_map)。
請直接使用:
    python -m pipeline.bundle
或
    python update_story_map.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import bundle_story_map

def main():
    print("[WARN] dashboard/scripts/bundle_story_map.py 已廢棄，自動委派至唯一權威打包器 pipeline.bundle。")
    dry_run = "--dry-run" in sys.argv
    success = bundle_story_map(dry_run=dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
