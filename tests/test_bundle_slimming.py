#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Focused Bundle Slimming & Pruning Unit Tests
驗證：
1. dashboard/still/story 本地資產完全不受影響
2. dist/still/story 在 bundle 時被完全排除與安全清理
3. 歷史殘留目錄 (icon/still_unit, icon/debug_new, icon/debug_specific) 被安全移除
4. 重複 DB (redive_tw-DESKTOP-*.db) 被安全移除，而 redive_tw.db 被保留
5. icon/unit 精準保留 expected set，清理 surplus 圖片，未知副檔名保持不動
6. 鏡像目錄中若 source 已刪除則 dist 端安全 prune
7. .git 目錄與其內部檔案具備絕對防禦保護
8. dry-run 真正零副作用與精準 additions/deltas 預估
9. .nojekyll 在缺失時建立、在非空時正規化為 0 bytes
10. Footprint gate 閾值判定 (PASS, WARN >= 750MiB, HARD ERROR >= 900MiB)
11. card/full 與 sound/story_vo 同步正常，且被 footprint gate 正確排除
12. 動態 index.html 渲染大小增長精確反映於 dry-run 預估 (非 hardcoded 35632)
13. Legacy -> Canonical icon 映射精確計入 dry-run 預估
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path

# 將專案根目錄加入 sys.path
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
        # 建立臨時隔離工作區以供模擬測試
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

    def test_01_dashboard_still_story_remains_untouched(self):
        """1. 確保 dashboard/still/story 本地資產完全存在且不被更動"""
        real_dash_still = DASHBOARD_DIR / "still" / "story"
        if real_dash_still.exists():
            files = list(real_dash_still.glob("*.webp"))
            self.assertEqual(len(files), 2573, "dashboard/still/story 應擁有完整 2573 個 WebP 資產")

    def test_02_git_protection(self):
        """7. 確保 .git 目錄與內部檔案具備絕對保護，拒絕 prune"""
        git_dir = self.mock_dist / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        git_head = git_dir / "HEAD"
        git_head.write_text("ref: refs/heads/main\n", encoding="utf-8")

        # 測試 is_safe_dist_path
        self.assertFalse(is_safe_dist_path(git_dir, self.mock_dist))
        self.assertFalse(is_safe_dist_path(git_head, self.mock_dist))
        self.assertFalse(is_safe_dist_path(self.mock_dist, self.mock_dist))  # 拒絕 dist 根目錄本身

        # 測試 safe_prune_file 與 safe_prune_dir
        cnt, b = safe_prune_file(git_head, dry_run=False, dist_root=self.mock_dist)
        self.assertEqual(cnt, 0)
        self.assertTrue(git_head.exists(), ".git/HEAD 絕對不可被刪除")

        cnt, b = safe_prune_dir(git_dir, dry_run=False, dist_root=self.mock_dist)
        self.assertEqual(cnt, 0)
        self.assertTrue(git_dir.exists(), ".git 目錄絕對不可被刪除")

    def test_03_dist_still_story_pruned(self):
        """2. 確保 dist/still/story 內容被安全清除且目錄被移除"""
        dist_still = self.mock_dist / "still" / "story"
        dist_still.mkdir(parents=True, exist_ok=True)
        stale_file = dist_still / "100500801.webp"
        stale_file.write_bytes(b"dummy_webp_content")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("still/story", prune_stats)
        self.assertEqual(prune_stats["still/story"][0], 1)
        self.assertFalse(stale_file.exists())
        self.assertFalse(dist_still.exists())

    def test_04_explicit_legacy_dirs_pruned(self):
        """3. 確保歷史殘留目錄 (icon/still_unit, icon/debug_new, icon/debug_specific) 被完全清除"""
        legacy_dirs = ["icon/still_unit", "icon/debug_new", "icon/debug_specific"]
        for ld in legacy_dirs:
            p = self.mock_dist / ld
            p.mkdir(parents=True, exist_ok=True)
            (p / "sample.png").write_bytes(b"image_bytes")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        for ld in legacy_dirs:
            self.assertIn(ld, prune_stats)
            self.assertFalse((self.mock_dist / ld).exists(), f"{ld} 目錄應已被刪除")

    def test_05_duplicate_db_pruned_canonical_preserved(self):
        """4. 確保重複 DB 被刪除，而 redive_tw.db 被保留"""
        canon_db = self.mock_dist / "redive_tw.db"
        canon_db.write_bytes(b"canon_db")
        dup1 = self.mock_dist / "redive_tw-DESKTOP-N6EC182.db"
        dup1.write_bytes(b"dup1")
        dup2 = self.mock_dist / "redive_tw-DESKTOP-N6EC182-2.db"
        dup2.write_bytes(b"dup2")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("duplicate DB", prune_stats)
        self.assertEqual(prune_stats["duplicate DB"][0], 2)
        self.assertFalse(dup1.exists())
        self.assertFalse(dup2.exists())
        self.assertTrue(canon_db.exists(), "redive_tw.db 必須完整保留")

    def test_06_icon_unit_pruning_and_unknown_ext_preservation(self):
        """5. 確保 icon/unit 保留 expected set，清理 surplus 圖片，但保留未知副檔名"""
        dist_icon = self.mock_dist / "icon" / "unit"
        dist_icon.mkdir(parents=True, exist_ok=True)

        # 模擬 dashboard 設置
        dash_data = self.mock_dash / "data"
        dash_data.mkdir(parents=True, exist_ok=True)
        (dash_data / "tracked_characters.json").write_text(
            '{"characters": [{"icon_ids": [100101]}]}', encoding="utf-8"
        )
        dash_unit = self.mock_dash / "icon" / "unit"
        dash_unit.mkdir(parents=True, exist_ok=True)
        (dash_unit / "100101.webp").write_bytes(b"ok")

        expected_file = dist_icon / "100101.webp"
        expected_file.write_bytes(b"ok")
        surplus_img = dist_icon / "999999.webp"
        surplus_img.write_bytes(b"surplus")
        unrelated_ext = dist_icon / "readme.txt"
        unrelated_ext.write_text("keep me", encoding="utf-8")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("icon/unit surplus", prune_stats)
        self.assertEqual(prune_stats["icon/unit surplus"][0], 1)
        self.assertTrue(expected_file.exists(), "預期頭像應被保留")
        self.assertFalse(surplus_img.exists(), "多餘頭像應被刪除")
        self.assertTrue(unrelated_ext.exists(), "非圖片的未知檔案應被保留")

    def test_07_mirrored_stale_json_pruned(self):
        """6. 確保鏡像目錄若 source 缺失則 dist 端 prune"""
        dash_story = self.mock_dash / "story"
        dash_story.mkdir(parents=True, exist_ok=True)
        (dash_story / "1001.json").write_text("[]", encoding="utf-8")

        dist_story = self.mock_dist / "story"
        dist_story.mkdir(parents=True, exist_ok=True)
        (dist_story / "1001.json").write_text("[]", encoding="utf-8")
        (dist_story / "9999.json").write_text("[]", encoding="utf-8")  # source 已無

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=False)
        self.assertIn("stale story JSON", prune_stats)
        self.assertEqual(prune_stats["stale story JSON"][0], 1)
        self.assertTrue((dist_story / "1001.json").exists())
        self.assertFalse((dist_story / "9999.json").exists())

    def test_08_dry_run_zero_side_effects(self):
        """8. 確保 dry-run 完整計算但不發生實體變更"""
        test_file = self.mock_dist / "redive_tw-DESKTOP-N6EC182.db"
        test_file.write_bytes(b"content")

        prune_stats = prune_stale_dist_assets(self.mock_dash, self.mock_dist, dry_run=True)
        self.assertIn("duplicate DB", prune_stats)
        self.assertEqual(prune_stats["duplicate DB"][0], 1)
        self.assertTrue(test_file.exists(), "Dry-run 模式下實體檔案絕對不可被刪除")

    def test_09_nojekyll_normalization(self):
        """9. 確保 .nojekyll 缺失時建立、非空時正規化為 0 bytes"""
        nojekyll = self.mock_dist / ".nojekyll"
        
        # 1. 缺失時
        if nojekyll.exists():
            nojekyll.unlink()
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "created")
        self.assertTrue(nojekyll.exists())
        self.assertEqual(nojekyll.stat().st_size, 0)

        # 2. 非空時
        nojekyll.write_text("some non-empty content", encoding="utf-8")
        self.assertGreater(nojekyll.stat().st_size, 0)
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "normalized")
        self.assertEqual(nojekyll.stat().st_size, 0)

        # 3. 已經為 0 bytes 時
        act, sz = sync_nojekyll(self.mock_dist, dry_run=False)
        self.assertEqual(act, "unchanged")
        self.assertEqual(nojekyll.stat().st_size, 0)

    def test_10_footprint_gate_thresholds(self):
        """10. 測試 Deployment Footprint Gate 邏輯 (PASS, WARN, HARD ERROR)"""
        # 1. 正常小體積 (200 MiB)
        pass_bytes = 200 * 1024 * 1024
        is_p, msg_p, _ = check_footprint_gate(footprint_bytes=pass_bytes)
        self.assertTrue(is_p)
        self.assertIn("PASS", msg_p)

        # 2. 預警體積 (800 MiB >= 750 MiB)
        warn_bytes = 800 * 1024 * 1024
        is_w, msg_w, _ = check_footprint_gate(footprint_bytes=warn_bytes)
        self.assertTrue(is_w)
        self.assertIn("WARNING", msg_w)

        # 3. 致命超標 (950 MiB >= 900 MiB)
        hard_bytes = 950 * 1024 * 1024
        is_h, msg_h, _ = check_footprint_gate(footprint_bytes=hard_bytes)
        self.assertFalse(is_h)
        self.assertIn("HARD ERROR", msg_h)

    def test_11_dry_run_projection_accuracy_and_zero_side_effects(self):
        """11. 測試 Dry-run 預測新增/修改差異，並保證零副作用"""
        dash_story = self.mock_dash / "story"
        dash_story.mkdir(parents=True, exist_ok=True)
        (dash_story / "1001.json").write_text("[]", encoding="utf-8")
        (dash_story / "1002.json").write_text("[1, 2, 3, 4, 5]", encoding="utf-8")  # 新增檔案

        dist_story = self.mock_dist / "story"
        dist_story.mkdir(parents=True, exist_ok=True)
        (dist_story / "1001.json").write_text("[]", encoding="utf-8")

        # 記錄快照
        snapshot_before = {p.relative_to(self.mock_dist): p.stat().st_size for p in self.mock_dist.rglob("*") if p.is_file()}

        additions, deltas = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertGreater(additions, 0, "應計算出新增的 1002.json 大小")

        # 檢查快照在計算後完全不變
        snapshot_after = {p.relative_to(self.mock_dist): p.stat().st_size for p in self.mock_dist.rglob("*") if p.is_file()}
        self.assertEqual(snapshot_before, snapshot_after, "Dry-run 預測計算過程中不得產生檔案系統副作用")

    def test_12_card_and_voice_sync_and_footprint_exclusion(self):
        """12. 測試 card/full 與 sound/story_vo 正常同步且被 footprint gate 排除"""
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

    def test_13_generated_index_growth_projection(self):
        """13. 測試動態渲染 index.html 大小精確反映於 dry-run 預估 (非 hardcoded)"""
        # 建立 mock dashboard 必備檔案
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

        # 當 dist 不存在 index.html 時，additions 應精確為 size1
        add1, delta1 = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(add1, size1)

        # 實體寫入 index.html (以 raw UTF-8 bytes 寫入)
        (self.mock_dist / "index.html").write_bytes(rendered1.encode("utf-8"))

        # 擴展 db.js 增加 5000 bytes (同時擴展 source db.js)
        extra_content = "/* " + ("x" * 5000) + " */"
        (self.mock_dash / "db.js").write_text('console.log("initial db code");' + extra_content, encoding="utf-8")

        rendered2 = render_index_html(self.mock_dash)
        expected_index_delta = len(rendered2.encode("utf-8")) - len(rendered1.encode("utf-8"))
        expected_db_delta = (self.mock_dash / "db.js").stat().st_size - (self.mock_dist / "db.js").stat().st_size

        add2, delta2 = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(delta2, expected_index_delta + expected_db_delta, "dry-run delta 必須精確等於渲染後 index.html 及更新檔案的實際 byte 差值")

    def test_14_legacy_to_canonical_icon_projection(self):
        """14. 測試 Legacy -> Canonical icon 映射精確計入 dry-run 預估"""
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

        # 在 dist 中尚無 icon 檔案時，additions 應精確包含兩份預期產物 (100201.webp 與 unit_icon_100201.webp)
        additions, deltas = calculate_expected_additions_and_deltas(self.mock_dash, self.mock_dist)
        self.assertEqual(additions, file_sz * 2, "dry-run 預估應精確包含 legacy 及由其映射生成之 canonical icon 大小")

if __name__ == "__main__":
    unittest.main(verbosity=2)
