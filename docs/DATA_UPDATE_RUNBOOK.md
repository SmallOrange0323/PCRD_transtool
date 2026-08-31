# PCRD Story Map — 資料更新標準作業程序手冊 (DATA_UPDATE_RUNBOOK.md)

> [!IMPORTANT]
> **本文件定義本專案（`PCRD_transtool`）在遊戲資料更新時的標準操作流程與規範。**
> 專案架構包含**來源倉庫 (Source Repo: `main`)** 與**發布倉庫 (Deployment Repo: `dist_story_map` / `gh-pages`)**。
> 正常發布必須嚴格遵守：**發布同步邊界 (Release Synchronization Boundary)** — 來源資料完成審查並合併至 `main` 後，禁止再次執行包含上游抓取的 full updater，必須使用純發布指令發布（Source Commit Precedes Deploy）。

---

## 一、 指令類型與發布同步邊界 (Command Types & Sync Boundary)

| 指令角色 | 具體指令 | 是否觸發上游抓取？ | 適用時機與說明 |
| :--- | :--- | :--- | :--- |
| **全流程更新 (Full Updater)** | `python update_story_map.py` | **是 (YES)** | **來源同步階段**：探測 CDN、下載 DB 與劇本、生成初始 dist 並自檢 |
| **純打包 (Bundle-Only)** | `python -m pipeline.bundle` | **否 (NO)** | **決定性建置**：基於當前本地原始碼重新決定性打包，不連線抓取上游 |
| **全量門禁 (Validator)** | `python -m pipeline.validate` | **否 (NO)** | **門禁自檢**：驗證來源與 dist 資料完整性 |
| **純發布 (Deploy-Only)** | `python -m pipeline.deploy` | **否 (NO)** | **正式發布唯一推薦**：將已驗證之 dist 提交並推送到 `gh-pages` |
| **單次一鍵更新發布 (One-Shot)** | `python update_story_map.py --deploy` | **是 (YES)** | **不推薦用於審查發布**：因包含上游同步，可能破壞已審查 main 的可重現性 |

---

## 二、 變更類型分類 (Update Change Classification)

| 變更類型 | 涵蓋情境 | 前端 Runtime 是否修改？ | 管線/工具代碼是否修改？ | 預期修改檔案範圍 |
| :--- | :--- | :--- | :--- | :--- |
| **TYPE A (Data Only)** | 遊戲日常換裝、新角色對白上線 (Schema 不變) | **否 (NO)** | **否 (NO)** | `redive_tw.db`, `dashboard/story/*.json`, `versions/` |
| **TYPE B (Generated Metadata)** | 角色縮圖快取更新、話數索引重建 | **否 (NO)** | **否 (NO)** | `dashboard/data/*.json`, `dist_story_map/data/` |
| **TYPE C (Upstream Contract Break)** | 官方 CDN 路徑變更、劇本欄位格式異動 | **通常否 (NO)** | **是 (YES)** | `pipeline/fetch.py`, `tools/pcrd_fetch.py` |
| **TYPE D (Runtime Feature Change)** | 網站新增功能分頁、UI 改版、Normalizer 策略調整 | **是 (YES)** | **依需求** | `dashboard/*.js`, `dashboard/*.css`, `tests/` |

---

## 三、 發布前覆蓋面檢查 (Pre-Flight Coverage Check)

在執行更新前，請先確認更新目標與涵蓋範圍：
1. **TruthVersion 探測是否成功？** 檢查 `update_story_map.py --dry-run` 輸出中是否有 `[CDN] 線上最高 TruthVersion: 006xxxxx`。
2. **資料庫是否最新？** 確認 `redive_tw.db` 版號是否與 CDN 一致。
3. **目標故事是否由 Canonical Pipeline 自動涵蓋？**
   - 若為**已追蹤角色個人劇情**：由 `tracked_characters.json` 自動增量下載。
   - 若為**全新角色個人劇情**：需先將新角色 `unit_id` 與 `icon_ids` 加入 `tracked_characters.json`，或執行 `python -m pipeline.fetch fetch-stories --unit-id <unit_id>`。
   - 若為**新主線/公會/活動/露娜塔劇情**：若需抓取該話對白，可執行單話同步指令 `python -m pipeline.fetch sync-episode --story-id <story_id>`。
   - 若為**第 3 部分支劇情**：需在 `branch_stories.json` 補充副標題元數據。

---

## 四、 運維狀態判讀等級 (Update Success Levels)

- 🟢 **GREEN (完整確認發布)**：CDN 探測成功且版號確認、目標劇本全數就緒、來源變更已 Commit/Push 至 main、驗證門禁 100% 通過。
- 🟡 **YELLOW (陳舊/降級成功警示)**：本地驗證通過，但 CDN 探測超時（可能使用舊 DB 打包）或目標新劇本未在追蹤清單中。
- 🔴 **RED (嚴重阻斷失敗)**：資料庫下載失敗、劇本檔案缺失、或全量驗證門禁未通過（Exit Code 1）。

---

## 五、 標準日常更新與可重現發布流程 (Authoritative Reproducible Release Path)

### 階段一：來源資料同步與審查 (Source Synchronization Phase)

#### 步驟 1：對齊 main 並建立資料更新分支
```bash
git switch main
git pull --ff-only
git switch -c data/update-YYYYMMDD
```

#### 步驟 2：執行零副作用 Dry-Run 模擬
```bash
python update_story_map.py --dry-run
```

#### 步驟 3：執行本地增量更新與決定性打包 (不發布)
```bash
python update_story_map.py
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

git commit -m "data: update story map data (TruthVersion 006xxxxx)"
```

#### 步驟 7：推送來源分支並合併至 main (Source Push Gate)
```bash
git push -u origin data/update-YYYYMMDD
# 經審查無誤後 Fast-Forward 合併至 main：
git switch main
git merge --ff-only data/update-YYYYMMDD
git push origin main
```

---

### 階段二：決定性發布階段 (Deterministic Release Phase — Zero Upstream Mutation)

#### 步驟 8：確認 Working Tree 與 Authoritative Main SHA
```bash
git status --short
# 確保除未追蹤之研究資料外，無任何意外修改的 tracked source 檔案
git rev-parse HEAD
git rev-parse origin/main
# 兩者必須完全一致！
```

#### 步驟 9：純本地決定性建置 (Rebuild Dist strictly from committed main)
```bash
python -m pipeline.bundle
python -m pipeline.validate
```

#### 步驟 10：純發布至生產環境 (Deploy-Only)
> [!IMPORTANT]
> **請使用純發布指令 `python -m pipeline.deploy`，嚴禁在已合併 main 後再次執行 `update_story_map.py --deploy`**（避免觸發二次上游同步破壞可重現性）。

```bash
python -m pipeline.deploy
```

#### 步驟 11：線上 Smoke Test 驗收
* 檢查 GitHub Pages 部署狀態，確認線上網頁運作正常。

---

## 六、 發布一致性契約與異常復原 (Release Consistency & Recovery)

### 發布一致性契約 (Release Consistency Invariant)
> **正式生產環境 (`gh-pages`) 上的部署產物，必須 100% 能由主倉庫 (`main`) 上的已審查提交 SHA 決定性重現，且來源提交與線上發布之間嚴禁發生任何上游突變。**

### 異常復原指南
- **情境 A (來源已 Push，但 Deploy 失敗)**: **`SAFE`**。Main 分支已安全保留最新資料狀態。排查網路或部署目錄鎖定後，重新執行 `python -m pipeline.deploy` 即可。
- **情境 B (Deploy 成功，但來源 Push 失敗)**: **`INCONSISTENT (不合規狀態)`**。此時線上產物領先於來源 main，不可視為發布完成！必須立即排除來源倉庫的網路或權限問題，完成 `git push origin main`，恢復 main 與 production 的嚴格對齊。
- **情境 C (來源已提交，但誤跑 full updater 導致來源再度變更)**: **`STOP / DO NOT DEPLOY`**。執行 `git status --short`，若發現 tracked source 與 `origin/main` 不一致，**禁止直接發布**！應安全捨棄非預期變更，或將其視為全新更新重新建立分支審查。
