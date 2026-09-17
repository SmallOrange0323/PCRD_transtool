#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avatar manifest / bundler contract tests.

These tests intentionally verify relationships and safety contracts instead of
hard-coding production asset counts. The avatar corpus is expected to grow as
new stories and canonical portraits are added.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    DASHBOARD_DIR,
    get_character_catalog_icon_mappings,
    get_expected_dialogue_icon_mappings,
    get_expected_dialogue_override_mappings,
    get_expected_icon_unit_mappings,
)
from pipeline.validate import ValidationResult, validate_avatar_manifest_and_assets


class TestAvatarManifestBundler(unittest.TestCase):
    def setUp(self):
        manifest_path = DASHBOARD_DIR / "data" / "avatar_assets.json"
        self.assertTrue(manifest_path.exists(), "Avatar manifest must exist")
        with manifest_path.open("r", encoding="utf-8") as f:
            self.manifest = json.load(f)
        self.assets = self.manifest.get("assets", [])

    @staticmethod
    def _write_manifest(dashboard_dir: Path, assets):
        data_dir = dashboard_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (dashboard_dir / "icon" / "unit").mkdir(parents=True, exist_ok=True)
        (data_dir / "avatar_assets.json").write_text(
            json.dumps({"version": 1, "assets": assets}),
            encoding="utf-8",
        )

    def test_1_active_manifest_portraits_are_published(self):
        """Every active dialogue portrait in the manifest is published."""
        mappings = get_expected_icon_unit_mappings()
        expected_files = set(mappings)
        active_dialogue_entries = [
            a
            for a in self.assets
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
        """Placeholder-only entries do not enter the physical publish set."""
        expected_files = set(get_expected_icon_unit_mappings())
        placeholder_entries = [a for a in self.assets if a.get("status") == "placeholder_only"]
        self.assertGreater(len(placeholder_entries), 0)

        for entry in placeholder_entries:
            filename = entry.get("filename")
            if filename:
                self.assertNotIn(filename, expected_files)

        res = ValidationResult()
        self.assertTrue(validate_avatar_manifest_and_assets(DASHBOARD_DIR, res))
        self.assertEqual(res.errors, [])

    def test_3_missing_active_file_fails(self):
        """An active manifest entry without its binary must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            self._write_manifest(
                tmp_dash,
                [
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
            )
            res = ValidationResult()
            self.assertFalse(validate_avatar_manifest_and_assets(tmp_dash, res))
            self.assertTrue(any("缺失" in e or "missing" in e.lower() for e in res.errors))

    def test_4_hash_mismatch_fails(self):
        """A binary whose SHA-256 differs from the manifest must fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            self._write_manifest(
                tmp_dash,
                [
                    {
                        "unit_id": 999999,
                        "filename": "999999.png",
                        "format": "png",
                        "usage": "dialogue",
                        "status": "active",
                        "size_bytes": 11,
                        "sha256": "0" * 64,
                        "provenance": "test",
                    }
                ],
            )
            (tmp_dash / "icon" / "unit" / "999999.png").write_bytes(b"hello world")
            res = ValidationResult()
            self.assertFalse(validate_avatar_manifest_and_assets(tmp_dash, res))
            self.assertTrue(any("SHA-256" in e or "雜湊失配" in e for e in res.errors))

    def test_5_manifest_omission_of_story_required_id_fails(self):
        """A story-required explicit unit_id omitted from the manifest must fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dash = Path(tmpdir)
            self._write_manifest(
                tmp_dash,
                [
                    {
                        "unit_id": 100012,
                        "filename": "100012.png",
                        "format": "png",
                        "usage": "dialogue",
                        "status": "active",
                        "size_bytes": 5,
                        "sha256": hashlib.sha256(b"dummy").hexdigest(),
                        "provenance": "test",
                    }
                ],
            )
            (tmp_dash / "icon" / "unit" / "100012.png").write_bytes(b"dummy")
            story_dir = tmp_dash / "story"
            story_dir.mkdir(parents=True)
            (story_dir / "1001.json").write_text(
                json.dumps([{"type": "dialogue", "unit_id": 100011, "name": "佩可"}]),
                encoding="utf-8",
            )

            res = ValidationResult()
            self.assertFalse(validate_avatar_manifest_and_assets(tmp_dash, res))
            self.assertTrue(any("登錄" in e for e in res.errors))

    def test_6_dialogue_mappings_resolve_to_real_sources(self):
        """Dialogue mappings must resolve to real source files without assuming one image format."""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        active_dialogue_entries = [
            a
            for a in self.assets
            if a.get("status") == "active" and a.get("usage") == "dialogue"
        ]

        self.assertGreater(len(dialogue_mappings), 0)
        for dst_name, src in dialogue_mappings.items():
            self.assertEqual(Path(dst_name).name, dst_name)
            self.assertTrue(src.exists(), f"Dialogue mapping source must exist: {dst_name} -> {src}")
            self.assertTrue(src.is_file(), f"Dialogue mapping source must be a file: {dst_name} -> {src}")

        for entry in active_dialogue_entries:
            filename = entry["filename"]
            expected_src = DASHBOARD_DIR / "icon" / "unit" / filename
            self.assertIn(filename, dialogue_mappings)
            self.assertEqual(dialogue_mappings[filename], expected_src)
            self.assertTrue(expected_src.is_file())

    def test_7_ui_only_required_assets_are_preserved(self):
        """All active UI-only assets remain in the publish set."""
        expected_files = set(get_expected_icon_unit_mappings())
        ui_entries = [
            a for a in self.assets if a.get("status") == "active" and a.get("usage") == "ui"
        ]
        self.assertGreater(len(ui_entries), 0)
        for entry in ui_entries:
            self.assertIn(entry["filename"], expected_files)

    def test_8_reality_fixtures_are_manifest_driven(self):
        """Known reality portraits remain published without legacy hard-coded rules."""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        reality_fixtures = [105812, 105913, 106012, 106412, 106831, 107331]
        for fid in reality_fixtures:
            self.assertIn(f"{fid}.png", dialogue_mappings)

    def test_9_dialogue_override_story_unit_published(self):
        """Dialogue override mapping is published independently of the primary portrait."""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        self.assertIn("192711.png", dialogue_mappings)
        self.assertEqual(
            dialogue_mappings["192711.png"],
            DASHBOARD_DIR / "icon" / "unit" / "192711.png",
        )

        override_mappings = get_expected_dialogue_override_mappings()
        self.assertEqual(len(override_mappings), 1)
        self.assertIn("icon/story_unit/192711.png", override_mappings)
        self.assertEqual(
            override_mappings["icon/story_unit/192711.png"],
            DASHBOARD_DIR / "icon" / "story_unit" / "192711.png",
        )

    def test_10_dialogue_override_validation_and_rejection(self):
        """Validator and bundler both reject unsafe dialogue override paths."""
        res = ValidationResult()
        self.assertTrue(validate_avatar_manifest_and_assets(DASHBOARD_DIR, res))
        self.assertEqual(res.errors, [])

        unsafe_paths = [
            "icon/story_unit/../999999.png",
            "C:/temp/999999.png",
            "/tmp/999999.png",
            "https://example.com/999999.png",
            "http://example.com/999999.png",
            r"\\server\share\999999.png",
        ]

        for unsafe_path in unsafe_paths:
            with self.subTest(path=unsafe_path), tempfile.TemporaryDirectory() as tmpdir:
                tmp_dash = Path(tmpdir)
                primary = b"primary content"
                self._write_manifest(
                    tmp_dash,
                    [
                        {
                            "unit_id": 999999,
                            "filename": "999999.png",
                            "format": "png",
                            "usage": "dialogue",
                            "status": "active",
                            "size_bytes": len(primary),
                            "sha256": hashlib.sha256(primary).hexdigest(),
                            "provenance": "test",
                            "dialogue_asset": {
                                "path": unsafe_path,
                                "format": "png",
                                "size_bytes": 100,
                                "sha256": "0" * 64,
                                "provenance": "test",
                            },
                        }
                    ],
                )
                (tmp_dash / "icon" / "unit" / "999999.png").write_bytes(primary)

                res_bad = ValidationResult()
                self.assertFalse(validate_avatar_manifest_and_assets(tmp_dash, res_bad))
                self.assertGreater(len(res_bad.errors), 0)
                with self.assertRaises(ValueError):
                    get_expected_dialogue_override_mappings(tmp_dash)

    def test_11_character_catalog_union_contract(self):
        """Expected icon/unit mappings equal dialogue-active ∪ available catalog assets."""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        catalog_mappings = get_character_catalog_icon_mappings()
        union_mappings = get_expected_icon_unit_mappings()

        expected_union = set(dialogue_mappings) | set(catalog_mappings)
        self.assertEqual(set(union_mappings), expected_union)
        for fname, src in dialogue_mappings.items():
            self.assertEqual(union_mappings[fname], src)
        for fname, src in catalog_mappings.items():
            self.assertEqual(union_mappings[fname], dialogue_mappings.get(fname) or src)


if __name__ == "__main__":
    unittest.main()
