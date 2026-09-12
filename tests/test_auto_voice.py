# -*- coding: utf-8 -*-
"""
單元測試：Story Map AUTO 語音連播控制器 (AutoVoiceController)
驗證 AutoVoiceController 核心行為、狀態機與非同步 Token 防護，
並呼叫 Node.js 執行 test_auto_voice_controller.js。
"""

import unittest
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JS_TEST_PATH = PROJECT_ROOT / "tests" / "test_auto_voice_controller.js"
CONTROLLER_PATH = PROJECT_ROOT / "dashboard" / "auto-voice-controller.js"
MEDIA_SERVICE_PATH = PROJECT_ROOT / "dashboard" / "media-service.js"
DIALOGUE_VIEW_PATH = PROJECT_ROOT / "dashboard" / "dialogue-view.js"

class TestAutoVoiceController(unittest.TestCase):

    def test_controller_file_exists(self):
        """驗證 auto-voice-controller.js 實體檔案存在且具備核心方法"""
        self.assertTrue(CONTROLLER_PATH.exists(), "dashboard/auto-voice-controller.js 必須存在")
        content = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertIn("start(dialogueList", content)
        self.assertIn("pause()", content)
        self.assertIn("resume()", content)
        self.assertIn("stop()", content)
        self.assertIn("findNextVoicedIndex", content)
        self.assertIn("sessionToken", content)

    def test_media_service_lifecycle_apis(self):
        """驗證 media-service.js 擴充之生命週期 API 存在"""
        self.assertTrue(MEDIA_SERVICE_PATH.exists())
        content = MEDIA_SERVICE_PATH.read_text(encoding="utf-8")
        self.assertIn("playVoiceWithOptions", content)
        self.assertIn("pauseVoice", content)
        self.assertIn("resumeVoice", content)
        self.assertIn("stopVoice", content)

    def test_dialogue_view_index_mapping(self):
        """驗證 dialogue-view.js 生成包含 data-dialogue-index 屬性與高亮函式"""
        self.assertTrue(DIALOGUE_VIEW_PATH.exists())
        content = DIALOGUE_VIEW_PATH.read_text(encoding="utf-8")
        self.assertIn('data-dialogue-index="${index}"', content)
        self.assertIn("highlightDialogueLine", content)
        self.assertIn("clearDialogueHighlight", content)

    def test_node_runner_12_indicators(self):
        """透過 Node.js 執行 12 項行為測試"""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js 未安裝於目前環境，跳過 JS 執行測試")

        res = subprocess.run(
            [node_bin, str(JS_TEST_PATH)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(PROJECT_ROOT)
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Node.js 測試執行失敗:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
        self.assertIn("AutoVoiceController", res.stdout)
        self.assertIn("全部順利通過", res.stdout)

if __name__ == "__main__":
    unittest.main()
