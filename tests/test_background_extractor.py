#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit/Regression Test: Canonical Background Extraction
驗證 AssetBundle 中包含多個 Texture2D/Sprite (如粒子特效貼圖與正牌背景) 時，
能優先選取 exact name (bg_<bg_id>)，而不是按順序取第一個 Texture2D。
"""

import unittest
from unittest.mock import MagicMock
from PIL import Image

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.fetch import extract_canonical_background_image


class MockTexture2D:
    def __init__(self, name: str, size: tuple):
        self.m_Name = name
        self.name = name
        self.image = Image.new("RGBA", size, color=(0, 0, 0, 0))


class MockUnityObject:
    def __init__(self, type_name: str, texture: MockTexture2D):
        self.type = MagicMock()
        self.type.name = type_name
        self._texture = texture

    def read(self):
        return self._texture


class MockUnityEnv:
    def __init__(self, objects):
        self.objects = objects


class TestBackgroundExtractor(unittest.TestCase):
    def test_exact_name_preferred_over_first_effect_texture(self):
        """
        Regression Test (500140 案例)：
        AssetBundle 依序包含：
        1. bg_effect_500140_7 (128x128) - 粒子特效光斑貼圖
        2. bg_effect_500140_2 (128x128)
        3. bg_mask_500140 (256x256)
        4. bg_500140 (1024x1024) - 正牌主背景
        結果必須選取 bg_500140，而不是第一個 Texture2D。
        """
        tex_effect1 = MockTexture2D("bg_effect_500140_7", (128, 128))
        tex_effect2 = MockTexture2D("bg_effect_500140_2", (128, 128))
        tex_mask = MockTexture2D("bg_mask_500140", (256, 256))
        tex_bg = MockTexture2D("bg_500140", (1024, 1024))

        mock_env = MockUnityEnv([
            MockUnityObject("Texture2D", tex_effect1),
            MockUnityObject("Texture2D", tex_effect2),
            MockUnityObject("Texture2D", tex_mask),
            MockUnityObject("Texture2D", tex_bg),
        ])

        img, name = extract_canonical_background_image(mock_env, "500140")

        self.assertIsNotNone(img, "應成功提取背景圖像")
        self.assertEqual(name, "bg_500140", "必須精確選取 bg_500140，而非特效貼圖")
        self.assertEqual(img.size, (1024, 1024), "背景尺寸應為 1024x1024")

    def test_fallback_to_largest_area_when_no_exact_name(self):
        """
        Fallback 測試：
        若 bundle 內無 exact match 'bg_<bg_id>'，應回退選取面積最大的貼圖。
        """
        tex_small = MockTexture2D("unnamed_effect", (256, 256))
        tex_large = MockTexture2D("scenario_bg_custom", (1024, 1024))

        mock_env = MockUnityEnv([
            MockUnityObject("Texture2D", tex_small),
            MockUnityObject("Texture2D", tex_large),
        ])

        img, name = extract_canonical_background_image(mock_env, "999999")

        self.assertIsNotNone(img)
        self.assertEqual(name, "scenario_bg_custom", "無 exact match 時應 fallback 至最大面積貼圖")
        self.assertEqual(img.size, (1024, 1024))

    def test_empty_env(self):
        """
        空 Bundle 測試：無貼圖時應安全返回 None, None。
        """
        mock_env = MockUnityEnv([])
        img, name = extract_canonical_background_image(mock_env, "500140")
        self.assertIsNone(img)
        self.assertIsNone(name)


if __name__ == "__main__":
    unittest.main()
