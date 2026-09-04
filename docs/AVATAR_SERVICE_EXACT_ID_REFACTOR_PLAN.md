# AvatarService 頭像解析中樞：Exact-ID-First 架構重構執行計畫與 RFC

> **文件狀態**：草案審查中（RFC - Request for Comments）  
> **提出日期**：2026-09-04  
> **目標系統**：`dashboard/avatar-service.js`、`dashboard/dialogue-view.js`  
> **適用範疇**：全專案 9,034 篇劇情劇本之角色立繪頭像解析與降級機制  

---

## 一、 背景與核心問題陳述

在公主連結（PCRD）官方客戶端與伺服器劇本中，每個對白項目（`dialogue`）均可由官方資料庫明確指派一個 6 位數的 `unit_id`。官方設計極其細緻，不僅區分了不同角色與不同換裝，亦透過特定後綴區分了不同情境下的角色外觀。

然而，經對專案全量 **9,034 篇劇本 JSON 檔案**進行全量掃描與資料審查，發現現行前端頭像解析服務 [`dashboard/avatar-service.js`](../dashboard/avatar-service.js) 存在嚴重的**整體架構性邏輯缺陷**：

### 現行問題邏輯（白名單 + 強制歸一化）
在 `AvatarService.resolveDialoguePortraitIds(unitId)` 中：
```javascript
// 現行邏輯：
// 1. NPC (>= 190000) 保留 exact ID
// 2. exactPortraitIds (白名單) 保留 exact ID
// 3. exactFirstWithBaseFallback (白名單) 保留 exact ID 並 fallback base+11
// 4. exactRealityIds (白名單) 保留 exact ID 並 fallback base+11
// 5. 其餘所有 < 190000 的角色（普通可玩角色及其所有變體）：
const baseId = Math.floor(numId / 100) * 100;
return [baseId + 11, baseId + 31]; // ⚠️ 致命缺陷：強制將所有非白名單 ID 抹平成 base+11
```

### 造成的連鎖破壞
1. **官方原始資料被前端強制篡改**：
   本地圖庫 `dashboard/icon/unit/` 實體存放了 **1,715 張官方正版 PNG**，其中 `< 190000` 且後綴非基礎 `11` 的外觀圖檔多達 **884 張**。
   但由於上述第 5 條規則，全專案共有 **246 個官方在 JSON 裡明確指派且本地圖檔明明存在的 `unit_id`，被前端 JS 硬生生抹平降級成 `base+11`**。
2. **影響台詞高達 293,244 句**。
3. **「手動加白名單」是不可持續的打補丁方案**：
   先前每當發現特定角色（如似似花 `107031`、佩可 `138331`）在特定話數顯示異常，便在 JS 裡手動加入一個 Set 白名單。此種作法治標不治本，無法涵蓋其餘 240+ 個角色。

---

## 二、 全量劇本受害數據深度盤點

經由全量自動化審查腳本統計，被前端 JS 誤殺篡改的 246 個具體 ID 呈現三大典型結構性錯誤：

### 類別 1：現實世界造型與特殊角色外觀（共 68 個角色 / 19,842 句台詞）
* **模索路晶（晶）**：官方原始 JSON 寫 `106831`（現實眼鏡大姊姊造型），本地有 `106831.png`，被系統強制改成 `106811`（阿斯特朗拉比林斯達戰鬥裝），**影響 2,664 次**。
* **拉基拉基**：官方在現實篇章寫 `107331`（現實常服），本地有 `107331.png`，被強制改成 `107311`（阿斯特朗綠髮騎士），**影響 921 次**。
* **似似花**：官方在現世審問室寫 `107031`（水手服短髮），本地有圖，原先被強制改成 `107011`（長髮禮服變貌大妃）。
* **其他現實回憶角色**：優衣（`100231`）、嘉夜（`106531`）、深月（`105131`）、真步（`101031`）、莫妮卡（`105331`）、忍（`103131`）、可可蘿（`105931`）、智（`103731`）、惠理子（`102731`）、栞（`103831`）、秋乃（`103231`）等。

### 類別 2：靈獸、人偶、闇影、魔物（共 3 個角色 / 81 句台詞）
* **幽靈小狗（布爾布）**：官方在劇情中分配的 ID 是 `133118`，本地有 `133118.png`。現行 JS 判斷其小於 190000，將其歸納為薇歐莉特本體，**強制改成了美少女 `133111`**。導致小狗吠叫時畫面上顯示美少女頭像！
* **霞的闇影（小霧）**：官方給 `101421`，本地有圖，被強制篡改為霞本體 `101411`。
* **莉莉的闇影**：官方給 `125821`，本地有圖，被強制篡改為莉莉本體 `125811`。

### 類別 3：官方劇情精確差分與服裝動態切換（共 175 個角色 / 273,321 句台詞）
* **霸瞳皇帝 / 尤絲蒂亞娜**：官方指派 `106914`（王女便服），本地有圖，被強制改成 `106911`（霸瞳皇帝裝），**影響 2,170 次**。
* **貪吃佩可**：官方劇情指定差分 `105812`，本地有圖，被強制退回 `105811`，**影響 18,937 次**。
* **可可蘿**：官方劇情指定差分 `105913`，本地有圖，被強制退回 `105911`，**影響 17,453 次**。
* **凱留**：官方劇情指定差分 `106012`，本地有圖，被強制退回 `106011`，**影響 16,830 次**。
* **雪菲**：官方劇情指定差分 `106412`，本地有圖，被強制退回 `106411`，**影響 8,260 次**。

---

## 三、 提議重構方案：Exact-ID-First 架構

### 核心設計理念
1. **官方優先（Official Authority First）**：
   劇本 JSON 中的 `unit_id` 是官方資料庫的權威輸出。只要劇本明確指定了 `unit_id`，系統**第一優先必須嘗試該 `unit_id` 本身**，嚴禁以靜態白名單攔截或擅自修改。
2. **多階梯隊安全降級（Fallback Ladder）**：
   僅將基礎外觀（`baseId + 11` 與 `baseId + 31`）作為備選方案。當且僅當官方指派的 `unit_id` 在本地或遠端 CDN 均不存在時，才依序降級，保證絕不破圖。
3. **職責解耦（Separation of Concerns）**：
   - 劇本有具體 `unit_id` ➡️ 走 Exact-ID 優先解析。
   - 劇本無 `unit_id`（僅有名字）或卡片通用展示（`xx01`）➡️ 走 Name-based / Base-11 預設解析。

### 重構後之 `resolveDialoguePortraitIds` 決策虛擬碼
```javascript
resolveDialoguePortraitIds(unitId) {
    if (!unitId || (typeof unitId !== 'number' && typeof unitId !== 'string')) return [];
    const numId = Number(unitId);
    if (!Number.isInteger(numId) || numId < 100000) return [];

    // 1. 純卡片基礎代碼 (xx01，例如 105801)
    // 此類 ID 並非對白立繪，需推導日常對話外觀：首選 +11，次選 +31
    if (numId < 190000 && numId % 100 === 1) {
        const baseId = Math.floor(numId / 100) * 100;
        return [baseId + 11, baseId + 31];
    }

    // 2. 官方劇本明確指派之具體對白 ID (包括所有 NPC >= 190000、差分、現實造型、靈獸等)
    // 優先策略：第一候選絕對為 numId 本身 (Exact-ID First)
    const baseId = Math.floor(numId / 100) * 100;
    const candidates = [numId];

    // 若自身不是 base + 11，將 base + 11 作為第一安全備選
    if (numId !== baseId + 11) {
        candidates.push(baseId + 11);
    }
    // 若自身不是 base + 31，將 base + 31 作為第二安全備選
    if (numId !== baseId + 31) {
        candidates.push(baseId + 31);
    }

    return candidates;
}
```

### 降級安全網運行流程（Browser Runtime）
1. **初次載入**：
   - 前端輸出 `<img src="icon/unit/${primaryId}.png" onerror="AvatarService.handleError(...)">`，此處 `primaryId` 即為官方指定之 Exact-ID。
   - 本地圖庫中已有的 884 張差分/現實/靈獸圖片直接 200 OK 渲染，**達成 0 延遲完美顯示**。
2. **漸進降級（若 Exact ID 在本地不存在）**：
   - **Step 1 & 2**：嘗試官方 So-net CDN 的 Exact-ID。
   - **Step 3**：嘗試 EsterTion 鏡像站的 Exact-ID WebP。
   - **Step 4**：若 Exact ID 全管道皆無資源，自動回退嘗試 `secondaryId`（即 `baseId + 11` 本地 PNG）。
   - **Step 5**：若仍失敗，嘗試 EsterTion 的 `baseId + 11` WebP。
   - **Step 6**：若全數皆無，安全降級為角色文字佔位符徽章（Placeholder）。

---

## 四、 影響評估與風險控制

### 正向收益
* **29 萬句台詞視覺體驗巨幅升級**：
  晶、拉基拉基、似似花等角色的現實世界外觀自然呈現；幽靈小狗、闇影、人偶等不再被張冠李戴成美少女主角。
* **徹底免除人工白名單維護成本**：
  日後 So-net CDN 更新新角色、新差分時，管線下載圖檔後前端自動即刻生效，無需再於 `exactRealityIds` 中逐筆手動登錄。
* **符合專案核心最高原則**：
  「以官方原始 JSON 的 ID 為唯一基準，嚴禁猜測性修改與過度解讀」。

### 潛在風險與防護策略
* **風險 1：若官方劇本指派了一個「完全沒有被導出圖檔」的冷門差分 ID，是否會導致破圖？**
  - **防護機制**：`AvatarService.handleError` 已具備多階退回梯隊，當 Exact ID 請求 404 時，會在瀏覽器背景無縫切換至 `baseId + 11`，使用者肉眼完全無感知。
* **風險 2：既有單元測試合約變更**
  - **防護機制**：`tests/test_avatar_service.js` 需同步更新驗證合約，將「強制降級」的測試用例重構為「Exact-ID 優先，且 fallback 包含 base+11」。

---

## 五、 開放審查議題（Open Questions for Reviewers）

請各位審查者（包括其他協作 AI）針對以下 3 個具體決策點提供回饋：

1. **議題一：關於 `xx01`（卡片代碼）的判定規則**
   - 提議將 `< 190000 && numId % 100 === 1` 視為純卡片代碼並映射為 `[base+11, base+31]`。
   - *請審查者評估*：是否有任何官方 NPC 或對白角色其自身確切外觀代碼剛好為 `xx01`？（目前已知 NPC 均為 `xx11` 或 `xx01` 如 192701，若為 NPC 是否應放行？）
2. **議題二：歷史白名單變數的去留**
   - 原先的 `exactRealityIds`、`exactPortraitIds`、`exactFirstWithBaseFallback` 是否可以直接廢棄清理，或是保留作為特定少數特例的覆寫備用？
3. **議題三：驗收指標與覆蓋率檢驗**
   - 是否需撰寫一份專屬整合腳本，遍歷全部 9,034 個劇本，確保在新架構下 0 破圖、0 語意衝突？

---

## 六、 執行步驟規劃（待審查通過後執行）

- [ ] **Phase 1**：收集審查意見並微調 RFC 規格。
- [ ] **Phase 2**：更新 `dashboard/avatar-service.js` 中的 `resolveDialoguePortraitIds` 與 `handleError`。
- [ ] **Phase 3**：同步更新 `tests/test_avatar_service.js`、`tests/test_reality_avatars.js` 單元測試。
- [ ] **Phase 4**：執行全量劇本遍歷測試，驗證 246 個受害 ID 的渲染與降級表現。
- [ ] **Phase 5**：提交 Pull Request 並向使用者展示前後對照成果。
