# PCRD Story Map — Acquisition Coverage & Freshness Policy Investigation (Phase C2 Final Consistency)

> [!IMPORTANT]
> **本報告為 PCRD Story Map 資料管線 (Pipeline v1) 之上游新鮮度狀態機 (Freshness Policy)、必備劇本覆蓋集合 (Required Coverage Sets) 與通用劇本抓取原語契約 (Generic Acquisition Primitive) 之完整調研報告 (Investigation Only)**。未修改任何執行時代碼。

---

## 1. Executive Summary

本調研動態對齊了 Repository 當前資料庫與元數據之全量數據：
- **權威覆蓋集合對齊**：主線 (483)、公會 (54)、露娜塔/系統 (253)、追蹤角色 (6 角色 / 24 話)、分支 (63 話) 與新形式活動 (254 話)。
- **必備集合聯集總數 (Required Total)**: **1131 話** (集合間重疊: Tracked 與 story_detail 重疊 20 話；Branch 與 Main 重疊 0 話)。目前必備劇本缺失數為 **0 話** (100% 就緒)。
- **可選歷史活動集合 (Optional Historic)**: **2044 話**，缺失 **17 話** (精確對齊 Validator 的 17 話警告)。
- **覆蓋政策狀態 (Coverage Policy Status)**: 必備集合為 **`DEFINED`**，可選集合為 **`DEFINED`** (未知話數 Unknown = 0)。
- **新鮮度狀態機 (Freshness State Model)**：推薦採用**混合降級策略 (Hybrid / Explicit Degraded Mode)**，自動發布必須通過新鮮度確認或明確的覆蓋機制。
- **通用抓取原語契約 (Generic Acquisition Primitive)**：定義了輕量級 `StoryFetchResult` 結構，解耦多媒體下載與縮圖修改副作用，並支援 Manifest 一次性重用批次同步。

---

## 2. Freshness State Model (新鮮度狀態機模型)

| 狀態名稱 (State) | 觸發條件 (Entry Condition) | 是否允許本地更新？ | 是否允許生產發布？ | 運維處理行動 |
| :--- | :--- | :--- | :--- | :--- |
| **`CONFIRMED_CURRENT`** | remote_tv probe succeeds and matches local_tv | `YES` | `YES` | None (Pipeline verified upstream is current) |
| **`UPDATE_AVAILABLE`** | remote_tv probe succeeds and remote_tv > local_tv | `YES` | `NO` | Execute update (Download new DB & sync) |
| **`UPDATED_SUCCESSFULLY`** | New redive_tw.db downloaded and version_history.json atomically saved | `YES` | `YES` | Review source diff & commit before deploy |
| **`REMOTE_UNREACHABLE`** | remote_tv probe fails due to network error/timeout while local DB exists | `YES` | `NO` | Check network; allow local dry-run / bundle, but block auto-deploy without explicit override |
| **`LOCAL_STATE_MISSING`** | Local redive_tw.db does not exist and remote_tv probe fails | `NO` | `NO` | Fix network to download base DB |
| **`UPDATE_FAILED`** | DB download or dialogue JSON bundle decryption fails | `NO` | `NO` | Inspect logs and retry update |

---

## 3. Freshness Policy Options & Evaluation

| 策略選項 | 行為模式 | 優點 | 缺點 / 風險 | 評估結論 |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy A: Current Warning-Only Model** | Remote probe failure logs [WARN] and continues pipeline using local DB without blocking deploy | High resilience for offline/local development | Stale-success risk: may deploy outdated site without operator awareness (MEDIUM (Production freshness uncertainty)) | **REJECT AS DEFAULT FOR DEPLOY** |
| **Strategy B: Strict Fail-Closed Model** | Remote probe failure immediately halts pipeline with exit code 1 | Zero stale deploy risk | Completely breaks offline bundling, local testing, and air-gapped workflows (LOW freshness risk, HIGH usability friction) | **TOO RIGID FOR LOCAL WORKFLOWS** |
| **Strategy C: Hybrid / Explicit Degraded Mode (RECOMMENDED)** | Local update/dry-run allows degraded mode with explicit warning; Auto-deploy enforces confirmed freshness unless explicitly overridden via explicit override mechanism | Perfect balance: offline bundle works seamlessly, while production deployment is strictly protected | Requires clean separation between local build and deploy validation (VERY LOW) | **RECOMMENDED POLICY** |

---

## 4. Authoritative Coverage Snapshot (權威覆蓋現況快照)

- **本地數字劇本總數 (Local Present)**: **`9033`** 篇
- **資料庫 `story_detail` 總數**: **`2854`** 筆
- **追蹤角色必備話數 (Tracked Characters via helper)**: **`24`** 話 (6 個追蹤角色)
- **主線必備話數 (Main Required from story_detail)**: **`483`** 話
- **公會必備話數 (Guild Required from story_detail)**: **`54`** 話
- **露娜塔/系統必備話數 (Tower/System Required from story_detail)**: **`253`** 話
- **第 3 部分支補充話數 (Branch Expected from branch_stories.json)**: **`63`** 話
- **新形式活動話數 (Extra Events from extra_events.json)**: **`254`** 話
- **產品必備劇本聯集總數 (Total Product Required Union)**: **`1131`** 話
- **可選歷史劇本總數 (Optional Historic Set)**: **`2044`** 話
- **未歸類之預期劇本 (Unknown Expected IDs)**: **`0`** 話
- **必備劇本缺失數 (Missing Required)**: **`0`** 話 (✅ 核心必備 100% 就緒)
- **可選劇本缺失數 (Missing Optional)**: **`17`** 話 (精確對齊 Validator 警告: 17 話)
- **本地非 `story_detail` 劇本數量 (Local Not in story_detail)**: **`6196`** 篇
- **未在任何已知權威來源之本地劇本 (Unknown Local Extras)**: **`5875`** 篇

### 集合重疊分析 (Set Overlaps)
- `branch_stories` ∩ `story_detail(main)`: **0** 話
- `extra_events` ∩ `story_detail`: **0** 話
- `tracked_characters` ∩ `story_detail(character)`: **20** 話

> [!NOTE]
> **Validator 警告來源**：Validator 檢驗 `db_story_ids ∪ extra_events ∪ branch_stories - local_present`，產生的 17 話缺失全部落入可選歷史劇本集合中 (14 話日版/非追蹤角色 + 3 話特殊話數)，必備劇本無任何遺漏。

---

## 5. Generic Story Download Primitive Contract (通用抓取原語契約)

- **函式簽名**: `fetch_story_json_by_id(story_id: int, manifest_hash_map: Optional[Dict[int, str]] = None, timeout: int = 15) -> StoryFetchResult`
- **回傳型別**: `StoryFetchResult (Typed Data Structure)`
  - 欄位: `story_id: int`, `status: 'OK' | 'HASH_NOT_FOUND' | 'NETWORK_ERROR' | 'PARSE_ERROR' | 'WRITE_ERROR'`, `dialogues: Optional[List[Dict[str, Any]]]`, `dialogue_count: int`, `hash: Optional[str]`, `written_path: Optional[str]`, `error_message: Optional[str]`

### 原語行為保證 (Behavior Guarantees)
- 1. NO sys.exit() calls — returns structured error result or raises typed exception
- 2. NO report file side effects — purely in-memory execution
- 3. NO media downloading (M4A voice, background WebP, CG WebP) — handles JSON dialogues only
- 4. NO thumbnail or metadata mutation — pure acquisition primitive
- 5. Reuses provided manifest_hash_map when batching to eliminate redundant manifest downloads

---

## 6. Batch Acquisition Failure Policy

- **Manifest 下載失敗**: `ABORT_WHOLE_BATCH (Cannot resolve bundle hashes without manifest)`
- **單話 Hash 缺失**: `COLLECT_FAILURE (Record as HASH_NOT_FOUND, continue remaining batch)`
- **網路或解析異常**: `COLLECT_FAILURE (Record as ERROR, continue remaining batch)`
- **寫入異常**: `COLLECT_FAILURE (Record as WRITE_ERROR, continue remaining batch)`
- **批次結論門禁**: `If any REQUIRED story failed -> Overall Exit Code 1; If only OPTIONAL failed -> Log warning & Exit Code 0`
- **安全重跑冪等性**: `REQUIRED_DESIGN_PROPERTY (TO_BE_VERIFIED_IN_IMPLEMENTATION)`

---

## 7. Key Questions & Direct Answers

### Q1. 管線目前能否證明上游新鮮度？
**【答】不能 (NO)**。目前探測失敗僅記錄 Warning，本地有 DB 即會以舊資料完成打包，無法向運維者強保證新鮮度已確認。

### Q2. 新鮮度未確認時，是否應允許自動生產發布？
**【答】不應允許 (NO / EXPLICIT OVERRIDE ONLY)**。生產發布應強制要求 `CONFIRMED_CURRENT` 或 `UPDATED_SUCCESSFULLY`，僅在帶有專用覆蓋機制時允許應急發布。

### Q3. 權威更新管線目前能否偵測到所有相關缺失的劇本？
**【答】不能 (NO / PARTIAL)**。目前僅依賴 `tracked_characters.json` 掃描已追蹤角色，對新主線或公會/活動缺失話數無法自動對比。

### Q4. 權威的必備故事集合 (Required-Story Set) 目前是否已定義？
**【答】已建立精確定義模型 (`DEFINED`)**。涵蓋主線 (483)、公會 (54)、露娜塔 (253)、追蹤角色 (24)、分支 (63) 與新活動 (254)，聯集共 1131 話，本地缺失數為 0 話。

### Q5. 單純的「DB 減去本地」差集是否足夠作為下載依據？
**【答】不足夠 (NO)**。直接差集會嘗試下載歷史不可用話數導致錯誤，必須經過 Required 集合規則過濾。

### Q6. 現有 `sync-episode` 是否適合直接用於批次抓取？
**【答】不適合 (NO)**。因其包含語音、圖片下載與縮圖修改等重型副作用，且每話重複下載 Manifest，效率極低。

### Q7. 最小且最有價值的實作範圍是什麼？
**【答】FRESHNESS STATUS + GENERIC STORY JSON PRIMITIVE + READ-ONLY COVERAGE REPORT**（建立新鮮度狀態與門禁，提取輕量單話/批次 JSON 抓取原語，並輸出覆蓋報告；在未完全實施自動同步前不冒進開啟 auto-sync）。

### Q8. 這是否需要修改前端代碼？
**【答】不需要 (NO)**。前端由 SQLite 自動驅動，所有改進純屬後端資料管線架構。

---

## 8. Final Recommendation

> [!TIP]
> **C2 調研結論：PASS (已成功建立數值 100% 一致之覆蓋模型、新鮮度狀態機流轉與輕量抓取原語契約，建議後續進入實作階段)**。
