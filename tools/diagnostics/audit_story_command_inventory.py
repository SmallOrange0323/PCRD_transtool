#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_story_command_inventory.py

專案: PCRD Story Map (PCRD_transtool)
功能: 全面盤點 So-net CDN Story AssetBundle 二進位指令流 (Command Census & Unknown Command Inventory)
約束: 嚴格唯讀 (Strictly Read-Only)。只輸出結果至 scratch/，嚴禁修改任何正式目錄或資料庫。
"""

import os
import sys
import json
import sqlite3
import argparse
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict

# 動態推導專案根目錄，確保跨 CWD 執行無副作用
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 引入管線安全常量與解密工具
try:
    from tools.pcrd_fetch import (
        SONET_CDN,
        WEB_HEADER,
        _get_sonet_ver,
        load_story_manifest_hash_map,
        _deserialize_story_raw,
    )
except ImportError:
    from pipeline.fetch import (
        SONET_CDN,
        WEB_HEADER,
        _get_sonet_ver,
        load_story_manifest_hash_map,
        _deserialize_story_raw,
    )

try:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
except ImportError:
    UnityPy = None


PARSER_BEHAVIOR_MAP = {
    0: {
        "parser_behavior": "PARSED_BUT_DROPPED",
        "semantic_hypothesis": "Primary / Display-Title Metadata (Main/Chara/Guild/Sys 多數為序號標籤，Event 可能為 display title)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "HIGH",
        "currently_persisted": False,
        "product_value": "話數標題與序號展示"
    },
    1: {
        "parser_behavior": "PARSED_BUT_DROPPED",
        "semantic_hypothesis": "官方長篇劇情大綱 (Official Synopsis)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": False,
        "product_value": "📜 官方大綱面板"
    },
    5: {
        "parser_behavior": "PARSED_AND_PERSISTED",
        "semantic_hypothesis": "背景設定／切換 (Background Transition)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": True,
        "product_value": "劇情場景即時背景圖渲染"
    },
    6: {
        "parser_behavior": "PARSED_AND_PERSISTED",
        "semantic_hypothesis": "對白文本與說話者 (Dialogue Text & Speaker)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": True,
        "product_value": "劇情全文對話主體"
    },
    12: {
        "parser_behavior": "PARTIALLY_PARSED",
        "semantic_hypothesis": "語音音檔關聯 (Voice Association，current_voice 暫存並綁定下一個 cmd 6)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": True,
        "product_value": "單句語音播放"
    },
    32: {
        "parser_behavior": "PARSED_BUT_DROPPED",
        "semantic_hypothesis": "官方話數副標題／話名 (Official Episode Subtitle / Episode Name)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": False,
        "product_value": "話名展示"
    },
    46: {
        "parser_behavior": "PARSED_AND_PERSISTED",
        "semantic_hypothesis": "動畫影片切換／播放 (Movie Playback)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": True,
        "product_value": "劇情動畫影片播放"
    },
    49: {
        "parser_behavior": "PARSED_AND_PERSISTED",
        "semantic_hypothesis": "CG 插畫切換／結束 (Still Display / End)",
        "semantic_status": "CONFIRMED",
        "semantic_confidence": "VERY HIGH",
        "currently_persisted": True,
        "product_value": "劇情插畫 CG 渲染"
    }
}


def get_story_category(story_id: int) -> str:
    """依照 ID 區段判定故事類型"""
    sid = int(story_id)
    if 1000000 <= sid < 2000000:
        return "Chara"
    elif 2000000 <= sid < 3000000:
        return "Main"
    elif 3000000 <= sid < 4000000:
        return "Guild"
    elif 5000000 <= sid < 6000000:
        return "Event"
    elif 4000000 <= sid < 5000000 or 9000000 <= sid:
        return "System"
    return "Other"


def load_stratified_candidates(db_path: Path, manifest_ids: Set[int]) -> Dict[str, List[int]]:
    """從本地資料庫讀取各類型故事，並篩選在 manifest 中存在者"""
    candidates = defaultdict(list)
    if not db_path.exists():
        raise FileNotFoundError(f"找不到資料庫: {db_path}")

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT story_id FROM story_detail ORDER BY story_id ASC")
    for (sid,) in c.fetchall():
        if sid in manifest_ids:
            cat = get_story_category(sid)
            candidates[cat].append(sid)

    c.execute("SELECT story_id FROM event_story_detail ORDER BY story_id ASC")
    for (sid,) in c.fetchall():
        if sid in manifest_ids:
            candidates["Event"].append(sid)

    conn.close()
    return candidates


def pick_stratified_samples(candidates: Dict[str, List[int]], count_per_category: int = 20) -> List[Tuple[int, str, str]]:
    """
    分層均勻抽樣：每類按 Early / Mid / Late 均勻提取
    回傳清單: [(story_id, category, 'stratified')]
    """
    picked = []
    categories = ["Main", "Chara", "Guild", "Event", "System"]
    for cat in categories:
        ids = sorted(list(set(candidates.get(cat, []))))
        n = len(ids)
        if n == 0:
            continue
        if n <= count_per_category:
            for sid in ids:
                picked.append((sid, cat, "stratified"))
            continue

        early_target = count_per_category // 3
        mid_target = count_per_category // 3
        late_target = count_per_category - early_target - mid_target

        chunk_size = n // 3
        early_pool = ids[:chunk_size]
        mid_pool = ids[chunk_size: 2 * chunk_size]
        late_pool = ids[2 * chunk_size:]

        step_e = max(1, len(early_pool) // early_target)
        for i in range(0, len(early_pool), step_e):
            if len([x for x in picked if x[1] == cat and x[0] in early_pool]) < early_target:
                picked.append((early_pool[i], cat, "stratified"))

        step_m = max(1, len(mid_pool) // mid_target)
        for i in range(0, len(mid_pool), step_m):
            if len([x for x in picked if x[1] == cat and x[0] in mid_pool]) < mid_target:
                picked.append((mid_pool[i], cat, "stratified"))

        step_l = max(1, len(late_pool) // late_target)
        for i in range(0, len(late_pool), step_l):
            if len([x for x in picked if x[1] == cat and x[0] in late_pool]) < late_target:
                picked.append((late_pool[i], cat, "stratified"))

    return picked


def pick_rich_media_samples(project_root: Path, manifest_ids: Set[int], exclude_ids: Set[int], target_count: int = 25) -> List[Tuple[int, str, str]]:
    """
    從本地已有的 story JSON 中，挑選演出元素豐富的劇本：
    優先挑選含 movie, 含有多個 still, 多背景切換, 或高語音數的話數
    """
    story_dir = project_root / "dashboard" / "story"
    if not story_dir.exists():
        return []

    scored_stories = []
    for json_file in story_dir.glob("*.json"):
        if not json_file.stem.isdigit():
            continue
        sid = int(json_file.stem)
        if sid in exclude_ids or sid not in manifest_ids:
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                continue
            movie_count = sum(1 for d in data if d.get("type") == "movie")
            still_count = sum(1 for d in data if d.get("type") == "still" and d.get("still") != "end")
            bg_count = sum(1 for d in data if d.get("type") == "background")
            voice_count = sum(1 for d in data if d.get("voice"))

            score = (movie_count * 100) + (still_count * 20) + (bg_count * 5) + min(50, voice_count // 5)
            if score > 20:
                scored_stories.append((score, sid, get_story_category(sid)))
        except Exception:
            continue

    scored_stories.sort(key=lambda x: x[0], reverse=True)
    picked = []
    for score, sid, cat in scored_stories[:target_count]:
        picked.append((sid, cat, "rich_media"))
    return picked


def pick_adaptive_batch(candidates: Dict[str, List[int]], exclude_ids: Set[int], count: int = 50) -> List[Tuple[int, str, str]]:
    """自適應追加批次：均勻自五大類別挑選尚未被掃描的故事"""
    categories = ["Main", "Chara", "Guild", "Event", "System"]
    per_cat = count // len(categories)
    picked = []
    for cat in categories:
        avail = [sid for sid in candidates.get(cat, []) if sid not in exclude_ids]
        if not avail:
            continue
        step = max(1, len(avail) // per_cat)
        cnt = 0
        for i in range(0, len(avail), step):
            picked.append((avail[i], cat, "adaptive"))
            cnt += 1
            if cnt >= per_cat:
                break
    return picked


def download_and_parse_bundle(bundle_url: str) -> Tuple[str, Optional[List[Tuple[int, List[Any]]]]]:
    """下載並反序列化 Bundle，回傳 (status, commands)"""
    try:
        req = urllib.request.Request(bundle_url, headers=WEB_HEADER)
        with urllib.request.urlopen(req, timeout=20) as res:
            data = res.read()
    except Exception as e:
        return f"NETWORK_ERROR: {e}", None

    if UnityPy is None:
        return "PARSE_ERROR: UnityPy not installed", None

    try:
        bundle = UnityPy.load(data)
        for obj in bundle.objects:
            if obj.type.name == "TextAsset":
                tdata = obj.read()
                script = getattr(tdata, "script", None) or getattr(tdata, "m_Script", None)
                if not script:
                    continue
                if isinstance(script, str):
                    script = bytes(script, "utf-8", "surrogateescape")
                commands = _deserialize_story_raw(script)
                return "PARSE_OK", commands
        return "PARSE_ERROR: No TextAsset found", None
    except Exception as e:
        return f"PARSE_ERROR: {e}", None


def summarize_arg_type(arg: Any) -> str:
    """將參數轉換為簡短型態描述"""
    if isinstance(arg, bool):
        return "bool"
    elif isinstance(arg, int):
        return "int"
    elif isinstance(arg, float):
        return "float"
    elif isinstance(arg, str):
        if arg.isdigit():
            return "digit_str"
        return "str"
    return type(arg).__name__


def sanitize_sample_value(arg: Any, max_len: int = 100) -> Any:
    """短樣本截斷，防止記憶體或輸出過度膨脹"""
    if isinstance(arg, str):
        s = arg.strip().replace("\n", " ")
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    return arg


def run_command_census(project_root: Path, output_json: Path, max_limit: int = 250):
    print("=" * 60)
    print("🔍 Story AssetBundle Command Census & Inventory (Research R1)")
    print("=" * 60)

    # 1. 取得 TruthVersion 與 Manifest
    truth_version = _get_sonet_ver()
    print(f"  [CDN] TruthVersion: {truth_version}")
    manifest_map = load_story_manifest_hash_map(truth_version)
    manifest_ids = set(manifest_map.keys())
    print(f"  [Manifest] 解析出 {len(manifest_map):,} 個 Story AssetBundle")

    # 2. 載入資料庫候選集
    db_path = project_root / "dashboard" / "redive_tw.db"
    candidates = load_stratified_candidates(db_path, manifest_ids)
    for cat, items in candidates.items():
        print(f"    - {cat:<7}: 可用 {len(items):,} 話")

    # 3. 初始抽樣：分層 100 話
    stratified_samples = pick_stratified_samples(candidates, count_per_category=20)
    picked_set = set(x[0] for x in stratified_samples)
    print(f"\n  [Sample 1] 分層 100 話抽樣完成: 共 {len(stratified_samples)} 話")

    # 4. 富媒體偏向抽樣：額外 20~30 話
    rich_media_samples = pick_rich_media_samples(project_root, manifest_ids, picked_set, target_count=25)
    for s in rich_media_samples:
        picked_set.add(s[0])
    print(f"  [Sample 2] 富媒體偏向抽樣完成: 共 {len(rich_media_samples)} 話 (累計: {len(picked_set)} 話)")

    full_queue = stratified_samples + rich_media_samples

    # 5. 執行掃描與自適應擴展迴圈
    stats = {
        "PARSE_OK": 0,
        "NETWORK_ERROR": 0,
        "HASH_NOT_FOUND": 0,
        "PARSE_ERROR": 0
    }

    sample_composition = {
        "stratified": defaultdict(int),
        "rich_media": defaultdict(int),
        "adaptive": defaultdict(int),
        "total_by_category": defaultdict(int)
    }

    commands_meta = defaultdict(lambda: {
        "story_count": 0,
        "story_count_by_category": defaultdict(int),
        "occurrence_count": 0,
        "occurrence_count_by_category": defaultdict(int),
        "arg_count_min": float("inf"),
        "arg_count_max": 0,
        "arg_patterns": set(),
        "sample_args": [],
        "first_positions": [],
        "last_positions": [],
        "neighbor_contexts": [],
        "stories": []
    })

    known_command_ids: Set[int] = set()
    last_new_cmd_sample_index = 0
    processed_count = 0

    idx = 0
    while idx < len(full_queue):
        sid, cat, sample_type = full_queue[idx]
        idx += 1
        processed_count += 1

        sample_composition[sample_type][cat] += 1
        sample_composition["total_by_category"][cat] += 1

        h = manifest_map.get(sid)
        if not h:
            stats["HASH_NOT_FOUND"] += 1
            continue

        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        status, commands = download_and_parse_bundle(bundle_url)

        if not status.startswith("PARSE_OK") or commands is None:
            if "NETWORK_ERROR" in status:
                stats["NETWORK_ERROR"] += 1
            else:
                stats["PARSE_ERROR"] += 1
            print(f"  [{processed_count:03d}] Story {sid} ({cat}): {status}")
            continue

        stats["PARSE_OK"] += 1
        new_cmds_in_this_story = set()
        story_cmd_seq = [c[0] for c in commands]
        unique_cmds_in_story = set(story_cmd_seq)

        for cmd in unique_cmds_in_story:
            if cmd not in known_command_ids:
                known_command_ids.add(cmd)
                new_cmds_in_this_story.add(cmd)
                last_new_cmd_sample_index = processed_count

        # 記錄位置與詳細 command 數據
        first_pos_in_story = {}
        last_pos_in_story = {}
        for pos, (cmd_id, args) in enumerate(commands):
            if cmd_id not in first_pos_in_story:
                first_pos_in_story[cmd_id] = pos
            last_pos_in_story[cmd_id] = pos

            c_entry = commands_meta[cmd_id]
            c_entry["occurrence_count"] += 1
            c_entry["occurrence_count_by_category"][cat] += 1

            arg_len = len(args)
            if arg_len < c_entry["arg_count_min"]:
                c_entry["arg_count_min"] = arg_len
            if arg_len > c_entry["arg_count_max"]:
                c_entry["arg_count_max"] = arg_len

            pattern = tuple(summarize_arg_type(a) for a in args)
            c_entry["arg_patterns"].add(pattern)

            if len(c_entry["sample_args"]) < 3:
                sanitized = [sanitize_sample_value(a) for a in args]
                if sanitized not in c_entry["sample_args"]:
                    c_entry["sample_args"].append(sanitized)

            if len(c_entry["neighbor_contexts"]) < 5:
                prev_ctx = story_cmd_seq[max(0, pos - 3): pos]
                next_ctx = story_cmd_seq[pos + 1: min(len(story_cmd_seq), pos + 4)]
                ctx_item = {
                    "story_id": sid,
                    "category": cat,
                    "prev": prev_ctx,
                    "next": next_ctx,
                    "args": [sanitize_sample_value(a) for a in args]
                }
                c_entry["neighbor_contexts"].append(ctx_item)

        for cmd_id in unique_cmds_in_story:
            c_entry = commands_meta[cmd_id]
            c_entry["story_count"] += 1
            c_entry["story_count_by_category"][cat] += 1
            if len(c_entry["stories"]) < 10:
                c_entry["stories"].append(sid)

            if len(c_entry["first_positions"]) < 5 and cmd_id in first_pos_in_story:
                fpos = first_pos_in_story[cmd_id]
                c_entry["first_positions"].append({
                    "story_id": sid,
                    "category": cat,
                    "index": fpos,
                    "total": len(commands),
                    "ratio": round(fpos / max(1, len(commands)), 4)
                })
            if len(c_entry["last_positions"]) < 5 and cmd_id in last_pos_in_story:
                lpos = last_pos_in_story[cmd_id]
                c_entry["last_positions"].append({
                    "story_id": sid,
                    "category": cat,
                    "index": lpos,
                    "total": len(commands),
                    "ratio": round(lpos / max(1, len(commands)), 4)
                })

        new_info = f" -> NEW COMMANDS: {sorted(list(new_cmds_in_this_story))}" if new_cmds_in_this_story else ""
        if processed_count % 10 == 0 or new_cmds_in_this_story or processed_count == len(full_queue):
            print(f"  [{processed_count:03d}/{len(full_queue):03d}] Story {sid:<7} ({cat:<7}, {sample_type:<10}) | {len(commands)} cmds, {len(unique_cmds_in_story)} unique (Total Known: {len(known_command_ids)}){new_info}")

        if idx == len(full_queue) and len(full_queue) < max_limit:
            if processed_count - last_new_cmd_sample_index < 50:
                needed = min(max_limit - len(full_queue), 50 - (processed_count - last_new_cmd_sample_index) + 5)
                extra_batch = pick_adaptive_batch(candidates, picked_set, count=max(10, needed))
                if extra_batch:
                    print(f"\n  ⚠️ 距最後新指令僅 {processed_count - last_new_cmd_sample_index} 話 (未達 50 話飽和門檻)！追加 {len(extra_batch)} 話驗證收斂...")
                    for s in extra_batch:
                        picked_set.add(s[0])
                    full_queue.extend(extra_batch)

    saturation_reached = (processed_count - last_new_cmd_sample_index >= 50) or (processed_count >= max_limit)
    print("\n" + "=" * 60)
    print("📊 掃描完成統計 (Census Summary)")
    print("=" * 60)
    print(f"  總計處理故事數: {processed_count}")
    print(f"  狀態分佈: {stats}")
    print(f"  共發現獨立 Command IDs: {len(known_command_ids)} 個: {sorted(list(known_command_ids))}")
    print(f"  最後發現新 Command 於第 {last_new_cmd_sample_index} 話 (距今已連續 {processed_count - last_new_cmd_sample_index} 話無新指令)")
    print(f"  飽和收斂狀態 (Saturation Reached): {saturation_reached}")

    output_data = {
        "truth_version": truth_version,
        "stories_scanned": processed_count,
        "status_distribution": stats,
        "observed_command_count": len(known_command_ids),
        "observed_min_command_id": min(known_command_ids) if known_command_ids else 0,
        "observed_max_command_id": max(known_command_ids) if known_command_ids else 0,
        "observed_command_ids": sorted(list(known_command_ids)),
        "sample_composition": {
            "stratified": dict(sample_composition["stratified"]),
            "rich_media": dict(sample_composition["rich_media"]),
            "adaptive": dict(sample_composition["adaptive"]),
            "total_by_category": dict(sample_composition["total_by_category"])
        },
        "last_new_cmd_sample_index": last_new_cmd_sample_index,
        "samples_since_last_new_cmd": processed_count - last_new_cmd_sample_index,
        "saturation_reached": saturation_reached,
        "commands": {}
    }

    for cmd_id in sorted(list(known_command_ids)):
        c_entry = commands_meta[cmd_id]
        p_info = PARSER_BEHAVIOR_MAP.get(cmd_id, {
            "parser_behavior": "IGNORED",
            "semantic_hypothesis": "未知演出控制 (待後續 R2 驗證)",
            "semantic_status": "UNKNOWN",
            "semantic_confidence": "UNKNOWN",
            "currently_persisted": False,
            "product_value": "待調研"
        })

        output_data["commands"][str(cmd_id)] = {
            "command_id": cmd_id,
            "parser_behavior": p_info["parser_behavior"],
            "semantic_hypothesis": p_info["semantic_hypothesis"],
            "semantic_status": p_info["semantic_status"],
            "semantic_confidence": p_info["semantic_confidence"],
            "currently_persisted": p_info["currently_persisted"],
            "product_value": p_info["product_value"],
            "story_count": c_entry["story_count"],
            "story_count_by_category": dict(c_entry["story_count_by_category"]),
            "occurrence_count": c_entry["occurrence_count"],
            "occurrence_count_by_category": dict(c_entry["occurrence_count_by_category"]),
            "arg_count_min": 0 if c_entry["arg_count_min"] == float("inf") else c_entry["arg_count_min"],
            "arg_count_max": c_entry["arg_count_max"],
            "arg_patterns": [list(p) for p in c_entry["arg_patterns"]],
            "sample_args": c_entry["sample_args"],
            "first_positions": c_entry["first_positions"],
            "last_positions": c_entry["last_positions"],
            "neighbor_contexts": c_entry["neighbor_contexts"],
            "sample_stories": c_entry["stories"]
        }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 結果已寫入純本機 scratch: {output_json}")
    return output_data


def main():
    parser = argparse.ArgumentParser(description="Story AssetBundle Command Census & Inventory (Research R1)")
    parser.add_argument("--output", type=str, default=str(PROJECT_ROOT / "scratch" / "story_command_inventory.json"),
                        help="輸出 JSON 路徑 (預設: scratch/story_command_inventory.json)")
    parser.add_argument("--limit", type=int, default=250,
                        help="最大抽樣話數上限 (預設: 250)")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    run_command_census(PROJECT_ROOT, output_path, max_limit=args.limit)


if __name__ == "__main__":
    main()
