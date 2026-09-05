# -*- coding: utf-8 -*-
"""
官方台版主線章節標題提取器單元測試套件 (tests/test_official_chapter_title_extractor.py)
符合 Clean-Clone CI Hermetic 測試標準：
1. 100% 自包含 (In-Memory SQLite Fixtures)，零外部本機檔案依賴，零網路請求依賴。
2. Baseline 00600025 Fixture 驗證 (48 章, 部數分佈, 2214/2215/2216 錨點與 U+56AE 校驗)。
3. Generic Future-Compatible 模式驗證 (支援未來 2217 合法主線追加，總數 > 48 不報錯)。
4. 官方結構欄位 story_group_type == 2 與 ID family 雙重過濾驗證 (精準排除非主線)。
5. VERSION-PINNED 實體結構解析與未登錄版號 Fail-Closed 測試。
6. UnityPy 可選依賴隔離性驗證 (無 UnityPy 時模組載入與 DB 提取正常，Bundle 提取給出明確錯誤)。
7. partition("_") 精準分割規格與原生字元保留測試。
"""

import os
import sys
import json
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.extract_chapter_titles import (
    load_source_contract,
    extract_master_sqlite_from_bundle,
    extract_official_chapter_titles_from_db,
    resolve_physical_schema_for_version,
    discover_bundle_from_cdn_manifest,
    generate_review_table,
    CONTRACT_PATH,
    SQLITE_HEADER
)

# ──────────────── 00600025 官方基準資料 (Self-Contained Fixture) ────────────────
OFFICIAL_TW_00600025_BASELINE_ROWS = [
    (2000, 2, "序章_牽起羈絆的人們"),
    (2001, 2, "第1章_謎樣少女與記憶之鑰"),
    (2002, 2, "第2章_誓約女君"),
    (2003, 2, "第3章_襲來的黑色幻影"),
    (2004, 2, "第4章_災厄的牧場"),
    (2005, 2, "第5章_集結、七冠"),
    (2006, 2, "第6章_被遺忘的公主"),
    (2007, 2, "第7章_被預言的災禍"),
    (2008, 2, "第8章_彼此交錯的感情"),
    (2009, 2, "第9章_被盯上的演唱會"),
    (2010, 2, "第10章_貪吃佩可救出作戰"),
    (2011, 2, "第11章_打擊希望的黑鐵"),
    (2012, 2, "第12章_面具下的真實面貌"),
    (2013, 2, "第13章_決戰，蘭德索爾"),
    (2014, 2, "第14章_兇滅的霸瞳皇帝"),
    (2015, 2, "第15章_Re：連結"),
    (2101, 2, "第2部 第1章_冒險，再起"),
    (2102, 2, "第2部 第2章_災禍的軍團"),
    (2103, 2, "第2部 第3章_暴風雨的開始"),
    (2104, 2, "第2部 第4章_暫時的同班同學"),
    (2105, 2, "第2部 第5章_龍群與金幣的坩堝"),
    (2106, 2, "第2部 第6章 _大江戶漫遊湯煙旅情"),
    (2107, 2, "第2部 第7章 _自黑暗伸出的手"),
    (2108, 2, "第2部 第8章 _贊恩覺醒"),
    (2109, 2, "第2部 第9章_激鬥！【憤怒‧軍團】"),
    (2110, 2, "第2部 第10章_獸人族之國‧珊托魯斯"),
    (2111, 2, "第2部 第11章_虛空與魔性的遊戲"),
    (2112, 2, "第2部 第12章_激鬥、七冠"),
    (2113, 2, "第2部 第13章_被囚禁的愛梅斯"),
    (2114, 2, "第2部 第14章_封閉的理想鄉"),
    (2115, 2, "第2部 第15章_終局序曲"),
    (2116, 2, "第2部 第16章_終結世界"),
    (2201, 2, "第3部 第1章_反轉世界"),
    (2202, 2, "第3部 第2章_突襲！蠻賊三姊妹"),
    (2203, 2, "第3部 第3章_寶石兔與天使之雷"),
    (2204, 2, "第3部 第4章_存亡的吉歐‧提格尼亞"),
    (2205, 2, "第3部第5章_吉歐‧格黑納與煉花不死鳥"),
    (2206, 2, "第3部 第6章_幻變少女vs蠻賊三姊妹"),
    (2207, 2, "第3部 第7章_安涅默涅的眼淚"),
    (2208, 2, "第3部 第8章_四世界公主會議"),
    (2209, 2, "第3部 第9章_救出雪菲作戰"),
    (2210, 2, "第3部第10章_闇謀的吉歐‧尼布爾黑爾"),
    (2211, 2, "第3部 第11章_侵蝕的「正義」"),
    (2212, 2, "第3部 第12章_黑暗深處的死鬥"),
    (2213, 2, "第3部 第13章_降臨的幻境"),
    (2214, 2, "第3部 第14章_阿爾莎特的誘惑"),
    (2215, 2, "第3部 第15章_嚮導幼君"),
    (2216, 2, "第3部 第16章_三方爭霸"),
]


class TestOfficialChapterTitleExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_source_contract()
        cls.ver = "00600025"
        cls.schema = cls.contract["physical_schema_by_truth_version"][cls.ver]
        cls.table_name = cls.schema["physical_table"]
        cls.col_id = cls.schema["story_group_id_column"]
        cls.col_type = cls.schema["story_group_type_column"]
        cls.col_title = cls.schema["title_column"]

    def _create_mock_db(self, rows=None, custom_table=None, custom_cols=None):
        """建立記憶體中的 Hermetic Mock SQLite 資料庫"""
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        t_name = custom_table or self.table_name
        c_id = custom_cols[0] if custom_cols else self.col_id
        c_type = custom_cols[1] if custom_cols else self.col_type
        c_title = custom_cols[2] if custom_cols else self.col_title

        cur.execute(f"""
            CREATE TABLE "{t_name}" (
                "{c_id}" INTEGER PRIMARY KEY,
                "{c_type}" INTEGER,
                "{c_title}" TEXT
            )
        """)
        if rows:
            cur.executemany(f"""
                INSERT INTO "{t_name}" ("{c_id}", "{c_type}", "{c_title}") VALUES (?, ?, ?)
            """, rows)
        conn.commit()
        return conn

    # ──────────────── 1. 契約規格與 VERSION-PINNED 解析 ────────────────

    def test_contract_structure_schema_v2(self):
        """驗證契約 2.0.0 結構：包含 source, discovery, physical_schema 與 baseline_facts"""
        c = self.contract
        self.assertEqual(c.get("schema_version"), "2.0.0")
        self.assertEqual(c.get("source", {}).get("logical_table"), "story_group_data")
        self.assertIn("00600025", c.get("physical_schema_by_truth_version", {}))
        self.assertIn("baseline_00600025_facts", c)

    def test_version_pinned_schema_resolution(self):
        """驗證已知版號成功解析，未登錄版號 Fail-Closed 拒絕猜測"""
        ver, schema = resolve_physical_schema_for_version("00600025", self.contract)
        self.assertEqual(ver, "00600025")
        self.assertEqual(schema["physical_table"], self.table_name)

        # 未知版號必須明確報錯
        with self.assertRaises(ValueError) as ctx:
            resolve_physical_schema_for_version("99999999", self.contract)
        self.assertIn("Unsupported masterdata schema for TruthVersion 99999999", str(ctx.exception))

    # ──────────────── 2. Baseline 00600025 Fixture 驗證 ────────────────

    def test_baseline_00600025_facts_hermetic(self):
        """
        以記憶體 Hermetic Fixture 驗證 TruthVersion 00600025 基準事實：
        總數 48、部數分佈、錨點 2214、2215 (嚮導幼君 U+56AE)、2216。
        完全自包含，不依賴外部檔案或網路。
        """
        conn = self._create_mock_db(OFFICIAL_TW_00600025_BASELINE_ROWS)
        res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        chapters = res["chapters"]
        meta = res["source_metadata"]

        # 斷言總數為 48
        self.assertEqual(len(chapters), 48, "00600025 基準總數必須剛好為 48 章")

        # 斷言 ACTUAL run metadata 正確記錄
        self.assertEqual(meta["truth_version"], "00600025")
        self.assertEqual(meta["logical_table_resolution"], "VERSION-PINNED")

        by_id = {r["chapter_id"]: r for r in chapters}

        # 錨點 A: 2214 (阿爾莎特的誘惑)
        self.assertIn(2214, by_id)
        self.assertEqual(by_id[2214]["official_title"], "阿爾莎特的誘惑")

        # 錨點 B: 2215 (嚮導幼君) - 嚴格字元驗證
        self.assertIn(2215, by_id)
        title_2215 = by_id[2215]["official_title"]
        self.assertEqual(title_2215, "嚮導幼君")
        self.assertNotEqual(title_2215, "響導幼君", "官方母檔決策標題絕非實機截圖之 '響導幼君'")
        self.assertEqual(ord(title_2215[0]), 0x56AE, f"首字碼點必須為 U+56AE (嚮), 實際為 {hex(ord(title_2215[0]))}")

        # 錨點 C: 2216 (三方爭霸)
        self.assertIn(2216, by_id)
        self.assertEqual(by_id[2216]["official_title"], "三方爭霸")

        # 部數分佈驗證
        part1 = [r for r in chapters if r["part"] == 1]
        part2 = [r for r in chapters if r["part"] == 2]
        part3 = [r for r in chapters if r["part"] == 3]
        self.assertEqual(len(part1), 16, "第 1 部必須為 16 章 (含 2000 序章)")
        self.assertEqual(len(part2), 16, "第 2 部必須為 16 章 (2101~2116)")
        self.assertEqual(len(part3), 16, "第 3 部必須為 16 章 (2201~2216)")

    # ──────────────── 3. Generic Future-Compatible 模式驗證 ────────────────

    def test_generic_future_compatible_accepts_chapter_2217(self):
        """
        驗證通用提取邏輯支援未來合法主線追加 (例如 2217)，
        提取器不因總數超過 48 筆而報錯，並精準解析其部數與章數。
        """
        rows = list(OFFICIAL_TW_00600025_BASELINE_ROWS)
        # 合法 synthetic 未來 2217 章節
        rows.append((2217, 2, "第3部 第17章_合成測試未來第十七章標題"))

        conn = self._create_mock_db(rows)
        res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        chapters = res["chapters"]

        # 總數應為 49
        self.assertEqual(len(chapters), 49, "通用提取器必須能成功接受 49 筆主線章節")

        by_id = {r["chapter_id"]: r for r in chapters}
        self.assertIn(2217, by_id)
        c2217 = by_id[2217]
        self.assertEqual(c2217["part"], 3)
        self.assertEqual(c2217["chapter_num"], 17)
        self.assertEqual(c2217["official_title"], "合成測試未來第十七章標題")
        self.assertEqual(c2217["raw_title"], "第3部 第17章_合成測試未來第十七章標題")

    # ──────────────── 4. 結構欄位過濾 (story_group_type == 2) ────────────────

    def test_structural_filtering_excludes_non_main_story(self):
        """
        驗證 official 結構欄位 story_group_type == 2 能夠精準過濾掉非主線劇情，
        即便其 ID 剛好落在 2000-2999 之間，也不會被誤認為主線。
        """
        mock_rows = [
            (2001, 2, "第1章_正統主線第一章"),
            (2099, 1, "第99話_無關的角色劇情"),
            (2150, 3, "第50話_無關的公會劇情")
        ]
        conn = self._create_mock_db(mock_rows)
        res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        chapters = res["chapters"]

        self.assertEqual(len(chapters), 1, "僅有 story_group_type == 2 之主線章節被提取")
        self.assertEqual(chapters[0]["chapter_id"], 2001)

    def test_structural_filtering_excludes_out_of_family_ids(self):
        """
        驗證即便某記錄 story_group_type == 2，若其 ID 不在主線 ID family 範圍 (2000-2999)，
        也不會被通用提取器混入。
        """
        mock_rows = [
            (2001, 2, "第1章_正統主線第一章"),
            (5001, 2, "第5001章_異常大數字章節")
        ]
        conn = self._create_mock_db(mock_rows)
        res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        chapters = res["chapters"]

        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]["chapter_id"], 2001)

    # ──────────────── 5. UnityPy 隔離與可選依賴驗證 ────────────────

    def test_unitypy_optional_isolation(self):
        """
        驗證 UnityPy 為可選依賴：
        1. 當 UnityPy 不存在時，SQLite 與純標題提取功能 100% 正常運作。
        2. 僅在嘗試調用 AssetBundle 解壓時拋出明確的 ImportError。
        """
        # 模擬 UnityPy 模組完全不存在
        with patch.dict(sys.modules, {"UnityPy": None}):
            # A. 驗證純 DB 解析功能不受任何影響
            conn = self._create_mock_db(OFFICIAL_TW_00600025_BASELINE_ROWS[:3])
            res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
            self.assertEqual(len(res["chapters"]), 3)

            # B. 驗證調用 extract_master_sqlite_from_bundle 時給出明確錯誤
            with self.assertRaises(ImportError) as ctx:
                extract_master_sqlite_from_bundle(b"dummy_bundle_content")
            self.assertIn("提取 AssetBundle 需要 UnityPy 套件", str(ctx.exception))

    # ──────────────── 6. 分割邏輯與 Fail-Closed 防禦 ────────────────

    def test_partition_logic_with_multiple_underscores(self):
        """若標題後綴本身包含底線，partition('_') 必須保留所有後續底線"""
        mock_rows = [(2001, 2, "第1部 第1章_特殊_次級標題_結尾")]
        conn = self._create_mock_db(mock_rows)
        res = extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        self.assertEqual(res["chapters"][0]["official_title"], "特殊_次級標題_結尾")

    def test_fail_closed_invalid_sqlite_header(self):
        """非標準 SQLite 標頭必須直接拋出 ValueError 終止"""
        invalid_bytes = b"NOT_A_SQLITE_FILE_CONTENT"
        with self.assertRaises(ValueError) as ctx:
            extract_official_chapter_titles_from_db(invalid_bytes, contract=self.contract)
        self.assertIn("SQLite", str(ctx.exception))

    def test_fail_closed_missing_table(self):
        """資料庫缺少混淆實體表時必須拋出 KeyError 終止"""
        conn = self._create_mock_db(custom_table="wrong_table_name")
        with self.assertRaises(KeyError) as ctx:
            extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        self.assertIn("未找到混淆實體表", str(ctx.exception))

    def test_fail_closed_missing_column(self):
        """資料表缺少目標實體欄位時必須拋出 KeyError 終止"""
        conn = self._create_mock_db(custom_cols=("wrong_id", "wrong_type", "wrong_title"))
        with self.assertRaises(KeyError) as ctx:
            extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        self.assertIn("缺少欄位", str(ctx.exception))

    def test_fail_closed_missing_underscore_separator(self):
        """若原始標題缺少底線分隔符，必須拒絕猜測並拋出 ValueError"""
        mock_rows = [(2001, 2, "第1部 第1章 無底線分隔標題")]
        conn = self._create_mock_db(mock_rows)
        with self.assertRaises(ValueError) as ctx:
            extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        self.assertIn("缺少底線分隔符", str(ctx.exception))

    def test_fail_closed_empty_title_after_separator(self):
        """若底線後標題為空，必須拋出 ValueError 終止"""
        mock_rows = [(2001, 2, "第1部 第1章_")]
        conn = self._create_mock_db(mock_rows)
        with self.assertRaises(ValueError) as ctx:
            extract_official_chapter_titles_from_db(conn, contract=self.contract, truth_version="00600025")
        self.assertIn("為空字串", str(ctx.exception))

    # ──────────────── 7. CDN Manifest 動態解析測試 (Hermetic Mock) ────────────────

    def test_cdn_manifest_discovery_hermetic_mock(self):
        """
        在完全隔離無網路環境下，透過 Mock 驗證 discover_bundle_from_cdn_manifest 的解析邏輯：
        正確自 manifest 多行字串提取目標 bundle 之 pool_hash 與 compressed_size。
        """
        mock_manifest_body = (
            "a/other_bundle.unity3d,hash_a,pool_a,stage0,1234,\n"
            "a/masterdata_master.unity3d,md5_val,d93a6e336023c2fe,tutorial0,14171483,\n"
            "a/third_bundle.unity3d,hash_b,pool_b,stage0,5678,\n"
        ).encode("utf-8")

        mock_response = MagicMock()
        mock_response.read.return_value = mock_manifest_body
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            bundle_info = discover_bundle_from_cdn_manifest(
                truth_version="00600025",
                manifest_name="masterdata2_assetmanifest",
                target_bundle="a/masterdata_master.unity3d"
            )
            self.assertEqual(bundle_info["truth_version"], "00600025")
            self.assertEqual(bundle_info["bundle_pool_hash"], "d93a6e336023c2fe")
            self.assertEqual(bundle_info["bundle_compressed_size"], 14171483)

    # ──────────────── 8. 審查報表生成測試 ────────────────

    def test_review_table_generation(self):
        """驗證審查報表比對邏輯與 would_change 旗標精準度"""
        extracted = [
            {
                "chapter_id": 2214,
                "part": 3,
                "chapter_num": 14,
                "official_title": "阿爾莎特的誘惑",
                "raw_title": "第3部 第14章_阿爾莎特的誘惑",
                "provenance": "official_tw_masterdata"
            },
            {
                "chapter_id": 2215,
                "part": 3,
                "chapter_num": 15,
                "official_title": "嚮導幼君",  # 官方母檔
                "raw_title": "第3部 第15章_嚮導幼君",
                "provenance": "official_tw_masterdata"
            },
            {
                "chapter_id": 2213,
                "part": 3,
                "chapter_num": 13,
                "official_title": "降臨的幻境",
                "raw_title": "第3部 第13章_降臨的幻境",
                "provenance": "official_tw_masterdata"
            }
        ]

        review = generate_review_table(extracted)
        rev_by_id = {r["chapter_id"]: r for r in review}

        # 2214 在現有 chapters.json 中也是 "阿爾莎特的誘惑"
        self.assertIn(2214, rev_by_id)
        self.assertEqual(rev_by_id[2214]["current_title"], "阿爾莎特的誘惑")
        self.assertEqual(rev_by_id[2214]["official_title"], "阿爾莎特的誘惑")
        self.assertFalse(rev_by_id[2214]["would_change"])

        # 2215 在現有 chapters.json 中是 "響導幼君"，官方母檔為 "嚮導幼君"
        self.assertIn(2215, rev_by_id)
        self.assertEqual(rev_by_id[2215]["current_title"], "響導幼君")
        self.assertEqual(rev_by_id[2215]["official_title"], "嚮導幼君")
        self.assertTrue(rev_by_id[2215]["would_change"], "2215 應檢測出字元差異 (響導 -> 嚮導)")

        # 2213 在現有 chapters.json 中是 null (unresolved)
        self.assertIn(2213, rev_by_id)
        self.assertIsNone(rev_by_id[2213]["current_title"])
        self.assertEqual(rev_by_id[2213]["official_title"], "降臨的幻境")
        self.assertTrue(rev_by_id[2213]["would_change"])


if __name__ == "__main__":
    unittest.main()
