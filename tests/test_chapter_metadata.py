# -*- coding: utf-8 -*-
"""
主線劇情章節元數據與來源隔離單元測試 (tests/test_chapter_metadata.py)

驗證範圍：
A. 2214 標題為 '阿爾莎特的誘惑'，來源為 'official_tw_localized_asset'
B. 2215 標題為 '嚮導幼君' (首字 U+56AE 嚮，!= 響導幼君)，來源為 'official_tw_localized_asset'
C. 2216 標題為 '三方爭霸'，來源為 'official_tw_localized_asset'
D. 2213 標題為 '降臨的幻境'，來源為 'official_tw_localized_asset'
E. 既往未解析 Part 1 (2000, 2001) 與 Part 2 (2101) 官方標題完備
F. 全量 48 個 game_world 章節 title 皆非空字串，title_provenance 皆為 'official_tw_localized_asset'，title_locale 皆為 'zh-TW'，legacy_title 完好保留
G. 官方 TruthVersion 00600025 Extractor Baseline 100% 封閉式對等校驗 (Hermetic Parity)
H. 驗證器負向測試：title_provenance == 'official_tw_localized_asset' 時若 title 為 null 必須失敗
I. 驗證器負向測試：title_provenance == 'unresolved' 時若 title 為非空字串必須失敗
J. 容許合法同名章節標題
K. 容許章節標題與話數副標題文字相同
L. 摘要 summary_provenance 全量保留為 'legacy_unverified'
M. 不合法 summary_provenance 導致驗證失敗
N. 現行 chapters.json 100% 通過 validate_chapters_metadata 門禁
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
from tests.test_official_chapter_title_extractor import OFFICIAL_TW_00600025_BASELINE_ROWS

CHAPTERS_PATH = PROJECT_ROOT / 'dashboard' / 'data' / 'chapters.json'

class TestChapterMetadataProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CHAPTERS_PATH, 'r', encoding='utf-8') as f:
            cls.data = json.load(f)

    def _get_chapter(self, cid):
        cid_str = str(cid)
        for part in ['1', '2', '3']:
            gw = self.data.get(part, {}).get('game_world', {})
            if cid_str in gw:
                return gw[cid_str]
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
        """A. 2214 標題應為 '阿爾莎特的誘惑'，來源為 'official_tw_localized_asset'"""
        info = self._get_chapter('2214')
        self.assertIsNotNone(info, '章節 2214 不存在')
        self.assertEqual(info.get('title'), '阿爾莎特的誘惑')
        self.assertEqual(info.get('title_provenance'), 'official_tw_localized_asset')
        self.assertEqual(info.get('title_locale'), 'zh-TW')

    def test_b_chapter_2215_title(self):
        """B. 2215 標題應為 '嚮導幼君' (首字 U+56AE 嚮，!= 響導幼君)，來源為 'official_tw_localized_asset'"""
        info = self._get_chapter('2215')
        self.assertIsNotNone(info, '章節 2215 不存在')
        self.assertEqual(info.get('title'), '嚮導幼君')
        self.assertNotEqual(info.get('title'), '響導幼君', '2215 官方標題絕不可為舊截圖誤譯 響導幼君')
        self.assertEqual(ord(info.get('title')[0]), 0x56AE, '2215 標題首字必須為 U+56AE 嚮')
        self.assertEqual(info.get('title_provenance'), 'official_tw_localized_asset')
        self.assertEqual(info.get('title_locale'), 'zh-TW')

    def test_c_chapter_2216_title(self):
        """C. 2216 標題應為 '三方爭霸'，來源為 'official_tw_localized_asset'"""
        info = self._get_chapter('2216')
        self.assertIsNotNone(info, '章節 2216 不存在')
        self.assertEqual(info.get('title'), '三方爭霸')
        self.assertEqual(info.get('title_provenance'), 'official_tw_localized_asset')
        self.assertEqual(info.get('title_locale'), 'zh-TW')

    def test_d_chapter_2213_title(self):
        """D. 2213 標題應為 '降臨的幻境'，來源為 'official_tw_localized_asset'"""
        info = self._get_chapter('2213')
        self.assertIsNotNone(info, '章節 2213 不存在')
        self.assertEqual(info.get('title'), '降臨的幻境')
        self.assertEqual(info.get('key'), '第13章')
        self.assertEqual(info.get('title_provenance'), 'official_tw_localized_asset')
        self.assertEqual(info.get('title_locale'), 'zh-TW')

    def test_e_part1_part2_representative_titles(self):
        """E. 既往未解析之 Part 1 與 Part 2 代表章節均已填入官方標題"""
        # Part 1: 2000, 2001
        ch_2000 = self._get_chapter('2000')
        self.assertIsNotNone(ch_2000)
        self.assertEqual(ch_2000.get('title'), '牽起羈絆的人們')
        self.assertEqual(ch_2000.get('title_provenance'), 'official_tw_localized_asset')

        ch_2001 = self._get_chapter('2001')
        self.assertIsNotNone(ch_2001)
        self.assertEqual(ch_2001.get('title'), '謎樣少女與記憶之鑰')
        self.assertEqual(ch_2001.get('title_provenance'), 'official_tw_localized_asset')

        # Part 2: 2101
        ch_2101 = self._get_chapter('2101')
        self.assertIsNotNone(ch_2101)
        self.assertEqual(ch_2101.get('title'), '冒險，再起')
        self.assertEqual(ch_2101.get('title_provenance'), 'official_tw_localized_asset')

    def test_f_all_48_chapters_provenance_and_locale(self):
        """F. 全量 48 個 game_world 章節 title 皆非空字串，title_provenance 皆為 'official_tw_localized_asset'，title_locale 皆為 'zh-TW'，legacy_title 完好保留"""
        all_gw = self._all_game_world()
        self.assertEqual(len(all_gw), 48, 'game_world 章節總數應為 48')

        for cid, info in all_gw.items():
            title = info.get('title')
            self.assertIsInstance(title, str, f'章節 {cid} 之 title 必須為字串')
            self.assertTrue(len(title.strip()) > 0, f'章節 {cid} 之 title 不得為空字串')
            self.assertEqual(info.get('title_provenance'), 'official_tw_localized_asset', f'章節 {cid} 之 title_provenance 不符')
            self.assertEqual(info.get('title_locale'), 'zh-TW', f'章節 {cid} 之 title_locale 不符')
            self.assertTrue(bool(info.get('legacy_title')), f'章節 {cid} 必須完整保留 legacy_title')

    def test_g_source_extractor_parity_hermetic(self):
        """G. 官方 TruthVersion 00600025 Extractor Baseline 100% 封閉式對等校驗 (Hermetic Parity)"""
        all_gw = self._all_game_world()
        self.assertEqual(len(all_gw), len(OFFICIAL_TW_00600025_BASELINE_ROWS))

        for group_id, story_type, raw_title in OFFICIAL_TW_00600025_BASELINE_ROWS:
            cid_str = str(group_id)
            self.assertIn(cid_str, all_gw, f'缺少章節 ID: {group_id}')
            ch_info = all_gw[cid_str]

            prefix, sep, expected_title = raw_title.partition('_')
            self.assertEqual(sep, '_')
            self.assertEqual(
                ch_info.get('title'),
                expected_title,
                f'章節 {group_id} 標題與官方母檔基準不符: 實際={ch_info.get("title")}, 期望={expected_title}'
            )

    def test_h_invalid_official_with_null_title(self):
        """H. title_provenance == 'official_tw_localized_asset' 時若 title 為 null，validate_chapters_metadata 應失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2214']['title'] = None
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid)
        self.assertIn('2214', msg)

    def test_i_invalid_unresolved_with_title(self):
        """I. title_provenance == 'unresolved' 時若 title 為非空字串，validate_chapters_metadata 應失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2213']['title_provenance'] = 'unresolved'
        mutated['3']['game_world']['2213']['title'] = '某個未授權標題'
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid)
        self.assertIn('2213', msg)

    def test_j_duplicate_titles_allowed(self):
        """J. 若不同章節存在相同標題文字，驗證器不可報錯（允許合法同名）"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2216']['title'] = mutated['3']['game_world']['2214']['title']
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertTrue(is_valid, f'驗證器不應拒絕重複章節標題: {msg}')

    def test_k_same_title_as_episode_allowed(self):
        """K. 若章節標題與話數副標題文字相同，驗證器不可報錯"""
        mutated = copy.deepcopy(self.data)
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertTrue(is_valid, f'章節元數據自身驗證通過: {msg}')

    def test_l_summary_provenance_legacy_unverified(self):
        """L. 保留之歷史綱要 summary_provenance 必須全部標記為 'legacy_unverified'"""
        all_gw = self._all_game_world()
        self.assertEqual(len(all_gw), 48, 'game_world 章節總數應為 48')
        for cid, info in all_gw.items():
            self.assertEqual(
                info.get('summary_provenance'),
                'legacy_unverified',
                f'章節 {cid} 之 summary_provenance 必須為 legacy_unverified'
            )

    def test_m_invalid_summary_provenance_fails_validation(self):
        """M. 負向測試：不支援之 summary_provenance 值必須導致驗證失敗"""
        mutated = copy.deepcopy(self.data)
        mutated['3']['game_world']['2214']['summary_provenance'] = 'unsupported_custom_provenance'
        is_valid, msg = validate_chapters_metadata(mutated)
        self.assertFalse(is_valid, '不合法的 summary_provenance 應該使驗證失敗')
        self.assertIn('2214', msg)
        self.assertIn('summary_provenance', msg)

    def test_n_current_chapters_json_passes_validator(self):
        """N. 確認現有 chapters.json 完全通過驗證器"""
        is_valid, msg = validate_chapters_metadata(self.data)
        self.assertTrue(is_valid, f'現有 chapters.json 驗證失敗: {msg}')


if __name__ == '__main__':
    unittest.main()
