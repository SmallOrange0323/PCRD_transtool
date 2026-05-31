# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - 主整合控制中心 (main.py)
整合 ui_manager、ocr_vision 與 translator_api，利用多執行緒雙重防凍架構提供玩家流暢的即時翻譯體驗。
"""

import os
import sys
import time
import logging
import asyncio
from PIL import Image
import numpy as np
import cv2

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QApplication
from PyQt6.QtGui import QImage

# 設定日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s - %(message)s')
logger = logging.getLogger("PCRD_Main")

# 確保可以正確導入同目錄下的模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from ui_manager import UIManager
from ocr_vision import PCRDVisionDetector
from translator_api import GeminiTranslator

class TranslationWorker(QThread):
    """
    後台影像監控與翻譯處理執行緒。
    在背景獨立執行 OpenCV 影像分析與 API 呼叫，確保 PyQt GUI 主執行緒絕對不卡頓、不卡死。
    """
    # 翻譯結果完成的 PyQt 信號：傳送 (說話者, 日文原文, 中文譯文) 給 UI 執行緒
    translation_ready = pyqtSignal(str, str, str)
    
    # 系統日誌與狀態通知信號
    status_msg_ready = pyqtSignal(str)

    def __init__(self, ui_manager: UIManager, detector: PCRDVisionDetector, translator: GeminiTranslator):
        super().__init__()
        self.ui = ui_manager
        self.detector = detector
        self.translator = translator
        self.running = True
        
        # 紀錄上一句成功翻譯的日文，防止邊緣條件重複觸發
        self.last_translated_text = ""

    def run(self):
        """
        後台執行緒主迴圈
        """
        logger.info("後台影像監控 Worker 執行緒已啟動。")
        self.status_msg_ready.emit("系統初始化完成，正在尋找 PCRD 遊戲視窗...")
        
        # 每次文字改變時的狀態計數
        text_changed_detected = False
        change_timestamp = 0.0
        
        # 獲取 config 配置
        capture_interval = getattr(config, 'CAPTURE_INTERVAL_MS', 250) / 1000.0
        
        while self.running:
            try:
                # 稍微歇息，避免佔用過多 CPU
                self.msleep(int(capture_interval * 1000))
                
                # 1. 檢查遊戲視窗是否被捕獲
                if not self.ui.game_hwnd or not self.ui.isVisible():
                    # 遊戲視窗未啟動或最小化，Worker 進入輕量待命
                    continue
                
                # 2. 擷取整個遊戲視窗畫面（MSS 高速擷圖）
                # 傳入 1:1 的全屏比例，先抓下整張客戶區影像
                full_frame = self.ui.capture_game_region({"left": 0, "top": 0, "width": 1.0, "height": 1.0})
                if full_frame is None:
                    continue
                
                # 3. 裁剪出對話框區域
                dialog_img = self.detector.crop_dialog_box(full_frame)
                if dialog_img is None:
                    continue
                
                # 4. 監測對話框文字是否發生改變
                if self.detector.has_text_changed(dialog_img):
                    # 偵測到文字改變，開啟「等待翻譯觸發狀態」
                    text_changed_detected = True
                    change_timestamp = time.time()
                    logger.info("偵測到新台詞開始顯示，啟動 ▼ 箭頭監控程序。")
                    self.status_msg_ready.emit("偵測到新台詞，等待播放完畢...")
                    continue
                
                # 5. 如果處於「等待翻譯觸發狀態」，進行觸發條件判定
                if text_changed_detected:
                    # 判定 A：是否偵測到右下角粉紅箭頭 ▼ (代表文字播放完畢)
                    arrow_detected = self.detector.detect_pink_arrow(dialog_img)
                    
                    # 判定 B：是否觸發了逾時安全網 (防範某些劇情畫面沒有 ▼ 箭頭，預設 2.2 秒自動翻譯)
                    elapsed_time = time.time() - change_timestamp
                    timeout_triggered = elapsed_time > 2.2
                    
                    if arrow_detected or timeout_triggered:
                        # 滿足翻譯觸發條件！立即執行擷圖與雙軌翻譯
                        trigger_reason = "▼ 箭頭已出現" if arrow_detected else f"已播放完畢 (逾時安全網 {elapsed_time:.1f} 秒觸發)"
                        logger.info(f"滿足翻譯觸發條件：{trigger_reason}。啟動翻譯流程...")
                        self.status_msg_ready.emit("對話播放完畢，正在進行 AI 翻譯...")
                        
                        # 重置觸發狀態
                        text_changed_detected = False
                        
                        # 執行核心翻譯流程
                        self.process_translation(full_frame, dialog_img)
                        
            except Exception as e:
                logger.error(f"後台影像監控 Worker 發生異常: {e}", exc_info=True)
                self.msleep(1000)

    def process_translation(self, full_frame: np.ndarray, dialog_img: np.ndarray):
        """
        核心雙軌翻譯調度流程
        """
        try:
            # 1. 嘗試使用本地 OCR
            recognized_text = ""
            confidence = 0.0
            recommend_vision = True
            
            if self.detector.ocr_engine is not None:
                recognized_text, confidence, recommend_vision = self.detector.local_ocr(dialog_img)
            
            # 清理辨識出的文字
            cleaned_text = recognized_text.replace("\n", "").replace(" ", "").strip()
            
            # 2. 決策翻譯路徑：本地 OCR + 文本 API 軌
            if not recommend_vision and cleaned_text:
                # 排除重複翻譯同一句話的邊緣情況
                if cleaned_text == self.last_translated_text:
                    logger.info("此句與上一句翻譯文字完全相同，忽略翻譯。")
                    self.status_msg_ready.emit("對話靜止，略過重複翻譯")
                    return
                
                # 裁剪說話者名字
                speaker_img = self.detector.crop_speaker(full_frame)
                speaker_name = ""
                # 如果說話者區域存在，利用本地 OCR 順便辨識名字
                if speaker_img is not None and self.detector.ocr_engine is not None:
                    sp_text, _, _ = self.detector.local_ocr(speaker_img)
                    speaker_name = sp_text.replace("\n", "").strip()
                
                logger.info(f"【決策路徑 A】本地 OCR 信心度足夠，調用純文本翻譯 API。")
                self.last_translated_text = cleaned_text
                
                # 執行 API 文本翻譯 (非同步在後台利用 asyncio 執行)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    chinese_translation = loop.run_until_complete(
                        self.translator.translate_text(recognized_text, speaker=speaker_name)
                    )
                    # 傳送回主 GUI 執行緒更新畫面
                    self.translation_ready.emit(speaker_name, recognized_text, chinese_translation)
                    self.status_msg_ready.emit("翻譯成功！")
                finally:
                    loop.close()
            
            # 3. 決策翻譯路徑：多模態 Vision 讀圖 API 軌
            else:
                logger.info(f"【決策路徑 B】本地 OCR 信心度過低或不可用，調用多模態 Vision 讀圖翻譯。")
                # 將 OpenCV 的對話框影像轉為 PIL Image
                # OpenCV 為 BGR，需轉成 RGB 供 PIL 使用
                rgb_dialog = cv2.cvtColor(dialog_img, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_dialog)
                
                # 執行多模態 Vision 翻譯
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        self.translator.translate_vision(pil_image)
                    )
                    
                    speaker = result.get("speaker", "").strip()
                    japanese = result.get("japanese", "").strip()
                    chinese = result.get("chinese", "").strip()
                    
                    # 傳送回主 GUI 執行緒更新畫面
                    self.translation_ready.emit(speaker, japanese, chinese)
                    self.status_msg_ready.emit("翻譯成功！(多模態 Vision)")
                finally:
                    loop.close()
                    
        except Exception as e:
            logger.error(f"執行雙軌翻譯處理時發生錯誤: {e}", exc_info=True)
            self.status_msg_ready.emit(f"翻譯 API 呼叫失敗: {e}")

    def stop(self):
        """
        停止執行緒
        """
        self.running = False
        self.wait()


class PCRDTranslatorApp:
    """
    PCRD 即時 AI 翻譯系統的最終整合主類別。
    協調主 GUI 與後台影像 Worker 的生命週期與數據傳遞。
    """
    def __init__(self):
        logger.info("=== 啟動 PCRD 即時 AI 翻譯系統整合程序 ===")
        
        # 1. 實例化各子模組 (核心設定已載入)
        self.ui = UIManager()
        self.detector = PCRDVisionDetector()
        self.translator = GeminiTranslator()
        
        # 2. 建立並啟動背景監控 Worker 執行緒
        self.worker = TranslationWorker(self.ui, self.detector, self.translator)
        
        # 3. 綁定 PyQt 信號與槽函數 (Signal & Slot)
        # 後台翻譯完成時，傳送給 UI 的 update_translation 方法更新畫面
        self.worker.translation_ready.connect(self.ui.update_translation)
        # 後台狀態改變時，更新 UI 面板提示文字
        self.worker.status_msg_ready.connect(self.handle_status_update)
        
        # 啟動背景工作執行緒
        self.worker.start()
        
    def handle_status_update(self, msg: str):
        """
        處理後台發送過來的狀態 log，如果是等待對話則動態印出提示，不影響玩家看翻譯
        """
        logger.debug(f"[Worker Status]: {msg}")
        # 如果當前沒有對話（預設文字），可以更新文字標籤提示進度
        if self.ui.text_label.text() in ["等待遊戲對話中...", "正在載入 AI 翻譯模組..."]:
            self.ui.text_label.setText(msg)

    def run(self):
        """
        使 UIManager 置頂並呈現
        """
        self.ui.show()
        # 置頂
        self.ui.raise_()
        
    def close(self):
        """
        關閉應用程式，釋放所有執行緒與資源
        """
        logger.info("正在釋放應用程式資源...")
        self.worker.stop()
        self.ui.close()
        logger.info("系統安全退出。")


# ==============================================================================
# 🚀 系統主程式入口
# ==============================================================================
def main():
    # 建立 PyQt6 QApplication 實例
    app = QApplication(sys.argv)
    
    # 建立整合 App 實例
    app_instance = PCRDTranslatorApp()
    app_instance.run()
    
    # 註冊退出釋放事件
    app.aboutToQuit.connect(app_instance.close)
    
    # 啟動 GUI 主事件迴圈
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
