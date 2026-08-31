# Character Identity B1 — Speaker Identity & Avatar Representation Assessment

> [!IMPORTANT]
> **本報告為全域登場角色總覽 (Speaker View) 與頭像解析模型之產品評估與品質審計報告 (Assessment Only)**。
> 本階段未對任何執行時代碼或 UI 進行修改。

## Executive Summary

在 A1~A3 階段中，我們在對白氣泡 (Dialogue Bubbles) 層級完整保留了行級 `unit_id`，消除了同名台詞合併時的資訊遺失。
本 B1 階段聚焦於**登場角色總覽 (Global Speaker View)** 與**角色頭像解析模型 (AvatarService)**：
全面評估「單一角色名稱 ➡️ 單一代表性頭像」的抽象模型與執行時渲染處置 (Runtime Rendering Disposition)。

---

## 1. Runtime Rendering Disposition (執行時渲染處置分析)

經審計 `dashboard/speaker-view.js` 的真實代碼路徑：
`renderSpeakerCard` 假設只要 `unitId` 為 truthy 即可呼叫 `avatarService.getUrlCandidates(unitId)`。
若未來引入 `0 < unitId < 100000` (Low-ID/Generic NPC)，`getUrlCandidates` 回傳空陣列 `[]` 時，可能產生 `src="undefined"` 之破圖分支。

> [!NOTE]
> **潛在防禦性風險備忘 (Latent / Defensive Risk)**：
> 全量正式資料庫與映射表審計顯示：**目前線上真實暴露數為 0 張 (Current Broken Image Exposure = 0)**。
> 資料庫 SQL 查詢已嚴格限制 `100000 <= unit_id < 200000`，且 `npc_avatars.json` 與 `customMap` 全數為合法大於 100000 之 ID。
> 現行代碼在當前資料集下 100% 穩定，無需進行緊急 runtime 修改。

| Rendering Disposition | Card Count | Percentage | 執行時行為說明 |
| :--- | :--- | :--- | :--- |
| **`valid_candidate_image`** | **344** | 11.5% | `selected_uid >= 100000`，成功生成非空候選 URL 陣列 |
| **`broken_image_risk`** | **0** | 0.0% | `selected_uid < 100000`，進入圖片分支但候選為空 (目前線上為 0 筆) |
| **`text_fallback`** | **2,649** | 88.5% | `selected_uid` 為 `None`，正常進入文字佔位符分支 |

- **總卡片數核對 (Check Sum)**: 344 + 0 + 2649 = **2993** (100% 一致)

---

## 2. Identity Representation Quality (身份代表性品質)

| Quality Class | Card Count | Percentage | 定義 |
| :--- | :--- | :--- | :--- |
| **`GOOD_REPRESENTATIVE`** | **217** | 7.3% | 解析 ID 為該角色在劇本中最主要的 Dominant 型態 |
| **`VALID_NON_DOMINANT`** | **40** | 1.3% | 解析 ID 確實在劇本中登場，但非登場頻率最高型態 (如初始卡面) |
| **`AMBIGUOUS_MULTI_VARIANT`** | **45** | 1.5% | 角色具多種高頻異格 (泳裝、新年等)，各型態佔比分散 |
| **`UNOBSERVED`** | **42** | 1.4% | 透過 cleanName 解析出本體卡面，但該特定括號名稱未直接標註該 ID |
| **`GENERIC_NPC`** | **2,338** | 78.1% | 泛用 NPC、低數值 ID 或通用角色 |
| **`NO_RESOLUTION`** | **311** | 10.4% | 無可解析之 ID |

- **總品質等級核對 (Check Sum)**: 2993 = **2993** (100% 一致)

---

## 3. cleanName UI Exposure & Collisions

- **UI 暴露之 cleanName 歸併群組**: **23 組** (全數記錄於 JSON 產物)
- **人工審查範圍 (Manual Review Scope)**: 全部 23 組 UI 暴露群組
- **確認無關角色實質錯誤歸併 (Confirmed Unrelated Collisions)**: **0 組** (全數確證為合法之括號換裝限定詞、合稱拆分或同人物別名)

---

## 4. Character Modal Architecture & Decoupling

點擊登場角色卡片呼叫 `QuestMapModule.showCharaModal(name)`：
- **登場話數列表**: 由 `this.appearanceMap[realCharaName] || this.appearanceMap[charaName]` 獨立提供。
- **導航解耦確認**: **Representative avatar selection does not directly determine the story IDs used by the appearance-list navigation path**。外觀肖像選取與話數跳轉路徑完全解耦。

---

## 5. Spotlight Cases (代表性角色專案分析)

| 角色名稱 | 登場話數 | 解析 unit_id | 候選數 | 處置狀態 | 品質等級 | 主要 observed unit_id 分佈 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **優衣** | 334 話 | `100211` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `100211: 5298次, 100213: 3269次, 108811: 1650次` |
| **凱留** | 871 話 | `106012` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `106012: 14140次, 106011: 8446次, 127212: 1463次` |
| **可可蘿** | 1018 話 | `105913` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `105913: 14927次, 105911: 7797次, 107611: 1358次` |
| **咲戀** | 248 話 | `102811` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `102811: 7606次, 114511: 2191次, 127512: 1775次` |
| **怜** | 389 話 | `100311` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `100311: 7200次, 122511: 1632次, 108911: 1433次` |
| **日和** | 358 話 | `100111` | 8 | `valid_candidate_image` | `GOOD_REPRESENTATIVE` | `100111: 7800次, 122411: 1594次, 108711: 1304次` |
| **望** | 224 話 | `102913` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `102913: 2379次, 117211: 1709次, 132212: 1636次` |
| **栞** | 209 話 | `103811` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `103811: 3296次, 103813: 3027次, 125414: 957次` |
| **碧** | 175 話 | `104011` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `104011: 4639次, 116711: 1938次, 122111: 1868次` |
| **純** | 210 話 | `104711` | 8 | `valid_candidate_image` | `GOOD_REPRESENTATIVE` | `104711: 5458次, 104715: 756次, 124212: 597次` |
| **貪吃佩可** | 930 話 | `105812` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `105812: 15632次, 105811: 7821次, 105831: 3564次` |
| **雪菲** | 386 話 | `106412` | 8 | `valid_candidate_image` | `GOOD_REPRESENTATIVE` | `106412: 7365次, 106411: 2726次, 135111: 1783次` |
| **靜流** | 194 話 | `104911` | 8 | `valid_candidate_image` | `AMBIGUOUS_MULTI_VARIANT` | `104911: 3676次, 136511: 1675次, 104914: 1368次` |

---

## 6. Two-Tier Product Decision & Final Recommendations

### Tier 1: Identity Model Decision
- **結論**: **`KEEP CURRENT MODEL`**
- **依據**: 全域宏觀總覽採用「一角色一代表立繪」完全符合產品定位與社群認知，登場話數與導航功能完全獨立且精確。

### Tier 2: Runtime Rendering Decision
- **結論**: **`NO CURRENT RUNTIME FIX REQUIRED`**
- **依據**: 線上實際 broken-image 暴露數為 0，現行系統運行穩定，無當前修復必要。
- **可選防禦性備忘 (Optional Future Hardening)**: 若未來修改 `npc_avatars.json` 或 `customMap` 引入小於 100000 之 ID 時，再於 `speaker-view.js` 加入 `candidates.length > 0` 守衛。

### 最終結尾總結 (Final Assessment Status)
B1 審計確證目前**無任何證據**需要進行：
- 角色身份模型重構 (Speaker Identity Redesign)
- 多異格人物總覽 UI 重構 (Multi-Variant SpeakerView)
- 頭像映射表執行時變更 (Avatar Mapping Runtime Change)
- 登場角色卡片降級修補 (SpeakerView Fallback Runtime Patch)

> [!TIP]
> **最終綜合建議：`KEEP CURRENT MODEL`（維持現行生產代碼，無需修改）**
