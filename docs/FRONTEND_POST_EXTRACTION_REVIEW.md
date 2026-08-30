# 🔍 前端架構抽離後現狀重新評估報告 (FRONTEND_POST_EXTRACTION_REVIEW.md)

```text
STATUS: POST-EXTRACTION REVIEW SNAPSHOT
BASE: c33315ae0525ac5969d2dbbaccb53da0382c89dc
REFERENCE:
- docs/FRONTEND_ARCHITECTURE_REVIEW.md remains the original Review 1A snapshot.
- docs/ARCHITECTURE.md remains canonical system architecture.
```

---

## 1. 執行摘要 (Executive Summary)

在完成 **Phase 5.1 (登場人物總覽模組 `speaker-view.js`)** 與 **Phase 5.2 (角色檔案彈窗模組 `chara-modal.js`)** 的受控抽離後，本報告對當前前端架構與 `dashboard/map.js` 進行第二輪深度重新評估（Review 5.3A）。

### 核心量化指標變化
* **`map.js` 程式碼行數**：從原本 **2,624 行** 降至 **2,368 行**（淨減少 256 行核心邏輯，消除約 120 行重複渲染代碼）。
* **新增獨立模組**：
  * `dashboard/speaker-view.js` (173 行)：純展示/過濾/排序與網格組裝。
  * `dashboard/chara-modal.js` (193 行)：純 Profile 表格/自我介紹/話數按鈕與彈窗 DOM 單例管理。
* **架構邊界改進**：
  * 登場人物總覽與角色 Profile 彈窗的 UI 組裝已自 `map.js` 完全解耦。
  * `QuestMapModule` 成功退守為「宿主控制器與資料來源提供者」，維持資料快取（`charaDetailCache`, `appearanceMap`）與路由跳轉（`jumpToStory`）的單一擁有權。

---

## 2. 現存責任盤點 (Current Responsibility Inventory)

以下為 Phase 5.1/5.2 後，目前仍駐留在 `dashboard/map.js` 中的責任矩陣：

| 責任領域 (Responsibility) | 關鍵函式 (Key Functions) | 存取狀態 (State Touched) | 外部依賴 (External Deps) | 耦合度 (Coupling) |
| :--- | :--- | :--- | :--- | :---: |
| **1. 應用路由與分頁切換** | `render()`, `_render()`, `renderMenuTab()`, `renderMainLayout()` | `activeTabType`, `currentView`, `expandedChapter` | DOM (`#map-tab`) | **HIGH** |
| **2. 資料載入與快取預熱** | `loadData()`, `loadDialogueAvatars()` | `stories`, `events`, `eventStories`, `speakerAvatars`, `storyThumbnails` | `PCRDatabase`, fetch, `AvatarService` | **HIGH** |
| **3. 劇情章節資料分組** | `groupStories()`, `groupEventStories()`, `groupGuildStories()`, `groupCharaStories()`, `groupTowerStories()` | `stories`, `eventStories`, `chapters`, `currentPart` | 無 (純邏輯運算) | **MEDIUM** |
| **4. 章節樹與手風琴導航** | `toggleChapter()`, `selectStory()`, `selectPartFromTab()`, `selectChapterFromTab()`, `selectEpisodeFromTab()` | `expandedChapter`, `activeStoryId`, `currentPart` | DOM (`.accordion-content`, `#cinema-*`) | **HIGH** |
| **5. 大綱與摘要分頁控制器** | `updateSummaryContent()`, `updateSummaryTabsUI()`, `switchSummaryTab()` | `activeSummaryTab`, `activeStoryId`, `expandedChapter` | `ChapterDataService`, DOM | **MEDIUM** |
| **6. 對白載入與氣泡合併** | `loadDialogue()` (資料清洗/連續氣泡合併/發言人萃取) | `isLoadingDialogue`, `activeStoryId`, `speakerAvatars` | fetch (`story/{id}.json`), `AvatarService` | **HIGH** |
| **7. AVG 看板與對白視圖渲染** | `loadDialogue()` (HTML 組裝/角標/場景切換/完結 CG) | `activeStoryId` | `StoryAssetService`, `AvatarService`, DOM | **HIGH** |
| **8. 音訊播放控制器** | `playVoice(voiceName)` | `currentAudio` (Audio 實體) | Audio API, CDN 鏡像 | **LOW** |
| **9. CG 插畫全螢幕彈窗** | `openStillPopup()`, `closeStillPopup()` | `_stillPopupKeyHandler` | `StoryAssetService`, DOM (`#still-popup-overlay`) | **LOW** |
| **10. 角色劇情子搜尋** | `handleCharaSearch()`, `_updateCharaGrid()` | `charaSearchQuery`, `_charaSearchTimer` | DOM (`.chara-grid`) | **LOW** |
| **11. 跨模組話數跳轉** | `jumpToStory(storyId, closeModalId)` | `activeTabType`, `expandedChapter`, `pendingJumpStoryId` | DOM (`#story-item-*`) | **HIGH** |
| **12. 外部模組轉接層** | `renderSpeakerTab()`, `_updateSpeakerGrid()`, `showCharaModal()` | 無 (讀取 state 並打包 options) | `SpeakerView`, `CharaModalView` | **LOW (Thin Adapters)** |

---

## 3. 候選接縫重新評估 (Candidate Seam Re-evaluation)

| 候選接縫 (Candidate Seam) | 規模 (Size) | 狀態耦合 (State Coupling) | DOM 耦合 (DOM Coupling) | 資料耦合 (Data Coupling) | 回歸風險 (Regression Risk) | 期望收益 (Benefit) | 推薦優先序 (Rank) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seam A: 對話資料清洗與合併 (Dialogue Normalization)** | 約 45 行 | **NONE (0 狀態)** | **NONE (0 DOM)** | **LOW (純 JSON)** | **VERY LOW (極低回歸風險)** | 核心演算法可獨立單元測試，解除對白解析與 UI 渲染的混雜 | **第 1 優先 (強烈推薦)** |
| **Seam B: 多媒體彈窗與音訊服務 (Media Service: Voice & Still Popup)** | 約 70 行 | **LOW** (`currentAudio`) | **LOW** (獨立 Overlay) | **LOW** | **LOW** | 抽離 Audio 與 CG 放大視窗，乾淨隔離 Web Audio / DOM 事件 | **第 2 優先** |
| **Seam C: AVG 對白劇院渲染器 (Dialogue View / Player)** | 約 280 行 | **HIGH** (`isLoadingDialogue`, `activeStoryId`) | **HIGH** (`#dialogue-board`, `#chara-badges-bar`) | **HIGH** (`speakerAvatars`, `storyThumbnails`) | **MEDIUM** | 抽離龐大的對白 HTML 組裝邏輯 | **第 3 優先 (待 Seam A 完成後)** |
| **Seam D: 章節分組與資料導航 (Story Directory / Grouping)** | 約 200 行 | **CRITICAL (多寫入核心)** | **HIGH** (手風琴動畫/高度計算) | **MEDIUM** | **HIGH** | 解除章節樹與大地圖路由的耦合 | **暫緩 (高風險區)** |

---

## 4. 對白播放器 (Dialogue Player) 專題拆解

`loadDialogue()` (lines 1819-2103) 目前混合了四個層次的責任：

```text
[loadDialogue(storyId)]
  │
  ├── 1. 網路請求層 (Fetch): fetch(`story/${storyId}.json`)
  │
  ├── 2. 純邏輯資料清洗層 (Pure Transformation):
  │       ├── 忽略純空白行 / 換行符號
  │       ├── 連續同一發言人且相同 voice 標籤之氣泡合併 (lines 1845-1887)
  │       └── 萃取所有登場發言人名單 (speakerNames)
  │
  ├── 3. 頭像動態載入層 (Async Data Preload):
  │       └── loadDialogueAvatars(speakerNames) -> 查詢 SQLite 補齊 speakerAvatars
  │
  └── 4. 視圖渲染層 (View HTML Assembly):
          ├── 頂部登場發言人角標 (#chara-badges-bar)
          ├── 逐行氣泡 HTML 組裝 (頭像、姓名、音訊按鈕、對白文本、插畫、背景切換、動畫標記)
          ├── 結尾完結 CG 追加
          └── 看板背景動態切換 (.cinema-panel style.backgroundImage)
```

### 關鍵技術決策：
* **不建議一次性搬移整個 `DialoguePlayer`**：因為它直接依賴 `isLoadingDialogue` 互斥鎖、`activeStoryId`、`speakerAvatars` 快取預載與看板 DOM 操作。
* **強烈建議先抽離「對白清洗與氣泡合併演算法 (Seam A)」**：此段邏輯在現行程式碼中為 `loadDialogue()` 內的 inline pure transformation logic。抽離為獨立純函式模組後，輸入 raw array，輸出 normalized array 與 speaker 名單，具備 100% 確定性與可測試性。

---

## 5. 純函式候選清單 (Pure Function Candidates)

盤點當前 `map.js` 中無副作用（No Side-effects）、不存取 `this` 狀態的純計算邏輯：

| 邏輯區塊 / 函式 | 目前形式與是否無副作用 | 抽離難易度 | 可測試性 (Testability) | 抽離後建議歸宿與命名 |
| :--- | :---: | :---: | :---: | :--- |
| **對話氣泡合併與資料規整** | **目前為 `loadDialogue()` 內 inline logic (無副作用)** | **極容易** | **EXCELLENT (極高)** | `DialogueNormalizer.normalize(rawDialogueList)` |
| **字串容錯正規化 (`normalizeString`)** | **現存獨立方法 (無副作用)** | **極容易** | **EXCELLENT** | 工具函式 |
| **HTML 轉義 (`escapeHtml`, `escapeForAttr`)** | **現存獨立方法 (無副作用)** | **極容易** | **EXCELLENT** | 工具函式 |
| **章節清單群組演算法 (`groupStoriesByType`)** | **現存混合方法 (目前讀寫 this 狀態)** | **中等** (需改為純傳入陣列並回傳物件) | **HIGH** | 未來可重構為純函式 |

---

## 6. 共享狀態耦合矩陣 (State Coupling Matrix)

| 核心狀態 (State) | 寫入者 (Writers) | 讀取者 (Readers) | 影響之候選接縫 | 耦合風險等級 |
| :--- | :--- | :--- | :--- | :---: |
| `activeStoryId` | `selectStory()`, `selectEpisodeFromTab()`, `jumpToStory()`, `toPrevStory()`, `toNextStory()` | `loadDialogue()`, `updateSummaryContent()`, `renderMainLayout()` | Dialogue Player, Story Directory | **CRITICAL (5 個寫入者)** |
| `expandedChapter` | `toggleChapter()`, `selectChapterFromTab()`, `jumpToStory()`, `selectPartFromTab()` | `renderMainLayout()`, `updateSummaryContent()` | Story Directory | **HIGH (4 個寫入者)** |
| `currentPart` | `selectPartFromTab()`, `jumpToStory()` | `groupStories()`, `renderMainLayout()` | Story Directory, Routing | **HIGH** |
| `isLoadingDialogue` | `loadDialogue()` (進入設為 true, finally 設為 false) | `loadDialogue()` | Dialogue Player | **MEDIUM (互斥鎖)** |
| `currentAudio` | `playVoice()` | `playVoice()` (先 pause 舊音訊) | Media Service | **LOW (獨立音訊實體)** |
| `speakerAvatars` | `loadData()`, `loadDialogueAvatars()` | `AvatarService`, `SpeakerView`, `CharaModalView`, `loadDialogue()` | All Views | **MEDIUM (累積快取)** |

---

## 7. 明確禁區 (Explicit No-Go Areas)

在接下來的 Phase 5.3B 重構中，**嚴禁**碰觸以下區域：

1. **🚫 `selectStory()` 與 `jumpToStory()` 核心狀態寫入流程**：
   - 涉及多個寫入者與跨頁籤（main/event/guild/chara/tower）的全局狀態同步，目前不得重構其流程。
2. **🚫 `toggleChapter()` 手風琴高度動畫量測邏輯**：
   - 涉及動態量測 `scrollHeight` 與 `requestAnimationFrame` 兩段式過渡動畫，與 DOM 佈局緊密相關。
3. **🚫 `db.js` 與資料庫初始化層**：
   - 保持 0 修改。

---

## 8. 下一步重構建議 (Phase 5.3B Recommendation)

### 推薦重構目標：**Seam A — 對話資料清洗與正規化純函式抽離 (Dialogue Normalizer Extraction)**

* **為什麼選此接縫 (Why Now)**：
  1. **極低回歸風險 (VERY LOW regression risk)**：演算法本身不依賴 DOM 或 `QuestMapModule` state，且不修改傳入的原始物件。但注意：抽離重構仍存在模組載入順序、API 合約對齊、`speakerNames` 回傳結構與資料複製（clone semantics）等整合點，因此評級為 VERY LOW 而非無條件零風險。
  2. **為後續 Dialogue Player 解耦奠定基礎**：將「劇本資料清洗」與「HTML 標籤組裝」乾淨分開後，未來的對白渲染器才能變成純粹的視圖模組。
  3. **高測試覆蓋潛力**：可直接針對特殊對白（如空行、同一發言人連續說話、不同語音分段、特殊符號）建立決定性測試案例。

### Phase 5.3B 模組契約規格 (Module Contract Specification)：

建議建立 `dashboard/dialogue-normalizer.js`，暴露全域 `window.DialogueNormalizer`：

```javascript
window.DialogueNormalizer = {
    /**
     * 正規化對白劇本資料並萃取發言人清單
     * @param {Array<Object>} rawDialogueList - 原始對白劇本陣列
     * @returns {{ dialogueList: Array<Object>, speakerNames: Array<string> }}
     */
    normalize(rawDialogueList) { ... }
};
```

* **回傳結構定義**：
  * `dialogueList`：過濾純空白行、並將連續相同 `speaker` 且相同 `voice` 標籤的對白行合併（以換行符號連接 `text`）後的陣列。
  * `speakerNames`：從正規化後的 `dialogueList` 萃取出的唯一登場發言人名單（去除重複，過濾掉非角色/無姓名標籤）。
* **硬性約束保證 (Invariants & Guarantees)**：
  * **不修改輸入 (No Input Mutation)**：嚴禁修改傳入的 `rawDialogueList` 陣列或陣列內部的原生物件（必須採 shallow/deep copy 合併）。
  * **無外部依賴 (Zero External Deps)**：不讀取 `QuestMapModule`、不讀取 DOM、不發起 fetch 請求、不呼叫 `AvatarService` 或 `PCRDatabase`。
* **具體保留內容 (What Explicitly Stays)**：
  - `loadDialogue()` 依然留在 `map.js` 作為宿主協調者，負責 fetch 劇本 JSON、呼叫 `DialogueNormalizer.normalize()`、呼叫 `loadDialogueAvatars` 與組裝 HTML。
* **預期檔案變更**：
  - `A dashboard/dialogue-normalizer.js`
  - `M dashboard/map.js`
  - `M dashboard/story_map.html`
* **回滾難度**：極低（單一模組，若有異常可立即還原）。
