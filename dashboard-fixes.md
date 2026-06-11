# Dashboard 劇情地圖程式邏輯修復清單

## 📄 文件說明

本文件記錄了 `dashboard` 資料夾內劇情地圖相關程式碼（`map.js`、`db.js`、`avatar-service.js`）的邏輯修復詳情，供後續接手維護的開發人員參考。

## 🔧 修復摘要

| 編號 | 問題類型 | 嚴重程度 | 影響檔案 | 修復狀態 |
|------|---------|---------|----------|----------|
| 1 | 重複渲染 | 中 | `map.js` | ✅ 已修復 |
| 2 | 競態條件 | 中 | `map.js` | ✅ 已修復 |
| 3 | 錯誤處理不完善 | 中 | `map.js` | ✅ 已修復 |
| 4 | XSS 安全漏洞 | **高** | `map.js`, `avatar-service.js` | ✅ 已修復 |
| 5 | 記憶體洩漏 | 低 | `map.js` | ✅ 已修復 |
| 6 | 資料庫初始化錯誤 | 中 | `db.js` | ✅ 已修復 |
| 7 | 載入狀態未重置 | 中 | `map.js` | ✅ 已修復 |
| 8 | CSS Injection 風險 | **高** | `map.js`, `avatar-service.js` | ✅ 已修復 |

---

## 🐛 修復詳情

### 問題 1：Potential Infinite Re-render in `toggleChapter`

**症狀**：
當使用者快速切換章節時，`toggleChapter` 會自動呼叫 `selectStory`，而 `selectStory` 又會觸發 `updateSummaryContent()`，導致不必要的重複渲染。

**修復位置**：`map.js`

**修改內容**：
- 在 `toggleChapter` 中，分離了 UI 狀態更新與 Story 選擇邏輯
- 確保在展開/收合章節時，不會觸發額外的渲染回調
- 優化了 DOM 操作順序，減少 reflow 次數

---

### 問題 2：Race Condition in `render()`

**症狀**：
`render()` 在設定 `innerHTML` 後立即呼叫 `selectStory`，此時 DOM 可能尚未完全更新，可能導致選擇無效或 JavaScript 錯誤。

**修復位置**：`map.js`

**修改內容**：
- 加入 `isRendering` 鎖定旗標，防止重複渲染
- 使用 `setTimeout(..., 0)` 確保 DOM 更新完成後再執行 `selectStory`
- 使用 `try...finally` 確保鎖定旗標一定會被重置

```javascript
// 修復前
this.selectStory(this.chapters[this.expandedChapter][0].id);

// 修復後
setTimeout(() => {
    this.selectStory(this.chapters[this.expandedChapter][0].id);
}, 0);
```

---

### 問題 3：Missing Error Handling in `loadData()`

**症狀**：
`loadData()` 在查詢 `unit_data` 表時，沒有先檢查表格是否存在，若資料庫結構不完整會直接拋出未捕獲的錯誤。

**修復位置**：`map.js`

**修改內容**：
- 在查詢 `unit_data` 前，先執行 `sqlite_master` 檢查
- 若表格不存在，印出警告並優雅地跳過頭像預載入
- 確保即使部分資料缺失，模組仍能正常運作

---

### 問題 4：XSS (Cross-Site Scripting) 安全漏洞

**症狀**：
多處動態插入 HTML 的變數未經編碼，包含使用者可控輸入（搜尋值、角色名稱、劇情標題等），可能導致 XSS 攻擊。

**修復位置**：`map.js`, `avatar-service.js`

**修改內容**：
- 在 `QuestMapModule` 中加入 `escapeHtml()` 輔助函數
- 在 `AvatarService` 中加入 `escapeHtml()` 輔助函數
- 對所有動態插入的變數進行 HTML 實體編碼：
  - `searchVal`, `name`, `realName`, `chKey`, `chTitle`
  - `s.chapter`, `s.title`, `displayChapterName`
  - `officialSummary`, `summaryText`
  - `speaker`, `words`（對白文本）

```javascript
escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
```

---

### 問題 5：記憶體洩漏 (Memory Leak in Modal)

**症狀**：
`showCharaModal` 動態建立的 modal DOM 在關閉時僅被隱藏 (`classList.remove('active')`)，而非從 DOM 中移除，長期使用會累積無用節點。

**修復位置**：`map.js`

**修改內容**：
- 將關閉邏輯改為 `modalEl.remove()` 移除 DOM
- 更新 `onclick` 事件與關閉按鈕的呼叫方式
- 確保 `jumpToStory` 中的關閉邏輯也同步更新

---

### 問題 6：資料庫初始化錯誤處理不一致

**症狀**：
當 `verifyDatabase()` 失敗時，雖然拋出錯誤，但已建立的 `this.db` 實例未被清除，可能導致後續操作在無效資料庫上執行。

**修復位置**：`db.js`

**修改內容**：
- 在拋出錯誤前，先將 `this.db = null`
- 確保無效的資料庫連接不會被後續使用

```javascript
if (this.verifyDatabase()) {
    await this.saveToIDB(dbKey, dbData);
    return this.db;
} else {
    this.db = null; // 清除無效的資料庫實例
    throw new Error("載入的資料庫格式有誤...");
}
```

---

### 問題 7：載入狀態未重置

**症狀**：
`loadDialogue` 在發生錯誤時，沒有重置載入狀態，導致使用者快速切換劇情時，可能會看到上一個劇情的錯誤訊息殘留。

**修復位置**：`map.js`

**修改內容**：
- 加入 `isLoadingDialogue` 鎖定旗標
- 在 `try...finally` 中確保狀態一定會被重置
- 防止重複請求打斷正在進行的載入

---

### 問題 8：CSS Injection 風險

**症狀**：
動態生成的 `onerror` 處理器與 `style` 屬性中，字串跳脫不完善，若角色名稱包含特殊字元（如反斜線），可能破壞 HTML 結構。

**修復位置**：`map.js`, `avatar-service.js`

**修改內容**：
- 在 `AvatarService` 中加入 `escapeForJsString()` 輔助函數
- 正確處理反斜線跳脫：`replace(/\\/g, "\\\\")`
- 對所有插入 `onerror` 的字串進行統一跳脫

```javascript
escapeForJsString(str) {
    if (!str) return "";
    return String(str)
        .replace(/\\/g, "\\\\")  // 先處理反斜線
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"');
}
```

---

## 📁 修改檔案清單

| 檔案 | 修改行數 | 修改類型 |
|------|---------|---------|
| `map.js` | ~150 行 | 新增輔助函數、修正 XSS、修正競態條件、修正記憶體洩漏 |
| `db.js` | ~3 行 | 修正初始化錯誤處理 |
| `avatar-service.js` | ~40 行 | 新增輔助函數、修正 XSS |

---

## ✅ 驗證建議

1. **功能測試**：
   - 切換主線/活動/登場角色三個分頁
   - 搜尋角色名稱（包含特殊字元如 `<`, `>`, `"`）
   - 點擊不同章節，確認渲染正常

2. **安全性測試**：
   - 在搜尋框輸入 `<script>alert('XSS')</script>`，確認不會執行
   - 檢查瀏覽器開發者工具 Console，確認無 HTML 解析錯誤

3. **效能測試**：
   - 快速切換章節，確認無重複渲染
   - 開啟/關閉角色 modal 多次，確認 DOM 節點數量穩定

---

## 📝 備註

- 所有修改遵循「最小侵入原則」，僅修復邏輯問題，未改變原有功能設計
- 新增輔助函數 (`escapeHtml`, `escapeForJsString`) 可重複使用，建議後續開發時繼續採用
- 本次修復未涉及 `style.css` 或 `index.html`

## 🗓️ 修改日期

2025-06-09