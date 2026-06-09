# PCRD Data Hub - 劇情地圖模組 交接文件

**版本**：v2.0 (重構後)
**日期**：2026-06-09
**模組名稱**：`QuestMapModule` / 劇情地圖 (主線 + 活動 + 登場角色)
**原始碼路徑**：`dashboard/map.js`（重構版 ~1150 行）
**負責模型**：opencode 工作階段 (2026-06-09)

---

## 1. 本次重構摘要

### 修正的 11 項問題

| # | 問題 | 嚴重性 | 修正方式 |
|---|------|--------|----------|
| 1 | 章節分組正則匹配脆弱 | 🔴 高 | 改用 `groupId` + `ChapterDataService.getPartFromGroupId()` |
| 2 | 資料欄位 `id`/`story_id` 不一致 | 🔴 高 | 統一為 `{ id, chapter, title, groupId, part, isEvent }` |
| 3 | 頭像 URL 假設固定模式 | 🟡 中 | 抽離 `AvatarService`，支援多 CDN 降級 |
| 4 | 競態條件防護不完整 | 🔴 高 | 新增 `safeRender()` 包裝器，統一 await |
| 5 | 章節摘要查找鍵值不匹配 | 🔴 高 | 改用 `ChapterDataService.getSummary(part, groupId)` |
| 6 | 活動 Logo URL 可能失效 | 🟡 中 | 加上 `onerror` 降級 + 預設圖示 |
| 7 | 登場角色分頁搜尋/排序不同步 | 🟡 中 | 統一呼叫 `renderSpeakerTab()` |
| 8 | Modal 重複建立 DOM 元素 | 🟡 中 | 單例模式複用 |
| 9 | 對白載入無重試機制 | 🟢 低 | 新增「重新載入」按鈕 |
| 10 | 硬編碼章節資料超 1000 行 | 🟡 中 | 外部化為 `data/chapters.json` |
| 11 | speaker_appearance.json 不存在 | 🔴 高 | 撰寫生成腳本 |

### 新檔案結構

```
dashboard/
├── map.js                # 重構 (核心邏輯 ~1150 行)
├── avatar-service.js     # 新增 — 統一頭像服務
├── chapter-data.js       # 新增 — 章節資料載入器
├── data/
│   └── chapters.json     # 新增 — 章節標題/摘要（外部化）
├── scripts/
│   ├── generate_speaker_appearance.py  # 新增 — 生成登場統計
│   └── export_chapter_template.py      # 新增 — 匯出章節維護模板
├── story/
│   ├── *.json            # 對白檔（不變）
│   └── speaker_appearance.json  # 新增—自動生成
├── index.html            # 微調—載入順序新增 avatar-service.js, chapter-data.js
├── db.js                 # 不變
├── style.css             # 不變
└── ...
```

---

## 2. 核心架構

### 2.1 資料模型 `StoryEntry`

```javascript
// map.js 內部使用，統一格式
{
  id: number,           // story_id (PK)
  chapter: string,      // 章節顯示名（如 "第1章"）
  title: string,        // 話標題（官方大綱）
  groupId: number,      // story_group_id（分組主鍵，核心欄位）
  part: 1 | 2 | 3,      // 部別（由 ChapterDataService.getPartFromGroupId 衍生）
  isEvent: boolean,     // 主線/活動區分
  eventValue?: number,  // 活動 event_id（CDN Logo 用）
}
```

### 2.2 相依服務順序

```
index.html 載入順序：
1. sql.js (CDN)
2. db.js         → window.PCRDatabase
3. avatar-service.js  → window.AvatarService
4. chapter-data.js    → window.ChapterDataService
5. characters.js
6. clan-battle.js
7. map.js        → window.QuestMapModule (相依 AvatarService, ChapterDataService)
8. events.js
9. usage-stats.js
```

### 2.3 章節分組新邏輯

```javascript
// 舊：用正則解析 title 欄位字串
// 新：用 groupId 計算

// ChapterDataService.getChapterKey(part, groupId, fallback)
// 第一部 (part=1): groupId 2000=序章, 2001=第1章, 2002=第2章, ...
// 第二部 (part=2): groupId 2007=第1章, 2008=第2章, ..., 3001=幕間 1
// 第三部 (part=3): groupId 3001=第1章, 3002=第2章, ..., 4001=幕間 1
```

---

## 3. 關鍵 API 一覽

### 3.1 `QuestMapModule` (map.js)

| 公開方法 | 說明 | 參數 | 注意事項 |
|---------|------|------|---------|
| `render(skipAutoSelect)` | 完整渲染 | `bool` | 經由 `safeRender` 包裝，防競態 |
| `switchPart(part)` | 切換 1/2/3 部 | `1\|2\|3` | 重置 activeStoryId + expandedChapter |
| `switchTabType(type)` | 切換 main/event/speaker | `string` | 同上 |
| `selectStory(storyId)` | 選擇話數 | `number` | 非同步，await updateSummaryContent |
| `jumpToStory(storyId, modalId?)` | 外部跳轉 | `number, string?` | 自動判斷主線/活動/部別 |
| `toggleChapter(index)` | 摺疊章節 | `number` | 收合前一個、展開新章節 |
| `loadDialogue(storyId)` | 載入對白 | `number` | 有 `isLoadingDialogue` 鎖 |
| `playVoice(voiceName)` | 播放語音 | `string` | 自動中斷前一個 |
| `showCharaModal(name)` | 角色檔案彈窗 | `string` | 單例 Modal，複用 DOM |
| `handleSpeakerSearch(value)` | 登場角色搜尋 | `string` | 即時重繪 speaker-grid |
| `handleSpeakerSort(value)` | 登場角色排序 | `string` | 同上 |

### 3.2 `AvatarService` (avatar-service.js)

```javascript
// 核心 API
AvatarService.getUnitId(charaName, externalAvatars)  // 取得 unit_id
AvatarService.getUrlCandidates(unitId)                // 取得頭像 URL 陣列（依優先序）
AvatarService.getAvatarHtml(charaName, externalAvatars) // 取得 img HTML
AvatarService.getFallbackHtml(charaName)              // 文字佔位符
AvatarService.registerCustom(charaName, unitId)       // 運行時註冊 NPC

// URL 嘗試順序：
// 1. icon/unit/{base+31}.webp (本地大圖)
// 2. CDN: https://redive.estertion.win/icon/unit/{base+31}.webp
// 3. icon/unit/{base+11}.webp (本地小圖)
// 4. CDN: {base+11}.webp
// 全部失敗 → 文字佔位符
```

### 3.3 `ChapterDataService` (chapter-data.js)

```javascript
ChapterDataService.load()                    // 載入 data/chapters.json
ChapterDataService.getChapterInfo(part, groupId) // { title, summary, key, order }
ChapterDataService.getTitle(part, groupId)       // 章節標題
ChapterDataService.getSummary(part, groupId)     // 章節摘要
ChapterDataService.getOrder(part, groupId)       // 章節順序
ChapterDataService.getAllChapters(part)          // 該部所有章節（排序後）
ChapterDataService.getPartFromGroupId(groupId)   // 由 groupId 推斷部別
ChapterDataService.getChapterKey(part, groupId, fallback) // 章節鍵名
```

---

## 4. 維護操作指南

### 4.1 遊戲版本更新後

```powershell
# 1. 取得最新資料庫（DB 更新由外部工具負責）
# 2. 更新章節中繼資料
python dashboard/scripts/export_chapter_template.py
REM → 編輯 data/chapters_template.json → 另存為 data/chapters.json

# 3. 下載新話數對白
python download_stories_tw.py

# 4. 重新生成登場角色統計
python dashboard/scripts/generate_speaker_appearance.py

# 5. 啟動驗證
python -m http.server 8080
REM → 瀏覽器開啟 http://localhost:8080
```

### 4.2 新增 NPC 頭像映射

編輯 `avatar-service.js` 中的 `customMap` 物件：
```javascript
customMap: {
    "涅婭": 123311,
    // 新增格式："顯示名稱": unit_id
    // unit_id 取 MIN(unit_id) 且 < 200000
}
```

或於運行時註冊（Console）：
```javascript
AvatarService.registerCustom("新角色名", 123456);
```

### 4.3 修正章節顯示資訊

編輯 `data/chapters.json`，格式如下：
```json
{
  "1": {
    "2000": {
      "title": "阿斯特萊亞大陸",
      "summary": "描述主角祐樹...",
      "key": "序章",
      "order": 0
    }
  }
}
```
- `title`：地標標題（顯示在章節名旁）
- `summary`：整章摘要（支援 HTML）
- `key`：章節鍵名（如 "序章"、"第1章"、"幕間 1"）
- `order`：顯示順序（小→大）

### 4.4 除錯常用 Console 指令

```javascript
// 檢查資料
QuestMapModule.stories              // 所有主線劇情
QuestMapModule.chapters             // 當前分組結果
QuestMapModule.getStoryById(2001001) // 取得特定話數

// 檢查頭像
AvatarService.getUnitId("可可蘿", QuestMapModule.speakerAvatars)
AvatarService.getUrlCandidates(105913)

// 手動渲染
QuestMapModule.switchPart(2)
QuestMapModule.switchTabType('event')

// 檢查章節資料
ChapterDataService.getChapterInfo(1, 2001)
ChapterDataService.getAllChapters(2)
```

---

## 5. 錯誤處理

| 情境 | 處理方式 |
|------|----------|
| 對白 JSON 不存在 | 顯示下載指引 + 「重新載入」按鈕 |
| unit_data 表不存在 | 跳過頭像預載，console.warn |
| 章節摘要未設定 | 顯示「暫無本章節的摘要簡介」 |
| 活動日期解析失敗 | 顯示「【未知時間】」 |
| 頭像載入失敗 | 自動降級 CDN → SD 圖 → 文字佔位符 |
| 資料庫未初始化 | Promise 拋錯 → 載入覆蓋層顯示錯誤 |

---

## 6. 已知限制

1. **`file://` 協議不可用**：必須透過 HTTP Server（Live Server / `python -m http.server`）
2. **第三部幕間雙線敘事**：UI 已用 🎮/🏙️ 圖示區分，但分組邏輯以 `groupId` 為準，部分幕間章節可能需人工調整 `chapters.json`
3. **活動劇情無詳細摘要**：`data/chapters.json` 僅含主線摘要，活動摘要尚未整理
4. **語音播放無重試**：`playVoice` 網路異常時僅 log error，無自動重試
5. **speaker_appearance.json**：需手動執行 Python 腳本生成，非自動更新

---

## 7. 檔案變更總表

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `map.js` | **重寫** | 全部邏輯重構，移除硬編碼 `chapterTitles`/`chapterSummaries`，改用服務層 |
| `avatar-service.js` | **新增** | 頭像統一管理，CDN 降級鏈，NPC 映射 |
| `chapter-data.js` | **新增** | 章節資料載入與查詢 |
| `data/chapters.json` | **新增** | 章節外部資料（原 map.js 中 1000+ 行硬編碼） |
| `scripts/generate_speaker_appearance.py` | **新增** | 登場統計生成工具 |
| `scripts/export_chapter_template.py` | **新增** | 章節維護模板匯出工具 |
| `index.html` | **修改** | 載入順序新增 avatar-service.js / chapter-data.js |

---

## 8. 驗收檢查清單

- [ ] 首次載入：資料庫初始化正常、無紅字錯誤
- [ ] 切換部別（1→2→3）：章節列表正確、順序正確
- [ ] 第三部章節顯示 🎮 遊戲世界 / 🏙️ 現實世界 標記
- [ ] 點選話數：官方大綱載入、對白載入、角色頭像顯示
- [ ] 活動劇情分頁：年月分組正確、活動 Logo 顯示
- [ ] 登場角色分頁：搜尋與排序即時生效
- [ ] 角色彈窗：資料正確、登場話數可點擊跳轉
- [ ] 連續快速切換分頁無競態錯誤
- [ ] 缺少對白 JSON 時顯示友善錯誤與重新載入按鈕

---

## 9. 備註

- 本文件撰寫於重構完成後，請下一位接手者優先閱讀此文件與 `map.js` 模組註解
- 所有服務（AvatarService, ChapterDataService）均掛載於 `window` 下，與既有程式碼相容
- 下載對白腳本 `download_stories_tw.py` 位於專案根目錄，非 `dashboard/scripts/` 下
- 如有架構性變更（如引入前端框架），請同步更新本文件
