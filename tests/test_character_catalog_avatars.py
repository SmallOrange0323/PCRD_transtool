#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Character Catalog Avatar Local Resolution & Bundler Regression Tests

測試範疇：
1. AvatarService.getCharacterCardAvatarHtml API 存在性與語意規範
2. 驗證資料庫 unit_id xxxx01 正常規整化至代表頭像 xxxx11.png (杜絕文字佔位符)
3. 驗證原缺失 7 位可玩角色 (181101, 181001, 180901, 180801, 180701, 123001, 118601) 均產生合法 img 標籤
4. 驗證資料庫全部 334 位可玩角色 100% 產生合法代表頭像 img 標籤
5. 驗證 characters.js 統一呼叫 getCharacterCardAvatarHtml，無遺漏之 getAvatarHtmlByUnitId
6. 驗證 Story Map 既有對白頭像 Exact-ID 語意與行為零破壞、零回歸
7. 驗證 get_character_catalog_icon_mappings 完整納入可玩角色代表頭像
8. 驗證 get_expected_icon_unit_mappings 為對白與角色圖鑑之決定性聯集 (Deterministic Union)
"""

import os
import sys
import json
import sqlite3
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import (
    get_expected_icon_unit_mappings,
    get_expected_dialogue_icon_mappings,
    get_character_catalog_icon_mappings,
    get_playable_character_unit_ids,
    DASHBOARD_DIR
)

class TestCharacterCatalogAvatars(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.avatar_service_js = DASHBOARD_DIR / "avatar-service.js"
        cls.characters_js = DASHBOARD_DIR / "characters.js"
        cls.db_path = DASHBOARD_DIR / "redive_tw.db"

    def _run_node_avatar_eval(self, js_code: str) -> str:
        """在隔離 Node.js 環境中載入 avatar-service.js 並評估 JS 表達式"""
        js_path_posix = self.avatar_service_js.as_posix()
        wrapper = f"""
        const fs = require('fs');
        const code = fs.readFileSync('{js_path_posix}', 'utf8');
        eval(code);
        {js_code}
        """
        res = subprocess.run(
            ["node", "-e", wrapper],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True
        )
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip() and line.strip() != "avatar-service.js loaded"]
        return lines[-1] if lines else ""

    def test_01_avatar_service_character_card_method_exists(self):
        """1. 驗證 AvatarService.getCharacterCardAvatarHtml 存在且為函式"""
        output = self._run_node_avatar_eval("""
        console.log(typeof AvatarService.getCharacterCardAvatarHtml);
        """)
        self.assertEqual(output, "function")

    def test_02_database_unit_id_normalizes_to_11_portrait(self):
        """2. 驗證傳入資料庫 unit_id 181201 (雪菲 公主) 能正常解析至 181211.png，絕不直接降級為文字佔位符"""
        output = self._run_node_avatar_eval("""
        const html = AvatarService.getCharacterCardAvatarHtml(181201, '雪菲（公主）');
        console.log(JSON.stringify({
            html: html,
            isImg: html.includes('<img src="icon/unit/181211.png"'),
            hasPlaceholder: html.includes('npc-avatar-placeholder'),
            hasErrorFallback: html.includes("AvatarService.handleError(this,") && html.includes("181201)")
        }));
        """)
        data = json.loads(output)
        self.assertTrue(data["isImg"], f"Expected 181211.png img tag, got: {data['html']}")
        self.assertFalse(data["hasPlaceholder"], "Must not fall back to text placeholder")
        self.assertTrue(data["hasErrorFallback"], "Must include onerror fallback to handleError")

    def test_03_missing_7_characters_resolve_to_canonical_card_avatars(self):
        """3. 驗證原先缺失的 7 位角色均可正常生成合法代表頭像 img 標籤"""
        missing_7 = [
            (181101, "靜流＆璃乃", 181111),
            (181001, "安＆古蕾婭", 181011),
            (180901, "秋乃&咲戀", 180911),
            (180801, "禊＆美美＆鏡華", 180811),
            (180701, "初音＆栞", 180711),
            (123001, "愛梅斯", 123011),
            (118601, "涅比亞", 118611),
        ]
        for uid, name, expected_icon_id in missing_7:
            output = self._run_node_avatar_eval(f"""
            const html = AvatarService.getCharacterCardAvatarHtml({uid}, '{name}');
            console.log(JSON.stringify({{
                html: html,
                expectedSrc: 'icon/unit/{expected_icon_id}.png',
                isMatch: html.includes('icon/unit/{expected_icon_id}.png'),
                hasPlaceholder: html.includes('npc-avatar-placeholder')
            }}));
            """)
            data = json.loads(output)
            self.assertTrue(data["isMatch"], f"ID {uid} ({name}) failed to match {expected_icon_id}: {data['html']}")
            self.assertFalse(data["hasPlaceholder"], f"ID {uid} ({name}) must not produce placeholder")

    def test_04_all_334_db_playable_characters_generate_valid_img_tags(self):
        """4. 驗證資料庫全部 334 位可玩角色 100% 產生合法代表頭像 img 標籤"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT t.max_id, u.unit_name 
            FROM (
                SELECT MAX(unit_id) as max_id, unit_name 
                FROM unit_data 
                WHERE unit_id < 200000 AND unit_id > 100000 
                AND unit_name NOT LIKE '%怪物%'
                AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
                GROUP BY unit_name
            ) as t
            JOIN unit_data as u ON u.unit_id = t.max_id
            ORDER BY unit_id DESC
        """)
        playable = c.fetchall()
        conn.close()

        self.assertEqual(len(playable), 334)

        eval_payload = json.dumps(playable, ensure_ascii=False)
        output = self._run_node_avatar_eval(f"""
        const units = {eval_payload};
        let validImgs = 0;
        let placeholders = 0;
        const failedList = [];

        for (const [uid, name] of units) {{
            const html = AvatarService.getCharacterCardAvatarHtml(uid, name);
            if (html.includes('<img src="icon/unit/')) {{
                validImgs++;
            }} else {{
                placeholders++;
                failedList.push([uid, name, html]);
            }}
        }}
        console.log(JSON.stringify({{
            total: units.length,
            validImgs: validImgs,
            placeholders: placeholders,
            failedList: failedList
        }}));
        """)
        data = json.loads(output)
        self.assertEqual(data["validImgs"], 334, f"Failed characters: {data['failedList']}")
        self.assertEqual(data["placeholders"], 0)

    def test_05_characters_js_uses_character_card_avatar_method(self):
        """5. 靜態斷言 characters.js 統一改用 getCharacterCardAvatarHtml，無遺漏之 getAvatarHtmlByUnitId"""
        content = self.characters_js.read_text(encoding="utf-8")
        self.assertNotIn(
            "AvatarService.getAvatarHtmlByUnitId",
            content,
            "characters.js must not call getAvatarHtmlByUnitId"
        )
        self.assertIn(
            "AvatarService.getCharacterCardAvatarHtml",
            content,
            "characters.js must call getCharacterCardAvatarHtml"
        )

    def test_06_dialogue_avatar_resolver_unmodified(self):
        """6. 驗證既有對白頭像 Exact-ID 語意完全不受影響 (非 active 或未登錄仍嚴格 Fail-Closed)"""
        output = self._run_node_avatar_eval("""
        // 傳入資料庫 ID 181201 至對白解析器：因為非 active 對白資產，依舊必須嚴格 fail-closed 為文字佔位符
        const dialogueHtml = AvatarService.getAvatarHtmlByUnitId(181201, '雪菲（公主）');
        console.log(JSON.stringify({
            hasPlaceholder: dialogueHtml.includes('npc-avatar-placeholder')
        }));
        """)
        data = json.loads(output)
        self.assertTrue(
            data["hasPlaceholder"],
            "Dialogue resolver must remain unchanged and fail closed on unmanifested IDs"
        )

    def test_07_bundler_character_catalog_mappings_covers_all_playable(self):
        """7. 驗證 get_character_catalog_icon_mappings 之預期打包覆蓋 (expected bundle coverage，非實體 dist 檔案系統)"""
        playable_uids = get_playable_character_unit_ids()
        # 資料庫 334 位可玩角色 + tracked_characters.json 登錄之聯動角色 139401 (艾麗卡) = 335 位
        self.assertEqual(len(playable_uids), 335, f"Expected 335 playable characters (334 DB + 139401), got {len(playable_uids)}")
        self.assertIn(139401, playable_uids, "139401 (Erika) must be included from tracked_characters.json")

        catalog_mappings = get_character_catalog_icon_mappings()
        self.assertGreaterEqual(len(catalog_mappings), 670)

        # 驗證原缺失 7 位角色的 +11 與 +31 實體檔案都在預期打包映射中
        missing_7 = [181101, 181001, 180901, 180801, 180701, 123001, 118601]
        for uid in missing_7:
            base_id = (uid // 100) * 100
            self.assertIn(f"{base_id + 11}.png", catalog_mappings)
            self.assertIn(f"{base_id + 31}.png", catalog_mappings)
            self.assertTrue(catalog_mappings[f"{base_id + 11}.png"].exists())
            self.assertTrue(catalog_mappings[f"{base_id + 31}.png"].exists())

    def test_08_bundler_union_mappings_deterministic_and_contains_both(self):
        """8. 驗證 get_expected_icon_unit_mappings 完整包含對白與角色圖鑑資產 (聯集大於對白集合)"""
        dialogue_mappings = get_expected_dialogue_icon_mappings()
        catalog_mappings = get_character_catalog_icon_mappings()
        union_mappings = get_expected_icon_unit_mappings()

        self.assertEqual(len(dialogue_mappings), 927)
        self.assertEqual(len(union_mappings), 1143)

        # 驗證對白資產 100% 存在於 union 中
        for k in dialogue_mappings:
            self.assertIn(k, union_mappings)

        # 驗證角色圖鑑資產 100% 存在於 union 中
        for k in catalog_mappings:
            self.assertIn(k, union_mappings)

        # 驗證順序為嚴格字母遞增 (deterministic)
        keys_list = list(union_mappings.keys())
        self.assertEqual(keys_list, sorted(keys_list))

if __name__ == "__main__":
    unittest.main()
