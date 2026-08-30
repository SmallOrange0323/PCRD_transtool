# 📜 PCRD 歷史文件索引與權威邊界說明 (HISTORICAL_DOCUMENTS.md)

本文件定義專案中所有歷史文件、開荒報告與評估記錄的權威狀態與定位。

> [!IMPORTANT]
> **文件權威層級與真實來源 (Authority Hierarchy)**：
> 1. **實際程式碼實作 (Current Implementation)**：定義系統實際運行的唯一行為。
> 2. **現行權威技術手冊 (Canonical Technical References)**：
>    - 🏛️ [系統架構手冊 (ARCHITECTURE.md)](ARCHITECTURE.md) — 系統架構、模組邊界、資料所有權與架構不變量。
>    - 🔄 [資料更新管線工作手冊 (PIPELINE_WORKFLOW.md)](PIPELINE_WORKFLOW.md) — Pipeline v1 生命週期、更新/驗證/部署標準 SOP。
> 3. **AI 協作準則與上下文導引**：
>    - 🤝 [AI 協作開發原則 (agent.md)](../agent.md)
>    - 🌌 [AI Agent 專案導引 (antigravity.md)](../antigravity.md)
>    - 📖 [世界觀與術語基準 (.agents/AGENTS.md)](../.agents/AGENTS.md)
> 4. **歷史存檔文件 (Historical Documents & Snapshots)**：
>    - 僅供歷史追溯、設計脈絡與原始研究參考。
>    - **嚴禁覆蓋現行實作與 Canonical Docs**。

---

## 1. 歷史文檔盤點與狀態對照表 (Historical Inventory Table)

| 歷史文件路徑 | 權威狀態 (Status) | 建立時期 / 原始用途 | 現行權威替代來源 (Current Authority / Replacement) |
| :--- | :--- | :--- | :--- |
| `HANDOVER_HOME.md` | `HISTORICAL_REFERENCE` | 2026-06 開發者日常交接與本機啟動指引 | [README.md](../README.md)、[PIPELINE_WORKFLOW.md](PIPELINE_WORKFLOW.md) |
| `PCR_PROJECT_SPEC.md` | `HISTORICAL_REFERENCE` | 2026-04 專案草創時期之功能規格草案（含舊版 News/Arena 規劃） | [ARCHITECTURE.md](ARCHITECTURE.md)（已定稿為 Story Map 核心） |
| `PCR_TASK_TRACKER.md` | `HISTORICAL_REFERENCE` | 2026-04 專案早期任務開荒清單 | [README.md](../README.md)、Phase 3/4 成果 |
| `PCR_Data_Source_Guide.md` | `PARTIALLY_SUPERSEDED` | 2026-05 早期在瀏覽器端使用 sql.js 讀取資料庫之探索教學 | [ARCHITECTURE.md](ARCHITECTURE.md)、`dashboard/db.js` |
| `WEBSITE_REVIEW.md` | `HISTORICAL_SNAPSHOT` | 2026-06-24 針對 `map.js v5.2.2` 與 `dashboard/` 進行之全面架構評估報告 | [ARCHITECTURE.md](ARCHITECTURE.md)（現行架構） |
| `dashboard-fixes.md` | `HISTORICAL_REFERENCE` | 2026-06 記錄 `map.js`、`db.js` 早期 8 大邏輯與安全修復 | 現行程式碼實作（修復已固化在代碼中） |
| `peco_astraea_report.md` | `HISTORICAL_REFERENCE` | 2026-07 佩可（阿斯特賴亞）單一角色繁中數據抓取範例報告 | `dashboard/redive_tw.db`、`tracked_characters.json` |
| `docs/PHASE3_SCRIPT_INVENTORY.md` | `HISTORICAL_SNAPSHOT` | Phase 3A 專案舊腳本盤點與分類記錄快照（**保持不可變**） | [ARCHITECTURE.md](ARCHITECTURE.md)（現行模組分類） |

---

## 2. 歷史文檔詳細審計摘要

### 2.1 `HANDOVER_HOME.md`
* **用途**：2026 年 6 月中旬記錄當日完成之 CG 內嵌、Footer 聲明以及本地伺服器啟動方式。
* **保留價值**：包含專案早期開發軌跡。
* **處置**：保留於根目錄作為歷史參考，標準更新與部署請參閱 `PIPELINE_WORKFLOW.md`。

### 2.2 `PCR_PROJECT_SPEC.md` & `PCR_TASK_TRACKER.md`
* **用途**：專案初始化階段的願景與任務清單，包含舊版規劃之競技場查隊、公會戰 BOSS 數據導航、新聞公告監控等模組。
* **處置**：此類功能已於 Phase 3/4 明確標記為 Legacy，保留文檔作為草創歷史見證，不作為當前維護目標。

### 2.3 `PCR_Data_Source_Guide.md`
* **用途**：早期探索 sql.js WebAssembly 載入 `redive_tw.db` 之教學手冊。
* **保留價值**：包含瀏覽器端 SQLite 初始化與查詢原理之詳細技術說明。
* **處置**：保留作為底層原理參考文件。

### 2.4 `WEBSITE_REVIEW.md`
* **用途**：針對舊版 `map.js`（2400+ 行時期）之架構深度評估與 UX 分析報告。
* **保留價值**：高。記錄了大量前端重構痛點與演進脈絡。
* **處置**：保留作為不可變之架構評估歷史快照。

### 2.5 `dashboard-fixes.md` & `peco_astraea_report.md`
* **用途**：特定修復記錄與單一角色實裝數據報告。
* **處置**：保留作為歷史修復與資料抓取之範本參考。

### 2.6 `docs/PHASE3_SCRIPT_INVENTORY.md`
* **用途**：Phase 3A 進行 140 支腳本結構化盤點之歷史快照。
* **不變性原則**：本檔案為特定重構階段之歷史記錄，嚴禁更新其數字或分類，保持原始存檔不變。

---

## 3. Phase 4 文件重構與邊界收斂總結 (Phase 4 Documentation Closure)

Phase 4 完成了本專案全方位的文件結構審計、對齊與權威體系建立：

* **Phase 4.1**：完成專案全目錄結構審計與 Staleness Matrix 盤點。
* **Phase 4.1A**：完成本地工作區衛生審查，確認 21 份 untracked 本地資產與救援目錄安全隔離。
* **Phase 4.2**：完成 `README.md` 與 `antigravity.md` 的現況目錄樹與職責對齊。
* **Phase 4.3**：正式建立權威手冊 `docs/ARCHITECTURE.md` 與 `docs/PIPELINE_WORKFLOW.md`。
* **Phase 4.4**：完成 AI 指導文件（`agent.md`, `antigravity.md`, `.agents/AGENTS.md`）職責分工與權威層級收斂。
* **Phase 4.5**：完成歷史文檔盤點與權威邊界界定（本文件）。

### 結論
```text
專案文檔體系現已建立明確的權威層級：
實際程式碼實作 (Implementation) > 權威技術規範 (Canonical Docs) > 作業與導引原則 (Operational Guidance) > 歷史參考文檔 (Historical References)。
```
