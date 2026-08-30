# 🔄 PCRD 劇情地圖資料更新與發布管線手冊 (PIPELINE_WORKFLOW.md)

本文件為 **Story Map Update Pipeline v1** 的官方操作與生命週期規範手冊。  
詳細說明資料獲取、決定性封裝、全量資料驗證與 GitHub Pages 發布機制。

---

## 1. 官方標準更新指令 (Canonical Entry Points)

專案根目錄之 `update_story_map.py` 為管線的唯一統一入口：

| 操作情境 | 執行指令 | 說明 |
| :--- | :--- | :--- |
| **日常增量更新** (推薦) | `python update_story_map.py` | 探測 CDN ➔ 同步 DB / 劇本 ➔ 決定性打包 ➔ 全量驗證 (不發布) |
| **模擬運行** (零副作用) | `python update_story_map.py --dry-run` | 僅比對版號與印出預期操作，不寫入檔案、不修改 Git |
| **正式線上發布** | `python update_story_map.py --deploy` | 驗證門禁通過後，自動將 `dist_story_map/` 推送至 `gh-pages` |
| **自定義 Commit 訊息發布** | `python update_story_map.py --deploy -m "deploy: update chara 138301"` | 附帶自定義 Git 提交訊息進行部署 |
| **手動執行全量資料自檢** | `python -m pipeline.validate` | 對 `dashboard/` 與 `dist_story_map/` 執行全量一致性深度檢查 |
| **手動執行 Story Map 封裝** | `python -m pipeline.bundle` | 單獨執行從 `dashboard/` 到 `dist_story_map/` 的決定性打包 |
| **手動單話素材下載** | `python -m pipeline.fetch fetch-story-voices --story-id <ID>`<br>`python -m pipeline.fetch fetch-story-images --story-id <ID>` | 手動補齊特定話數之語音 (.m4a) 或 CG / 背景大圖 |

---

## 2. 管線生命週期 (Pipeline Lifecycle)

當執行 `python update_story_map.py` 時，協調器 `pipeline/update.py` 將依序推進以下 5 個階段：

```text
  [ 階段 1: 預檢與版號探測 (Preflight) ]
             │
             ▼
  [ 階段 2: 上游增量同步 (Fetch Stage) ]
             │
             ▼
  [ 階段 3: 決定性封裝與 Cache-Busting (Bundle Stage) ]
             │
             ▼
  [ 階段 4: 單一全量驗證門禁 (Validation Stage) ]
             │
             ▼ (驗證通過且帶有 --deploy 參數時)
  [ 階段 5: 獨立發布推送 (Deploy Stage) ]
```

---

## 3. 各階段運作機制與技術規範

### 3.1 階段 1 & 2：獲取階段 (Fetch Stage)
* **版號探測**：
  * 調用 `pipeline.fetch.get_truth_version()` 向 So-net CDN 的 `storydata2_assetmanifest` 探測線上最高 `TruthVersion`。
  * 比對 `dashboard/versions/version_history.json` 中記錄的本地版號。
* **資料庫同步**：
  * 若線上版號遞增或本地 DB 缺失，自動下載最新 `redive_tw.db`。
  * 支援原子狀態寫入：寫入 `version_history.json.tmp` 後原子替換，避免中斷造成狀態檔案損壞。
* **追蹤角色劇本補齊 (Tracked Stories Sync)**：
  * 讀取 `dashboard/data/tracked_characters.json`。
  * 透過 `pipeline.fetch.get_story_ids_for_unit(unit_id)` 取得該角色的標準好感度話數 ID 清單。
  * 檢查 `dashboard/story/{story_id}.json` 是否存在，若缺失則自動自 So-net CDN 下載對應 AssetBundle，經 UnityPy 解密後寫入繁中劇本 JSON。
  * **強一致性防護**：下載完成後即刻檢驗實體檔案存在性，若檔案未成功生成則判定同步失敗。

### 3.2 階段 3：打包階段 (Bundle Stage)
* **SHA-256 內容比對 (Deterministic Content Comparison)**：
  * 對 `story_map.html`, `*.js`, `*.css`, `redive_tw.db`, `data/*.json`, `story/*.json` 逐一計算 SHA-256 Hash。
  * 僅在來源檔案內容實質變更時才執行複製與更新，避免無謂的時間戳變動。
* **決定性版本號生成 (Deterministic Cache-Busting)**：
  * 移除隨機時間戳，改以 `db.js` 與 `redive_tw.db` 的 SHA-256 雜湊前綴生成決定性版本號（例如 `hash_94692392601e`）。
  * 寫入 `dist_story_map/data/db_info.json`。
* **腳本內嵌 (Script Inlining)**：
  * 將 `db.js` 與 `chapter-data.js` 的實體內容直接內嵌至 `dist_story_map/index.html`，徹底杜絕 GitHub Pages CDN 舊快取遺留問題。

### 3.3 階段 4：驗證階段 (Validation Stage - Single Source of Truth)
* **核心檔案存在性檢查**：確認 HTML, CSS, map.js, characters.js, avatar-service.js, story-asset-service.js, chapter-data.js, db.js, sql-wasm.js, sql-wasm.wasm, redive_tw.db 均齊全。
* **元數據 Schema 語法解析**：驗證 `chapters.json`、`extra_events.json`、`story_thumbnails.json`、`npc_avatars.json`、`tracked_characters.json`、`event_summaries.json` 均為合法 JSON。
* **SQLite 資料庫完整性**：實際開啟 SQLite 連線，驗證 `unit_data`、`story_detail`、`event_story_data` 等表存在且有記錄。
* **全量 9,000+ 篇劇本深檢**：遍歷 `story/` 下所有 JSON 劇本，逐份進行 JSON 解析與結構合法性檢驗。
* **發布集合對白檢驗**：驗證 `dashboard/story/` 中的數字 ID 劇本是否全部存在於 `dist_story_map/story/`，並逐份解析 dist 中的劇本 JSON（註：目前門禁不會將 dist 中額外存在的 story JSON 視為錯誤）。

### 3.4 階段 5：部署階段 (Deploy Stage)
* **發布前自檢**：在執行任何 Git 操作前，強制執行 `validate_story_map(check_dist=True)`。
* **獨立工作樹推送**：
  * 確認 `dist_story_map/.git` 存在。
  * 在 `dist_story_map/` 目錄內執行 `git add -A`、`git commit`。
  * 僅將發布產物推送至 `origin/gh-pages`（`HEAD:gh-pages`）。
  * **嚴禁**：向 `main` / `master` 源碼分支推送未經審查的變更。

---

## 4. 模擬運行語意 (Dry-Run Semantics)

當加上 `--dry-run` 參數時：
* **會執行的操作**：
  * 線上 CDN TruthVersion 探測。
  * 本地版本比對與缺失話數掃描。
  * 計算預期打包的 SHA-256 與 `db_version`。
  * 執行全量唯讀資料驗證門禁。
* **絕對不會執行的操作 (零副作用保障)**：
  * ❌ 不下載或覆寫 `redive_tw.db`。
  * ❌ 不更新 `version_history.json`。
  * ❌ 不寫入或修改 `dashboard/story/` 與 `dist_story_map/` 下的任何實體檔案。
  * ❌ 不執行任何 Git commit 或 Git push。

---

## 5. 異常處理與 Exit Code 行為 (Failure Behavior)

| 失敗情境 | 發生階段 | 預期系統行為 |
| :--- | :--- | :--- |
| **CDN 連線逾時 / 無法解析** | Fetch Stage | 印出警告 Log，使用本地現有資料庫繼續執行（離線降級） |
| **追蹤角色話數下載失敗** | Fetch Stage | 拋出同步錯誤，終止管線，Exit 1 |
| **元數據損壞 / JSON 語法錯誤** | Validation Stage | 驗證門禁報錯，印出錯誤行數，終止管線，Exit 1 |
| **全量劇本中有損壞 JSON** | Validation Stage | 驗證門禁攔截，標記錯誤篇數，終止管線，Exit 1 |
| **dist_story_map 缺少 .git** | Deploy Stage | 部署器攔截，報錯缺少獨立發布目錄，終止發布，Exit 1 |
| **GitHub 網路推送失敗** | Deploy Stage | 捕捉 Git 異常並印出錯誤訊息，Exit 1 |

> [!NOTE]
> 在 Pipeline v1 中，非零 Exit Code（Exit 1 / Exit 2）均代表執行中斷或驗證失敗；Exit 0 代表全流程無錯誤通過。

---

## 6. 維護工具與診斷工具邊界 (Maintenance Boundaries)

* **日常標準工作流**：一律使用 `python update_story_map.py`。
* **批次維護工具 (`tools/maintenance/`)**：
  * `download_stories_tw.py`：僅在需要全量重建本地 9000+ 篇劇本池時手動執行。
  * `download_voices_tw.py`：僅在需要批次下載台版特定語音封包時手動執行。
* **診斷探查工具 (`tools/diagnostics/`)**：
  * 純唯讀探查（如 `list_tw_tables.py`、`scan_highest_sonet_version.py`），不會修改專案狀態。
* **相容性舊部署腳本 (`tools/pcrd_deploy.py`)**：
  * 保留作為相容性介面，非正式發布途徑。

---

## 7. 日常更新安全操作標準程序 (SOP)

當台服維護完畢或有新角色上線時，請依循以下標準作業程序：

1. **確認工作區狀態**：
   ```bash
   git status
   ```
2. **執行模擬運行預檢 (Dry-Run)**：
   ```bash
   python update_story_map.py --dry-run
   ```
   *確認輸出顯示 Exit 0 且無異常報錯。*
3. **執行正式增量更新與封裝**：
   ```bash
   python update_story_map.py
   ```
4. **手動確認資料完整性**：
   ```bash
   python -m pipeline.validate
   ```
5. **檢視工作區變更並決定是否發布**：
   ```bash
   # 若確認要同步發布至 GitHub Pages 線上網頁：
   python update_story_map.py --deploy -m "deploy: update version 00600023"
   ```

---

## 8. 相關架構手冊引用

* 🏛️ [系統架構手冊](ARCHITECTURE.md)
* 📖 [專案總覽與快速開始](../README.md)

