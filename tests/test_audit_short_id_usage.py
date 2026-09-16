# -*- coding: utf-8 -*-
"""
tests/test_audit_short_id_usage.py — 6111 Usage Audit 分類邏輯最小 Hermetic 單元測試
"""

import unittest


def classify_short_id_row(current_uid, parsed_uid):
    """分類邏輯純函式"""
    if current_uid == 6111 and parsed_uid == 6111:
        return "VERIFIED_EXACT"
    if current_uid == 6111 and parsed_uid != 6111:
        return "COLLISION"
    if current_uid != 6111 and parsed_uid == 6111:
        return "MISSING_CANONICAL"
    return "IRRELEVANT"


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


if __name__ == "__main__":
    unittest.main()
