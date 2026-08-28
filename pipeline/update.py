#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Update Orchestrator (統一更新協調器)
提供一鍵從 CDN 探測、同步、封裝、驗證到發布的完整流程。

Exit Codes:
  0 = success
  1 = runtime / validation failure
  2 = invalid configuration / missing required dependency
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.bundle import bundle_story_map
from pipeline.validate import validate_story_map
from pipeline.deploy import run_deploy

def run_pipeline_update(dry_run: bool = False, auto_deploy: bool = False, message: str = None) -> int:
    """
    執行一鍵更新管線
    :return: exit code (0=成功, 1=執行或驗證失敗, 2=環境或依賴缺失)
    """
    print("=" * 60)
    print("🚀 PCRD 劇情地圖 (Story Map) 自動化更新管線啟動")
    print(f"模式: {'[DRY-RUN 零副作用模擬]' if dry_run else ('[更新 + 自動發布]' if auto_deploy else '[本地更新與驗證]')}")
    print("=" * 60)

    # 1. 探測 CDN 狀態
    print("\n[步驟 1/3] 探測 So-net CDN 狀態...")
    try:
        from pipeline.fetch import get_truth_version
        tv = get_truth_version()
        print(f"  [CDN] 當前 CDN 最高 TruthVersion: {tv}")
    except Exception as e:
        print(f"  [WARN] 無法探測 CDN 版本 (離線或網路異常): {e}")

    # 2. 封裝 Story Map 獨立發布包
    print("\n[步驟 2/3] 執行 Story Map 打包與 Cache-Busting...")
    try:
        bundle_ok = bundle_story_map(dry_run=dry_run)
        if not bundle_ok:
            print("❌ 打包步驟失敗！", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 打包過程發生異常: {e}", file=sys.stderr)
        return 1

    # 3. 執行全量一致性驗證門禁
    print("\n[步驟 3/3] 執行資料完整性驗證門禁...")
    try:
        # 如果是 dry_run，驗證 dashboard 即可；若非 dry_run 則同時檢查 dist
        validate_ok = validate_story_map(check_dist=(not dry_run))
        if not validate_ok:
            print("❌ 驗證門禁未通過！", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 驗證過程發生異常: {e}", file=sys.stderr)
        return 1

    # 4. 可選部署 (只有明確指定 auto_deploy 且非 dry_run 時執行)
    if auto_deploy:
        if dry_run:
            print("\n[部署步驟] [DRY-RUN] 模擬部署模式：驗證通過，不執行 Git 提交與推送。")
        else:
            print("\n[部署步驟] 啟動 GitHub Pages 自動部署...")
            deploy_ok = run_deploy(message=message, dry_run=False)
            if not deploy_ok:
                print("❌ 部署步驟失敗！", file=sys.stderr)
                return 1

    print("\n" + "=" * 60)
    print("🎉 PCRD Story Map 管線執行完畢！所有核心檢查均已通過。")
    print("=" * 60)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="PCRD Story Map 一鍵自動化更新管線",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用範例:
  python update_story_map.py --dry-run   # 零副作用模擬運行
  python update_story_map.py             # 本地打包與驗證門禁 (預設不部署)
  python update_story_map.py --deploy    # 本地更新、驗證通過後自動推送至 GitHub Pages
"""
    )
    parser.add_argument("--dry-run", action="store_true", help="模擬運行（零副作用）：不寫入檔案、不提交 Git")
    parser.add_argument("--deploy", action="store_true", help="驗證通過後自動推送到 GitHub Pages")
    parser.add_argument("-m", "--message", type=str, default=None, help="發布時的 Git Commit 訊息")
    args = parser.parse_args()

    exit_code = run_pipeline_update(
        dry_run=args.dry_run,
        auto_deploy=args.deploy,
        message=args.message
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
