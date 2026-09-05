# -*- coding: utf-8 -*-
"""
主線劇情章節元數據與來源隔離單元測試 (tests/test_chapter_metadata.py)

驗證範圍：
A. 2214 標題為 '阿爾莎特的誘惑'
B. 2215 標題為 '響導幼君' (嚴格採用官方實機 '響導' 字樣)
C. 2216 標題為 '三方爭霸'
D. 2214-2216 來源標記為 'official_tw_game_ui'
E. 2213 (未解析) 標題為 null，章節 key 為 '第13章'
F. legacy_title 僅供溯源，不可作為 official title (title 保持 None)
G. title_provenance == 'unresolved' 時若 title 為非空字串，驗證必須失敗
H. title_provenance == 'official_tw_game_ui' 時若 title 為 null，驗證必須失敗
I. 若不同章節存在相同標題文字，驗證器不可報錯（允許合法同名）
J. 若章節標題恰好與話數副標題文字相同，驗證器不可報錯
K. 保留之歷史摘要 summary_provenance 必須為 'legacy_unverified'
L. 不支援之 summary_provenance 值必須導致驗證失敗 (負向測試)
"""

import os
import sys
import json
import unittest
import copy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.validate import validate_chapters_metadata

CHAPTERS_PATH = PROJECT_ROOT / 'dashboard' / 'data' / 'chapters.json'

class TestChapterMetadataProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CHAPTERS_PATH, 'r', encoding='utf-8') as f:
            cls.data = json.load(f)

    def _get_chapter(self, cid):
        for part in ['1', '2', '3']:
            gw = self.data.get(part, {}).get('game_world', {})
            if cid in gw:
                return gw[cid]
        return None

    def _all_game_world(self, data_dict=None):
        target = data_dict if data_dict is not None else self.data
        res = {}
        for part in ['1', '2', '3']:
            gw = target.get(part, {}).get('game_world', {})
            for cid, info in gw.items():
                res[cid] = info
        return res

    def test_a_chapter_2214_title(self):
        """A. 2214 標題應為 '阿爾莎特的誘惑'"""
        info = self._get_chapter('2214')
        self.assertIsNotNone(info, '章節 2214 不存在')
        self.assertEqual(info.get('title'), '阿爾莎特的誘惑')

    def test_b_chapter_2215_title(self):
        """B. 2215 標題應為 '響導幼君' (必須完全相符，不可擅自改為嚮導)"""
        info = self._get_chapter('2215')
        self.assertIsNotNone(info, '章節 2215 不存在')
        self.assertEqual(info.get('title'), '響導幼君')

    def test_c_chapter_2216_title(self):
        """C. 2216 標題應為 '三方爭霸'"""
        info = self._get_chapter('2216')
        self.assertIsNotNone(info, '章節 2216 不存在')
        self.assertEqual(info.get('title'), '三方爭霸')

    def test_d_official_provenance(self):
        """D. 2214-2216 來源標記應為 'official_tw_game_ui'"""
        for cid in ['2214', '2215', '2216']:
            info = self._get_chapter(cid)
            self.assertIsNotNone(info, f'章節 {cid} 不存在')
            self.assertEqual(info.get('title_provenance'), 'official_tw_game_ui', f'{cid} 來源標記不符')

    def test_e_unresolved_chapter_2213(self):
        """E. 2213 為未解析章節，title 應為 null，章節 key 應為 '第13章'"""
        info = self._get_chapter('2213')
        self.assertIsNotNone(info, '章節 2213 不存在')
        self.assertIsNone(info.get('title'))
        self.assertEqual(info.get('key'), '第13章')
        self.assertEqual(info.get('title_provenance'), 'unresolved')
        self.assertTrue(bool(info.get('legacy_title')), '未解析章節 2213 應保留 legacy_title')

    def test_f_legacy_title_not_official(self):
        """F. 未解析章節之 legacy_title 僅供溯源，不可被視為 official title (title 必須為 null)"""
        all_gw = self._all_game_world()
        for cid, info in all_gw.items():
            if info.get('title_provenance') == 'unresolved':
                self.assertIsNone(info.get('title'), f'未解析章節 {cid} 之 title 必須為 null')
                self.assertIsNotNone(info.get('legacy_title'), f'未解析章節 {cid} 應保留 legacy_title')

    def test_g_invalid_unresolved_with_title(self):
        """G. title_provenance == 'unresolved' 時若 title 為非空字串，validate_chapters_metadata 應失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2213']['title'] = '某個未授權標題'
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid)
        self.assertIn('2213', msg)

    def test_h_invalid_official_with_null_title(self):
        """H. title_provenance == 'official_tw_game_ui' 時若 title 為 null，validate_chapters_metadata 應失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2214']['title'] = None
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid)
        self.assertIn('2214', msg)

    def test_i_duplicate_titles_allowed(self):
        """I. 若不同章節存在相同標題文字，驗證器不可報錯（允許合法同名）"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2216']['title'] = mutated['3']['game_world']['2214']['title']
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertTrue(is_valid, f'驗證器不應拒絕重複章節標題: {msg}')

    def test_j_same_title_as_episode_allowed(self):
        """J. 若章節標題與話數副標題文字相同，驗證器不可報錯"""
        mutated = copy.deepcopy(self.data)
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertTrue(is_valid, f'章節元數據自身驗證通過: {msg}')

    def test_k_summary_provenance_legacy_unverified(self):
        """K. 保留之歷史綱要 summary_provenance 必須全部標記為 'legacy_unverified'"""
        all_gw = self._all_game_world()
        self.assertEqual(len(all_gw), 48, 'game_world 章節總數應為 48')
        for cid, info in all_gw.items():
            self.assertEqual(
                info.get('summary_provenance'),
                'legacy_unverified',
                f'章節 {cid} 之 summary_provenance 必須為 legacy_unverified'
            )

    def test_l_invalid_summary_provenance_fails_validation(self):
        """L. 負向測試：不支援之 summary_provenance 值必須導致驗證失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2214']['summary_provenance'] = 'unsupported_custom_provenance'
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid, '不合法的 summary_provenance 應該使驗證失敗')
        self.assertIn('2214', msg)
        self.assertIn('summary_provenance', msg)

    def test_current_chapters_json_passes_validator(self):
        """確認現有 chapters.json 完全通過驗證器"""
        is_valid, msg = validate_chapters_metadata(self.data)
        self.assertTrue(is_valid, f'現有 chapters.json 驗證失敗: {msg}')


if __name__ == '__main__':
    unittest.main()
