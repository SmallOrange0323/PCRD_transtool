#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Gap Voice Deployment & Button UX Unit Tests

驗證項目：
1. Gap Voice 權威清單 (voice_gap_assets.json) 完整性與實體一致性 (236 檔 / 25,051,018 bytes / SHA256 / 非 0-byte)。
2. 白名單映射 (get_expected_gap_voice_mappings / build_expected_gap_voice_set) 正確性。
3. Pruning 行為：多餘的非 gap 音檔安全清理，白名單內的 gap 音檔妥善保留。
4. Dry-run 與部署包體積門禁：預估大小符合預期 (< 650 MiB，綠燈安全標準)。
5. dist_story_map/.gitignore 設定：解除 sound/ 忽略，確保 gap 語音能納入追蹤發布。
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    get_expected_gap_voice_mappings,
    build_expected_gap_voice_set,
    prune_stale_dist_assets,
    calculate_expected_additions_and_deltas,
    get_directory_size,
    VOICE_GAP_ASSETS_PATH,
    DASHBOARD_DIR,
    DIST_DIR
)
from pipeline.validate import check_footprint_gate


class TestVoiceGapPipeline(unittest.TestCase):

    def test_voice_gap_assets_manifest_integrity(self):
        """驗證 voice_gap_assets.json 的結構、數量、大小與哈希完整性"""
        self.assertTrue(VOICE_GAP_ASSETS_PATH.exists(), f"找不到權威清單: {VOICE_GAP_ASSETS_PATH}")
        with open(VOICE_GAP_ASSETS_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("count"), 236)
        self.assertEqual(manifest.get("total_bytes"), 25051018)

        assets = manifest.get("assets", [])
        self.assertEqual(len(assets), 236)

        calc_total_size = 0
        sound_dir = DASHBOARD_DIR / "sound" / "story_vo"
        for item in assets:
            filename = item["filename"]
            self.assertTrue(filename.endswith(".m4a"))
            expected_size = item["size"]
            expected_sha = item["sha256"]
            calc_total_size += expected_size

            local_file = sound_dir / filename
            self.assertTrue(local_file.exists(), f"本地缺失 gap 語音檔: {local_file}")
            actual_size = local_file.stat().st_size
            self.assertEqual(actual_size, expected_size, f"{filename} 大小不符合")
            self.assertGreater(actual_size, 0, f"{filename} 為 0-byte 檔案")

            hasher = hashlib.sha256()
            with open(local_file, "rb") as bf:
                for chunk in iter(lambda: bf.read(65536), b""):
                    hasher.update(chunk)
            self.assertEqual(hasher.hexdigest(), expected_sha, f"{filename} sha256 驗證失敗")

        self.assertEqual(calc_total_size, 25051018)

    def test_expected_gap_voice_mappings_and_set(self):
        """驗證 mappings 與 set 生成函數"""
        mappings = get_expected_gap_voice_mappings()
        self.assertEqual(len(mappings), 236)
        for fname, sf in mappings.items():
            self.assertTrue(sf.exists())
            self.assertEqual(sf.name, fname)
            self.assertTrue(sf.name.endswith(".m4a"))

        expected_set = build_expected_gap_voice_set()
        self.assertEqual(len(expected_set), 236)
        for fname in expected_set:
            self.assertTrue(fname.endswith(".m4a"))

    def test_gap_voice_pruning_in_isolated_dist(self):
        """在隔離暫存目錄中測試 prune_stale_dist_assets 對 sound/story_vo 的清理與保留"""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dist = Path(tmpdir) / "dist"
            temp_dist.mkdir()
            temp_sound_dir = temp_dist / "sound" / "story_vo"
            temp_sound_dir.mkdir(parents=True)

            expected_set = build_expected_gap_voice_set()
            sample_gap_file = next(iter(expected_set))

            # 建立合法 gap 音檔
            (temp_sound_dir / sample_gap_file).write_bytes(b"VALID_GAP_VOICE_AUDIO")
            # 建立多餘的非 gap 音檔
            surplus_file = temp_sound_dir / "vo_surplus_not_in_gap.m4a"
            surplus_file.write_bytes(b"SURPLUS_AUDIO")
            # 建立非 m4a 檔案
            non_m4a_file = temp_sound_dir / "ignore_me.txt"
            non_m4a_file.write_bytes(b"TEXT_FILE")

            # 執行 pruning
            prune_report = prune_stale_dist_assets(dashboard_dir=DASHBOARD_DIR, dist_dir=temp_dist, dry_run=False)

            # 驗證多餘 m4a 音檔被清理
            self.assertFalse(surplus_file.exists(), "多餘非 gap 音檔應被 prune")
            self.assertIn(sample_gap_file, [f.name for f in temp_sound_dir.iterdir()], "白名單內的 gap 音檔應被保留")
            self.assertTrue((temp_sound_dir / sample_gap_file).exists())
            self.assertTrue(non_m4a_file.exists(), "非 m4a 檔案不應被任意刪除")

            self.assertIn("sound/story_vo surplus", prune_report)
            cnt, b = prune_report["sound/story_vo surplus"]
            self.assertEqual(cnt, 1)

    def test_dist_gitignore_allows_sound(self):
        """驗證 dist_story_map/.gitignore 收緊規則：僅允許 sound/story_vo/*.m4a 追蹤"""
        dist_gitignore = DIST_DIR / ".gitignore"
        if dist_gitignore.exists():
            content = dist_gitignore.read_text(encoding="utf-8")
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            self.assertNotIn("sound/", lines, "dist_story_map/.gitignore 不應包含全域忽略 sound/")
            self.assertIn("sound/*", lines, "應包含 sound/* 忽略其他 sound 子目錄")
            self.assertIn("!sound/story_vo/", lines, "應包含 !sound/story_vo/ 允許遞迴進入")
            self.assertIn("sound/story_vo/*", lines, "應包含 sound/story_vo/* 忽略非 m4a 檔案")
            self.assertIn("!sound/story_vo/*.m4a", lines, "應包含 !sound/story_vo/*.m4a 允許追蹤 gap 語音檔")
            self.assertIn("card/", lines, "dist_story_map/.gitignore 仍應保留 card/")

    def test_deployment_footprint_gate_with_gap_voices(self):
        """驗證加入 236 個 Gap 語音後，整體部署包體積仍能通過綠燈安全門禁 (< 650 MiB)"""
        prune_stats = prune_stale_dist_assets(dashboard_dir=DASHBOARD_DIR, dist_dir=DIST_DIR, dry_run=True)
        total_pruned_bytes = sum(b for _, b in prune_stats.values())

        additions, deltas = calculate_expected_additions_and_deltas(
            dashboard_dir=DASHBOARD_DIR,
            dist_dir=DIST_DIR
        )
        base_size = get_directory_size(DIST_DIR, exclude_subdirs={".git", "card"})
        projected_size = base_size - total_pruned_bytes + additions + deltas

        is_pass, msg, actual_bytes = check_footprint_gate(footprint_bytes=projected_size)
        self.assertTrue(is_pass)
        self.assertIn("PASS", msg)
        self.assertLess(projected_size, 650 * 1024 * 1024, f"預估大小過大: {projected_size / 1024 / 1024:.2f} MiB")
        # 預期大小應在 300 ~ 305 MiB 區間
        self.assertGreater(projected_size, 300 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
