#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Update Orchestrator (統一增量更新協調器)
負責協調完整的 CDN 增量同步、決定性打包、全量驗證與發布。

Story Map Update Pipeline v1:
  1. Freshness Evaluation & Gate (結構化判定、防滯後信任邊界、離線降級支援、生產發布新鮮度防禦門禁)
  2. Story Coverage Guard + Required Story Auto Sync (缺失核心劇本自動以官方 CDN snapshot 補齊；dry-run 僅驗證可抓取性)
  3. DB sync (TruthVersion 遠端探測與 So-net 官方 CDN Master DB 原生解密/正規化；未證實新鮮度前不虛假推進 version_history)
  4. Asset Completeness Gate (Event Top / Story Thumbnail 自動補齊；Movie 新缺口阻斷)
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
from pipeline.deploy import run_deploy, _get_internal_deploy_authorization
from pipeline.assets import analyze_asset_completeness
from pipeline.story_sync import ensure_required_story_coverage
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
    探測上游新鮮度、評估劇本覆蓋現況，並自動補齊缺失的核心必備劇本。
    :return: (sync_ok, freshness_result, coverage_result)
    """
    print("\n[步驟 1/4] 探測 So-net CDN 與執行增量資料同步 (Pipeline v1 Scope)...")
    
    try:
        from pipeline.fetch import (
            probe_truth_version,
            update_db,
        )
    except ImportError as e:
        print(f"❌ [ERROR] 無法載入 fetch 模組: {e}", file=sys.stderr)
        freshness_dummy = evaluate_freshness(None, None, False)
        coverage_dummy = analyze_coverage()
        return False, freshness_dummy, coverage_dummy

    # 1. 探測遠端 TruthVersion (ACTIVE_TRUTH_VERSION 當前由 remote_wthee_api 探測，待 Phase F2B 替換；Master DB 則由 So-net 官方 CDN 原生解密獲取)
    remote_tv = None
    try:
        probe = probe_truth_version()
        if probe.confirmed_remote:
            remote_tv = probe.version
            print(f"  [TruthVersion] 遠端版本探測: {remote_tv} (source={probe.source})")
        else:
            print(f"  [WARN] 遠端 TruthVersion 未取得 (source={probe.source}): {probe.error or 'unknown error'}")
    except Exception as e:
        print(f"  [WARN] 無法連接遠端探測版號 (離線或逾時): {e}")

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
            print(f"  [DRY-RUN] 預計執行: 從 So-net 官方 CDN 獲取並正規化 TruthVersion {remote_tv} 之 Master DB (So-net Official Master DB)")
        else:
            if not remote_tv:
                print("❌ [ERROR] 缺少有效的遠端 TruthVersion，無法從 So-net 官方 CDN 獲取資料庫！", file=sys.stderr)
                freshness = FreshnessResult(
                    status=FreshnessStatus.UPDATE_FAILED,
                    remote_version=remote_tv,
                    local_version=local_tv,
                    confirmed=False,
                    update_required=False,
                    degraded=True,
                    message="缺少有效遠端 TruthVersion"
                )
                return False, freshness, analyze_coverage()
            print(f"  [Sync] 正在從 So-net 官方 CDN 獲取並解密 TruthVersion {remote_tv} 之 Master DB...")
            try:
                update_result = update_db(
                    truth_version=remote_tv,
                    output="tools/db_update_report.json"
                )
                if not isinstance(update_result, dict) or update_result.get("status") != "ok":
                    detail = (update_result.get("error") if isinstance(update_result, dict) else "fetcher returned no success result")
                    raise RuntimeError(f"So-net Master DB 獲取/正規化失敗: {detail}")
                # 官方 CDN 資料庫下載與正規化完成：與指定 TruthVersion 決定性綁定
                freshness = FreshnessResult(
                    status=FreshnessStatus.UPDATED_SUCCESSFULLY,
                    remote_version=remote_tv,
                    local_version=local_tv,
                    confirmed=True,
                    update_required=False,
                    degraded=False,
                    message=(
                        f"已成功從 So-net 官方 CDN 獲取並正規化 Master DB，保證與指定 TruthVersion ({remote_tv}) 完全對齊 "
                        "(Official CDN Sourced & Version-Bound)"
                    )
                )
                print(f"  [Freshness] 狀態更新: {freshness.status} (Confirmed: {freshness.confirmed}) — {freshness.message}")
            except Exception as e:
                print(f"❌ [ERROR] 獲取/正規化 So-net 資料庫失敗: {e}", file=sys.stderr)
                freshness = FreshnessResult(
                    status=FreshnessStatus.UPDATE_FAILED,
                    remote_version=remote_tv,
                    local_version=local_tv,
                    confirmed=False,
                    update_required=False,
                    degraded=True,
                    message=f"獲取/正規化 So-net 資料庫失敗: {e}"
                )
                return False, freshness, analyze_coverage()
    else:
        if freshness.status == FreshnessStatus.REMOTE_BEHIND_LOCAL:
            print(f"  [Sync] 線上 CDN 版本 ({remote_tv}) 落後於本地記錄 ({local_tv})，安全跳過資料庫下載。")
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

    # 5. 核心必備劇本缺失：自動接回官方 CDN Story Fetch primitive。
    if coverage.missing_required_count > 0:
        print(f"  [StorySync] 發現 {coverage.missing_required_count} 話核心必備劇本缺失。")
        print(f"  [StorySync] 缺失 Sample: {coverage.missing_required_ids[:10]}")
        sync_result, effective_coverage = ensure_required_story_coverage(
            coverage,
            truth_version=remote_tv,
            dry_run=dry_run,
        )

        if not sync_result.success:
            print(f"❌ [ERROR] Required Story Auto Sync 失敗: {sync_result.message}", file=sys.stderr)
            if sync_result.unavailable_ids:
                print(f"  CDN manifest 尚無對應話數: {sync_result.unavailable_ids[:20]}", file=sys.stderr)
            if sync_result.failed_ids:
                print(f"  同步失敗話數: {sync_result.failed_ids[:20]}", file=sys.stderr)
            return False, freshness, effective_coverage

        if dry_run:
            print(
                f"  [DRY-RUN][StorySync] {len(sync_result.fetchable_ids)} 話均存在於 "
                f"TruthVersion {remote_tv} 官方 story manifest；正式執行時將自動補齊。"
            )
        else:
            coverage = effective_coverage
            print(f"  [StorySync] 已自動補齊 {len(sync_result.synced_ids)} 話核心必備劇本並重新通過 Coverage Guard。")

    if coverage.unknown_expected_count > 0 or coverage.missing_unknown_count > 0:
        print(f"⚠️  [WARN] 發現未歸類之預期話數 (Unknown Expected: {coverage.unknown_expected_count} 話, 缺失: {coverage.missing_unknown_count} 話)")
        if coverage.missing_unknown_ids:
            print(f"  未歸類缺失話數 Sample: {coverage.missing_unknown_ids[:10]}")

    if coverage.missing_optional_count > 0:
        print(f"  [WARN] 尚有 {coverage.missing_optional_count} 話可選歷史劇本未下載 (不影響核心功能)")

    if dry_run and coverage.missing_required_count > 0:
        print("  [Sync] DRY-RUN：核心必備劇本目前仍缺，但已確認正式執行時可由官方 CDN 自動補齊。")
    else:
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

    # 2. 執行資產完整性門禁 (Asset Completeness Gate v1)
    print("\n[步驟 2/4] 執行資產完整性門禁 (Asset Completeness Gate v1)...")
    try:
        asset_res = analyze_asset_completeness(
            truth_version=freshness.remote_version,
            dry_run=dry_run
        )
        if not asset_res.success:
            print("❌ 資產完整性門禁未通過！阻止後續打包與發布。", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 資產完整性檢查過程發生異常: {e}", file=sys.stderr)
        return 1

    # 3. 封裝 Story Map 獨立發布包
    print("\n[步驟 3/4] 執行 Story Map 決定性打包與 Cache-Busting...")
    try:
        bundle_ok = bundle_story_map(dry_run=dry_run)
        if not bundle_ok:
            print("❌ 打包步驟失敗！", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 打包過程發生異常: {e}", file=sys.stderr)
        return 1

    # 4. 執行全量一致性驗證門禁
    print("\n[步驟 4/4] 執行全量資料完整性驗證門禁...")
    try:
        validate_ok = validate_story_map(
            check_dist=(not dry_run),
            allow_metadata_bootstrap_incomplete=(not (auto_deploy and not dry_run))
        )
        if not validate_ok:
            print("❌ 驗證門禁未通過！", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"❌ 驗證過程發生異常: {e}", file=sys.stderr)
        return 1

    # 4.1 晉升 TruthVersion 狀態 (僅在全流程驗證通過、非 dry-run 且狀態已確認時執行)
    if not dry_run and freshness.confirmed and freshness.remote_version:
        if freshness.remote_version != freshness.local_version:
            print(f"\n[Version State Promotion] 全流程驗證通過，正在推進本地 TruthVersion 狀態: {freshness.remote_version}...")
            promoted = save_truth_version_state(freshness.remote_version)
            if not promoted:
                print("❌ [ERROR] 版本狀態寫入失敗！阻斷流程。", file=sys.stderr)
                return 1

    # 5. 晉升 Movie Reference Baseline (只有全流程驗證通過、非 dry-run 且有新 reference 時執行)
    if not dry_run and asset_res.movie_coverage.new_references_count > 0:
        print("\n[Baseline Promotion] 正在更新動畫參照基準清單 (movie_reference_manifest.json)...")
        try:
            from pipeline.assets import scan_movie_references, promote_movie_baseline
            current_refs, _ = scan_movie_references()
            promoted = promote_movie_baseline(current_refs)
            if promoted:
                print(f"  [Baseline] 已成功晉升並更新動畫基準清單 (新增 {asset_res.movie_coverage.new_references_count} 部動畫參照)")
            else:
                print("❌ [ERROR] 動畫基準清單 (movie_reference_manifest.json) 寫入失敗！阻斷發布流程。", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"❌ [ERROR] 晉升動畫基準清單時發生異常: {e}", file=sys.stderr)
            return 1

    # 6. 可選部署 (只有明確指定 auto_deploy 且非 dry_run 時執行)
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
            deploy_ok = run_deploy(
                message=message,
                dry_run=False,
                authorization=_get_internal_deploy_authorization(),
            )
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
  python update_story_map.py --dry-run                        # 零副作用模擬運行 (不寫入、不下載 Story/資產檔、不提交 Git)
  python update_story_map.py                                  # 自動補齊 required stories / assets、打包與全量驗證 (預設不發布)
  python update_story_map.py --coverage                       # 僅輸出劇本覆蓋率報告 (唯讀零副作用)
  python update_story_map.py --deploy                         # 完整更新、新鮮度與全量驗證通過後自動推送
  python update_story_map.py --deploy --allow-unconfirmed-freshness  # 緊急模式：覆蓋新鮮度門禁進行發布
"""
    )
    parser.add_argument("--dry-run", action="store_true", help="模擬運行（零副作用）：不寫入、不下載 Story/資產檔、不提交 Git")
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
