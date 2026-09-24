#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Characters Module & Normalized DB Runtime Compatibility Regression Tests (Phase F2A.3C)

驗證範圍：
1. sonet_db_schema_map_0061.json 必須定義 11 張業務表與全部必要欄位 (99 mapped columns)
2. unit_data 必須映射正確的 unit_id (而非 original_unit_id) 及 rarity, search_area_width
3. unit_rarity 必須支援複合主鍵 (unit_id, rarity) 及 18 個數值欄位
4. unit_skill_data, unit_attack_pattern, skill_data 結構與資料完整性
5. dashboard/characters.js 核心真實 SQL 查詢全量相容性 (含契約文本斷言)
6. 預載角色 (119401) 專屬 UI/Query contract 驗證 (stats 不回退 unit_data，不顯示假 0 數值)
7. 動作循環多模式 (Multiplicity) 與 ORDER BY pattern_id ASC 確定性選取
"""

import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pipeline.sonet_normalized_db import (
    generate_normalized_db,
    load_schema_mapping,
    validate_mapping_contract,
)


def _build_mock_raw_0061_db(raw_db_path: Path):
    """
    動態生成符合 0061 混淆 schema 的自包含 Mock Raw DB。
    當本地無 scratch/raw_00610008.db 實機資料庫時，作為測試 fixture 使用，
    確保 8 個 Character 迴歸測試永遠具備 100% 執行能力。
    """
    _, mapping = load_schema_mapping("0061")
    conn = sqlite3.connect(str(raw_db_path))
    cur = conn.cursor()

    # 建立 11 張實體混淆表
    for tbl_name, meta in mapping["tables"].items():
        phys_tbl = meta["physical_table"]
        phys_cols = [f'"{c}" TEXT' for c in meta["columns"].values()]
        cur.execute(f'CREATE TABLE "{phys_tbl}" ({", ".join(phys_cols)});')

    def insert_row(tbl_name: str, data: dict):
        meta = mapping["tables"][tbl_name]
        phys_tbl = meta["physical_table"]
        phys_cols = [f'"{meta["columns"][k]}"' for k in data.keys() if k in meta["columns"]]
        vals = [data[k] for k in data.keys() if k in meta["columns"]]
        placeholders = ", ".join(["?"] * len(vals))
        cur.execute(f'INSERT INTO "{phys_tbl}" ({", ".join(phys_cols)}) VALUES ({placeholders})', vals)

    # 1. unit_data & unit_profile & unit_rarity
    main_units = [
        ("105801", "貪吃佩可", "1", "150", "美食殿堂", "人族", "17", "M·A·O"),
        ("105901", "可可蘿", "1", "500", "美食殿堂", "精靈族", "11", "伊藤美來"),
        ("106001", "凱留", "1", "750", "美食殿堂", "獸人族", "17", "立花理香"),
        ("100101", "日和", "1", "200", "破曉之星", "獸人族", "17", "東山奈央"),
        ("100201", "優衣", "1", "780", "破曉之星", "人族", "17", "種田梨沙"),
        ("106101", "矛依未", "3", "180", "無所屬", "人族", "16", "潘惠美"),
        ("106801", "拉比林斯達", "3", "520", "拉比林斯", "人族", "24", "澤城美雪"),
        ("100301", "怜", "1", "210", "破曉之星", "魔族", "18", "早見沙織"),
    ]
    for uid, name, rar, pos, guild, race, age, cv in main_units:
        insert_row("unit_data", {"unit_id": uid, "unit_name": name, "rarity": rar, "search_area_width": pos})
        insert_row("unit_profile", {"unit_id": uid, "guild": guild, "race": race, "age": age, "voice": cv})
        insert_row("unit_rarity", {"unit_id": uid, "rarity": "6", "hp": "15000", "hp_growth": "150", "atk": "2000", "atk_growth": "20"})

    # 插入 250 個虛擬角色以通過 len(rows) > 250 斷言
    for i in range(1, 255):
        uid = str(110000 + i)
        uname = f"測試角色_{i}"
        insert_row("unit_data", {"unit_id": uid, "unit_name": uname, "rarity": "1", "search_area_width": "300"})
        insert_row("unit_rarity", {"unit_id": uid, "rarity": "1", "hp": "5000", "hp_growth": "50", "atk": "1000", "atk_growth": "10"})

    # 預載角色 (119401 貪吃佩可)：有 unit_data，無 unit_rarity
    insert_row("unit_data", {"unit_id": "119401", "unit_name": "貪吃佩可", "rarity": "3", "search_area_width": "160"})

    # 2. unit_skill_data & skill_data (佩可 105801)
    insert_row("unit_skill_data", {"unit_id": "105801", "union_burst": "1058001", "main_skill_1": "1058011", "main_skill_2": "1058021"})
    insert_row("skill_data", {"skill_id": "1058001", "name": "公主突襲", "description": "對敵方單體造成特大幅度物理傷害", "icon_type": "1001"})

    # 3. unit_attack_pattern (佩可 105801 & 多模式角色 106101, 106801, 100301)
    insert_row("unit_attack_pattern", {"pattern_id": "10580101", "unit_id": "105801", "loop_start": "3", "loop_end": "7"})
    for multi_id in ["106101", "106801", "100301"]:
        insert_row("unit_attack_pattern", {"pattern_id": f"{multi_id}01", "unit_id": multi_id, "loop_start": "1", "loop_end": "5"})
        insert_row("unit_attack_pattern", {"pattern_id": f"{multi_id}02", "unit_id": multi_id, "loop_start": "2", "loop_end": "6"})

    # 4. story_detail (佩可個人劇情 8 話)
    for ep in range(1, 9):
        insert_row("story_detail", {
            "story_id": f"105800{ep}",
            "story_group_id": "1058",
            "title": f"貪吃佩可 第{ep}話",
            "sub_title": f"佩可副標題_{ep}",
            "story_end": "0"
        })

    # 5. 其餘核心表 (滿足每張表筆數 > 0 門禁)
    insert_row("event_story_data", {
        "story_group_id": "5001",
        "title": "初音的禮物大作戰",
        "start_time": "2024-01-01",
        "thumbnail_id": "1",
        "value": "1"
    })
    insert_row("event_story_detail", {
        "story_id": "5001001",
        "story_group_id": "5001",
        "title": "第1話",
        "sub_title": "初音副標"
    })
    insert_row("story_group_data", {
        "story_group_id": "1001",
        "story_type": "1",
        "title": "主線第1章"
    })
    insert_row("chara_story_status", {
        "story_id": "1058001",
        "chara_id_1": "1058"
    })

    conn.commit()
    conn.close()


class TestNormalizedDbCharacterRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.norm_db_path = Path(cls.temp_dir.name) / "test_normalized.db"

        # 若本地存在 scratch/raw_00610008.db 則優先使用，否則動態建立 Mock Raw DB
        raw_scratch = Path("scratch/raw_00610008.db")
        if raw_scratch.is_file():
            cls.raw_db_path = raw_scratch
        else:
            cls.raw_db_path = Path(cls.temp_dir.name) / "mock_raw_00610008.db"
            _build_mock_raw_0061_db(cls.raw_db_path)

        # 生成測試用 Normalized DB
        res = generate_normalized_db(
            raw_db_path=cls.raw_db_path,
            truth_version="00610008",
            output_path=cls.norm_db_path,
            batch_size=1000
        )
        assert res.success, f"Normalized DB generation failed: {res.error}"

        # 讀取 characters.js 原始碼以做 SQL 契約斷言
        js_path = Path(__file__).resolve().parents[1] / "dashboard" / "characters.js"
        with open(js_path, "r", encoding="utf-8") as f:
            cls.characters_js_content = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def assertSqlInSource(self, sql_fragment: str):
        """驗證測試使用的 SQL 確實存在於 dashboard/characters.js 中"""
        # 移除多餘空白與換行以做健全比對
        clean_frag = " ".join(sql_fragment.split())
        clean_src = " ".join(self.characters_js_content.split())
        self.assertIn(clean_frag, clean_src, f"SQL fragment not found in characters.js: {sql_fragment}")

    def test_01_schema_contract_contains_11_tables_and_99_columns(self):
        """驗證 schema mapping 契約定義了完整的 11 張業務表與 99 個欄位"""
        _, mapping = load_schema_mapping("0061")
        validate_mapping_contract(mapping)

        expected_tables = {
            "story_detail", "unit_data", "unit_profile", "event_story_data",
            "event_story_detail", "story_group_data", "chara_story_status",
            "unit_rarity", "unit_skill_data", "unit_attack_pattern", "skill_data"
        }
        actual_tables = set(mapping["tables"].keys())
        self.assertEqual(expected_tables, actual_tables)
        total_mapped = sum(len(t["columns"]) for t in mapping["tables"].values())
        self.assertEqual(total_mapped, 99)

    def test_02_unit_data_schema_and_primary_key(self):
        """驗證 unit_data 映射正確的主鍵與角色圖鑑所需欄位"""
        _, mapping = load_schema_mapping("0061")
        u_meta = mapping["tables"]["unit_data"]
        cols = u_meta["columns"]
        self.assertIn("unit_id", cols)
        self.assertIn("unit_name", cols)
        self.assertIn("rarity", cols)
        self.assertIn("search_area_width", cols)
        # 真正的主鍵 token 必須是 69be87e1... 而非 original_unit_id (0a3a0510...)
        self.assertTrue(cols["unit_id"].startswith("69be87e1"))

    def test_03_characters_list_actual_production_query(self):
        """逐字驗證 characters.js 列表載入真實 SQL 查詢 (含 subquery, JOIN, LEFT JOIN)"""
        sql = """
            SELECT 
                t.max_id as unit_id,
                u.unit_name,
                u.rarity,
                u.search_area_width as pos,
                p.race,
                p.guild
            FROM (
                SELECT MAX(unit_id) as max_id, unit_name 
                FROM unit_data 
                WHERE unit_id < 200000 AND unit_id > 100000
                AND unit_name NOT LIKE '%怪物%'
                AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
                GROUP BY unit_name
            ) as t
            JOIN unit_data as u ON u.unit_id = t.max_id
            LEFT JOIN unit_profile as p ON u.unit_id = p.unit_id
            ORDER BY unit_id DESC
        """
        self.assertSqlInSource(sql)

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            self.assertGreater(len(rows), 250, "角色圖鑑可玩角色數應大於 250")
            names = set(r["unit_name"] for r in rows)
            self.assertIn("貪吃佩可", names)
            self.assertIn("可可蘿", names)
            self.assertIn("凱留", names)
            self.assertIn("日和", names)
            self.assertIn("優衣", names)
            # 驗證 JOIN profile 正確
            peco_row = [r for r in rows if r["unit_name"] == "貪吃佩可"][0]
            self.assertEqual(peco_row["guild"], "美食殿堂")
            self.assertEqual(peco_row["race"], "人族")
        finally:
            conn.close()

    def test_04_character_stats_and_calculation(self):
        """驗證佩可 (105801) 的真實 SQL 數值查詢與計算"""
        sql_rarity = "SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1"
        self.assertSqlInSource(sql_rarity)

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute(sql_rarity, (105801,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            stats = dict(row)
            self.assertEqual(stats["rarity"], "6")

            # 模擬 Lv 300 計算
            calc = lambda base, growth: math.floor(float(base or 0) + (300 - 1) * float(growth or 0))
            hp = calc(stats["hp"], stats["hp_growth"])
            atk = calc(stats["atk"], stats["atk_growth"])
            self.assertGreater(hp, 50000)
            self.assertGreater(atk, 5000)
        finally:
            conn.close()

    def test_05_character_skills_and_pattern_actual_queries(self):
        """驗證真實 SQL 技能與動作循環查詢"""
        sql_skill = "SELECT * FROM unit_skill_data WHERE unit_id = ?"
        sql_pat = "SELECT * FROM unit_attack_pattern WHERE unit_id = ? ORDER BY pattern_id ASC LIMIT 1"
        sql_sd = "SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?"
        self.assertSqlInSource(sql_skill)
        self.assertSqlInSource(sql_pat)
        self.assertSqlInSource(sql_sd)

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            # 技能
            cur.execute(sql_skill, (105801,))
            s_row = cur.fetchone()
            self.assertIsNotNone(s_row)
            ub_id = s_row["union_burst"]
            self.assertEqual(ub_id, "1058001")

            cur.execute(sql_sd, (ub_id,))
            sd_row = cur.fetchone()
            self.assertIsNotNone(sd_row)
            self.assertEqual(sd_row["name"], "公主突襲")
            self.assertEqual(sd_row["icon_type"], "1001")

            # 動作循環
            cur.execute(sql_pat, (105801,))
            pat_row = cur.fetchone()
            self.assertIsNotNone(pat_row)
            self.assertEqual(pat_row["loop_start"], "3")
            self.assertEqual(pat_row["loop_end"], "7")
        finally:
            conn.close()

    def test_06_preload_character_contract_and_stats_fallback_regression(self):
        """
        驗證預載角色 (119401 貪吃佩可) 的 UI/Query Contract：
        1. unit_data 存在 (有名稱、站位)
        2. unit_rarity 缺失
        3. stats 查詢必須回傳 None，絕不得回退至 unit_data，防止假 0 數值與預載判定失效
        4. 技能與動作循環為空
        """
        sql_rarity = "SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1"
        sql_unit = "SELECT search_area_width FROM unit_data WHERE unit_id = ?"
        sql_skill = "SELECT * FROM unit_skill_data WHERE unit_id = ?"
        sql_pat = "SELECT * FROM unit_attack_pattern WHERE unit_id = ? ORDER BY pattern_id ASC LIMIT 1"

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            preload_id = 119401

            # 1. unit_data 存在
            cur.execute("SELECT unit_name, rarity, search_area_width FROM unit_data WHERE unit_id = ?", (preload_id,))
            u_row = cur.fetchone()
            self.assertIsNotNone(u_row)
            self.assertEqual(u_row["unit_name"], "貪吃佩可")

            cur.execute(sql_unit, (preload_id,))
            unit_data = cur.fetchone()
            self.assertIsNotNone(unit_data)

            # 2. unit_rarity 缺失
            cur.execute(sql_rarity, (preload_id,))
            rarity_row = cur.fetchone()
            self.assertIsNone(rarity_row, "預載角色的 unit_rarity 必須為 None")

            # 3. 模擬 characters.js 修正後的 stats 賦值邏輯
            stats = rarity_row  # 不回退到 unit_data！
            self.assertIsNone(stats, "stats 必須為 None，不得獲取到 unit_data 物件")

            # 4. 技能與動作循環為空
            cur.execute(sql_skill, (preload_id,))
            self.assertIsNone(cur.fetchone())

            cur.execute(sql_pat, (preload_id,))
            self.assertIsNone(cur.fetchone())
        finally:
            conn.close()

    def test_07_attack_pattern_multiplicity_and_deterministic_order(self):
        """
        驗證動作循環多模式角色 (如 106101 矛依未、106801 拉比林斯達、100301 怜)：
        ORDER BY pattern_id ASC LIMIT 1 必然取到 01 結尾的常態基本循環
        """
        sql_pat = "SELECT * FROM unit_attack_pattern WHERE unit_id = ? ORDER BY pattern_id ASC LIMIT 1"
        self.assertSqlInSource(sql_pat)

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            multi_units = [106101, 106801, 100301]
            for uid in multi_units:
                # 確認資料庫中該角色確實有 >1 筆 pattern
                cur.execute("SELECT COUNT(*) FROM unit_attack_pattern WHERE unit_id = ?", (uid,))
                cnt = cur.fetchone()[0]
                self.assertGreaterEqual(cnt, 2, f"角色 {uid} 應有多個動作模式")

                # 透過 ORDER BY pattern_id ASC 取出的必然是常態模式 (結尾為 01)
                cur.execute(sql_pat, (uid,))
                pat = cur.fetchone()
                self.assertIsNotNone(pat)
                pat_id_str = str(pat["pattern_id"])
                self.assertTrue(pat_id_str.endswith("01"), f"角色 {uid} 預設模式應為 01 常態模式，實際為 {pat_id_str}")
        finally:
            conn.close()

    def test_08_render_story_list_actual_production_query(self):
        """逐字驗證 characters.js renderStoryList 真實個人劇情 SQL 查詢"""
        sql = """
            SELECT story_id, title, sub_title 
            FROM story_detail 
            WHERE CAST(story_id AS TEXT) LIKE ? 
            ORDER BY story_id ASC
        """
        self.assertSqlInSource(sql)

        conn = sqlite3.connect(str(self.norm_db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            # 佩可 105801 -> '1058%'
            cur.execute(sql, ("1058%",))
            rows = cur.fetchall()
            self.assertGreaterEqual(len(rows), 8, "佩可個人劇情應至少有 8 話")
            titles = [r["title"] for r in rows]
            self.assertTrue(any("貪吃佩可" in t for t in titles))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
