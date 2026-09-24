#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Normalized DB Generator (Phase F2A.3)
"""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pipeline.sonet_normalized_db import (
    generate_normalized_db,
    get_client_family,
    load_schema_mapping,
    validate_mapping_contract,
    NormalizedDbResult,
)


class TestSonetNormalizedDb(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.manifest_dir = self.test_dir / "manifests"
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        
        # 建立測試用 minimal raw SQLite
        self.raw_db_path = self.test_dir / "test_raw.db"
        conn = sqlite3.connect(str(self.raw_db_path))
        cur = conn.cursor()
        cur.execute('CREATE TABLE "v1_mock_story" ("phys_sid" INTEGER, "phys_title" TEXT, "phys_sub_title" TEXT, "phys_gid" INTEGER);')
        cur.execute('INSERT INTO "v1_mock_story" VALUES (101, "第1話", "副標1", 10);')
        cur.execute('INSERT INTO "v1_mock_story" VALUES (102, "第2話", "副標2", 10);')
        
        cur.execute('CREATE TABLE "v1_mock_unit" ("phys_uid" INTEGER, "phys_uname" TEXT);')
        cur.execute('INSERT INTO "v1_mock_unit" VALUES (1001, "佩可");')
        
        cur.execute('CREATE TABLE "v1_mock_rarity" ("phys_uid" INTEGER);')
        cur.execute('INSERT INTO "v1_mock_rarity" VALUES (1001);')

        cur.execute('CREATE TABLE "v1_mock_event" ("phys_gid" INTEGER, "phys_title" TEXT, "phys_stime" TEXT);')
        cur.execute('INSERT INTO "v1_mock_event" VALUES (5001, "活動1", "2024-01-01");')
        
        cur.execute('CREATE TABLE "v1_mock_css" ("phys_sid" INTEGER, "phys_cid" INTEGER);')
        cur.execute('INSERT INTO "v1_mock_css" VALUES (101, 10);')
        cur.execute('INSERT INTO "v1_mock_css" VALUES (102, 10);')
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_client_family(self):
        self.assertEqual(get_client_family("00610008"), "0061")
        self.assertEqual(get_client_family("00600025"), "0060")
        with self.assertRaises(ValueError):
            get_client_family("00")
        with self.assertRaises(ValueError):
            get_client_family("")

    def test_unknown_client_family_fail_closed(self):
        """未知 client family 必須拋出 KeyError (NEEDS_NEW_SCHEMA_MAPPING)"""
        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00990001", # 未知版本
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertFalse(res.success)
        self.assertIn("NEEDS_NEW_SCHEMA_MAPPING", res.error)
        self.assertFalse(output_db.exists())

    def test_duplicate_mapping_fail_closed(self):
        """Mapping 契約存在重複定義必須報錯"""
        bad_manifest = {
            "client_family": "0061",
            "tables": {
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "columns": {
                        "unit_id": "phys_uid",
                        "unit_name": "phys_uid" # 重複指向同一個 physical column
                    }
                }
            }
        }
        with self.assertRaises(ValueError):
            validate_mapping_contract(bad_manifest)

    def test_missing_physical_table_fail_closed(self):
        """raw DB 缺失 physical table 必須拒絕生成"""
        mapping = {
            "client_family": "0061",
            "tables": {
                "non_existent": {
                    "physical_table": "v1_missing_table_xyz",
                    "columns": {"id": "col_a"}
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00610008",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertFalse(res.success)
        self.assertIn("缺失實體表", res.error)
        self.assertFalse(output_db.exists())

    def test_missing_physical_column_fail_closed(self):
        """raw DB 缺失 physical column 必須拒絕生成"""
        mapping = {
            "client_family": "0061",
            "tables": {
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "columns": {
                        "unit_id": "phys_uid",
                        "missing_col": "non_existent_phys_col"
                    }
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00610008",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertFalse(res.success)
        self.assertIn("缺失實體欄位", res.error)
        self.assertFalse(output_db.exists())

    def test_successful_normalized_db_generation_and_schema_match(self):
        """驗證正常生成流程、Schema 乾淨精確匹配與業務查詢"""
        mapping = {
            "client_family": "0061",
            "tables": {
                "story_detail": {
                    "physical_table": "v1_mock_story",
                    "primary_key": "story_id",
                    "columns": {
                        "story_id": "phys_sid",
                        "title": "phys_title",
                        "story_group_id": "phys_gid"
                    }
                },
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "primary_key": "unit_id",
                    "columns": {
                        "unit_id": "phys_uid",
                        "unit_name": "phys_uname"
                    }
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00610008",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertTrue(res.success)
        self.assertTrue(output_db.exists())
        self.assertEqual(res.table_stats["story_detail"], 2)
        self.assertEqual(res.table_stats["unit_data"], 1)

        # 檢驗生成之 SQLite 結構
        conn = sqlite3.connect(str(output_db))
        cur = conn.cursor()
        
        # 1. PRAGMA integrity_check
        cur.execute("PRAGMA integrity_check")
        self.assertEqual(cur.fetchone()[0], "ok")
        
        # 2. Table exact match
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        self.assertEqual(tables, ["story_detail", "unit_data"])
        
        # 3. Column exact match
        cur.execute("PRAGMA table_info('story_detail')")
        cols_sd = [r[1] for r in cur.fetchall()]
        self.assertEqual(cols_sd, ["story_id", "title", "story_group_id"])
        
        # 4. Semantic Query Smoke
        cur.execute("SELECT title FROM story_detail WHERE story_id = '101'")
        self.assertEqual(cur.fetchone()[0], "第1話")
        
        cur.execute("SELECT unit_name FROM unit_data WHERE unit_id = '1001'")
        self.assertEqual(cur.fetchone()[0], "佩可")
        
        conn.close()

    def test_repo_canonical_0061_mapping_validity(self):
        """驗證正式 pipeline/manifests/sonet_db_schema_map_0061.json 格式健全性"""
        canonical_map_file = Path(__file__).resolve().parents[1] / "pipeline" / "manifests" / "sonet_db_schema_map_0061.json"
        self.assertTrue(canonical_map_file.is_file())
        with open(canonical_map_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 必須包含全部 11 張核心表且 mapped columns 總計 99 個
        expected_tables = {
            "story_detail", "unit_data", "unit_profile", "event_story_data",
            "event_story_detail", "story_group_data", "chara_story_status",
            "unit_rarity", "unit_skill_data", "unit_attack_pattern", "skill_data"
        }
        self.assertEqual(set(data["tables"].keys()), expected_tables)
        mapped_cols_count = sum(len(tbl["columns"]) for tbl in data["tables"].values())
        self.assertEqual(mapped_cols_count, 99)
        validate_mapping_contract(data)

    def test_game_snapshot_query_against_normalized_db(self):
        """驗證 tools/pcrd_fetch.py 的 _query_game_snapshot 查詢在 normalized DB 上運作正常"""
        mapping = {
            "client_family": "0061",
            "tables": {
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "primary_key": "unit_id",
                    "columns": {"unit_id": "phys_uid", "unit_name": "phys_uname"}
                },
                "unit_rarity": {
                    "physical_table": "v1_mock_rarity",
                    "primary_key": "unit_id",
                    "columns": {"unit_id": "phys_uid"}
                },
                "story_detail": {
                    "physical_table": "v1_mock_story",
                    "primary_key": "story_id",
                    "columns": {"story_id": "phys_sid", "title": "phys_title", "sub_title": "phys_sub_title"}
                },
                "event_story_data": {
                    "physical_table": "v1_mock_event",
                    "primary_key": "story_group_id",
                    "columns": {"story_group_id": "phys_gid", "title": "phys_title", "start_time": "phys_stime"}
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00610008",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertTrue(res.success)

        # 模擬 _query_game_snapshot 查詢
        conn = sqlite3.connect(str(output_db))
        cur = conn.cursor()
        
        # 1. 最新角色查詢 (EXISTS unit_rarity)
        cur.execute(
            "SELECT u.unit_id, u.unit_name FROM unit_data u "
            "WHERE u.unit_id >= 1000 AND u.unit_id < 180000 "
            "AND EXISTS (SELECT 1 FROM unit_rarity r WHERE r.unit_id = u.unit_id) "
            "ORDER BY u.unit_id DESC LIMIT 5"
        )
        chars = cur.fetchall()
        self.assertEqual(len(chars), 1)
        self.assertEqual(chars[0][1], "佩可")

        # 2. 最新主線查詢
        cur.execute("SELECT story_id, title, sub_title FROM story_detail ORDER BY story_id DESC LIMIT 5")
        main_stories = cur.fetchall()
        self.assertEqual(len(main_stories), 2)

        # 3. 最新活動查詢
        cur.execute("SELECT story_group_id, title, start_time FROM event_story_data ORDER BY story_group_id DESC LIMIT 5")
        events = cur.fetchall()
        self.assertEqual(len(events), 1)
        conn.close()

    def test_maintenance_pcrd_fetch_queries_work(self):
        """驗證維護工具所需之查詢 (unit_name, chara_story_status) 能正常執行"""
        mapping = {
            "client_family": "0061",
            "tables": {
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "primary_key": "unit_id",
                    "columns": {"unit_id": "phys_uid", "unit_name": "phys_uname"}
                },
                "chara_story_status": {
                    "physical_table": "v1_mock_css",
                    "primary_key": "story_id",
                    "columns": {"story_id": "phys_sid", "chara_id_1": "phys_cid"}
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00610008",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertTrue(res.success)

        conn = sqlite3.connect(str(output_db))
        cur = conn.cursor()
        
        # 1. 角色名稱查詢
        cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_id = '1001'")
        self.assertEqual(cur.fetchone()[1], "佩可")

        # 2. 個人劇情數統計 (使用 chara_id_1)
        cur.execute("SELECT COUNT(*) FROM chara_story_status WHERE chara_id_1 = '10'")
        self.assertEqual(cur.fetchone()[0], 2)
        conn.close()

    def test_unknown_0062_family_fails_closed_needs_new_schema_mapping(self):
        """驗證未知 0062 家族在沒有 0062 mapping 時嚴格 Fail-Closed 並返回 NEEDS_NEW_SCHEMA_MAPPING"""
        output_db = self.test_dir / "out.db"
        res = generate_normalized_db(
            raw_db_path=self.raw_db_path,
            truth_version="00620001",
            output_path=output_db,
            manifest_dir=self.manifest_dir
        )
        self.assertFalse(res.success)
        self.assertIn("NEEDS_NEW_SCHEMA_MAPPING", res.error)
        self.assertIn("client family '0062'", res.error)
        self.assertFalse(output_db.exists())

    def test_no_wthee_http_request_during_generation(self):
        """驗證 generate_normalized_db 在執行期間為純本地操作，絕無任何外部 HTTP / wthee 請求"""
        from unittest.mock import patch

        mapping = {
            "client_family": "0061",
            "tables": {
                "unit_data": {
                    "physical_table": "v1_mock_unit",
                    "primary_key": "unit_id",
                    "columns": {"unit_id": "phys_uid", "unit_name": "phys_uname"}
                }
            }
        }
        m_file = self.manifest_dir / "sonet_db_schema_map_0061.json"
        with open(m_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

        output_db = self.test_dir / "out.db"
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            res = generate_normalized_db(
                raw_db_path=self.raw_db_path,
                truth_version="00610008",
                output_path=output_db,
                manifest_dir=self.manifest_dir
            )
            self.assertTrue(res.success)
            mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()

