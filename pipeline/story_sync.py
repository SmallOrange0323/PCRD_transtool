#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map - Required Story Auto Sync

將 Coverage Guard 發現的核心必備劇本缺口接回既有官方 CDN 抓取 primitive。

政策：
- 只處理 coverage.missing_required_ids；optional / unknown 不自動抓取。
- 使用單一 TruthVersion snapshot 載入 storydata2_assetmanifest。
- dry-run 只驗證缺失話數是否存在於該 snapshot，不下載 story bundle、不寫檔。
- normal mode 重用 tools.pcrd_fetch.sync_story_batch_with_metadata，同步 Story JSON + 官方 metadata。
- 同步後必須重新執行 Coverage Guard；仍有 required missing 即 FAIL。
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class RequiredStorySyncResult:
    requested_ids: List[int] = field(default_factory=list)
    fetchable_ids: List[int] = field(default_factory=list)
    unavailable_ids: List[int] = field(default_factory=list)
    synced_ids: List[int] = field(default_factory=list)
    failed_ids: List[int] = field(default_factory=list)
    dry_run: bool = False
    success: bool = True
    message: str = ""


def ensure_required_story_coverage(
    coverage: Any,
    truth_version: Optional[str],
    dry_run: bool = False,
) -> Tuple[RequiredStorySyncResult, Any]:
    """
    補齊 Coverage Guard 判定為 required 的缺失劇本。

    :return: (sync_result, effective_coverage)
      - dry-run 成功時 effective_coverage 仍為原 coverage（零寫入，缺口尚未真的補齊）。
      - normal mode 成功時 effective_coverage 為同步後重新 analyze 的結果。
    """
    raw_missing = list(getattr(coverage, "missing_required_ids", []) or [])
    missing_ids = sorted({int(sid) for sid in raw_missing})

    result = RequiredStorySyncResult(
        requested_ids=missing_ids,
        dry_run=dry_run,
    )

    if not missing_ids:
        result.message = "required story coverage already complete"
        return result, coverage

    if not truth_version:
        result.success = False
        result.failed_ids = missing_ids
        result.message = "missing authoritative TruthVersion; cannot auto-sync required stories"
        return result, coverage

    try:
        from tools.pcrd_fetch import (
            load_story_manifest_bundle_refs,
            sync_story_batch_with_metadata,
        )
    except Exception as exc:
        result.success = False
        result.failed_ids = missing_ids
        result.message = f"cannot load canonical story fetch primitive: {exc}"
        return result, coverage

    try:
        bundle_refs = load_story_manifest_bundle_refs(truth_version=str(truth_version))
    except Exception as exc:
        result.success = False
        result.failed_ids = missing_ids
        result.message = f"cannot load storydata2_assetmanifest for TruthVersion {truth_version}: {exc}"
        return result, coverage

    result.fetchable_ids = [sid for sid in missing_ids if sid in bundle_refs]
    result.unavailable_ids = [sid for sid in missing_ids if sid not in bundle_refs]

    if result.unavailable_ids:
        result.success = False
        result.failed_ids = list(result.unavailable_ids)
        result.message = (
            f"{len(result.unavailable_ids)} required stories are not present in "
            f"TruthVersion {truth_version} story manifest"
        )
        return result, coverage

    if dry_run:
        result.message = (
            f"dry-run: {len(result.fetchable_ids)} required stories are fetchable "
            f"from TruthVersion {truth_version}"
        )
        return result, coverage

    ok, _metadata_version, success_ids, failed_ids = sync_story_batch_with_metadata(
        missing_ids,
        truth_version=str(truth_version),
        write_story_json=True,
        bundle_refs=bundle_refs,
        replace_existing=False,
    )

    result.synced_ids = sorted({int(sid) for sid in success_ids})
    result.failed_ids = sorted({int(sid) for sid in failed_ids})

    if not ok:
        result.success = False
        if not result.failed_ids:
            result.failed_ids = sorted(set(missing_ids) - set(result.synced_ids))
        result.message = "required story batch sync failed"
        return result, coverage

    # Canonical post-sync verification: do not trust downloader success alone.
    from pipeline.coverage import analyze_coverage, CoverageAnalysisStatus

    refreshed = analyze_coverage()
    if refreshed.analysis_status == CoverageAnalysisStatus.INVALID:
        result.success = False
        result.message = "post-sync coverage analysis is INVALID"
        return result, refreshed

    remaining = sorted({int(sid) for sid in (refreshed.missing_required_ids or [])})
    if remaining:
        result.success = False
        result.failed_ids = remaining
        result.message = f"post-sync coverage still missing {len(remaining)} required stories"
        return result, refreshed

    result.success = True
    result.message = f"synced {len(result.synced_ids)} required stories successfully"
    return result, refreshed
