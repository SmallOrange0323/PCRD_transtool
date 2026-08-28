#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Deployer
負責執行發布前驗證門禁，並將 dist_story_map/ 獨立 working tree 推送至 GitHub Pages。
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.validate import validate_story_map

try:
    from pcrd_deploy import (
        cmd_push_pages as push_to_pages,
        cmd_inject_character as inject_character,
        cmd_monitor as monitor_deployment,
        main as pcrd_deploy_main
    )
except ImportError as e:
    print(f"[ERROR] 無法載入 tools/pcrd_deploy.py: {e}", file=sys.stderr)
    sys.exit(1)

def run_deploy(message: str = None, dry_run: bool = False) -> bool:
    """
    執行帶有門禁驗證之部署
    """
    # 1. 執行單一驗證門禁 (驗證 dist_story_map)
    if not validate_story_map(check_dist=True):
        print("[ERROR] 部署前自檢未通過，終止發布！", file=sys.stderr)
        return False

    if dry_run:
        print("[DRY-RUN] 模擬部署模式：驗證通過，不執行 Git 提交與推送。")
        return True

    # 構造 args
    class DeployArgs:
        def __init__(self, msg):
            self.message = msg
            self.output = "tools/push_report.json"

    args = DeployArgs(message)
    return push_to_pages(args)

if __name__ == "__main__":
    pcrd_deploy_main()
