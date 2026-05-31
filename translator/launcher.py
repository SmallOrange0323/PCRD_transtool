# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - 啟動控制台 (launcher.py)
提供玩家極具美感 (櫻花粉與星空暗藍漸變)、開箱即用的圖形化 Launcher 面板。
支援 API Key 本地儲存、翻譯模型挑選、Wiki 字典手動更新、以及一鍵啟動/停止翻譯系統。
"""

import os
import sys
import json
import logging
import asyncio
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton, 
                              QVBoxLayout, QHBoxLayout, QComboBox, QFrame, QMessageBox,
                              QSystemTrayIcon, QMenu)
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QMovie

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("PCRD_Launcher")

# 確保可以導入同目錄下的 config 與 main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from main import PCRDTranslatorApp
from wiki_scraper import load_or_create_glossary

class ScrapeWorker(QThread):
    """
    非同步爬取 Wiki 字典的背景執行緒，避免阻塞 Launcher UI。
    """
    finished_signal = pyqtSignal(int) # 傳回更新後的名詞筆數
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            logger.info("背景爬蟲執行緒啟動，正在更新名詞對照表...")
            # 強制執行 Wiki 爬蟲，重新合併寫入 glossary.json
            glossary = load_or_create_glossary(force_update=True)
            self.finished_signal.emit(len(glossary))
        except Exception as e:
            logger.error(f"背景更新字典失敗: {e}")
            self.error_signal.emit(str(e))

class LauncherWindow(QWidget):
    """
    PCRD AI 翻譯器精美啟動器介面
    """
    def __init__(self):
        super().__init__()
        logger.info("正在初始化 Launcher 控制台...")
        
        # 翻譯 App 的執行個體
        self.translator_app = None
        self.api_key_visible = False
        
        # 1. 初始化視窗美感設定
        self.init_window_settings()
        
        # 2. 建立 Launcher UI
        self.setup_ui()
        
        # 3. 載入本地儲存的設定（如 API Key）
        self.load_saved_settings()
        
        # 4. 初始化系統托盤 (System Tray)
        self.setup_system_tray()
        
        logger.info("Launcher 控制台初始化完成！")

    def init_window_settings(self):
        """
        設定 Launcher 的視窗樣式
        """
        self.setFixedSize(450, 520)
        self.setWindowTitle("✨ PCRD AI 翻譯器控制台 v1.0")
        
        # 設定暗色 Premium 摩登藍黑背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #121218;
                color: #FFFFFF;
                font-family: 'Noto Sans TC', sans-serif;
            }
            QLabel {
                background: transparent;
            }
        """)

    def setup_ui(self):
        """
        建構控制台的視覺元件與漸層版面
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(18)
        
        # ==============================================================================
        # 1. 頂部標題區域 (Title)
        # ==============================================================================
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        
        self.title_label = QLabel("✨ PCRD AI 翻譯器", self)
        self.title_label.setStyleSheet("""
            color: #FFB6C1;
            font-size: 24px;
            font-weight: bold;
            font-family: 'Outfit', 'Noto Sans TC';
        """)
        
        sub_title = QLabel("Princess Connect Re:Dive Real-time Translator", self)
        sub_title.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-family: 'Outfit';")
        
        title_box.addWidget(self.title_label)
        title_box.addWidget(sub_title)
        main_layout.addLayout(title_box)
        
        # 裝飾分割線
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        main_layout.addWidget(line)

        # ==============================================================================
        # 2. API 配置卡片 (API Configuration Card)
        # ==============================================================================
        api_card = QFrame(self)
        api_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
            }
        """)
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(15, 15, 15, 15)
        api_layout.setSpacing(10)
        
        api_title = QLabel("🔑 Gemini API 金鑰配置", api_card)
        api_title.setStyleSheet("color: #FFD700; font-size: 13px; font-weight: bold;")
        api_layout.addWidget(api_title)
        
        # 輸入框與雙按鈕佈局
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)
        
        self.api_input = QLineEdit(api_card)
        self.api_input.setPlaceholderText("請在此輸入您的 Gemini API 金鑰...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password) # 預設隱藏
        self.api_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 6px 10px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #FFB6C1;
            }
        """)
        
        # 眼睛顯示/隱藏按鈕 (👁️)
        self.btn_eye = QPushButton("👁️", api_card)
        self.btn_eye.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_eye.setFixedSize(32, 30)
        self.btn_eye.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        self.btn_eye.clicked.connect(self.toggle_api_visibility)
        
        input_layout.addWidget(self.api_input)
        input_layout.addWidget(self.btn_eye)
        api_layout.addLayout(input_layout)
        
        # 儲存金鑰按鈕
        self.btn_save_api = QPushButton("💾 儲存金鑰", api_card)
        self.btn_save_api.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_api.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 182, 193, 0.1);
                color: #FFB6C1;
                border: 1px solid rgba(255, 182, 193, 0.25);
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 182, 193, 0.2);
                border: 1px solid #FFB6C1;
            }
        """)
        self.btn_save_api.clicked.connect(self.save_api_key)
        api_layout.addWidget(self.btn_save_api)
        
        main_layout.addWidget(api_card)

        # ==============================================================================
        # 3. 系統偏好設定卡片 (Settings Card)
        # ==============================================================================
        settings_card = QFrame(self)
        settings_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
            }
        """)
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(12)
        
        settings_title = QLabel("⚙️ 翻譯偏好設定", settings_card)
        settings_title.setStyleSheet("color: #87CEFA; font-size: 13px; font-weight: bold;")
        settings_layout.addWidget(settings_title)
        
        # 模型挑選佈局
        model_layout = QHBoxLayout()
        model_label = QLabel("🤖 翻譯模型：", settings_card)
        model_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        
        self.model_combo = QComboBox(settings_card)
        self.model_combo.addItems(["gemini-2.5-flash (推薦，速度極快)", "gemini-2.5-pro (精準，延遲略高)"])
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }
        """)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        settings_layout.addLayout(model_layout)
        
        # 模式挑選佈局
        mode_layout = QHBoxLayout()
        mode_label = QLabel("🚀 翻譯模式：", settings_card)
        mode_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        
        self.mode_combo = QComboBox(settings_card)
        self.mode_combo.addItems(["自適應雙軌模式 (本地 OCR + Vision 讀圖)", "高精度多模態模式 (強制 Vision 讀圖)"])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }
        """)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        settings_layout.addLayout(mode_layout)
        
        main_layout.addWidget(settings_card)

        # ==============================================================================
        # 4. 一鍵更新 Wiki 字典卡片
        # ==============================================================================
        self.btn_update_wiki = QPushButton("🕷️ 一鍵強制更新角色 Wiki 字典", self)
        self.btn_update_wiki.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_wiki.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #E6E6FA;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        self.btn_update_wiki.clicked.connect(self.trigger_wiki_update)
        main_layout.addWidget(self.btn_update_wiki)

        # ==============================================================================
        # 5. 核心啟動大按鈕 (Start/Stop Action)
        # ==============================================================================
        self.btn_action = QPushButton("🚀 啟動即時翻譯監控", self)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFixedHeight(48)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: #FFB6C1;
                color: #121218;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #FFC0CB;
            }
            QPushButton:pressed {
                background-color: #FFA07A;
            }
        """)
        self.btn_action.clicked.connect(self.handle_action_click)
        main_layout.addWidget(self.btn_action)

        # ==============================================================================
        # 6. 底部狀態列 (Status Bar)
        # ==============================================================================
        status_layout = QHBoxLayout()
        
        # 狀態小燈
        self.status_light = QFrame(self)
        self.status_light.setFixedSize(10, 10)
        self.status_light.setStyleSheet("background-color: #808080; border-radius: 5px;")
        
        # 狀態文字
        self.status_text = QLabel("系統狀態：控制面板待命", self)
        self.status_text.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        
        status_layout.addWidget(self.status_light)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        
        version_label = QLabel("v1.0 (Premium)", self)
        version_label.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 10px;")
        status_layout.addWidget(version_label)
        
        main_layout.addLayout(status_layout)

    # ==============================================================================
    # 核心邏輯功能
    # ==============================================================================
    def toggle_api_visibility(self):
        """
        切換 API Key 的明文/密文顯示
        """
        if self.api_key_visible:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_eye.setText("👁️")
            self.api_key_visible = False
        else:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_eye.setText("🔒")
            self.api_key_visible = True

    def save_api_key(self):
        """
        將 API Key 儲存至本地 config.py 中，並寫入快取檔案，方便玩家下次直接讀取。
        """
        api_key = self.api_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "請輸入有效的 API 金鑰後再儲存。")
            return
            
        try:
            # 1. 寫入本地 config 快取檔案
            cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"GEMINI_API_KEY": api_key}, f)
            
            # 2. 動態覆蓋 config 中的配置，以便運行時生效
            config.GEMINI_API_KEY = api_key
            
            # 3. 嘗試直接改寫 config.py 檔案，以實現永久實體儲存
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 正則替換 GEMINI_API_KEY = "..." 的內容
                pattern = r'GEMINI_API_KEY\s*=\s*os\.getenv\("GEMINI_API_KEY",\s*"[^"]*"\)'
                new_line = f'GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "{api_key}")'
                
                # 如果沒有匹配到 os.getenv 的寫法，就替換一般的 GEMINI_API_KEY = "..."
                if not re.search(pattern, content):
                    content = re.sub(r'GEMINI_API_KEY\s*=\s*"[^"]*"', f'GEMINI_API_KEY = "{api_key}"', content)
                else:
                    content = re.sub(pattern, new_line, content)
                    
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(content)
            
            QMessageBox.information(self, "成功", "Gemini API 金鑰已成功安全儲存，下次啟動將自動載入！")
            logger.info("API Key 已儲存至本地設定中。")
            
        except Exception as e:
            logger.error(f"儲存 API Key 失敗: {e}")
            QMessageBox.critical(self, "錯誤", f"儲存金鑰失敗: {e}")

    def load_saved_settings(self):
        """
        載入已儲存的金鑰與偏好
        """
        # 1. 優先從環境變數讀取
        env_key = os.getenv("GEMINI_API_KEY", "")
        if env_key:
            self.api_input.setText(env_key)
            config.GEMINI_API_KEY = env_key
            logger.info("已從系統環境變數自動載入 API 金鑰。")
            return
            
        # 2. 次要從本地快取 json 讀取
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saved_key = data.get("GEMINI_API_KEY", "")
                    if saved_key:
                        self.api_input.setText(saved_key)
                        config.GEMINI_API_KEY = saved_key
                        logger.info("已從本地快取自動載入 API 金鑰。")
                        return
            except Exception as e:
                logger.warning(f"讀取 api_cache.json 失敗: {e}")
                
        # 3. 再者嘗試直接讀取 config.py 原生變數
        if config.GEMINI_API_KEY:
            self.api_input.setText(config.GEMINI_API_KEY)
            logger.info("已從 config.py 自動載入 API 金鑰。")

    # ==============================================================================
    # 字典更新非同步處理
    # ==============================================================================
    def trigger_wiki_update(self):
        """
        點擊一鍵更新字典，啟動背景執行緒更新 Wiki
        """
        self.btn_update_wiki.setEnabled(False)
        self.btn_update_wiki.setText("🕷️ 正在爬取 Wiki 更新中...")
        self.status_text.setText("系統狀態：正在連線維基百科更新名詞對照表...")
        
        self.worker = ScrapeWorker()
        self.worker.finished_signal.connect(self.handle_wiki_success)
        self.worker.error_signal.connect(self.handle_wiki_error)
        self.worker.start()

    def handle_wiki_success(self, count: int):
        self.btn_update_wiki.setEnabled(True)
        self.btn_update_wiki.setText("🕷️ 一鍵強制更新角色 Wiki 字典")
        self.status_text.setText(f"系統狀態：Wiki 字典更新成功！共 {count} 筆")
        QMessageBox.information(self, "更新成功", f"Wiki 角色譯名對照表更新成功！\n目前字典總計共有 {count} 筆資料。")
        
        # 如果翻譯器實例存在，動態重新載入字典
        if self.translator_app and self.translator_app.translator:
            self.translator_app.translator.glossary = load_or_create_glossary()

    def handle_wiki_error(self, err_msg: str):
        self.btn_update_wiki.setEnabled(True)
        self.btn_update_wiki.setText("🕷️ 一鍵強制更新角色 Wiki 字典")
        self.status_text.setText("系統狀態：Wiki 更新失敗，已自動啟用本地核心字典")
        QMessageBox.warning(self, "更新失敗", f"無法從網頁爬取 Wiki 譯名 ({err_msg})。\n系統已自動啟動內建核心對照字典，可正常運作！")

    # ==============================================================================
    # 啟動 / 停止 翻譯器生命週期管理
    # ==============================================================================
    def handle_action_click(self):
        """
        處理大按鈕的點擊事件（啟動/停止切換）
        """
        if self.translator_app is None:
            # --- 啟動翻譯監控 ---
            api_key = self.api_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "設定錯誤", "請先輸入您的 Gemini API 金鑰後，再啟動翻譯監控。")
                return
                
            config.GEMINI_API_KEY = api_key
            
            # 設定使用者挑選的模型
            selected_model = "gemini-2.5-flash"
            if "pro" in self.model_combo.currentText():
                selected_model = "gemini-2.5-pro"
            config.GEMINI_TEXT_MODEL = selected_model
            config.GEMINI_VISION_MODEL = selected_model
            
            # 設定翻譯模式（是否強制多模態）
            if "強制" in self.mode_combo.currentText():
                # 可以直接在 config 加上自訂開關
                config.FORCE_VISION_MODE = True
                logger.info("已設定翻譯模式：強制 Vision 讀圖模式。")
            else:
                config.FORCE_VISION_MODE = False
                logger.info("已設定翻譯模式：自適應雙軌模式 (OCR + Vision)。")
            
            # 覆蓋 main.py 中 OCR 模組對該開關的對接
            if hasattr(config, "FORCE_VISION_MODE") and config.FORCE_VISION_MODE:
                # 若強制 Vision 模式，我們可以在 Worker 中跳過本地 OCR，直接走 Vision
                pass
                
            try:
                self.status_text.setText("系統狀態：正在啟動翻譯系統...")
                self.status_light.setStyleSheet("background-color: #FFA500; border-radius: 5px;") # 亮橘燈
                
                # 實例化 main.py 中的主程式，開啟置頂懸浮窗並啟動後台監控執行緒
                self.translator_app = PCRDTranslatorApp()
                
                # 如果使用者勾選了強制多模態，對 Worker 進行直接屬性修正
                if getattr(config, "FORCE_VISION_MODE", False):
                    # 透過讓本地 ocr 引擎設定為 None，Worker 就會自動直接走 Vision 路線！
                    self.translator_app.detector.ocr_engine = None
                
                # 啟動懸浮窗
                self.translator_app.run()
                
                # 成功啟動，切換按鈕狀態
                self.btn_action.setText("🛑 停止即時翻譯監控")
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #FF6B6B;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 10px;
                        font-size: 16px;
                        font-weight: bold;
                        letter-spacing: 1px;
                    }
                    QPushButton:hover {
                        background-color: #FF8787;
                    }
                """)
                
                self.status_text.setText("系統狀態：即時翻譯監控運行中")
                self.status_light.setStyleSheet("background-color: #00FF00; border-radius: 5px;") # 亮綠燈
                
                # 智慧功能：啟動後自動最小化 Launcher 視窗，保持桌面清爽
                QTimer.singleShot(800, self.minimize_to_tray_prompt)
                
            except Exception as e:
                logger.error(f"啟動翻譯系統失敗: {e}", exc_info=True)
                QMessageBox.critical(self, "啟動失敗", f"無法啟動翻譯系統: {e}")
                self.status_text.setText("系統狀態：啟動失敗")
                self.status_light.setStyleSheet("background-color: #FF0000; border-radius: 5px;") # 紅燈
                self.translator_app = None
                
        else:
            # --- 停止翻譯監控 ---
            self.stop_translation_system()

    def stop_translation_system(self):
        """
        停止翻譯監控系統，回收所有視窗與背景執行緒
        """
        if self.translator_app:
            try:
                logger.info("正在停止即時翻譯系統...")
                self.status_text.setText("系統狀態：正在停止監控...")
                
                # 釋放 main.py 的 Worker 執行緒與 UIManager 視窗
                self.translator_app.close()
                self.translator_app = None
                
                # 恢復按鈕狀態
                self.btn_action.setText("🚀 啟動即時翻譯監控")
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #FFB6C1;
                        color: #121218;
                        border: none;
                        border-radius: 10px;
                        font-size: 16px;
                        font-weight: bold;
                        letter-spacing: 1px;
                    }
                    QPushButton:hover {
                        background-color: #FFC0CB;
                    }
                """)
                
                self.status_text.setText("系統狀態：控制面板待命")
                self.status_light.setStyleSheet("background-color: #808080; border-radius: 5px;") # 灰燈
                logger.info("即時翻譯系統已安全停止。")
                
            except Exception as e:
                logger.error(f"停止翻譯系統時發生錯誤: {e}")

    # ==============================================================================
    # 智慧系統托盤 (System Tray)
    # ==============================================================================
    def setup_system_tray(self):
        """
        建立系統右下角托盤圖示與右鍵選單
        """
        self.tray_icon = QSystemTrayIcon(self)
        
        # 由於打包 EXE 時可能沒有圖示檔案，我們使用 PyQt 內建的圖示作為 Tray Icon
        self.tray_icon.setIcon(self.style().standardIcon(QApplication.StyleStandardIcon.SP_ComputerIcon))
        
        # 建立托盤選單
        tray_menu = QMenu()
        
        show_action = QAction("💻 顯示控制台", self)
        show_action.triggered.connect(self.show_normal)
        
        stop_action = QAction("🛑 停止翻譯", self)
        stop_action.triggered.connect(self.stop_translation_system)
        
        quit_action = QAction("🚪 完全退出", self)
        quit_action.triggered.connect(self.complete_exit)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(stop_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def minimize_to_tray_prompt(self):
        """
        提示並最小化至系統托盤
        """
        self.hide() # 直接隱藏至系統托盤
        self.tray_icon.showMessage(
            "PCRD 即時 AI 翻譯器",
            "翻譯系統已在後台運行！控制面板已縮小至右下角系統托盤，雙擊托盤圖示可重新展開控制台。",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

    def show_normal(self):
        """
        重新顯示控制台主視窗
        """
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_icon_activated(self, reason):
        """
        點擊或雙擊托盤圖示
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def complete_exit(self):
        """
        完全退出整個軟體
        """
        self.stop_translation_system()
        QApplication.quit()

    def closeEvent(self, event):
        """
        點擊關閉 X 按鈕時，不退出軟體，而是隱藏至系統托盤。
        """
        if self.translator_app is not None:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "PCRD 即時 AI 翻譯器",
                "控制面板已隱藏至右下角系統托盤，軟體仍持續在背景運行監控中！",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self.complete_exit()


import re
# ==============================================================================
# Launcher 啟動入口
# ==============================================================================
def main():
    app = QApplication(sys.argv)
    
    # 載入好看的 App 圖示（若無，使用 PyQt 內建圖示）
    app.setWindowIcon(app.style().standardIcon(QApplication.StyleStandardIcon.SP_ComputerIcon))
    
    launcher = LauncherWindow()
    launcher.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
