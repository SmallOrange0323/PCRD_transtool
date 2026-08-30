# 🔍 前端架構現狀依賴與職責審查報告 (FRONTEND_ARCHITECTURE_REVIEW.md)

```text
STATUS: CURRENT-STATE REVIEW SNAPSHOT
PHASE: Frontend Architecture Review 1A
SCOPE: Read-Only Audit (0 Code Changes / 0 Refactors)
REFERENCE: docs/ARCHITECTURE.md remains canonical system architecture.
```

---

## 1. 執行摘要 (Executive Summary)

本報告為 **PCRD 劇情地圖 (PCRD Story Map)** 前端架構之現狀深度審查（Review 1A）。  
針對 `story_map.html`、`map.js` (2,624 行)、`characters.js` (923 行)、`db.js` (387 行)、`avatar-service.js` (272 行)、`story-asset-service.js` (219 行)、`chapter-data.js` (150 行) 及相關靜態元數據進行相依性、狀態擁有權與職責邊界盤點。

### 核心發現總覽
1. **模組集中度極高**：`map.js` 單一檔案承擔了全域路由、資料加載、章節樹、話數面板、對白 JSON 剖析、AVG 播放器、登場角色統計、人物設定彈窗、關鍵字搜尋等多達 12 項不同職責。
2. **全域命名空間依賴 (Global Namespace Coupling)**：所有模組均直接掛載在 `window.*` 下，模組間透過全域物件互相呼叫，HTML 內嵌大量的 `onclick="QuestMapModule.*"` 內聯事件處理。
3. **資料與視圖混雜 (Data + View + DOM in Single Object)**：`characters.js` 與 `map.js` 均同時負責直接寫入 SQL 查詢、維護本地記憶體快取、組裝大型 HTML 字串並直接操作 DOM。
4. **多重資料真實來源 (Multiple Sources of Truth)**：新角色與新活動資料部分寫死在 JS 程式碼中（例如 `characters.js` 中的 `extraUnits`、`map.js` 中的 `villaEvent`），與 `redive_tw.db`、`extra_events.json`、`tracked_characters.json` 存在重複定義與維護分歧。

---

## 2. 前端啟動時序 (Frontend Boot Sequence)

### 2.1 腳本載入順序 (Script Loading Order)
`dashboard/story_map.html` 的實際載入與執行時序如下：

```text
[story_map.html]
       │
       ├─ 1. <head> 載入 sql-wasm.js (定義全域 initSqlJs 函式)
       │
       ├─ 2. <body> 渲染靜態 DOM (#loading-overlay, .navbar, #map-tab, #characters-tab, #char-detail-modal)
       │
       ├─ 3. 依序載入服務與控制器腳本 (Synchronous Script Tags)：
       │       ├── 3.1 db.js (註冊 window.PCRDatabase，設定預設伺服器為 tw)
       │       ├── 3.2 avatar-service.js (註冊 window.AvatarService，定義 customMap 與 CDN 候選邏輯)
       │       ├── 3.3 story-asset-service.js (註冊 window.StoryAssetService，定義 CG/背景 URL 邏輯)
       │       ├── 3.4 chapter-data.js (註冊 window.ChapterDataService，提供章節摘要介面)
       │       ├── 3.5 characters.js (註冊 window.CharactersModule)
       │       └── 3.6 map.js (註冊 window.QuestMapModule，快取 AvatarService 與 ChapterDataService)
       │
       └─ 4. <script> inline 區塊：監聽 DOMContentLoaded 事件
               │
               ▼
   [DOMContentLoaded 觸發]
       │
       ├── 4.1 呼叫 window.PCRDatabase.initDatabase(onProgress)
       │       ├── 初始化 WebAssembly SQLite 虛擬機 (initSqlJs)
       │       ├── 讀取 data/db_info.json (取得 db_version 與檔案大小)
       │       ├── 檢查 IndexedDB 快取 (PCRD_DB_STORE/files) 是否命中
       │       └── 若快取未命中，自 ./redive_tw.db 下載 14.7MB 二進位數據並存入 IndexedDB
       │
       ├── 4.2 隱藏 #loading-overlay (淡出動畫 500ms)
       │
       └── 4.3 呼叫 QuestMapModule.render()
               │
               ▼
   [QuestMapModule.render() / loadData()]
       │
       ├── 4.3.1 查詢 SQLite unit_data 預載頭像映射 (this.speakerAvatars)
       ├── 4.3.2 異步 fetch 載入 data/story_thumbnails.json
       ├── 4.3.3 異步 fetch 載入 data/event_summaries.json
       ├── 4.3.4 異步 fetch 載入 story/speaker_appearance.json
       ├── 4.3.5 異步 fetch 載入 data/extra_events.json
       ├── 4.3.6 查詢 SQLite story_detail 載入主線、活動、公會、個人與其他劇情清單
       ├── 4.3.7 執行 groupStories() 分組
       └── 4.3.8 渲染 #map-tab 預設章節與預設第一話
```

---

## 3. 模組職責矩陣 (Module Responsibility Matrix)

| 模組檔案 | 程式碼行數 | 核心職責 | 依賴對象 | 職責集中度評估 | 候選抽離模組 (Candidate) |
| :--- | :---: | :--- | :--- | :---: | :---: |
| **`map.js`** | 2,624 行 | 1. 劇情大地圖分頁路由<br>2. 階層式章節摺疊樹<br>3. 話數清單渲染<br>4. 對話 JSON 剖析與連續氣泡合併<br>5. AVG 劇院播放器 (背景/語音/CG)<br>6. 登場角色統計與篩選<br>7. 角色資料彈窗 (Profile Modal)<br>8. 全劇本關鍵字搜尋 | `PCRDatabase`<br>`AvatarService`<br>`ChapterDataService`<br>`DOM` | **極高 (God Object)** | **YES** (應漸進式拆分為 Reader, Player, Directory, Search) |
| **`characters.js`** | 923 行 | 1. 角色圖鑑網格渲染<br>2. 角色搜尋與站位/時間排序<br>3. 角色詳細資料彈窗 (Modal)<br>4. 好感度劇情話數導航與跳轉 | `PCRDatabase`<br>`AvatarService`<br>`QuestMapModule`<br>`DOM` | **中高 (Mixed Controller)** | **MAYBE** (資料層與 UI 渲染可分離) |
| **`db.js`** | 387 行 | 1. SQLite WASM 初始化<br>2. IndexedDB 二進位快取管理<br>3. 通用 `runQuery` SQL 執行器<br>4. 版本比對與快取失效 | `initSqlJs`<br>`IndexedDB`<br>`localStorage` | **適中 (Data Access)** | **NO** (邊界清晰，保持現狀) |
| **`avatar-service.js`** | 272 行 | 1. 角色名稱規整化 (Clean Name)<br>2. 自定義 NPC unit_id 映射<br>3. 多層 CDN/本地頭像 URL 候選清單<br>4. 頭像 HTML 生成與 XSS 防護 | `DOM` (onerror 事件字串) | **良好 (Service)** | **NO** (職責專一) |
| **`story-asset-service.js`** | 219 行 | 1. 劇情背景圖 URL 候選與降級<br>2. CG 劇情插畫 URL 候選與降級<br>3. 圖片 onerror 重試處理器 | `DOM` (dataset 狀態) | **良好 (Service)** | **NO** (職責專一) |
| **`chapter-data.js`** | 150 行 | 1. `chapters.json` 載入與快取<br>2. 章節標題、順序、官方與 AI 摘要查詢 | `fetch` API | **良好 (Service)** | **NO** (職責專一) |

---

## 4. 全域依賴審查 (Global Namespace Audit)

| 全域變數 / 物件 | 定義位置 | 主要使用者 (Consumers) | 角色與職責 | 耦合風險 (Coupling Risk) |
| :--- | :--- | :--- | :--- | :---: |
| `window.PCRDatabase` | `db.js` | `story_map.html`, `map.js`, `characters.js` | 全域單例資料庫引擎 | **MEDIUM** (跨模組核心資料源) |
| `window.AvatarService` | `avatar-service.js` | `map.js`, `characters.js`, `story_map.html` | 全域單例頭像與名稱解析服務 | **LOW** (純函式與唯讀快取居多) |
| `window.StoryAssetService` | `story-asset-service.js` | `map.js` | 全域單例 CG/背景資源服務 | **LOW** (無狀態 URL 解析器) |
| `window.ChapterDataService` | `chapter-data.js` | `map.js`, `story_map.html` | 全域單例章節元數據快取 | **LOW** (資料查詢服務) |
| `window.QuestMapModule` | `map.js` | `story_map.html`, `characters.js`, DOM onclick | 主線劇情大地圖主控制器 | **HIGH** (全域掛載多個 onclick 事件) |
| `window.CharactersModule` | `characters.js` | `story_map.html`, `map.js`, DOM onclick | 角色圖鑑主控制器 | **MEDIUM** (與 HTML 彈窗及 map.js 互連) |
| `switchTab(tabId)` | `story_map.html` (inline) | 導航列 `<button onclick="...">` | 全域分頁切換函式 | **LOW** |

---

## 5. 共享狀態與所有權 (Shared State Ownership)

| 狀態名稱 (State) | 現有擁有者 (Owner) | 讀取者 (Readers) | 寫入者 (Writers) | 屬性與風險 |
| :--- | :--- | :--- | :--- | :--- |
| `currentRegion` | `PCRDatabase` | `characters.js`, `map.js`, `story_map.html` | `PCRDatabase.switchRegion()` | 單一寫入者 (固定為 `'tw'`) |
| `db` (SQLite 實體) | `PCRDatabase` | `PCRDatabase.runQuery()` | `PCRDatabase.initDatabase()` | 單一寫入者 (唯讀連線) |
| `activeStoryId` | `QuestMapModule` | `map.js` (導航、大綱、對白) | `selectStory()`, `selectEpisodeFromTab()`, `jumpToStory()` | **MULTIPLE WRITERS (多重入口寫入)** |
| `expandedChapter` | `QuestMapModule` | `map.js` (手風琴、快速目錄) | `toggleChapter()`, `selectChapterFromTab()`, `jumpToStory()` | **MULTIPLE WRITERS** |
| `speakerAvatars` | `QuestMapModule` | `AvatarService`, `map.js` | `loadData()`, `loadDialogueAvatars()` | **MUTABLE CACHE (動態累積快取)** |
| `isRendering` | `QuestMapModule` | `safeRender()` | `safeRender()` | 渲染互斥鎖 |
| `activeTabType` | `QuestMapModule` | `map.js` (main, event, guild, chara, tower) | `switchTab()`, `jumpToStory()` | 控制器狀態 |
| `allCharacters` | `CharactersModule` | `characters.js` | `render()`, `filter()` | 圖鑑內部狀態 |
| `tab-content.active` | **DOM** | `switchTab()`, CSS | `switchTab()` | **DOM-AS-STATE (以 DOM class 作為狀態)** |

---

## 6. DOM 契約審查 (DOM Contract Audit)

以下為若 HTML 結構或 ID 變更，將直接導致 JavaScript 拋出致命錯誤或功能失效的核心 DOM 節點：

| DOM ID / Selector | 使用模組 | 契約用途 | 耦合風險 (Coupling Risk) |
| :--- | :--- | :--- | :---: |
| `#map-tab` | `story_map.html`, `map.js` | 劇情地圖主渲染容器 | **HIGH** (`innerHTML` 全量覆寫) |
| `#characters-tab` | `story_map.html`, `characters.js` | 角色圖鑑主渲染容器 | **HIGH** (`innerHTML` 全量覆寫) |
| `#dialogue-board` | `map.js` | 官方對話對白動態串流面板 | **HIGH** (動態寫入 9000+ 篇劇本對白) |
| `#loading-overlay` | `story_map.html` | 啟動載入遮罩 | **MEDIUM** (淡出控制) |
| `#loader-progress`, `#loader-text` | `story_map.html` | 載入進度條與狀態文字 | **LOW** |
| `#char-detail-modal`, `#modal-body` | `story_map.html`, `characters.js` | 角色圖鑑詳細彈窗 | **MEDIUM** (點擊背景關閉與事件阻止) |
| `#game-chara-modal` | `map.js` (動態建立) | 劇情中角色檔案彈窗 (Profile Modal) | **HIGH** (動態掛載於 `document.body`) |
| `.cinema-panel` | `map.js` | AVG 播放器看板背景容器 | **MEDIUM** (動態切換 `style.backgroundImage`) |
| `#cinema-ch-tag`, `#cinema-title` | `map.js` | 當前播放話數標籤與標題 | **MEDIUM** (動態文字更新) |
| `#btn-prev-story`, `#btn-next-story` | `map.js` | 上一話 / 下一話導航按鈕 | **LOW** (顯示/隱藏切換) |

---

## 7. 核心使用者流程時序 (Core User Flows)

### Flow 1：使用者點選章節 ➔ 展開話數 ➔ 開啟劇情
```text
使用者點擊章節手風琴 (.accordion-header)
      │
      ▼
QuestMapModule.toggleChapter(chIndex)
      │
      ├── 1. 更新 expandedChapter 狀態
      ├── 2. 操作 DOM：切換 .active class，計算 scrollHeight 展開 maxHeight 動畫
      ├── 3. 取得該章節第一話 childStories[0].id
      └── 4. 呼叫 QuestMapModule.selectStory(firstStoryId)
                │
                ├── 4.1 更新 activeStoryId 狀態，高亮對應 .story-item
                ├── 4.2 更新 #cinema-ch-tag 與 #cinema-title
                ├── 4.3 呼叫 updateSummaryContent() (更新大綱/AI 摘要/整章簡介)
                ├── 4.4 呼叫 loadDialogue(storyId)
                │       ├── fetch('story/{storyId}.json')
                │       ├── 剖析 raw JSON，合併同角色/同語音之連續氣泡
                │       ├── 萃取登場發言人，呼叫 loadDialogueAvatars() 查詢 unit_id
                │       ├── 組裝對話氣泡 HTML (包含頭像、語音按鈕、CG 插畫、場景切換)
                │       └── 注入 #dialogue-board，將視窗捲動至頂部
                └── 4.5 呼叫 updateNavigationButtons() (更新上一話/下一話按鈕)
```

### Flow 2：登場角色搜尋 ➔ 篩選列表 ➔ 查看人物設定與登場話數
```text
使用者在登場角色搜尋框輸入關鍵字 (oninput)
      │
      ▼
QuestMapModule.handleSpeakerSearch(keyword)
      │
      ├── 1. 設定 speakerSearchQuery
      ├── 2. 觸發 300ms Debounce 定時器
      └── 3. 呼叫 _updateSpeakerGrid()
                │
                ├── 3.1 遍歷 appearanceMap，過濾非實體角色 (旁白/系統/店員)
                ├── 3.2 依 speakerSortOrder (登場數/名稱) 排序
                ├── 3.3 呼叫 AvatarService.getUnitId 取得頭像 URL
                └── 3.4 僅更新 .speaker-grid 容器 (保留搜尋框焦點與游標)
```

### Flow 3：自角色詳細彈窗跳轉至特定劇情 (Cross-Module Navigation)
```text
使用者在人物檔案彈窗點擊特定登場話數按鈕 (onclick)
      │
      ▼
QuestMapModule.jumpToStory(storyId, 'game-chara-modal')
      │
      ├── 1. 關閉人物檔案彈窗 (#game-chara-modal)
      ├── 2. 呼叫 getStoryById(storyId) 判斷劇情類別 (main / event / guild / chara)
      ├── 3. 自動切換 activeTabType 並重新分組 (groupStories / groupEventStories)
      ├── 4. 自動定位所屬章節 key，設定 expandedChapter
      └── 5. 呼叫 safeRender() 重新渲染列表，並觸發 selectStory(storyId)
                └── 自動捲動畫面至對應 #story-item 節點 (scrollIntoView smooth)
```

---

## 8. 現行相依架構圖 (Current Dependency Graph)

```text
+-------------------------------------------------------------------------+
| story_map.html (Entry Page)                                             |
| ├── #loading-overlay                                                    |
| ├── .navbar (switchTab)                                                 |
| ├── #map-tab ◄─────────────────────────┐                                |
| ├── #characters-tab ◄────────┐          │                                |
| └── #char-detail-modal       │          │                                |
+------------------------------┼──────────┼--------------------------------+
                               │          │
         ┌─────────────────────┘          └─────────────────────┐
         ▼                                                      ▼
+──────────────────────────+                  +──────────────────────────+
| CharactersModule         |                  | QuestMapModule (map.js)  |
| (characters.js)          |                  | ├── 路由 & 頁籤控制      |
| ├── 角色數據清洗         |                  | ├── 章節列表與手風琴動畫 |
| ├── 網格與站位排序       |                  | ├── 對話 JSON 剖析與合併 |
| ├── 角色詳細彈窗         |                  | ├── AVG 劇院看板播放器   |
| └── 寫死 extraUnits      |                  | ├── 語音音訊播放控制     |
+────────────┬─────────────+                  | ├── 登場人物統計與搜尋   |
             │                                | ├── 角色檔案彈窗 (Modal) |
             │                                | └── 全劇本關鍵字搜尋     |
             │                                +────────────┬─────────────+
             │                                             │
             └──────────────────────┬──────────────────────┘
                                    │
                                    ▼
+────────────────────────────────────────────────────────────────────────+
| 共享基礎服務層 (Shared Service Layer)                                  |
|                                                                        |
| ├── PCRDatabase (db.js)                                                |
| │   └── sql-wasm.js / sql-wasm.wasm ➔ redive_tw.db (IndexedDB 快取)    |
|                                                                        |
| ├── AvatarService (avatar-service.js)                                  |
| │   └── customMap ➔ data/npc_avatars.json ➔ So-net / EsterTion CDN     |
|                                                                        |
| ├── StoryAssetService (story-asset-service.js)                         |
| │   └── CG / 背景圖 URL 候選與多層 Fallback                            |
|                                                                        |
| └── ChapterDataService (chapter-data.js)                               |
|     └── data/chapters.json ➔ data/main_story_chapter_summaries.json    |
+────────────────────────────────────────────────────────────────────────+
```

---

## 9. 架構審查發現 (Architectural Findings)

### [P0] 正確性與架構阻礙 (Correctness / Architecture Blocker)
*無致命阻礙性 Bug，目前系統運作穩定。*

### [P1] 高耦合度與變更風險 (High Coupling / High Change Risk)
* **F-01: `map.js` 職責過度集中 (God Object Anti-Pattern)**
  * *現狀*：2,624 行包含 12 項不同領域的邏輯，任何單一 UI 小改動（如調整手風琴動畫）都需要在巨大的全域控制器中修改，容易引發未預期之連帶副作用。
  * *建議方向*：按領域接縫（Seam）進行邏輯模組拆分（例如分離 AVG 播放器、登場角色總覽、搜尋引擎）。
* **F-02: HTML 內聯事件綁定過多 (Tight Inline Event Coupling)**
  * *現狀*：HTML 與動態組裝之字串中充斥著 `onclick="QuestMapModule.selectStory(...)"`、`onclick="QuestMapModule.showCharaModal(...)"`，強烈依賴全域命名空間。
  * *建議方向*：未來可評估採用事件代理（Event Delegation）模式，降低對全域 window 物件的強耦合。
* **F-03: 使用者介面包含過時維護指令 (User-Facing Stale Maintenance Command)**
  * *現狀*：`map.js`（約 line 2095）的對白下載失敗提示 UI 仍要求執行 root-level 的 `python download_stories_tw.py`，但該腳本在 Phase 3 已搬移至 `tools/maintenance/download_stories_tw.py`。
  * *影響*：使用者若依 UI 指示複製貼上執行，將直接遭遇找不到檔案錯誤（file-not-found），屬於使用者可見之操作偏差（operational drift）。
  * *建議方向*：應建立獨立小型 correctness fix batch，專門修正此 UI 提示文字，不與架構重構混合進行。

### [P2] 可維護性與重複定義 (Maintainability & Duplication)
* **F-04: 多重資料真實來源 (Multiple Sources of Truth)**
  * *現狀*：`characters.js` 內寫死了 19 筆 `extraUnits` 陣列（lines 51-71）；`map.js` 內寫死了 `10215` 活動（lines 305-334）。這些資料同時存在於資料庫與 JSON 配置中。
  * *建議方向*：由 Pipeline 資料同步階段統一產出標準 JSON 元數據，前端僅負責讀取，不再硬編碼業務資料。
* **F-05: 重複的 HTML 轉義邏輯 (Duplicated Escape Logic)**
  * *現狀*：`map.js`、`avatar-service.js`、`story-asset-service.js` 各自實作了 `escapeHtml()` 函式。
  * *建議方向*：未來可收斂為單一全域工具函式。

### [P3] 清理與命名規範 (Cleanup & Naming)
* **F-06: 殘留的過時註解與廢棄函式**
  * *現狀*：`map.js` 中存在已廢棄之 `handleAvatarError()` 宣告（標註由 AvatarService 接管）。
  * *建議方向*：待重構時一併清理無用代碼。

---

## 10. 候選安全抽離接縫 (Candidate Extraction Seams)

以下依「低風險、高內聚、易驗證」原則，評估可自 `map.js` 安全抽離的潛在模組接縫：

| 接縫名稱 (Seam) | 建議抽離內容 | 收益 (Benefit) | 風險 (Risk) | 完整依賴項 (Dependencies) | 建議順序 |
| :--- | :--- | :--- | :---: | :--- | :---: |
| **Seam 1: 登場人物總覽模組 (`speaker-view.js`)** | 抽離 speaker list filtering / sorting / card rendering，透過明確 callbacks 保留 modal 與 navigation 行為 | 抽離約 200 行獨立 UI，完全不影響主線劇情閱讀與 AVG 播放 | **LOW–MEDIUM** | `appearanceMap`, `speakerSearchQuery`, `speakerSortOrder`, `speakerAvatars`, `AvatarService`, `getCharaRealName()`, `escapeHtml()`, `showCharaModal()`, navigation callbacks, `QuestMapModule` inline event contract | **第 1 優先 (推薦首批)** |
| **Seam 2: 角色檔案彈窗模組 (`chara-modal.js`)** | `getCharaModal()`, `showCharaModal()` | 抽離人物 Profile 查詢與彈窗組裝邏輯，解耦 `unit_profile` 查詢 | **LOW** | `PCRDatabase`, `AvatarService` | **第 2 優先** |
| **Seam 3: AVG 對白播放渲染器 (`dialogue-player.js`)** | `loadDialogue()`, `openStillPopup()`, `playVoice()` | 將核心對白剖析、連續氣泡合併、音訊播放自大地圖路由中解耦 | **MEDIUM** | `StoryAssetService`, `AvatarService` | **第 3 優先** |
| **Seam 4: 章節大地圖導航控制器 (`story-directory.js`)** | `groupStories()`, `toggleChapter()`, `selectStory()` | 保留為純粹的章節樹與話數清單導航控制器 | **MEDIUM** | `ChapterDataService` | **第 4 優先** |

> [!IMPORTANT]
> **Seam 1 抽離實作注意事項**：
> 登場人物模組仍可作為第一批抽離候選，但第一步應採用**依賴注入 / 適配器風格 (Dependency-Injection / Adapter Style Extraction)**，不能直接將 200 行搬移至新檔案後期待自動解耦。  
> 應先抽離 speaker list filtering / sorting / card rendering，並透過明確 callback 介面呼叫宿主之 `showCharaModal` 與導航跳轉，嚴禁將全域狀態與彈窗邏輯一次性硬搬。

---

## 11. 明確禁區 (Explicit No-Go Areas)

在第一階段重構中，**嚴禁**碰觸以下高風險核心：

1. **🚫 `db.js` 資料庫連線與 IndexedDB 快取機制**：
   - 涉及 WebAssembly 跨執行緒載入、14.7MB 大檔案流式下載與快取失效判斷，目前極度穩定，嚴禁重構其內部實作。
2. **🚫 `story_map.html` 核心容器階層結構**：
   - `#loading-overlay`、`#map-tab`、`#characters-tab` 為 CSS 與各模組掛載之根節點，重構時不得更動其 DOM ID。
3. **🚫 多語音連續對白合併演算法 (lines 1845-1887)**：
   - 此處包含針對 So-net 斷句與特殊語音標籤的專屬處理，稍有不慎即會破壞台詞閱讀流暢感，非專屬測試覆蓋前不宜改動。

---

## 12. 建議重構路線圖 (Recommended Refactor Roadmap)

```text
[ Review 1A: 現狀審查與相依性審計 (本階段 - 0 Code Changes) ]
                       │
                       ▼
[ Correctness Fix Batch (可選): 修正 map.js 中過時的維護指令文字 (tools/maintenance/...) ]
                       │
                       ▼
[ Phase 5.1: Seam 1 抽離 — 登場角色總覽模組 (speaker-view.js) ]
  - 採 Dependency Injection / Adapter 風格抽離 filtering / sorting / grid rendering (約 200 行)
  - 透過明確 callbacks 保留 modal 與 navigation 行為
  - 驗證：登場角色頁籤展示、即時搜尋、排序功能 100% 正常
                       │
                       ▼
[ Phase 5.2: Seam 2 抽離 — 角色檔案彈窗服務 (chara-modal.js) ]
  - 抽離 showCharaModal 與登場話數跳轉介面
  - 驗證：點擊任意角色頭像可正常彈出設定集並跳轉話數
                       │
                       ▼
[ Phase 5.3: Seam 3 抽離 — AVG 劇院對白播放器 (dialogue-player.js) ]
  - 封裝對話串流載入、語音播放、CG 插畫彈窗
  - 驗證：全章節劇本正常播放、語音正常發聲、插畫正常預覽
```

