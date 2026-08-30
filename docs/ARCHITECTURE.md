# 🏛️ PCRD 劇情地圖系統架構手冊 (ARCHITECTURE.md)

本文件為 **公主連結劇情地圖（PCRD Story Map）** 現行系統架構的權威規範文檔（Canonical Architecture Documentation）。  
定義本專案之生產範圍、模組邊界、資料所有權、資料流向、前端架構快照與不可破壞之架構不變量。

---

## 1. 系統範疇 (System Scope)

`PCRD_transtool` 儲存庫之唯一核心生產目標為 **「公主連結劇情地圖 (PCRD Story Map)」**。

### 核心生產範疇 (Production Core)
* **`dashboard/`**：Story Map 前端源碼目錄、工作資料庫與本機開發環境。
* **`pipeline/`**：Story Map Update Pipeline v1 核心管線（增量同步、封裝、驗證、部署）。
* **`update_story_map.py`**：專案根目錄官方標準一鍵更新入口。
* **`dist_story_map/`**：GitHub Pages 獨立發布產物目錄。
* **`tools/pcrd_fetch.py`**：經長期實證之 So-net CDN / 上游資料獲取與解密底層引擎。

### 非生產核心範疇 (Non-Production Scope)
* **獨立 / 歷史實驗專案 (Side Projects / Legacy)**：
  * `translator/`：獨立日翻中即時懸浮翻譯工具（不參與 Story Map 構建與發布）。
  * `pcr_demo/`、`pcrd_sim/`：早期原型探索與戰鬥模擬實驗（已停止維護）。
* **歷史封存 (Archive)**：
  * `archive/legacy_scripts/`：過往特定活動修補腳本與舊部署入口（具副作用者已配置 Hard Stop 防護）。
* **維護與診斷支援層 (Maintenance & Diagnostics)**：
  * `tools/diagnostics/`：唯讀探查、表結構分析與 CDN 監控工具。
  * `tools/maintenance/`：手動觸發之全量/批次資料恢復工具。

---

## 2. 高階資料流架構 (High-Level Architecture)

Story Map 系統採用 **「單向資料流」** 與 **「發布前強制驗證門禁」** 設計：

```text
+-------------------------------------------------------------+
| 上游資料源 (Upstream Data Source)                             |
| 1. So-net CDN (https://img-pc.so-net.tw/dl/)                |
| 2. wthee 鏡像站 (https://wthee.xyz/db/redive_tw.db)           |
+-------------------------------------------------------------+
                              │
                              ▼ (HTTP 探測 / Unity3D Bundle 下載)
+-------------------------------------------------------------+
| 底層獲取引擎 (tools/pcrd_fetch.py)                           |
| - TruthVersion 探測、SQLite 資料庫解密                      |
| - UnityPy 對白文字解密、語音 / CG 插畫對應解析              |
+-------------------------------------------------------------+
                              │
                              ▼ (模組化包裝)
+-------------------------------------------------------------+
| 資料同步層 (pipeline/fetch.py)                              |
| - 支援單話話數推算 (get_story_ids_for_unit)                 |
| - 執行增量資料拉取與實體檔案存在性檢驗                      |
+-------------------------------------------------------------+
                              │
                              ▼ (原子替換 / 增量寫入)
+-------------------------------------------------------------+
| 工作區 / 單一真實來源 (dashboard/)                          |
| ├── redive_tw.db (正式台版 MasterData SQLite 資料庫)       |
| ├── story/*.json (全量 9000+ 篇官方解密繁中對白劇本)        |
| ├── data/*.json (章節、活動、頭像、劇照映射元數據)          |
| └── story_map.html, map.js, characters.js (前端源碼)        |
+-------------------------------------------------------------+
                              │
                              ▼ (SHA-256 內容比對 / Cache-Busting)
+-------------------------------------------------------------+
| 決定性打包器 (pipeline/bundle.py)                           |
| - 精準同步已追蹤角色與必要素材                              |
| - 生成決定性 db_info.json 版本號 (基於 Content Hash)        |
| - 內嵌 db.js / chapter-data.js 至 index.html                |
+-------------------------------------------------------------+
                              │
                              ▼ (複製產出)
+-------------------------------------------------------------+
| 獨立發布目錄 (dist_story_map/)                              |
| └── 具備獨立 .git 工作樹之 GitHub Pages 發布目錄            |
+-------------------------------------------------------------+
                              │
                              ▼ (全量深度自檢)
+-------------------------------------------------------------+
| 單一驗證門禁 (pipeline/validate.py)                         |
| ├── 核心檔案完整性檢查 (HTML, JS, CSS, WASM, DB)           |
| ├── SQLite 資料庫連線與角色/話數筆數檢驗                   |
| ├── 全量 9000+ 篇對白 JSON 逐份 Syntax 解析驗證            |
| └── dist_story_map 對白存在性與 JSON 語法檢驗 (dashboard 劇本均存在於 dist) |
+-------------------------------------------------------------+

                              │
                              ▼ (驗證通過後可選發布)
+-------------------------------------------------------------+
| 獨立發布部署器 (pipeline/deploy.py)                         |
| └── 僅將 dist_story_map/ 推送至 origin/gh-pages             |
+-------------------------------------------------------------+
```

---

## 3. 目錄職責與模組邊界 (Directory Responsibilities)

### 3.1 `dashboard/`
* **定位**：Story Map 前端源碼之單一真實來源（Source of Truth）與本地即時開發目錄。
* **主要組成**：
  * `story_map.html`：系統主介面結構。
  * `map.js`、`characters.js`：核心業務控制器。
  * `avatar-service.js`、`story-asset-service.js`：資產解析與多層 CDN 降級服務。
  * `chapter-data.js`、`db.js`：資料查詢與客戶端快取適配器。
  * `sql-wasm.js`、`sql-wasm.wasm`：瀏覽器端 SQLite WebAssembly 引擎。
  * `redive_tw.db`：**台版 MasterData 正式資料庫**（非根目錄資料庫）。
  * `data/`：章節大綱（`chapters.json`）、活動配置（`extra_events.json`）、頭像映射（`npc_avatars.json`）、劇照索引（`story_thumbnails.json`）等靜態元數據。
  * `story/`：已收錄之 9,000+ 篇官方繁中對白 JSON 劇本集合。

### 3.2 `pipeline/`
* **定位**：自動化增量更新、封裝、驗證與發布之標準管線模組。
* **各模組職責**：
  * **`update.py`**：
    * *職責*：統一更新協調器。串聯 Fetch ➔ Bundle ➔ Validate ➔ (Optional) Deploy。
    * *輸入*：CLI 參數（`--dry-run`, `--deploy`, `--message`）。
    * *副作用*：協調更新版本狀態（`version_history.json`）與觸發下游階段。
  * **`fetch.py`**：
    * *職責*：資料獲取適配層。重用 `tools/pcrd_fetch.py` 成熟邏輯，執行 TruthVersion 探測、資料庫同步與追蹤角色劇本下載。
    * *副作用*：寫入 `dashboard/redive_tw.db` 與 `dashboard/story/*.json`。
  * **`bundle.py`**：
    * *職責*：決定性打包器。基於 SHA-256 Content Hash 比對，精準將工作區代碼與資產複製至 `dist_story_map/`。
    * *副作用*：寫入/更新 `dist_story_map/` 下之檔案，內嵌核心腳本至 `index.html`。
    * *嚴禁*：依賴系統時間戳（Timestamp）生成版本號。
  * **`validate.py`**：
    * *職責*：單一驗證門禁。全專案唯一的驗證邏輯來源，負責執行全量資料庫、元數據、對白 JSON 與部署集合之一致性檢驗。
    * *輸出*：布林值（`True` 通過 / `False` 失敗）與詳細檢驗報告。
    * *副作用*：**無任何檔案寫入副作用（純唯讀）**。
  * **`deploy.py`**：
    * *職責*：獨立部署發布器。在發布前強制執行 `validate_story_map(check_dist=True)`，通過後在 `dist_story_map/` 獨立工作樹提交並推送至 `gh-pages`。
    * *嚴禁*：推送或修改根目錄專案原始碼分支（`main` / `master`）。

### 3.3 `tools/`
* **`tools/pcrd_fetch.py`**：上游資料抓取與 Unity AssetBundle 解析核心引擎。正式管線應持續重用其成熟邏輯，避免重複實作。
* **`tools/local_server.py`**：本地 HTTP 測試伺服器，已配置正確的 WASM、WebP、M4A MIME 類型。
* **`tools/pcrd_deploy.py`**：舊版部署輔助腳本（相容性保留，非官方標準發布途徑）。

### 3.4 `tools/diagnostics/`
* **定位**：唯讀性探查、除錯與分析工具集。
* **特性**：提供資料庫比對、表結構統計、CDN 版本探索等功能。
* **重要例外說明**：`tools/diagnostics/find_db_files.py` 刻意採用 `os.walk('.')` 從執行當前工作目錄（CWD）動態尋找資料庫，為專案保留之 CWD 執行例外。

### 3.5 `tools/maintenance/`
* **定位**：高影響、手動觸發的批次維護與修復工具。
* **收錄腳本**：`download_stories_tw.py`（全量批次對白下載）、`download_voices_tw.py`（批次語音下載）。
* **規則**：非日常更新入口，僅供特定資料修復使用。

### 3.6 `archive/legacy_scripts/`
* **定位**：歷史一次性修復腳本與舊部署入口封存區。
* **防護機制**：具破壞性、具副作用或已過期之入口（如 `archive/legacy_scripts/deploy.py`、`patch_winter_assets_and_json.py` 等）均已加入 **Execution Guard (Hard Stop)**，直接執行會拋出 RuntimeError 並終止；歷史唯讀腳本則安全保留供歷史追溯。

---

## 4. 資料所有權與單一真實來源 (Data Ownership & Source of Truth)

| 資料資產 | 正式存放路徑 (Canonical Location) | 生產者 (Producer) | 主要消費者 (Consumer) | 屬性 |
| :--- | :--- | :--- | :--- | :--- |
| **台版 MasterData 資料庫** | `dashboard/redive_tw.db` | `pipeline/fetch.py` (來自 wthee/So-net) | `db.js` (WebAssembly 查詢) | 核心資料 (Working DB) |
| **官方對白劇本 JSON** | `dashboard/story/{story_id}.json` | `pipeline/fetch.py` (UnityPy 解密) | `map.js` (前端對話渲染) | 核心資料 (9000+ 篇) |
| **章節與活動元數據** | `dashboard/data/*.json` | 手動維護 / 腳本增量建構 | `map.js`, `chapter-data.js` | 核心配置 |
| **版本歷程與狀態** | `dashboard/versions/version_history.json` | `pipeline/update.py` (原子更新) | `pipeline/update.py` (比對) | 狀態持久化 (State) |
| **前端應用源碼** | `dashboard/*.html, *.js, *.css` | 開發者維護 | 瀏覽器 / 本機開發 | 原始碼 (Source) |
| **發布建構產物** | `dist_story_map/*` | `pipeline/bundle.py` | GitHub Pages CDN | **生成物 (Generated Artifact)** |

> [!IMPORTANT]
> **嚴格禁止將根目錄下殘留的 `redive_tw.db` 視為正式資料庫**。正式資料庫路徑一律為 `dashboard/redive_tw.db`。

---

## 5. 源碼區與發布產物邊界 (Source vs. Generated Boundary)

* **`dashboard/`（源碼區）**：開發者唯一應該進行程式碼編修與資料維護的工作目錄。
* **`dist_story_map/`（發布產物區）**：由 `pipeline/bundle.py` 自動生成的發布封裝，內含獨立的 `.git`（追蹤 `gh-pages` 分支）。
* **規範**：**嚴禁手動修改 `dist_story_map/` 內的任何檔案**（Do not manually edit generated deploy output）。任何改動均應在 `dashboard/` 完成後，透過 Pipeline 重新打包生成。

---

## 6. 前端架構快照 (Frontend Architecture Snapshot)

Story Map 前端採用純前端（Zero-Backend）、輕量無框架（Vanilla Web Standard）設計：

```text
[ 瀏覽器 (Browser) ]
        │
        ├── 1. 載入 story_map.html & style.css
        ├── 2. 初始化 sql-wasm.js (載入 SQLite WASM 虛擬機器)
        ├── 3. 異步載入 redive_tw.db (14.7MB 二進位資料庫至記憶體)
        │
        ├── 4. 控制器調度：
        │       ├── map.js (核心業務控制器：章節樹、話數面板、AVG 劇場播放器)
        │       └── characters.js (角色圖鑑控制器：角色清單、好感度故事導航)
        │
        └── 5. 服務層支援：
                ├── db.js (SQL 查詢封裝：角色話數、登場統計、活動關聯)
                ├── chapter-data.js (章節與活動元數據快取)
                ├── avatar-service.js (角色頭像解析、NPC 規整化與 Fallback)
                └── story-asset-service.js (CG 插畫、背景與語音 CDN URL 構造)
```

### 已知架構特性 (Known Architectural Snapshot)
* **`map.js` 模組集中度高**：目前 `map.js` 承擔了章節選單切換、話數列表渲染、AVG 劇院播放器、全劇本關鍵字搜尋等多重職責，為專案中最大的單一控制器。此為現有架構現況，待後續專屬 Frontend Review 階段再行評估模組化拆分。

---

## 7. 部署發布架構 (Deployment Architecture)

* **官方正式發布路徑 (Canonical Path)**：
  ```bash
  python update_story_map.py --deploy
  ```
  內部流程：呼叫 `pipeline/deploy.py` ➔ 觸發 `pipeline.validate` 門禁 ➔ 在 `dist_story_map/` 目錄執行 Git commit ➔ 推送至遠端 `origin/gh-pages`。
* **舊版部署工具邊界 (Legacy Boundary)**：
  `tools/pcrd_deploy.py` 屬過渡相容工具，包含舊版直接推送到分支或同步 source branch 的歷史行為，不屬於當前規範的標準發布工作流。

---

## 8. 不可破壞之架構不變量 (Architecture Invariants)

所有未來的開發、重構、管線調整與 AI 協作均必須恪守以下 9 大硬性不變量：

1. **Story Map 唯一核心**：`PCRD Story Map` 為本儲存庫唯一的生產級目標。
2. **標準更新入口**：`update_story_map.py`（調用 `pipeline/`）為官方唯一的更新入口。
3. **MasterData 單一真理**：`dashboard/redive_tw.db` 為專案唯一的台版 MasterData 真實來源。
4. **生成物不可手動修改**：`dist_story_map/` 為純打包產物，嚴禁手動改動其內容。
5. **驗證門禁絕對先行**：正式發布前必須 100% 通過 `pipeline.validate` 門禁，自檢失敗嚴禁部署。
6. **重用成熟抓取引擎**：上游 So-net CDN 與 Unity3D 解析邏輯應重用 `tools/pcrd_fetch.py`，嚴禁重複發明輪子。
7. **封存區非運行時**：`archive/` 僅供歷史追溯，嚴禁被生產管線或正式前端代碼引用。
8. **診斷工具不可成為運行依賴**：`tools/diagnostics/` 為純唯讀探查工具，不得被主業務邏輯或 Pipeline 所依賴。
9. **歷史盤點文檔為不可變快照**：歷史盤點記錄（如 `docs/PHASE3_SCRIPT_INVENTORY.md`）為歷史存檔，不應隨當前重構而修改歷史內容。

---

## 9. 相關技術文件引用

* 🔄 [資料更新管線工作手冊](PIPELINE_WORKFLOW.md)
* 📖 [專案總覽與快速開始](../README.md)

