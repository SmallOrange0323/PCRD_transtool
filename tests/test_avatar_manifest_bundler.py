#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Avatar Manifest & Bundler Authority Unit Tests (Phase 5)

驗證範圍：
1. active manifest portrait is published
2. placeholder_only does not require physical image
3. missing active file fails gate validation
4. hash mismatch fails gate validation
5. manifest omission of story-required ID fails gate validation
6. duplicate legacy WebP is not part of future expected set
7. UI-only required asset is preserved
8. old Reality hard-coded publication rule is no longer required for dialogue publication
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import hashlib
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    get_expected_icon_unit_mappings,
    get_expected_dialogue_icon_mappings,
    get_character_catalog_icon_mappings,
    get_expected_dialogue_override_mappings,
    build_expected_icon_unit_set,
    DASHBOARD_DIR,
    DIST_DIR
)
from pipeline.validate import (
    validate_avatar_manifest_and_assets,
    ValidationResult
)

class TestAvatarManifestBundler(unittest.TestCase):

    def setUp(self):
        manifest_path = DASHBOARD_DIR / "data" / "avatar_assets.json"
        self.assertTrue(manifest_path.exists(), "Avatar manifest must exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)
        self.assets = self.manifest.get("assets", [])

    def test_1_active_manifest_portrait_is_published(self):
        """1. 驗證 active manifest portrait 會被加入 bundler expected 映射中"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        # 抽樣驗證 active 對白頭像
        active_dialogue_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "dialogue"
        ]
        self.assertTrue(active_dialogue_entries, "Manifest must contain active dialogue assets")

        for entry in active_dialogue_entries:
            self.assertIn(
                entry["filename"],
                expected_files,
                f"Active portrait {entry['filename']} must be published by bundler"
            )

    def test_2_placeholder_only_does_not_require_physical_image(self):
        """2. 驗證 placeholder_only 不產生實體檔案發布映射，門禁也不會要求二進位"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        placeholder_entries = [
            a for a in self.assets
            if a.get("status") == "placeholder_only"
        ]

        for entry in placeholder_entries:
            uid = entry["unit_id"]
            # 確保不會試圖發布該 ID 的圖檔
            for ext in [".png", ".webp"]:
                self.assertNotIn(f"{uid}{ext}", expected_files)
                self.assertNotIn(f"unit_icon_{uid}{ext}", expected_files)

        # 執行門禁驗證，確保 3 個 placeholder 不會觸發缺失報錯
        res = ValidationResult()
        is_valid = validate_avatar_manifest_and_assets(DASHBOARD_DIR, res)
        self.assertTrue(is_valid)
        self.assertEqual(len(res.errors), 0, f"Errors found: {res.errors}")

    def test_3_missing_active_file_fails(self):
        """3. 驗證若 active 登記之來源檔案缺失，門禁驗證會失敗"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            tmp_data = tmp_dash / "data"
            tmp_data.mkdir(parents=True)
            tmp_icon = tmp_dash / "icon" / "unit"
            tmp_icon.mkdir(parents=True)

            mock_manifest = {
                "version": 1,
                "assets": [
                    {
                        "unit_id": 999999,
                        "filename": "999999.png",
                        "format": "png",
                        "usage": "dialogue",
                        "status": "active",
                        "size_bytes": 12345,
                        "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                        "provenance": "test"
                    }
                ]
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            missing_errors = [e for e in res.errors if "缺失" in e or "missing" in e.lower()]
            self.assertGreater(len(missing_errors), 0, f"Should report missing file error: {res.errors}")

    def test_4_hash_mismatch_fails(self):
        """4. 驗證若檔案 SHA-256 與 manifest 不符，門禁驗證會失敗"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            tmp_data = tmp_dash / "data"
            tmp_data.mkdir(parents=True)
            tmp_icon = tmp_dash / "icon" / "unit"
            tmp_icon.mkdir(parents=True)

            # 建立一個實體檔案
            dummy_file = tmp_icon / "999999.png"
            dummy_file.write_bytes(b"hello world")

            mock_manifest = {
                "version": 1,
                "assets": [
                    {
                        "unit_id": 999999,
                        "filename": "999999.png",
                        "format": "png",
                        "usage": "dialogue",
                        "status": "active",
                        "size_bytes": 11,
                        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",  # 偽造錯誤 hash
                        "provenance": "test"
                    }
                ]
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            hash_errors = [e for e in res.errors if "SHA-256" in e or "雜湊失配" in e]
            self.assertGreater(len(hash_errors), 0, f"Should report hash mismatch error: {res.errors}")

    def test_5_manifest_omission_of_story_required_id_fails(self):
        """5. 驗證若劇本中需要的 avatar-eligible ID 未登錄於 manifest，門禁驗證會失敗"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            tmp_data = tmp_dash / "data"
            tmp_data.mkdir(parents=True)
            tmp_story = tmp_dash / "story"
            tmp_story.mkdir(parents=True)
            tmp_icon = tmp_dash / "icon" / "unit"
            tmp_icon.mkdir(parents=True)

            # 建立包含對白 ID 100011 的假劇本
            story_file = tmp_story / "1001.json"
            story_file.write_text(json.dumps([{"type": "dialogue", "unit_id": 100011, "name": "佩可"}]), encoding="utf-8")

            # 建立一個實體檔案給 100012
            dummy_file = tmp_icon / "100012.png"
            dummy_file.write_bytes(b"dummy")
            sha = hashlib.sha256(b"dummy").hexdigest()

            # Manifest 登記了 100012，但遺漏了劇本中的 100011
            mock_manifest = {
                "version": 1,
                "assets": [
                    {
                        "unit_id": 100012,
                        "filename": "100012.png",
                        "format": "png",
                        "usage": "dialogue",
                        "status": "active",
                        "size_bytes": 5,
                        "sha256": sha,
                        "provenance": "test"
                    }
                ]
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            omission_errors = [e for e in res.errors if "未在 avatar_assets.json 中登錄" in e or "登錄" in e]
            self.assertGreater(len(omission_errors), 0, f"Should report omission error: {res.errors}")

    def test_6_duplicate_legacy_webp_is_not_part_of_future_expected_set(self):
        """6. 驗證若存在 duplicate legacy WebP，不會被加入 expected set（未來會被清理）"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        # 驗證所有對白頭像中，若本地同時有同名 webp，bundler 絕不將其列入 expected mappings
        dialogue_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "dialogue"
        ]
        self.assertTrue(dialogue_entries, "Manifest must contain active dialogue assets")

        # 抽樣檢查其中知名且曾存在 webp 的對白頭像
        for entry in dialogue_entries[:100]:
            uid = entry["unit_id"]
            self.assertNotIn(f"{uid}.webp", expected_files)
            self.assertNotIn(f"unit_icon_{uid}.webp", expected_files)

    def test_7_ui_only_required_asset_is_preserved(self):
        """7. 驗證 UI 所需的非對白資產（category: ui）依然被 bundler 完整發布"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        ui_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "ui"
        ]
        self.assertTrue(ui_entries, "Manifest must contain UI assets")

        for entry in ui_entries:
            self.assertIn(
                entry["filename"],
                expected_files,
                f"UI-required asset {entry['filename']} must be published by bundler"
            )

    def test_8_old_reality_hardcoded_rule_no_longer_required(self):
        """8. 驗證 Manifest-First 權威模式不再需要 legacy hard-coded reality 規則"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()

        # 驗證著名的 reality fixtures 在 expected 中
        reality_fixtures = [105812, 105913, 106012, 106412, 106831, 107331]
        for fid in reality_fixtures:
            self.assertIn(f"{fid}.png", dialogue_mappings)

    def test_9_dialogue_override_story_unit_published(self):
        """9. 驗證 dialogue_asset 宣告之覆蓋頭像會被獨立映射發布，且 primary 不受影響"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        self.assertIn("192711.png", dialogue_mappings)
        self.assertEqual(dialogue_mappings["192711.png"], DASHBOARD_DIR / "icon" / "unit" / "192711.png")

        override_mappings = get_expected_dialogue_override_mappings()
        self.assertGreaterEqual(len(override_mappings), 1)
        self.assertIn("icon/story_unit/192711.png", override_mappings)
        self.assertEqual(override_mappings["icon/story_unit/192711.png"], DASHBOARD_DIR / "icon" / "story_unit" / "192711.png")

    def test_11_character_catalog_avatars_included(self):
        """11. 驗證角色圖鑑代表頭像完整納入發布集合，補齊原本缺失的 7 位可玩角色"""
        catalog_mappings = get_character_catalog_icon_mappings()
        self.assertTrue(catalog_mappings, "Character catalog mappings must not be empty")

        missing_7 = [181101, 181001, 180901, 180801, 180701, 123001, 118601]
        for uid in missing_7:
            base_id = (uid // 100) * 100
            self.assertIn(f"{base_id + 11}.png", catalog_mappings)
            self.assertIn(f"{base_id + 31}.png", catalog_mappings)

        union_mappings = get_expected_icon_unit_mappings()
        self.assertEqual(
            set(union_mappings),
            set(get_expected_dialogue_icon_mappings()) | set(catalog_mappings),
            "Published icon set must equal dialogue ∪ character-catalog mappings"
        )
        # 確保對白 active 頭像全部包含
        for fname in get_expected_dialogue_icon_mappings():
            self.assertIn(fname, union_mappings)
        # 確保角色圖鑑頭像全部包含
        for fname in catalog_mappings:
            self.assertIn(fname, union_mappings)

    def test_10_dialogue_override_validation_and_rejection(self):
        """10. 驗證 validator 獨立校驗 dialogue_asset，並拒絕不安全路徑"""
        res = ValidationResult()
        is_valid = validate_avatar_manifest_and_assets(DASHBOARD_DIR, res)
        self.assertTrue(is_valid, f"Validation should pass on canonical source: {res.errors}")

        # 正向案例：icon/story_unit/192711.png 必須在 validator 與 bundler 雙雙通過
        override_mappings = get_expected_dialogue_override_mappings(DASHBOARD_DIR)
        self.assertIn("icon/story_unit/192711.png", override_mappings)

        # 測試不安全路徑矩陣：驗證 Validator 與 Bundler 雙層合約均拒絕
        unsafe_paths = [
            "icon/story_unit/../999999.png",
            "C:/temp/999999.png",
            "/tmp/999999.png",
            "https://example.com/999999.png",
            "http://example.com/999999.png",
            r"\server\share\999999.png"
        ]

        for unsafe_p in unsafe_paths:
            with self.subTest(path=unsafe_p):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_dash = Path(tmpdir)
                    tmp_data = tmp_dash / "data"
                    tmp_data.mkdir(parents=True)
                    tmp_icon = tmp_dash / "icon" / "unit"
                    tmp_icon.mkdir(parents=True)
                    (tmp_icon / "999999.png").write_bytes(b"primary content")
                    p_sha = hashlib.sha256(b"primary content").hexdigest()

                    mock_manifest = {
                        "version": 1,
                        "assets": [
                            {
                                "unit_id": 999999,
                                "filename": "999999.png",
                                "format": "png",
                                "usage": "dialogue",
                                "status": "active",
                                "size_bytes": len(b"primary content"),
                                "sha256": p_sha,
                                "provenance": "test",
                                "dialogue_asset": {
                                    "path": unsafe_p,
                                    "format": "png",
                                    "size_bytes": 100,
                                    "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                                    "provenance": "test"
                                }
                            }
                        ]
                    }
                    with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                        json.dump(mock_manifest, f)

                    # A. 驗證 Validator 拒絕
                    res_bad = ValidationResult()
                    is_valid_bad = validate_avatar_manifest_and_assets(tmp_dash, res_bad)
                    self.assertFalse(is_valid_bad, f"Validator must reject unsafe path: {unsafe_p}")
                    self.assertGreater(
                        len(res_bad.errors), 0,
                        f"Validator must report errors for unsafe path: {unsafe_p}"
                    )

                    # B. 驗證 Bundler 拒絕 (必須拋出 ValueError)
                    with self.assertRaises(ValueError, msg=f"Bundler must reject unsafe path: {unsafe_p}"):
                        get_expected_dialogue_override_mappings(tmp_dash)

if __name__ == "__main__":
    unittest.main()
