# PCR 台版數據導航站 — Flash 執行交接文件

> **給 Flash 的說明**：這份文件包含你需要知道的所有背景知識與精確指令，請你照著「任務清單」依序完成所有文件的建立與撰寫。

---

## 一、專案背景

**目標**：在現有的 PCRD_tool 專案中，新增一個 `dashboard/` 目錄，實作兩個功能頁面：
1. **戰隊戰 Boss 資訊** — 顯示最新一期公會戰的 Boss 名稱、圖片、各階段血量、防禦、攻擊力
2. **活動日曆** — 顯示正在進行中與即將到來（預告）的活動

**現有工具位置**：`e:\OneDrive - 寰宇知識科技股份有限公司\PCRD_tool\`
- `index.html` / `index.css` / `index.js` — 戰隊戰作業轉換工具（**不要修改它**）

---

## 二、技術方案（最重要，請完整理解）

### 數據來源

`wthee.xyz` 的 REST API 有 App 版本鎖定，**無法從瀏覽器直接呼叫**。
正確的方式是：**直接下載 SQLite 資料庫文件，在瀏覽器中用 sql.js 查詢**。

| 資源 | URL |
|------|-----|
| 台服完整資料庫（Brotli 壓縮） | `https://wthee.xyz/db/redive_tw.db.br` |
| Boss 圖片（unit_id 加 31，WebP 格式） | `https://redive.estertion.win/icon/unit/{prefab_id_padded}31.webp` |
| Boss 圖片備用格式 | `https://redive.estertion.win/icon/unit/{prefab_id_padded}61.webp` |

**圖片 ID 計算規則**：`prefab_id` 補零至 6 位數，例如 `prefab_id = 170101` → URL 為 `17010131.webp`

### 解壓技術

瀏覽器原生支援 `DecompressionStream`，但**只支援 gzip 和 deflate-raw，不支援 brotli**。

因此需要使用 `brotli-dec-wasm` 或 `brotli.js` 這類 CDN 函式庫來解壓 `.br` 文件。

**推薦的 CDN 方案**：使用 `https://cdn.jsdelivr.net/npm/brotli-dec-wasm@1.3.2/brotli_dec.js` 這個 JS 函式庫。

> **備用降級方案（更簡單）**：如果 brotli 解壓失敗，可以嘗試直接 fetch `https://wthee.xyz/db/redive_tw.db`（無壓縮版本），如果 HTTP 回傳 200，就直接用。如果不行，才使用 brotli 解壓。

### 前端技術棧
- **Vanilla HTML + CSS + JS**（不使用任何 框架）
- **sql.js** (WebAssembly SQLite)：`https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js`
  - sql-wasm.wasm 需要指定路徑：`https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.wasm`
- **字體**：Google Fonts `Noto Sans TC` + `Outfit`

### 快取策略

- 資料庫文件下載後，儲存在 **IndexedDB** （key: `pcr_tw_db_cache`）
- 同時在 **localStorage** 儲存下載時間戳（key: `pcr_tw_db_timestamp`）
- **24 小時內**使用快取，超過則重新下載
- 第一次載入時顯示「正在下載資料庫…」進度提示

---

## 三、資料庫表結構（從 pcr-tool 原始碼分析）

### 戰隊戰相關表

```
clan_battle_schedule
  - clan_battle_id  INTEGER  (期數 ID)
  - release_month   INTEGER  (月份，如 2025 → 25年，不含年份; 格式: YYYYMM, 如 202501)
  - start_time      TEXT     (開始時間，格式: "2025/01/01 05:00:00")

clan_battle_2_map_data
  - clan_battle_id  INTEGER
  - phase           INTEGER  (階段: 1, 2, 3, 4...)
  - lap_num_from    INTEGER  (從第幾刀開始此階段)
  - wave_group_id_1 ~ wave_group_id_5  INTEGER

wave_group_data
  - wave_group_id   INTEGER
  - enemy_id_1      INTEGER  (boss 的 enemy_id，公會戰通常只有 1 個主 boss)

enemy_parameter
  - enemy_id        INTEGER
  - unit_id         INTEGER
  - name            TEXT     (boss 名稱)
  - level           INTEGER
  - hp              INTEGER  (血量)
  - atk             INTEGER  (物理攻擊)
  - magic_str       INTEGER  (魔法攻擊)
  - def             INTEGER  (物理防禦)
  - magic_def       INTEGER  (魔法防禦)
  - physical_critical INTEGER
  - accuracy        INTEGER

unit_enemy_data
  - unit_id         INTEGER
  - prefab_id       INTEGER  (用來組合圖片 URL 的 ID)
  - comment         TEXT     (boss 描述)
```

### 活動相關表

```
hatsune_schedule  (劇情活動時程)
  - event_id        INTEGER
  - start_time      TEXT     (格式: "2025/01/01 05:00:00")
  - end_time        TEXT

event_story_data  (活動標題)
  - story_group_id  INTEGER  (= event_id % 10000 + 5000)
  - title           TEXT

campaign_schedule  (加倍活動)
  - campaign_category INTEGER
  - value           INTEGER  (倍率，如 150 表示 1.5x)
  - start_time      TEXT
  - end_time        TEXT
```

---

## 四、關鍵 SQL 查詢（已驗證正確性）

### SQL 1：取得最新一期公會戰各階段 Boss 列表

```sql
SELECT
    a.clan_battle_id,
    a.phase,
    a.lap_num_from,
    b.release_month,
    b.start_time AS battle_start,
    e.enemy_id,
    e.name AS boss_name,
    e.hp,
    e.atk,
    e.magic_str,
    e.def,
    e.magic_def,
    f.unit_id,
    f.prefab_id,
    f.comment
FROM
    clan_battle_2_map_data AS a
    LEFT JOIN clan_battle_schedule AS b ON b.clan_battle_id = a.clan_battle_id
    LEFT JOIN wave_group_data AS c ON c.wave_group_id = a.wave_group_id_1
    LEFT JOIN enemy_parameter AS e ON c.enemy_id_1 = e.enemy_id
    LEFT JOIN unit_enemy_data AS f ON e.unit_id = f.unit_id
WHERE
    (a.lap_num_from > 1 OR a.clan_battle_id < 1011)
    AND b.release_month IS NOT NULL
    AND a.clan_battle_id = (
        SELECT MAX(clan_battle_id) FROM clan_battle_schedule
    )
ORDER BY
    a.phase ASC,
    a.clan_battle_id DESC
```

### SQL 2：取得最近的活動列表（含進行中與預告）

```sql
SELECT
    event.event_id,
    event.start_time,
    event.end_time,
    COALESCE(c.title, '特殊活動') AS title
FROM (
    SELECT a.event_id, a.start_time, a.end_time
    FROM hatsune_schedule AS a
    UNION
    SELECT b.event_id, b.start_time, b.end_time
    FROM shiori_event_list AS b
) AS event
LEFT JOIN event_story_data AS c ON c.story_group_id = (event.event_id % 10000 + 5000)
ORDER BY event.start_time DESC
LIMIT 30
```

### SQL 3：確認最新一期公會戰日程（含結束時間估算）

```sql
SELECT
    clan_battle_id,
    release_month,
    start_time
FROM clan_battle_schedule
ORDER BY clan_battle_id DESC
LIMIT 3
```

---

## 五、文件結構（你需要建立的文件）

```
PCRD_tool/
└── dashboard/
    ├── index.html      ← 主頁面（Navbar + Tab 切換）
    ├── style.css       ← 美學樣式
    ├── db.js           ← DB 下載/快取/查詢引擎
    ├── clan-battle.js  ← 公會戰頁面邏輯
    └── events.js       ← 活動頁面邏輯
```

---

## 六、UI 設計規格

### 整體風格
- **Dark Mode 背景**：`#0a0e1a`（深藍黑色）
- **玻璃擬態卡片**：`background: rgba(255,255,255,0.05)`, `backdrop-filter: blur(12px)`, `border: 1px solid rgba(255,255,255,0.1)`
- **強調色**：粉橘漸層 `linear-gradient(135deg, #ff6b9d, #ffa94d)`（呼應 PCR 遊戲風格）
- **字體**：`Outfit`（英數）+ `Noto Sans TC`（中文）

### Navbar 設計
- 左側：PCRD Logo 文字 + ⚔️ 圖示
- 中間：兩個 Tab 按鈕（戰隊戰、活動）
- 右上：「回到工具」連結（導向 `../index.html`）
- Tab 切換有底部滑動指示器動畫

### 戰隊戰 Boss 卡片設計
- 頁面頂部：當期月份標題 + 開始時間，公會戰結束時間（開始日期加5天，時間減5小時減1秒）
- Boss 以**水平滾動橫列**排列（1~5號 Boss）
- 每張卡片包含：
  - Boss 圖片（圓形頭像，帶發光邊框）
  - Boss 名稱（置中）
  - **階段切換 Tab**（甲/乙/丙/丁等，由 phase 決定）
  - 數據表格：HP、物攻、魔攻、物防、魔防
- 切換階段時，卡片數據有淡入淡出動畫

### 活動頁面設計
- 分為兩個區塊：「📡 進行中」和「📅 即將到來」
- 以目前時間（台灣時區，UTC+8）判斷活動狀態
- 進行中的活動顯示剩餘天數倒數（綠色）
- 即將到來的活動顯示開始倒數（藍色）
- 超過 60 天後的活動不顯示（視為過期預告）

---

## 七、db.js 的核心邏輯（詳細說明）

```javascript
// db.js 需要實作以下功能：

// 1. 初始化函式（頁面載入時呼叫）
async function initDatabase(onProgress) {
  // Step 1: 檢查 localStorage 的時間戳
  // Step 2: 若快取有效（24小時內），從 IndexedDB 讀取 DB 二進位資料
  // Step 3: 若快取失效或不存在，從 wthee.xyz 下載
  // Step 4: 下載後用 brotli 函式庫解壓
  // Step 5: 用 sql.js 載入解壓後的 Uint8Array
  // Step 6: 將 DB 存入 IndexedDB，更新時間戳
  // 返回 sql.js 的 Database 物件
}

// 2. 查詢函式（供各頁面呼叫）
function runQuery(db, sql, params = []) {
  // 執行 SQL，將結果轉換為 JS 物件陣列
  // 返回格式: [{column1: value1, column2: value2, ...}, ...]
}

// 3. IndexedDB 存取
async function saveToIDB(data) { /* 儲存 ArrayBuffer 到 IDB */ }
async function loadFromIDB() { /* 從 IDB 讀取 ArrayBuffer */ }
```

**Brotli 解壓方法**（使用 `brotli-dec-wasm`）：
```javascript
// 引入：<script src="https://cdn.jsdelivr.net/npm/brotli-dec-wasm@1.3.2/brotli_dec.js"></script>
// 使用：
const { BrotliDecode } = await import('brotli-dec-wasm');
// 或是 CDN 版本會掛在 window.brotliDec 上
const uint8Array = brotliDec.decompress(compressedData);
```

---

## 八、圖片 URL 計算方式

```javascript
function getBossImageUrl(prefabId) {
    // prefab_id 通常是 6 位數，例如 170101
    // 圖片名稱 = prefab_id + "31" (一般站立圖)
    const paddedId = String(prefabId).padStart(6, '0');
    return `https://redive.estertion.win/icon/unit/${paddedId}31.webp`;
}

// 如果 prefab_id 是 0 或無效，顯示預設圖片
// 備用圖片: https://redive.estertion.win/icon/unit/unknown.webp
// 或用 CSS 顯示一個帶有問號的灰色圓形
```

---

## 九、任務清單（請按順序執行）

- [ ] **任務 1**：建立 `dashboard/` 目錄，建立 `dashboard/db.js`
  - 實作 IndexedDB 存取函式（`saveToIDB`, `loadFromIDB`）
  - 實作 brotli 下載+解壓+sql.js 載入的完整流程（`initDatabase`）
  - 實作 `runQuery` 工具函式
  - 在 `window` 上暴露 `PCRDatabase` 物件，包含 `initDatabase` 和 `runQuery`

- [ ] **任務 2**：建立 `dashboard/clan-battle.js`
  - 呼叫 `PCRDatabase.runQuery` 執行 SQL 1 和 SQL 3
  - 組合各期各階段的 Boss 資料
  - 渲染 Boss 卡片 HTML（含圖片、名稱、數據）
  - 實作階段切換互動邏輯

- [ ] **任務 3**：建立 `dashboard/events.js`
  - 呼叫 `PCRDatabase.runQuery` 執行 SQL 2
  - 用目前時間（UTC+8）判斷「進行中」vs「即將到來」
  - 渲染活動卡片 HTML（含標題、時間、倒數）

- [ ] **任務 4**：建立 `dashboard/style.css`
  - 實作所有 UI 設計規格（第六節）
  - Dark Mode 背景、玻璃擬態卡片、強調色漸層
  - Navbar 樣式（含 Tab 滑動指示器）
  - Boss 卡片樣式（含圖片圓形邊框、數據表格）
  - 活動卡片樣式（含進行中/預告狀態標籤）
  - 動畫：載入進度、Tab 切換淡入淡出、hover 效果

- [ ] **任務 5**：建立 `dashboard/index.html`
  - 引入所有 CDN 資源（sql.js, brotli-dec-wasm, Google Fonts）
  - 建立 Navbar 結構
  - 建立兩個 Tab 的容器 (`#clan-battle-tab`, `#events-tab`)
  - 建立載入進度條 (`#loading-overlay`)
  - 引入 `db.js`, `clan-battle.js`, `events.js`
  - 在 `DOMContentLoaded` 時呼叫 `initDatabase`，成功後分別呼叫各頁面的渲染函式

---

## 十、驗收標準

1. 用 VSCode 的 Live Server（或任何本地 HTTP Server）開啟 `dashboard/index.html`
2. 頁面應顯示「正在下載資料庫…」的載入覆蓋層
3. 下載完成（約 2-5 秒）後，「戰隊戰」Tab 應顯示：
   - 頂部有當期月份與時間範圍
   - 至少 1 隻 Boss 卡片，有圖片（或預設圖）、名稱、HP 數值
   - 可切換階段（如甲/乙/丙/丁）
4. 切換到「活動」Tab，應顯示活動列表，分為「進行中」與「即將到來」兩區
5. 瀏覽器 Console 不應有未處理的錯誤（網路錯誤除外）
6. 第二次開啟頁面時，應從 IndexedDB 讀取快取，載入速度明顯更快

---

## 十一、注意事項與陷阱

1. **CORS 問題**：`wthee.xyz` 的資源有設定 CORS header，允許跨域，可以直接 fetch。
   但如果用 `file://` 協議開啟 HTML，fetch 會被瀏覽器阻止。必須透過 HTTP Server。
   → 在 `index.html` 頂部加入一個醒目提示框，說明需要用 Live Server 開啟。

2. **sql.js 的 wasm 路徑**：sql.js 需要額外的 `.wasm` 文件，必須指定 `locateFile`：
   ```javascript
   const SQL = await initSqlJs({
     locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
   });
   ```

3. **公會戰結束時間**：資料庫沒有直接儲存結束時間，計算方式是「開始時間加 5 天，時間減 5 小時減 1 秒」。

4. **活動時間格式**：資料庫中的時間格式是 `"2025/01/15 05:00:00"`（斜線分隔，非破折號），需注意 JS Date 的解析。
   → 建議用 `.replace(/\//g, '-')` 轉換後再用 `new Date()` 解析。

5. **台灣時區**：所有時間比較請統一用 UTC+8，可用 `new Date().toLocaleString('en-US', {timeZone: 'Asia/Taipei'})` 處理。

6. **Boss 圖片可能不存在**：部分 Boss 的 prefab_id 可能無法對應到圖片，需要用 `onerror` fallback：
   ```html
   <img src="..." onerror="this.src='fallback.png'">
   ```
   fallback 可以用 CSS 純色圓形取代。

7. **brotli-dec-wasm CDN**：如果這個套件的 CDN 無法使用，備用方案是直接測試下載 `.db` 未壓縮版本（URL 去掉 `.br`）。
