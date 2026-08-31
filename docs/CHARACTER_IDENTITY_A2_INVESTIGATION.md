# Character Identity A2 — Targeted Fix Investigation

> [!IMPORTANT]
> **本報告為 DialogueNormalizer 合併策略之量化研究與比較報告 (Investigation Only)**。
> 本階段未對任何執行時代碼 (`dialogue-normalizer.js`) 進行修改或部署。

## Executive Summary

在 A1 審計中，我們確證了現行 `DialogueNormalizer` 在遇上同名、相容語音但背後具有不同 Concrete `unit_id` 的台詞時，會強制合併並覆蓋後續台詞的 `unit_id` (造成 523 次資訊遺失事件)。
本階段針對 4 種對白合併策略進行全量 9,033 篇故事劇本的模擬比對與衝擊量化：

1. **`LEGACY` (現行基準)**：不比對 `unit_id`，保留全部 523 次 Hazard。
2. **`CONCRETE_GUARD` (具體衝突防護 — 核心推薦)**：僅在兩者均具備 Concrete `unit_id` 且不相等時阻止合併。
3. **`STRICT` (嚴格相等)**：嚴格要求 `last.unit_id === item.unit_id` (任一方為 None 即阻止合併)。
4. **`NO_MERGE` (完全不合併 — 極端對照組)**：完全關閉同發言人連續合併。

---

## Core Decision Table (核心策略決策矩陣)

| Strategy | Normalized Rows | Additional Rows (vs Legacy) | Hazards Remaining | Policy Blocks | Confirmed Conflict Blocks | Missing-ID Blocks | Content-Changed Stories |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`LEGACY`** | **365,612** | +0 (0.000%) | **523** | 0 | 0 | 0 | **0** |
| **`STRICT`** | **365,835** | +223 (0.061%) | **0** | 223 | 219 | 4 | **133** |
| **`CONCRETE_GUARD`** | **365,831** | +219 (0.060%) | **0** | 219 | 219 | 0 | **131** |
| **`NO_MERGE`** | **1,234,474** | +868,862 (237.646%) | **0** | N/A (All rejected) | N/A | N/A | **8735** |

---

## Key Strategy Analysis & Trade-Offs

### 1. `CONCRETE_GUARD` (具體衝突防護 — 核心推薦)
- **危害消除率**: **100%** (將 523 次 Hazard 徹底歸零，Hazards Remaining = 0)。
- **策略決策精準度**: **100%** (所有的 Policy Blocks 均為 `confirmed_conflict_block`，Missing-ID Blocks = 0，Other Blocks = 0)。
- **行數微增**: 全站正規化後總行數僅微增 **+219 行** (+0.060%，自 365,612 行增至 365,831 行)。
- **Chain Merge 聚合效益**: 消除 523 次 Hazard 僅產生 219 行增量，是因為在連續 3~4 行切換序列中，拆開後同屬新 unit_id 的後續多行台詞依然順利聚合合併。
- **資料流一致性驗證**: 透過逐節點正規化內容比較 (Canonical Stream Comparison) 確證：
  - **Content-Changed Stories**: **131 篇** (100% 精確對齊 131 篇 Hazard 故事)。
  - **Unchanged Stories**: **8,902 篇** (其餘 8,902 篇故事之正規化輸出在所有 runtime-relevant 欄位上 100% 精確一致)。
  - **Content-Changed without Row-Count Change**: **0 篇**。

### 2. `STRICT` (嚴格相等)
- **危害消除率**: **100%** (Hazards Remaining = 0)。
- **副作用 (Collateral Damage)**: 因一端帶有 `unit_id` 另一端為 None 即拒絕合併 (Missing-ID Blocks > 0)，導致波及話數擴大至 **133 篇** (+223 行)，額外破壞了 2 篇完全無衝突的正常對白合併。

### 3. `NO_MERGE` (完全不合併 — 極端上限)
- 顯示若完全停止合併，全站將暴增 **+868,862 行對白** (+237.6%)，嚴重損害閱讀流暢度與氣泡聚合體驗。

---

## Strict-Only Additional Changed Stories (STRICT 額外破壞話數調查)

| 話數 ID | Legacy 行數 | Strict 行數 | 額外被阻止的決策原因 (Missing-ID Blocks) |
| :--- | :--- | :--- | :--- |
| `2012005` | 54 | 56 | `idx=163 (珠希: 104611 vs None); idx=165 (香織: 101711 vs None)` |
| `5050003` | 215 | 217 | `idx=246 (維多: 5812 vs None); idx=571 (維多: 5812 vs None)` |

---

## Top Story Deltas (受影響最大的故事章節 Top 20)

| 話數 ID | Legacy 行數 | Concrete Guard 行數 | 行數增量 (+Delta) | Legacy 危害數 | Guard 殘留危害 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `1086004` | 97 | 121 | **+24** | 76 | **0** |
| `1233006` | 107 | 120 | **+13** | 18 | **0** |
| `7004005` | 123 | 133 | **+10** | 17 | **0** |
| `1233001` | 82 | 90 | **+8** | 12 | **0** |
| `1023004` | 74 | 78 | **+4** | 8 | **0** |
| `5210000` | 120 | 124 | **+4** | 18 | **0** |
| `1023008` | 73 | 76 | **+3** | 7 | **0** |
| `1233005` | 74 | 77 | **+3** | 3 | **0** |
| `2210006` | 220 | 223 | **+3** | 5 | **0** |
| `4014003` | 84 | 87 | **+3** | 7 | **0** |
| `5154003` | 130 | 133 | **+3** | 4 | **0** |
| `5211002` | 109 | 112 | **+3** | 6 | **0** |
| `6042101` | 5 | 8 | **+3** | 3 | **0** |
| `1809004` | 112 | 114 | **+2** | 3 | **0** |
| `1811003` | 148 | 150 | **+2** | 2 | **0** |
| `2209101` | 129 | 131 | **+2** | 3 | **0** |
| `4014001` | 52 | 54 | **+2** | 11 | **0** |
| `5012001` | 60 | 62 | **+2** | 3 | **0** |
| `5118101` | 17 | 19 | **+2** | 2 | **0** |
| `5154001` | 116 | 118 | **+2** | 7 | **0** |

---

## Real Hazard Spotlight (已知經典案例驗證)

### 故事 `1023004`
- **行數變化**: Legacy `74` ➡️ Concrete Guard `78` (Delta: +4)
- **Hazard 狀態**: Legacy 存在 `8` 次 ➡️ Concrete Guard 徹底降為 **`0` 次**

### 故事 `1023005`
- **行數變化**: Legacy `45` ➡️ Concrete Guard `46` (Delta: +1)
- **Hazard 狀態**: Legacy 存在 `1` 次 ➡️ Concrete Guard 徹底降為 **`0` 次**

### 故事 `1023008`
- **行數變化**: Legacy `73` ➡️ Concrete Guard `76` (Delta: +3)
- **Hazard 狀態**: Legacy 存在 `7` 次 ➡️ Concrete Guard 徹底降為 **`0` 次**

### 故事 `1086004`
- **行數變化**: Legacy `97` ➡️ Concrete Guard `121` (Delta: +24)
- **Hazard 狀態**: Legacy 存在 `76` 次 ➡️ Concrete Guard 徹底降為 **`0` 次**

---

## Speaker Badges Secondary Assessment

1. **現況**：頂部角色徽章 (Speaker Badges) 清單主要依賴發言人名稱透過 `AvatarService.getAvatarHtml(name)` 查詢全域靜態映射表。
2. **評估**：角色徽章代表的是「該章節登場人物總覽」，屬於 Chapter-Level 宏觀摘要，而非行級對白氣泡。
3. **決策建議**：**不建議** 將 Speaker Badges 與 Normalizer 的修復綁在同一個 Commit。應保持職責分離，後續若有需要可另立 `B1` 階段獨立評估。

---

## Conclusions & Recommended Next Step

### 實證結論 (Evidence-Based Findings)
1. **`CONCRETE_GUARD` 表現完美且極度精準**：
   - 徹底消除全部 523 次資訊遺失危害 (Hazards Remaining = 0)。
   - **所有 Policy Blocks 100% 均為明確之具體實體衝突 (Confirmed Conflict Blocks)**，Missing-ID 誤阻數為 0。
   - 逐節點比對證實：全站 8,902 篇無 Hazard 故事之正規化輸出在所有 runtime-relevant 欄位上 100% 完全相同。
2. **衝擊面微小**：全站正規化總行數僅微增 +219 行 (+0.060%)，且僅發生於該 131 篇話數中。

> [!TIP]
> **明確推薦進入 `A3 IMPLEMENT CONCRETE-CONFLICT GUARD` 階段**：
> 在 `dashboard/dialogue-normalizer.js` 中實作 Concrete-Conflict Guard 合併防護條件。
