"""NPC 頭像圖鑑資料 (`dashboard/data/npc_catalog.json`) 與生成腳本之單元及全語料稽核測試。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard.scripts.generate_npc_catalog import (
    AVATAR_ASSETS_PATH,
    EXCLUDED_NPC_NAMES,
    FEMALE_NPC_NAMES,
    NPC_CATALOG_PATH,
    RULES_PATH,
    UNIT_ICON_DIR,
    build_npc_catalog,
    load_active_avatar_unit_ids,
)
from dashboard.scripts.generate_speaker_appearance import has_japanese_kana


class TestNpcCatalog(unittest.TestCase):
    """驗證 npc_catalog.json 的 Schema、資產一致性、排除規則、性別與故事分類統計。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assert_catalog_exists = NPC_CATALOG_PATH.is_file()
        cls.catalog = json.loads(NPC_CATALOG_PATH.read_text(encoding="utf-8"))
        cls.rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        cls.active_unit_ids = load_active_avatar_unit_ids(AVATAR_ASSETS_PATH)

    def test_01_file_and_top_level_schema(self) -> None:
        self.assertTrue(self.assert_catalog_exists)
        self.assertEqual(self.catalog.get("version"), 1)
        meta = self.catalog.get("metadata")
        npcs = self.catalog.get("npcs")
        self.assertIsInstance(meta, dict)
        self.assertIsInstance(npcs, list)
        self.assertGreater(len(npcs), 0)

        for key in ("total_npcs", "female_count", "main_count", "event_count", "special_count"):
            self.assertIn(key, meta)
            self.assertIsInstance(meta[key], int)

        self.assertEqual(meta["total_npcs"], len(npcs))
        self.assertEqual(meta["female_count"], sum(1 for n in npcs if n["gender"] == "female"))
        self.assertEqual(meta["main_count"], sum(1 for n in npcs if n["main_count"] > 0))
        self.assertEqual(meta["event_count"], sum(1 for n in npcs if n["event_count"] > 0))
        self.assertEqual(meta["special_count"], sum(1 for n in npcs if n["is_special"]))

        # 排序規則：appearance_count 降冪、name 升冪
        sort_keys = [(-n["appearance_count"], n["name"]) for n in npcs]
        self.assertEqual(sort_keys, sorted(sort_keys))

    def test_02_item_schema_and_scope_sums(self) -> None:
        required_keys = {
            "name",
            "unit_id",
            "gender",
            "appearance_count",
            "main_count",
            "event_count",
            "other_count",
            "story_scopes",
            "is_special",
            "special_label",
            "aliases",
            "variants",
        }
        seen_names: set[str] = set()
        for item in self.catalog["npcs"]:
            self.assertEqual(set(item.keys()), required_keys)
            name = item["name"]
            self.assertNotIn(name, seen_names)
            seen_names.add(name)

            self.assertIsInstance(item["unit_id"], int)
            self.assertIn(item["gender"], ("female", "male", "other"))
            self.assertGreater(item["appearance_count"], 0)
            self.assertEqual(
                item["main_count"] + item["event_count"] + item["other_count"],
                item["appearance_count"],
                msg=f"{name} 分類話數加總不等於 appearance_count",
            )

            expected_scopes = [
                scope
                for scope, cnt in (
                    ("main", item["main_count"]),
                    ("event", item["event_count"]),
                    ("other", item["other_count"]),
                )
                if cnt > 0
            ]
            self.assertEqual(item["story_scopes"], expected_scopes)
            self.assertIsInstance(item["aliases"], list)
            self.assertIsInstance(item["variants"], list)

            if not item["is_special"]:
                self.assertIsNone(item["special_label"])
                self.assertEqual(item["variants"], [])

    def test_03_all_unit_ids_active_and_on_disk(self) -> None:
        for item in self.catalog["npcs"]:
            uids_to_check = [item["unit_id"]] + [v["unit_id"] for v in item["variants"]]
            for uid in uids_to_check:
                self.assertIn(
                    uid,
                    self.active_unit_ids,
                    msg=f"{item['name']} 的 unit_id={uid} 不在 avatar_assets.json active PNG 中",
                )
                png_path = UNIT_ICON_DIR / f"{uid:06d}.png"
                self.assertTrue(
                    png_path.is_file(),
                    msg=f"{item['name']} 缺少磁碟頭像 {png_path}",
                )

    def test_04_exclusions_no_kana_entities_or_secondary_aliases(self) -> None:
        entities = set(self.rules.get("entities", {}).keys())
        entity_rules = set(self.rules.get("speaker_rules", {}).keys())
        secondary_npc_aliases = {
            alias
            for alias, entries in self.rules.get("npc_rules", {}).items()
            if all(e.get("npc_group") != alias for e in entries)
        }

        catalog_names = {item["name"] for item in self.catalog["npcs"]}
        for name in catalog_names:
            self.assertFalse(has_japanese_kana(name), msg=f"圖鑑不可含假名角色: {name}")
            self.assertNotIn(name, entities, msg=f"圖鑑不可含 entity: {name}")
            self.assertNotIn(name, entity_rules, msg=f"圖鑑不可含 entity speaker_rules: {name}")
            self.assertNotIn(name, secondary_npc_aliases, msg=f"圖鑑不可含次要別名: {name}")
            self.assertNotIn(name, EXCLUDED_NPC_NAMES, msg=f"圖鑑不可含排除角色: {name}")

    def test_05_special_secretary_and_fixed_npcs(self) -> None:
        by_name = {item["name"]: item for item in self.catalog["npcs"]}

        self.assertIn("秘書", by_name)
        sec = by_name["秘書"]
        self.assertTrue(sec["is_special"])
        self.assertEqual(sec["special_label"], "秘書子")
        self.assertEqual(sec["gender"], "female")
        self.assertIn("秘書子", sec["aliases"])
        self.assertEqual(
            sec["variants"],
            [{"unit_id": 6111, "label": "常服"}, {"unit_id": 6112, "label": "泳裝"}],
        )

        expected_fixed = {
            "女性教員": 3211,
            "魔物的公主": 7011,
            "神燈精靈": 5313,
            "鬼魂教父": 14011,
            "惡代官": 11411,
            "聖誕老人": 3911,
            "山神大人": 12711,
            "黑之王": 13411,
            "長老": 107212,
            "嚮導老君": 107211,
            "哥布林女士": 19411,
            "輔佐": 8711,
            "老虎族族長": 8611,
            "鬼族族長": 7412,
        }
        for name, expected_uid in expected_fixed.items():
            self.assertIn(name, by_name, msg=f"缺少固定 NPC: {name}")
            self.assertEqual(by_name[name]["unit_id"], expected_uid)

    def test_06_gender_precision(self) -> None:
        by_name = {item["name"]: item for item in self.catalog["npcs"]}

        for fname in FEMALE_NPC_NAMES:
            self.assertIn(fname, by_name, msg=f"女角白名單成員未收錄: {fname}")
            self.assertEqual(by_name[fname]["gender"], "female", msg=f"{fname} 應標為 female")

        must_not_be_female = ("卡里莎", "格魯尼", "亞斯來", "小樂", "帕克", "索菲", "摩拉")
        for mname in must_not_be_female:
            self.assertIn(mname, by_name, msg=f"驗證角色未收錄: {mname}")
            self.assertNotEqual(
                by_name[mname]["gender"],
                "female",
                msg=f"{mname} 嚴禁標記為 female",
            )

    def test_07_deterministic_rebuild(self) -> None:
        rebuilt = build_npc_catalog()
        self.assertEqual(rebuilt, self.catalog)


if __name__ == "__main__":
    unittest.main()
