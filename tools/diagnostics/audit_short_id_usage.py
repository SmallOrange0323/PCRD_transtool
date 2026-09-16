# -*- coding: utf-8 -*-
"""
tools/diagnostics/audit_short_id_usage.py — Phase 3A Usage-Driven 6111 Collision Audit

用途:
1. 建立 current stored unit_id: 6111 baseline。
2. 透過單一 TruthVersion snapshot (00610007) 官方無寫入解析 (No-Write Parse) 進行對照。
3. 嚴格比對故事語意對齊 (Semantic Alignment)，排除漂移話數。
4. 驗證現有 6111 是否 100% 符合官方 command stream (VERIFIED_EXACT) 或存在衝突 (COLLISION)。
5. 探索官方 command stream 中存在 6111 但現有資料缺失之話數 (MISSING_CANONICAL_6111)。
6. 產出 docs/data/npc_6111_usage_audit.json 與解耦後的精確統計數據。
"""

import os
import sys
import json
import glob
import re
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
    _parse_bundle_dialogues,
    _http_get,
    WEB_HEADER,
    SONET_CDN
)


def normalize_text(text: Any) -> str:
    """對白文字規範化比對（忽略換行符格式、玩家佔位符、空白差異）"""
    if text is None:
        return ""
    w = str(text)
    w = w.replace("{0}", "主角").replace("{player}", "主角")
    w = w.replace("主公大人", "主人")
    w = w.replace("\\n", "\n")
    w = re.sub(r"\s+", "", w)
    return w


def story_rows_semantically_align(
    current_rows: List[Dict[str, Any]],
    parsed_rows: List[Dict[str, Any]]
) -> Tuple[bool, str, int]:
    """
    純函式：比對整篇故事的 current rows 與 parsed rows 是否語意完全對齊。
    必須比對：type, name, words, voice, bg_id/background, still/still_id, movie_id。
    特別注意：忽略 unit_id（因為 unit_id 為審計目標）。
    回傳：(is_aligned, reason_str, mismatch_row_index)
    """
    if len(current_rows) != len(parsed_rows):
        return False, "UNVERIFIABLE_STORY_DRIFT_LENGTH", -1

    for idx, (c_row, p_row) in enumerate(zip(current_rows, parsed_rows)):
        # 1. type（若無 type 但有 words 或 name 則視為 dialogue）
        c_type = c_row.get("type") or ("dialogue" if "words" in c_row or "name" in c_row else None)
        p_type = p_row.get("type") or ("dialogue" if "words" in p_row or "name" in p_row else None)
        if c_type != p_type:
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: type mismatch ('{c_type}' vs '{p_type}')", idx

        # 2. name (speaker)
        c_name = (c_row.get("name") or "").strip()
        p_name = (p_row.get("name") or "").strip()
        if c_name != p_name:
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: speaker name mismatch ('{c_name}' vs '{p_name}')", idx

        # 3. words (normalized)
        c_words = normalize_text(c_row.get("words"))
        p_words = normalize_text(p_row.get("words"))
        if c_words != p_words:
            return False, "UNVERIFIABLE_STORY_DRIFT_CONTENT: words mismatch", idx

        # 4. voice
        c_voice = c_row.get("voice") or None
        p_voice = p_row.get("voice") or None
        if c_voice != p_voice:
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: voice mismatch ('{c_voice}' vs '{p_voice}')", idx

        # 5. bg_id / background
        c_bg = c_row.get("bg_id") or c_row.get("background") or None
        p_bg = p_row.get("bg_id") or p_row.get("background") or None
        if (str(c_bg) if c_bg is not None else None) != (str(p_bg) if p_bg is not None else None):
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: bg_id mismatch ('{c_bg}' vs '{p_bg}')", idx

        # 6. still / still_id
        c_still = c_row.get("still") or c_row.get("still_id") or None
        p_still = p_row.get("still") or p_row.get("still_id") or None
        if (str(c_still) if c_still is not None else None) != (str(p_still) if p_still is not None else None):
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: still mismatch ('{c_still}' vs '{p_still}')", idx

        c_still_id = c_row.get("still_id") or c_row.get("still") or None
        p_still_id = p_row.get("still_id") or p_row.get("still") or None
        if (str(c_still_id) if c_still_id is not None else None) != (str(p_still_id) if p_still_id is not None else None):
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: still_id mismatch ('{c_still_id}' vs '{p_still_id}')", idx

        # 7. movie_id
        c_movie = c_row.get("movie_id") or None
        p_movie = p_row.get("movie_id") or None
        if (str(c_movie) if c_movie is not None else None) != (str(p_movie) if p_movie is not None else None):
            return False, f"UNVERIFIABLE_STORY_DRIFT_CONTENT: movie_id mismatch ('{c_movie}' vs '{p_movie}')", idx

    return True, "ALIGNED", -1


def classify_short_id_row(current_uid: Any, parsed_uid: Any, target_short_id: int = 6111) -> str:
    """分類單列在指定 target_short_id 下的比對狀態"""
    if current_uid == target_short_id and parsed_uid == target_short_id:
        return "VERIFIED_EXACT"
    if current_uid == target_short_id and parsed_uid != target_short_id:
        return "COLLISION"
    if current_uid != target_short_id and parsed_uid == target_short_id:
        return "MISSING_CANONICAL"
    return "IRRELEVANT"


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

    observed_parsed_6111_rows = 0
    aligned_parsed_6111_rows = 0
    unmatched_due_to_story_drift = 0

    per_story_results = []
    collisions_detail = []

    for sid in audit_target_sids:
        curr_path = os.path.join(story_dir, f"{sid}.json")
        curr_dialogues = []
        if os.path.exists(curr_path):
            with open(curr_path, "r", encoding="utf-8") as f:
                curr_dialogues = json.load(f)

        stored_rows = baseline_stories.get(sid, [])
        stored_count = len(stored_rows)

        ref = refs.get(sid)
        if not ref:
            unverifiable_total += stored_count
            per_story_results.append({
                "story_id": sid,
                "status": "UNVERIFIABLE_BUNDLE_MISSING",
                "stored_6111_rows": stored_count,
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": stored_count,
                "missing_canonical": 0,
                "observed_parsed_6111": 0
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
            unverifiable_total += stored_count
            per_story_results.append({
                "story_id": sid,
                "status": f"UNVERIFIABLE_PARSE_ERROR: {e}",
                "stored_6111_rows": stored_count,
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": stored_count,
                "missing_canonical": 0,
                "observed_parsed_6111": 0
            })
            continue

        story_parsed_6111 = sum(1 for r in parsed_dialogues if r.get("unit_id") == 6111)
        observed_parsed_6111_rows += story_parsed_6111

        # 執行整篇語意對齊檢查 (Semantic Alignment)
        is_aligned, align_reason, mismatch_idx = story_rows_semantically_align(curr_dialogues, parsed_dialogues)

        if not is_aligned:
            unverifiable_total += stored_count
            unmatched_due_to_story_drift += story_parsed_6111
            per_story_results.append({
                "story_id": sid,
                "status": align_reason,
                "mismatch_index": mismatch_idx,
                "current_length": len(curr_dialogues),
                "parsed_length": len(parsed_dialogues),
                "stored_6111_rows": stored_count,
                "verified_exact": 0,
                "collision": 0,
                "unverifiable": stored_count,
                "missing_canonical": 0,
                "observed_parsed_6111": story_parsed_6111
            })
            continue

        # 故事完全語意對齊，進行逐列 Short-ID 分類
        aligned_parsed_6111_rows += story_parsed_6111
        story_verified = 0
        story_collision = 0
        story_missing = 0
        story_missing_details = []

        for ridx, (c_row, p_row) in enumerate(zip(curr_dialogues, parsed_dialogues)):
            c_uid = c_row.get("unit_id")
            p_uid = p_row.get("unit_id")

            cls = classify_short_id_row(c_uid, p_uid, target_short_id=6111)

            if cls == "VERIFIED_EXACT":
                story_verified += 1
                verified_exact_total += 1
            elif cls == "COLLISION":
                story_collision += 1
                collision_total += 1
                collisions_detail.append({
                    "story_id": sid,
                    "row_index": ridx,
                    "speaker": c_row.get("name"),
                    "words": c_row.get("words", "")[:30],
                    "current_unit_id": c_uid,
                    "parsed_unit_id": p_uid,
                    "reason": "NOT_REPRODUCIBLE_UNDER_CONSERVATIVE_PARSER"
                })
            elif cls == "MISSING_CANONICAL":
                story_missing += 1
                missing_canonical_total += 1
                missing_speaker_dist[p_row.get("name")] += 1
                story_missing_details.append({
                    "story_id": sid,
                    "row_index": ridx,
                    "speaker": p_row.get("name"),
                    "words": p_row.get("words", "")[:30],
                    "current_unit_id": c_uid,
                    "parsed_unit_id": p_uid
                })

        if story_missing_details:
            missing_by_story[sid] = story_missing_details

        per_story_results.append({
            "story_id": sid,
            "status": "PASS" if story_collision == 0 else "FAIL",
            "dialogue_count": len(curr_dialogues),
            "stored_6111_rows": stored_count,
            "verified_exact": story_verified,
            "collision": story_collision,
            "unverifiable": 0,
            "missing_canonical": story_missing,
            "observed_parsed_6111": story_parsed_6111
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
            "observed_parsed_6111_rows": observed_parsed_6111_rows,
            "aligned_parsed_6111_rows": aligned_parsed_6111_rows,
            "already_present_verified": verified_exact_total,
            "missing_from_current_aligned": missing_canonical_total,
            "unmatched_due_to_story_drift": unmatched_due_to_story_drift,
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
    out_path = os.path.join(PROJECT_ROOT, "docs", "data", "npc_6111_usage_audit.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"Report JSON written to: {out_path}")
    print("AUDIT_COMPLETE")
    print("TruthVersion:", res["truth_version"])
    print("Stored rows:", res["baseline"]["stored_rows"])
    print("Verified exact:", res["verification"]["verified_exact"])
    print("Collision:", res["verification"]["collision"])
    print("Unverifiable:", res["verification"]["unverifiable"])
    print("Observed parsed 6111 rows:", res["official_usage"]["observed_parsed_6111_rows"])
    print("Aligned parsed 6111 rows:", res["official_usage"]["aligned_parsed_6111_rows"])
    print("Missing canonical:", res["official_usage"]["missing_from_current_aligned"])
    print("Safe for current corpus:", res["safety_assessment"]["safe_for_current_stored_corpus"])


