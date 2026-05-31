# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - UI 管理與擷圖模組
實作一個無邊框、置頂、半透明背景的懸浮視窗，具備 Windows 鼠標穿透、視窗精準跟隨與歷史日誌抽屜功能。
同時整合 mss 庫提供高速擷圖服務。
"""

import os
import sys
import time
import logging
import numpy as np
import cv2
import mss
import win32gui
import win32con
import win32process

from PyQt6.QtCore import QTimer, Qt, QRect, QPropertyAnimation, QEasingCurve, pyqtSignal, QPoint
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtGui import QFont, QColor, QCursor, QPainter, QLinearGradient

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("PCRD_UIManager")

# 匯入共享設定檔
try:
    import config
except ImportError:
    # 確保同目錄下的 config 可以被匯入
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config

class HistoryItemWidget(QFrame):
    """
    歷史劇情日誌中的單個對話條目 Widget
    """
    def __init__(self, japanese: str, chinese: str, parent=None):
        super().__init__(parent)
        self.setObjectName("HistoryItem")
        self.setStyleSheet("""
            QFrame#HistoryItem {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                padding: 10px;
                margin-bottom: 8px;
            }
            QFrame#HistoryItem:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 240, 245, 0.15);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        # 日文原文
        self.jp_label = QLabel(japanese, self)
        self.jp_label.setWordWrap(True)
        self.jp_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; font-family: 'Noto Sans TC';")
        
        # 中文翻譯
        self.zh_label = QLabel(chinese, self)
        self.zh_label.setWordWrap(True)
        self.zh_label.setStyleSheet(f"color: {config.UI_TEXT_COLOR}; font-size: 14px; font-weight: bold; font-family: 'Noto Sans TC';")
        
        layout.addWidget(self.jp_label)
        layout.addWidget(self.zh_label)


class UIManager(QWidget):
    """
    PCRD 即時 AI 翻譯系統的主 UI 控制中心
    """
    # 當翻譯文字更新時發送的信號 (日文, 中文)
    translation_updated = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        logger.info("正在初始化 UIManager...")
        
        # 遊戲視窗 HWND
        self.game_hwnd = None
        # 當前滑鼠穿透狀態
        self.is_transparent = False
        
        # 儲存歷史對話清單
        self.history_records = []
        
        # 1. 初始化無邊框、置頂、半透明屬性
        self.init_window_attributes()
        
        # 2. 建立 UI 畫面佈局與組件
        self.setup_ui()
        
        # 3. 建立計時器：同步遊戲視窗位置 (100ms) 與動態滑鼠穿透檢測 (50ms)
        self.init_timers()
        
        # 4. 初始化 mss 高速擷圖實例
        self.sct = mss.mss()
        
        logger.info("UIManager 初始化成功！")
        
    def init_window_attributes(self):
        """
        初始化懸浮視窗的特殊視窗屬性與樣式
        """
        # 置頂 (WindowStaysOnTopHint)、無邊框 (FramelessWindowHint) 且不在工作列顯示圖示 (Tool)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool
        )
        # 背景完全透明，依賴子 Widget 的半透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        # 啟用滑鼠追蹤
        self.setMouseTracking(True)
        
        # 設定預設視窗大小與位置 (稍後會由遊戲視窗定位覆蓋)
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("PCRD Real-time AI Translator Overlay")
        
    def setup_ui(self):
        """
        建構 Premium 質感的懸浮窗與抽屜佈局
        """
        # 整個主視窗的佈局 (透明)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # ==============================================================================
        # A. 翻譯主面板區域 (Translation Panel)
        # ==============================================================================
        self.translation_container = QWidget(self)
        self.translation_container.setStyleSheet("background: transparent;")
        # 由於要精準定位，我們在 container 內使用手動定位 (Manual Geometry) 
        # 這樣才能在同步視窗大小時，精確按照 DIALOG_BOX_RATIO 來放置翻譯面板
        
        # 實際顯示翻譯的半透明圓角面板
        self.translation_panel = QFrame(self.translation_container)
        self.translation_panel.setObjectName("TranslationPanel")
        self.translation_panel.setStyleSheet(f"""
            QFrame#TranslationPanel {{
                background-color: {config.UI_BACKGROUND_COLOR};
                border-radius: 14px;
                border: 1.5px solid rgba(255, 255, 255, 0.12);
            }}
        """)
        
        # 翻譯面板內部佈局
        panel_layout = QVBoxLayout(self.translation_panel)
        panel_layout.setContentsMargins(20, 15, 20, 15)
        panel_layout.setSpacing(8)
        
        # 說話者名字標籤
        self.speaker_label = QLabel("角色名字", self.translation_panel)
        self.speaker_label.setStyleSheet(f"""
            color: #FFB6C1;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Outfit', 'Noto Sans TC';
        """)
        
        # 翻譯文本標籤
        self.text_label = QLabel("等待遊戲對話中...", self.translation_panel)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(f"""
            color: {config.UI_TEXT_COLOR};
            font-size: 17px;
            line-height: 1.5;
            font-family: 'Noto Sans TC';
        """)
        
        panel_layout.addWidget(self.speaker_label)
        panel_layout.addWidget(self.text_label)
        
        # ==============================================================================
        # B. 歷史劇情日誌抽屜區域 (History Log Drawer)
        # ==============================================================================
        # 抽屜面板本體
        self.drawer_panel = QFrame(self)
        self.drawer_panel.setObjectName("DrawerPanel")
        self.drawer_panel.setStyleSheet(f"""
            QFrame#DrawerPanel {{
                background-color: {config.UI_DRAWER_COLOR};
                border-left: 2px solid rgba(255, 255, 255, 0.08);
            }}
        """)
        
        # 抽屜寬度設定
        self.drawer_width = 350
        self.drawer_expanded = False
        self.drawer_panel.setGeometry(self.width(), 0, 0, self.height()) # 初始收起
        
        # 抽屜內部佈局
        drawer_layout = QVBoxLayout(self.drawer_panel)
        drawer_layout.setContentsMargins(15, 20, 15, 20)
        drawer_layout.setSpacing(15)
        
        # 抽屜頂部控制欄
        top_bar = QHBoxLayout()
        drawer_title = QLabel("📜 歷史劇情日誌", self.drawer_panel)
        drawer_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; font-family: 'Noto Sans TC';")
        
        # 清除歷史按鈕 (🗑️)
        self.btn_clear = QPushButton("🗑️ 清除", self.drawer_panel)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 75, 75, 0.15);
                color: #FF6B6B;
                border: 1px solid rgba(255, 75, 75, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-family: 'Noto Sans TC';
            }
            QPushButton:hover {
                background-color: rgba(255, 75, 75, 0.25);
                border: 1px solid rgba(255, 75, 75, 0.5);
            }
        """)
        self.btn_clear.clicked.connect(self.clear_history)
        
        # 收合抽屜按鈕 (▶)
        self.btn_close_drawer = QPushButton("▶", self.drawer_panel)
        self.btn_close_drawer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_drawer.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        self.btn_close_drawer.clicked.connect(self.toggle_drawer)
        
        top_bar.addWidget(drawer_title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_clear)
        top_bar.addWidget(self.btn_close_drawer)
        drawer_layout.addLayout(top_bar)
        
        # 歷史記錄滾動區域
        self.scroll_area = QScrollArea(self.drawer_panel)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.4);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # 滾動區域內部的 Widget 與垂直佈局
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 4, 0)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()  # 從底部向上排版
        
        self.scroll_area.setWidget(self.scroll_content)
        drawer_layout.addWidget(self.scroll_area)
        
        # ==============================================================================
        # C. 抽屜控制微按鈕 (Drawer Toggle Button)
        # ==============================================================================
        # 此按鈕放置在螢幕最右側邊緣，點擊可滑出抽屜
        self.btn_toggle = QPushButton("◀\n歷\n史", self)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: rgba(18, 18, 24, 220);
                color: #FFB6C1;
                border-left: 2px solid rgba(255, 182, 193, 0.5);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                padding: 10px 4px;
                font-size: 11px;
                font-weight: bold;
                font-family: 'Noto Sans TC';
                line-height: 1.3;
            }
            QPushButton:hover {
                background-color: rgba(28, 28, 36, 240);
                color: #FFFFFF;
                border-left: 2.5px solid #FFB6C1;
            }
        """)
        self.btn_toggle.clicked.connect(self.toggle_drawer)
        
        # 設置按鈕初始位置 (靠右置中，寬 32，高 80)
        self.btn_toggle_width = 30
        self.btn_toggle_height = 80
        self.btn_toggle.setGeometry(self.width() - self.btn_toggle_width, 
                                     (self.height() - self.btn_toggle_height) // 2, 
                                     self.btn_toggle_width, 
                                     self.btn_toggle_height)
        
        # 3. 組合主佈局
        self.main_layout.addWidget(self.translation_container)
        
    def init_timers(self):
        """
        初始化定時器：同步遊戲座標、滑鼠穿透狀態
        """
        # A. 遊戲視窗座標與大小追蹤計時器 (100ms)
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.sync_with_game_window)
        self.track_timer.start(100)
        
        # B. 滑鼠穿透檢測計時器 (50ms)
        # 用於判斷滑鼠是否在互動區域（按鈕/展開的抽屜）上，動態切換穿透狀態
        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self.check_mouse_position)
        self.mouse_timer.start(50)
        
    # ==============================================================================
    # 核心功能 1：同步遊戲視窗位置與大小
    # ==============================================================================
    def sync_with_game_window(self):
        """
        尋找遊戲視窗，並精準覆蓋其客戶區 (Client Area)
        """
        # 取得遊戲 HWND，若無效則重新搜尋
        if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd):
            self.game_hwnd = win32gui.FindWindow(None, config.GAME_WINDOW_NAME)
            if not self.game_hwnd:
                if self.isVisible():
                    logger.info(f"找不到遊戲視窗 [{config.GAME_WINDOW_NAME}]，隱藏懸浮窗...")
                    self.hide()
                return

        # 檢查視窗是否最小化或不可見
        if not self.is_window_active(self.game_hwnd):
            if self.isVisible():
                logger.debug("遊戲視窗最小化或隱藏，隱藏懸浮窗...")
                self.hide()
            return
            
        # 獲取遊戲視窗客戶區的螢幕絕對座標與大小
        try:
            client_rect = win32gui.GetClientRect(self.game_hwnd)
            client_w = client_rect[2] - client_rect[0]
            client_h = client_rect[3] - client_rect[1]
            
            # 將客戶區左上角 (0, 0) 轉換為螢幕絕對座標
            client_x, client_y = win32gui.ClientToScreen(self.game_hwnd, (0, 0))
            
            # 驗證座標有效性
            if client_w <= 0 or client_h <= 0:
                return
                
            # 若位置或大小有變動，進行更新
            current_geom = self.geometry()
            if (current_geom.x() != client_x or current_geom.y() != client_y or 
                current_geom.width() != client_w or current_geom.height() != client_h):
                
                logger.debug(f"同步遊戲視窗幾何：x={client_x}, y={client_y}, w={client_w}, h={client_h}")
                # 重新設定懸浮主視窗大小，使其 1:1 貼合遊戲畫面
                self.setGeometry(client_x, client_y, client_w, client_h)
                
                # 同步更新子組件佈局位置
                self.layout_components(client_w, client_h)
                
            if not self.isVisible():
                logger.info("遊戲視窗處於活動狀態，顯示懸浮窗...")
                self.show()
                # 顯示時將懸浮窗置頂
                self.raise_()
                
        except Exception as e:
            logger.error(f"同步遊戲視窗位置時發生錯誤: {e}")
            
    def is_window_active(self, hwnd) -> bool:
        """
        判斷視窗是否可見且未最小化
        """
        if not win32gui.IsWindow(hwnd):
            return False
        if not win32gui.IsWindowVisible(hwnd):
            return False
        placement = win32gui.GetWindowPlacement(hwnd)
        # placement[1] 表示視窗狀態，2 為最小化 (SW_SHOWMINIMIZED)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            return False
        return True
        
    def layout_components(self, w: int, h: int):
        """
        當主視窗縮放時，重新計算各子組件的精準幾何位置
        """
        # A. 翻譯面板：根據 config.DIALOG_BOX_RATIO 計算
        ratio = config.DIALOG_BOX_RATIO
        panel_x = int(w * ratio["left"])
        panel_y = int(h * ratio["top"])
        panel_w = int(w * ratio["width"])
        panel_h = int(h * ratio["height"])
        
        self.translation_panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
        
        # B. 歷史日誌抽屜面板
        # 根據抽屜是否展開，決定其寬度與 x 座標
        if self.drawer_expanded:
            self.drawer_panel.setGeometry(w - self.drawer_width, 0, self.drawer_width, h)
            self.btn_toggle.setGeometry(w - self.drawer_width - self.btn_toggle_width, 
                                         (h - self.btn_toggle_height) // 2, 
                                         self.btn_toggle_width, 
                                         self.btn_toggle_height)
        else:
            self.drawer_panel.setGeometry(w, 0, 0, h)
            self.btn_toggle.setGeometry(w - self.btn_toggle_width, 
                                         (h - self.btn_toggle_height) // 2, 
                                         self.btn_toggle_width, 
                                         self.btn_toggle_height)

    # ==============================================================================
    # 核心功能 2：高速擷圖 (mss)
    # ==============================================================================
    def capture_game_region(self, ratio_dict: dict) -> np.ndarray:
        """
        根據指定的螢幕比例字典，對遊戲視窗內的特定區域進行高速擷圖，並回傳 OpenCV (numpy array) 影像。
        ratio_dict: 包含 'left', 'top', 'width', 'height' 佔總寬高比例的字典，例如 config.DIALOG_BOX_RATIO
        """
        if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd):
            logger.warning("擷圖失敗：遊戲視窗不存在")
            return None
            
        try:
            # 1. 取得遊戲客戶區的螢幕絕對座標與大小
            client_rect = win32gui.GetClientRect(self.game_hwnd)
            client_w = client_rect[2] - client_rect[0]
            client_h = client_rect[3] - client_rect[1]
            client_x, client_y = win32gui.ClientToScreen(self.game_hwnd, (0, 0))
            
            if client_w <= 0 or client_h <= 0:
                return None
                
            # 2. 計算目標區域的螢幕絕對座標與長寬
            target_x = client_x + int(client_w * ratio_dict["left"])
            target_y = client_y + int(client_h * ratio_dict["top"])
            target_w = int(client_w * ratio_dict["width"])
            target_h = int(client_h * ratio_dict["height"])
            
            # 定義 mss 擷取範圍
            monitor = {
                "top": target_y,
                "left": target_x,
                "width": target_w,
                "height": target_h
            }
            
            # 3. 高速擷圖並轉為 OpenCV numpy 格式
            sct_img = self.sct.grab(monitor)
            # 轉換為 numpy 陣列 (BGRA 格式)
            frame = np.array(sct_img)
            # 轉換成一般的 BGR 影像 (OpenCV 格式)
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            return bgr_frame
            
        except Exception as e:
            logger.error(f"擷取遊戲特定區域時發生異常: {e}")
            return None

    # ==============================================================================
    # 核心功能 3：置頂與鼠標穿透控制
    # ==============================================================================
    def set_mouse_transparent(self, enabled: bool):
        """
        呼叫 Windows API 動態切換視窗的鼠標穿透樣式 (WS_EX_TRANSPARENT)
        """
        if self.is_transparent == enabled:
            return
            
        self.is_transparent = enabled
        hwnd = int(self.winId())
        
        try:
            # 獲取視窗原有的擴展樣式
            extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            if enabled:
                # 加上 WS_EX_TRANSPARENT (滑鼠穿透) 與 WS_EX_LAYERED (分層)
                # 讓玩家的點擊可以穿透至底下的遊戲
                extended_style |= win32con.WS_EX_TRANSPARENT
                extended_style |= win32con.WS_EX_LAYERED
                logger.debug("已將懸浮窗切換為：鼠標穿透狀態")
            else:
                # 移除 WS_EX_TRANSPARENT，恢復一般可互動視窗狀態
                extended_style &= ~win32con.WS_EX_TRANSPARENT
                logger.debug("已將懸浮窗切換為：一般互動狀態 (接收滑鼠點擊)")
                
            # 設定新的樣式
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, extended_style)
            
            # 必須調用 SetWindowPos 才能使變更立即生效
            # 使用 HWND_TOPMOST 保持置頂，SWP_FRAMECHANGED 重刷邊框
            win32gui.SetWindowPos(
                hwnd, 
                win32con.HWND_TOPMOST, 
                0, 0, 0, 0, 
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED
            )
        except Exception as e:
            logger.error(f"切換鼠標穿透狀態時發生錯誤: {e}")
            
    def check_mouse_position(self):
        """
        滑鼠檢測計時器回呼：
        利用 QCursor.pos() 監測滑鼠絕對座標。若滑鼠在「互動區域（按鈕/抽屜）」內，
        則「關閉」鼠標穿透；若滑鼠在「非互動區域（透明背景/對話框文字）」，則「開啟」鼠標穿透。
        """
        if not self.isVisible():
            return
            
        # 獲取滑鼠的螢幕絕對座標
        cursor_pos = QCursor.pos()
        # 轉換為本懸浮視窗的相對座標
        local_pos = self.mapFromGlobal(cursor_pos)
        
        # 判定滑鼠是否落在「抽屜控制微按鈕」的矩形區域內
        in_toggle_btn = self.btn_toggle.geometry().contains(local_pos)
        
        # 判定滑鼠是否落在「歷史日誌抽屜面板」的矩形區域內
        in_drawer = False
        if self.drawer_expanded:
            in_drawer = self.drawer_panel.geometry().contains(local_pos)
            
        # 如果滑鼠在按鈕或抽屜上，則必須可以點擊（非穿透）
        if in_toggle_btn or in_drawer:
            self.set_mouse_transparent(False)
        else:
            # 其它區域（包括對話框文字與透明背景）皆維持穿透，不干擾遊戲操作
            self.set_mouse_transparent(True)

    # ==============================================================================
    # 核心功能 4：歷史劇情日誌抽屜與流暢動畫
    # ==============================================================================
    def toggle_drawer(self):
        """
        點擊按鈕後，以流暢動畫向左/右展開或收合歷史劇情日誌抽屜
        """
        w = self.width()
        h = self.height()
        
        # 建立抽屜面板與按鈕的位置動畫
        self.drawer_anim = QPropertyAnimation(self.drawer_panel, b"geometry")
        self.btn_anim = QPropertyAnimation(self.btn_toggle, b"geometry")
        
        # 設定彈性平滑動畫曲線 (OutCubic 或 OutQuad 效果更 Premium)
        self.drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.btn_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.drawer_anim.setDuration(300) # 300 毫秒動畫
        self.btn_anim.setDuration(300)
        
        if not self.drawer_expanded:
            # --- 展開抽屜 ---
            logger.info("展開歷史劇情抽屜...")
            self.drawer_expanded = True
            self.btn_toggle.setText("▶\n收\n合")
            
            # 抽屜從畫面外 (w, 0, 0, h) 展開至 (w - drawer_width, 0, drawer_width, h)
            self.drawer_anim.setStartValue(QRect(w, 0, 0, h))
            self.drawer_anim.setEndValue(QRect(w - self.drawer_width, 0, self.drawer_width, h))
            
            # 按鈕從右邊緣移動到抽屜左側
            self.btn_anim.setStartValue(self.btn_toggle.geometry())
            self.btn_anim.setEndValue(QRect(w - self.drawer_width - self.btn_toggle_width, 
                                            (h - self.btn_toggle_height) // 2, 
                                            self.btn_toggle_width, 
                                            self.btn_toggle_height))
        else:
            # --- 收合抽屜 ---
            logger.info("收合歷史劇情抽屜...")
            self.drawer_expanded = False
            self.btn_toggle.setText("◀\n歷\n史")
            
            # 抽屜縮回 (w, 0, 0, h)
            self.drawer_anim.setStartValue(self.drawer_panel.geometry())
            self.drawer_anim.setEndValue(QRect(w, 0, 0, h))
            
            # 按鈕移回右邊緣
            self.btn_anim.setStartValue(self.btn_toggle.geometry())
            self.btn_anim.setEndValue(QRect(w - self.btn_toggle_width, 
                                            (h - self.btn_toggle_height) // 2, 
                                            self.btn_toggle_width, 
                                            self.btn_toggle_height))
            
        # 同步啟動動畫
        self.drawer_anim.start()
        self.btn_anim.start()

    # ==============================================================================
    # 翻譯數據對接與歷史條目更新
    # ==============================================================================
    def update_translation(self, speaker: str, japanese: str, chinese: str):
        """
        對外主要接口：更新目前對話框的說話者與翻譯中文。
        若對話內容與上一句不同，則會自動添加至歷史日誌中。
        """
        # 更新翻譯主面板文字
        self.speaker_label.setText(speaker if speaker else "角色名字")
        self.text_label.setText(chinese)
        
        # 避免重複添加相同的對話
        if not self.history_records or self.history_records[-1]["jp"] != japanese:
            # 保存到歷史紀錄
            record = {"speaker": speaker, "jp": japanese, "zh": chinese, "timestamp": time.time()}
            self.history_records.append(record)
            
            # 建立歷史項目 Widget 並加入佈局
            item_widget = HistoryItemWidget(japanese, chinese, self.scroll_content)
            
            # 插入到 Stretch 之前（即從最底端往上排版）
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item_widget)
            
            # 自動滾動到最底部
            QTimer.singleShot(100, self.scroll_to_bottom)
            
            logger.info(f"新增歷史紀錄: [{speaker}] -> {chinese[:15]}...")
            
    def scroll_to_bottom(self):
        """
        自動將歷史抽屜滾動條滾動至最底部
        """
        v_bar = self.scroll_area.verticalScrollBar()
        v_bar.setValue(v_bar.maximum())
        
    def clear_history(self):
        """
        清除所有的對話歷史紀錄
        """
        logger.info("清除劇情對話歷史...")
        self.history_records.clear()
        
        # 移除所有子 Widget (排除最後一個 stretch)
        while self.scroll_layout.count() > 1:
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def closeEvent(self, event):
        """
        關閉視窗時釋放資源
        """
        self.track_timer.stop()
        self.mouse_timer.stop()
        self.sct.close()
        logger.info("UIManager 已安全關閉。")
        super().closeEvent(event)


# ==============================================================================
# 5. 單機測試啟動區塊
# ==============================================================================
if __name__ == "__main__":
    import sys
    print("正在以獨立模式啟動 UIManager 測試...")
    
    app = QApplication(sys.argv)
    ui = UIManager()
    ui.show()
    
    # 建立一個測試定時器，模擬每隔 3 秒送出一段新翻譯
    test_timer = QTimer()
    test_counter = 0
    
    test_dialogues = [
        ("ペコリーヌ", "おいっすー！お腹がペコペコですよ☆", "哈囉哈囉！肚子好餓好餓喔☆"),
        ("コッコロ", "主さま、お怪我はありませんか？", "主人，您沒有受傷吧？"),
        ("キャル", "ちょっと！何ぼさっとしてんのよ！", "等一下！你是在發什麼呆啊！"),
        ("ペコリーヌ", "今日も一日、元気に冒險しましょう！", "今天一天也朝氣蓬勃地去冒險吧！")
    ]
    
    def simulate_translation():
        global test_counter
        speaker, jp, zh = test_dialogues[test_counter % len(test_dialogues)]
        ui.update_translation(speaker, jp, zh)
        test_counter += 1
        
    test_timer.timeout.connect(simulate_translation)
    test_timer.start(3000)
    
    sys.exit(app.exec())
