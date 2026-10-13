# 公主連結劇情地圖（Story Map）全系統審查報告與跨 AI 改版交接紀錄（2026-10-13）

```text
STATUS: ACTIVE REVIEW & HANDOVER RECORD
BASE MAIN COMMIT: 9c6b221e95b37daf1a293f8adb593a96adcb5afc
CURRENT SLICE BRANCH: fix/avatar-and-media-edge-cases
DEPLOYED GH-PAGES HEAD: 810a60483277aa0e9813bbd0e8b45fd863c4141a (TruthVersion: 00610018)
```

本文件供共同維護本專案之所有 AI 智能體（Antigravity、GPT-6、Codex、Claude 等）與開發者參考，記錄 2026-10-13 完成之改版、全系統唯讀審查發現（依循 Evidence-Calibrated Research Mode），以及分階段修復路線圖（3-Slice Roadmap）。

---

## 一、 2026-10-13 已合併至 `main` 之改版紀錄

### 1. UX 細節修正與重試安全加固（Commit `79b069c22052a032a874c850beded4b74f832340`）
* **分支**：`fix/story-map-ux-refinements`（已快轉合併至 `main`，並部署至 `gh-pages` `810a60483277aa0e9813bbd0e8b45fd863c4141a`）
* **變更內容**：
  1. **`dashboard/chara-modal.js`**：
     - `updateAppearancesSection()` 重新渲染時，完整保留搜尋輸入框之 focus、游標位置（`selectionStart` / `selectionEnd`）、目錄捲動位置（`scrollTop`）及使用者手動展開／收合之 `<details>` 節點狀態。
     - 將重試按鈕獨立於 `.chara-appearance-search-status` 之外（置於 `.chara-appearance-search-meta` 容器內），確保輸入或清空搜尋文字時不會覆寫刪除重試按鈕。
     - 將重試事件改為透過 `data-chara-name` 屬性傳遞（`this.getAttribute('data-chara-name')`），消除含單引號／雙引號角色名稱在 inline `onclick` 字串拼接時的語法錯誤與注入風險，且不改變角色 identity key。
  2. **`dashboard/story-data-service.js` & `dashboard/map.js`**：
     - 新增 `StoryDataService.hasMetadataFailed()` 狀態查詢。
     - 當 `official_story_metadata.json` 載入失敗時，`resolveAppearanceStoryMeta()` 不再無限停留於「載入名稱中…」，而是轉換為明確之 `名稱載入失敗（ID: {storyId}）`（維持 `canNavigate: false`、`hasFailed: true`），並提供 `QuestMapModule.retryCharaMetadata(charaName)` 安全重試。
  3. **`dashboard/dialogue-view.js`**：
     - 將 `renderError()` 中的開發者 Python CLI 維護指令移除，改為一般網站訪客易讀之網路連線提示與「🔄 重新載入」按鈕。
  4. **回歸測試**：`tests/test_chara_modal.js`（新增 Test 14～18）、`tests/test_dialogue_view.js`（更新 Test 8）。

### 2. CDN 狀態驗證記錄（Commit `3dfa127efd0fd0c1fbc7d67abf7921e7c1ebca1d`）
* 正式部署期間執行標準 Freshness Gate 與 Validate Gate，確認 `TruthVersion` 維持 `00610018`，並將驗證時間與雜湊指紋記錄於 `dashboard/versions/version_history.json` 與 `tools/db_update_report.json`。

### 3. GitHub Actions CI `UnityPy` 依賴修復（Commit `d1f5e368e11a1715d6288e267ea266db47021204`）
* **分支**：`fix/ci-unitypy-dependency`（已快轉合併至 `main`，GitHub Actions Run `#37722470560` 全數 PASS）
* **根因與修復**：`pipeline/__init__.py` 會提前匯入 `pipeline.fetch` 進而載入 `UnityPy`，而 `.github/workflows/ci.yml` 原先未安裝 Python 套件導致 `pytest` 階段拋出 `ModuleNotFoundError: No module named 'UnityPy'`。已在 `.github/workflows/ci.yml` 補上 `pip install UnityPy==1.25.3`。

### 4. Slice 1：閱讀器、登場目錄第 3 部分支歸類與淺色主題對比修復（Commit `67730a4475a36246ab59aa1a54a7a233851d7620`）
* **分支**：`fix/reader-and-branch-ux`（經 GPT-6 審查通過並已快轉合併至 `main`，GitHub Actions Run `#38357316451` 全數 PASS）
* **變更內容**：
  1. **`dashboard/dialogue-view.js` & `dashboard/speaker-view.js`**：修正淺色主題下殘留深色主題的半透明白字（改用 `var(--text-secondary)` / `var(--text-muted)`）；移除旁白與選擇肢無效之 `showCharaModal("")` 點擊與手型游標；角色頭像與人名點擊補上 `event.stopPropagation()`；修正 `hasStillInList` 排除不渲染 DOM 的 `still_id === 'end'` 標記，恢復片尾 `currentStoryObj.still_id` 自動追加（並補齊已有有效 `still` 時不重複追加之反向測試）。
  2. **`dashboard/map.js`**：空對白話數與載入錯誤時在當前權杖下清除並隱藏 `#chara-badges-bar`；`resolveAppearanceStoryMeta()` 針對 `story.isBranch === true && part === 3 && groupId > 2200 && groupId < 2300` 推導 `第${groupId - 2200}章`，同時保留一般非分支主線之「序章／幕間」判定。
  3. **`dashboard/style.css`**：行動端 `@media (max-width: 768px)` 下將 `.game-dialogue-header` 之 `top` 設為 `0`。

### 5. Slice 2：管線門禁、版本狀態原子晉升與 CI 強化（Commit `9c6b221e95b37daf1a293f8adb593a96adcb5afc`）
* **分支**：`fix/pipeline-and-validation-gate`（經 GPT-6 審查通過並已快轉合併至 `main`，GitHub Actions Run `#38361428304` 全數 PASS）
* **變更內容**：
  1. **`dashboard/data/db_info.json`**：同步更新 Source 端之雜湊與大小，對齊實際 `redive_tw.db`（`db_version: "hash_8f2a5555b328"`、`tw_size: 2220032`、`metadata_version: "2769c249bdd4"`）。
  2. **`pipeline/validate.py`**：補齊 6 個核心前端 JS 檔案之存在性檢查，並對 Dist 12 個外部 JS 與 `style.css` 執行版本雜湊引用校驗。
  3. **`pipeline/update.py`**：消除 `check_and_sync_upstream()` 提前推進版本紀錄的漏洞（GPT-6 Review P1），統一由 `run_pipeline_update()` 步驟 4.1 在全量驗證成功後原子晉升 TruthVersion 與指紋；支援相同版號指紋變更推進，並在寫入失敗時嚴格回傳 `1` 阻斷發布流程。
  4. **CI 測試與離線隔離**：重構三大更新管線政策測試（`test_update_pipeline_c2_implementation`、`test_content_driven_update_policy`、`test_direct_sonet_db_pipeline_integration`）並在 `.github/workflows/ci.yml` 補上獨立離線測試步驟（GPT-6 Review P2）。

### 6. Slice 3：角色頭像邊界解析、登場清單 NPC 本地頭像支援與媒體生命週期強化（分支 `fix/avatar-and-media-edge-cases`）
* **分支**：`fix/avatar-and-media-edge-cases`（READY FOR GPT-6 REVIEW）
* **變更內容**：
  1. **`dashboard/avatar-service.js`**：
     - 修復 `cleanName()`：調整順序為先完整移除全形與半形括號說明語（消除「栞（初音＆栞）」殘留未閉合括號），再移除後綴「的聲音」，並以否定後行斷言 `/[、＆&]|(?<!日)和|與/` 分割並列發言人，徹底保護「日和」、「春咲日和」本名不被誤截斷為單字「日」。
     - 修復 `getAvatarHtml()`：傳遞原始 `charaName` 給 `getUnitId()`，確保「佩可（現實）」等現實篇章換裝括號名稱能被優先精準解析為對應 Unit ID。
  2. **`dashboard/speaker-view.js`**：
     - `renderSpeakerCard()`：優先使用 `avatarService.getAvatarHtml(realName, speakerAvatars)`，享有完整本地 NPC `.png` 與 6 級 CDN fallback 鏈；降級路徑（`getUrlCandidates`）優先選取 `.png` 並補上 `this.onerror=null` 防止循環。
  3. **`dashboard/media-service.js`**：
     - `getVoiceCandidates()`：以 `voiceName.match(/\d{7}/)` 安全抽取 7 位數字 groupId，解決固定 7 字元切片脆弱性。
     - `_playVoiceSequential()`：在 `onStarted` 時清理 `this._resumePendingCandidate = null`，避免播放中重複觸發。
     - `openStillPopup()`：在綁定鍵盤事件前先清理舊的 `_stillPopupKeyHandler`，防止重複開啟事件監聽器洩漏。
  4. **回歸測試與 CI**：
     - `tests/test_avatar_service.js`（新增 Test 19 覆蓋「日和」、括號內＆、連接詞分割等情境）。
     - `tests/test_media_service.js`（新增 Case 6 抽取非標準 voice 前綴、Case 7 重複開啟 still 彈窗之監聽器清理）。
     - `tests/test_speaker_view.js`（新建專屬單元測試，驗證 `renderSpeakerCard`、NPC `.png` 優先級與排序/過濾契約）。
     - `.github/workflows/ci.yml`（新增 `Run Speaker View Tests` 步驟）。

---

## 二、 全系統深度審查發現清單（System Review Findings）

以下為針對全系統進行唯讀審查後，按模組與證據等級彙整之問題清單：

### A. 功能與邏輯正確性（Functional & Logic Bugs）
1. **`[VERIFIED]` `AvatarService.cleanName()` 誤截斷含「和／與」的角色本名（已於 Slice 3 修復）**
   - 位置：`dashboard/avatar-service.js` `cleanName()`（`#L828-L834`）與 `getAvatarHtml()`（`#L901-L904`）。
   - 修復：調整為先完整剝除全形／半形括號說明語（消除「栞（初音＆栞）」未閉合括號），再移除後綴「的聲音」，並以否定後行斷言 `/[、＆&]|(?<!日)和|與/` 分割並列發言人，徹底保護「日和」、「春咲日和」本名不被誤截斷為單字「日」；`getAvatarHtml()` 傳遞原始 `charaName` 給 `getUnitId()` 確保換裝名稱優先 Exact 解析。
2. **`[VERIFIED]` 第 3 部分支劇情在角色登場目錄中被歸入「其他」（已於 Slice 1 `67730a44` 修復並合併）**
3. **`[VERIFIED]` 空對白話數與對白載入失敗時，`#chara-badges-bar` 卡在載入中（已於 Slice 1 `67730a44` 修復並合併）**
4. **`[VERIFIED]` `SpeakerView.renderSpeakerCard` 繞過 `AvatarService` 導致 NPC `.png` 頭像破圖（已於 Slice 3 修復）**
   - 位置：`dashboard/speaker-view.js#L64-L72`。
   - 修復：優先呼叫 `avatarService.getAvatarHtml(realName, speakerAvatars)` 取得包含本地 NPC `.png` 與 6 級 CDN fallback 鏈之頭像；降級路徑（`getUrlCandidates`）優先選取 `.png` 並補上 `this.onerror=null` 防止死循環。
5. **`[VERIFIED]` `DialogueView` 旁白／選擇肢無效點擊、事件冒泡與 `'end'` 標記阻斷片尾 CG（已於 Slice 1 `67730a44` 修復並合併）**
6. **`[VERIFIED]` `MediaService` 語音路徑固定 7 字元切片與 `_resumePendingCandidate` 殘留（已於 Slice 3 修復）**
   - 位置：`dashboard/media-service.js#L25-L36`、`#L181-L209`、`#L371-L380`。
   - 修復：以 `voiceName.match(/\d{7}/)` 支援非標準前綴語音之 7 位 groupId 抽取；在播放開始時清理 `_resumePendingCandidate` 避免重複觸發；在重複開啟 still 彈窗前清理舊的鍵盤 Escape 監聽器。

### B. 本地開發與打包環境對等性、管線門禁與 CI（Pipeline, Gate & CI — 已於 Slice 2 處理）
1. **`[VERIFIED]` Source 端 `dashboard/data/db_info.json` 與 `dist_story_map/data/db_info.json` 脫節（已於 Slice 2 修復）**
   - 位置：`dashboard/data/db_info.json`。
   - 現象与設計決策：`bundle_story_map()` 依循 D2 契約將 `dashboard/` 視為唯讀來源並僅寫入 `dist_story_map/data/db_info.json`。但受 Git 追蹤之 `dashboard/data/db_info.json` 仍停留於舊版 `tw_size: 14823424`（實際 `redive_tw.db` 為 `2220032` bytes）且缺少 `metadata_version`，導致直接開啟 `dashboard/story_map.html` 時觸發 `matchesRelease()` 大小不符。已於 Slice 2 將 `dashboard/data/db_info.json` 同步對齊為當前 `db_version: "hash_8f2a5555b328"`、`tw_size: 2220032`、`metadata_version: "2769c249bdd4"`，同時保持 `bundle.py` 不污染 Source 工作樹。
2. **`[VERIFIED]` `pipeline/validate.py` 漏檢 6 個核心前端 JS 檔案與 Dist 雜湊（已於 Slice 2 修復）**
   - 位置：`pipeline/validate.py#L1118-L1138`、`#L1345-L1366`。
   - 修復內容：在 `required_files` 補齊 `speaker-view.js`、`chara-modal.js`、`dialogue-normalizer.js`、`media-service.js`、`dialogue-view.js`、`auto-voice-controller.js`；並在 `check_dist=True` 區段對 `style.css` 與全部 12 個外部 JS 檔案執行 `validate_content_hash_reference` 驗證（同步更新 `tests/test_story_data_service.py` `test_25` 之 mock 面板）。
3. **`[VERIFIED]` `pipeline/update.py` 在 DB 真實更新（`UPDATED_SUCCESSFULLY`）或相同內容（`NO_CHANGE`）時的版本狀態與指紋晉升安全性（已於 Slice 2 修復）**
   - 位置：`pipeline/coverage.py` `FreshnessResult`、`pipeline/update.py#L235-L279`、`#L460-L476`。
   - 修復內容：
     1. **修復 `NO_CHANGE` 提前寫入漏洞（GPT-6 Review P1）**：移除 `check_and_sync_upstream()` 在 `update_db()` 回傳 `applied=False` 時提前呼叫之 `save_truth_version_state()`；將指紋妥善保存在 `FreshnessResult.fingerprint`，統一交由 `run_pipeline_update()` 步驟 4.1，在 Asset Completeness、Bundle 與全量 Validate 門禁全部成功後才原子晉升版本狀態與指紋。
     2. **支援「同版號、指紋變更、DB 內容不變」安全推進指紋**：在步驟 4.1 中若 `freshness.fingerprint` 存在，即使 `remote_version == local_version` 依然推進新指紋，避免下次更新重複下載。
     3. **門禁失敗不晉升 & 寫入失敗嚴格阻斷**：全量門禁失敗時 `version_history.json` 完全保持不變；步驟 4.1 正式寫入若失敗（`not promoted`）則嚴格回傳 `1` 阻斷部署流程。
4. **`[VERIFIED]` `tests/test_update_pipeline_c2_implementation.py` 測試漂移與 CI 測試覆蓋缺口（已於 Slice 2 修復）**
   - 位置：`tests/test_update_pipeline_c2_implementation.py`、`tests/test_direct_sonet_db_pipeline_integration.py`、`.github/workflows/ci.yml`。
   - 修復內容：
     1. 更新 `test_06` 以 `UPDATE_DOWNLOADED_UNCONFIRMED` 驗證未確認新鮮度之發布阻斷與 `--allow-unconfirmed-freshness` 覆蓋；重構 `test_13` 與 `test_14` 補齊 `probe_third_party_reference`、`discover_cdn_candidate_snapshots` 離線 mock 與指紋晉升斷言。
     2. 新增 `test_16`（不同版號相同內容不提前寫入、驗證失敗不晉升、全流程成功才晉升）、`test_17`（相同版號指紋變更在驗證成功後推進新指紋）、`test_18`（步驟 4.1 寫入失敗阻斷流程且不部署）。
     3. 在 `test_direct_sonet_db_pipeline_integration.py` `test_01` & `test_07` 補齊離線 mock，確保完全無外網請求。
     4. **補強 GitHub Actions CI 覆蓋（GPT-6 Review P2）**：在 `.github/workflows/ci.yml` 補上獨立離線測試步驟 `Run Update Pipeline & Content-Driven Policy Hermetic Tests`，納入 `test_update_pipeline_c2_implementation`、`test_content_driven_update_policy` 與 `test_direct_sonet_db_pipeline_integration`。

### C. UI/UX 樣式與 DOM 轉義（UI/UX & Security）
1. **`[VERIFIED]` 淺色主題下殘留深色主題的半透明白字（已於 Slice 1 `67730a44` 修復並合併）**
2. **`[VERIFIED]` 行動端 `.game-dialogue-header` Sticky Top 64px 懸空間隙（已於 Slice 1 `67730a44` 修復並合併）**
3. **`[VERIFIED]` `dashboard/characters.js` 與局部未轉義 `innerHTML`（待於後續 Slice 處理）**

---

## 三、 分階段修復路線圖與執行狀態（3-Slice Roadmap）

| 階段 | 分支名稱 | 狀態 | 核心目標與邊界 |
| :--- | :--- | :---: | :--- |
| **Slice 1** | `fix/reader-and-branch-ux` | **已合併至 `main` (`67730a44`)** | 修復 `dialogue-view.js`、`speaker-view.js` 淺色主題白字、移除旁白／選擇肢無效 `showCharaModal("")`、角色頭像／人名點擊 `stopPropagation`、排除 `'end'` 標記對片尾 CG 的阻斷、空話數／錯誤時隱藏 `#chara-badges-bar`、第 3 部分支劇情登場目錄章節歸類（限定 `story.isBranch === true`）、手機端 `.game-dialogue-header` `top: 0`。 |
| **Slice 2** | `fix/pipeline-and-validation-gate` | **已合併至 `main` (`9c6b221e`)** | 同步更新 Source `dashboard/data/db_info.json`、補齊 `pipeline/validate.py` 6 個前端 JS 與 12 個外部 JS Dist 雜湊檢查、消除 `check_and_sync_upstream()` 提前寫入版本紀錄、統一於步驟 4.1 全量驗證成功後原子晉升 TruthVersion 與指紋（含同版號指紋變更與寫入失敗阻斷）、在 `.github/workflows/ci.yml` 補齊三大核心管線政策離線測試。 |
| **Slice 3** | `fix/avatar-and-media-edge-cases` | **已完成待審 (READY FOR GPT-6 REVIEW)** | 修復 `AvatarService.cleanName()`「日和」截斷與括號順序（保護本名含「和」與 Exact-ID-First 契約）、`SpeakerView` NPC 本地 `.png` 頭像支援與 6 級 fallback 鏈、`MediaService` 7 位 groupId 抽取與 `_resumePendingCandidate` / `openStillPopup` 鍵盤監聽器清理，新建 `tests/test_speaker_view.js` 並納入 CI。 |

---

## 四、 跨 AI 協作保護禁區與不變量（Guardrails for Other AIs）

1. **Git 與工作區安全**：
   - **嚴禁修改或刪除兩份既有 Stash**：
     - `stash@{0}: On feat/npc-catalog-pilot: wip: npc pilot before appearance directory work`
     - `stash@{1}: On fix/rurui-home-sync: wip: local uncommitted investigations`
   - **嚴禁直接手動修改 `dist_story_map/.git`**：所有發布產物同步與部署必須透過 `python update_story_map.py --deploy` 執行。
   - **OneDrive 環境注意**：本倉庫位於 OneDrive 同步目錄下，若偶發 `.git/index` 時間戳或暫存狀態與 `HEAD` 反向漂移（`git status` 出現成對 `MM` 但 `git diff HEAD` 為空），請先以 `git diff HEAD` 確認工作樹無變更後執行 `git reset HEAD` 同步索引，切勿盲目執行 `git checkout --` 或 `git reset --hard`。
2. **核心契約不變量**：
   - **Canonical Story Navigation**：不得破壞 `ReaderNavigation` 的深連結（`#story=...&line=...`）、同頁書籤與進度保存契約（驗證：`node tests/test_reader_navigation.js`、`node tests/test_reader_navigation_contract.js`）。
   - **Avatar Exact-ID-First**：顯式 `unit_id` 永遠優先於名稱推斷與 `realityAvatarMap`（驗證：`node tests/test_avatar_exact_id_resolution.js`）。
   - **AUTO 語音狀態機**：不得破壞 `AutoVoiceController` 與 `MediaService` 的單飛權杖（Token）與世代清理機制（驗證：`node tests/test_auto_voice_controller.js`、`node tests/test_voice_lifecycle_hardening.js`）。
