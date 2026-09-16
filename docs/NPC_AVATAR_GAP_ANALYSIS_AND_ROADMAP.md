# PCRD Story Map NPC 頭像覆蓋缺口分析與規格規整化設計 (RFC)

**文件代號**：`RFC-20260916-NPC-AVATAR-GAP`  
**建立日期**：2026-09-16  
**規格收斂日期**：2026-09-16（正式規格鎖定，作為後續實作之權威依據）  
**狀態**：`ACCEPTED SPECIFICATION / READY FOR IMPLEMENTATION`  
**適用範疇**：`pipeline/`（資料更新管線）、`tools/pcrd_fetch.py`（劇理解包器）、`dashboard/data/`（資產登錄表）

---

## 摘要 (Executive Summary)

在《公主連結 Re:Dive》劇情導航站（Story Map）中，讀者與維護者反映大量劇情配角與 NPC 僅能顯示粉紅色文字佔位符（如「秘書」、「摩拉」、「米亞」）。經排除非對白項目（`still` 劇情插畫、`background` 背景切換、`movie` 動畫標記及純空白行）之精確審計，確認：

1. **官方 CDN 資源池與登錄現況**：
   - 官方 CDN 的 `storydata2_assetmanifest` 儲備了 **1,472 個官方立繪頭像 Bundle**。
   - 現有 `avatar_assets.json` 登錄有 934 個 ID（其中 926 個屬於此池，8 個屬於池外特殊項目）。
   - 官方 CDN 尚有 **546 個頭像 Bundle 處於未開採狀態**，其中 **463 個屬於官方前導補零（`0xxxxx`）的特殊 NPC / 配角 / 怪物 ID**。
2. **目前前端解析覆蓋率**：
   - 全站 9,096 篇正規劇情中，真正實質對白總數為 **1,221,991 行**。
   - **Current UI Avatar Resolution Coverage（目前 UI 頭像可解析率）** 為 **84.17%（1,028,524 行）**。
   - **降級為文字方塊之對白 (Placeholder Rows)** 達 **193,467 行（佔 15.83%）**。
3. **架構核心定案 (Locked Architectural Decisions)**：
   - **否定單一名字映射**：`npc_avatars.json` 單一名字映射無法處理同一 NPC 在不同活動的換裝造型（例如秘書之常態 `006111` vs 泳裝 `006112`）。
   - **Canonical Contract 鎖定**：確立 `command unit_id: integer`（如 `6112`）、`official asset_key: six-digit string`（如 `"006112"`）、`filename: "006112.png"` 的標準契約，不再進行型別二選一討論。
   - **Closed-Universe Manifest Gate**：短 ID（`< 100000`）的合法性不得依賴數值或位數，必須透過 `zfill(6)` 在權威 `storydata2_assetmanifest` 中確認存在對應 Bundle 始得採納。

---

## 一、 客觀數據審核與集合關係 (Empirical Audit & Set Relations)

### 1. 官方 CDN 與資產庫之精確集合關係

經對 So-net 官方 `storydata2_assetmanifest` 與本地 `dashboard/data/avatar_assets.json` 進行嚴格之集合交集運算：

```text
┌─────────────────────────────────────────────────────────────┐
│                   Asset Pool Set Relations                  │
├─────────────────────────────────────────────┬───────────────┤
│ CDN pool total (storydata_icon_unit_*)      │ 1,472         │
│ Registry total (avatar_assets.json unique)  │   934         │
│ Registry ∩ CDN pool                         │   926         │
│ CDN missing from registry (1,472 - 926)     │   546         │
│ Registry outside CDN pool (934 - 926)       │     8         │
└─────────────────────────────────────────────────────────────┘
```

> **集合關係說明**：
> `avatar_assets.json` 中現存的 934 筆 ID，並非 100% 來自 `storydata2_assetmanifest`。其中有 8 筆屬於池外資產（包含 3 筆 `placeholder_only` 無圖差分 `[105921, 106913, 190813]`，以及 5 筆特定 UI/追蹤角色資產 `[138931, 139031, 139131, 195511, 195512]`）。
> 因此，官方 CDN 未開採缺口為 **$1,472 - 926 = 546$ 個**，不能單純使用 $1,472 - 934$ 計算。

### 2. CDN 1,472 個資源池結構拆解

| 資源分類區段 | 命名模式 | Bundle 數量 | 實體內容說明 |
| :--- | :--- | :---: | :--- |
| **前導補零特例區** | `storydata_icon_unit_0xxxxx.unity3d` | **463 個** | 特殊劇情 NPC、專屬配角（如秘書）、各行會路人、特定魔物、村民 |
| **標準劇情 NPC 區** | `storydata_icon_unit_19xxxx.unity3d` | **88 個** | 主線第二部/第三部具名核心 NPC（如八斗神 `193611`、羅蘭 `194212`） |
| **可玩角色與換裝區** | `storydata_icon_unit_{10-18}xxxx.unity3d` | **921 個** | 可玩角色之常態、換裝（泳裝、新年、女武神等）、星級差分 |

---

## 二、 對白覆蓋率指標語意與基準 (Dialogue Coverage Semantics)

本次統計母體嚴格排除 `still`（劇情插畫）、`background`（背景切換）、`movie`（過場動畫）以及無實質台詞之空行氣泡：

* **全量正規話數 (Total Stories)**：**9,096 篇**
* **實質對白總行數 (Total Dialogue Rows)**：**1,221,991 行**
* **可解析頭像對白行數 (Resolvable Avatar Rows)**：**1,028,524 行（84.17%）**
* **降級為文字方塊行數 (Placeholder Rows)**：**193,467 行（15.83%）**
* **涉及降級之獨立發言標籤總數**：**3,348 個**

> [!IMPORTANT]
> **指標語意精確界定 (Coverage Semantics Boundary)**：
> **84.17% 的指標名稱為「Current UI Avatar Resolution Coverage」（目前 UI 頭像可解析率）**。
> 此比例代表依照目前 Story Map 前端解析規則，該對白可以解析到某個 active avatar。其中**同時包含**：
> 1. 顯式 `unit_id` 的精確立繪解析；
> 2. `npc_avatars.json` 名稱 fallback 解析。
> 
> 因此，**84.17% 不等同於官方 command stream 的 exact appearance coverage（官方精確造型覆蓋率）**，亦不保證 fallback 解析出的頭像與劇中當下服裝／形態完全一致。

---

## 三、 高頻文字方塊發言排行統計

### 1. 高頻文字方塊發言標籤排行 (Top 20 Placeholder Speaker Labels)

包含全量未被頭像解析的發言人字串（含角色分類、泛用稱謂與群體標籤）：

| 排名 | 發言標籤 (Speaker Label) | 實質對白句數 | 性質分類 |
| :---: | :--- | :---: | :--- |
| 1 | **旁白** | 18,987 句 | 系統旁白 |
| 2 | **？？？** | 4,761 句 | 未知發言者 |
| 3 | **男性** | 3,937 句 | 泛用路人分類標籤 |
| 4 | **女性** | 2,923 句 | 泛用路人分類標籤 |
| 5 | **店長** | 2,479 句 | 職稱稱謂（含多個行會店長） |
| 6 | **女子** | 2,466 句 | 泛用路人分類標籤 |
| 7 | **摩拉** | 2,420 句 | 具名角色（主線重要妖精） |
| 8 | **男子** | 2,001 句 | 泛用路人分類標籤 |
| 9 | **米亞** | 1,749 句 | 具名角色 |
| 10 | **秘書** | 1,741 句 | 具名角色（克蕾琪塔的秘書） |
| 11 | **美穗** | 1,740 句 | 具名角色 |
| 12 | **和正** | 1,559 句 | 具名角色 |
| 13 | **男性１** | 1,498 句 | 泛用序號標籤 |
| 14 | **波波爺爺** | 1,446 句 | 具名角色 |
| 15 | **貴族** | 1,428 句 | 身分稱謂 |
| 16 | **奶奶** | 1,367 句 | 泛用親屬/稱謂 |
| 17 | **瑪麗亞** | 1,277 句 | 具名角色 |
| 18 | **司儀** | 1,250 句 | 職稱稱謂 |
| 19 | **老奶奶** | 1,236 句 | 泛用稱謂 |
| 20 | **輝美** | 1,210 句 | 具名角色 |

### 2. 高頻具名文字方塊角色排行 (Top 20 Named Placeholder Characters)

排除泛用身分稱謂（男子、女子、店長、司儀、長老、父親、奶奶等）與群體雜訊後，全站台詞量最高之真實具名角色如下：

| 排名 | 具名角色 (Named Character) | 實質對白句數 | 官方 CDN 是否有對應 AssetBundle |
| :---: | :--- | :---: | :--- |
| 1 | **摩拉** | 2,420 句 | 待清查 |
| 2 | **米亞** | 1,749 句 | 待清查 |
| 3 | **秘書**（克蕾琪塔的秘書） | **1,741 句** | **VERIFIED：官方存在 `006111`（常態）與 `006112`（泳裝）** |
| 4 | **美穗** | 1,740 句 | 待清查 |
| 5 | **和正** | 1,559 句 | 待清查 |
| 6 | **波波爺爺** | 1,446 句 | 待清查 |
| 7 | **瑪麗亞** | 1,277 句 | 待清查 |
| 8 | **輝美** | 1,210 句 | 待清查 |
| 9 | **梅莉莎** | 1,185 句 | 待清查 |
| 10 | **拉菲** | 1,163 句 | 待清查 |
| 11 | **昴** | 1,135 句 | 待清查 |
| 12 | **艾麗卡** | 1,065 句 | 待清查 |
| 13 | **真穗** | 1,044 句 | 待清查 |
| 14 | **老人** | 948 句 | 待清查 |
| 15 | **商人** | 923 句 | 待清查 |
| 16 | **村長** | 901 句 | 待清查 |
| 17 | **王宮騎士** | 888 句 | 待清查 |
| 18 | **工廠長** | 862 句 | 待清查 |
| 19 | **博士** | 840 句 | 待清查 |
| 20 | **靈界之王** | 770 句 | 待清查 |

---

## 四、 案例深入剖析：克蕾琪塔的秘書 (Deep Dive: Secretary of Crechetta)

### 1. 官方 AssetBundle 實體驗證 [VERIFIED]

直接連線 So-net 官方 CDN 下載並透過 `UnityPy` 解密，取得以下兩張 128×128 RGBA 官方立繪頭像：

* **常態秘書**：
  * Bundle 路徑：`a/storydata_icon_unit_006111.unity3d`
  * CDN Pool Hash：`1b65eb2126363493`
  * 規格：128×128 RGBA PNG，黑短編髮、深色常態商會制服。
* **泳裝秘書（本次【史上最糟的夏天，開幕】活動）**：
  * Bundle 路徑：`a/storydata_icon_unit_006112.unity3d`
  * CDN Pool Hash：`bcff253ff3778bd6`
  * 規格：128×128 RGBA PNG，頭戴**白色雞蛋花**、泳裝吊帶、微笑表情。

### 2. 官方指令流（Command Stream）現場還原 [VERIFIED]

在活動第 4 話（`5218004`）之官方 AssetBundle（`c5016a78b974fa32`）的 TextAsset 指令流中：

```text
120: cmd=122, args=['false', 'false']
121: cmd=4,   args=['6112']                     <-- 鏡頭焦點鎖定至 6112
122: cmd=50,  args=['6112', '1']
123: cmd=12,  args=['vo_adv_5218004_006']        <-- 語音掛載
124: cmd=3,   args=['6112', '6']                <-- 表情切換 (6)
125: cmd=6,   args=['秘書', '簡直就像歷經生離死別的姊妹呢，'] <-- 對白文字
126: cmd=13,  args=['50']
127: cmd=6,   args=['秘書', '兩位。']
```

以及該話結尾（回憶克蕾琪塔身邊工作）：

```text
873: cmd=4,   args=['6112']
874: cmd=50,  args=['6112', '0']
875: cmd=12,  args=['vo_adv_5218004_050']
876: cmd=3,   args=['6112', '6']
877: cmd=6,   args=['秘書', '……']
879: cmd=6,   args=['秘書', '\n那是因為。']
...
1074: cmd=4,  args=['6112']
1075: cmd=50, args=['6112', '0']
1076: cmd=12, args=['vo_adv_5218004_061']
1077: cmd=3,  args=['6112', '1']
1079: cmd=6,  args=['秘書', '……呵呵。']
```

### 3. 解包器過濾器斷點分析 [VERIFIED]

在 `tools/pcrd_fetch.py` 的 `_parse_bundle_dialogues()` 函式中：

```python
# tools/pcrd_fetch.py:501-508
if idx == 4 and args:
    target_str = str(args[0]).strip()
    if target_str.isdigit() and len(target_str) == 6 and int(target_str) >= 100000:
        block_cmd4_units.append(int(target_str))
    elif target_str == "0" or ":" in target_str:
        block_cmd4_units.append(None)
```

* **過濾原因**：官方劇本中數值為 `6112`，字串長度為 4 且數值小於 100000。
* **直接後果**：`block_cmd4_units` 判定此指令非合法 unit ID，因此對白輸出物件僅有 `"name": "秘書"`，其 `unit_id` 欄位為 `None`。
* **前端連鎖反應**：前端 `avatar-service.js` 先嘗試查詢顯式 `unit_id`（失敗），再 fallback 查詢 `npc_avatars.json`（查無 `"秘書"`），最終觸發 Fail-Closed 機制顯示粉紅色文字佔位符。

---

## 五、 正式架構契約：Canonical Contract 與 Manifest Gate

### 1. 為何「單一名稱映射（`npc_avatars.json`）」不是正式解法？

在過往架構中，部分 NPC 透過 `npc_avatars.json` 將名稱直接映射到固定 ID。但秘書案例徹底否定了這種做法作為通用解法：
- **同名不同造型（形態差分 / 換裝）**：
  - 秘書在常態劇情中使用 **`006111`**（商會制服）。
  - 秘書在本次活動劇情中使用 **`006112`**（泳裝與雞蛋花）。
- 若在 `npc_avatars.json` 中將 `"秘書"` 映射至任何單一 ID，必然導致另一場景發生時空錯亂（夏日活動穿西裝，或辦公室穿泳裝）。
- **架構結論**：對白中的換裝與差分，**唯一權威來源是劇本指令流（Command Stream）中的顯式立繪 ID**。

### 2. 正式鎖定之標準契約 (Canonical Contract)

本規格正式定案，不再保留型別選擇空間，所有後續實作必須嚴格遵守以下對齊規則：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      LOCKED CANONICAL CONTRACT                         │
├──────────────────────┬─────────────┬───────────────────────────────────┤
│ 項目                 │ 型別        │ 規範與範例                        │
├──────────────────────┼─────────────┼───────────────────────────────────┤
│ Command unit_id      │ integer     │ 6112 (劇本 JSON 欄位永遠為整數)   │
│ Official asset_key   │ string(6)   │ "006112" (6 碼補零官方識別碼)     │
│ Binary filename      │ string      │ "006112.png" (實體二進位圖檔)     │
│ Registry unit_id     │ integer     │ 6112 (avatar_assets.json 查表鍵)  │
│ Registry asset_key   │ string(6)   │ "006112" (登錄於 avatar_assets)   │
└──────────────────────┴─────────────┴───────────────────────────────────┘
```

#### Story JSON 呈現格式：
```json
{
  "name": "秘書",
  "words": "簡直就像歷經生離死別的姊妹呢，",
  "voice": "vo_adv_5218004_006",
  "unit_id": 6112
}
```
> **嚴格約束**：Story JSON 中的 `unit_id` 永遠維持為數值 `6112`（integer），不得儲存為字串 `"006112"`，亦不得人為加上 offset（如 `196112`）。

#### Avatar Registry (`avatar_assets.json`) 登錄格式：
```json
{
  "unit_id": 6112,
  "asset_key": "006112",
  "filename": "006112.png",
  "format": "png",
  "usage": "dialogue",
  "status": "active",
  "size_bytes": 10560,
  "sha256": "...",
  "provenance": "storydata2_assetmanifest"
}
```

### 3. Closed-Universe Manifest Gate（密閉式清冊門禁規範）

短 ID（`< 100000`）不得因為「長度小於 6」或「數值大於 0」就無條件採納，必須由官方 `storydata2_assetmanifest` membership 作為唯一合法性依據。

#### 判定流程：
```text
Command target (如 "6112" 或 "0" 或 "1")
    ↓
1. 確認為純數字字串 (target_str.isdigit())
    ↓
2. 轉為整數值 (val = int(target_str))
    ↓
3. 區分號段：
   ├─ val >= 100000 且 len == 6：
   │     直接採納為標準角色 ID
   │
   └─ val > 0 且 len < 6 (短 ID 候選者)：
         ↓
         a. 格式化為 6 碼 official asset_key: asset_key = target_str.zfill(6)
         ↓
         b. 查詢權威清冊: 檢查 storydata_icon_unit_<asset_key>.unity3d 
            是否存在於 authoritative storydata2_assetmanifest
         ↓
         ├─ 存在 (VALID)  → 採納 val (例如 6112) 為合法角色 unit_id
         └─ 不存在 (DROP) → 視為鏡頭/層級控制參數，安全忽略
```

* **反例驗證**：若劇本出現 `cmd 4: ['1']`，雖然 `1.zfill(6)` 為 `"000001"`，但官方清冊中不存在 `storydata_icon_unit_000001.unity3d`，門禁直接將其視為機位參數忽略，**零誤判**。
* **正例驗證**：若劇本出現 `cmd 4: ['6112']`，`6112.zfill(6)` 為 `"006112"`，清冊中精確存在 `storydata_icon_unit_006112.unity3d`，立即判定為合法角色立繪。

---

## 六、 實作路線 (Implementation Roadmap)

### 階段一：秘書專項 Pilot Case (Phase 1: Canonical Secretary Pilot)

* **性質**：端到端規格驗證試點（不使用 Name Fallback，全面驗證 Canonical Contract）。
* **收錄項目**：
  - 常態秘書：`unit_id: 6111` ↔ `asset_key: "006111"` ↔ `filename: "006111.png"`
  - 泳裝秘書：`unit_id: 6112` ↔ `asset_key: "006112"` ↔ `filename: "006112.png"`
* **驗證範圍**：
  - 下載解密圖檔至 `dashboard/icon/unit/006111.png` 與 `006112.png`。
  - 在 `avatar_assets.json` 登錄此兩筆 active dialogue 資產。
  - 更新 `5218004.json` 對白寫入 `unit_id: 6112`。
  - 執行 `pipeline.bundle` 與 `pipeline.validate` 確認 100% 通過。

### 階段二：解包器權威清冊校驗升級 (Phase 2: Manifest-Backed Parser Upgrade)

* **目標**：正式將 Closed-Universe Manifest Gate 實作入 `tools/pcrd_fetch.py::_parse_bundle_dialogues()`。
* **驗證**：重解含前導零 NPC 之相關話數，確認非角色指令零誤判，短 ID NPC 100% 自動獲取正確 `unit_id`。

### 階段三：全域 NPC 資產自動化探測工具鏈 (Phase 3: Automated NPC Discovery Pipeline)

* **目標**：系統化開採剩餘 544 個官方未使用的頭像 Bundle。
* **工具鏈規劃**：
  1. 對 `storydata2_assetmanifest` 中所有 463 個 `0xxxxx` Bundle 建立快速比對索引。
  2. 掃描全量 9,096 篇劇本，產出《高頻缺圖 NPC 與候選 Bundle 對照建議表》。
  3. 人工/AI 協同審核後，批次匯入二進位檔案與登錄清冊。

---

## 七、 Evidence Boundary（證據邊界宣告）

| 結論項目 | 證據強度 (Confidence Level) | 依據說明 |
| :--- | :---: | :--- |
| 官方 CDN 存在秘書專屬頭像 | **VERIFIED** | 已直接從 CDN 下載 `006111` 與 `006112` 並以 UnityPy 解出無損 PNG。 |
| 5218004 劇本中秘書使用 `6112` | **VERIFIED** | 解析官方 AssetBundle TextAsset command stream，第 121、873、1074 行明確記載 `cmd 4: ['6112']`。 |
| 解包器過濾規則導致 `unit_id` 遺漏 | **VERIFIED** | `tools/pcrd_fetch.py:503` 明文限制 `len == 6 and >= 100000`，直接導致數值為 6112 時被跳過。 |
| 官方 CDN 共有 546 個未收錄頭像 | **VERIFIED** | 經精確交集運算：$1472 - 926 = 546$ 個未收錄，8 個池外項目。 |
| 實質對白總數為 1,221,991 行 | **VERIFIED** | 經排除 `still`、`background`、`movie` 及空白行後之全量審計結果。 |
| 其他 3,347 個佔位符發言標籤皆有對應官方立繪 | **UNRESOLVED** | 部分標籤純屬無立繪路人（如「女性教員」或純語音），需透過 Phase 3 腳本進行個案交叉比對才能確定。 |
