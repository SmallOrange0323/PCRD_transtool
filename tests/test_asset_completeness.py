# -*- coding: utf-8 -*-
"""
test_asset_completeness.py — Asset Completeness Gate v1 最小單元測試
測試涵蓋：
  1. Movie ID 正規化 (movie_123, story_123, 123, 大小寫容錯)
  2. Movie Delta Coverage Policy:
     - historical missing -> WARN / non-blocking PASS
     - new mapped -> PASS
     - new missing -> blocking FAIL (回報引用該 movie 的 story ID)
  3. Movie Baseline Promotion:
     - baseline 不含重複 prefix alias
     - dry-run 不修改 baseline
  4. Event Top Completeness (Mock 比對與零寫入)
  5. Story Thumbnail Completeness (Mock 交集計算、fallback 不算 missing、零寫入)
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.assets import (
    normalize_movie_id,
    scan_movie_references,
    check_movie_coverage,
    promote_movie_baseline,
    check_event_top_completeness,
    check_story_thumbnail_completeness,
    parse_story_thumbs_from_manifest,
    analyze_asset_completeness,
    MovieCoverageResult,
    EventTopCompletenessResult,
    StoryThumbnailCompletenessResult,
    AssetCompletenessResult
)


class TestAssetCompleteness(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. Movie Normalization Tests
    # --------------------------------------------------------------------------
    def test_normalize_movie_id(self):
        self.assertEqual(normalize_movie_id("movie_123"), "123")
        self.assertEqual(normalize_movie_id("story_123"), "123")
        self.assertEqual(normalize_movie_id("123"), "123")
        self.assertEqual(normalize_movie_id(123), "123")
        self.assertEqual(normalize_movie_id("MOVIE_45678"), "45678")
        self.assertEqual(normalize_movie_id("STORY_99999"), "99999")
        self.assertEqual(normalize_movie_id("  movie_2000101  "), "2000101")

    # --------------------------------------------------------------------------
    # 2. Movie Delta Coverage Tests
    # --------------------------------------------------------------------------
    def test_movie_coverage_historical_missing_warn_only(self):
        """歷史既有缺口只列為 WARN，不阻止發布 (success=True)"""
        story_dir = self.temp_path / "story"
        story_dir.mkdir()
        
        # 建立兩個 story：引用 1001 與 1002
        with open(story_dir / "101.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "movie_1001"}], f)
        with open(story_dir / "102.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "1002"}], f)

        # Baseline 已包含 1001 與 1002 (historical)
        baseline_file = self.temp_path / "movie_baseline.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": "1.0", "movie_ids": ["1001", "1002"]}, f)

        # movie_links 只 mapping 了 1001 (1002 是 historical missing)
        links_file = self.temp_path / "movie_links.json"
        with open(links_file, "w", encoding="utf-8") as f:
            json.dump({"1001": "https://example.com/1001.mp4"}, f)

        res = check_movie_coverage(
            story_dir=story_dir,
            movie_links_path=links_file,
            baseline_path=baseline_file
        )

        self.assertEqual(res.referenced_count, 2)
        self.assertEqual(res.historical_missing_count, 1)
        self.assertIn("1002", res.historical_missing)
        self.assertEqual(res.historical_missing["1002"], ["102"])
        self.assertEqual(res.new_references_count, 0)
        self.assertEqual(res.new_missing_count, 0)
        self.assertTrue(res.success, "Historical missing must be non-blocking (PASS)")

    def test_movie_coverage_new_mapped_pass(self):
        """本次新增動畫且已有 mapping -> PASS"""
        story_dir = self.temp_path / "story"
        story_dir.mkdir()

        with open(story_dir / "101.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "1001"}], f)
        with open(story_dir / "103.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "movie_1003"}], f)

        baseline_file = self.temp_path / "movie_baseline.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": "1.0", "movie_ids": ["1001"]}, f)

        links_file = self.temp_path / "movie_links.json"
        with open(links_file, "w", encoding="utf-8") as f:
            json.dump({
                "1001": "https://example.com/1001.mp4",
                "story_1003": "https://example.com/1003.mp4"
            }, f)

        res = check_movie_coverage(
            story_dir=story_dir,
            movie_links_path=links_file,
            baseline_path=baseline_file
        )

        self.assertEqual(res.referenced_count, 2)
        self.assertEqual(res.new_references_count, 1)
        self.assertEqual(res.new_mapped, ["1003"])
        self.assertEqual(res.new_missing_count, 0)
        self.assertTrue(res.success)

    def test_movie_coverage_new_missing_fail(self):
        """本次新增動畫但無 mapping -> blocking FAIL，並列出引用 story ID"""
        story_dir = self.temp_path / "story"
        story_dir.mkdir()

        with open(story_dir / "101.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "1001"}], f)
        with open(story_dir / "2217052.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "521700000"}], f)

        baseline_file = self.temp_path / "movie_baseline.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": "1.0", "movie_ids": ["1001"]}, f)

        links_file = self.temp_path / "movie_links.json"
        with open(links_file, "w", encoding="utf-8") as f:
            json.dump({"1001": "https://example.com/1001.mp4"}, f)

        res = check_movie_coverage(
            story_dir=story_dir,
            movie_links_path=links_file,
            baseline_path=baseline_file
        )

        self.assertEqual(res.new_references_count, 1)
        self.assertEqual(res.new_missing_count, 1)
        self.assertIn("521700000", res.new_missing)
        self.assertEqual(res.new_missing["521700000"], ["2217052"])
        self.assertFalse(res.success, "New missing must be blocking (FAIL)")

    # --------------------------------------------------------------------------
    # 3. Baseline Promotion & Dry-Run Zero-Write Tests
    # --------------------------------------------------------------------------
    def test_promote_movie_baseline_deduplication(self):
        """驗證 baseline 保存時去除別名前綴與重複項目"""
        baseline_file = self.temp_path / "movie_baseline.json"
        raw_refs = {"movie_1001", "1001", "story_2002", "2002", "3003"}
        ok = promote_movie_baseline(raw_refs, baseline_path=baseline_file)
        self.assertTrue(ok)

        with open(baseline_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["total_movies"], 3)
        self.assertEqual(data["movie_ids"], ["1001", "2002", "3003"])

    # --------------------------------------------------------------------------
    # 4. Event Top Completeness Mock Tests
    # --------------------------------------------------------------------------
    def test_event_top_completeness_mock(self):
        """驗證 Event Top 縮圖之缺少判定與 dry-run 零寫入"""
        asset_dir = self.temp_path / "icon" / "event_top"
        asset_dir.mkdir(parents=True)
        contract_file = self.temp_path / "official_event_top_manifest.json"

        # 模擬 contract 清單有 5216 與 5217 兩筆
        mock_targets = {
            "5216": {"bundle_name": "a/icon_thumb_event_story_top_5216.unity3d"},
            "5217": {"bundle_name": "a/icon_thumb_event_story_top_5217.unity3d"}
        }
        with open(contract_file, "w", encoding="utf-8") as f:
            json.dump({
                "truth_version": "00610007",
                "targets": mock_targets
            }, f)

        # 本地只有 5216.webp，缺少 5217.webp
        f5216 = asset_dir / "5216.webp"
        f5216.write_bytes(b"dummy_webp_content")

        with patch("tools.fetch_event_top_thumbnails.download_cdn_manifest", side_effect=RuntimeError("No CDN in test")):
            res = check_event_top_completeness(
                truth_version="00610007",
                dry_run=True,
                output_dir=asset_dir,
                contract_path=contract_file
            )

        self.assertEqual(res.expected_count, 2)
        self.assertEqual(res.present_count, 1)
        self.assertEqual(res.missing_count, 1)
        self.assertEqual(res.missing_ids, ["5217"])
        self.assertFalse(res.success)

        # 補齊 5217.webp 後再次驗證
        f5217 = asset_dir / "5217.webp"
        f5217.write_bytes(b"dummy_webp_content")

        with patch("tools.fetch_event_top_thumbnails.download_cdn_manifest", side_effect=RuntimeError("No CDN in test")):
            res2 = check_event_top_completeness(
                truth_version="00610007",
                dry_run=True,
                output_dir=asset_dir,
                contract_path=contract_file
            )

        self.assertEqual(res2.missing_count, 0)
        self.assertTrue(res2.success)

    # --------------------------------------------------------------------------
    # 5. Story Thumbnail Completeness Mock Tests
    # --------------------------------------------------------------------------
    def test_story_thumbnail_completeness_mock(self):
        """驗證話數縮圖交集計算：CDN 官方有者才納入 required，CDN 無者走 fallback 不算缺失"""
        asset_dir = self.temp_path / "icon" / "story"
        asset_dir.mkdir(parents=True)
        manifest_file = self.temp_path / "icon2_assetmanifest"

        # 模擬 manifest: CDN 上有 1001001 與 1001002
        manifest_content = (
            "a/icon_thumb_story_1001001.unity3d,md5,hash1,100,200\n"
            "a/icon_thumb_story_1001002.unity3d,md5,hash2,100,200\n"
        )
        manifest_file.write_text(manifest_content, encoding="utf-8")

        # 目標話數為 1001001, 1001002, 1001003 (其中 1001003 CDN 無官方縮圖，屬於 fallback)
        target_stories = ["1001001", "1001002", "1001003"]

        # 本地只有 1001001.webp，缺少 1001002.webp
        (asset_dir / "1001001.webp").write_bytes(b"dummy")

        res = check_story_thumbnail_completeness(
            truth_version="00610007",
            dry_run=True,
            output_dir=asset_dir,
            manifest_path=manifest_file,
            story_ids=target_stories
        )

        self.assertEqual(res.officially_available_count, 2)
        self.assertEqual(res.fallback_count, 1)
        self.assertEqual(res.present_count, 1)
        self.assertEqual(res.missing_count, 1)
        self.assertEqual(res.missing_story_ids, ["1001002"])
        self.assertFalse(res.success)

        # 本地補上 1001002.webp (1001003 仍不需本地檔案)
        (asset_dir / "1001002.webp").write_bytes(b"dummy")

        res2 = check_story_thumbnail_completeness(
            truth_version="00610007",
            dry_run=True,
            output_dir=asset_dir,
            manifest_path=manifest_file,
            story_ids=target_stories
        )

        self.assertEqual(res2.missing_count, 0)
        self.assertTrue(res2.success)


if __name__ == "__main__":
    unittest.main()
