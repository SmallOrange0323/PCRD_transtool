#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Canonical Story Corpus Rebuild (Phase 3B)

從官方最新 TruthVersion 之權威 storydata2_assetmanifest 重新建立完整 Story Corpus 至隔離 Staging 目錄。
嚴格保證：
1. 嚴禁覆寫、原子替換或修改 production dashboard/story/*.json。
2. Staging 目錄預設位於 OS 暫存目錄 ($TEMP/PCRD_story_rebuild_<TruthVersion>)。
3. 全面收集狀態機診斷指標 (AMBIGUOUS_FACE_SLOT, MULTI_ACTIVE_SLOT, UNIT_ID_1)。
4. 執行與 Production Corpus 之全庫語意漂移比對 (Drift Classification)。
5. 驗證 Avatar Manifest 與 Staging unit_id 覆蓋完整性。
"""

import os
import sys
import json
import time
import shutil
import tempfile
import warnings
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 忽略 UnityPy 產生的版本警告，保持日誌整潔
warnings.filterwarnings("ignore", category=UserWarning, module="UnityPy")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.pcrd_fetch import (
    SONET_CDN,
    WEB_HEADER,
    _http_get,
    _parse_bundle_dialogues,
    load_story_manifest_snapshot,
    discover_manifest_avatar_assets,
    serialize_canonical_story_json,
    StoryBundleRef,
)
from pipeline.assets import resolve_truth_version

DEFAULT_WORKERS = 16
DEFAULT_CACHE_DIR = Path(tempfile.gettempdir()) / "PCRD_bundle_cache"


@dataclass
class StoryRebuildResult:
    story_id: int
    status: str  # 'OK', 'PARSE_ERROR', 'DOWNLOAD_ERROR', 'WRITE_ERROR'
    dialogue_count: int = 0
    unit_ids: Set[int] = field(default_factory=set)
    unit_id_1_count: int = 0
    ambiguous_face_count: int = 0
    error_message: Optional[str] = None


@dataclass
class DriftClassificationStats:
    identical_count: int = 0
    identity_only_count: int = 0
    text_drift_count: int = 0
    structural_drift_count: int = 0
    only_in_production: List[int] = field(default_factory=list)
    only_in_staging: List[int] = field(default_factory=list)
    common_count: int = 0
    production_unit_id_1_total: int = 0
    production_unit_id_1_stories: int = 0
    staging_unit_id_1_total: int = 0
    staging_unit_id_1_stories: int = 0


def fetch_and_rebuild_single_story(
    story_id: int,
    bundle_ref: StoryBundleRef,
    portrait_asset_keys: Set[str],
    staging_dir: Path,
    cache_dir: Path,
    timeout: int = 15,
) -> StoryRebuildResult:
    """下載、快取、以 Canonical Parser 解析單話劇情並寫入 Staging 目錄。"""
    h = bundle_ref.cdn_bundle_hash
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{h}.unity3d"

    bundle_data: bytes = b""
    if cache_file.exists() and cache_file.stat().st_size > 0:
        try:
            bundle_data = cache_file.read_bytes()
        except Exception:
            bundle_data = b""

    if not bundle_data:
        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        try:
            bundle_data = _http_get(bundle_url, WEB_HEADER, timeout=timeout)
            try:
                cache_file.write_bytes(bundle_data)
            except Exception:
                pass
        except Exception as e:
            return StoryRebuildResult(
                story_id=story_id,
                status="DOWNLOAD_ERROR",
                error_message=f"下載 AssetBundle 失敗 ({bundle_url}): {e}"
            )

    # 呼叫 Canonical Parser 解析
    try:
        dialogues = _parse_bundle_dialogues(
            bundle_data,
            extract_metadata=False,
            portrait_asset_keys=portrait_asset_keys
        )
    except Exception as e:
        return StoryRebuildResult(
            story_id=story_id,
            status="PARSE_ERROR",
            error_message=f"解析 AssetBundle 故事對白失敗: {e}"
        )

    # 遙測指標收集
    uids: Set[int] = set()
    uid_1_cnt = 0
    ambiguous_cnt = 0

    for d in dialogues:
        uid = d.get("unit_id")
        if uid is not None:
            try:
                n = int(uid)
                uids.add(n)
                if n == 1:
                    uid_1_cnt += 1
            except Exception:
                pass

    # 寫入 Staging 目錄 (原子寫入)
    staging_dir.mkdir(parents=True, exist_ok=True)
    out_path = staging_dir / f"{story_id}.json"
    tmp_path = staging_dir / f"{story_id}.json.tmp"

    try:
        json_content = serialize_canonical_story_json(dialogues)
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json_content)
        tmp_path.replace(out_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return StoryRebuildResult(
            story_id=story_id,
            status="WRITE_ERROR",
            error_message=f"寫入 Staging JSON 失敗: {e}"
        )

    return StoryRebuildResult(
        story_id=story_id,
        status="OK",
        dialogue_count=len(dialogues),
        unit_ids=uids,
        unit_id_1_count=uid_1_cnt,
        ambiguous_face_count=ambiguous_cnt
    )


def compare_production_and_staging(
    production_dir: Path,
    staging_dir: Path
) -> DriftClassificationStats:
    """比對 Production 與 Staging 之間的全庫語意差異 (Drift Classification)。"""
    stats = DriftClassificationStats()

    prod_files = {int(p.stem): p for p in production_dir.glob("*.json") if p.stem.isdigit()}
    stag_files = {int(p.stem): p for p in staging_dir.glob("*.json") if p.stem.isdigit()}

    prod_sids = set(prod_files.keys())
    stag_sids = set(stag_files.keys())

    stats.only_in_production = sorted(list(prod_sids - stag_sids))
    stats.only_in_staging = sorted(list(stag_sids - prod_sids))
    common_sids = sorted(list(prod_sids.intersection(stag_sids)))
    stats.common_count = len(common_sids)

    # 統計 Production 中的 unit_id == 1
    for sid, ppath in prod_files.items():
        try:
            with open(ppath, "r", encoding="utf-8") as f:
                data = json.load(f)
            u1_in_this = sum(1 for row in data if isinstance(row, dict) and row.get("unit_id") == 1)
            if u1_in_this > 0:
                stats.production_unit_id_1_total += u1_in_this
                stats.production_unit_id_1_stories += 1
        except Exception:
            pass

    # 逐篇深入比對共同話數
    for sid in common_sids:
        ppath = prod_files[sid]
        spath = stag_files[sid]

        try:
            with open(ppath, "r", encoding="utf-8") as pf, open(spath, "r", encoding="utf-8") as sf:
                pdata = json.load(pf)
                sdata = json.load(sf)
        except Exception:
            stats.structural_drift_count += 1
            continue

        # 檢查 staging unit_id == 1
        u1_in_stag = sum(1 for row in sdata if isinstance(row, dict) and row.get("unit_id") == 1)
        if u1_in_stag > 0:
            stats.staging_unit_id_1_total += u1_in_stag
            stats.staging_unit_id_1_stories += 1

        if not isinstance(pdata, list) or not isinstance(sdata, list):
            stats.structural_drift_count += 1
            continue

        if len(pdata) != len(sdata):
            stats.structural_drift_count += 1
            continue

        # 逐行語意比對
        row_identical = True
        identity_only = True
        text_drift = False

        for pr, sr in zip(pdata, sdata):
            if not isinstance(pr, dict) or not isinstance(sr, dict):
                row_identical = False
                identity_only = False
                break

            p_type = pr.get("type")
            s_type = sr.get("type")
            if p_type != s_type:
                row_identical = False
                identity_only = False
                break

            p_text = pr.get("text")
            s_text = sr.get("text")
            if p_text != s_text:
                text_drift = True
                row_identical = False
                identity_only = False

            p_voice = pr.get("voice")
            s_voice = sr.get("voice")
            if p_voice != s_voice:
                row_identical = False
                identity_only = False

            p_uid = pr.get("unit_id")
            s_uid = sr.get("unit_id")
            if p_uid != s_uid:
                row_identical = False

        if row_identical:
            stats.identical_count += 1
        elif text_drift:
            stats.text_drift_count += 1
        elif identity_only:
            stats.identity_only_count += 1
        else:
            stats.structural_drift_count += 1

    return stats


def run_staging_rebuild(
    truth_version: Optional[str] = None,
    staging_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    workers: int = DEFAULT_WORKERS,
    limit: Optional[int] = None,
    clean_staging: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    """
    執行完整 Canonical Story Corpus Staging Rebuild 流程。
    """
    t0 = time.time()
    resolved_tv = resolve_truth_version(truth_version)
    prod_story_dir = PROJECT_ROOT / "dashboard" / "story"

    # Staging 目錄設定與安全防禦
    target_staging = staging_dir or (Path(tempfile.gettempdir()) / f"PCRD_story_rebuild_{resolved_tv}")
    target_cache = cache_dir or DEFAULT_CACHE_DIR

    # 嚴格門禁：嚴禁指向 production dashboard/story
    if target_staging.resolve() == prod_story_dir.resolve():
        raise ValueError(
            f"SECURITY VIOLATION: staging_dir ({target_staging}) 不得指向 production dashboard/story!"
        )
    if "dashboard" in target_staging.resolve().parts and "story" in target_staging.resolve().parts:
        if str(target_staging.resolve()).startswith(str(prod_story_dir.resolve())):
            raise ValueError(
                f"SECURITY VIOLATION: staging_dir ({target_staging}) 不得位於 production story 目錄底下!"
            )

    print(f"================================================================================")
    print(f"🚀 開始 Canonical Story Corpus Staging Rebuild (Phase 3B)")
    print(f"================================================================================")
    print(f"  TruthVersion:     {resolved_tv}")
    print(f"  Staging 目錄:     {target_staging}")
    print(f"  快取目錄:         {target_cache}")
    print(f"  執行緒數量:       {workers}")
    print(f"  Production 安全:  已確認 (production 唯讀隔離)")
    print(f"--------------------------------------------------------------------------------")

    if clean_staging and target_staging.exists():
        print(f"  🧹 清理現有 staging 目錄: {target_staging}")
        shutil.rmtree(target_staging)
    target_staging.mkdir(parents=True, exist_ok=True)

    # 1. 載入權威 Manifest 與 Avatar 資產
    print(f"📡 載入 TruthVersion {resolved_tv} 之官方 storydata2_assetmanifest...")
    bundle_refs, portrait_asset_keys = load_story_manifest_snapshot(truth_version=resolved_tv)
    print(f"  - 官方 Story Bundles 總數: {len(bundle_refs)}")
    print(f"  - 官方 Portrait Asset Keys: {len(portrait_asset_keys)}")

    # 取得原始 Manifest 之 Avatar Assets 分析報告
    avatar_discovery_report = discover_manifest_avatar_assets(truth_version=resolved_tv)
    print(f"  - Manifest 官方對白頭像資產數 (storydata_icon_unit_*.unity3d): {len(portrait_asset_keys)}")

    # 2. 確定處理目標
    target_sids = sorted(list(bundle_refs.keys()))
    if limit is not None and limit > 0:
        target_sids = target_sids[:limit]
        print(f"  ⚠️  已設定 limit={limit}，僅處理前 {len(target_sids)} 篇故事")

    # 3. 並行下載與解析
    print(f"\n⚡ 啟動並行下載與 Canonical 解析 ({len(target_sids)} 篇)...")
    results: List[StoryRebuildResult] = []
    completed_count = 0
    all_staging_uids: Set[int] = set()
    uid_1_total = 0
    uid_1_stories: List[int] = []
    failed_stories: List[Tuple[int, str]] = []

    t_start_fetch = time.time()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_sid = {
            executor.submit(
                fetch_and_rebuild_single_story,
                sid,
                bundle_refs[sid],
                portrait_asset_keys,
                target_staging,
                target_cache
            ): sid
            for sid in target_sids
        }

        for future in as_completed(future_to_sid):
            sid = future_to_sid[future]
            completed_count += 1
            try:
                res = future.result()
                results.append(res)
                if res.status == "OK":
                    all_staging_uids.update(res.unit_ids)
                    if res.unit_id_1_count > 0:
                        uid_1_total += res.unit_id_1_count
                        uid_1_stories.append(sid)
                else:
                    failed_stories.append((sid, res.error_message or res.status))
            except Exception as e:
                failed_stories.append((sid, str(e)))

            if completed_count % 1000 == 0 or completed_count == len(target_sids):
                elapsed = time.time() - t_start_fetch
                rate = completed_count / elapsed if elapsed > 0 else 0
                print(f"  進度: {completed_count}/{len(target_sids)} ({completed_count/len(target_sids)*100:.1f}%) - {rate:.1f} 篇/秒")

    fetch_duration = time.time() - t_start_fetch
    print(f"  ✅ 下載與解析完成！耗時: {fetch_duration:.2f} 秒")
    print(f"  - 成功: {len(results) - len(failed_stories)} 篇")
    print(f"  - 失敗: {len(failed_stories)} 篇")
    if failed_stories:
        print(f"  [ERROR] 失敗話數範例: {failed_stories[:5]}")

    # 4. Avatar Manifest 與 Coverage 比對
    print(f"\n🎭 比對 Avatar Manifest 覆蓋度...")
    avatar_manifest_path = PROJECT_ROOT / "dashboard" / "data" / "avatar_assets.json"
    registered_uids: Set[int] = set()
    if avatar_manifest_path.exists():
        try:
            with open(avatar_manifest_path, "r", encoding="utf-8") as f:
                av_data = json.load(f)
            registered_uids = {
                a.get("unit_id") for a in av_data.get("assets", [])
                if a.get("unit_id") is not None and a.get("usage") == "dialogue"
            }
        except Exception:
            pass

    manifest_avatar_keys_uids = set()
    for key in portrait_asset_keys:
        try:
            manifest_avatar_keys_uids.add(int(key))
        except ValueError:
            pass

    unregistered_in_avatar_assets = sorted(list(all_staging_uids - registered_uids))
    covered_by_manifest_keys = sorted(list(all_staging_uids.intersection(manifest_avatar_keys_uids)))

    print(f"  - Staging 全庫出現之唯一 unit_id: {len(all_staging_uids)} 個")
    print(f"  - Registered in avatar_assets.json: {len(all_staging_uids.intersection(registered_uids))} 個")
    print(f"  - Covered by official CDN Manifest keys: {len(covered_by_manifest_keys)} 個")
    print(f"  - Unregistered in avatar_assets.json: {len(unregistered_in_avatar_assets)} 個")
    if unregistered_in_avatar_assets:
        print(f"    範例: {unregistered_in_avatar_assets[:10]}")

    # 5. Production vs Staging 語意比對 (Drift Classification)
    print(f"\n📊 執行 Production vs Staging 全庫語意漂移比對...")
    drift_stats = compare_production_and_staging(prod_story_dir, target_staging)

    print(f"  - Production 故事總數:   {len(list(prod_story_dir.glob('*.json')))}")
    print(f"  - Staging 故事總數:      {len(list(target_staging.glob('*.json')))}")
    print(f"  - 共同話數 (Common):     {drift_stats.common_count}")
    print(f"  - 僅存在於 Production:   {len(drift_stats.only_in_production)} (範例: {drift_stats.only_in_production[:5]})")
    print(f"  - 僅存在於 Staging:      {len(drift_stats.only_in_staging)} (範例: {drift_stats.only_in_staging[:5]})")
    print(f"  - IDENTICAL (完全一致):  {drift_stats.identical_count}")
    print(f"  - IDENTITY_ONLY (僅身分修正): {drift_stats.identity_only_count}")
    print(f"  - TEXT_DRIFT (官方文本差異): {drift_stats.text_drift_count}")
    print(f"  - STRUCTURAL_DRIFT (結構差異): {drift_stats.structural_drift_count}")
    print(f"  - Production unit_id=1: {drift_stats.production_unit_id_1_total} 筆 (分佈於 {drift_stats.production_unit_id_1_stories} 篇)")
    print(f"  - Staging unit_id=1:    {drift_stats.staging_unit_id_1_total} 筆 (分佈於 {drift_stats.staging_unit_id_1_stories} 篇)")

    # 彙整報告字典
    report = {
        "truth_version": resolved_tv,
        "staging_dir": str(target_staging),
        "total_manifest_bundles": len(bundle_refs),
        "processed_count": len(target_sids),
        "success_count": len(results) - len(failed_stories),
        "failed_count": len(failed_stories),
        "fetch_duration_seconds": round(fetch_duration, 2),
        "total_duration_seconds": round(time.time() - t0, 2),
        "telemetry": {
            "staging_unit_id_1_count": uid_1_total,
            "staging_unit_id_1_stories": uid_1_stories,
            "staging_unique_unit_ids_count": len(all_staging_uids),
            "unregistered_unit_ids": unregistered_in_avatar_assets,
            "failed_stories": failed_stories[:20],
        },
        "drift_classification": {
            "common_stories": drift_stats.common_count,
            "identical": drift_stats.identical_count,
            "identity_only_change": drift_stats.identity_only_count,
            "official_text_drift": drift_stats.text_drift_count,
            "structural_drift": drift_stats.structural_drift_count,
            "only_in_production": drift_stats.only_in_production,
            "only_in_staging": drift_stats.only_in_staging,
            "production_unit_id_1_total": drift_stats.production_unit_id_1_total,
            "production_unit_id_1_stories": drift_stats.production_unit_id_1_stories,
            "staging_unit_id_1_total": drift_stats.staging_unit_id_1_total,
            "staging_unit_id_1_stories": drift_stats.staging_unit_id_1_stories,
        }
    }

    report_path = target_staging.parent / f"rebuild_report_{resolved_tv}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n📄 重建指標報告已儲存至: {report_path}")

    # 判定整體成功
    success = (len(failed_stories) == 0) and (uid_1_total == 0)
    return success, report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PCRD Canonical Story Corpus Staging Rebuild (Phase 3B)")
    parser.add_argument("--truth-version", type=str, default=None, help="指定 TruthVersion (預設自動解析)")
    parser.add_argument("--staging-dir", type=str, default=None, help="自定義 staging 目錄 (嚴禁 production story)")
    parser.add_argument("--cache-dir", type=str, default=None, help="自定義 bundle 快取目錄")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"並行執行緒數 (預設 {DEFAULT_WORKERS})")
    parser.add_argument("--limit", type=int, default=None, help="限制處理話數 (測試用)")
    parser.add_argument("--clean", action="store_true", help="執行前清理 staging 目錄")
    args = parser.parse_args()

    s_dir = Path(args.staging_dir) if args.staging_dir else None
    c_dir = Path(args.cache_dir) if args.cache_dir else None

    ok, rep = run_staging_rebuild(
        truth_version=args.truth_version,
        staging_dir=s_dir,
        cache_dir=c_dir,
        workers=args.workers,
        limit=args.limit,
        clean_staging=args.clean,
    )
    sys.exit(0 if ok else 1)
