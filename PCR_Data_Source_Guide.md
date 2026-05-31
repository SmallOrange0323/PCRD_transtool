# PCR 台服數據源技術指南

> 本文件說明如何在瀏覽器環境中取得《公主連結 Re:Dive》台版的遊戲數據，適合有 JavaScript 基礎的開發者閱讀。

---

## 一、數據來源概覽

`wthee.xyz` 是目前最完整的 PCR 數據源，提供台版完整 SQLite 資料庫下載。

> [!WARNING]
> `wthee.xyz` 的 REST API 有 **App 版本鎖定**，無法從瀏覽器直接呼叫。**請勿**嘗試呼叫其 API endpoint。
> 正確的方式是**直接下載 SQLite 資料庫**，在瀏覽器端用 sql.js 查詢。

### 可用資源 URL

| 資源 | URL |
|------|-----|
| 台服完整資料庫（Brotli 壓縮） | `https://wthee.xyz/db/redive_tw.db.br` |
| 台服資料庫（未壓縮，約 **13MB**） | `https://wthee.xyz/db/redive_tw.db` |
| Boss 圖片（WebP） | `https://redive.estertion.win/icon/unit/{id}31.webp` |
| Boss 備用圖片 | `https://redive.estertion.win/icon/unit/{id}61.webp` |

---

## 二、在瀏覽器中開啟資料庫

### 技術棧需求

```html
<!-- sql.js：瀏覽器端 SQLite 引擎 (WebAssembly) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js"></script>

<!-- Brotli 解壓（如果要讀 .br 壓縮版本） -->
<script src="https://cdn.jsdelivr.net/npm/brotli-dec-wasm@1.3.2/brotli_dec.js"></script>
```

### 初始化 sql.js

`sql.js` 依賴一個 `.wasm` 二進位檔，必須告訴它去哪裡找：

```javascript
const SQL = await initSqlJs({
    locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
});
```

### 下載並載入資料庫

```javascript
async function loadDatabase() {
    // 直接下載未壓縮版本（約 13MB，實測值）
    const response = await fetch('https://wthee.xyz/db/redive_tw.db');
    const buffer = await response.arrayBuffer();

    // 用 sql.js 開啟
    const db = new SQL.Database(new Uint8Array(buffer));
    return db;
}
```

> [!IMPORTANT]
> 由於瀏覽器的 CORS 安全機制，**必須透過 HTTP 伺服器開啟頁面**，不能用 `file://` 直接開啟 HTML 檔案。
> 最簡單的本機方式是使用 VS Code 的 **Live Server** 擴充套件。

---

## 三、執行 SQL 查詢

載入資料庫後，就可以用標準 SQL 語法查詢任何數據。

```javascript
function runQuery(db, sql, params = []) {
    const stmt = db.prepare(sql);
    stmt.bind(params);
    const results = [];
    while (stmt.step()) {
        results.push(stmt.getAsObject());
    }
    stmt.free();
    return results; // 回傳格式：[{column1: value1, ...}, ...]
}

// 使用範例
const bosses = runQuery(db, `
    SELECT name, hp, atk FROM enemy_parameter WHERE hp > 1000000
`);
console.log(bosses);
// 輸出：[{ name: 'ペコリーヌ', hp: 5000000, atk: 123456 }, ...]
```

---

## 四、重要資料表結構

### 公會戰（戰隊戰）

```sql
-- 公會戰期程
clan_battle_schedule
├── clan_battle_id  INTEGER  (期數)
├── release_month   INTEGER  (月份，格式 YYYYMM，如 202504)
└── start_time      TEXT     (開始時間，格式 "2025/04/01 05:00:00")

-- 各階段 Boss 配置（哪個階段用哪組 Boss）
clan_battle_2_map_data
├── clan_battle_id  INTEGER
├── phase           INTEGER  (階段 1=甲, 2=乙, 3=丙, 4=丁...)
├── lap_num_from    INTEGER  (從第幾刀進入此階段)
└── wave_group_id_1 ~ wave_group_id_5  INTEGER  (Boss 群組 ID)

-- Boss 能力值
enemy_parameter
├── enemy_id        INTEGER
├── unit_id         INTEGER
├── name            TEXT     (Boss 名稱，日文)
├── hp              INTEGER
├── atk             INTEGER  (物理攻擊)
├── magic_str       INTEGER  (魔法攻擊)
├── def             INTEGER  (物理防禦)
└── magic_def       INTEGER  (魔法防禦)

-- Boss 圖片對應
unit_enemy_data
├── unit_id         INTEGER
└── prefab_id       INTEGER  (用來組 Boss 圖片 URL 的 ID)
```

### 活動

```sql
-- 劇情活動時程
hatsune_schedule
├── event_id        INTEGER
├── start_time      TEXT
└── end_time        TEXT

-- 活動名稱
event_story_data
├── story_group_id  INTEGER  (= event_id % 10000 + 5000)
└── title           TEXT

-- 加倍活動
campaign_schedule
├── campaign_category INTEGER  (類型代碼)
├── value           INTEGER  (倍率，如 150 = 1.5x)
├── start_time      TEXT
└── end_time        TEXT
```

---

## 五、實用查詢範例

### 取得最新一期公會戰所有階段的 Boss

```sql
SELECT
    a.phase,
    e.name AS boss_name,
    e.hp, e.atk, e.magic_str, e.def, e.magic_def,
    f.prefab_id
FROM
    clan_battle_2_map_data AS a
    LEFT JOIN wave_group_data AS c ON c.wave_group_id = a.wave_group_id_1
    LEFT JOIN enemy_parameter AS e ON c.enemy_id_1 = e.enemy_id
    LEFT JOIN unit_enemy_data AS f ON e.unit_id = f.unit_id
WHERE
    a.clan_battle_id = (SELECT MAX(clan_battle_id) FROM clan_battle_schedule)
ORDER BY a.phase ASC, a.lap_num_from ASC
```

### 取得進行中和即將到來的活動

```sql
SELECT
    event.event_id,
    event.start_time,
    event.end_time,
    COALESCE(c.title, '特殊活動') AS title
FROM (
    SELECT event_id, start_time, end_time FROM hatsune_schedule
    UNION
    SELECT event_id, start_time, end_time FROM shiori_event_list
) AS event
LEFT JOIN event_story_data AS c ON c.story_group_id = (event.event_id % 10000 + 5000)
ORDER BY event.start_time DESC
LIMIT 30
```

---

## 六、Boss 圖片 URL 計算

```javascript
function getBossImageUrl(prefabId) {
    // prefab_id 補零至 6 位數，再加上 "31"
    // 例如：prefabId = 170101 → URL = .../17010131.webp
    const paddedId = String(prefabId).padStart(6, '0');
    const primary   = `https://redive.estertion.win/icon/unit/${paddedId}31.webp`;
    const fallback  = `https://redive.estertion.win/icon/unit/${paddedId}61.webp`;
    return { primary, fallback };
}

// 在 HTML 中使用，搭配錯誤降級：
// <img src="{primary}" onerror="this.src='{fallback}'">
```

---

## 七、快取策略（避免重複下載）

```javascript
const CACHE_KEY   = 'pcr_tw_db_cache';
const TIMESTAMP   = 'pcr_tw_db_timestamp';
const CACHE_TTL   = 24 * 60 * 60 * 1000; // 24 小時

async function getDatabase() {
    const ts = localStorage.getItem(TIMESTAMP);
    if (ts && Date.now() - parseInt(ts) < CACHE_TTL) {
        // 從 IndexedDB 讀取快取
        const cached = await loadFromIDB(CACHE_KEY);
        if (cached) return new SQL.Database(new Uint8Array(cached));
    }

    // 重新下載並儲存
    const buf = await fetch('https://wthee.xyz/db/redive_tw.db').then(r => r.arrayBuffer());
    await saveToIDB(CACHE_KEY, buf);
    localStorage.setItem(TIMESTAMP, Date.now().toString());
    return new SQL.Database(new Uint8Array(buf));
}
```

> [!TIP]
> `wthee.xyz` 的資料庫更新頻率**尚未有官方說明**。實測 `Last-Modified` header 顯示更新時間約在台灣時間下午，但不確定是否每天更新或跟隨遊戲版本更新。
> 建議快取時效設定為 **24 小時**，若想確保取得最新數據，可在 UI 提供「強制刷新」功能（清除 localStorage 時間戳並重新下載）。
> 
> 如需確認實際更新時間，可在每次載入時比對 HTTP Response 的 `Last-Modified` header 與上次快取的時間戳。

---

## 八、時間格式注意事項

資料庫內的時間格式為斜線分隔：`"2025/04/01 05:00:00"`

```javascript
// 必須先轉換才能被 new Date() 正確解析
const dateStr = "2025/04/01 05:00:00";
const date = new Date(dateStr.replace(/\//g, '-'));
// → "2025-04-01 05:00:00" ✅
```

所有活動時間皆為**台灣時間（UTC+8）**。
