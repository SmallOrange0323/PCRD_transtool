# PCRD 劇情地圖 (Story Map) - AI Agent 專案導引

## 🌌 專案核心定位
`PCRD_transtool` 的唯一核心生產專案為 **「公主連結劇情地圖（PCRD Story Map）」**。
本專案專注於提供高沉浸感、全話數繁中對白檢索、專屬 CG 劇照、場景背景與語音播放之 Web 應用，並擁有自動化從 So-net CDN 下載、解密與構建元數據的專屬資料管線。

> [!NOTE]
> 歷史上的競技場解法、戰隊戰 BOSS 導航、新聞公告監控等規劃屬舊版初期探索（Legacy），已不再作為核心開發方向。AI Agent 在開發與協作時應專注於 Story Map 前端功能與 CDN 資料管線之維護。

## 📁 目錄結構職責說明
*   `dashboard/`: Story Map 前端原始碼與本地即時開發目錄（包含 `map.js`, `characters.js`, `avatar-service.js`, `data/`, `story/`）。
*   `dist_story_map/`: 打包後的 GitHub Pages 獨立發布目錄（由 pipeline 生成，請勿手動修改）。
*   `pipeline/`: 核心資料管線（`fetch.py`, `bundle.py`, `deploy.py`, `validate.py`, `update.py`）。
*   `update_story_map.py`: 官方標準一鍵更新入口。
*   `tools/`: 核心底層工具與相容性工具，下轄 `tools/diagnostics/`（診斷探查）與 `tools/maintenance/`（維護工具）。
*   `archive/legacy_scripts/`: 歷史特定活動一次性修復腳本與過期工具安全封存區。
*   `docs/`: 世界觀指南、版本記錄、歷史盤點，以及正式的系統架構與 Pipeline 規範文件。
*   `.agents/`: AI Agent 協作規範與長期記憶指南。
*   `translator/`: 獨立實驗專案（日翻中即時懸浮翻譯器）。
*   `pcr_demo/`, `pcrd_sim/`: 早期探索與原型專案 (Legacy)。

## 📚 權威技術規範 (Technical Source of Truth)
*   🏛️ [系統架構手冊](docs/ARCHITECTURE.md) — 系統架構、資料所有權、模組職責與 9 大架構不變量。
*   🔄 [資料更新管線工作手冊](docs/PIPELINE_WORKFLOW.md) — Pipeline v1 生命週期、更新/驗證/部署 SOP。

> [!IMPORTANT]
> **文件權威層級 (Authority Hierarchy)**：
> 1. **實際程式碼實作 (Current Implementation)**：定義系統真實運行行為。
> 2. **權威技術手冊 (`docs/ARCHITECTURE.md`, `docs/PIPELINE_WORKFLOW.md`)**：定義正式架構與標準管線流程。當本導引文件與權威手冊發生細節不一致時，以權威手冊為準。
> 3. **AI 協作準則 (`agent.md`, `antigravity.md`)**：定義操作原則與專案上下文導引。
> 4. **歷史存檔文件 (Historical Snapshots)**：僅供歷史追溯參考，不得作為當前技術依據。

## 🧠 上下文記憶 (Context)
*   **主要產物**: 公主連結劇情地圖 (Web App)
*   **資料來源**: 台灣代理商 So-net CDN (官方唯一基準)
*   **更新週期**: 遊戲例行維護、新活動/新主線上線時執行 `python update_story_map.py`

