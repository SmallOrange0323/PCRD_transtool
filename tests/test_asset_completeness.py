# -*- coding: utf-8 -*-
"""
test_asset_completeness.py — Asset Completeness Gate v1 最小單元測試
測試涵蓋：
  1. Movie ID 正規化 (movie_123, story_123, 123, 大小寫容錯)
  2. Movie Delta Coverage Policy:
     - historical missing -> WARN / non-blocking PASS
     - new mapped -> PASS
     - new missing -> blocking FAIL (回報引用該 movie 的 story ID)
     - empty/null mapping -> new missing -> FAIL
  3. Movie Baseline Promotion & Timing:
     - baseline 不含重複 prefix alias
     - Asset Gate 單獨呼叫時無副作用 (不得自行寫入 baseline)
     - Bundle 失敗時不得 promotion baseline
     - Validate 成功後精準 promotion 1 次
  4. Event Top Completeness:
     - CDN manifest 抓取失敗時 Fail-Closed (不得 fallback 至舊 contract)
     - Upstream identity change 檢測 (old hash != new hash -> stale -> FAIL)
     - New contract target 檢測 (CDN 有但舊 contract 沒有 -> stale -> FAIL)
  5. Story Thumbnail Completeness:
     - stale-manifest 防禦 (不信任本地舊 manifest，以 CDN 為唯一權威)
     - fallback 不算 missing
     - dry-run 零寫入
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
from pipeline.update import run_pipeline_update
from pipeline.coverage import FreshnessResult, FreshnessStatus, CoverageResult, CoverageAnalysisStatus


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
        
        with open(story_dir / "101.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "movie_1001"}], f)
        with open(story_dir / "102.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "1002"}], f)

        baseline_file = self.temp_path / "movie_baseline.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": "1.0", "movie_ids": ["1001", "1002"]}, f)

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

    def test_movie_coverage_empty_mapping_fail(self):
        """空字串、空白或 null 之 mapping value 視為無效 mapping -> new missing -> FAIL"""
        story_dir = self.temp_path / "story"
        story_dir.mkdir()

        with open(story_dir / "101.json", "w", encoding="utf-8") as f:
            json.dump([{"type": "movie", "movie_id": "1003"}], f)

        baseline_file = self.temp_path / "movie_baseline.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": "1.0", "movie_ids": []}, f)

        # 存在 1003 但 mapping value 為空字串
        links_file = self.temp_path / "movie_links.json"
        with open(links_file, "w", encoding="utf-8") as f:
            json.dump({"1003": "", "1004": "   ", "1005": None}, f)

        res = check_movie_coverage(
            story_dir=story_dir,
            movie_links_path=links_file,
            baseline_path=baseline_file
        )

        self.assertEqual(res.new_references_count, 1)
        self.assertEqual(res.new_missing_count, 1)
        self.assertIn("1003", res.new_missing)
        self.assertFalse(res.success, "Empty mapping string must NOT count as mapped")

    # --------------------------------------------------------------------------
    # 3. Baseline Promotion & Timing Tests
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

    def test_asset_gate_side_effect_free_baseline(self):
        """單獨呼叫 analyze_asset_completeness() 必須零副作用，不得自行執行 promotion"""
        with patch("pipeline.assets.check_event_top_completeness") as mock_et, \
             patch("pipeline.assets.check_story_thumbnail_completeness") as mock_st, \
             patch("pipeline.assets.check_movie_coverage") as mock_mv, \
             patch("pipeline.assets.promote_movie_baseline") as mock_promote:

            mock_et.return_value = EventTopCompletenessResult(success=True)
            mock_st.return_value = StoryThumbnailCompletenessResult(success=True)
            mock_mv.return_value = MovieCoverageResult(new_references_count=2, new_missing_count=0, success=True)

            res = analyze_asset_completeness(dry_run=False)
            self.assertTrue(res.success)
            mock_promote.assert_not_called()

    def test_pipeline_promotion_timing_on_bundle_failure(self):
        """管線在 Bundle 失敗時，不得晉升 baseline"""
        freshness_dummy = MagicMock(spec=FreshnessResult)
        freshness_dummy.confirmed = True
        freshness_dummy.remote_version = "00610007"
        freshness_dummy.status = FreshnessStatus.CONFIRMED_CURRENT

        cov_dummy = MagicMock(spec=CoverageResult)
        cov_dummy.analysis_status = CoverageAnalysisStatus.VALID
        cov_dummy.unknown_expected_count = 0
        cov_dummy.missing_unknown_count = 0
        cov_dummy.missing_required_count = 0

        asset_dummy = AssetCompletenessResult(
            movie_coverage=MovieCoverageResult(new_references_count=1, new_missing_count=0, success=True),
            success=True
        )

        with patch("pipeline.update.check_and_sync_upstream", return_value=(True, freshness_dummy, cov_dummy)), \
             patch("pipeline.update.analyze_asset_completeness", return_value=asset_dummy), \
             patch("pipeline.update.bundle_story_map", return_value=False), \
             patch("pipeline.assets.promote_movie_baseline") as mock_promote:

            code = run_pipeline_update(dry_run=False, auto_deploy=False)
            self.assertEqual(code, 1)
            mock_promote.assert_not_called()

    def test_pipeline_promotion_timing_on_validate_success(self):
        """管線在 Validate 成功後，精確晉升 baseline 一次"""
        freshness_dummy = MagicMock(spec=FreshnessResult)
        freshness_dummy.confirmed = True
        freshness_dummy.remote_version = "00610007"
        freshness_dummy.status = FreshnessStatus.CONFIRMED_CURRENT

        cov_dummy = MagicMock(spec=CoverageResult)
        cov_dummy.analysis_status = CoverageAnalysisStatus.VALID
        cov_dummy.unknown_expected_count = 0
        cov_dummy.missing_unknown_count = 0
        cov_dummy.missing_required_count = 0

        asset_dummy = AssetCompletenessResult(
            movie_coverage=MovieCoverageResult(new_references_count=1, new_missing_count=0, success=True),
            success=True
        )

        with patch("pipeline.update.check_and_sync_upstream", return_value=(True, freshness_dummy, cov_dummy)), \
             patch("pipeline.update.analyze_asset_completeness", return_value=asset_dummy), \
             patch("pipeline.update.bundle_story_map", return_value=True), \
             patch("pipeline.update.validate_story_map", return_value=True), \
             patch("pipeline.assets.promote_movie_baseline", return_value=True) as mock_promote:

            code = run_pipeline_update(dry_run=False, auto_deploy=False)
            self.assertEqual(code, 0)
            mock_promote.assert_called_once()

    # --------------------------------------------------------------------------
    # 4. Event Top Completeness Mock Tests
    # --------------------------------------------------------------------------
    def test_event_top_cdn_unavailable_fail_closed(self):
        """CDN manifest 抓取失敗時必須 Fail-Closed，嚴禁 fallback 至舊 contract 判定 PASS"""
        asset_dir = self.temp_path / "icon" / "event_top"
        asset_dir.mkdir(parents=True)
        contract_file = self.temp_path / "official_event_top_manifest.json"

        # 即使舊 contract 存在且本地檔案齊全
        mock_targets = {
            "5216": {"bundle_name": "a/icon_thumb_event_story_top_5216.unity3d"}
        }
        with open(contract_file, "w", encoding="utf-8") as f:
            json.dump({"truth_version": "00610007", "targets": mock_targets}, f)
        (asset_dir / "5216.webp").write_bytes(b"dummy")

        with patch("tools.fetch_event_top_thumbnails.download_cdn_manifest", side_effect=RuntimeError("CDN manifest 404")):
            res = check_event_top_completeness(
                truth_version="00610007",
                dry_run=True,
                output_dir=asset_dir,
                contract_path=contract_file
            )

        self.assertFalse(res.success, "CDN failure must fail closed")

    def test_event_top_identity_change_detection(self):
        """同 ID 但 hash 改變 -> stale -> FAIL"""
        asset_dir = self.temp_path / "icon" / "event_top"
        asset_dir.mkdir(parents=True)
        contract_file = self.temp_path / "official_event_top_manifest.json"

        old_targets = {
            "5216": {
                "bundle_name": "a/icon_thumb_event_story_top_5216.unity3d",
                "bundle_md5": "old_md5",
                "pool_hash": "old_hash",
                "bundle_size": 1000
            }
        }
        with open(contract_file, "w", encoding="utf-8") as f:
            json.dump({"truth_version": "00610007", "targets": old_targets}, f)

        (asset_dir / "5216.webp").write_bytes(b"dummy_webp")
        cdn_manifest_text = "a/icon_thumb_event_story_top_5216.unity3d,new_md5,new_hash,header,2000\n"

        with patch("tools.fetch_event_top_thumbnails.download_cdn_manifest", return_value=cdn_manifest_text):
            res = check_event_top_completeness(
                truth_version="00610008",
                dry_run=True,
                output_dir=asset_dir,
                contract_path=contract_file
            )

        self.assertEqual(res.expected_count, 1)
        self.assertEqual(res.present_count, 1)
        self.assertEqual(res.stale_count, 1)
        self.assertEqual(res.stale_ids, ["5216"])
        self.assertFalse(res.success, "Identity change must be detected and marked as FAIL in dry-run")

    def test_event_top_new_contract_target_detection(self):
        """current CDN 有 5219，舊 contract 沒有 5219，即使本地已有 5219.webp 亦必須標為 stale/changed"""
        asset_dir = self.temp_path / "icon" / "event_top"
        asset_dir.mkdir(parents=True)
        contract_file = self.temp_path / "official_event_top_manifest.json"

        old_targets = {
            "5216": {
                "bundle_name": "a/icon_thumb_event_story_top_5216.unity3d",
                "bundle_md5": "md5_5216",
                "pool_hash": "hash_5216",
                "bundle_size": 1000
            }
        }
        with open(contract_file, "w", encoding="utf-8") as f:
            json.dump({"truth_version": "00610007", "targets": old_targets}, f)

        # 本地 5216 與 5219 都存在
        (asset_dir / "5216.webp").write_bytes(b"dummy_5216")
        (asset_dir / "5219.webp").write_bytes(b"dummy_5219")

        cdn_manifest_text = (
            "a/icon_thumb_event_story_top_5216.unity3d,md5_5216,hash_5216,header,1000\n"
            "a/icon_thumb_event_story_top_5219.unity3d,md5_5219,hash_5219,header,1000\n"
        )

        with patch("tools.fetch_event_top_thumbnails.download_cdn_manifest", return_value=cdn_manifest_text):
            res = check_event_top_completeness(
                truth_version="00610008",
                dry_run=True,
                output_dir=asset_dir,
                contract_path=contract_file
            )

        self.assertEqual(res.expected_count, 2)
        self.assertEqual(res.missing_count, 0)
        self.assertEqual(res.stale_count, 1)
        self.assertEqual(res.stale_ids, ["5219"])
        self.assertFalse(res.success, "New target in CDN not present in contract must be detected as stale")

    # --------------------------------------------------------------------------
    # 5. Story Thumbnail Completeness Mock Tests
    # --------------------------------------------------------------------------
    def test_story_thumbnail_stale_local_manifest_regression(self):
        """
        Regression Test:
        本地存在舊 manifest (只含 1001001)；
        線上 TruthVersion CDN manifest 含有 1001001 與 1001002；
        目標話數包含兩話，但本地缺少 1001002.webp。
        Gate 必須向 CDN 抓取權威清單，判定 missing = 1001002 並 FAIL，嚴禁信任本地舊清單假 PASS。
        """
        asset_dir = self.temp_path / "icon" / "story"
        asset_dir.mkdir(parents=True)
        local_manifest_file = self.temp_path / "icon2_assetmanifest"

        local_manifest_file.write_text("a/icon_thumb_story_1001001.unity3d,md5,hash1,100,200\n", encoding="utf-8")
        (asset_dir / "1001001.webp").write_bytes(b"dummy")

        cdn_manifest_bytes = (
            b"a/icon_thumb_story_1001001.unity3d,md5,hash1,100,200\n"
            b"a/icon_thumb_story_1001002.unity3d,md5,hash2,100,200\n"
        )

        class FakeResp:
            def read(self):
                return cdn_manifest_bytes
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            res = check_story_thumbnail_completeness(
                truth_version="00610008",
                dry_run=True,
                output_dir=asset_dir,
                manifest_path=local_manifest_file,
                story_ids=["1001001", "1001002"]
            )

        self.assertEqual(res.officially_available_count, 2)
        self.assertEqual(res.missing_count, 1)
        self.assertEqual(res.missing_story_ids, ["1001002"])
        self.assertFalse(res.success, "Must fail because CDN has 1001002 thumbnail but local is missing")

    def test_story_thumbnail_completeness_fallback_not_missing(self):
        """驗證話數縮圖 fallback：CDN 無官方縮圖之項目不視為 missing"""
        asset_dir = self.temp_path / "icon" / "story"
        asset_dir.mkdir(parents=True)

        cdn_manifest_bytes = b"a/icon_thumb_story_1001001.unity3d,md5,hash1,100,200\n"
        (asset_dir / "1001001.webp").write_bytes(b"dummy")

        class FakeResp:
            def read(self):
                return cdn_manifest_bytes
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            res = check_story_thumbnail_completeness(
                truth_version="00610007",
                dry_run=True,
                output_dir=asset_dir,
                story_ids=["1001001", "1001003"]
            )

        self.assertEqual(res.officially_available_count, 1)
        self.assertEqual(res.fallback_count, 1)
        self.assertEqual(res.missing_count, 0)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
