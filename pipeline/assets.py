# -*- coding: utf-8 -*-
"""
assets.py — PCRD Story Map 資產完整性門禁模組 (Asset Completeness Gate v1)
負責協調與檢查：
  1. Event Top 封面縮圖完整性 (Event Top Completeness)
  2. 官方話數縮圖完整性 (Story Thumbnail Completeness)
  3. 動畫映射覆蓋門禁 (Delta-based Movie Coverage Gate)

約束與防禦政策：
  - 輕量化協調 (Orchestration only)，重用既有 tools 下載工具，不重複實作下載邏輯。
  - Dry-Run 零寫入保證：0 WebP download, 0 contract write, 0 report write, 0 manifest write。
  - 歷史既有動畫缺口 (historical gaps) 列為 WARN (non-blocking legacy debt)。
  - 新引入動畫 (newly introduced references) 若無 mapping 則 blocking FAIL。
"""

import io
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any, Union

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DASHBOARD_DIR = BASE_DIR / "dashboard"
STORY_DIR = DASHBOARD_DIR / "story"
DATA_DIR = DASHBOARD_DIR / "data"
EVENT_TOP_DIR = DASHBOARD_DIR / "icon" / "event_top"
STORY_THUMB_DIR = DASHBOARD_DIR / "icon" / "story"

MOVIE_LINKS_PATH = DATA_DIR / "movie_links.json"
MOVIE_BASELINE_PATH = BASE_DIR / "pipeline" / "manifests" / "movie_reference_manifest.json"
OFFICIAL_EVENT_TOP_MANIFEST = BASE_DIR / "pipeline" / "manifests" / "official_event_top_manifest.json"


# ==============================================================================
# 1. 結構化資料定義 (Result Dataclasses)
# ==============================================================================

@dataclass
class MovieCoverageResult:
    referenced_count: int = 0
    historical_missing_count: int = 0
    new_references_count: int = 0
    new_missing_count: int = 0
    historical_missing: Dict[str, List[str]] = field(default_factory=dict)
    new_missing: Dict[str, List[str]] = field(default_factory=dict)
    new_mapped: List[str] = field(default_factory=list)
    success: bool = True


@dataclass
class EventTopCompletenessResult:
    expected_count: int = 0
    present_count: int = 0
    missing_count: int = 0
    stale_count: int = 0
    missing_ids: List[str] = field(default_factory=list)
    stale_ids: List[str] = field(default_factory=list)
    success: bool = True


@dataclass
class StoryThumbnailCompletenessResult:
    officially_available_count: int = 0
    present_count: int = 0
    missing_count: int = 0
    missing_story_ids: List[str] = field(default_factory=list)
    fallback_count: int = 0
    success: bool = True


@dataclass
class AssetCompletenessResult:
    event_top: EventTopCompletenessResult = field(default_factory=EventTopCompletenessResult)
    story_thumbnail: StoryThumbnailCompletenessResult = field(default_factory=StoryThumbnailCompletenessResult)
    movie_coverage: MovieCoverageResult = field(default_factory=MovieCoverageResult)
    success: bool = True


# ==============================================================================
# 2. Movie Normalization & Delta Coverage
# ==============================================================================

def normalize_movie_id(raw_id: Any) -> str:
    """
    正規化 Movie ID，與前端 MediaService.normalizeMovieId() 一致。
    範例：
      'movie_123' -> '123'
      'story_123' -> '123'
      '123'       -> '123'
      123         -> '123'
    """
    s = str(raw_id).strip()
    s = re.sub(r'^(?:movie|story)_', '', s, flags=re.IGNORECASE)
    return s


def scan_movie_references(story_dir: Optional[Path] = None) -> Tuple[Set[str], Dict[str, List[str]]]:
    """
    唯讀掃描 dashboard/story/*.json 中的所有純數字劇本，
    提取 item.get('type') == 'movie' 的 movie_id。
    :return: (unique_movie_ids_set, movie_to_referencing_stories_map)
    """
    target_dir = story_dir or STORY_DIR
    movie_to_stories: Dict[str, List[str]] = {}
    
    if not target_dir.exists():
        return set(), {}

    for p in sorted(target_dir.glob('*.json')):
        if not p.stem.isdigit():
            continue
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get('items', [])
            for item in items:
                if isinstance(item, dict) and item.get('type') == 'movie':
                    mid = item.get('movie_id')
                    if mid:
                        norm = normalize_movie_id(mid)
                        if norm not in movie_to_stories:
                            movie_to_stories[norm] = []
                        if p.stem not in movie_to_stories[norm]:
                            movie_to_stories[norm].append(p.stem)
        except Exception:
            pass

    return set(movie_to_stories.keys()), movie_to_stories


def check_movie_coverage(
    story_dir: Optional[Path] = None,
    movie_links_path: Optional[Path] = None,
    baseline_path: Optional[Path] = None
) -> MovieCoverageResult:
    """
    執行 Delta-based Movie Coverage 分析：
    - historical missing -> WARN (non-blocking)
    - newly introduced missing -> FAIL (blocking)
    """
    target_story_dir = story_dir or STORY_DIR
    target_links_path = movie_links_path or MOVIE_LINKS_PATH
    target_baseline_path = baseline_path or MOVIE_BASELINE_PATH

    current_refs, movie_to_stories = scan_movie_references(target_story_dir)

    # 讀取 tracked baseline
    previous_refs: Set[str] = set()
    if target_baseline_path.exists():
        try:
            with open(target_baseline_path, 'r', encoding='utf-8') as f:
                bdata = json.load(f)
            previous_refs = {normalize_movie_id(m) for m in bdata.get('movie_ids', [])}
        except Exception as e:
            print(f"  [WARN] 讀取 movie baseline 失敗: {e}", file=sys.stderr)

    # 讀取 mapped movie_links.json (要求 mapping value 必須非空)
    mapped_ids: Set[str] = set()
    if target_links_path.exists():
        try:
            with open(target_links_path, 'r', encoding='utf-8') as f:
                mldata = json.load(f)
            mapped_ids = {
                normalize_movie_id(k)
                for k, v in mldata.items()
                if v and str(v).strip()
            }
        except Exception as e:
            print(f"  [WARN] 讀取 movie_links.json 失敗: {e}", file=sys.stderr)

    new_refs = current_refs - previous_refs
    historical_refs = current_refs & previous_refs

    historical_missing = {
        m: movie_to_stories.get(m, [])
        for m in sorted(historical_refs)
        if m not in mapped_ids
    }
    new_missing = {
        m: movie_to_stories.get(m, [])
        for m in sorted(new_refs)
        if m not in mapped_ids
    }
    new_mapped = [
        m for m in sorted(new_refs)
        if m in mapped_ids
    ]

    success = (len(new_missing) == 0)

    return MovieCoverageResult(
        referenced_count=len(current_refs),
        historical_missing_count=len(historical_missing),
        new_references_count=len(new_refs),
        new_missing_count=len(new_missing),
        historical_missing=historical_missing,
        new_missing=new_missing,
        new_mapped=new_mapped,
        success=success
    )


def promote_movie_baseline(
    current_refs: Set[str],
    baseline_path: Optional[Path] = None
) -> bool:
    """
    在通過門禁且確認更新後，原子性寫入更新 movie_reference_manifest.json。
    """
    target_path = baseline_path or MOVIE_BASELINE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_ids = sorted(list({normalize_movie_id(m) for m in current_refs}))

    data = {
        "schema_version": "1.0",
        "description": "Tracked baseline of known referenced movie IDs in production stories",
        "total_movies": len(sorted_ids),
        "movie_ids": sorted_ids
    }

    tmp_path = target_path.with_suffix('.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(target_path)
        return True
    except Exception as e:
        print(f"  [ERROR] 寫入 movie baseline 失敗: {e}", file=sys.stderr)
        return False


def resolve_truth_version(specified: Optional[str] = None) -> str:
    """決定性解析當前 TruthVersion，優先使用較新之官方 pinned 版本或傳入值，防範第三方鏡像滯後"""
    pinned_tv = None
    if OFFICIAL_EVENT_TOP_MANIFEST.exists():
        try:
            with open(OFFICIAL_EVENT_TOP_MANIFEST, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                pinned_tv = cdata.get("truth_version")
                if pinned_tv:
                    pinned_tv = str(pinned_tv).strip()
        except Exception:
            pass

    if specified and str(specified).strip():
        spec_str = str(specified).strip()
        if pinned_tv and pinned_tv > spec_str:
            return pinned_tv
        return spec_str

    if pinned_tv:
        return pinned_tv

    try:
        from pipeline.extract_chapter_titles import get_current_truth_version
        return get_current_truth_version()
    except Exception:
        return "00610007"


# ==============================================================================
# 3. Event Top Completeness Gate
# ==============================================================================

def check_event_top_completeness(
    truth_version: Optional[str] = None,
    dry_run: bool = False,
    output_dir: Optional[Path] = None,
    contract_path: Optional[Path] = None
) -> EventTopCompletenessResult:
    """
    檢查活動頂層專屬縮圖 (256x128) 完整性。
    重用 tools/fetch_event_top_thumbnails.py：
      - dry-run: 僅透過 CDN manifest 或本地契約比對，零檔案寫入。
      - non-dry-run: 自動補齊缺失並驗證，若仍有缺失則 FAIL。
    """
    from tools.fetch_event_top_thumbnails import (
        download_cdn_manifest,
        parse_event_top_targets_from_manifest,
        run_pipeline,
        is_target_identity_equal,
        MANIFEST_CONTRACT_PATH
    )

    target_dir = output_dir or EVENT_TOP_DIR
    target_contract = contract_path or OFFICIAL_EVENT_TOP_MANIFEST
    tv = resolve_truth_version(truth_version)

    # 取得預期 targets (current CDN targets)
    targets: Dict[str, Any] = {}
    try:
        manifest_text = download_cdn_manifest(tv)
        targets = parse_event_top_targets_from_manifest(manifest_text)
    except Exception as e:
        # 若連線 CDN 失敗，嘗試從本地 pinned contract 讀取
        if target_contract.exists():
            try:
                with open(target_contract, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                targets = cdata.get('targets', {})
            except Exception:
                pass
        if not targets:
            print(f"  [WARN] 無法取得 Event Top 預期清單: {e}", file=sys.stderr)
            return EventTopCompletenessResult(success=False)

    expected_ids = set(targets.keys())

    # 載入現有 tracked contract (作為 identity 比對基準)
    old_targets: Dict[str, Any] = {}
    if target_contract.exists():
        try:
            with open(target_contract, 'r', encoding='utf-8') as f:
                cdata = json.load(f)
                old_targets = cdata.get('targets', {})
        except Exception:
            pass

    # 比對本地檔案
    local_files: Set[str] = set()
    if target_dir.exists():
        for p in target_dir.glob('*.webp'):
            if p.is_file() and p.stat().st_size > 0:
                local_files.add(p.stem)

    missing = sorted(list(expected_ids - local_files))
    present = sorted(list(expected_ids & local_files))

    # 檢查 upstream identity 是否變更 (stale/changed)
    stale_ids = []
    for eid, new_info in targets.items():
        old_info = old_targets.get(eid)
        if old_info and not is_target_identity_equal(old_info, new_info):
            stale_ids.append(eid)
    stale_ids = sorted(stale_ids)

    # 若非 dry-run 且有缺失或素材變更，呼叫既有 pipeline 自動同步
    if not dry_run and (missing or stale_ids):
        print(f"  [EventTop] 發現 {len(missing)} 張官方活動頂層縮圖缺失、{len(stale_ids)} 張素材變更，啟動自動同步...")
        try:
            run_pipeline(
                from_contract=False,
                specified_truth_version=tv,
                output_dir=target_dir,
                contract_path=target_contract
            )
            # 重新比對本地
            local_files.clear()
            for p in target_dir.glob('*.webp'):
                if p.is_file() and p.stat().st_size > 0:
                    local_files.add(p.stem)
            missing = sorted(list(expected_ids - local_files))
            present = sorted(list(expected_ids & local_files))

            # 重新載入更新後的 contract 比對 identity
            new_old_targets: Dict[str, Any] = {}
            if target_contract.exists():
                with open(target_contract, 'r', encoding='utf-8') as f:
                    new_old_targets = json.load(f).get('targets', {})
            stale_ids = sorted([
                eid for eid, new_info in targets.items()
                if not is_target_identity_equal(new_old_targets.get(eid), new_info)
            ])
        except Exception as e:
            print(f"  [ERROR] Event Top 自動同步失敗: {e}", file=sys.stderr)

    success = (len(missing) == 0 and len(stale_ids) == 0)

    return EventTopCompletenessResult(
        expected_count=len(expected_ids),
        present_count=len(present),
        missing_count=len(missing),
        stale_count=len(stale_ids),
        missing_ids=missing,
        stale_ids=stale_ids,
        success=success
    )


# ==============================================================================
# 4. Story Thumbnail Completeness Gate
# ==============================================================================

def parse_story_thumbs_from_manifest(manifest_content: str) -> Dict[str, str]:
    """從 icon2_assetmanifest 字串解析所有官方話數縮圖 {story_id: bundle_hash}"""
    thumbs = {}
    for line in manifest_content.splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 3 and "icon_thumb_story_" in parts[0]:
            bundle_name = parts[0]
            bundle_hash = parts[2]
            stem = bundle_name.replace("a/icon_thumb_story_", "").replace(".unity3d", "")
            thumbs[stem] = bundle_hash
    return thumbs


def check_story_thumbnail_completeness(
    truth_version: Optional[str] = None,
    dry_run: bool = False,
    output_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    story_ids: Optional[List[str]] = None
) -> StoryThumbnailCompletenessResult:
    """
    檢查官方劇情話數專屬縮圖 (256x128) 完整性。
    僅要求：CDN 明確有官方縮圖之 target (required story IDs ∩ CDN thumbs)，本地必須存在 WebP。
    CDN 原本就沒有專屬縮圖的話數，走前端 fallback，不視為缺失。
    """
    from tools.fetch_story_thumbnails import (
        collect_target_story_ids,
        fetch_all_story_thumbnails,
        SONET_CDN,
        SONET_HEADER,
        MANIFEST_PATH
    )
    target_dir = output_dir or STORY_THUMB_DIR
    target_manifest_file = manifest_path or MANIFEST_PATH
    tv = resolve_truth_version(truth_version)

    # 1. 取得指定 TruthVersion 的 CDN 官方縮圖清單 (權威來源，記憶體解析零寫入)
    cdn_thumbs: Dict[str, str] = {}
    try:
        url = f"{SONET_CDN}/Resources/{tv}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
        req = urllib.request.Request(url, headers=SONET_HEADER)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        manifest_text = data.decode("utf-8", errors="ignore")
        cdn_thumbs = parse_story_thumbs_from_manifest(manifest_text)
        # 僅在非 dry-run 且使用本地路徑時，作為下載工具快取保存
        if not dry_run and target_manifest_file:
            with open(target_manifest_file, "wb") as f:
                f.write(data)
    except Exception as e:
        print(f"  [ERROR] 無法從 CDN 取得 TruthVersion {tv} 之 icon2_assetmanifest 權威清單: {e}", file=sys.stderr)
        return StoryThumbnailCompletenessResult(success=False)

    # 2. 收集目標話數 universe
    target_universe = collect_target_story_ids(story_ids=story_ids)

    # 3. 計算交集：官方明確有縮圖的項目
    officially_available = set(target_universe) & set(cdn_thumbs.keys())
    fallback_count = len(set(target_universe) - set(cdn_thumbs.keys()))

    # 4. 比對本地檔案
    local_files: Set[str] = set()
    if target_dir.exists():
        for p in target_dir.glob('*.webp'):
            if p.is_file() and p.stat().st_size > 0:
                local_files.add(p.stem)

    missing = sorted(list(officially_available - local_files))
    present = sorted(list(officially_available & local_files))

    # 若非 dry-run 且有缺失，呼叫既有工具補齊缺失項目
    if not dry_run and missing:
        print(f"  [StoryThumb] 發現 {len(missing)} 話官方縮圖缺失，啟動自動同步...")
        try:
            fetch_all_story_thumbnails(
                force=False,
                story_ids=missing,
                truth_version=tv,
                update_manifest=True
            )
            # 重新比對本地
            local_files.clear()
            for p in target_dir.glob('*.webp'):
                if p.is_file() and p.stat().st_size > 0:
                    local_files.add(p.stem)
            missing = sorted(list(officially_available - local_files))
            present = sorted(list(officially_available & local_files))
        except Exception as e:
            print(f"  [ERROR] Story Thumbnails 自動同步失敗: {e}", file=sys.stderr)

    success = (len(missing) == 0)

    return StoryThumbnailCompletenessResult(
        officially_available_count=len(officially_available),
        present_count=len(present),
        missing_count=len(missing),
        missing_story_ids=missing,
        fallback_count=fallback_count,
        success=success
    )


# ==============================================================================
# 5. Asset Completeness Orchestration
# ==============================================================================

def analyze_asset_completeness(
    truth_version: Optional[str] = None,
    dry_run: bool = False
) -> AssetCompletenessResult:
    """
    執行完整資產完整性門禁分析與回報。
    包含：
      1. Event Top 封面縮圖
      2. Story Thumbnail 各話縮圖
      3. Delta-based Movie Coverage
    """
    print("\n[Asset Completeness]")

    # 1. Event Top
    et_res = check_event_top_completeness(truth_version=truth_version, dry_run=dry_run)
    print("\nEvent Top:")
    print(f"  expected: {et_res.expected_count}")
    print(f"  missing: {et_res.missing_count}")
    if et_res.stale_count > 0:
        print(f"  stale/changed: {et_res.stale_count}")
    print(f"  {'PASS' if et_res.success else 'FAIL'}")
    if not et_res.success:
        err_msg = []
        if et_res.missing_ids:
            err_msg.append(f"缺失 IDs: {et_res.missing_ids}")
        if et_res.stale_ids:
            err_msg.append(f"素材變更 IDs: {et_res.stale_ids}")
        print(f"  ❌ Event Top Gate FAILED ({'; '.join(err_msg)})")

    # 2. Story Thumbnail
    st_res = check_story_thumbnail_completeness(truth_version=truth_version, dry_run=dry_run)
    print("\nStory Thumbnail:")
    print(f"  officially available: {st_res.officially_available_count}")
    print(f"  missing: {st_res.missing_count}")
    print(f"  {'PASS' if st_res.success else 'FAIL'}")
    if not st_res.success:
        print(f"  ❌ Story Thumbnail Gate FAILED (缺失 IDs: {st_res.missing_story_ids[:10]}...)")

    # 3. Movie Coverage
    mv_res = check_movie_coverage()
    print("\nMovie Coverage:")
    print(f"  referenced: {mv_res.referenced_count}")
    print(f"  historical missing: {mv_res.historical_missing_count}")
    print(f"  new references: {mv_res.new_references_count}")
    print(f"  new missing: {mv_res.new_missing_count}")
    print(f"  {'PASS' if mv_res.success else 'FAIL'}")
    if not mv_res.success:
        print("\n❌ Movie Coverage Gate FAILED")
        print(f"New movie references: {mv_res.new_references_count}")
        print(f"New mapped: {len(mv_res.new_mapped)}")
        print(f"New missing: {mv_res.new_missing_count}\n")
        for mid, sids in sorted(mv_res.new_missing.items()):
            print(f"{mid}")
            print(f"  referenced by: {', '.join(sids)}\n")
        print("Movie processing/upload is required before release.")

    overall_success = et_res.success and st_res.success and mv_res.success

    if overall_success:
        # 非 dry-run 且有新 reference 時，晉升 baseline
        if not dry_run and mv_res.new_references_count > 0:
            current_refs, _ = scan_movie_references()
            promoted = promote_movie_baseline(current_refs)
            if promoted:
                print("  [Baseline] 已成功晉升並更新 movie_reference_manifest.json")
            else:
                print("  ❌ [ERROR] Baseline promotion 寫入失敗！阻斷後續發布。", file=sys.stderr)
                overall_success = False

    if overall_success:
        print("\n✅ Asset Completeness PASS")
    else:
        print("\n❌ Asset Completeness FAIL")

    return AssetCompletenessResult(
        event_top=et_res,
        story_thumbnail=st_res,
        movie_coverage=mv_res,
        success=overall_success
    )
