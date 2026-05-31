# 👑 PCRD 超異域公主連結 Re:Dive 終極工具箱 (PCRD Transtool)

[![GitHub License](https://img.shields.io/github/license/SmallOrange0323/PCRD_transtool?style=flat-square&color=blue)](LICENSE)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-pink?style=flat-square)](https://www.riverbankcomputing.com/software/pyqt/)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.5-blue?style=flat-square)](https://ai.google.dev/)
[![OpenCV](https://img.shields.io/badge/Vision-OpenCV-green?style=flat-square)](https://opencv.org/)

本專案是一個專為《超異域公主連結 Re:Dive》(PCRD) 玩家與開發者打造的**終極雙效工具箱**。
完美整合了**「網頁版數據轉換與分析儀表板」**與全新的**「PC 遊戲即時 AI 翻譯系統 (獨立 EXE 雙擊即玩)」**，提供最沉浸、極致視覺享受的遊戲輔助體驗。

---

## 🌟 核心雙軌功能介紹

### 📊 軌道一：網頁版數據轉換與分析儀表板
本專案的網頁核心工具，提供強大的 PCRD 遊戲數據解析與視覺化呈現：
*   **角色與公會戰數據分析**：解析遊戲內 raw 數據，轉化為直觀的圖表與數據報表。
*   **Web 介面操作**：雙擊 `index.html` 即可在瀏覽器中直接開啟精美的數據儀表板，支援 TW/JP 雙伺服器數據切換。
*   **無痛輕量**：採用純 Vanilla CSS 與高效 JS 打造，無需配置複雜的網頁伺服器。

### 🚀 軌道二：PC 遊戲即時 AI 翻譯系統 (Premium 置頂懸浮版)
專為觀賞日版遊戲劇情的玩家設計，採用**「100% 安全、非侵入式 (OCR + 懸浮窗)」**技術：
*   **🌸 櫻花粉 Premium 啟動控制台**：
    *   開箱即用的圖形化介面（Launcher），免手動改設定檔！
    *   安全儲存 Gemini API Key，支持顯示/隱藏金鑰。
    *   智慧最小化：點擊啟動自動收合至右下角系統托盤，不佔用您的螢幕。
*   **🖥️ 原生融入的置頂懸浮窗**：
    *   100ms 同步追蹤遊戲視窗位置與大小，排除標題列與邊框干擾。
    *   **動態滑鼠穿透**：滑鼠在透明背景上直接穿透至下方遊戲，在「歷史抽屜」上自動恢復點擊互動，完全不影響游戏操作。
    *   **平滑動畫歷史抽屜**：300ms 動態滑出劇情對照面板，方便回看上一句台詞。
*   **🔍 自適應雙軌翻譯 (Dual-Path)**：
    *   文字改變過濾（MAE）：切除 ▼ 箭頭區域只比對文字主體，**節省 90% 重複翻譯 API Token**。
    *   粉紅箭頭 ▼ HSV 偵測，配合 2.2 秒逾時安全網雙重觸發。
    *   本地 OCR 信心度不足自動 Fallback 轉交 Gemini Vision 多模態讀圖翻譯。
*   **🧠 專屬角色性格翻譯**：
    *   串接 Wiki 爬蟲自動更新譯名字典 `glossary.json`。
    *   約束 Gemini 依照可可蘿（主公大人溫柔體貼）、凱留（傲嬌吐槽）等角色性格進行繁中劇情翻譯。

---

## 📦 如何使用執行檔 (.EXE) 雙擊即玩

為了讓您能以最優雅、無痛的方式體驗即時翻譯小工具，我們已將其打包為獨立執行檔：

1.  **開啟發佈目錄：** 
    進入 [translator/dist/](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/translator/dist/) 資料夾。
2.  **雙擊運行：** 
    雙擊直接運行 [PCRD_AI_Translator.exe](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/translator/dist/PCRD_AI_Translator.exe)。
3.  **金鑰配置：** 
    在控制面板貼上您的 Gemini API Key 並點擊「💾 儲存金鑰」。
4.  **啟動翻譯：** 
    點擊「🚀 啟動即時翻譯監控」。控制台會自動收縮至右下角托盤，懸浮窗會自動開啟並緊貼您的 DMM 遊戲視窗！

---

## 🛠️ 開發環境與依賴套件

如果您想以原始碼方式執行或參與本專案開發，請準備 Python 3.10+ 環境並執行：

```bash
# 一鍵安裝所有 UI, 擷圖, 影像處理與 AI SDK 依賴
pip install PyQt6 pywin32 mss pygetwindow opencv-python google-generativeai beautifulsoup4 requests httpx pyinstaller
```

*   **啟動網頁儀表板**：直接雙擊 `index.html`。
*   **啟動翻譯器控制面板**：執行 `python translator/launcher.py`。
*   **啟動翻譯監控主程式**：執行 `python translator/main.py`。
*   **重新一鍵打包成 EXE**：執行 `pyinstaller --noconsole --onefile --name="PCRD_AI_Translator" translator/launcher.py`。
