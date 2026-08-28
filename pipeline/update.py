#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Update Orchestrator (統一增量更新協調器)
負責協調完整的 CDN 增量同步、決定性打包、全量驗證與發布。

Story Map Update Pipeline v1 核心能力：
  1. DB sync (TruthVersion 探測、SQLite 增量下載與版本狀態持久化)
  2. Tracked character story JSON sync (逐角色增量補齊缺失好感度劇本)
  3. Deterministic bundle & Cache-Busting (SHA-256 內容比對、體積控制)
  4. Single-source validation gate (9000+ 篇劇本與 dist 集合全量深度自檢)
  5. Optional GitHub Pages deploy (只推送 dist_story_map 至 gh-pages)

Exit Codes:
  0 = success
  1 = runtime / validation failure
  2 = invalid configuration / missing required dependency
"""

import os
import sys
import json
import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.bundle import bundle_story_map
from pipeline.validate import validate_story_map
from pipeline.deploy import run_deploy

def save_truth_version_state(new_version: str) -> bool:
    """
    以原子替換方式更新版本狀態 (P0-2 核心實作)
    """
    if not new_version:
        return False
    ver_dir = DASHBOARD_DIR / "versions"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ver_file = ver_dir / "version_history.json"
    tmp_file = ver_dir / "version_history.json.tmp"
    
    current_data = {}
    if ver_file.exists():
        try:
            with open(ver_file, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass

    current_data["truth_version"] = new_version
    current_data["last_version"] = new_version

    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(ver_file)
        print(f"  [State] 已原子更新本地 TruthVersion 狀態: {new_version}")
        return True
    except Exception as e:
        print(f"  [WARN] 寫入版本狀態失敗: {e}", file=sys.stderr)
        return False

def check_and_sync_upstream(dry_run: bool = False) -> bool:
    """
    探測並執行增量資料同步 (P0-1 與 P0-2 核心實作)
    """
    print("\n[步驟 1/3] 探測 So-net CDN 與執行增量資料同步 (Pipeline v1 Scope)...")
    
    try:
        from pipeline.fetch import get_truth_version, update_db, fetch_stories
    except ImportError as e:
        print(f"❌ [ERROR] 無法載入 fetch 模組: {e}", file=sys.stderr)
        return False

    # 1. 探測 CDN 版號
    remote_tv = None
    try:
        remote_tv = get_truth_version()
        print(f"  [CDN] 線上最高 TruthVersion: {remote_tv}")
    except Exception as e:
        print(f"  [WARN] 無法連接 CDN 探測版號 (離線或逾時): {e}")

    # 2. 比對本地記錄的 TruthVersion
    ver_file = DASHBOARD_DIR / "versions" / "version_history.json"
    local_tv = None
    if ver_file.exists():
        try:
            with open(ver_file, "r", encoding="utf-8") as f:
                vdata = json.load(f)
            local_tv = vdata.get("truth_version") or vdata.get("last_version")
        except Exception:
            pass

    print(f"  [Local] 本地記錄 TruthVersion: {local_tv or '未記錄'}")

    need_db_update = (remote_tv and remote_tv != local_tv) or not (DASHBOARD_DIR / "redive_tw.db").exists()
    
    if need_db_update:
        print(f"  [Sync] 檢測到 CDN 有新版本或本地 DB 缺失 (線上: {remote_tv}, 本地: {local_tv})")
        if dry_run:
            print("  [DRY-RUN] 預計執行: 下載新版台版資料庫 redive_tw.db 並更新 version state")
        else:
            print("  [Sync] 正在下載並解密最新台版 SQLite 資料庫...")
            class MockArgs:
                force = False
                source = "sonet"
                output = "tools/db_update_report.json"
            try:
                update_db(MockArgs())
                if remote_tv:
                    save_truth_version_state(remote_tv)
            except Exception as e:
                print(f"❌ [ERROR] 下載資料庫失敗: {e}", file=sys.stderr)
                return False
    else:
        print("  [Sync] 本地資料庫與 CDN 版號一致，無需重新下載資料庫。")

    # 3. 掃描本地缺失的已追蹤角色對白 (P0-1 核心：按 unit_id 呼叫 downloader)
    db_path = DASHBOARD_DIR / "redive_tw.db"
    missing_unit_ids = []
    total_missing_stories = 0
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            
            tracked_path = DASHBOARD_DIR / "data" / "tracked_characters.json"
            if tracked_path.exists():
                with open(tracked_path, "r", encoding="utf-8") as f:
                    tracked_data = json.load(f)
                for char in tracked_data.get("characters", []):
                    uid = char.get("unit_id")
                    if uid:
                        cur.execute("SELECT story_id FROM story_detail WHERE story_group_id = ?", (uid,))
                        char_story_ids = [row[0] for row in cur.fetchall()]
                        char_missing = [sid for sid in char_story_ids if not (DASHBOARD_DIR / "story" / f"{sid}.json").exists()]
                        if char_missing:
                            missing_unit_ids.append((uid, char.get("name", str(uid)), len(char_missing)))
                            total_missing_stories += len(char_missing)
            conn.close()
        except Exception as e:
            print(f"  [WARN] 掃描缺失劇情時發生異常: {e}")

    if missing_unit_ids:
        print(f"  [Sync] 發現 {len(missing_unit_ids)} 位追蹤角色尚有 {total_missing_stories} 篇對白未下載:")
        for uid, name, count in missing_unit_ids:
            print(f"    - {name} (Unit {uid}): 缺失 {count} 篇")
            
        if dry_run:
            print(f"  [DRY-RUN] 預計執行: 依序為 {len(missing_unit_ids)} 位角色增量抓取對白 JSON")
        else:
            print(f"  [Sync] 正在依序下載缺失角色對白...")
            for uid, name, _ in missing_unit_ids:
                class SingleUnitFetchArgs:
                    def __init__(self, unit_id):
                        self.unit_id = unit_id
                        self.all = False
                        self.output = "tools/story_fetch_report.json"
                try:
                    fetch_stories(SingleUnitFetchArgs(uid))
                except Exception as e:
                    print(f"  [WARN] 下載角色 {name} (Unit {uid}) 劇情失敗: {e}")
    else:
        print("  [Sync] 所有追蹤角色之對白劇本已全數就緒。")

    return True

def run_pipeline_update(dry_run: bool = False, auto_deploy: bool = False, message: str = None) -> int:
    """
    執行一鍵更新管線 (Pipeline v1)
    :return: exit code (0=成功, 1=執行或驗證失敗, 2=環境或依賴缺失)
    """
    print("=" * 60)
    print("🚀 PCRD 劇情地圖 (Story Map) 自動化增量更新管線 (Pipeline v1) 啟動")
    print(f"模式: {'[DRY-RUN 零副作用模擬]' if dry_run else ('[增量同步 + 決定性封裝 + 發布]' if auto_deploy else '[增量同步 + 決定性封裝 + 驗證]')}")
    print("=" * 60)

    # 1. 執行增量同步
    sync_ok = check_and_sync_upstream(dry_run=dry_run)
    if not sync_ok:
        print("❌ 增量同步步驟失敗！", file=sys.stderr)
        return 1

    # 2. 封裝 Story Map 獨立發布包
    print("\n[步驟 2/3] 執行 Story Map 決定性打包與 Cache-Busting...")
    try:
        bundle_ok = bundle_story_map(dry_run=dry_run)
        if not bundle_ok:
            print("❌ 打包步驟失敗！", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 打包過程發生異常: {e}", file=sys.stderr)
        return 1

    # 3. 執行全量一致性驗證門禁
    print("\n[步驟 3/3] 執行全量資料完整性驗證門禁...")
    try:
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
            print("\n[部署步驟] 啟動 GitHub Pages 自動發布 (僅推送 dist_story_map)...")
            deploy_ok = run_deploy(message=message, dry_run=False)
            if not deploy_ok:
                print("❌ 部署步驟失敗！", file=sys.stderr)
                return 1

    print("\n" + "=" * 60)
    print("🎉 PCRD Story Map 管線 (Pipeline v1) 執行完畢！所有核心檢查均已通過。")
    print("=" * 60)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="PCRD Story Map 一鍵自動化更新管線 (Pipeline v1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用範例:
  python update_story_map.py --dry-run   # 零副作用模擬運行 (不下載、不寫入檔案、不提交 Git)
  python update_story_map.py             # 本地增量同步、打包與全量驗證 (預設不發布)
  python update_story_map.py --deploy    # 本地更新、全量驗證通過後自動推送至 GitHub Pages
"""
    )
    parser.add_argument("--dry-run", action="store_true", help="模擬運行（零副作用）：不下載、不寫入檔案、不提交 Git")
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
