# Phase 5.5A — Dialogue View Boundary Review 評估報告

本文件詳細盤點 `dashboard/map.js` 中 `QuestMapModule.loadDialogue()` 的責任邊界，評估在 Phase 5.3B（`DialogueNormalizer` 純資料轉換）與 Phase 5.4（`MediaService` 多媒體服務）抽離完成後，抽離 `DialogueView`（對白渲染視圖模組）的精確邊界、API 介面、DOM 所有權與回歸測試清單。

---

## 一、 現有 `loadDialogue` 責任詳細盤點 (Current Inventory)

目前 `loadDialogue(storyId)` 約佔 `map.js` L1819 ~ L2050（約 230 行），其各子責任分析如下：

| 責任區塊 | 程式碼範圍 | 讀取狀態 | 寫入狀態 | 觸碰 DOM | 外部服務依賴 | 是否建議抽離 | 責任歸屬 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Loading lock / 生命周期** | L1820-1825, L1840, L2048 | `isLoadingDialogue` | `isLoadingDialogue` | `#dialogue-board` | 無 | **NO** | **Controller** (`QuestMapModule`) |
| **B. Loading placeholder UI** | L1826-1830 | 無 | 無 | `#dialogue-board` | 無 | **YES** | **View** (`DialogueView`) |
| **C. Story fetch** | L1833-1836 | 傳參 `storyId` | 無 | 無 | 瀏覽器 `fetch` | **NO** | **Controller** (`QuestMapModule`) |
| **D. Empty dialogue check & UI** | L1838-1842 | 無 | `isLoadingDialogue` | `#dialogue-board` | 無 | **PARTIAL** (邏輯留 Controller，HTML 抽 View) | **Controller + View** |
| **E. Dialogue normalization** | L1844-1845 | 無 | 無 | 無 | `DialogueNormalizer` | **NO** (已於 5.3B 獨立) | **Controller** 調用 Normalizer |
| **F. Speaker avatar preload** | L1847 | `speakerNames` | `speakerAvatars` 快取 | 無 (純 SQL / 記憶體) | SQLite `redive_tw.db` | **NO** | **Controller** (`loadDialogueAvatars`) |
| **G. Speaker badge rendering** | L1849-1876 | `speakerNames`, `speakerAvatars`, `getCharaRealName` | 無 | `#chara-badges-bar` | `AvatarService` | **YES** | **View** (`DialogueView`) |
| **H. Special items (still/bg/movie)** | L1880-1939 | 無 | `firstBgUrl` (局部變數) | 無 (字串累積) | `StoryAssetService` | **YES** | **View** (`DialogueView`) |
| **I. Dialogue bubbles & avatars** | L1940-1996 | `activeStoryId`, `speakerAvatars`, `getCharaRealName` | 無 | 無 (字串累積) | `AvatarService` | **YES** | **View** (`DialogueView`) |
| **J. Ending still append** | L1998-2015 | `currentStoryObj` (`getStoryById`) | 無 | 無 (字串累積) | `StoryAssetService` | **YES** | **View** (`DialogueView`) |
| **K. DOM replacement & cinema bg** | L2017-2030 | `firstBgUrl` | 無 | `#dialogue-board`, `.cinema-panel` | 無 | **YES** | **View** (`DialogueView`) |
| **L. Error rendering** | L2032-2046 | 傳參 `storyId` | 無 | `#dialogue-board` | 無 | **YES** | **View** (`DialogueView`) |
| **M. Lifecycle unlock** | L2047-2049 | 無 | `isLoadingDialogue = false` | 無 | 無 | **NO** | **Controller** (`finally`) |

---

## 二、 職責劃分原則 (Architecture Separation)

### 1. Controller (`QuestMapModule`) 保持擁有之職責：
- **生命週期與並發控制**：`isLoadingDialogue` 鎖旗標、`activeStoryId` 當前話數狀態。
- **資料獲取**：`fetch('story/${storyId}.json')` 取得原始劇本陣列。
- **資料庫快取**：`loadDialogueAvatars(speakerNames)`（向 SQLite 資料庫查詢角色頭像並填充 `this.speakerAvatars` 字典）。
- **業務決策**：取得 `this.getStoryById(storyId)` 與 `this.getCharaRealName(name)`。

### 2. View (`window.DialogueView`) 建議接管之職責：
- **純 HTML 模板生成**：
  - 載入中（Loading Spinner）、空資料（Empty State）、錯誤重試盒（Error Box）。
  - 上方登場角色頭像徽章列（Speaker Badges）。
  - 對白氣泡清單（含旁白/選擇肢樣式、發言人名稱、語音按鈕、角色頭像、貪吃佩可特定話數立繪覆寫）。
  - 特殊劇情標記（插畫 Still、背景切換標記 Background、過場動畫 Movie、話數末端完結 CG）。
- **視圖 DOM 更新**：
  - 更新 `#dialogue-board` 內容與捲動位置重設 (`scrollTop = 0`)。
  - 更新 `#chara-badges-bar` 顯示狀態與內容。
  - 更新 `.cinema-panel` 看板劇院背景圖。

---

## 三、 建議之 API 設計 (`window.DialogueView`)

遵循 Phase 5 依賴注入（Dependency Injection）與零全域污染原則：

```javascript
window.DialogueView = {
    /** 渲染載入中狀態 */
    renderLoading(containerEl),

    /** 渲染無對白空狀態 */
    renderEmpty(containerEl),

    /** 渲染對白載入失敗錯誤盒 */
    renderError(containerEl, storyId),

    /** 渲染上方登場角色徽章列 */
    renderSpeakerBadges(badgesBarEl, {
        speakerNames,
        speakerAvatars,
        resolveRealName
    }),

    /** 生成對白完整 HTML 字串 */
    generateDialogueHtml({
        storyId,
        dialogueList,
        speakerAvatars,
        currentStoryObj,
        resolveRealName,
        escapeHtml
    }),

    /** 渲染完整對白看板與背景特效 */
    renderDialogue({
        boardEl,
        badgesBarEl,
        cinemaPanelEl,
        storyId,
        dialogueList,
        speakerNames,
        speakerAvatars,
        currentStoryObj,
        resolveRealName,
        escapeHtml
    })
};
```

---

## 四、 內聯事件合約 (Inline Event Contracts)

Dialogue HTML 中涉及的現有事件合約，抽離後必須 100% 保留現有轉發相容性：

| 內聯事件屬性 | 所在元素 | 調用目標 | 抽離後處理策略 |
| :--- | :--- | :--- | :--- |
| `onclick="QuestMapModule.showCharaModal(...)"` | `.game-chara-avatar-badge`, `.game-chara-avatar-wrapper`, `.game-dialogue-speaker` | 角色檔案 Modal | **保留相容合約**（由 `QuestMapModule.showCharaModal` 委託至 `CharaModalView`） |
| `onclick="event.stopPropagation(); QuestMapModule.playVoice('...')"` | `.dialogue-voice-btn` (🔊) | 語音播放 | **保留相容合約**（由 `QuestMapModule.playVoice` 委託至 `MediaService.playVoice`） |
| `onclick="QuestMapModule.openStillPopup(event)"` | `.game-dialogue-still` (劇情插畫/完結CG) | 全螢幕插畫彈窗 | **保留相容合約**（由 `QuestMapModule.openStillPopup` 委託至 `MediaService.openStillPopup`） |
| `onclick="QuestMapModule.loadDialogue(storyId)"` | `.dialogue-error-box button` (重新載入) | 對白重試 | **保留相容合約**（直接重新執行 Controller 載入） |

---

## 五、 DOM 所有權 (DOM Ownership)

| DOM 元素 / 容器 | 目前修改者 | 抽離後所有權歸屬 | 理由 |
| :--- | :--- | :--- | :--- |
| `#dialogue-board` | `QuestMapModule` 直接賦值 `innerHTML` | `DialogueView` 專屬渲染 | 避免 Controller 與 View 同時操作對白板塊 |
| `#chara-badges-bar` | `QuestMapModule` 直接修改 `style.display` 與 `innerHTML` | `DialogueView` 專屬渲染 | 登場人物徽章列屬視圖展示層 |
| `.cinema-panel` | `QuestMapModule` 直接修改 `style.backgroundImage` | `DialogueView` 專屬更新 | 看板背景切換屬對白場景視圖渲染的一環 |

---

## 六、 外部相依服務 (External Dependencies)

在 `DialogueView` 中：
- `AvatarService`：直接硬依賴（調用 `getAvatarHtml` 與 `getAvatarHtmlByUnitId`）。
- `StoryAssetService`：直接硬依賴（調用 `getStillHtml` 與 `getBackgroundHtml`）。
- `MediaService`：不直接依賴（視圖僅生成包含 `QuestMapModule.playVoice` / `openStillPopup` 之 HTML 字串）。
- `DialogueNormalizer`：由 Controller 在進入 View 之前調用完成，View 僅接收已規整之 `dialogueList`。

---

## 七、 回歸測試重點 (Regression-Sensitive Points)

1. **角色徽章過濾與順序**：排除「旁白」、「【系統】」、「？？？」與「【選擇肢】」，且僅渲染存在於 `speakerAvatars` 中的可玩角色。
2. **同發言人合併對白氣泡**：連續台詞正確合併於同一氣泡中呈現。
3. **語音按鈕**：有 `item.voice` 時顯示 🔊 按鈕，點擊時觸發 `stopPropagation`。
4. **特殊項目渲染**：
   - `item.type === 'still'`：正確渲染 `✨ 劇情插畫` 與點擊彈窗。
   - `item.type === 'background'`：正確渲染 `🎬 場景切換：{bgId}` 標記並提取首張背景用於 `.cinema-panel`。
   - `item.type === 'movie'`：正確渲染過場動畫提示方塊。
5. **貪吃佩可特例立繪**：當 `activeStoryId` 以 `"13830"` 開頭且角色為「貪吃佩可」時，頭像 unit_id 覆寫為 `138331`。
6. **完結 CG 追加**：當章節包含 `still_id` 或 `bg_id` 且對白列表中無特殊 still 時，正確在最末端追加完結 CG。
7. **HTML 跳脫安全**：`{player}` 與 `{0}` 正確替換為「佑樹」，`\n` 正確轉為 `<br>`，發言人與對白內容正確通過 `escapeHtml`。

---

## 八、 Phase 5.5B 實作建議範圍

- **實作策略**：單一受控抽離（Single Controlled Extraction）。
- **新增檔案**：`dashboard/dialogue-view.js` (`window.DialogueView`)。
- **修改檔案**：
  - `dashboard/map.js`（移除 inline 渲染邏輯，委託至 `DialogueView`）。
  - `dashboard/story_map.html`（引入 `dialogue-view.js`）。
  - `pipeline/bundle.py`（將 `dialogue-view.js` 納入 core_files 與 cache-busting）。
  - `tests/test_dialogue_view.js`（單元測試驗證 HTML 生成與邊界條件）。
- **預估 `map.js` 瘦身幅度**：約 180 ~ 200 行。
- **風險等級**：**LOW**（純視圖渲染抽離，不變更資料管線、不修改資料庫、不破壞現有事件合約）。
