# PCRD Story Map — Update Pipeline C2 Minimal Implementation Report

> [!IMPORTANT]
> **本報告記錄 PCRD Story Map 資料管線 (Pipeline v1) 之 Phase C2 最小安全實作成果 (含資料庫新鮮度證明與鏡像防滯後修正)**。
> 實作落實了三大核心保證：新鮮度狀態與發布防禦門禁 (Freshness Gate & Mirror Lag Defense)、通用單話對白 JSON 抓取原語 (Generic JSON Fetch Primitive) 以及具備來源健康度檢驗的唯讀劇本覆蓋率守衛 (Read-Only Coverage Guard & Integrity Gate)。

---

## 1. 實作範圍 (Scope Summary)

本階段將 C2 調研成果轉化為 Production Runtime 代碼，精準實作以下項目：
1. **Freshness Contract & Mirror Lag Defense Gate**：
   - 建立 `FreshnessResult` 結構化狀態模型 (`CONFIRMED_CURRENT`, `UPDATE_AVAILABLE`, `UPDATED_SUCCESSFULLY`, `UPDATE_DOWNLOADED_UNCONFIRMED`, `REMOTE_UNREACHABLE`, `LOCAL_STATE_MISSING`, `UPDATE_FAILED`)。
   - 嚴格分離 **So-net CDN 探測 (TruthVersion)** 與 **第三方鏡像 DB 下載 (wthee)** 之信任邊界；在缺乏直接版本證明時誠實標記為 `UPDATE_DOWNLOADED_UNCONFIRMED`，不虛假推進 `version_history.json`。
   - `update_story_map.py --deploy` 預設阻斷未確認新鮮度或鏡像未證實之版本發布，支援顯式應急覆蓋旗標 `--allow-unconfirmed-freshness`。
2. **Generic Story JSON Primitive**：
   - 提取輕量單話對白 JSON 抓取函式 `fetch_story_json_by_id(story_id, manifest_hash_map)`。
   - 結構化結果 `StoryFetchResult`，支援 Manifest 一次性解析快取 `load_story_manifest_hash_map()`。
   - 零 `sys.exit()`、零多媒體下載、零縮圖/報告修改副作用，採用原子寫入 (`.tmp` -> `replace`)。
   - 提供 CLI 子命令：`python tools/pcrd_fetch.py fetch-story --story-id <id>`。
3. **Read-Only Story Coverage Guard & Integrity Gate**：
   - 模組 `pipeline/coverage.py` 提供 `analyze_coverage()`，計算必備集合 (Required Union)、可選歷史集合 (Optional) 與未知分類 (Unknown)。
   - 結構化分析完整性狀態 (`analysis_status`: `VALID` / `DEGRADED` / `INVALID`) 與來源健康度 (`source_status`)，不吞沒任何權威來源錯誤。
   - 政策狀態嚴格判定：只有在 `analysis_status == VALID` 且 `unknown_expected == 0` 時，政策狀態才標記為 `DEFINED`；若 `DEGRADED` 則為 `PARTIAL`；若 `INVALID` 則為 `UNRESOLVED`。
   - 提供唯讀 CLI 入口：`python update_story_map.py --coverage`。
   - 若檢測到必備話數缺失 (`missing_required > 0`)，管線立即安全中止 (Fail-Stop) 並引導使用 `fetch-story` 補齊，**不執行自動 bulk download**。
   - 若覆蓋率分析降級 (`DEGRADED` / `INVALID`) 或存在未歸類話數 (`unknown_expected > 0`)，**自動生產發布立即強制阻斷 (BLOCK DEPLOY)**，且 `--allow-unconfirmed-freshness` 無法繞過此門禁。

---

## 2. 核心契約與介面 (Core Contracts & Interfaces)

### 2.1 新鮮度判定契約 (Freshness Evaluation)
- 模組位置: `pipeline/coverage.py`
- 函式: `evaluate_freshness(remote_tv: Optional[str], local_tv: Optional[str], db_exists: bool) -> FreshnessResult`
- 欄位:
  - `status: str` (狀態代碼: `CONFIRMED_CURRENT`, `UPDATE_AVAILABLE`, `UPDATED_SUCCESSFULLY`, `UPDATE_DOWNLOADED_UNCONFIRMED`, `REMOTE_UNREACHABLE`, `LOCAL_STATE_MISSING`, `UPDATE_FAILED`)
  - `remote_version: Optional[str]`
  - `local_version: Optional[str]`
  - `confirmed: bool` (是否確認線上一致)
  - `update_required: bool` (是否需要下載新 DB)
  - `degraded: bool` (是否降級為離線模式)
  - `message: str` (人類可讀日誌)

### 2.2 通用抓取原語契約 (Generic JSON Fetch Primitive)
- 模組位置: `tools/pcrd_fetch.py` (由 `pipeline/fetch.py` 匯出)
- 函式: `fetch_story_json_by_id(story_id: int, manifest_hash_map: Optional[Dict[int, str]] = None, timeout: int = 15) -> StoryFetchResult`
- 結構:
  ```python
  @dataclass
  class StoryFetchResult:
      story_id: int
      status: str          # 'OK' | 'HASH_NOT_FOUND' | 'NETWORK_ERROR' | 'PARSE_ERROR' | 'WRITE_ERROR'
      dialogue_count: int  # 對白句數
      hash: Optional[str]  # Bundle Hash
      written_path: Optional[str]
      error_message: Optional[str]
  ```

### 2.3 覆蓋率分析與完整性契約 (Coverage Guard & Integrity)
- 模組位置: `pipeline/coverage.py`
- 函式: `analyze_coverage() -> CoverageResult`
- 欄位包含: `analysis_status`, `analysis_errors`, `source_status`, `required_total_count`, `optional_total_count`, `unknown_expected_count`, `missing_required_count`, `missing_optional_count`, `missing_unknown_count`
- 必備規則: Main (483) ∪ Guild (54) ∪ Tower (253) ∪ Tracked Characters (24) ∪ Branch (63) ∪ Extra Events (254) = **1,131 話**。
- 可選規則: Untracked Characters (1,876) ∪ Special/Other (168) = **2,044 話**。
- 未知分類: **0 話**。

---

## 3. 命令列行為 (CLI Behavior)

| 指令 | 模式 | 寫入副作用？ | 說明 |
| :--- | :--- | :--- | :--- |
| `python update_story_map.py --coverage` | 唯讀分析 | **無 (NO)** | 輸出來源健康度、分析完整性、劇本覆蓋與缺失統計，立即 Exit 0 |
| `python update_story_map.py --dry-run` | 零副作用模擬 | **無 (NO)** | 輸出 Freshness 與 Coverage 摘要，不寫入檔案或 Git |
| `python update_story_map.py` | 本地更新與打包 | **有 (Data only)** | 同步 DB、執行決定性封裝與全量驗證 (必備劇本缺失時 Fail-Stop) |
| `python update_story_map.py --deploy` | 自動發布 | **有 (Git deploy)** | 若新鮮度未確認 (含 `UPDATE_DOWNLOADED_UNCONFIRMED`)、或覆蓋率非 VALID、或存在未分類話數則**強制阻斷發布** (Exit 1) |
| `python update_story_map.py --deploy --allow-unconfirmed-freshness` | 緊急發布 | **有 (Git deploy)** | 僅覆蓋新鮮度門禁；若覆蓋率非 VALID 依然阻斷 |
| `python tools/pcrd_fetch.py fetch-story --story-id <id>` | 單話抓取 | **有 (Story JSON)** | 僅下載單話對白 JSON，使用原子替換寫入 |

---

## 4. 向後相容性與非目標 (Compatibility & Known Non-Goals)

1. **向後相容性 (Backward Compatibility)**：
   - `tools/pcrd_fetch.py sync-episode --story-id <id>` 保持完整的多媒體 (語音/背景/CG) 下載與縮圖快取更新 UX。
   - `python -m pipeline.deploy` 維持純粹發布 (Deploy-Only)，不執行額外網路探測，嚴格保護 C1 Release Synchronization Boundary。
2. **明確非目標 (Known Non-Goals)**：
   - 本階段**不實作未經審查的自動批次抓取 (Automatic Acquisition Queue)**。
   - 本階段**不修改前端任何代碼或靜態檔案 (No Frontend Changes)**。
   - 本階段**不修改 dist_story_map 目錄架構 (No Dist Architecture Rewrite)**。
   - 本階段**不執行任何主倉庫 Git 自動提交 (No Git Automation for Source Repo)**。

---

## 5. 自動化測試驗證 (Test Verification)

* **針對性單元測試 (`tests/test_update_pipeline_c2_implementation.py`)**: **`15/15 PASS`** (涵蓋新鮮度矩陣、來源健康度、DB/元數據故障降級、Manifest 快取、原子寫入、Hash 缺失、未分類話數阻斷、覆蓋率降級阻斷、鏡像防滯後未證實狀態阻斷、新鮮度覆蓋旗標隔離與全綠燈發布路徑)
* **全量單元測試 (`python -m unittest discover tests`)**: **`67/67 PASS`**
* **覆蓋率唯讀檢驗 (`python update_story_map.py --coverage`)**: **`PASS`** (Analysis Integrity: VALID, Source Health: 全部 OK)
* **Dry-Run 模擬驗證 (`python update_story_map.py --dry-run`)**: **`PASS`** (Exit Code 0, 零寫入副作用)
* **資料完整性驗證 (`python -m pipeline.validate`)**: **`0 個錯誤, 2 個警告`** (Exit Code 0 ✅)
