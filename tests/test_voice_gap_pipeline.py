#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Gap Voice Deployment & Button UX Unit Tests

完整覆蓋：
1. 權威清單 (voice_gap_assets.json) 完整性與實體一致性 (236 檔 / 25,051,018 bytes / SHA-256 / 非 0-byte)。
2. Canonical deployment footprint 計算：sound 納入、.git 與 card 排除。
3. 容錯與門禁 Fail-Loudly：manifest 缺失、重複檔名、不安全路徑、來源缺失或雜湊不合一律拋出異常阻斷。
4. Dist Parity 門禁（在隔離暫存 fixture 驗證）：缺失檔案、多餘音檔、內容損壞一律報錯；完全吻合時 PASS。
5. 白名單映射與 pruning 隔離驗證。
6. dist_story_map/.gitignore 收緊規則校驗。
7. 部署包體積門禁預估 (< 650 MiB 綠燈標準)。
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
from pipeline.validate import (
    calculate_deployment_footprint,
    check_footprint_gate,
    load_and_validate_gap_voice_manifest,
    validate_voice_gap_manifest_and_assets,
    ValidationResult,
    EXPECTED_GAP_VOICE_COUNT,
    EXPECTED_GAP_VOICE_TOTAL_BYTES
)


class TestVoiceGapPipeline(unittest.TestCase):

    def test_voice_gap_assets_manifest_integrity(self):
        """驗證真實 voice_gap_assets.json 的結構、數量、大小與哈希完整性"""
        self.assertTrue(VOICE_GAP_ASSETS_PATH.exists(), f"找不到權威清單: {VOICE_GAP_ASSETS_PATH}")
        with open(VOICE_GAP_ASSETS_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("count"), EXPECTED_GAP_VOICE_COUNT)
        self.assertEqual(manifest.get("total_bytes"), EXPECTED_GAP_VOICE_TOTAL_BYTES)

        assets = manifest.get("assets", [])
        self.assertEqual(len(assets), EXPECTED_GAP_VOICE_COUNT)

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

        self.assertEqual(calc_total_size, EXPECTED_GAP_VOICE_TOTAL_BYTES)

    def test_canonical_footprint_includes_sound_and_excludes_card_git(self):
        """驗證 canonical deployment footprint 預設計入 sound，排除 .git 與 card"""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dist = Path(tmpdir) / "dist"
            temp_dist.mkdir()

            # 建立應排除的 .git 檔案 (100 bytes)
            git_dir = temp_dist / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_bytes(b"A" * 100)

            # 建立應排除的 card 檔案 (200 bytes)
            card_dir = temp_dist / "card" / "full"
            card_dir.mkdir(parents=True)
            (card_dir / "1001.webp").write_bytes(b"B" * 200)

            # 建立應計入的 sound/story_vo 檔案 (300 bytes)
            sound_dir = temp_dist / "sound" / "story_vo"
            sound_dir.mkdir(parents=True)
            (sound_dir / "test_gap.m4a").write_bytes(b"C" * 300)

            # 建立應計入的根目錄一般檔案 (50 bytes)
            (temp_dist / "index.html").write_bytes(b"D" * 50)

            # 預設計算: 應為 300 (sound) + 50 (index.html) = 350 bytes
            footprint = calculate_deployment_footprint(temp_dist)
            self.assertEqual(footprint, 350, f"部署體積計算錯誤: 預期 350 bytes, 實際 {footprint} bytes")

    def test_bundler_fails_loudly_when_manifest_missing(self):
        """驗證當 voice_gap_assets.json 缺失時，bundler 必須拋出 FileNotFoundError，絕不默默回傳空集"""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dash = Path(tmpdir) / "dashboard"
            empty_dash.mkdir()
            (empty_dash / "data").mkdir()
            (empty_dash / "sound" / "story_vo").mkdir(parents=True)

            with self.assertRaises(FileNotFoundError):
                get_expected_gap_voice_mappings(dashboard_dir=empty_dash)

    def test_manifest_fails_on_duplicate_or_unsafe_filename(self):
        """驗證清單含不安全路徑、重複檔名或非 m4a 時拒絕並報錯"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mf_dir = Path(tmpdir)
            mf_path = mf_dir / "voice_gap_assets.json"

            # 1. 不安全檔名 (路徑穿越)
            unsafe_manifest = {
                "count": 1,
                "total_bytes": 100,
                "assets": [{
                    "voice": "hack",
                    "filename": "../hack.m4a",
                    "size": 100,
                    "sha256": "0" * 64
                }]
            }
            mf_path.write_text(json.dumps(unsafe_manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path)

            # 2. 不安全檔名 (絕對路徑)
            unsafe_manifest["assets"][0]["filename"] = "/etc/passwd.m4a"
            unsafe_manifest["assets"][0]["voice"] = "/etc/passwd"
            mf_path.write_text(json.dumps(unsafe_manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path)

            # 3. 非 m4a 副檔名
            unsafe_manifest["assets"][0]["filename"] = "hack.exe"
            unsafe_manifest["assets"][0]["voice"] = "hack"
            mf_path.write_text(json.dumps(unsafe_manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path)

            # 4. 重複檔名
            dup_manifest = {
                "count": 2,
                "total_bytes": 200,
                "assets": [
                    {"voice": "dup1", "filename": "dup.m4a", "size": 100, "sha256": "0" * 64},
                    {"voice": "dup", "filename": "dup.m4a", "size": 100, "sha256": "0" * 64}
                ]
            }
            mf_path.write_text(json.dumps(dup_manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path)

    def test_manifest_fails_on_missing_or_corrupted_source_file(self):
        """驗證當宣告的實體音檔缺失、大小不符或雜湊不符時拋出異常"""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            mf_path = temp_dir / "voice_gap_assets.json"
            snd_dir = temp_dir / "sound"
            snd_dir.mkdir()

            test_asset = {
                "voice": "test_vo",
                "filename": "test_vo.m4a",
                "size": 10,
                "sha256": hashlib.sha256(b"0123456789").hexdigest()
            }
            manifest_data = {
                "count": 1,
                "total_bytes": 10,
                "assets": [test_asset]
            }
            mf_path.write_text(json.dumps(manifest_data), encoding="utf-8")

            # 檔案不存在
            with self.assertRaises(FileNotFoundError):
                load_and_validate_gap_voice_manifest(mf_path, sound_dir=snd_dir)

            # 檔案大小不符
            (snd_dir / "test_vo.m4a").write_bytes(b"012")
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path, sound_dir=snd_dir)

            # 雜湊不符
            (snd_dir / "test_vo.m4a").write_bytes(b"ABCDEFGHIJ")  # 10 bytes 但 sha 不同
            with self.assertRaises(ValueError):
                load_and_validate_gap_voice_manifest(mf_path, sound_dir=snd_dir, verify_hashes=True)

    def test_validator_dist_parity_in_isolated_fixture(self):
        """在隔離暫存 fixture 測試 validate_voice_gap_manifest_and_assets 的 dist parity 門禁"""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dist = Path(tmpdir) / "dist"
            temp_dist.mkdir()
            temp_sound = temp_dist / "sound" / "story_vo"
            temp_sound.mkdir(parents=True)

            # A. 初始空目錄：缺少全部 236 檔 -> 必須失敗
            res_empty = ValidationResult()
            passed = validate_voice_gap_manifest_and_assets(
                dashboard_dir=DASHBOARD_DIR,
                dist_dir=temp_dist,
                res=res_empty,
                check_dist=True,
                verbose=False
            )
            self.assertFalse(passed)
            self.assertTrue(any("缺失檔案" in e for e in res_empty.errors))

            # B. 建立完美的 236 檔
            src_sound = DASHBOARD_DIR / "sound" / "story_vo"
            with open(VOICE_GAP_ASSETS_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for item in manifest["assets"]:
                fname = item["filename"]
                shutil.copy2(src_sound / fname, temp_sound / fname)

            # 完美吻合 -> 必須 PASS
            res_pass = ValidationResult()
            passed = validate_voice_gap_manifest_and_assets(
                dashboard_dir=DASHBOARD_DIR,
                dist_dir=temp_dist,
                res=res_pass,
                check_dist=True,
                verbose=False
            )
            self.assertTrue(passed, f"完美 236 檔應通過驗證: {res_pass.errors}")
            self.assertEqual(len(res_pass.errors), 0)

            # C. 多了一個非白名單音檔 -> 必須失敗
            (temp_sound / "extra_vo.m4a").write_bytes(b"EXTRA")
            res_extra = ValidationResult()
            passed = validate_voice_gap_manifest_and_assets(
                dashboard_dir=DASHBOARD_DIR,
                dist_dir=temp_dist,
                res=res_extra,
                check_dist=True,
                verbose=False
            )
            self.assertFalse(passed)
            self.assertTrue(any("非白名單多餘音檔" in e for e in res_extra.errors))
            (temp_sound / "extra_vo.m4a").unlink()

            # D. 其中一個檔案被破壞 (損壞) -> 必須失敗
            first_fname = manifest["assets"][0]["filename"]
            (temp_sound / first_fname).write_bytes(b"CORRUPTED_DATA")
            res_corrupt = ValidationResult()
            passed = validate_voice_gap_manifest_and_assets(
                dashboard_dir=DASHBOARD_DIR,
                dist_dir=temp_dist,
                res=res_corrupt,
                check_dist=True,
                verbose=False
            )
            self.assertFalse(passed)
            self.assertTrue(any("檔案內容損壞" in e for e in res_corrupt.errors))

    def test_expected_gap_voice_mappings_and_set(self):
        """驗證 mappings 與 set 生成函數"""
        mappings = get_expected_gap_voice_mappings()
        self.assertEqual(len(mappings), EXPECTED_GAP_VOICE_COUNT)
        for fname, sf in mappings.items():
            self.assertTrue(sf.exists())
            self.assertEqual(sf.name, fname)
            self.assertTrue(sf.name.endswith(".m4a"))

        expected_set = build_expected_gap_voice_set()
        self.assertEqual(len(expected_set), EXPECTED_GAP_VOICE_COUNT)
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
        self.assertGreater(projected_size, 300 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
