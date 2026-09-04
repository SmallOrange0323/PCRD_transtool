#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Deployer
負責執行發布前驗證門禁，並將 dist_story_map/ 獨立 working tree 推送至 GitHub Pages。
嚴格遵守職責單一：只推送 dist_story_map 至 gh-pages，絕不推送 source branch。
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist_story_map"

from pipeline.validate import validate_story_map

def _run_git_in_dist(args: list) -> tuple[int, str]:
    """在 dist_story_map/ 獨立 working tree 執行 git 指令"""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(DIST_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)

def run_deploy(message: str = None, dry_run: bool = False) -> bool:
    """
    執行帶有門禁驗證之部署
    :param message: Git commit 訊息
    :param dry_run: 模擬部署模式，不提交、不推送
    :return: True 部署成功, False 部署失敗
    """
    print("\n🚀 啟動 Story Map 發布流程...")

    # 1. 執行單一驗證門禁 (驗證 dist_story_map)
    if not validate_story_map(check_dist=True):
        print("❌ [ERROR] 部署前自檢未通過，終止發布！", file=sys.stderr)
        return False

    if dry_run:
        print("  [DRY-RUN] 模擬部署模式：驗證通過，不執行 Git 提交與推送。")
        return True

    # 2. 確認 dist_story_map/.git 存在
    dist_git = DIST_DIR / ".git"
    if not dist_git.exists():
        print(f"❌ [ERROR] {DIST_DIR} 缺少 .git 獨立部署目錄！", file=sys.stderr)
        return False

    # 3. 在 dist_story_map 執行 git add, commit, push
    commit_msg = message or "deploy: update story map production build"
    print(f"  [Git] 正在為 dist_story_map 建立發布 commit: {commit_msg}")

    code, out = _run_git_in_dist(["add", "-A"])
    if code != 0:
        print(f"❌ [ERROR] dist git add 失敗: {out}", file=sys.stderr)
        return False

    code, out = _run_git_in_dist(["status", "--porcelain"])
    if not out:
        print("  [Git] dist_story_map 無新變更需要提交。")
    else:
        code, out = _run_git_in_dist(["commit", "-m", commit_msg])
        if code != 0:
            print(f"❌ [ERROR] dist git commit 失敗: {out}", file=sys.stderr)
            return False
        print(f"  [Git] commit 成功: {out.splitlines()[-1] if out else ''}")

    print("  [Git] 正在推送至 GitHub Pages (origin gh-pages)...")
    code, out = _run_git_in_dist(["push", "origin", "HEAD:gh-pages"])
    if code != 0:
        print(f"❌ [ERROR] dist git push 失敗: {out}", file=sys.stderr)
        return False

    print("✅ Story Map 成功部署至 GitHub Pages！")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PCRD Story Map GitHub Pages 部署工具")
    parser.add_argument("-m", "--message", type=str, default=None, help="Commit 訊息")
    parser.add_argument("--dry-run", action="store_true", help="模擬運行，不提交、不推送")
    args = parser.parse_args()

    success = run_deploy(message=args.message, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
