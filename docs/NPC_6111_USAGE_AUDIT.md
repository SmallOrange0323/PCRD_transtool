# Phase 3A — Usage-Driven 6111 Collision Audit Report

本報告記錄針對 `unit_id: 6111`（常態秘書 / asset_key: `006111`）的全庫使用現狀、官方指令流對齊度與衝突檢驗結果。

> [!IMPORTANT]
> **核心安全結論**：
> **`6111 exact-registry activation safe for CURRENT stored corpus: NO`**  
> 現有庫存劇本中包含 **214 筆 COLLISION**（現有 JSON 帶有 6111，但在官方 conservative parser 下無法重現；即 parsed_unit_id != 6111）與 **281 筆 UNVERIFIABLE**（11 篇話數因行數或未翻譯講者名稱存在漂移），若此時將 6111 登錄至 Avatar Registry，將導致非官方背書的對白錯誤 exact-resolve。

---

## 一、 審計基準與執行環境

- **Audit Universe**：含有現有 `unit_id: 6111` 的 57 篇話數 $\cup$ `{5218004}`（共 58 篇話數）。
- **TruthVersion Snapshot**：`00610007`（全流程單一快照，`storydata2_assetmanifest` 下載次數：1）。
- **官方資產確認**：
  - Manifest 收錄：`storydata_icon_unit_006111.unity3d` (**YES**)
  - 本地 PNG 狀態：`dashboard/icon/unit/006111.png` (**PRESENT**)
    - Size: 15,842 bytes
    - SHA256: `0c09afda774adda3c068917f3620733069fcc7ea127bd1ca436716cc3bf6dc00`

---

## 二、 核心審計指標 (Audit Decision Metrics)

### 1. 現有庫存對齊檢驗 (Current Stored 6111 Verification)

| 指標項目 | 統計數值 | 佔比 / 說明 |
| :--- | :---: | :--- |
| **Existing Stored 6111 Stories** | **57** 篇 | 現有庫存含有 6111 的話數總數 |
| **Existing Stored 6111 Rows** | **1,649** 行 | 秘書: 1,627 行，秘書一號: 22 行 |
| ├─ **VERIFIED_EXACT** | **1,154** 行 | 69.98%（經嚴格全篇語意對齊，與官方 parser 輸出精確一致） |
| ├─ **COLLISION** | **214** 行 | 12.98%（現有為 6111，但官方 conservative parser 解析為 None） |
| └─ **UNVERIFIABLE** | **281** 行 | 17.04%（11 篇話數因長度或語言內容漂移判定為 UNVERIFIABLE_STORY_DRIFT） |

### 2. 官方指令流使用量 (Official Usage - Decoupled Metrics)

| 指標項目 | 統計數值 | 說明 |
| :--- | :---: | :--- |
| **Observed Parsed 6111 Rows** | **1,397** 行 | 審計 universe 58 篇經官方指令流解析出 6111 的總行數 |
| ├─ **Aligned Parsed 6111 Rows** | **1,167** 行 | 在語意完全對齊的故事中解析出的 6111 行數 |
| │  ├─ **Already Present (Verified Exact)** | **1,154** 行 | 現有庫存已登錄且精確吻合 |
| │  └─ **Missing from Current Aligned** | **13** 行 | 現有庫存缺失，全部來自 `5218004` 之「草莓」 |
| └─ **Unmatched due to Story Drift** | **230** 行 | 處於 drift 話數中、尚未進行行級比對的官方 parsed 6111 行數 |
| **Stories with Verified Collisions** | **34** 篇 | 存在至少 1 行無法重現衝突的話數 |
| **Stories with Missing 6111 Rows** | **1** 篇 | `5218004` (草莓，精確吻合 13 行) |

---

## 三、 衝突（COLLISION）根因分析

經抽樣追蹤官方原始指令流（如 `1180002` Row 50）：

```text
178: (6, ['秘書', '\n'])
179: (3, ['6111', '4'])               <-- cmd 3 表情指令
180: (6, ['秘書', '倒不如說，您以為是誰在負責管理這邊的帳簿呀……'])  <-- Row 50
```

1. **表情指令阻斷 carry-forward**：
   官方指令在對白前插入了 `cmd 3: ['6111', '4']` 表情指令，依據 Phase 2 conservative parser 規範，區塊存在表情指令時阻斷同一發言人的 carry-forward，且當前區塊無 `cmd 4` 焦點切換，因此官方 parser 輸出 `unit_id: None`。
2. **歷史資料人造寬鬆賦值 (Unverified Legacy Assignment)**：
   現有存檔中此類行數被賦予了 `unit_id: 6111`，研判為早期歷史爬蟲或批次維護腳本「只要 speaker 包含秘書即全面賦予 6111」所殘留的非官方標準資料。
3. **安全影響**：
   若現在把 `6111` 加入 `avatar_assets.json`，這 214 行未獲官方當前 conservative parser 背書的對白將直接命中 exact dialogue portrait，造成非預期的頭像解析。

---

## 四、 漂移（UNVERIFIABLE）話數清單

本輪審計實施嚴格全篇語意對齊（比對 `type`, `name`, `words`, `voice`, `bg_id`, `still`, `movie_id`），共 11 篇話數（合計 281 行 stored 6111）觸發漂移保護：

### 1. 行數長度漂移 (Length Drift - 5 篇，共 140 行 6111)
- **5132005**：Stored 6111 = 90 行（本地 605 行 vs 官方 606 行）
- **5132006**：Stored 6111 = 32 行（本地 603 行 vs 官方 604 行）
- **5132007**：Stored 6111 = 10 行（本地 252 行 vs 官方 253 行）
- **5213003**：Stored 6111 = 4 行（本地 607 行 vs 官方 609 行）
- **5213011**：Stored 6111 = 4 行（本地 502 行 vs 官方 503 行）

### 2. 講者名稱/語言內容漂移 (Content Drift - 6 篇，共 141 行 6111)
本地存檔講者名稱殘留日版原名（`ペコリーヌ`），而官方解析器已映射為繁中譯名（`貪吃佩可`）：
- **5140061**：Stored 6111 = 47 行
- **5140169**：Stored 6111 = 10 行
- **5142402**：Stored 6111 = 14 行
- **5142411**：Stored 6111 = 13 行
- **5146061**：Stored 6111 = 47 行
- **5146169**：Stored 6111 = 10 行

---

## 五、 後續行動建議

1. **維持現行狀態**：本輪不啟用 6111 Registry，不修改任何 Story JSON。
2. **Phase 3 整合建議**：
   在未來考慮正式登錄 6111 前，應先對上述 34 篇 collision 話數與 11 篇 drift 話數執行官方 Phase 2 parser 重新抽取，將 214 筆未背書的歷史 6111 規整為 `None`，並修復 6 篇日文原名話數，使庫存資料 100% 官方化後再行登錄。

