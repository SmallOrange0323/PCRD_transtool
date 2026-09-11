#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_story_command_semantics.py

專案: PCRD Story Map (PCRD_transtool)
功能: 深度驗證 Story AssetBundle 高價值指令語意 (Issue #2 Research R2)
約束: Production/source read-only. Writes are permitted only under scratch/.
      嚴格遵守 Evidence-Calibrated Research Mode 規範。
"""

import os
import sys
import json
import shutil
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


def resolve_ffprobe_path(cli_path: Optional[str] = None) -> Optional[str]:
    """
    可重現的 ffprobe 探索機制：
    1. CLI 指定參數 --ffprobe
    2. shutil.which("ffprobe") 系統 PATH 尋找
    3. Windows 常見安裝路徑 fallback
    """
    if cli_path and Path(cli_path).exists():
        return str(Path(cli_path).resolve())
    system_which = shutil.which("ffprobe")
    if system_which:
        return system_which
    windows_fallback = r"C:\FFmpeg\bin\ffprobe.exe"
    if Path(windows_fallback).exists():
        return windows_fallback
    return None


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
    掃描參數中的資源字串，反向統計特定前綴對應到的 Command IDs，
    並由 script 自動計算 prefix_total 與 ratio_of_prefix，包含嚴格 invariant 檢驗。
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

    prefix_summary = {}
    for pfx in known_prefixes:
        cdict = prefix_to_cmds.get(pfx, {})
        prefix_total = sum(cdict.values())
        cmd_list = []
        for cid, cnt in sorted(cdict.items(), key=lambda x: x[1], reverse=True):
            ratio = round(cnt / prefix_total, 4) if prefix_total > 0 else 0.0
            cmd_list.append({
                "command_id": cid,
                "count": cnt,
                "ratio_of_prefix": ratio
            })

        # Invariant / Consistency Checks
        if prefix_total > 0:
            count_sum = sum(x["count"] for x in cmd_list)
            ratio_sum = sum(x["ratio_of_prefix"] for x in cmd_list)
            assert count_sum == prefix_total, f"Invariant violation: {pfx} count sum {count_sum} != {prefix_total}"
            assert abs(ratio_sum - 1.0) <= 0.005, f"Invariant violation: {pfx} ratio sum {ratio_sum} != 1.0"

        prefix_summary[pfx] = {
            "prefix_total": prefix_total,
            "commands": cmd_list
        }

    result = {
        "prefix_summary": prefix_summary,
        "command_to_prefixes": {str(cid): dict(pdict) for cid, pdict in cmd_to_prefixes.items()},
        "prefix_samples": dict(sample_values_by_prefix),
    }

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

                trigram = (prev_cid, cid, next_cid)
                trigram_counts[cid][trigram] += 1

    results = {}
    for cid in target_cids:
        tot = total_counts[cid]
        top_prev = [
            {"prev_cid": pc, "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0.0}
            for pc, cnt in prev_counts[cid].most_common(5)
        ]
        top_next = [
            {"next_cid": nc, "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0.0}
            for nc, cnt in next_counts[cid].most_common(5)
        ]
        top_trigrams = [
            {"trigram": f"{tg[0]} -> {tg[1]} -> {tg[2]}", "count": cnt, "ratio": round(cnt / tot, 4) if tot > 0 else 0.0}
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
    ffprobe_path: Optional[str] = None,
    max_alignment_samples: int = 150
) -> Dict[str, Any]:
    """
    3. 時序指令數值分佈與語音時長實測對齊 (Timing vs Voice Duration Correlation)
    以邊界終止符明確分割 Voice Turn Window，修正 EOF finalization，並保存全部成功對齊之完整 provenance。
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

    # 語音長度對齊實測
    resolved_ffprobe = resolve_ffprobe_path(ffprobe_path)
    ffprobe_available = (resolved_ffprobe is not None and Path(resolved_ffprobe).exists())

    voice_turn_candidates = 0
    local_audio_present = 0
    local_audio_missing = 0
    probe_attempted = 0
    probe_success = 0
    probe_failed = 0

    voice_alignments = []
    boundary_cids = {12, 7, 11, 5, 27, 46, 49}

    for sid, cmds in commands_pool:
        active_turn: Optional[Dict[str, Any]] = None

        def finalize_turn(turn: Dict[str, Any], end_idx: int):
            nonlocal voice_turn_candidates, local_audio_present, local_audio_missing
            nonlocal probe_attempted, probe_success, probe_failed

            voice_turn_candidates += 1
            vname = turn["voice_id"]
            m4a_path = sound_dir / f"{vname}.m4a"

            if not m4a_path.exists():
                local_audio_missing += 1
                return

            local_audio_present += 1

            if len(voice_alignments) >= max_alignment_samples or not ffprobe_available:
                return

            probe_attempted += 1
            try:
                probe_cmd = [
                    resolved_ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json", str(m4a_path)
                ]
                res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                dur = float(json.loads(res.stdout)["format"]["duration"])
                probe_success += 1
                voice_alignments.append({
                    "story_id": sid,
                    "voice_id": vname,
                    "voice_command_index": turn["voice_cmd_idx"],
                    "segmentation_end_index": end_idx,
                    "included_cmd13_indices": list(turn["cmd13_indices"]),
                    "included_cmd13_values": list(turn["cmd13_values"]),
                    "cmd13_count": len(turn["cmd13_values"]),
                    "cmd13_sum": sum(turn["cmd13_values"]),
                    "cmd13_first": turn["cmd13_values"][0] if turn["cmd13_values"] else 0.0,
                    "actual_duration_sec": round(dur, 3)
                })
            except Exception:
                probe_failed += 1

        for idx, (cid, args) in enumerate(cmds):
            if cid in boundary_cids and active_turn:
                finalize_turn(active_turn, idx)
                active_turn = None

            if cid == 12 and args:
                active_turn = {
                    "voice_id": args[0],
                    "voice_cmd_idx": idx,
                    "cmd13_indices": [],
                    "cmd13_values": []
                }
            elif cid == 13 and active_turn and args:
                try:
                    v = float(args[0])
                    active_turn["cmd13_indices"].append(idx)
                    active_turn["cmd13_values"].append(v)
                except ValueError:
                    pass

        # EOF finalization
        if active_turn:
            finalize_turn(active_turn, len(cmds))

    # 判定評估狀態
    if not ffprobe_available:
        evaluation_status = "NOT_EVALUATED"
    elif len(voice_alignments) < 10:
        evaluation_status = "INCONCLUSIVE"
    elif probe_failed > 0:
        evaluation_status = "PARTIAL"
    else:
        evaluation_status = "EVALUATED"

    # 計算統計相關性 (Pearson r)
    correlation_sum = None
    correlation_first = None

    if evaluation_status in ["EVALUATED", "PARTIAL"] and len(voice_alignments) >= 10:
        durs = [x["actual_duration_sec"] for x in voice_alignments]
        sums = [x["cmd13_sum"] for x in voice_alignments]
        firsts = [x["cmd13_first"] for x in voice_alignments]

        def calc_pearson(x: List[float], y: List[float]) -> Optional[float]:
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

    # Invariant: successful_alignment_samples 嚴格等於 len(alignments)
    assert len(voice_alignments) == probe_success, f"Alignment invariant mismatch: {len(voice_alignments)} != {probe_success}"

    return {
        "timing_distribution": timing_distribution,
        "ffprobe_available": ffprobe_available,
        "ffprobe_path_used": resolved_ffprobe,
        "evaluation_status": evaluation_status,
        "max_alignment_samples": max_alignment_samples,
        "voice_turn_candidates": voice_turn_candidates,
        "local_audio_present": local_audio_present,
        "local_audio_missing": local_audio_missing,
        "probe_attempted": probe_attempted,
        "probe_success": probe_success,
        "probe_failed": probe_failed,
        "successful_alignment_samples": len(voice_alignments),
        "correlation_sample_count": len(voice_alignments),
        "pearson_r_duration_vs_cmd13_sum": correlation_sum,
        "pearson_r_duration_vs_cmd13_first": correlation_first,
        "alignments": voice_alignments,
        "alignment_preview": voice_alignments[:10]
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
    ffprobe_path: Optional[str] = None,
    max_samples: int = 180,
    max_alignment_samples: int = 150
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
    requested_story_samples = len(full_queue)
    print(f"  [Queue] 確定性重現 {requested_story_samples} 話抽樣隊列")

    # 統計樣品組成
    sample_composition = defaultdict(int)
    for sid, cat, stype in full_queue:
        sample_composition[cat] += 1

    # 3. 載入與反序列化所有抽樣話數，完整記錄 parsing accounting
    commands_pool: List[Tuple[int, List[Tuple[int, List[Any]]]]] = []
    failed_story_parses = 0
    print("\n  [Parse] 開始載入並解析抽樣 Bundle...")
    for idx, (sid, cat, stype) in enumerate(full_queue, 1):
        status, cmds = download_and_parse_bundle_cached(sid, manifest_map, cache_dir)
        if status == "PARSE_OK" and cmds:
            commands_pool.append((sid, cmds))
        else:
            failed_story_parses += 1
        if idx % 30 == 0 or idx == len(full_queue):
            print(f"    - 進度: {idx}/{len(full_queue)} 話完成 (有效解析: {len(commands_pool)} 話)")

    successfully_parsed_stories = len(commands_pool)

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
    timing_results = analyze_timing_and_voice(commands_pool, sound_dir, ffprobe_path, max_alignment_samples)

    print("  [Analysis 4] 提取全部 cmd 100 地點文字...")
    location_results = extract_location_command_data(commands_pool)

    print("  [Analysis 5] 提取分歧選項 (cmd 11)...")
    choice_results = analyze_interactive_choices(commands_pool)

    # 5. 彙總結構化結果
    report_data = {
        "truth_version": truth_version,
        "sample_count": len(commands_pool),
        "parsing_accounting": {
            "requested_story_samples": requested_story_samples,
            "successfully_parsed_stories": successfully_parsed_stories,
            "failed_story_parses": failed_story_parses
        },
        "sample_composition_by_category": dict(sample_composition),
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
        "--ffprobe",
        type=str,
        default=None,
        help="指定 ffprobe 執行檔路徑 (選填，若未指定則自動依序探索 PATH 與 Windows 預設路徑)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=180,
        help="掃描抽樣話數上限 (預設: 180，完全對齊 R1 抽樣集)"
    )
    parser.add_argument(
        "--max-alignment-samples",
        type=int,
        default=150,
        help="語音對齊最大抽樣上限 cap (預設: 150)"
    )

    args = parser.parse_args()
    run_semantics_audit(
        project_root=PROJECT_ROOT,
        output_json=args.output,
        cache_dir=args.cache_dir,
        ffprobe_path=args.ffprobe,
        max_samples=args.samples,
        max_alignment_samples=args.max_alignment_samples
    )


if __name__ == "__main__":
    main()
