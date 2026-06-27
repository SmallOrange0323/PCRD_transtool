# PCRD 劇情與數據導航站 — 全面架構評估報告

> **評估日期**：2026-06-24  
> **評估版本**：map.js v5.2.2 / style.css v5.0  
> **評估對象**：`dashboard/story_map.html`（對外 GitHub Pages 劇情站）及 `dashboard/index.html`（內部多功能 Data Hub）  
> **本報告目的**：提供客觀的程式碼與 UX 評估，供後續 AI 或開發者接手時快速掌握現況、優先事項與具體改法。

---

## 一、專案整體架構說明

### 1.1 入口頁面

| 檔案 | 用途 | 對外？ |
|:---|:---|:---:|
| `dashboard/story_map.html` | 劇情閱覽站主頁，部署至 GitHub Pages | ✅ 是 |
| `dashboard/index.html` | 內部 Data Hub，含戰隊戰、角色圖鑑、活動日曆、作業統計、資料比對 6 個分頁 | ❌ 否（本機使用）|

兩個頁面共用同一套 CSS（`style.css`）和大部分的 JS 模組。

### 1.2 JavaScript 模組分工

| 檔案 | 負責模組 | 主要功能 |
|:---|:---|:---|
| `db.js` | `PCRDatabase` | 透過 sql.js（WebAssembly）在瀏覽器端讀取 `redive_tw.db` SQLite 資料庫 |
| `map.js` | `QuestMapModule` | 劇情地圖主模組（2417 行），含列表渲染、台詞載入、頭像、摘要、模態框等 |
| `avatar-service.js` | `AvatarService` | 統一管理角色頭像 URL 與多 CDN fallback 邏輯 |
| `story-asset-service.js` | `StoryAssetService` | 管理劇情插畫（Still）、背景圖的 URL 建構與 fallback |
| `chapter-data.js` | `ChapterDataService` | 讀取 `data/chapters.json`，提供章節摘要、標題、現實線摘要查詢 |
| `characters.js` | `CharactersModule` | 角色圖鑑模組（僅 `index.html` 使用）|
| `clan-battle.js` | `ClanBattleModule` | 戰隊戰資料模組（僅 `index.html` 使用）|
| `events.js` | `EventsModule` | 活動日曆模組（僅 `index.html` 使用）|
| `usage-stats.js` | `UsageStatsModule` | 作業統計模組（僅 `index.html` 使用）|
| `diff.js` | `DatabaseDiffModule` | 日台資料庫比對模組（僅 `index.html` 使用）|

### 1.3 資料來源

| 資料 | 來源 |
|:---|:---|
| 角色名稱、劇情標題、官方大綱 | `redive_tw.db`（SQLite，透過 sql.js 在瀏覽器端查詢）|
| 章節摘要（AI 生成）、現實線摘要 | `data/chapters.json`（286KB，本地靜態 JSON）|
| 劇情台詞（對話文本） | `story/{story_id}.json`（每話一個 JSON，從 So-net 解包後本地存放）|
| 角色頭像、插畫 CDN | `https://redive.estertion.win/` 系列（外部，有 fallback 機制）|
| 活動劇情（非資料庫格式的新形式活動）| `data/extra_events.json`（手動維護）|
| 劇情縮圖快取 | `data/story_thumbnails.json`（722KB）|
| 登場角色快取 | `story/speaker_appearance.json` |

### 1.4 劇情 ID 編號規則

```
story_id 範圍     劇情類別
2000000–2999999  主線劇情（Main Story）
1000000–1999999  個人劇情（Chara Story）
3000000–3999999  公會劇情（Guild Story）
4000000–4999999  露娜塔/系統劇情（Tower/System Story）
活動劇情由 event_story_detail 資料表管理，使用 event_story_id
```

---

## 二、優點分析

### 2.1 視覺設計

- **Glassmorphism 毛玻璃**風格貫穿全站（`glass-card`、`backdrop-filter: blur(12px)`），搭配粉橘漸層（`--accent-gradient: linear-gradient(135deg, #e83875 0%, #c4246a 100%)`），符合遊戲氣氛。
- **Google Fonts** 正確引入 `Noto Sans TC`（中文）+ `Outfit`（英文數字），排版可讀性高。
- **Navbar 置頂 sticky + 毛玻璃背景**，在向下捲動時依然保持導覽清晰。
- 載入時的**進度條動畫**（`loader-progress`）提供視覺緩衝，不讓使用者面對白屏等待。

### 2.2 劇情大廳入口設計

「主要 / 角色 / 公會 / 額外」四個大卡片（`menu-card`）以全版背景圖呈現，滑鼠懸停會更換大廳背景視覺，與遊戲主選單邏輯高度呼應，對玩家來說很直覺。

### 2.3 對話閱覽功能

**這部分是整個網站最完整的核心功能，亮點如下：**

1. **連續台詞合併**：相同說話者的連續斷句行會自動合併為單一氣泡，避免閱讀破碎感（`map.js` 約 L.1680–L.1718）。

2. **🔊 語音播放**：每行台詞若有語音檔，會出現可點擊的 🔊 按鈕，透過多 CDN 依序嘗試播放：
   ```js
   const cdnList = [
       `https://prcn-sound.estertion.win/story_vo/${groupId}/${voiceName}.m4a`,
       `https://redive.estertion.win/sound/story_vo/${groupId}/${voiceName}.m4a`
   ];
   ```

3. **🖼️ CG 插畫（Still）**：使用 `StoryAssetService.getStillHtml()` 多層 CDN 載入，點擊可全螢幕彈出（支援 ESC 鍵關閉）。

4. **🎬 過場動畫（Movie）佔位提示**：遊戲內嵌影片無法在網頁播放，目前以粉色說明框提示「此處為過場動畫，可至 YouTube 搜尋」，這是合理的降級方案，不需要更動。

5. **場景切換（Background）**：`background` 節點會更新大畫面（`cinema-panel`）的背景圖，讓整體氛圍隨著故事推進而改變。

6. **登場角色 badges bar**：對話框頂部顯示本話所有有頭像的角色縮圖，點擊可進入角色資料頁。

7. **角色 Modal**：點擊角色名稱彈出詳情（公會、種族、年齡、身高、體重、生日、聲優、自我介紹、登場話數列表），點擊登場話數可直接跳轉閱讀。

### 2.4 導覽架構

- **三層面包屑**（劇情大廳 → 分類 → 角色名）配合左上角浮動返回按鈕，導覽邏輯清晰。
- **跨話數導覽**（上一話 / 下一話）讓連續閱讀流暢。
- **角色搜尋**（支援繁簡容錯，如「菈/拉」「婭/亞」互通）在角色數量龐大時很實用。

### 2.5 資料架構

- 章節資料分離至 `chapters.json`，前端透過 `ChapterDataService` 懶載入，不污染主程式邏輯。
- `chapters.json` 設計了雙軌摘要：`summary`（遊戲內劇情摘要）和 `real_world_summary`（現實線視角摘要），目前主線部分已完成，是本站的獨特賣點。

---

## 三、問題清單（依優先度分類）

---

### 【🔴 高優先】立即影響使用者的顯示問題

---

#### 問題 1：整章摘要分頁 — 空字串無法正確顯示 fallback 提示

**問題檔案**：`dashboard/map.js`，約 L.1601

**現象**：點擊「📖 整章摘要簡介」分頁，部分章節顯示**空白**，而非「暫無本章節的摘要簡介。」

**根本原因**：

`chapters.json` 中，尚未填寫摘要的章節，`summary` 欄位是空字串 `""`，而非 `null`。目前的判斷邏輯只對 `info` 本身為 null 時才 fallback：

```js
// 現況（有 bug）
const summaryText = info ? info.summary : "暫無本章節的摘要簡介。";
// 當 info.summary === "" 時，summaryText = ""，頁面空白
```

**修正方法**：

```js
// 修正後
const summaryText = (info && info.summary) ? info.summary : "暫無本章節的摘要簡介。";
```

`real_world_summary` 同一行也需要同樣處理：

```js
// 現況（可能有相同問題）
const realWorldSummary = info ? info.real_world_summary : null;

// 修正後
const realWorldSummary = (info && info.real_world_summary) ? info.real_world_summary : null;
```

**改動幅度**：極小，僅修改 2 行。

---

#### 問題 2：角色劇情頁搜尋框 — 每次輸入游標消失

**問題檔案**：`dashboard/map.js`，`handleCharaSearch()` 函數，約 L.49–L.88

**現象**：在「角色」分頁的搜尋框中輸入角色名時，每打一個字，游標（文字輸入位置）就會跳走，無法順暢地連續輸入。

**根本原因**：

`handleCharaSearch()` 目前的邏輯是：每次有輸入時，更新整個 `.chara-grid` 的 `innerHTML`。這本身是正確的優化（不重建整頁），但問題在於同樣叫做 `handleCharaSearch` 的函數也被 `_render()` 呼叫，以致在某些路徑下會觸發整頁重建，連搜尋框本身都被銷毀。

相比之下，「登場角色」分頁（Speaker Tab）已有完整的修法：

```js
// speaker tab 的作法（正確）：
// 搜尋輸入時，只更新下方 .speaker-grid 的內容
// 搜尋框本身不被動到，游標不會消失
_updateSpeakerGrid() {
    const gridEl = document.querySelector('.speaker-grid');
    if (!gridEl) { ... return; }
    // 只更新 gridEl.innerHTML，搜尋框不受影響
}
```

**修正方向**：

仿照 `_updateSpeakerGrid()` 的模式，為角色頁撰寫 `_updateCharaGrid()`，僅更新 `.chara-grid` 的內容，並在 `handleCharaSearch()` 中改為呼叫 `_updateCharaGrid()`：

```js
_updateCharaGrid() {
    const gridEl = document.querySelector('.chara-grid');
    if (!gridEl) {
        // fallback: 找不到 grid 就完整重建
        this.safeRender(() => this._render());
        return;
    }
    // 在此只更新 gridEl.innerHTML，複製 handleCharaSearch 的篩選邏輯
    // ...
},

handleCharaSearch(inputVal) {
    this.charaSearchQuery = inputVal;
    clearTimeout(this._charaSearchTimer);
    this._charaSearchTimer = setTimeout(() => {
        this._updateCharaGrid(); // 改呼叫這個
    }, 300);
},
```

**改動幅度**：中等，需新增一個約 30–40 行的 `_updateCharaGrid()` 函數。

---

### 【🟡 中優先】功能不完整或體驗有明顯落差

---

#### 問題 3：活動「整章摘要」是固定罐頭文案，對所有活動都一樣

**問題檔案**：`dashboard/map.js`，約 L.1572–L.1597

**現象**：點擊活動劇情的「📖 整章摘要簡介」分頁，看到的是以下固定文字（對每一個活動都相同）：

```
本劇情為 [月份] 登場的期間限定角色活動劇情。
講述了與該活動核心主角們展開的專屬冒險篇章。
```

**原因**：活動摘要尚未有內容資料來源，目前是硬寫在程式碼中的 hardcode 佔位文字。

**建議改進方向**：

在 `data/extra_events.json` 或未來設計的活動描述 JSON 中，加入 `description` 欄位：

```json
{
    "story_group_id": 10201,
    "title": "活動名稱",
    "description": "這是對這個活動劇情的真實摘要描述...",
    ...
}
```

然後在 `updateSummaryContent()` 的活動分支中，優先顯示 `description`，若無則 fallback 到目前的罐頭文字。

**改動幅度**：中等，需要同時更新 JSON 資料與 JS 渲染邏輯。

---

#### 問題 4：角色 / 公會話數清單樣式遜於主線章節卡

**問題檔案**：`dashboard/map.js`，渲染控制面板段落，約 L.860–L.972

**現象**：

- **主線章節列表**（accordion-item）：每個章節有帶縮圖的「章節卡片」（`chapter-card`），有圖、有標題、有話數，視覺精緻。
- **角色劇情 / 公會劇情 / 露娜塔劇情**的話數清單：只是簡單的 accordion，沒有縮圖、沒有視覺層次，和主線落差很大。

**HANDOVER 文件中也有記錄此待辦（backlog #1）。**

**建議改進方向**：

對角色、公會、額外劇情的每一話，仿照 `getStoryItemHtml()` 已有的縮圖邏輯，改為帶有 16:9 縮圖的長條卡片，例如：

```
┌─────────────────────────────────────────────────┐
│ [縮圖] │  個人故事 第1話                         │
│ 16:9   │  「那個誰誰誰的故事」                    │
└─────────────────────────────────────────────────┘
```

目前 `getStoryItemHtml()` 已有縮圖選取邏輯，可以復用。

**改動幅度**：中到大，需要修改 accordion 的 HTML 結構與對應的 CSS。

---

#### 問題 5：`floating-back-btn` 在快速切換視圖時可能短暫殘留兩個

**問題檔案**：`dashboard/map.js`，多處渲染函數

**現象**：

`floating-back-btn`（左上角藍色圓形返回鈕）是透過 `innerHTML` 直接插入到 tab 內容中的。在下列幾個視圖中各有獨立一個：

- 角色清單視圖（L.796）
- 一般清單視圖（L.983）
- 登場角色 tab（L.2262）

角色清單視圖結尾有清除邏輯，但其他視圖沒有：

```js
// 角色清單視圖結尾有清理（L.836-837）：
const existingBackBtn = document.querySelector('.floating-back-btn');
if (existingBackBtn) existingBackBtn.remove();
// ← 但其他視圖沒有這段清理
```

在快速切換視圖的情況下（例如 fade-in/fade-out transition 期間），可能短暫出現兩個返回按鈕。

**建議改進方向**：

將 `floating-back-btn` 從 `innerHTML` 中移出，改為在 `index.html` / `story_map.html` 中直接用 HTML 宣告為固定 DOM 元素，並在切換視圖時透過 JS 控制其 `display` 與 `onclick` 事件。這樣它就不會隨 `innerHTML` 刷新而重建。

**改動幅度**：中等，需要修改 HTML、CSS 和多個 JS 渲染函數。

---

### 【🟢 低優先】程式碼品質與長期維護性問題

---

#### 問題 6：版本號散落在 HTML 中，需手動維護，容易遺漏

**問題檔案**：`dashboard/index.html`、`dashboard/story_map.html`

**現象**：

```html
<!-- story_map.html 中的版本號，需要每次手動更新 -->
<script src="db.js?v=5.2.0"></script>
<script src="avatar-service.js?v=5.2.1"></script>
<script src="map.js?v=5.2.2"></script>
```

若修改了 `map.js` 但忘記更新 `?v=5.2.2`，使用者的瀏覽器可能繼續讀舊的 cache 版本，看到的還是舊程式碼。

**建議改進方向**：

在 `bundle_story_map.py`（打包腳本）中，改為自動注入打包時的 timestamp 或 git commit hash 作為版本號：

```python
import time
version = int(time.time())  # 或者用 git rev-parse --short HEAD

# 在複製 HTML 時，將版本號佔位符替換為實際版本
content = content.replace('__VERSION__', str(version))
```

**改動幅度**：小，修改打包腳本即可。

---

#### 問題 7：角色詳情 Modal 有兩套獨立實作，未來維護易漏改

**問題檔案**：`dashboard/characters.js`（CharactersModule 的 Modal）、`dashboard/map.js`（QuestMapModule.showCharaModal）

**現象**：

兩個頁面（`index.html` 和 `story_map.html`）各自有一套「點擊角色名稱 → 彈出角色詳情」的 Modal 實作，資料來源和 UI 格式幾乎相同但分別寫在不同檔案中。

若未來要修改 Modal 的外觀、增加欄位（例如加上角色的 3 星卡圖），需要同時修改兩個地方，容易只改一邊。

**建議改進方向**：

將共用的角色 Modal 邏輯抽成一個 `CharaModalService`（獨立 JS 檔），讓兩個頁面共用同一套實作。

**改動幅度**：大，屬於重構工程，建議放到長期 backlog，不急於現在處理。

---

#### 問題 8：`map.js` 單一檔案過長（2417 行），不利維護

**現況**：

`map.js` 含括了以下所有邏輯，全部擠在一個 2417 行的檔案內：

- 資料載入（`loadData`）
- 章節分組（`groupStories`, `groupEventStories`, `groupGuildStories` 等）
- 視圖渲染（`_render`, `renderSpeakerTab`）
- 台詞載入（`loadDialogue`）
- 摘要更新（`updateSummaryContent`）
- 角色 Modal（`showCharaModal`）
- 導覽控制（`toggleChapter`, `selectStory` 等）

**建議改進方向（長期）**：

依功能將 `map.js` 拆分為多個模組，例如：
- `map-data.js`：資料載入與分組邏輯
- `map-render.js`：HTML 渲染函數
- `map-dialogue.js`：台詞載入與渲染
- `map-modal.js`：角色 Modal 邏輯

**改動幅度**：很大，屬大型重構，目前功能優先，此項可列為長期規劃。

---

## 四、各維度綜合評分

```
視覺設計        ████████░░  8/10
  — 配色精準、動畫流暢、Glassmorphism 效果到位
  — 扣分：場景切換提示視覺略顯空洞，罐頭活動摘要對使用者無實際幫助

功能完整度       ███████░░░  7/10
  — 主線劇情功能組合完整：語音、插畫、摘要、跳轉、角色詳情一應俱全
  — 扣分：活動摘要未實作、角色/公會/露娜塔話數清單視覺落後主線

程式碼品質       ██████░░░░  6/10
  — 功能性強，非同步競態保護（safeRender）、多 CDN fallback 設計良好
  — 扣分：map.js 過長（2417行）、兩套 Modal 重複、版本號手動維護

UX 體驗        ███████░░░  7/10
  — 大方向正確：面包屑、返回按鈕、跨話數導覽、搜尋容錯均有考慮
  — 扣分：角色搜尋游標消失、手機版操作路徑較繁瑣

可維護性        █████░░░░░  5/10
  — 扣分：版本號手動管理、兩套 Modal 未統一、單一巨型 JS 檔案
```

---

## 五、建議的下一步處理優先順序

| 優先 | 問題 | 問題所在位置 | 預估工時 | 影響使用者？ |
|:---:|:---|:---|:---:|:---:|
| 🔴 1 | 整章摘要空字串 fallback 修正 | `map.js` L.1601 附近，共 2 行 | 15 分鐘 | ✅ 是 |
| 🔴 2 | 角色搜尋框游標消失 | `map.js` `handleCharaSearch()` | 1–2 小時 | ✅ 是 |
| 🟡 3 | 角色/公會話數清單卡片化 | `map.js` accordion 渲染段 | 3–4 小時 | ✅ 是（視覺體驗）|
| 🟡 4 | `floating-back-btn` 殘留問題 | `map.js` 多處渲染函數 | 1–2 小時 | ❌ 偶發才看到 |
| 🟡 5 | 活動摘要替換罐頭文案 | `map.js` + `extra_events.json` | 2–3 小時 | ❌ 偶發才看到 |
| 🟢 6 | 打包時自動注入版本號 | `scripts/bundle_story_map.py` | 1 小時 | ❌ 暫不影響 |
| 🟢 7 | 兩套角色 Modal 統一 | `characters.js` + `map.js` | 3–5 小時 | ❌ 暫不影響 |
| 🟢 8 | `map.js` 拆分重構 | 整個 `map.js` | 1–2 天 | ❌ 純維護性 |

---

## 六、專案脈絡補充說明（給接手的 AI）

1. **版權聲明**：本站為非官方粉絲工具，所有遊戲資料來自 So-net 台灣代理版，素材版權屬 Cygames 及台灣索尼網路娛樂所有。這是開發者已知情況，**不應在網站上移除現有的版權聲明 footer**。

2. **台版官方術語**：本專案嚴格使用 So-net 台版官方中文翻譯，**任何 AI 生成的摘要內容均須確保術語正確**。核心術語參見 `.agents/AGENTS.md`（或同根目錄下的 `AGENTS.md`）。

3. **`real_world_summary` 的注意事項**：`chapters.json` 中所有的 `real_world_summary` 欄位目前均為 AI 離線自動生成，**可能存在名詞或時空幻覺，尚未完成人工校對**。修改時請確認所有 AI 生成文字的準確性。詳見 `HANDOVER_HOME.md`。

4. **部署流程**：
   - 修改 `dashboard/` 底下的任何 CSS/JS/HTML 後，執行 `python dashboard/scripts/bundle_story_map.py` 更新 `dist_story_map/`。
   - 執行 `python deploy.py` 推送至 GitHub Pages（`gh-pages` 分支）。
   - 最後執行 `git add . && git commit && git push origin HEAD:master` 保存原始碼。

5. **本地測試**：在專案根目錄執行 `python -m http.server 8085`，開啟 `http://localhost:8085/dashboard/story_map.html` 即可本地測試。

---

*報告撰寫：Antigravity AI，2026-06-24*
