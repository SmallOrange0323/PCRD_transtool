# -*- coding: utf-8 -*-
"""
Focused regression tests for Canonical Normalized DB Promotion Guard (Phase U15).
Ensures raw, hybrid, missing-table, missing-column, corrupt, or invalid databases
are strictly rejected and never promoted to production.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipeline.sonet_normalized_db import (
    validate_canonical_normalized_db,
    CanonicalDbValidationResult,
    load_schema_mapping,
)
from pipeline.fetch import update_db, CANONICAL_DB_PATH


def _create_minimal_canonical_db(db_path: Path, client_family: str = "0061"):
    """建立一個符合 schema mapping 契約之最小合法 normalized sqlite 資料庫"""
    _, mapping = load_schema_mapping(client_family)
    tables_cfg = mapping["tables"]
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    for tbl_name, tbl_meta in tables_cfg.items():
        cols = list(tbl_meta["columns"].keys())
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        cur.execute(f'CREATE TABLE "{tbl_name}" ({col_defs})')
        # 插入一筆 dummy 資料
        placeholders = ", ".join("?" for _ in cols)
        dummy_row = ["1" for _ in cols]
        cur.execute(f'INSERT INTO "{tbl_name}" VALUES ({placeholders})', dummy_row)
    conn.commit()
    conn.close()


class TestCanonicalDbPromotionGuard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.truth_version = "00610014"
        self.client_family = "0061"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_case_a_valid_normalized_db(self):
        """A. VALID normalized DB: canonical mapped tables, columns, no v1 tables, integrity ok -> PASS"""
        db_path = self.dir_path / "valid_norm.db"
        _create_minimal_canonical_db(db_path, self.client_family)

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertTrue(res.valid)
        self.assertEqual(len(res.errors), 0)
        self.assertEqual(res.integrity_result, "ok")
        self.assertEqual(len(res.raw_v1_tables), 0)
        self.assertEqual(res.table_count, 11)
        self.assertEqual(res.mapped_column_count, 99)

    def test_case_b_raw_db_rejected(self):
        """B. RAW DB: contains many v1_* tables -> FAIL"""
        db_path = self.dir_path / "raw.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("CREATE TABLE v1_abc123 (id INT)")
        cur.execute("CREATE TABLE v1_def456 (id INT)")
        conn.commit()
        conn.close()

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertFalse(res.valid)
        self.assertGreater(len(res.raw_v1_tables), 0)
        self.assertTrue(any("raw/hybrid" in err for err in res.errors))

    def test_case_c_hybrid_db_rejected(self):
        """C. HYBRID DB: some canonical table names plus remaining v1_* tables -> FAIL"""
        db_path = self.dir_path / "hybrid.db"
        _create_minimal_canonical_db(db_path, self.client_family)
        # 額外加入混淆表
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("CREATE TABLE v1_leftover (id INT)")
        conn.commit()
        conn.close()

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertFalse(res.valid)
        self.assertEqual(res.raw_v1_tables, ["v1_leftover"])
        self.assertTrue(any("raw/hybrid" in err for err in res.errors))

    def test_case_d_missing_canonical_table_rejected(self):
        """D. Missing canonical table -> FAIL"""
        db_path = self.dir_path / "missing_tbl.db"
        _create_minimal_canonical_db(db_path, self.client_family)
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("DROP TABLE unit_data")
        conn.commit()
        conn.close()

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertFalse(res.valid)
        self.assertIn("unit_data", res.missing_tables)
        self.assertTrue(any("缺失 Canonical 必要業務表" in err for err in res.errors))

    def test_case_e_missing_required_column_rejected(self):
        """E. Missing required mapped column -> FAIL"""
        db_path = self.dir_path / "missing_col.db"
        _, mapping = load_schema_mapping(self.client_family)
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        for tbl_name, tbl_meta in mapping["tables"].items():
            cols = list(tbl_meta["columns"].keys())
            if tbl_name == "unit_data":
                # 刻意漏掉 unit_name
                cols = [c for c in cols if c != "unit_name"]
            col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
            cur.execute(f'CREATE TABLE "{tbl_name}" ({col_defs})')
        conn.commit()
        conn.close()

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertFalse(res.valid)
        self.assertIn("unit_data", res.missing_columns)
        self.assertIn("unit_name", res.missing_columns["unit_data"])
        self.assertTrue(any("缺失 Canonical 欄位" in err for err in res.errors))

    def test_case_f_corrupt_non_sqlite_rejected(self):
        """F. Corrupt / non-SQLite candidate -> FAIL"""
        db_path = self.dir_path / "corrupt.db"
        db_path.write_bytes(b"NOT_A_SQLITE_DATABASE_CORRUPTED_BYTES_1234567890")

        res = validate_canonical_normalized_db(db_path, self.truth_version)
        self.assertFalse(res.valid)
        self.assertTrue(len(res.errors) > 0)

    def test_case_g_promotion_state_safety_on_failure(self):
        """
        G. State safety:
        When promotion validation fails:
        - target production DB remains byte-identical
        - update_db reports error
        - update_db does not apply replacement
        """
        mock_prod = self.dir_path / "mock_redive_tw.db"
        _create_minimal_canonical_db(mock_prod, self.client_family)
        orig_bytes = mock_prod.read_bytes()
        orig_sha = hashlib.sha256(orig_bytes).hexdigest()

        # 模擬 fetcher 回傳一個 hybrid/raw db
        bad_staging = self.dir_path / "bad_staging.db"
        conn = sqlite3.connect(str(bad_staging))
        conn.cursor().execute("CREATE TABLE v1_malformed (col TEXT)")
        conn.commit()
        conn.close()

        with patch("pipeline.fetch.fetch_master_db_from_sonet") as mock_fetch, \
             patch("pipeline.fetch.generate_normalized_db") as mock_gen:
            
            # 讓 fetcher 回傳 success
            mock_fetch_res = MagicMock()
            mock_fetch_res.success = True
            mock_fetch_res.manifest_url = "http://mock"
            mock_fetch_res.manifest_sha256 = "mock_manifest_sha"
            mock_fetch_res.bundle_name = "mock_bundle"
            mock_fetch_res.bundle_md5 = "mock_bundle_md5"
            mock_fetch_res.pool_hash = "mock_pool"
            mock_fetch_res.bundle_size = 1000
            mock_fetch_res.bundle_url = "http://mock/bundle"
            mock_fetch_res.db_sha256 = "mock_raw_sha"
            mock_fetch.return_value = mock_fetch_res

            # 讓 generator 意外輸出一個惡意或損壞的 hybrid/raw 資料庫到 staging
            def fake_gen(raw_db_path, truth_version, output_path, **kwargs):
                shutil.copy2(bad_staging, output_path)
                res = MagicMock()
                res.success = True
                res.table_stats = {"v1_malformed": 1}
                res.mapping_schema_version = "1.0.0"
                res.mapping_file = None
                res.provenance = {}
                return res

            mock_gen.side_effect = fake_gen

            report_file = self.dir_path / "test_report.json"
            res_dict = update_db(
                truth_version=self.truth_version,
                output=str(report_file),
                db_path=mock_prod,
                force=True
            )

            # 驗證 update_db 回傳 error 且未 applied
            self.assertEqual(res_dict.get("status"), "error")
            self.assertFalse(res_dict.get("applied", False))
            self.assertIn("HARD STOP", str(res_dict.get("error")))

            # 核心安全保證：正式資料庫位元組完全未被修改
            current_bytes = mock_prod.read_bytes()
            current_sha = hashlib.sha256(current_bytes).hexdigest()
            self.assertEqual(orig_sha, current_sha)
            self.assertEqual(orig_bytes, current_bytes)

    def test_case_h_orchestration_boundary_failed_promotion_state_safety(self):
        """
        H. Orchestration boundary state safety regression:
        When canonical guard rejects candidate DB during check_and_sync_upstream / pipeline update:
        - production DB bytes remain unchanged
        - applied CDN version does NOT advance
        - applied normalized DB SHA does NOT advance
        - save_truth_version_state is NOT called
        - version_history.json is NOT modified
        - FreshnessStatus is UPDATE_FAILED (never NO_CHANGE or UPDATED_SUCCESSFULLY)
        - pipeline run aborts with non-zero exit code
        """
        import pipeline.update as update_module

        # 1. 建立隔離的假生產環境
        mock_prod = self.dir_path / "redive_tw.db"
        _create_minimal_canonical_db(mock_prod, self.client_family)
        orig_prod_bytes = mock_prod.read_bytes()
        orig_prod_sha = hashlib.sha256(orig_prod_bytes).hexdigest()

        # 2. 建立已知健全的假版本狀態檔案 (known-good state)
        ver_dir = self.dir_path / "versions"
        ver_dir.mkdir(parents=True, exist_ok=True)
        ver_file = ver_dir / "version_history.json"
        initial_state = {
            "last_applied_cdn_version": "00610013",
            "last_applied_normalized_db_sha256": "known_good_normalized_sha_00610013",
            "truth_version": "00610013",
            "last_version": "00610013",
            "processed_versions": ["00610013"]
        }
        with open(ver_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f, indent=2)
        orig_state_bytes = ver_file.read_bytes()

        # 3. 準備惡意/混淆 candidate staging DB
        bad_staging = self.dir_path / "bad_staging.db"
        conn = sqlite3.connect(str(bad_staging))
        conn.cursor().execute("CREATE TABLE v1_malformed (col TEXT)")
        conn.commit()
        conn.close()

        with patch("pipeline.fetch.CANONICAL_DB_PATH", mock_prod), \
             patch("pipeline.update.DASHBOARD_DIR", self.dir_path), \
             patch("pipeline.fetch.fetch_master_db_from_sonet") as mock_fetch, \
             patch("pipeline.fetch.generate_normalized_db") as mock_gen, \
             patch("pipeline.update.save_truth_version_state") as mock_save_state, \
             patch("pipeline.update.analyze_coverage") as mock_cov:

            # Coverage mock
            mock_coverage = MagicMock()
            mock_coverage.analysis_status = update_module.CoverageAnalysisStatus.VALID
            mock_coverage.analysis_errors = []
            mock_coverage.missing_required_count = 0
            mock_coverage.missing_optional_count = 0
            mock_coverage.unknown_expected_count = 0
            mock_coverage.missing_unknown_count = 0
            mock_cov.return_value = mock_coverage

            # Fetcher mock: 假裝從線上探索到新版本 00610014
            mock_fetch_res = MagicMock()
            mock_fetch_res.success = True
            mock_fetch_res.manifest_url = "http://mock/manifest"
            mock_fetch_res.manifest_sha256 = "candidate_manifest_sha"
            mock_fetch_res.bundle_name = "candidate_bundle"
            mock_fetch_res.bundle_md5 = "candidate_bundle_md5"
            mock_fetch_res.pool_hash = "candidate_pool"
            mock_fetch_res.bundle_size = 1000
            mock_fetch_res.bundle_url = "http://mock/bundle"
            mock_fetch_res.db_sha256 = "candidate_raw_sha"
            mock_fetch.return_value = mock_fetch_res

            # Normalizer mock: 輸出混淆 DB
            def fake_gen(raw_db_path, truth_version, output_path, **kwargs):
                shutil.copy2(bad_staging, output_path)
                res = MagicMock()
                res.success = True
                res.table_stats = {"v1_malformed": 1}
                res.mapping_schema_version = "1.0.0"
                res.mapping_file = None
                res.provenance = {}
                return res

            mock_gen.side_effect = fake_gen

            # 模擬 CDN 快照探索回傳 candidate 00610014
            candidate = MagicMock()
            candidate.truth_version = self.truth_version  # "00610014"
            candidate.manifest_sha256 = "candidate_manifest_sha"
            candidate.master_bundle_md5 = "candidate_bundle_md5"
            candidate.master_pool_hash = "candidate_pool"

            cdn_discovery = MagicMock()
            cdn_discovery.highest_observed_cdn_version = self.truth_version
            cdn_discovery.candidates = {self.truth_version: candidate}

            real_update_db = update_db
            temp_report = self.dir_path / "temp_db_update_report.json"
            def wrapped_update_db(*args, **kwargs):
                kwargs["output"] = str(temp_report)
                return real_update_db(*args, **kwargs)

            with patch("pipeline.fetch.discover_cdn_candidate_snapshots", return_value=cdn_discovery), \
                 patch("pipeline.fetch.probe_third_party_reference", return_value={}), \
                 patch("pipeline.fetch.update_db", side_effect=wrapped_update_db):

                sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

                # A. 協調器層級同步必須失敗
                self.assertFalse(sync_ok, "門禁失敗時 check_and_sync_upstream 必須回傳 False")
                self.assertEqual(freshness.status, update_module.FreshnessStatus.UPDATE_FAILED)
                self.assertNotEqual(freshness.status, update_module.FreshnessStatus.NO_CHANGE)
                self.assertNotEqual(freshness.status, update_module.FreshnessStatus.UPDATED_SUCCESSFULLY)

                # B. state-writer 絕對不被呼叫
                mock_save_state.assert_not_called()

                # C. 生產庫位元組完全未被修改
                self.assertEqual(mock_prod.read_bytes(), orig_prod_bytes)
                self.assertEqual(hashlib.sha256(mock_prod.read_bytes()).hexdigest(), orig_prod_sha)

                # D. 狀態檔案完全未被修改 (version, sha 未推進)
                self.assertEqual(ver_file.read_bytes(), orig_state_bytes)
                saved_state = json.loads(ver_file.read_text(encoding="utf-8"))
                self.assertEqual(saved_state["last_applied_cdn_version"], "00610013")
                self.assertEqual(saved_state["last_applied_normalized_db_sha256"], "known_good_normalized_sha_00610013")
                self.assertNotIn("00610014", saved_state["processed_versions"])


if __name__ == "__main__":
    unittest.main()
