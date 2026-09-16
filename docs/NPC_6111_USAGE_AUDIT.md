# Phase 3A — Usage-Driven 6111 Collision Audit Report

本報告記錄針對 `unit_id: 6111`（常態秘書 / asset_key: `006111`）的全庫使用現狀、官方指令流對齊度與衝突檢驗結果。

> [!IMPORTANT]
> **核心安全結論**：
> **`6111 exact-registry activation safe for CURRENT stored corpus: NO`**  
> 現有庫存劇本中包含 **240 筆 COLLISION**（現有 JSON 帶有 6111，但官方 command stream 無焦點背書或被表情阻斷）與 **140 筆 UNVERIFIABLE**（話數行數漂移），若此時將 6111 登錄至 Avatar Registry，將導致非官方背書的對白錯誤 exact-resolve。

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

| 指標項目 | 統計數值 | 佔比 / 說明 |
| :--- | :---: | :--- |
| **Existing Stored 6111 Stories** | **57** 篇 | 現有庫存含有 6111 的話數總數 |
| **Existing Stored 6111 Rows** | **1,649** 行 | 秘書: 1,627 行，秘書一號: 22 行 |
| ├─ **VERIFIED_EXACT** | **1,269** 行 | 76.96%（與官方 command stream 焦點/carry 100% 一致） |
| ├─ **COLLISION** | **240** 行 | 14.55%（現有為 6111，但官方解析為 None） |
| └─ **UNVERIFIABLE** | **140** 行 | 8.49%（5 篇話數因行數漂移判定為 UNVERIFIABLE_STORY_DRIFT） |
| **Official Parsed 6111 Rows** | **1,282** 行 | 官方真實指令流中合法存在的 6111 總行數 |
| ├─ **Already Present in Corpus** | **1,269** 行 | 已在庫存中且正確對位 |
| └─ **Missing from Current Corpus** | **13** 行 | 現有庫存缺失，全部來自 `5218004` 之「草莓」 |
| **Stories with Verified Collisions** | **38** 篇 | 存在至少 1 行衝突的話數 |
| **Stories with Missing 6111 Rows** | **1** 篇 | `5218004` (預期 13 行，實際吻合 13 行) |

---

## 三、 衝突（COLLISION）根因分析

經抽樣深入追蹤官方原始指令流（如 `1180002` Row 50）：

```text
178: (6, ['秘書', '\n'])
179: (3, ['6111', '4'])               <-- cmd 3 表情指令
180: (6, ['秘書', '倒不如說，您以為是誰在負責管理這邊的帳簿呀……'])  <-- Row 50
```

1. **表情阻斷 carry-forward**：
   官方指令在對白前插入了 `cmd 3: ['6111', '4']` 表情指令，依據 Phase 2 規範，區塊存在表情指令時阻斷同一發言人的 carry-forward，且無 `cmd 4` 焦點切換，因此官方 parser 輸出 `unit_id: None`。
2. **歷史資料人造寬鬆賦值**：
   現有存檔中此類行數被賦予了 `unit_id: 6111`，研判為早期歷史爬蟲或批次腳本「只要 speaker 包含秘書即全面覆寫 6111」所殘留的人造資料。
3. **安全影響**：
   若現在把 `6111` 加入 `avatar_assets.json`，這 240 行非官方焦點的對白將直接命中 exact dialogue portrait，造成非預期的頭像顯示。

---

## 四、 漂移（UNVERIFIABLE）話數清單

以下 5 篇話數在本地存檔與最新 CDN bundle 之間存在行數漂移（相差 1~2 行），為免誤判強制標記為 UNVERIFIABLE：

- **5132005**：Stored 6111 = 90 行（本地 605 行 vs 官方 606 行）
- **5132006**：Stored 6111 = 32 行（本地 603 行 vs 官方 604 行）
- **5132007**：Stored 6111 = 10 行（本地 252 行 vs 官方 253 行）
- **5213003**：Stored 6111 = 4 行（本地 607 行 vs 官方 609 行）
- **5213011**：Stored 6111 = 4 行（本地 502 行 vs 官方 503 行）

---

## 五、 後續行動建議

1. **維持現行狀態**：本輪不啟用 6111 Registry，不修改任何 Story JSON。
2. **Phase 3 整合建議**：
   在未來考慮正式登錄 6111 前，應先對上述 38 篇 collision 話數與 5 篇 drift 話數執行官方 Phase 2 parser 重新抽取，將 240 筆偽 6111 清洗為 `None`，使庫存資料 100% 官方化後再行登錄。
