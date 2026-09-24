#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for canonical So-net Master DB acquisition primitive (pipeline.sonet_master_db)
使用 Mock 網絡與 Fixture 隔離測試，嚴禁在單元測試中下載真實大型檔案。
"""

import hashlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from pipeline.sonet_master_db import (
    fetch_master_db_from_sonet,
    MasterDbFetchResult,
    REQUIRED_TABLES,
    REQUIRED_COLUMNS,
    SQLITE_MAGIC
)


def _create_mock_valid_sqlite_bytes() -> bytes:
    """建立一個記憶體中合法的完整 SQLite 資料庫二進位。"""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    # 建立所有必要表格與欄位
    cur.execute("CREATE TABLE story_detail (story_id INTEGER, story_group_id INTEGER, title TEXT);")
    cur.execute("INSERT INTO story_detail VALUES (1001001, 1001, '第一話');")
    
    cur.execute("CREATE TABLE unit_data (unit_id INTEGER, unit_name TEXT);")
    cur.execute("INSERT INTO unit_data VALUES (100101, '佩可');")

    cur.execute("CREATE TABLE unit_profile (unit_id INTEGER);")
    cur.execute("CREATE TABLE event_story_data (story_id INTEGER);")
    cur.execute("CREATE TABLE tower_story_data (story_id INTEGER);")
    cur.execute("CREATE TABLE chara_story_status (chara_id INTEGER);")
    conn.commit()

    db_bytes = conn.serialize()
    conn.close()
    return db_bytes


class TestSonetMasterDbFetcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dest_dir = Path(self.temp_dir.name)
        self.dest_db = self.dest_dir / "redive_tw.db"

        # 寫入初始舊 DB 作為對照組
        self.initial_old_bytes = b"OLD_DATABASE_BYTE_IDENTICAL_SENTINEL_DATA_1234567890"
        with open(self.dest_db, "wb") as f:
            f.write(self.initial_old_bytes)
        self.old_sha256 = hashlib.sha256(self.initial_old_bytes).hexdigest()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _assert_old_db_unchanged(self):
        """驗證目標檔案必須保持 100% byte-identical。"""
        self.assertTrue(self.dest_db.exists(), "原資料庫檔案應當存在")
        with open(self.dest_db, "rb") as f:
            actual_bytes = f.read()
        actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()
        self.assertEqual(actual_sha256, self.old_sha256, "原資料庫 SHA256 遭到竄改，違反 byte-identical 安全保證！")

    def test_invalid_truth_version_format(self):
        """1. 傳入非法格式之 TruthVersion 應直接拒絕，不發送網路請求。"""
        for invalid_tv in ["0061", "006100089", "0061000a", "", None, 610008]:
            res = fetch_master_db_from_sonet(invalid_tv, self.dest_db)
            self.assertFalse(res.success)
            self.assertIn("無效的 TruthVersion 格式", res.error)
            self._assert_old_db_unchanged()

    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_manifest_404_error(self, mock_http):
        """2. Manifest 回傳 HTTP 404 時，優雅失敗且原 DB 不變。"""
        mock_http.side_effect = urllib.error.HTTPError(
            url="http://mock", code=404, msg="Not Found", hdrs={}, fp=None
        )
        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertFalse(res.success)
        self.assertIn("404", res.error)
        self._assert_old_db_unchanged()

    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_manifest_missing_masterdata_entry(self, mock_http):
        """3. Manifest 格式損壞或缺少 masterdata_master.unity3d 條目。"""
        mock_http.return_value = b"other_asset.unity3d,1234567890abcdef1234567890abcdef,hash123,tag,100,"
        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertFalse(res.success)
        self.assertIn("未找到 masterdata_master.unity3d", res.error)
        self._assert_old_db_unchanged()

    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_bundle_md5_mismatch(self, mock_http):
        """4. 下載之 Pool Bundle MD5 與 Manifest 宣告不一致，觸發硬門禁攔截。"""
        manifest_line = b"a/masterdata_master.unity3d,e590b77dd2a9062a4181ba3ea8f545c5,ea31a8de308910be,tag,100,"
        corrupt_bundle = b"THIS_IS_CORRUPT_BUNDLE_CONTENT_NOT_MATCHING_MD5"
        mock_http.side_effect = [manifest_line, corrupt_bundle]

        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertFalse(res.success)
        self.assertIn("Bundle MD5 校驗不符", res.error)
        self._assert_old_db_unchanged()

    @patch("UnityPy.load")
    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_missing_sqlite_magic_in_bundle(self, mock_http, mock_unity):
        """5. UnityPy 解出的 TextAsset 未包含 SQLite Magic bytes。"""
        fake_bundle = b"FAKE_BUNDLE_BYTES"
        fake_md5 = hashlib.md5(fake_bundle).hexdigest()
        manifest_line = f"a/masterdata_master.unity3d,{fake_md5},ea31a8de308910be,tag,{len(fake_bundle)},".encode()
        mock_http.side_effect = [manifest_line, fake_bundle]

        mock_obj = MagicMock()
        mock_obj.type.name = "TextAsset"
        mock_obj.get_raw_data.return_value = b"NOT_A_SQLITE_DATABASE_TEXT_ASSET"
        mock_env = MagicMock()
        mock_env.objects = [mock_obj]
        mock_unity.return_value = mock_env

        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertFalse(res.success)
        self.assertIn("Magic bytes 缺失", res.error)
        self._assert_old_db_unchanged()

    @patch("pipeline.sonet_master_db._validate_sqlite_db")
    @patch("UnityPy.load")
    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_validation_failure_preserves_old_db(self, mock_http, mock_unity, mock_val):
        """6. SQLite 驗證失敗 (如 integrity 異常或缺表) 阻斷替換。"""
        fake_bundle = b"FAKE_BUNDLE_BYTES"
        fake_md5 = hashlib.md5(fake_bundle).hexdigest()
        manifest_line = f"a/masterdata_master.unity3d,{fake_md5},ea31a8de308910be,tag,{len(fake_bundle)},".encode()
        mock_http.side_effect = [manifest_line, fake_bundle]

        mock_obj = MagicMock()
        mock_obj.type.name = "TextAsset"
        mock_obj.get_raw_data.return_value = SQLITE_MAGIC + b"CORRUPTED_BODY"
        mock_env = MagicMock()
        mock_env.objects = [mock_obj]
        mock_unity.return_value = mock_env

        mock_val.side_effect = ValueError("PRAGMA integrity_check 失敗: corrupted")

        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertFalse(res.success)
        self.assertIn("corrupted", res.error)
        self._assert_old_db_unchanged()

    @patch("UnityPy.load")
    @patch("pipeline.sonet_master_db._http_get_bytes")
    def test_successful_acquisition_and_atomic_replace(self, mock_http, mock_unity):
        """7. 完整成功流程：下載、MD5 校驗、解包、通過 6 重驗證、原子替換成功。"""
        valid_db = _create_mock_valid_sqlite_bytes()
        fake_bundle = b"FAKE_BUNDLE_BYTES"
        fake_md5 = hashlib.md5(fake_bundle).hexdigest()
        manifest_line = f"a/masterdata_master.unity3d,{fake_md5},ea31a8de308910be,tag,{len(fake_bundle)},".encode()
        mock_http.side_effect = [manifest_line, fake_bundle]

        mock_obj = MagicMock()
        mock_obj.type.name = "TextAsset"
        # 模擬 UnityPy 物件前置 16 bytes 自訂 header 後接真實 SQLite
        mock_obj.get_raw_data.return_value = b"HEADER_16_BYTES_" + valid_db
        mock_env = MagicMock()
        mock_env.objects = [mock_obj]
        mock_unity.return_value = mock_env

        res = fetch_master_db_from_sonet("00610008", self.dest_db)
        self.assertTrue(res.success, f"應當執行成功，錯誤為: {res.error}")
        self.assertEqual(res.truth_version, "00610008")
        self.assertEqual(res.written_path, self.dest_db)
        self.assertEqual(res.bundle_md5, fake_md5)
        self.assertEqual(res.pool_hash, "ea31a8de308910be")

        # 驗證目標檔案已成功替換為新 DB
        with open(self.dest_db, "rb") as f:
            final_bytes = f.read()
        self.assertEqual(final_bytes, valid_db)
        self.assertEqual(res.db_sha256, hashlib.sha256(valid_db).hexdigest())

        # 驗證 Staging 殘留檔案已被乾淨清理
        staging = self.dest_db.parent / f"{self.dest_db.name}.download.tmp"
        self.assertFalse(staging.exists(), "Staging 暫存檔案必須已被清除")


if __name__ == "__main__":
    unittest.main()
