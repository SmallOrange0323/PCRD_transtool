#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Avatar Manifest & Bundler Authority Unit Tests (Phase 5)

驗證範圍：
1. active manifest portrait is published
2. placeholder_only does not require physical image
3. missing active file fails gate validation
4. hash mismatch fails gate validation
5. manifest omission of story-required ID fails
6. duplicate legacy WebP is not part of future expected set
7. UI-only required asset is preserved
8. old Reality hard-coded publication rule is no longer required for dialogue publication
9. dialogue override is published independently
10. override path validation rejects unsafe paths
11. character catalog mappings are a deterministic subset of the final union
"""

import sys
import unittest
import tempfile
import json
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    get_expected_icon_unit_mappings,
    get_expected_dialogue_icon_mappings,
    get_character_catalog_icon_mappings,
    get_expected_dialogue_override_mappings,
    DASHBOARD_DIR,
)
from pipeline.validate import (
    validate_avatar_manifest_and_assets,
    ValidationResult,
)


class TestAvatarManifestBundler(unittest.TestCase):

    def setUp(self):
        manifest_path = DASHBOARD_DIR / "data" / "avatar_assets.json"
        self.assertTrue(manifest_path.exists(), "Avatar manifest must exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)
        self.assets = self.manifest.get("assets", [])

    def test_1_active_manifest_portrait_is_published(self):
        """1. 驗證所有 active manifest portrait 都會被 bundler 發布。"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        active_dialogue_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "dialogue"
        ]
        self.assertGreater(len(active_dialogue_entries), 0)

        for entry in active_dialogue_entries:
            self.assertIn(
                entry["filename"],
                expected_files,
                f"Active portrait {entry['filename']} must be published by bundler",
            )

    def test_2_placeholder_only_does_not_require_physical_image(self):
        """2. 驗證 placeholder_only 不產生實體檔案發布映射，門禁也不會要求二進位。"""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings.keys())

        placeholder_entries = [
            a for a in self.assets
            if a.get("status") == "placeholder_only"
        ]
        metadata_count = self.manifest.get("metadata", {}).get("placeholder_only_count")
        if metadata_count is not None:
            self.assertEqual(len(placeholder_entries), metadata_count)

        for entry in placeholder_entries:
            uid = entry["unit_id"]
            filename = entry.get("filename")
            if filename:
                self.assertNotIn(filename, expected_files)
            for ext in [".png", ".webp"]:
                self.assertNotIn(f"{uid}{ext}", expected_files)
                self.assertNotIn(f"unit_icon_{uid}{ext}", expected_files)

        res = ValidationResult()
        is_valid = validate_avatar_manifest_and_assets(DASHBOARD_DIR, res)
        self.assertTrue(is_valid)
        self.assertEqual(len(res.errors), 0, f"Errors found: {res.errors}")

    def test_3_missing_active_file_fails(self):
        """3. 驗證若 active 登記之來源檔案缺失，門禁驗證會失敗。"""
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
                        "provenance": "test",
                    }
                ],
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            missing_errors = [e for e in res.errors if "缺失" in e or "missing" in e.lower()]
            self.assertGreater(len(missing_errors), 0, f"Should report missing file error: {res.errors}")

    def test_4_hash_mismatch_fails(self):
        """4. 驗證若檔案 SHA-256 與 manifest 不符，門禁驗證會失敗。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            tmp_data = tmp_dash / "data"
            tmp_data.mkdir(parents=True)
            tmp_icon = tmp_dash / "icon" / "unit"
            tmp_icon.mkdir(parents=True)

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
                        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                        "provenance": "test",
                    }
                ],
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            hash_errors = [e for e in res.errors if "SHA-256" in e or "雜湊失配" in e]
            self.assertGreater(len(hash_errors), 0, f"Should report hash mismatch error: {res.errors}")

    def test_5_manifest_omission_of_story_required_id_fails(self):
        """5. 驗證劇本需要的 avatar-eligible ID 未登錄於 manifest 時會失敗。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            tmp_data = tmp_dash / "data"
            tmp_data.mkdir(parents=True)
            tmp_story = tmp_dash / "story"
            tmp_story.mkdir(parents=True)
            tmp_icon = tmp_dash / "icon" / "unit"
            tmp_icon.mkdir(parents=True)

            story_file = tmp_story / "1001.json"
            story_file.write_text(
                json.dumps([{"type": "dialogue", "unit_id": 100011, "name": "佩可"}]),
                encoding="utf-8",
            )

            dummy_file = tmp_icon / "100012.png"
            dummy_file.write_bytes(b"dummy")
            sha = hashlib.sha256(b"dummy").hexdigest()

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
                        "provenance": "test",
                    }
                ],
            }
            with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                json.dump(mock_manifest, f)

            res = ValidationResult()
            is_valid = validate_avatar_manifest_and_assets(tmp_dash, res)
            self.assertFalse(is_valid)
            omission_errors = [e for e in res.errors if "未在 avatar_assets.json 中登錄" in e or "登錄" in e]
            self.assertGreater(len(omission_errors), 0, f"Should report omission error: {res.errors}")

    def test_6_duplicate_legacy_webp_is_not_part_of_future_expected_set(self):
        """6. 驗證 active 對白 PNG 不會讓同 ID legacy WebP 混入 expected set。"""
        expected_files = set(get_expected_icon_unit_mappings().keys())
        dialogue_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "dialogue"
        ]
        self.assertGreater(len(dialogue_entries), 0)

        for entry in dialogue_entries:
            filename = entry["filename"]
            stem = Path(filename).stem
            uid = entry["unit_id"]
            self.assertNotIn(f"{stem}.webp", expected_files)
            self.assertNotIn(f"unit_icon_{stem}.webp", expected_files)
            self.assertNotIn(f"{uid}.webp", expected_files)
            self.assertNotIn(f"unit_icon_{uid}.webp", expected_files)

    def test_7_ui_only_required_asset_is_preserved(self):
        """7. 驗證 UI 所需 active 資產依然由 bundler 完整發布。"""
        expected_files = set(get_expected_icon_unit_mappings().keys())
        ui_entries = [
            a for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "ui"
        ]
        metadata_count = self.manifest.get("metadata", {}).get("ui_assets_count")
        if metadata_count is not None:
            self.assertEqual(len(ui_entries), metadata_count)

        for entry in ui_entries:
            self.assertIn(
                entry["filename"],
                expected_files,
                f"UI-required asset {entry['filename']} must be published by bundler",
            )

    def test_8_old_reality_hardcoded_rule_no_longer_required(self):
        """8. 驗證 Manifest-First 模式仍發布代表性 reality fixtures，不依賴總數常數。"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()

        reality_fixtures = [105812, 105913, 106012, 106412, 106831, 107331]
        for fid in reality_fixtures:
            self.assertIn(f"{fid}.png", dialogue_mappings)

    def test_9_dialogue_override_story_unit_published(self):
        """9. 驗證 dialogue_asset 覆蓋頭像獨立映射發布，primary 不受影響。"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        self.assertIn("192711.png", dialogue_mappings)
        self.assertEqual(
            dialogue_mappings["192711.png"],
            DASHBOARD_DIR / "icon" / "unit" / "192711.png",
        )

        override_mappings = get_expected_dialogue_override_mappings()
        self.assertIn("icon/story_unit/192711.png", override_mappings)
        self.assertEqual(
            override_mappings["icon/story_unit/192711.png"],
            DASHBOARD_DIR / "icon" / "story_unit" / "192711.png",
        )

    def test_10_dialogue_override_validation_and_rejection(self):
        """10. 驗證 validator 獨立校驗 dialogue_asset，並拒絕不安全路徑。"""
        res = ValidationResult()
        is_valid = validate_avatar_manifest_and_assets(DASHBOARD_DIR, res)
        self.assertTrue(is_valid, f"Validation should pass on canonical source: {res.errors}")

        override_mappings = get_expected_dialogue_override_mappings(DASHBOARD_DIR)
        self.assertIn("icon/story_unit/192711.png", override_mappings)

        unsafe_paths = [
            "icon/story_unit/../999999.png",
            "C:/temp/999999.png",
            "/tmp/999999.png",
            "https://example.com/999999.png",
            "http://example.com/999999.png",
            r"\\server\share\999999.png",
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
                                    "provenance": "test",
                                },
                            }
                        ],
                    }
                    with open(tmp_data / "avatar_assets.json", "w", encoding="utf-8") as f:
                        json.dump(mock_manifest, f)

                    res_bad = ValidationResult()
                    is_valid_bad = validate_avatar_manifest_and_assets(tmp_dash, res_bad)
                    self.assertFalse(is_valid_bad, f"Validator must reject unsafe path: {unsafe_p}")
                    self.assertGreater(
                        len(res_bad.errors),
                        0,
                        f"Validator must report errors for unsafe path: {unsafe_p}",
                    )

                    with self.assertRaises(ValueError, msg=f"Bundler must reject unsafe path: {unsafe_p}"):
                        get_expected_dialogue_override_mappings(tmp_dash)

    def test_11_character_catalog_avatars_included(self):
        """11. 驗證 clean-clone 中可用 catalog mappings 全數進入 deterministic union。"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        catalog_mappings = get_character_catalog_icon_mappings()
        union_mappings = get_expected_icon_unit_mappings()

        self.assertGreater(len(catalog_mappings), 0)

        for fname, src_path in catalog_mappings.items():
            self.assertTrue(src_path.exists(), f"Catalog source must exist: {src_path}")
            self.assertEqual(src_path.parent, DASHBOARD_DIR / "icon" / "unit")
            self.assertEqual(src_path.name, fname)

        expected_union_keys = set(dialogue_mappings) | set(catalog_mappings)
        self.assertEqual(set(union_mappings), expected_union_keys)

        for fname in expected_union_keys:
            expected_src = dialogue_mappings.get(fname) or catalog_mappings[fname]
            self.assertEqual(union_mappings[fname], expected_src)


if __name__ == "__main__":
    unittest.main()
