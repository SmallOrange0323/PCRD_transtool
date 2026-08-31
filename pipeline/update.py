#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Update Orchestrator (統一增量更新協調器)
負責協調完整的 CDN 增量同步、決定性打包、全量驗證與發布。

Story Map Update Pipeline v1 (Phase C2 Minimal Implementation):
  1. Freshness Evaluation & Gate (結構化判定、鏡像防滯後信任邊界、離線降級支援、生產發布新鮮度防禦門禁)
  2. Read-Only Story Coverage Guard (唯讀分析必備與可選話數覆蓋，來源完整性檢驗與未歸類話數防禦，不自動抓取)
  3. DB sync (TruthVersion 探測與 SQLite 鏡像下載；未證實新鮮度前不虛假推進 version_history)
  4. Tracked character verification (透過 Coverage Guard 確認 100% 就緒，缺失需手動補齊)
  5. Deterministic bundle & Cache-Busting (SHA-256 內容比對、體積控制)
  6. Single-source validation gate (9000+ 篇劇本與 dist 集合全量深度自檢)
  7. Safe GitHub Pages deploy (只推送 dist_story_map 至 gh-pages)

Exit Codes:
  0 = success
  1 = runtime / validation / freshness / coverage gate failure
  2 = invalid configuration / missing required dependency
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.bundle import bundle_story_map
from pipeline.validate import validate_story_map
from pipeline.deploy import run_deploy
from pipeline.coverage import (
    evaluate_freshness,
    analyze_coverage,
    FreshnessResult,
    CoverageResult,
    FreshnessStatus,
    CoverageAnalysisStatus
)

def save_truth_version_state(new_version: str) -> bool:
    """
    以原子替換方式更新版本狀態 (僅在版號經證實時調用)
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

def check_and_sync_upstream(dry_run: bool = False) -> Tuple[bool, FreshnessResult, CoverageResult]:
    """
    探測上游新鮮度、評估劇本覆蓋現況，並執行必要之資料庫同步。
    :return: (sync_ok, freshness_result, coverage_result)
    """
    print("\n[步驟 1/3] 探測 So-net CDN 與執行增量資料同步 (Pipeline v1 Scope)...")
    
    try:
        from pipeline.fetch import (
            get_truth_version,
            update_db,
            get_story_ids_for_unit
        )
    except ImportError as e:
        print(f"❌ [ERROR] 無法載入 fetch 模組: {e}", file=sys.stderr)
        freshness_dummy = evaluate_freshness(None, None, False)
        coverage_dummy = analyze_coverage()
        return False, freshness_dummy, coverage_dummy

    # 1. 探測 CDN 版號 (So-net 上游觀察)
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

    db_file_exists = (DASHBOARD_DIR / "redive_tw.db").exists()
    freshness = evaluate_freshness(remote_tv, local_tv, db_file_exists)
    print(f"  [Freshness] 狀態: {freshness.status} (Confirmed: {freshness.confirmed}) — {freshness.message}")

    if freshness.status == FreshnessStatus.LOCAL_STATE_MISSING:
        print("❌ [ERROR] 本地資料庫缺失且無法連接 CDN，管線終止！", file=sys.stderr)
        return False, freshness, analyze_coverage()

    # 3. 執行 DB 下載與同步 (若有新版本或本地 DB 缺失)
    if freshness.update_required:
        print(f"  [Sync] 檢測到 CDN 有新版本或本地 DB 缺失 (線上: {remote_tv}, 本地: {local_tv})")
        if dry_run:
            print("  [DRY-RUN] 預計執行: 從鏡像下載最新台版資料庫 redive_tw.db")
        else:
            print("  [Sync] 正在從鏡像下載並解密最新台版 SQLite 資料庫...")
            class MockArgs:
                force = False
                source = "sonet"
                output = "tools/db_update_report.json"
            try:
                update_db(MockArgs())
                # 鏡像資料庫下載完成：因第三方鏡像缺乏直接 So-net TruthVersion 對齊證明，誠實標記為未確認
                freshness = FreshnessResult(
                    status=FreshnessStatus.UPDATE_DOWNLOADED_UNCONFIRMED,
                    remote_version=remote_tv,
                    local_version=local_tv,
                    confirmed=False,
                    update_required=False,
                    degraded=True,
                    message=(
                        f"已成功從鏡像下載資料庫，但鏡像內容無法直接驗證與 So-net TruthVersion ({remote_tv}) 之對齊性 "
                        "(Mirror Freshness Unproven)；為防範 mirror-lag 風險，未虛假推進 version_history"
                    )
                )
                print(f"  [Freshness] 狀態更新: {freshness.status} (Confirmed: {freshness.confirmed}) — {freshness.message}")
            except Exception as e:
                print(f"❌ [ERROR] 下載資料庫失敗: {e}", file=sys.stderr)
                freshness = FreshnessResult(
                    status=FreshnessStatus.UPDATE_FAILED,
                    remote_version=remote_tv,
                    local_version=local_tv,
                    confirmed=False,
                    update_required=False,
                    degraded=True,
                    message=f"下載資料庫失敗: {e}"
                )
                return False, freshness, analyze_coverage()
    else:
        print("  [Sync] 本地資料庫與 CDN 版號一致，無需重新下載資料庫。")

    # 4. 執行劇本覆蓋率與來源健康度分析 (Coverage Guard)
    coverage = analyze_coverage()
    m = coverage.metrics
    print(f"  [Coverage] 分析狀態: {coverage.analysis_status} | 必備劇本: {coverage.required_total_count} 話 (缺失: {coverage.missing_required_count}) | 可選劇本: {coverage.optional_total_count} 話 (缺失: {coverage.missing_optional_count})")

    if coverage.analysis_status == CoverageAnalysisStatus.INVALID:
        print(f"❌ [ERROR] 覆蓋率分析失敗 (Coverage Analysis INVALID)，權威來源載入異常！", file=sys.stderr)
        for err in coverage.analysis_errors:
            print(f"    - {err}", file=sys.stderr)
        return False, freshness, coverage
    elif coverage.analysis_status == CoverageAnalysisStatus.DEGRADED:
        print(f"⚠️  [WARN] 覆蓋率分析降級 (Coverage Analysis DEGRADED)，部分來源無法完整解析：")
        for err in coverage.analysis_errors:
            print(f"    - {err}")

    if coverage.missing_required_count > 0:
        print(f"❌ [ERROR] 發現 {coverage.missing_required_count} 話核心必備劇本缺失，管線安全中斷！", file=sys.stderr)
        sample_missing = coverage.missing_required_ids[:10]
        print(f"  缺失必備話數 Sample: {sample_missing}", file=sys.stderr)
        print(f"  👉 請使用單話抓取工具補齊缺失劇本: python tools/pcrd_fetch.py fetch-story --story-id <id>", file=sys.stderr)
        return False, freshness, coverage

    if coverage.unknown_expected_count > 0 or coverage.missing_unknown_count > 0:
        print(f"⚠️  [WARN] 發現未歸類之預期話數 (Unknown Expected: {coverage.unknown_expected_count} 話, 缺失: {coverage.missing_unknown_count} 話)")
        if coverage.missing_unknown_ids:
            print(f"  未歸類缺失話數 Sample: {coverage.missing_unknown_ids[:10]}")

    if coverage.missing_optional_count > 0:
        print(f"  [WARN] 尚有 {coverage.missing_optional_count} 話可選歷史劇本未下載 (不影響核心功能)")

    print("  [Sync] 所有核心必備劇本與追蹤角色對白均已就緒。")
    return True, freshness, coverage

def print_coverage_report():
    """唯讀輸出完整劇本覆蓋率報告 (零寫入副作用)"""
    print("=" * 60)
    print("📊 PCRD Story Map 劇本覆蓋率分析 (Coverage Report)")
    print("=" * 60)
    cov = analyze_coverage()
    m = cov.metrics
    ol = cov.overlaps
    ps = cov.policy_status
    sh = cov.source_status

    print(f"覆蓋率分析狀態 (Analysis Integrity): {cov.analysis_status}")
    if cov.analysis_errors:
        print(f"異常警告訊息:")
        for err in cov.analysis_errors:
            print(f"  - {err}")
    print("-" * 60)
    print("權威來源健康狀態 (Source Health):")
    for src, st in sh.items():
        print(f"  - {src:20s}: {st}")
    print("-" * 60)
    print(f"本地數字劇本總數 (Local Present):   {cov.local_present_count} 篇")
    print(f"資料庫 story_detail 總數:           {m.get('db_story_detail_total', 0)} 筆")
    print(f"追蹤角色必備話數:                   {m.get('tracked_character_required_count', 0)} 話 ({m.get('tracked_units_count', 0)} 個追蹤角色)")
    print(f"主線必備話數:                       {m.get('main_required_count', 0)} 話")
    print(f"公會必備話數:                       {m.get('guild_required_count', 0)} 話")
    print(f"露娜塔/系統必備話數:                {m.get('tower_system_required_count', 0)} 話")
    print(f"第 3 部分支補充話數:                {m.get('branch_expected_count', 0)} 話")
    print(f"新形式活動話數:                     {m.get('extra_event_expected_count', 0)} 話")
    print("-" * 60)
    print(f"產品必備劇本總數 (Required Union):  {cov.required_total_count} 話 (缺失: {cov.missing_required_count}) -> 政策狀態: {ps.get('required_policy_status')}")
    print(f"可選歷史劇本總數 (Optional):        {cov.optional_total_count} 話 (缺失: {cov.missing_optional_count}) -> 政策狀態: {ps.get('optional_policy_status')}")
    print(f"未知分類預期劇本 (Unknown):         {cov.unknown_expected_count} 話 (缺失: {cov.missing_unknown_count})")
    print("-" * 60)
    print(f"集合重疊分析: Tracked∩DB={ol.get('tracked_vs_story_detail', 0)}, Branch∩Main={ol.get('branch_vs_main', 0)}, Extra∩DB={ol.get('extra_vs_story_detail', 0)}")
    if cov.missing_required_count > 0:
        print(f"❌ 必備劇本缺失清單: {cov.missing_required_ids}")
    else:
        print("✅ 核心必備劇本 100% 就緒！")
    print("=" * 60)

def run_pipeline_update(
    dry_run: bool = False,
    auto_deploy: bool = False,
    message: str = None,
    allow_unconfirmed_freshness: bool = False,
    check_coverage_only: bool = False
) -> int:
    """
    執行一鍵更新管線 (Pipeline v1)
    :return: exit code (0=成功, 1=執行或驗證失敗, 2=環境或依賴缺失)
    """
    if check_coverage_only:
        print_coverage_report()
        return 0

    print("=" * 60)
    print("🚀 PCRD 劇情地圖 (Story Map) 自動化增量更新管線 (Pipeline v1) 啟動")
    print(f"模式: {'[DRY-RUN 零副作用模擬]' if dry_run else ('[增量同步 + 決定性封裝 + 發布]' if auto_deploy else '[增量同步 + 決定性封裝 + 驗證]')}")
    print("=" * 60)

    # 1. 執行增量同步、新鮮度與覆蓋率完整性探測
    sync_ok, freshness, coverage = check_and_sync_upstream(dry_run=dry_run)
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
            # 檢查新鮮度防禦門禁 (Freshness Gate: 包括未探測與鏡像未證實之狀態)
            if not freshness.confirmed:
                if not allow_unconfirmed_freshness:
                    print("\n" + "!" * 60, file=sys.stderr)
                    print(f"❌ [ERROR] 上游新鮮度未確認 (Freshness Status: {freshness.status})！", file=sys.stderr)
                    print(f"  原因: {freshness.message}", file=sys.stderr)
                    print("🛡️  安全防禦門禁已阻斷自動生產發布，避免將過期或鏡像滯後版本推送至線上！", file=sys.stderr)
                    print("👉 若經人工作業已確認資料庫完整無誤，請帶入明確覆蓋參數: --allow-unconfirmed-freshness", file=sys.stderr)
                    print("!" * 60, file=sys.stderr)
                    return 1
                else:
                    print("\n⚠️ [WARN] 偵測到 --allow-unconfirmed-freshness，手動覆蓋新鮮度門禁，繼續執行發布檢查。")

            # 檢查劇本覆蓋率完整性門禁 (Coverage Integrity & Unknown Gate)
            if coverage.analysis_status != CoverageAnalysisStatus.VALID:
                print("\n" + "!" * 60, file=sys.stderr)
                print(f"❌ [ERROR] 劇本覆蓋率分析不具完整性 (Coverage Status: {coverage.analysis_status})！", file=sys.stderr)
                print("🛡️  權威來源載入異常或缺失，嚴禁發布未經驗證之產物！(--allow-unconfirmed-freshness 無法覆蓋此門禁)", file=sys.stderr)
                print("!" * 60, file=sys.stderr)
                return 1

            if coverage.unknown_expected_count > 0 or coverage.missing_unknown_count > 0:
                print("\n" + "!" * 60, file=sys.stderr)
                print(f"❌ [ERROR] 發現未歸類之預期話數 (Unknown Expected: {coverage.unknown_expected_count}, Missing: {coverage.missing_unknown_count})！", file=sys.stderr)
                print("🛡️  覆蓋率政策未完全收斂 (Policy Status 非 DEFINED)，生產發布已被安全阻斷！", file=sys.stderr)
                print("!" * 60, file=sys.stderr)
                return 1

            if coverage.missing_required_count > 0:
                print(f"❌ [ERROR] 仍有 {coverage.missing_required_count} 話核心必備劇本缺失，嚴禁發布！", file=sys.stderr)
                return 1

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
  python update_story_map.py --dry-run                        # 零副作用模擬運行 (不下載、不寫入檔案、不提交 Git)
  python update_story_map.py                                  # 本地增量同步、打包與全量驗證 (預設不發布)
  python update_story_map.py --coverage                       # 僅輸出劇本覆蓋率報告 (唯讀零副作用)
  python update_story_map.py --deploy                         # 本地更新、新鮮度與全量驗證通過後自動推送
  python update_story_map.py --deploy --allow-unconfirmed-freshness  # 緊急模式：覆蓋新鮮度門禁進行發布
"""
    )
    parser.add_argument("--dry-run", action="store_true", help="模擬運行（零副作用）：不下載、不寫入檔案、不提交 Git")
    parser.add_argument("--coverage", action="store_true", help="僅輸出唯讀劇本覆蓋率報告 (零副作用)")
    parser.add_argument("--deploy", action="store_true", help="驗證通過後自動推送到 GitHub Pages")
    parser.add_argument("--allow-unconfirmed-freshness", "--allow-unconfirmed", action="store_true", help="允許在新鮮度未確認時強制執行自動部署 (緊急應急覆蓋)")
    parser.add_argument("-m", "--message", type=str, default=None, help="發布時的 Git Commit訊息")
    args = parser.parse_args()

    exit_code = run_pipeline_update(
        dry_run=args.dry_run,
        auto_deploy=args.deploy,
        message=args.message,
        allow_unconfirmed_freshness=args.allow_unconfirmed_freshness,
        check_coverage_only=args.coverage
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
