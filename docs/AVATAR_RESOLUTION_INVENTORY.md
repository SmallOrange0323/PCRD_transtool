# Avatar Resolution Inventory — 統一頭像讀取規則前置盤點報告

> **核心目標**：  
> 釐清目前網站「從劇情人物找到頭像」的所有分歧路徑，明確劃分「身分識別（Identity）」與「外觀降級（Appearance Fallback）」，並定義未來統一收斂至 `unit_id → avatar registry → image` 的標準模型與遷移路徑。

---

## 0. 安全邊界與盤點環境

- **Base Branch**：`main`
- **Base HEAD**：`a6c6108f2097151087ccd6597b93b34a35a03f2c`
- **Audit Branch**：`audit/avatar-resolution-inventory`
- **本階段約束**：純文件與架構盤點（READ-ONLY），不修改前端程式碼、不修改 Story JSON、不修改 `avatar_assets.json`、不變更 parser 行為、不下載圖片、不部署。

---

## 一、 現行所有 Avatar Resolution 路徑盤點

經由審查 `dashboard/avatar-service.js`、`dashboard/dialogue-view.js` 及 `dashboard/characters.js`，目前系統中存在 **9 條** 不同的頭像解析與降級路徑：

| 編號 | 路徑名稱 | 入口函式 / 位置 | 觸發條件 | 使用 Key | 最終圖片來源 | 降級行為 (Fallback) | 用途與定位 | 是否仍需存在 |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **A** | **顯式對白 Exact Lookup** | `resolveExactDialoguePortrait`<br>`getAvatarHtmlByUnitId` | 顯式 `unit_id > 0` 且在 Registry 登錄為 active | `numId`<br>(如 `6112`, `100011`, `107411`) | `icon/unit/{filename}`<br>(本地無損 PNG/WebP) | **Fail-Closed**：若失敗或不在 Registry，直接轉文字佔位符，**不重試 CDN、不換 ID、不退回名字** | **未來唯一核心身分路徑**：100% 尊重官方指令流指定的精確角色與形態 | **絕對保留 (Core)** |
| **B** | **>=190000 NPC Exact 規則** | `resolveDefaultPortraitIds` (Rule 1) | `numId >= 190000` | `numId`<br>(如 `193631`, `194211`) | `icon/unit/{numId}.png`<br>或 CDN 鏡像 | 透過 `handleError` 依序重試本地 → So-net 00500012 → So-net 00500015 → EsterTion → 文字佔位符 | 歷史 NPC 號段保護：防止 NPC 被普通角色的 `+11/+31` 規則改寫 | **可淘汰 (CAN REMOVE)**<br>NPC 登錄 Registry 後直接走 Path A |
| **C** | **特殊 Boss/NPC Exact 集合** | `exactPortraitIds`<br>(Rule 2) | `exactPortraitIds.has(numId)` (硬編碼 `107411, 107412, 107431`) | `numId` | `icon/unit/{numId}.png` | 透過 `handleError` 依序嘗試 CDN 鏡像 | 歷史特例白名單：防止 <190000 的特殊敵方/Boss 被誤加 `+11` 改寫 | **可淘汰 (CAN REMOVE)**<br>登錄 Registry 後直接走 Path A |
| **D** | **Exact-First 帶 Base+11 備選** | `exactFirstWithBaseFallback`<br>(Rule 3) | 命中 Set (`138331`, `139231`, `139331`, `139431`) | `[numId, baseId + 11]` | 優先 `numId.png`，失敗時取 `baseId+11.png` | 若 primary 404，在 `handleError` step 4 嘗試 secondary (`baseId + 11`) | GuP 聯動角或特殊形態的跨星級立繪備選 | **可淘汰出核心邏輯**<br>退為資產層 Fallback |
| **E** | **現實專屬頭像映射表** | `realityAvatarMap` & `exactRealityIds` (Rule 4) | `isRealityStory` 篇章或名字命中 120+ 個映射項目 | 角色名稱字串 (如 `"優衣"` → `100232`) | `icon/unit/{realityId}.png` | 透過 `handleError` 重試 CDN 或降至文字佔位符 | **彌補舊話數缺少 unit_id**：因爬蟲未提取到現實 ID，由前端硬編碼話數與名字覆寫 | **可淘汰 (CAN REMOVE)**<br>Story 補全 unit_id 後廢除 |
| **F** | **自定義名稱補全映射** | `customMap` (約 20 個項目) | 僅有角色名字且 `customMap[name]` 存在 | 角色清理後名稱 (如 `"八斗神局長"` → `193631`) | 依推導出的 ID 請求本地或 CDN 圖片 | 透過 `handleError` 逐步重試 | **彌補舊話數/非對白 UI 缺少 unit_id** | **對白路徑可淘汰**<br>僅保留供純文字 UI |
| **G** | **普通角色 Base +11/+31 規整化** | `resolveDefaultPortraitIds` (Rule 5) | `numId < 190000` 且未命中前面任何特例 | `[baseId + 11, baseId + 31]` | 優先 `baseId+11.png` (1星)，備選 `baseId+31.png` (3星) | 若 1 星失敗嘗試 3 星，皆失敗轉文字佔位符 | **外觀立繪星級規整化**：將卡片/基礎 ID (如 `105801`) 轉為真實圖檔 ID (`105811`) | **保留於圖鑑/外觀層**<br>不可干預對白 Exact ID |
| **H** | **發言人名稱推斷降級** | `getAvatarHtml`<br>`getUnitId` | 對白 `unit_id` 為空或無效，僅有 `speaker` 字串 | `speaker` / `cleanName` | 透過 `customMap` / `externalAvatars` 猜測 ID | 無匹配則直接渲染文字佔位符 `<div class="npc-avatar-placeholder">` | 舊版資料與純文字話數的相容兜底 | **保留為 Legacy 兜底**<br>嚴禁覆蓋已有 unit_id |
| **I** | **文字佔位符終極兜底** | `getFallbackHtml`<br>`handleExactDialogueError` | 所有解析失敗、圖片 404、或 Registry 標記為佔位符 | `charaName` 前兩字 | 純 CSS 圓形漸層文字佔位符，無網路請求 | 無 | 防止瀏覽器原生破圖圖示，確保沉浸式體驗 | **絕對保留 (Fail-Closed)** |

---

## 二、 現行正常顯示 NPC 頭像之代表案例分析

為驗證現行不同路徑的運作機制，抽樣 5 個代表性實例如下：

### Case A — 重要敵方 / Boss Exact-ID（如 `107411` 幻境龍后）
- **Story unit_id**：`107411`
- **走入路徑**：`resolveExactDialoguePortrait(107411)`
- **Registry 狀態**：**已收錄** (`status: "active"`, `filename: "107411.png"`, `provenance: "legacy_existing_asset"`)
- **最終路徑**：`icon/unit/107411.png`。
- **機制特點**：雖然它也被寫在 `exactPortraitIds` Set 中，但因為 `unit_id >= 100000` 且已在 Registry 登錄，**它在第一步就直接命中 Path A 精確解析**，根本不需要執行到 `exactPortraitIds`！
- **反例**：`107431`（幻境龍后另一形態）目前未登錄在 Registry 中，若對白指定 `107431`，目前會因 Fail-Closed 判定為 `unknown_placeholder`。

### Case B — >= 190000 NPC（如 `193631` 八斗神局長、`194211` 羅蘭）
- **Story unit_id**：`193631`
- **走入路徑**：`resolveExactDialoguePortrait(193631)`
- **Registry 狀態**：**已收錄** (`status: "active"`, `filename: "193631.png"`, `provenance: "legacy_existing_asset"`)
- **最終路徑**：`icon/unit/193631.png`。
- **機制特點**：在現行版本中，這類 NPC 如果 Story JSON 帶有 `unit_id: 193631`，**已經能 100% 走 Path A 精確解析**。原本代碼中的 `>= 190000` 規則純粹是為了無 unit_id 時、或通用推斷路徑下防止被改寫而設立的保護。

### Case C — 依賴 `customMap` / 名稱映射的案例（如「媞雅」無 unit_id 的 547 行舊對白）
- **Story 資料現況**：在部分早期抽取的話數中，`name: "媞雅"` 但 `unit_id: None`（共 547 行）。
- **走入路徑**：因無 unit_id，落入 `dialogue-view.js` 的 else 分支，調用 `getAvatarHtml("媞雅")`。
- **解析鏈條**：
  1. `getUnitId("媞雅")` 命中 `customMap["媞雅"] = 193211`。
  2. 呼叫 `resolveDefaultPortraitIds(193211)`，觸發 `>= 190000` 規則回傳 `[193211]`。
  3. 組裝 `<img src="icon/unit/193211.png">`。
- **機制特點**：這是典型的 **Missing Identity Shim**。一旦這 547 行話數透過官方 parser 重新抽取並帶有 `unit_id: 193211`，這條名稱映射路徑將立刻失去存在的必要。

### Case D — 普通可玩角色（如 `105801` 佩可莉姆 vs `105811` / `105831`）
- **現象**：資料庫/圖鑑中的 unit_id 通常為 `105801`（角色基礎代碼），但遊戲素材庫**不存在** `105801.png`，只有 `105811.png` (1星)、`105831.png` (3星)、`105861.png` (6星)。
- **走入路徑**：圖鑑系統 (`getCharacterCardAvatarHtml`) 呼叫 `resolveDefaultPortraitIds(105801)`：
  1. `baseId = Math.floor(105801 / 100) * 100 = 105800`。
  2. 回傳 `[105811, 105831]`。
- **本質釐清**：
  - 這**不是** Story Identity Normalization（劇情身分認定）。
  - 這純粹是 **Appearance / Asset Fallback**（因素材命名規則產生的立繪外觀對齊）。
  - 在官方劇情指令流中，cmd 4 / cmd 6 給出的往往直接就是 `105811` 或 `105831`（角色當下穿著的確切外觀）。若對白已有精確 ID，直接查 Registry 即可，絕不應強制將 `105831` 降為 `105811`。

### Case E — Short ID pilot 驗證（如 `6112` 泳裝秘書）
- **Story unit_id**：`6112`（整數）
- **Registry 狀態**：**已收錄** (`status: "active"`, `asset_key: "006112"`, `filename: "006112.png"`, `usage: "dialogue"`)
- **走入路徑**：`resolveExactDialoguePortrait(6112)`
  - 成功命中 `manifestMap.get(6112)`。
  - 回傳 `{ status: "active", unitId: 6112, filename: "006112.png", path: "icon/unit/006112.png" }`。
- **關鍵發現**：
  `AvatarService` 內部已完全具備 short ID exact route 能力。目前唯一阻礙是前端調用處（`dashboard/dialogue-view.js` 第 213 行）硬編碼了門禁：
  `const hasExplicitUnitId = Number.isInteger(numUnitId) && numUnitId >= 100000;`
  只要將此處門禁放寬為 `numUnitId > 0`（由 `AvatarService` 自行審核是否為 registered active ID），Short ID 即已 100% 能走 exact route。

---

## 三、 核心架構問題解答

### 問題 A：若 Story JSON 已有可靠 `unit_id: 107411`，理論上是否只需 `avatar_assets.json[107411]` 就足以找到頭像？
- **結論**：**YES，完全足夠。**
- **目前缺了什麼**：
  1. **Registry 覆蓋完整度**：部分特殊 NPC/Boss（如 `107431` 等）尚未在 `avatar_assets.json` 中登錄 active 條目。
  2. **調用端門禁過嚴**：`dialogue-view.js` 存在歷史防禦門禁 `numUnitId >= 100000`，使 `< 100000` 的 short ID 無法直接抵達 `getAvatarHtmlByUnitId`。
  3. **架構解耦**：只要 Registry 登錄了該 `unit_id` 與其對應的 `filename`，前端 Service 就能一對一產出正確的 `icon/unit/{filename}`，完全不再需要任何額外 hardcoded Set 或規則。

### 問題 B：現有規則中，哪些在補「缺少 unit_id」，哪些在處理「同角色不同 appearance fallback」？
- **彌補「Story JSON 缺少正確 unit_id」（Missing Identity Shim）**：
  - `realityAvatarMap`（120+ 個字串映射）：**100% 補漏洞**。因舊爬蟲未抽取出第 3 部現實劇情的校服 ID，前端被迫用名字 + 話數 ID 反查現實立繪。
  - `customMap`（約 20 個 NPC 映射）：**100% 補漏洞**。彌補舊話數中「八斗神局長」、「媞雅」等對白 `unit_id: null` 的問題。
  - `dialogue-view.js` 佩可 138331 特判：**100% 補漏洞**。彌補該章節對白未標註 138331 的缺陷。
- **處理「同角色不同 appearance / costume fallback」（Appearance Fallback）**：
  - 普通角色 `base + 11 / + 31` 規整化：卡片 ID (`105801`) 到星級立繪檔名 (`105811.png` / `105831.png`) 的外觀映射。
  - `exactFirstWithBaseFallback`（美穗、真穗、艾麗卡、138331）：特定星級圖檔 404 時向 1 星降級的資產 fallback。

### 問題 C：未來官方 canonical unit_id 普及後，Legacy Rules 的淘汰分類

#### 1. CAN REMOVE AFTER UNIT_ID MIGRATION（可全數淘汰）
- `realityAvatarMap`（對白解析路徑）：官方指令流在現實篇章自然帶有現實 unit_id（如 105932），不再需要前端偷看 storyId 做字串反查。
- `exactPortraitIds`（Set: 107411, 107412, 107431）：正式登錄 Registry 後廢除。
- `>= 190000` NPC 特判規則：所有 NPC 統一在 Registry 登記 exact 身分，廢除號段特殊邏輯。
- `dialogue-view.js` 內部的 `isRealityStory` 與 `13830*` 專屬 Hardcode。

#### 2. STILL NEEDED FOR APPEARANCE FALLBACK（外觀/資產層降級保留）
- `base + 11 / + 31` 規整化：**保留於角色圖鑑與卡片展示（Character Catalog / Card Grid）**，因為圖鑑輸入的是資料庫 `unit_id: 105801`，仍需轉為 `105811`。**但在對白閱讀器中退出主流程**。
- `exactFirstWithBaseFallback`：若角色未提供特定星級頭像，作為資產層載入失敗時的備選。

#### 3. STILL NEEDED FOR NAME-ONLY UI（純文字 UI 兜底保留）
- `customMap`：僅在無 unit_id 的純文字搜尋、歷史統計等非劇情閱讀器 UI 中保留。
- `getFallbackHtml`：文字佔位符終極兜底，確保永不破圖。

#### 4. UNKNOWN / NEEDS LATER REVIEW
- `exactRealityIds`：待盤點是否有其他非劇情視圖（如外部個人資料頁）仍在調用，確認後再決定廢除。

---

## 四、 未來統一目標模型 (Proposed Unified Contract)

### 1. 核心模型架構

```text
官方 Story Bundle (AssetBundle)
      │
      ▼
Pipeline Parser (cmd 4 / cmd 6 / 官方 manifest)
      │
      ▼
Story JSON: { "unit_id": 107411, "name": "幻境龍后", "words": "..." }
      │
      ▼
AvatarService.resolveExactDialoguePortrait(unit_id)
      │
      ▼ (單一 O(1) 字典查詢)
avatar_assets.json (Canonical Dialogue Registry)
      │
      ├─ [Active] ─────────────► icon/unit/{filename} (Direct Render)
      ├─ [Placeholder-Only] ──► <div class="npc-avatar-placeholder"> (Fail-Closed)
      └─ [Absent] ─────────────► <div class="npc-avatar-placeholder"> (Strict Fail-Closed)
```

### 2. 統一契約原則
1. **`unit_id` 即唯一身分（Single Source of Identity）**：
   前端閱讀器不再依角色類別區分規則：不管是可玩角色、換裝角色、NPC、Boss、Short ID 或 >= 190000，**只要有 `unit_id`，一律走同一條 Exact Registry Lookup**。
2. **Registry 即資產清單（Identity to Asset Gateway）**：
   `avatar_assets.json` 是唯一的對話頭像白名單。存在且 active 即顯示圖檔；不存在即 Fail-Closed 顯示文字佔位符，嚴格禁止靜默猜測名字。
3. **名字推斷僅為遺產兜底（Inference is strictly Legacy Fallback）**：
   只有在 `unit_id == null` 的舊話數或純文字 UI 中，才允許調用 `customMap` / Name Fallback。

---

## 五、 最小遷移步驟序列 (Minimal Migration Sequence)

本提案僅定義後續實施步驟，**本輪不執行實作**：

- **Step 1：調用端門禁放寬**
  修改 `dashboard/dialogue-view.js`，將 `hasExplicitUnitId` 門禁由 `numUnitId >= 100000` 改為 `numUnitId > 0`，使短 ID（如 6112）與各類合法 ID 一律直接進入 `resolveExactDialoguePortrait`。
- **Step 2：現有 Exact NPC / Boss 全數納入 Registry**
  將目前硬編碼在 `exactPortraitIds` (107411, 107412, 107431) 及 `customMap` 中的常態 NPC，在 `avatar_assets.json` 中確認並補齊 `active` dialogue 條目。
- **Step 3：Parser 全面穩定輸出官方 Canonical unit_id**
  驗證官方 Story Parser 對新舊話數均能穩定提取 cmd 4 / cmd 6 的真實 `unit_id`，逐步透過增量更新補全既有話數的 unit_id。
- **Step 4：廢除前端對白專用硬編碼特判**
  刪除 `dialogue-view.js` 中的 `realityAvatarMap` 反查邏輯與 `13830*` 佩可覆寫邏輯，使對白閱讀器完全純淨。
- **Step 5：淘汰 `resolveDefaultPortraitIds` 中的身分干預**
  廢除 `exactPortraitIds` 與 `>= 190000` 特判，將 `resolveDefaultPortraitIds` 限縮為僅供圖鑑與卡片使用的「資產外觀規整化器（+11/+31）」。
- **Step 6：保留 Name Fallback 於非對白 UI**
  將 `customMap` 標記為內部輔助字典，僅在發言人統計搜尋等無 unit_id 情境發揮作用。
