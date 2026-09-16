# -*- coding: utf-8 -*-
"""
tests/test_audit_short_id_usage.py — 6111 Usage Audit 分類與語意對齊 Hermetic 單元測試
"""

import unittest
from tools.diagnostics.audit_short_id_usage import (
    classify_short_id_row,
    story_rows_semantically_align,
    normalize_text
)


class TestAuditClassification(unittest.TestCase):
    def test_verified_exact(self):
        self.assertEqual(classify_short_id_row(6111, 6111), "VERIFIED_EXACT")

    def test_collision(self):
        self.assertEqual(classify_short_id_row(6111, None), "COLLISION")
        self.assertEqual(classify_short_id_row(6111, 6112), "COLLISION")

    def test_missing_canonical(self):
        self.assertEqual(classify_short_id_row(None, 6111), "MISSING_CANONICAL")
        self.assertEqual(classify_short_id_row(100011, 6111), "MISSING_CANONICAL")

    def test_irrelevant(self):
        self.assertEqual(classify_short_id_row(100011, 100011), "IRRELEVANT")
        self.assertEqual(classify_short_id_row(None, None), "IRRELEVANT")


class TestSemanticAlignment(unittest.TestCase):
    def setUp(self):
        self.base_current = [
            {
                "type": "dialogue",
                "name": "秘書",
                "words": "您好，{player}大人！\\n今天也有很多工作呢。",
                "voice": "vo_1180002_001",
                "bg_id": 500010,
                "still": None,
                "still_id": None,
                "movie_id": None,
                "unit_id": 6111
            }
        ]
        self.base_parsed = [
            {
                "type": "dialogue",
                "name": "秘書",
                "words": "您好，{0}大人！\n今天也有很多工作呢。",
                "voice": "vo_1180002_001",
                "bg_id": 500010,
                "still": None,
                "still_id": None,
                "movie_id": None,
                "unit_id": None  # 忽略 unit_id
            }
        ]

    def test_aligned_with_text_normalization_and_different_unit_id(self):
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, self.base_parsed)
        self.assertTrue(is_aligned)
        self.assertEqual(reason, "ALIGNED")
        self.assertEqual(idx, -1)

    def test_drift_length(self):
        parsed = self.base_parsed + [{"type": "dialogue", "name": "秘書", "words": "追加"}]
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, parsed)
        self.assertFalse(is_aligned)
        self.assertEqual(reason, "UNVERIFIABLE_STORY_DRIFT_LENGTH")
        self.assertEqual(idx, -1)

    def test_drift_content_speaker(self):
        parsed = [dict(self.base_parsed[0], name="其他人")]
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, parsed)
        self.assertFalse(is_aligned)
        self.assertTrue("speaker name mismatch" in reason)
        self.assertEqual(idx, 0)

    def test_drift_content_words(self):
        parsed = [dict(self.base_parsed[0], words="完全不同的台詞")]
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, parsed)
        self.assertFalse(is_aligned)
        self.assertTrue("words mismatch" in reason)
        self.assertEqual(idx, 0)

    def test_drift_content_voice(self):
        parsed = [dict(self.base_parsed[0], voice="vo_diff")]
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, parsed)
        self.assertFalse(is_aligned)
        self.assertTrue("voice mismatch" in reason)
        self.assertEqual(idx, 0)

    def test_drift_content_type(self):
        parsed = [dict(self.base_parsed[0], type="narration")]
        is_aligned, reason, idx = story_rows_semantically_align(self.base_current, parsed)
        self.assertFalse(is_aligned)
        self.assertTrue("type mismatch" in reason)
        self.assertEqual(idx, 0)


if __name__ == "__main__":
    unittest.main()

