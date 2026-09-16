# -*- coding: utf-8 -*-
"""
tools/diagnostics/audit_short_id_usage.py — Phase 3A Usage-Driven 6111 Collision Audit

用途:
1. 建立 current stored unit_id: 6111 baseline。
2. 透過單一 TruthVersion snapshot (00610007) 官方無寫入解析 (No-Write Parse) 進行對照。
3. 驗證現有 6111 是否 100% 符合官方 command stream (VERIFIED_EXACT) 或存在衝突 (COLLISION)。
4. 探索官方 command stream 中存在 6111 但現有資料缺失之話數 (MISSING_CANONICAL_6111)。
5. 產出 docs/data/npc_6111_usage_audit.json 與統計數據。
"""

import os
import sys
import json
import glob
from collections import Counter
from typing import Dict, List, Any, Set, Tuple

# 確保引用專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

from tools.pcrd_fetch import (
    load_story_manifest_snapshot,
    fetch_story_json_by_id,
    _parse_bundle_dialogues,
    _http_get,
    WEB_HEADER,
    SONET_CDN
)


def scan_baseline_6111(story_dir: str) -> Tuple[Dict[int, List[Dict[str, Any]]], Counter]:
    """掃描目前 dashboard/story/*.json 找出所有包含 unit_id == 6111 的話數與對白列"""
    stories_with_6111 = {}
    speaker_dist = Counter()

    for p in glob.glob(os.path.join(story_dir, "*.json")):
        fname = os.path.basename(p)
        try:
            sid = int(fname.split(".")[0])
        except ValueError:
            continue

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not isinstance(data, list):
            continue

        matched_rows = []
        for idx, row in enumerate(data):
            if row.get("unit_id") == 6111:
                matched_rows.append({
                    "row_index": idx,
                    "speaker": row.get("name"),
                    "words": row.get("words", ""),
                    "voice": row.get("voice")
                })
                speaker_dist[row.get("name")] += 1

        if matched_rows:
            stories_with_6111[sid] = matched_rows

    return stories_with_6111, speaker_dist


def run_6111_audit(truth_version: str = "00610007") -> Dict[str, Any]:
    story_dir = os.path.join(PROJECT_ROOT, "dashboard", "story")
    baseline_stories, speaker_dist = scan_baseline_6111(story_dir)

    total_stored_rows = sum(len(rows) for rows in baseline_stories.values())

    # Audit universe: baseline_stories UNION {5218004}
    audit_target_sids = sorted(list(set(baseline_stories.keys()) | {5218004}))

    # 載入單一快照
    refs, portrait_keys = load_story_manifest_snapshot(truth_version=truth_version)

    verified_exact_total = 0
    collision_total = 0
    unverifiable_total = 0

    missing_canonical_total = 0
    missing_by_story = {}
    missing_speaker_dist = Counter()

    per_story_results = []
    collisions_detail = []

    for sid in audit_target_sids:
        curr_path = os.path.join(story_dir, f"{sid}.json")
        curr_dialogues = []
        if os.path.exists(curr_path):
            with open(curr_path, "r", encoding="utf-8") as f:
                curr_dialogues = json.load(f)

        ref = refs.get(sid)
        if not ref:
            unverifiable_total += len(baseline_stories.get(sid, []))
            per_story_results.append({
                "story_id": sid,
                "status": "UNVERIFIABLE_BUNDLE_MISSING",
                "stored_6111_rows": len(baseline_stories.get(sid, [])),
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": len(baseline_stories.get(sid, [])),
                "missing_canonical": 0
            })
            continue

        # 下載 bundle 並無寫入解析
        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{ref.cdn_bundle_hash[:2]}/{ref.cdn_bundle_hash}"
        try:
            bundle_bytes = _http_get(bundle_url, WEB_HEADER, timeout=15)
            parsed_dialogues = _parse_bundle_dialogues(
                bundle_bytes,
                extract_metadata=False,
                portrait_asset_keys=portrait_keys
            )
        except Exception as e:
            unverifiable_total += len(baseline_stories.get(sid, []))
            per_story_results.append({
                "story_id": sid,
                "status": f"UNVERIFIABLE_PARSE_ERROR: {e}",
                "stored_6111_rows": len(baseline_stories.get(sid, [])),
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": len(baseline_stories.get(sid, [])),
                "missing_canonical": 0
            })
            continue

        # 檢查 row count alignment
        if len(curr_dialogues) != len(parsed_dialogues):
            unverifiable_total += len(baseline_stories.get(sid, []))
            per_story_results.append({
                "story_id": sid,
                "status": "UNVERIFIABLE_STORY_DRIFT_LENGTH",
                "current_length": len(curr_dialogues),
                "parsed_length": len(parsed_dialogues),
                "stored_6111_rows": len(baseline_stories.get(sid, [])),
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": len(baseline_stories.get(sid, [])),
                "missing_canonical": 0
            })
            continue

        # 逐列比對
        stored_rows = baseline_stories.get(sid, [])
        story_verified = 0
        story_collision = 0
        story_unverifiable = 0
        story_missing = 0
        story_missing_details = []

        for r in stored_rows:
            ridx = r["row_index"]
            c_row = curr_dialogues[ridx]
            p_row = parsed_dialogues[ridx]

            # 檢查 基本對位 (speaker & words)
            if c_row.get("name") != p_row.get("name"):
                story_collision += 1
                collision_total += 1
                collisions_detail.append({
                    "story_id": sid,
                    "row_index": ridx,
                    "current_speaker": c_row.get("name"),
                    "parsed_speaker": p_row.get("name"),
                    "current_unit_id": c_row.get("unit_id"),
                    "parsed_unit_id": p_row.get("unit_id"),
                    "reason": "SPEAKER_MISMATCH"
                })
            elif p_row.get("unit_id") == 6111:
                story_verified += 1
                verified_exact_total += 1
            else:
                story_collision += 1
                collision_total += 1
                collisions_detail.append({
                    "story_id": sid,
                    "row_index": ridx,
                    "speaker": c_row.get("name"),
                    "words": c_row.get("words", "")[:30],
                    "current_unit_id": c_row.get("unit_id"),
                    "parsed_unit_id": p_row.get("unit_id"),
                    "reason": "UNIT_ID_MISMATCH"
                })

        # 檢查 missing canonical 6111 (parsed 有 6111 但 current 無 6111)
        for ridx, p_row in enumerate(parsed_dialogues):
            if p_row.get("unit_id") == 6111:
                c_row = curr_dialogues[ridx] if ridx < len(curr_dialogues) else {}
                if c_row.get("unit_id") != 6111:
                    story_missing += 1
                    missing_canonical_total += 1
                    missing_speaker_dist[p_row.get("name")] += 1
                    story_missing_details.append({
                        "story_id": sid,
                        "row_index": ridx,
                        "speaker": p_row.get("name"),
                        "words": p_row.get("words", "")[:30],
                        "current_unit_id": c_row.get("unit_id"),
                        "parsed_unit_id": p_row.get("unit_id")
                    })

        if story_missing_details:
            missing_by_story[sid] = story_missing_details

        per_story_results.append({
            "story_id": sid,
            "status": "PASS" if story_collision == 0 and story_unverifiable == 0 else "FAIL",
            "dialogue_count": len(curr_dialogues),
            "stored_6111_rows": len(stored_rows),
            "verified_exact": story_verified,
            "collision": story_collision,
            "unverifiable": story_unverifiable,
            "missing_canonical": story_missing
        })

    audit_result = {
        "truth_version": truth_version,
        "manifest_requests": 1,
        "baseline": {
            "stories": len(baseline_stories),
            "stored_rows": total_stored_rows,
            "speaker_distribution": dict(speaker_dist)
        },
        "verification": {
            "verified_exact": verified_exact_total,
            "collision": collision_total,
            "unverifiable": unverifiable_total
        },
        "official_usage": {
            "total_6111_rows": verified_exact_total + missing_canonical_total,
            "already_present": verified_exact_total,
            "missing_from_current": missing_canonical_total,
            "missing_speaker_distribution": dict(missing_speaker_dist),
            "stories_with_missing_rows": len(missing_by_story)
        },
        "safety_assessment": {
            "collision_count": collision_total,
            "unverifiable_count": unverifiable_total,
            "safe_for_current_stored_corpus": "YES" if (collision_total == 0 and unverifiable_total == 0) else ("NO" if collision_total > 0 else "INCOMPLETE")
        },
        "per_story": per_story_results,
        "collisions_detail": collisions_detail,
        "missing_canonical_details": missing_by_story
    }

    return audit_result


if __name__ == "__main__":
    res = run_6111_audit()
    print("AUDIT_COMPLETE")
    print("TruthVersion:", res["truth_version"])
    print("Stored rows:", res["baseline"]["stored_rows"])
    print("Verified exact:", res["verification"]["verified_exact"])
    print("Collision:", res["verification"]["collision"])
    print("Unverifiable:", res["verification"]["unverifiable"])
    print("Missing canonical:", res["official_usage"]["missing_from_current"])
    print("Safe for current corpus:", res["safety_assessment"]["safe_for_current_stored_corpus"])
