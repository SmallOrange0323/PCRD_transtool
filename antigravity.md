# PCRD 劇情地圖 (Story Map) - AI Agent 專案導引

## 🌌 專案核心定位
`PCRD_transtool` 的唯一核心生產專案為 **「公主連結劇情地圖（PCRD Story Map）」**。
本專案專注於提供高沉浸感、全話數繁中對白檢索、專屬 CG 劇照、場景背景與語音播放之 Web 應用，並擁有自動化從 So-net CDN 下載、解密與構建元數據的專屬資料管線。

> [!NOTE]
> 歷史上的競技場解法、戰隊戰 BOSS 導航、新聞公告監控等規劃屬舊版初期探索（Legacy），已不再作為核心開發方向。AI Agent 在開發與協作時應專注於 Story Map 前端功能與 CDN 資料管線之維護。

## 📁 目錄結構職責說明
*   `dashboard/`: Story Map 前端原始碼與本地即時開發目錄（包含 `map.js`, `characters.js`, `avatar-service.js`, `data/`, `story/`）。
*   `dist_story_map/`: 打包後的 GitHub Pages 獨立發布目錄（具備獨立 git working tree）。
*   `pipeline/`: 核心資料管線（`fetch.py`, `bundle.py`, `deploy.py`, `validate.py`, `update.py`）。
*   `update_story_map.py`: 根目錄一鍵更新入口。
*   `tools/`: 通用維護工具（`tools/maintenance/`）與診斷工具（`tools/diagnostics/`）。
*   `experiments/`: 獨立/歷史實驗專案（如 `experiments/translator/` 日翻中即時翻譯器）。
*   `archive/`: 歷史特定活動一次性修復腳本與遷移工具。
*   `docs/`: 最新架構文檔與資料流手冊。
*   `.agents/`: AI Agent 協作規範與長期記憶指南。

## 🧠 上下文記憶 (Context)
*   **主要產物**: 公主連結劇情地圖 (Web App)
*   **資料來源**: 台灣代理商 So-net CDN (官方唯一基準)
*   **更新週期**: 遊戲例行維護、新活動/新主線上線時執行 `python update_story_map.py`
