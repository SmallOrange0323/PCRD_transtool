# PCRD Story Map — 資料更新標準作業程序手冊 (DATA_UPDATE_RUNBOOK.md)

> [!IMPORTANT]
> **本文件定義本專案（`PCRD_transtool`）在遊戲資料更新時的標準操作流程與規範。**
> 專案架構包含**來源倉庫 (Source Repo: `main`)** 與**發布倉庫 (Deployment Repo: `dist_story_map` / `gh-pages`)**。
> 正常發布必須嚴格遵守：**發布同步邊界 (Release Synchronization Boundary)** — 來源資料完成審查並合併至 `main` 後，禁止再次執行包含上游抓取的 full updater，必須使用純發布指令發布（Source Commit Precedes Deploy）。

---

## 一、 指令類型與發布同步邊界 (Command Types & Sync Boundary)

| 指令角色 | 具體指令 | 是否觸發上游抓取？ | 適用時機與說明 |
| :--- | :--- | :--- | :--- |
| **全流程更新 (Full Updater)** | `python update_story_map.py` | **是 (YES)** | **來源同步階段**：探測 CDN、下載 DB 與劇本、評估新鮮度與覆蓋率、生成初始 dist 並自檢 |
| **覆蓋率分析 (Coverage-Only)** | `python update_story_map.py --coverage` | **否 (NO)** | **唯讀覆蓋檢驗**：分析必備/可選劇本覆蓋與缺失，零寫入副作用 |
| **單話對白抓取 (Story Fetch)** | `python tools/pcrd_fetch.py fetch-story --story-id <id>` | **是 (YES)** | **輕量補齊**：僅抓取與解密單話對白 JSON，無多媒體與縮圖副作用 |
| **純打包 (Bundle-Only)** | `python -m pipeline.bundle` | **否 (NO)** | **決定性建置**：基於當前本地原始碼重新決定性打包，不連線抓取上游 |
| **全量門禁 (Validator)** | `python -m pipeline.validate` | **否 (NO)** | **門禁自檢**：驗證來源與 dist 資料完整性 |
| **純發布 (Deploy-Only)** | `python -m pipeline.deploy` | **否 (NO)** | **正式發布唯一推薦**：將已驗證之 dist 提交並推送到 `gh-pages` |
| **單次一鍵更新發布 (One-Shot)** | `python update_story_map.py --deploy` | **是 (YES)** | **不推薦用於審查發布**：因包含上游同步，可能破壞已審查 main 的可重現性；受新鮮度防禦門禁保護 |

---

## 二、 新鮮度狀態模型與發布防禦門禁 (Freshness States & Gate)

管線每次執行時均會程式化評估上游新鮮度狀態（`FreshnessResult`）：

| 新鮮度狀態 (Freshness Status) | 判定條件 | 本地更新是否允許？ | 自動發布 (`--deploy`) 是否允許？ | 狀態意涵與處置 |
| :--- | :--- | :--- | :--- | :--- |
| **`CONFIRMED_CURRENT`** | CDN 探測成功且與本地版號一致 | `YES` | `YES` | 上游已確認為最新版，新鮮度具備強保證。 |
| **`UPDATE_AVAILABLE`** | CDN 探測成功且版號高於本地 (或 DB 缺失) | `YES` | `NO (需先同步)` | 檢測到新版本，管線會下載新 SQLite 資料庫。 |
| **`UPDATED_SUCCESSFULLY`** | 新資料庫與版本狀態經直接證實並原子寫入完成 | `YES` | `YES` | 新版資料同步就緒，等待審查與發布。 |
| **`UPDATE_DOWNLOADED_UNCONFIRMED`** | 鏡像資料庫下載成功，但鏡像內容無法直接證明與 So-net TruthVersion 對齊 | `YES (降級)` | **`BLOCKED (預設阻斷)`** | 為防範第三方鏡像滯後 (Mirror Lag)，未虛假推進版號；阻斷自動發布以策安全。 |
| **`REMOTE_UNREACHABLE`** | CDN 探測超時/連線失敗，本地 DB 存在 | `YES (降級)` | **`BLOCKED (預設阻斷)`** | 降級支援離線打包；但阻斷自動發布以防 stale deploy。 |
| **`LOCAL_STATE_MISSING`** | CDN 探測失敗且本地無資料庫 | `NO` | `NO` | 本地無可用資料庫，管線立即終止。 |
| **`UPDATE_FAILED`** | 下載資料庫或解密異常中斷 | `NO` | `NO` | 下載異常，管線立即終止。 |

> [!WARNING]
> **新鮮度生產防禦門禁 (Freshness Deploy Gate)**：
> 當執行 `python update_story_map.py --deploy` 時，若新鮮度為 `UPDATE_DOWNLOADED_UNCONFIRMED` 或 `REMOTE_UNREACHABLE` 等未確認狀態，管線會**立即阻斷發布並返回 Exit Code 1**。
> 若經人工作業已審查鏡像資料庫完整無誤，請帶入明確覆蓋參數：`--allow-unconfirmed-freshness`；或依循標準工作流合併至 `main` 後執行純發布指令 `python -m pipeline.deploy`。

---

## 三、 劇本覆蓋率模型、來源健康度與發布防禦 (Coverage Guard & Integrity Gate)

管線內建具備來源健康度檢驗之唯讀覆蓋率守衛（Coverage Guard），嚴格區分產品必備與可選劇本，並不吞沒任何權威來源錯誤：

1. **覆蓋率分析狀態 (Analysis Integrity States)**：
   - **`VALID`**：資料庫與所有元數據來源均成功讀取並解析，覆蓋率具備 100% 完整性。
   - **`DEGRADED`**：部分非核心元數據（如分支或新活動 JSON）讀取失敗，覆蓋率降級為部分解析（政策狀態標記為 `PARTIAL`）。
   - **`INVALID`**：核心來源（如 SQLite 資料庫）缺失或查詢失敗，覆蓋率無法解析（政策狀態標記為 `UNRESOLVED`）。
2. **產品必備集合 (Required Union)**：
   - 主線劇情 (`story_detail` 2xxxxxx)
   - 公會劇情 (`story_detail` 3xxxxxx)
   - 露娜塔與系統劇情 (`story_detail` 4xxxxxx)
   - 追蹤角色劇情 (`tracked_characters.json` 各角色之 `chara_story_status`)
   - 第 3 部分支補充劇情 (`branch_stories.json`)
   - 新形式活動劇情 (`extra_events.json`)
3. **可選歷史集合 (Optional Historic)**：
   - 未在追蹤清單中之歷史角色劇情 (`story_detail` 1xxxxxx)
   - 週年慶與特殊迷你活動 (`story_detail` 9xxxxxx)
4. **缺失與未分類處理政策 (Missing & Unknown Policy)**：
   - **必備劇本缺失 (`missing_required > 0`)**：管線判定為**嚴重錯誤，立即中止建置 (Fail-Stop)**，並印出缺失清單，引導運維者使用 `fetch-story --story-id <id>` 補齊。管線**不執行未經審查的自動 bulk download**。
   - **未分類預期話數 (`unknown_expected > 0` 或 `missing_unknown > 0`)**：代表政策尚未完全收斂，本地操作印出 Warning，**自動生產發布立即阻斷 (BLOCK DEPLOY)**。
   - **可選歷史劇本缺失 (`missing_optional > 0`)**：管線記錄 `[WARN]` 提示，不阻斷本地打包與發布（對齊 Validator 警告語意）。

> [!CAUTION]
> **覆蓋率完整性發布防禦門禁 (Coverage Integrity Gate)**：
> 自動生產發布（`update_story_map.py --deploy`）強制要求 `analysis_status == VALID` 且 `unknown_expected == 0` 且 `missing_required == 0`。
> 若覆蓋率分析降級 (`DEGRADED` 或 `INVALID`)，發布將被強制阻斷。**`--allow-unconfirmed-freshness` 僅能 bypass 上游新鮮度檢查，絕對無法繞過此覆蓋率完整性門禁**！

---

## 四、 變更類型分類 (Update Change Classification)

| 變更類型 | 涵蓋情境 | 前端 Runtime 是否修改？ | 管線/工具代碼是否修改？ | 預期修改檔案範圍 |
| :--- | :--- | :--- | :--- | :--- |
| **TYPE A (Data Only)** | 遊戲日常換裝、新角色對白上線 (Schema 不變) | **否 (NO)** | **否 (NO)** | `redive_tw.db`, `dashboard/story/*.json`, `versions/` |
| **TYPE B (Generated Metadata)** | 角色縮圖快取更新、話數索引重建 | **否 (NO)** | **否 (NO)** | `dashboard/data/*.json`, `dist_story_map/data/` |
| **TYPE C (Upstream Contract Break)** | 官方 CDN 路徑變更、劇本欄位格式異動 | **通常否 (NO)** | **是 (YES)** | `pipeline/fetch.py`, `tools/pcrd_fetch.py` |
| **TYPE D (Runtime Feature Change)** | 網站新增功能分頁、UI 改版、Normalizer 策略調整 | **是 (YES)** | **依需求** | `dashboard/*.js`, `dashboard/*.css`, `tests/` |

---

## 五、 標準日常更新與可重現發布流程 (Authoritative Reproducible Release Path)

### 階段一：來源資料同步與審查 (Source Synchronization Phase)

#### 步驟 1：對齊 main 並建立資料更新分支
```bash
git switch main
git pull --ff-only
git switch -c data/update-YYYYMMDD
```

#### 步驟 2：執行零副作用 Dry-Run 模擬與覆蓋率檢驗
```bash
python update_story_map.py --dry-run
# 或僅檢驗劇本覆蓋現況：
python update_story_map.py --coverage
```

#### 步驟 3：執行本地增量更新與決定性打包 (不發布)
```bash
python update_story_map.py
```
* 若報告顯示有缺失話數，可執行單話輕量抓取指令：
  ```bash
  python tools/pcrd_fetch.py fetch-story --story-id <story_id>
  ```

#### 步驟 4：審查來源資料變更 (Source Review Gate)
```bash
git status --short
git diff --stat
```
* **資料庫審查**：對於二進位之 `redive_tw.db`，審查檔案大小、TruthVersion 與 DB hash，確認無異常縮水或損毀。
* **劇本審查**：確認新增的 `dashboard/story/<id>.json` 檔案名稱與內容符合預期。
* **代碼安全檢查**：若發現意外修改了 `dashboard/*.js` 等源碼檔案，**立即中止發布 (STOP)**！

#### 步驟 5：執行資料完整性驗證
```bash
python -m pipeline.validate
```

#### 步驟 6：針對性 Stage 與 Commit 來源變更 (嚴禁全局暫存)
> [!CAUTION]
> **嚴格禁止執行 `git add .`、`git add -A`、`git clean` 或 `git stash -u`**！
> **嚴格禁止執行 `git add dist_story_map`**（`dist_story_map` 為獨立 Git 工作區，絕不可被主倉庫暫存）！

```bash
# 僅針對實際更新的檔案進行精準暫存：
git add dashboard/redive_tw.db
git add dashboard/versions/version_history.json
git add dashboard/story/<新增的story_id>.json
# 若有更新元數據則暫存對應檔案

git commit -m "data: update tw db and story data YYYY-MM-DD"
```

#### 步驟 7：推送分支並合併至 main (Source Review Gate Passed)
```bash
git push -u origin data/update-YYYYMMDD
# 經審查通過後，Fast-Forward 合併至 main 並推送：
git switch main
git merge --ff-only data/update-YYYYMMDD
git push origin main
```

---

### 階段二：可重現發布與部署驗證 (Release & Deployment Phase)

當來源變更已完全提交並推送到權威 `main` 後，進入發布階段：

#### 步驟 8：在乾淨的 main 上執行純發布指令 (Deploy-Only)
> [!IMPORTANT]
> **嚴格禁止在此步驟再次執行 `python update_story_map.py --deploy`**！
> 必須使用 `python -m pipeline.deploy`，確保發布產物與已審查之 main SHA 100% 決定性一致。

```bash
python -m pipeline.deploy
```

#### 步驟 9：執行線上即時驗收 (Live Site Smoke Test)
在瀏覽器無痕視窗開啟線上 GitHub Pages 網站，檢驗：
1. **控制台日誌**：確認無 JavaScript 報錯。
2. **資料庫載入**：確認右下角/關於頁面顯示最新 DB Hash 與 TruthVersion。
3. **最新話數與立繪**：隨機點選最新實裝的角色與最新主線話數，確認對白氣泡、看板娘立繪與對話頭像渲染正常。
