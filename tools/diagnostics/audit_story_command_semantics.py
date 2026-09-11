#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_story_command_semantics.py

專案: PCRD Story Map (PCRD_transtool)
功能: 深度驗證 Story AssetBundle 高價值指令語意 (Issue #2 Research R2)
約束: 嚴格唯讀 (Strictly Read-Only)。只輸出結果至 scratch/，嚴禁修改任何正式目錄或資料庫。
"""

import os
import sys
import json
import sqlite3
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict, Counter

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

from tools.diagnostics.audit_story_command_inventory import (
    load_stratified_candidates,
    pick_stratified_samples,
    pick_rich_media_samples,
    pick_adaptive_batch,
    get_story_category,
)


def download_and_parse_bundle_cached(
    sid: int,
    manifest_map: Dict[int, str],
    cache_dir: Optional[Path] = None
) -> Tuple[str, Optional[List[Tuple[int, List[Any]]]]]:
    """
    下載並反序列化 Bundle，支援可選本地快取以加速分析並避免重複網路請求
    """
    h = manifest_map.get(sid)
    if not h:
        return "HASH_NOT_FOUND", None

    bundle_bytes = None
    cache_file = None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{sid}_{h[:10]}.bundle"
        if cache_file.exists():
            try:
                bundle_bytes = cache_file.read_bytes()
            except Exception:
                bundle_bytes = None

    if bundle_bytes is None:
        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        try:
            req = urllib.request.Request(bundle_url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=20) as res:
                bundle_bytes = res.read()
            if cache_file:
                cache_file.write_bytes(bundle_bytes)
        except Exception as e:
            return f"NETWORK_ERROR: {e}", None

    if UnityPy is None:
        return "PARSE_ERROR: UnityPy not installed", None

    try:
        bundle = UnityPy.load(bundle_bytes)
        for obj in bundle.objects:
            if obj.type.name == "TextAsset":
                script_bytes = None
                try:
                    raw = obj.get_raw_data()
                    if raw and len(raw) > 8:
                        import struct
                        name_len = struct.unpack("<I", raw[:4])[0]
                        offset = 4 + name_len
                        if offset % 4 != 0:
                            offset += 4 - (offset % 4)
                        if offset + 4 <= len(raw):
                            script_len = struct.unpack("<I", raw[offset:offset + 4])[0]
                            offset += 4
                            if offset + script_len <= len(raw):
                                script_bytes = raw[offset:offset + script_len]
                except Exception:
                    script_bytes = None

                if script_bytes is None:
                    tdata = obj.read()
                    script = getattr(tdata, "script", None) or getattr(tdata, "m_Script", None)
                    if not script:
                        continue
                    if isinstance(script, str):
                        script = bytes(script, "utf-8", "surrogateescape")
                    script_bytes = script

                commands = _deserialize_story_raw(script_bytes)
                return "PARSE_OK", commands
        return "PARSE_ERROR: No TextAsset found", None
    except Exception as e:
        return f"PARSE_ERROR: {e}", None


def analyze_prefix_inversion(commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]]) -> Dict[str, Any]:
    """
    1. 資源前綴反轉分析 (Resource-Prefix Inversion Analysis)
    掃描參數中的資源字串，反向統計特定前綴對應到的 Command IDs
    """
    prefix_to_cmds = defaultdict(lambda: defaultdict(int))
    cmd_to_prefixes = defaultdict(lambda: defaultdict(int))
    sample_values_by_prefix = defaultdict(list)

    known_prefixes = ["bgm_", "se_", "amb_", "vo_"]

    for sid, cmds in commands_pool:
        for cid, args in cmds:
            for a in args:
                if not isinstance(a, str):
                    continue
                matched_pfx = None
                for pfx in known_prefixes:
                    if a.startswith(pfx):
                        matched_pfx = pfx
                        break
                if matched_pfx:
                    prefix_to_cmds[matched_pfx][cid] += 1
                    cmd_to_prefixes[cid][matched_pfx] += 1
                    if len(sample_values_by_prefix[matched_pfx]) < 5 and a not in sample_values_by_prefix[matched_pfx]:
                        sample_values_by_prefix[matched_pfx].append(a)

    result = {
        "prefix_to_commands": {},
        "command_to_prefixes": {},
        "prefix_samples": dict(sample_values_by_prefix),
    }

    for pfx, cdict in prefix_to_cmds.items():
        result["prefix_to_commands"][pfx] = [
            {"command_id": cid, "count": cnt} for cid, cnt in sorted(cdict.items(), key=lambda x: x[1], reverse=True)
        ]

    for cid, pdict in cmd_to_prefixes.items():
        result["command_to_prefixes"][str(cid)] = dict(pdict)

    return result


def analyze_sequence_contexts(
    commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]],
    target_cids: List[int]
) -> Dict[str, Any]:
    """
    2. 上下文序列分析 (Sequence Context & N-Gram Analysis)
    分析目標指令的 Top Prev, Top Next, 及 Top 3-gram
    """
    prev_counts = defaultdict(Counter)
    next_counts = defaultdict(Counter)
    trigram_counts = defaultdict(Counter)
    total_counts = defaultdict(int)

    target_set = set(target_cids)

    for sid, cmds in commands_pool:
        n = len(cmds)
        for i in range(n):
            cid = cmds[i][0]
            if cid in target_set:
                total_counts[cid] += 1
                prev_cid = cmds[i - 1][0] if i > 0 else -1
                next_cid = cmds[i + 1][0] if i + 1 < n else -1

                prev_counts[cid][prev_cid] += 1
                next_counts[cid][next_cid] += 1

                # 3-gram: (i-1, i, i+1)
                trigram = (prev_cid, cid, next_cid)
                trigram_counts[cid][trigram] += 1

    results = {}
    for cid in target_cids:
        tot = total_counts[cid]
        top_prev = [
            {"prev_cid": pc, "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0}
            for pc, cnt in prev_counts[cid].most_common(5)
        ]
        top_next = [
            {"next_cid": nc, "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0}
            for nc, cnt in next_counts[cid].most_common(5)
        ]
        top_trigrams = [
            {"trigram": f"{tg[0]} -> {tg[1]} -> {tg[2]}", "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0}
            for tg, cnt in trigram_counts[cid].most_common(5)
        ]

        results[str(cid)] = {
            "total_occurrences": tot,
            "top_previous": top_prev,
            "top_next": top_next,
            "top_trigrams": top_trigrams,
        }

    return results


def analyze_timing_and_voice(
    commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]],
    sound_dir: Path,
    ffprobe_path: str = r"C:\FFmpeg\bin\ffprobe.exe",
    max_voice_align_samples: int = 150
) -> Dict[str, Any]:
    """
    3. 時序指令數值分佈與語音時長實測對齊 (Timing vs Voice Duration Correlation)
    """
    values_by_cmd = defaultdict(list)
    for sid, cmds in commands_pool:
        for cid, args in cmds:
            if cid in [13, 27, 61]:
                for a in args:
                    try:
                        v = float(a)
                        values_by_cmd[cid].append(v)
                    except ValueError:
                        pass

    timing_distribution = {}
    for cid in [13, 27, 61]:
        vals = values_by_cmd[cid]
        if vals:
            sorted_vals = sorted(vals)
            n = len(vals)
            counter = Counter(vals)
            timing_distribution[str(cid)] = {
                "count": n,
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "mean": round(sum(vals) / n, 2),
                "median": sorted_vals[n // 2],
                "p25": sorted_vals[int(n * 0.25)],
                "p75": sorted_vals[int(n * 0.75)],
                "top_discrete_values": [
                    {"value": val, "count": cnt, "ratio": round(cnt / n, 4)}
                    for val, cnt in counter.most_common(8)
                ]
            }
        else:
            timing_distribution[str(cid)] = {"count": 0}

    voice_alignments = []
    has_ffprobe = Path(ffprobe_path).exists()

    if has_ffprobe and sound_dir.exists():
        for sid, cmds in commands_pool:
            if len(voice_alignments) >= max_voice_align_samples:
                break

            curr_voice = None
            curr_cmd13 = []
            for cid, args in cmds:
                if cid == 12:
                    if curr_voice:
                        m4a_path = sound_dir / f"{curr_voice}.m4a"
                        if m4a_path.exists():
                            try:
                                probe_cmd = [
                                    ffprobe_path, "-v", "error",
                                    "-show_entries", "format=duration",
                                    "-of", "json", str(m4a_path)
                                ]
                                res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                                dur = float(json.loads(res.stdout)["format"]["duration"])
                                voice_alignments.append({
                                    "voice_id": curr_voice,
                                    "story_id": sid,
                                    "actual_duration_sec": round(dur, 3),
                                    "cmd13_count": len(curr_cmd13),
                                    "cmd13_sum": sum(curr_cmd13),
                                    "cmd13_first": curr_cmd13[0] if curr_cmd13 else 0,
                                    "cmd13_list": curr_cmd13
                                })
                                if len(voice_alignments) >= max_voice_align_samples:
                                    break
                            except Exception:
                                pass
                    curr_voice = args[0] if args else None
                    curr_cmd13 = []
                elif cid == 13:
                    if curr_voice and args:
                        try:
                            curr_cmd13.append(float(args[0]))
                        except ValueError:
                            pass

    correlation_sum = 0.0
    correlation_first = 0.0
    if len(voice_alignments) >= 10:
        durs = [x["actual_duration_sec"] for x in voice_alignments]
        sums = [x["cmd13_sum"] for x in voice_alignments]
        firsts = [x["cmd13_first"] for x in voice_alignments]

        def calc_pearson(x: List[float], y: List[float]) -> float:
            n = len(x)
            mx = sum(x) / n
            my = sum(y) / n
            var_x = sum((xi - mx) ** 2 for xi in x)
            var_y = sum((yi - my) ** 2 for yi in y)
            if var_x == 0 or var_y == 0:
                return 0.0
            cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
            return round(cov / ((var_x ** 0.5) * (var_y ** 0.5)), 4)

        correlation_sum = calc_pearson(durs, sums)
        correlation_first = calc_pearson(durs, firsts)

    return {
        "timing_distribution": timing_distribution,
        "voice_alignment_sample_count": len(voice_alignments),
        "pearson_r_duration_vs_cmd13_sum": correlation_sum,
        "pearson_r_duration_vs_cmd13_first": correlation_first,
        "sample_alignments": voice_alignments[:10]
    }


def extract_location_command_data(commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]]) -> Dict[str, Any]:
    """
    4. 地點／場景橫幅驗證 (cmd 100 Location Display Validation)
    提取所有 cmd 100 的文字參數並檢查語意一致性
    """
    occurrences = []
    for sid, cmds in commands_pool:
        cat = get_story_category(sid)
        for idx, (cid, args) in enumerate(cmds):
            if cid == 100:
                loc_text = args[0] if args else ""
                occurrences.append({
                    "story_id": sid,
                    "category": cat,
                    "stream_index": idx,
                    "location_text": loc_text,
                    "raw_args": args
                })

    unique_locations = sorted(list(set(x["location_text"] for x in occurrences)))
    return {
        "total_occurrences": len(occurrences),
        "unique_location_count": len(unique_locations),
        "unique_locations": unique_locations,
        "occurrences": occurrences
    }


def analyze_interactive_choices(commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]]) -> Dict[str, Any]:
    """
    5. 分歧選項驗證 (cmd 11 Interactive Choice Validation)
    """
    choice_occurrences = []
    for sid, cmds in commands_pool:
        cat = get_story_category(sid)
        for idx, (cid, args) in enumerate(cmds):
            if cid == 11:
                text = args[0] if len(args) > 0 else ""
                target_label = args[1] if len(args) > 1 else ""
                choice_occurrences.append({
                    "story_id": sid,
                    "category": cat,
                    "stream_index": idx,
                    "choice_text": text,
                    "target_branch_label": target_label,
                    "raw_args": args
                })

    return {
        "total_choice_count": len(choice_occurrences),
        "sample_choices": choice_occurrences[:15]
    }


def run_semantics_audit(
    project_root: Path,
    output_json: Path,
    cache_dir: Optional[Path] = None,
    max_samples: int = 180
):
    print("=" * 60)
    print("🔬 Story AssetBundle Command Semantics Audit (Research R2)")
    print("=" * 60)

    # 1. 取得 TruthVersion 與 Manifest
    truth_version = _get_sonet_ver()
    print(f"  [CDN] TruthVersion: {truth_version}")
    manifest_map = load_story_manifest_hash_map(truth_version)
    manifest_ids = set(manifest_map.keys())
    print(f"  [Manifest] 解析出 {len(manifest_map):,} 個 Story AssetBundle")

    # 2. 依 R1 確定性分層抽樣重現 180 話名單
    db_path = project_root / "dashboard" / "redive_tw.db"
    candidates = load_stratified_candidates(db_path, manifest_ids)

    stratified_samples = pick_stratified_samples(candidates, count_per_category=20)
    picked_set = set(x[0] for x in stratified_samples)
    rich_media_samples = pick_rich_media_samples(project_root, manifest_ids, picked_set, target_count=25)
    for s in rich_media_samples:
        picked_set.add(s[0])

    batch_1 = pick_adaptive_batch(candidates, picked_set, count=50)
    for s in batch_1:
        picked_set.add(s[0])

    batch_2 = pick_adaptive_batch(candidates, picked_set, count=5)
    for s in batch_2:
        picked_set.add(s[0])

    full_queue = (stratified_samples + rich_media_samples + batch_1 + batch_2)[:max_samples]
    print(f"  [Queue] 確定性重現 {len(full_queue)} 話抽樣隊列")

    # 3. 載入與反序列化所有抽樣話數
    commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]] = []
    print("\n  [Parse] 開始載入並解析抽樣 Bundle...")
    for idx, (sid, cat, stype) in enumerate(full_queue, 1):
        status, cmds = download_and_parse_bundle_cached(sid, manifest_map, cache_dir)
        if status == "PARSE_OK" and cmds:
            commands_pool.append((sid, cmds))
        if idx % 30 == 0 or idx == len(full_queue):
            print(f"    - 進度: {idx}/{len(full_queue)} 話完成 (有效解析: {len(commands_pool)} 話)")

    # 4. 各模組分析
    print("\n  [Analysis 1] 執行資源前綴反轉分析 (Resource-Prefix Inversion)...")
    prefix_results = analyze_prefix_inversion(commands_pool)

    print("  [Analysis 2] 執行高價值指令上下文序列分析 (N-Gram & Transitions)...")
    target_cids = [
        # Group A
        101, 103, 26, 67, 51,
        # Group B
        13, 27, 61,
        # Group C
        3, 4, 50, 59, 68,
        # Group D
        29, 70, 86, 87, 88,
        # Group E & F
        100, 11, 31
    ]
    sequence_results = analyze_sequence_contexts(commands_pool, target_cids)

    print("  [Analysis 3] 執行時序指令數值分佈與 ffprobe 語音長度實測對齊...")
    sound_dir = project_root / "dashboard" / "sound" / "story_vo"
    ffprobe_path = r"C:\FFmpeg\bin\ffprobe.exe"
    timing_results = analyze_timing_and_voice(commands_pool, sound_dir, ffprobe_path)

    print("  [Analysis 4] 提取全部 cmd 100 地點文字...")
    location_results = extract_location_command_data(commands_pool)

    print("  [Analysis 5] 提取分歧選項 (cmd 11)...")
    choice_results = analyze_interactive_choices(commands_pool)

    # 5. 彙總結構化結果
    report_data = {
        "truth_version": truth_version,
        "sample_count": len(commands_pool),
        "resource_prefix_inversion": prefix_results,
        "sequence_contexts": sequence_results,
        "timing_and_voice_correlation": timing_results,
        "location_validation": location_results,
        "choice_validation": choice_results,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n  [Output] 結構化診斷報告已寫入: {output_json}")
    print("=" * 60)
    print("✅ R2 語意驗證執行完畢。")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="PCRD Story AssetBundle 高價值指令語意驗證工具 (Research R2)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "scratch" / "story_command_semantics_r2.json",
        help="診斷結果輸出 JSON 路徑 (預設: scratch/story_command_semantics_r2.json)"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=PROJECT_ROOT / "scratch" / "story_bundles_cache",
        help="Bundle 本地暫存快取目錄 (預設: scratch/story_bundles_cache)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=180,
        help="掃描抽樣話數上限 (預設: 180，完全對齊 R1 抽樣集)"
    )

    args = parser.parse_args()
    run_semantics_audit(
        project_root=PROJECT_ROOT,
        output_json=args.output,
        cache_dir=args.cache_dir,
        max_samples=args.samples
    )


if __name__ == "__main__":
    main()
