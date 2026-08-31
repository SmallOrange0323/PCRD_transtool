#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Pages Recovery P3A Bundle Slimming & Pruning Unit Tests
包含：
1. 原有完整回歸覆蓋：
   - card/full 與 sound/story_vo 同步行為
   - card/sound 在 deployment footprint 中的安全排除
   - 動態渲染 index.html 大小增長精確反映於 dry-run 預估
   - legacy -> canonical icon 映射精確計入 dry-run 預估
2. P3A 契約與安全門禁覆蓋：
   - dashboard/still/story 來源資產不受影響 (隔離 fixture & real directory 存在性驗證)
   - dist/still/story 在 bundle 時被完全排除與清理
   - 歷史殘留目錄 (icon/still_unit, icon/debug_new, icon/debug_specific) 被安全移除
   - 重複 DB (redive_tw-DESKTOP-*.db) 被移除，而 redive_tw.db 被保留
   - icon/unit 精準保留 expected set，清理 surplus 圖片，未知副檔名保持不動
   - 鏡像目錄 (story/*.json, data/*.json, still/bg/*, still/scenario/*) 若 source 缺失則 dist 端 prune
   - .git 目錄與內部檔案具備絕對防禦保護
   - outside-DIST prune 安全拒絕
   - dry-run 真正零副作用
   - .nojekyll 缺失時建立、非空時正規化為 0 bytes
   - Footprint gate 閾值判定 (PASS, WARN >= 750MiB, HARD ERROR >= 900MiB)
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    is_safe_dist_path,
    safe_prune_file,
    safe_prune_dir,
    prune_stale_dist_assets,
    build_expected_icon_unit_set,
    get_expected_icon_unit_mappings,
    render_index_html,
    sync_nojekyll,
    calculate_expected_additions_and_deltas,
    sync_directory_assets,
    DASHBOARD_DIR,
    DIST_DIR
)
from pipeline.validate import (
    check_footprint_gate,
    calculate_deployment_footprint,
    FOOTPRINT_WARN_BYTES,
    FOOTPRINT_HARD_BYTES
)

class TestBundleSlimmingAndPrune(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pcrd_bundle_test_")
        self.mock_root = Path(self.temp_dir)
        self.mock_dash = self.mock_root / "dashboard"
        self.mock_dist = self.mock_root / "dist_story_map"
        self.mock_dash.mkdir(parents=True, exist_ok=True)
        self.mock_dist.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    # 1. dashboard/still/story source assets preserved (non-fragile check)
    def test_01_dashboard_still_story_source_preserved(self):
        """確保 dashboard/still/story 來源資產不受 bundle 影響 (使用 isolated fixture 與 real-repo 非死板斷言)"""
        # 1. 隔離 fixture 測試
        dash_still = self.mock_dash / "still" / "story"
        dash_still.mkdir(parents=True, exist_ok=True)
        (dash_still / "sample_cg.webp").write_bytes(b"source_cg_bytes")

        dist_still = self.mock_dist / "still" / "story"
        dist_still.mkdir(parents=True, exist_ok=True)
        (dist_still / "stale_cg.webp").write_bytes(b"dist_stale_bytes")

        prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertTrue((dash_still / "sample_cg.webp").exists(), "dashboard/still/story 來源檔案必須保持完整")
        self.assertFalse((dist_still / "stale_cg.webp").exists(), "dist 端 stale 檔案應被清除")

        # 2. 真實倉庫健全性檢查 (不硬編碼特定數字)
        real_dash_still = DASHBOARD_DIR / "still" / "story"
        if real_dash_still.exists():
            files = list(real_dash_still.glob("*.webp"))
            self.assertGreater(len(files), 0, "dashboard/still/story 應包含 WebP CG 檔案且不為空")

    # 2. dist/still/story stale asset removed
    def test_02_dist_still_story_stale_asset_removed(self):
        dist_still = self.mock_dist / "still" / "story"
        dist_still.mkdir(parents=True, exist_ok=True)
        stale_file = dist_still / "100500801.webp"
        stale_file.write_bytes(b"dummy_webp")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("still/story", prune_stats)
        self.assertEqual(prune_stats["still/story"][0], 1)
        self.assertFalse(stale_file.exists())
        self.assertFalse(dist_still.exists())

    # 3. icon/still_unit removed
    def test_03_icon_still_unit_removed(self):
        p = self.mock_dist / "icon" / "still_unit"
        p.mkdir(parents=True, exist_ok=True)
        (p / "sample.png").write_bytes(b"img")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("icon/still_unit", prune_stats)
        self.assertFalse(p.exists())

    # 4. icon/debug_new removed
    def test_04_icon_debug_new_removed(self):
        p = self.mock_dist / "icon" / "debug_new"
        p.mkdir(parents=True, exist_ok=True)
        (p / "sample.png").write_bytes(b"img")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("icon/debug_new", prune_stats)
        self.assertFalse(p.exists())

    # 5. icon/debug_specific removed
    def test_05_icon_debug_specific_removed(self):
        p = self.mock_dist / "icon" / "debug_specific"
        p.mkdir(parents=True, exist_ok=True)
        (p / "sample.png").write_bytes(b"img")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("icon/debug_specific", prune_stats)
        self.assertFalse(p.exists())

    # 6. duplicate stale DB x2 removed
    def test_06_duplicate_stale_db_removed(self):
        dup1 = self.mock_dist / "redive_tw-DESKTOP-N6EC182.db"
        dup1.write_bytes(b"dup1")
        dup2 = self.mock_dist / "redive_tw-DESKTOP-N6EC182-2.db"
        dup2.write_bytes(b"dup2")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("duplicate DB", prune_stats)
        self.assertEqual(prune_stats["duplicate DB"][0], 2)
        self.assertFalse(dup1.exists())
        self.assertFalse(dup2.exists())

    # 7. redive_tw.db preserved
    def test_07_redive_tw_db_preserved(self):
        canon_db = self.mock_dist / "redive_tw.db"
        canon_db.write_bytes(b"canon_db")

        prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertTrue(canon_db.exists(), "redive_tw.db 必須完整保留")

    # 8. icon/unit canonical image preserved
    def test_08_icon_unit_canonical_image_preserved(self):
        dash_data = self.mock_dash / "data"
        dash_data.mkdir(parents=True, exist_ok=True)
        (dash_data / "tracked_characters.json").write_text(
            '{"characters": [{"icon_ids": [100101]}]}', encoding="utf-8"
        )
        dash_unit = self.mock_dash / "icon" / "unit"
        dash_unit.mkdir(parents=True, exist_ok=True)
        (dash_unit / "100101.webp").write_bytes(b"ok")

        dist_unit = self.mock_dist / "icon" / "unit"
        dist_unit.mkdir(parents=True, exist_ok=True)
        canon_file = dist_unit / "100101.webp"
        canon_file.write_bytes(b"ok")

        prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertTrue(canon_file.exists(), "預期的 canonical icon 必須保留")

    # 9. icon/unit surplus .png/.webp removed
    def test_09_icon_unit_surplus_png_webp_removed(self):
        dash_data = self.mock_dash / "data"
        dash_data.mkdir(parents=True, exist_ok=True)
        (dash_data / "tracked_characters.json").write_text('{"characters": []}', encoding="utf-8")

        dist_unit = self.mock_dist / "icon" / "unit"
        dist_unit.mkdir(parents=True, exist_ok=True)
        surplus1 = dist_unit / "888888.png"
        surplus2 = dist_unit / "999999.webp"
        surplus1.write_bytes(b"s1")
        surplus2.write_bytes(b"s2")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("icon/unit surplus", prune_stats)
        self.assertEqual(prune_stats["icon/unit surplus"][0], 2)
        self.assertFalse(surplus1.exists())
        self.assertFalse(surplus2.exists())

    # 10. icon/unit unrelated extension preserved
    def test_10_icon_unit_unrelated_extension_preserved(self):
        dist_unit = self.mock_dist / "icon" / "unit"
        dist_unit.mkdir(parents=True, exist_ok=True)
        txt_file = dist_unit / "notes.txt"
        json_file = dist_unit / "config.json"
        txt_file.write_text("keep", encoding="utf-8")
        json_file.write_text("{}", encoding="utf-8")

        prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertTrue(txt_file.exists(), "非 png/webp 未知檔案應被保留")
        self.assertTrue(json_file.exists(), "非 png/webp 未知檔案應被保留")

    # 11. stale mirrored story JSON pruned
    def test_11_stale_mirrored_story_json_pruned(self):
        dash_story = self.mock_dash / "story"
        dash_story.mkdir(parents=True, exist_ok=True)
        (dash_story / "1001.json").write_text("[]", encoding="utf-8")

        dist_story = self.mock_dist / "story"
        dist_story.mkdir(parents=True, exist_ok=True)
        (dist_story / "1001.json").write_text("[]", encoding="utf-8")
        (dist_story / "9999.json").write_text("[]", encoding="utf-8")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("stale story JSON", prune_stats)
        self.assertTrue((dist_story / "1001.json").exists())
        self.assertFalse((dist_story / "9999.json").exists())

    # 12. stale mirrored data JSON pruned
    def test_12_stale_mirrored_data_json_pruned(self):
        dash_data = self.mock_dash / "data"
        dash_data.mkdir(parents=True, exist_ok=True)
        (dash_data / "chapters.json").write_text("{}", encoding="utf-8")

        dist_data = self.mock_dist / "data"
        dist_data.mkdir(parents=True, exist_ok=True)
        (dist_data / "chapters.json").write_text("{}", encoding="utf-8")
        (dist_data / "db_info.json").write_text("{}", encoding="utf-8")
        (dist_data / "obsolete.json").write_text("{}", encoding="utf-8")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("stale data JSON", prune_stats)
        self.assertTrue((dist_data / "chapters.json").exists())
        self.assertTrue((dist_data / "db_info.json").exists())
        self.assertFalse((dist_data / "obsolete.json").exists())

    # 13. dist .git protected
    def test_13_dist_git_protected(self):
        git_dir = self.mock_dist / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        git_head = git_dir / "HEAD"
        git_head.write_text("ref: refs/heads/main\n", encoding="utf-8")

        self.assertFalse(is_safe_dist_path(git_dir, self.mock_dist))
        self.assertFalse(is_safe_dist_path(git_head, self.mock_dist))

        cnt, _ = safe_prune_file(git_head, dry_run=False, dist_root=self.mock_dist)
        self.assertEqual(cnt, 0)
        self.assertTrue(git_head.exists())

        cnt, _ = safe_prune_dir(git_dir, dry_run=False, dist_root=self.mock_dist)
        self.assertEqual(cnt, 0)
        self.assertTrue(git_dir.exists())

    # 14. unsafe outside-DIST prune rejected
    def test_14_unsafe_outside_dist_prune_rejected(self):
        outside_file = self.mock_root / "outside.txt"
        outside_file.write_text("do not delete", encoding="utf-8")

        self.assertFalse(is_safe_dist_path(outside_file, self.mock_dist))
        cnt, _ = safe_prune_file(outside_file, dry_run=False, dist_root=self.mock_dist)
        self.assertEqual(cnt, 0)
        self.assertTrue(outside_file.exists())

    # 15. dry-run zero filesystem side effect
    def test_15_dry_run_zero_filesystem_side_effect(self):
        dup_file = self.mock_dist / "redive_tw-DESKTOP-N6EC182.db"
        dup_file.write_bytes(b"content")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=True)
        self.assertIn("duplicate DB", prune_stats)
        self.assertEqual(prune_stats["duplicate DB"][0], 1)
        self.assertTrue(dup_file.exists(), "Dry-run 下檔案不可被刪除")

    # 16. .nojekyll created size 0 & normalized
    def test_16_nojekyll_management(self):
        nojekyll = self.mock_dist / ".nojekyll"
        
        # 1. 缺失時建立
        if nojekyll.exists():
            nojekyll.unlink()
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "created")
        self.assertTrue(nojekyll.exists())
        self.assertEqual(nojekyll.stat().st_size, 0)

        # 2. 非空時正規化
        nojekyll.write_text("non-empty", encoding="utf-8")
        self.assertGreater(nojekyll.stat().st_size, 0)
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "normalized")
        self.assertEqual(nojekyll.stat().st_size, 0)

        # 3. 已經為 0 bytes 時保持
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "unchanged")
        self.assertEqual(nojekyll.stat().st_size, 0)

    # 17. footprint small fixture PASS
    def test_17_footprint_small_fixture_pass(self):
        small_bytes = 200 * 1024 * 1024
        is_p, msg, _ = check_footprint_gate(footprint_bytes=small_bytes)
        self.assertTrue(is_p)
        self.assertIn("PASS", msg)

    # 18. synthetic/mock >= 900 MiB FAIL
    def test_18_footprint_mock_900mib_fail(self):
        hard_bytes = 950 * 1024 * 1024
        is_p, msg, _ = check_footprint_gate(footprint_bytes=hard_bytes)
        self.assertFalse(is_p)
        self.assertIn("HARD ERROR", msg)

    # 19. card/full and sound/story_vo sync and footprint exclusion (Restored & Enhanced)
    def test_19_card_and_voice_sync_and_footprint_exclusion(self):
        """確保 card/full 與 sound/story_vo 正常同步至本地發布包，且被 Pages footprint 正確排除"""
        dash_card = self.mock_dash / "card" / "full"
        dash_voice = self.mock_dash / "sound" / "story_vo"
        dash_card.mkdir(parents=True, exist_ok=True)
        dash_voice.mkdir(parents=True, exist_ok=True)

        (dash_card / "100131.webp").write_bytes(b"card_image_bytes_12345")
        (dash_voice / "vo_1001.m4a").write_bytes(b"voice_audio_bytes_67890")

        dist_card = self.mock_dist / "card" / "full"
        dist_voice = self.mock_dist / "sound" / "story_vo"

        # 執行同步
        c1 = sync_directory_assets(dash_card, dist_card, [".webp", ".png"], dry_run=False)
        c2 = sync_directory_assets(dash_voice, dist_voice, [".m4a"], dry_run=False)

        self.assertEqual(c1, 1)
        self.assertEqual(c2, 1)
        self.assertTrue((dist_card / "100131.webp").exists())
        self.assertTrue((dist_voice / "vo_1001.m4a").exists())

        # 測試 calculate_deployment_footprint 是否正確排除 card/ 與 sound/
        footprint = calculate_deployment_footprint(self.mock_dist)
        self.assertEqual(footprint, 0, "card/ 與 sound/ 應被排除在 deployment footprint 之外")

    # 20. dynamic rendered index.html growth reflected in dry-run estimate (Restored & Enhanced)
    def test_20_generated_index_growth_projection(self):
        """確保動態渲染 index.html 大小精確反映於 dry-run 預估 (非 hardcoded 大小)"""
        (self.mock_dash / "story_map.html").write_text('<script src="db.js"></script><script src="chapter-data.js"></script>', encoding="utf-8")
        (self.mock_dash / "db.js").write_text('console.log("initial db code");', encoding="utf-8")
        (self.mock_dash / "chapter-data.js").write_text('console.log("initial chapter code");', encoding="utf-8")
        for js in ["characters.js", "avatar-service.js", "speaker-view.js", "chara-modal.js", "dialogue-normalizer.js", "media-service.js", "dialogue-view.js", "map.js"]:
            (self.mock_dash / js).write_text(f'// {js}', encoding="utf-8")
            (self.mock_dist / js).write_text(f'// {js}', encoding="utf-8")
        (self.mock_dist / "db.js").write_text('console.log("initial db code");', encoding="utf-8")
        (self.mock_dist / "chapter-data.js").write_text('console.log("initial chapter code");', encoding="utf-8")

        # 隔離 db_info.json
        (self.mock_dist / "data").mkdir(parents=True, exist_ok=True)
        sim_db_info = json.dumps({"db_version": "hash_nodata", "tw_size": 0, "jp_size": 0}, ensure_ascii=False, indent=2).encode("utf-8")
        (self.mock_dist / "data" / "db_info.json").write_bytes(sim_db_info)

        rendered1 = render_index_html(self.mock_dash)
        size1 = len(rendered1.encode("utf-8"))

        add1, delta1 = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(add1, size1)

        # 寫入 dist index.html
        (self.mock_dist / "index.html").write_bytes(rendered1.encode("utf-8"))

        # 擴展 db.js 增加 5000 bytes
        extra_content = "/* " + ("x" * 5000) + " */"
        (self.mock_dash / "db.js").write_text('console.log("initial db code");' + extra_content, encoding="utf-8")

        rendered2 = render_index_html(self.mock_dash)
        expected_index_delta = len(rendered2.encode("utf-8")) - len(rendered1.encode("utf-8"))
        expected_db_delta = (self.mock_dash / "db.js").stat().st_size - (self.mock_dist / "db.js").stat().st_size

        add2, delta2 = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(delta2, expected_index_delta + expected_db_delta, "dry-run delta 必須精確等於渲染後 index.html 及更新檔案的實際 byte 差值")

    # 21. legacy to canonical icon mapping in dry-run estimate (Restored & Enhanced)
    def test_21_legacy_to_canonical_icon_projection(self):
        """確保 Legacy -> Canonical icon 映射精確計入 dry-run 預估"""
        dash_data = self.mock_dash / "data"
        dist_data = self.mock_dist / "data"
        dash_data.mkdir(parents=True, exist_ok=True)
        dist_data.mkdir(parents=True, exist_ok=True)

        tracked_json = '{"characters": [{"icon_ids": [100201]}]}'
        (dash_data / "tracked_characters.json").write_text(tracked_json, encoding="utf-8")
        (dist_data / "tracked_characters.json").write_text(tracked_json, encoding="utf-8")

        # 隔離 db_info.json
        sim_db_info = json.dumps({"db_version": "hash_nodata", "tw_size": 0, "jp_size": 0}, ensure_ascii=False, indent=2).encode("utf-8")
        (dist_data / "db_info.json").write_bytes(sim_db_info)

        dash_unit = self.mock_dash / "icon" / "unit"
        dash_unit.mkdir(parents=True, exist_ok=True)
        
        # 僅提供 legacy 檔案 unit_icon_100201.webp
        legacy_file = dash_unit / "unit_icon_100201.webp"
        legacy_file.write_bytes(b"legacy_icon_content_123456")
        file_sz = len(b"legacy_icon_content_123456")

        mappings = get_expected_icon_unit_mappings(self.mock_dash)
        self.assertIn("100201.webp", mappings)
        self.assertIn("unit_icon_100201.webp", mappings)
        self.assertEqual(mappings["100201.webp"], legacy_file)

        additions, deltas = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(additions, file_sz * 2, "dry-run 預估應精確包含 legacy 及由其映射生成之 canonical icon 大小")

if __name__ == "__main__":
    unittest.main(verbosity=2)
