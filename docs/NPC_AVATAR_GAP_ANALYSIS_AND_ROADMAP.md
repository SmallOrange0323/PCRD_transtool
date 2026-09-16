# PCRD Story Map NPC 頭像覆蓋缺口分析與系統性應對藍圖 (RFC)

**文件代號**：`RFC-20260916-NPC-AVATAR-GAP`  
**建立日期**：2026-09-16  
**狀態**：`PROPOSED / UNDER REVIEW`  
**適用範疇**：`pipeline/`（資料更新管線）、`tools/pcrd_fetch.py`（劇理解包器）、`dashboard/data/`（資產登錄與 NPC 映射表）

---

## 摘要 (Executive Summary)

在目前維護的《公主連結 Re:Dive》劇情導航站（Story Map）中，讀者與維護者反映大量劇情配角與 NPC 僅能顯示粉紅色文字佔位符（如「秘書」、「摩拉」、「米亞」）。經全面掃描 So-net 官方 CDN 明文清冊與全量劇本指令流，確認：

1. **官方 CDN 實際上儲備了 1,472 個官方立繪頭像 Bundle**，目前專案僅登錄 934 個，尚有 **546 個官方頭像處於未開採狀態**。
2. 未開採頭像中有 **463 個屬於官方前導補零（`0xxxxx`）的特殊 NPC / 配角 / 怪物 ID**。
3. 專案解包器（`tools/pcrd_fetch.py`）過去採取硬性防禦條件 `len(target_str) == 6 and int(target_str) >= 100000`，導致官方指令流中去除了前導零的 NPC ID（例如克蕾琪塔秘書的 `6112`）被視為雜訊參數遭全面過濾。
4. 在全站 9,096 篇正規劇情（共 1,394,576 行對白）中，因缺少頭像而降級為文字佔位符的對白高達 **235,469 行（佔 16.88%）**。

本文件旨在完整記錄此現象的根本技術原因、數據基線、實體證據，並提出分階段的架構應對藍圖，供工程團隊與多方 AI 協作討論。

---

## 一、 客觀數據審核與基線 (Empirical Audit & Baseline Data)

以下數據皆由專案審核腳本於本地資料庫與 So-net 官方 CDN 鏡像即時統計產生：

### 1. 官方 CDN 故事頭像資源池結構

* **資料來源**：So-net 官方 `storydata2_assetmanifest`（快取於 `dashboard/versions/cached_manifests/storydata2_assetmanifest.txt`）。
* **官方 `storydata_icon_unit_*.unity3d` 總數**：**1,472 個**。

| 資源分類區段 | 命名模式 | Bundle 數量 | 實體內容說明 |
| :--- | :--- | :---: | :--- |
| **前導補零特例區** | `storydata_icon_unit_0xxxxx.unity3d` | **463 個** | 特殊劇情 NPC、專屬配角（如秘書）、各行會路人、特定魔物、村民 |
| **標準劇情 NPC 區** | `storydata_icon_unit_19xxxx.unity3d` | **88 個** | 主線第二部/第三部具名核心 NPC（如八斗神 `193611`、羅蘭 `194212`） |
| **可玩角色與換裝區** | `storydata_icon_unit_{10-18}xxxx.unity3d` | **921 個** | 可玩角色之常態、換裝（泳裝、新年、女武神等）、星級差分 |

### 2. 專案目前收錄現狀

* **現有 `avatar_assets.json` 登錄 ID 總量**：**934 個**（其中 `usage: "dialogue"` 為 923 個）。
* **官方 CDN 尚未納入專案之資源總量**：**546 個**（佔官方資源池之 37.1%）。
  * 未收錄之 `0xxxxx` 前導補零特例：463 個。
  * 未收錄之 `19xxxx` NPC 形態差分：12 個。
  * 未收錄之其他形態：71 個。

### 3. 全量劇情對白頭像覆蓋率統計

* **審核樣本範圍**：`dashboard/story/*.json` 全量正規劇情 **9,096 篇**。
* **對白總行數**：**1,394,576 行**。
* **成功解析官方頭像行數**：**1,159,107 行（83.12%）**。
* **降級為文字方塊行數**：**235,469 行（16.88%）**。
* **涉及文字方塊之獨立說話者名稱總數**：**3,348 個**。

### 4. 高頻具名文字方塊角色排行 (Top 20 Named Placeholder Speakers)

排除泛用旁白與群眾呼聲（如「旁白」19,012 句、「？？？」4,862 句、「士兵」、「居民」等），在全劇情中台詞最多、但目前無法顯示頭像的具名角色如下：

| 排名 | 角色名稱 | 全劇情對白句數 | 官方 CDN 是否有對應 AssetBundle |
| :---: | :--- | :---: | :--- |
| 1 | **店長** | 2,735 句 | 待清查（含多個行會專屬店長） |
| 2 | **摩拉** | 2,641 句 | 待確認（主線重要妖精） |
| 3 | **美穗** | 1,966 句 | 待確認 |
| 4 | **米亞** | 1,948 句 | 待確認 |
| 5 | **秘書**（克蕾琪塔的秘書） | **1,923 句** | **VERIFIED：官方存在 `006111`（常態）與 `006112`（泳裝）** |
| 6 | **和正** | 1,704 句 | 待確認 |
| 7 | **貴族** | 1,572 句 | 待確認 |
| 8 | **波波爺爺** | 1,540 句 | 待確認 |
| 9 | **奶奶** | 1,533 句 | 待確認 |
| 10 | **瑪麗亞** | 1,397 句 | 待確認 |
| 11 | **老奶奶** | 1,390 句 | 待確認 |
| 12 | **輝美** | 1,371 句 | 待確認 |
| 13 | **梅莉莎** | 1,363 句 | 待確認 |
| 14 | **司儀** | 1,348 句 | 待確認 |
| 15 | **拉菲** | 1,316 句 | 待確認 |
| 16 | **昴** | 1,274 句 | 待確認 |
| 17 | **店員** | 1,195 句 | 待確認 |
| 18 | **女性教員** | 1,093 句 | 待確認 |
| 19 | **長老** | 988 句 | 待確認 |
| 20 | **父親** | 946 句 | 待確認 |

---

## 二、 案例深入剖析：克蕾琪塔的秘書 (Deep Dive: Secretary of Crechetta)

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

## 三、 系統性架構缺口診斷 (Systemic Gaps)

1. **解包過濾器邊界過窄**：
   - 早期設計為了防禦 `cmd 4: ['0']`（鏡頭重置）或個位數 layer/slot 參數誤入，直接套用了 `len == 6 and val >= 100000` 的強硬假設。
   - 此假設忽略了官方存在 463 個以 `0` 開頭之 4~5 位數特例 NPC（AssetBundle 命名為 `006111` / `006112`，但腳本指令流中為 `6111` / `6112`）。
2. **缺乏前導補零 ID 的標準化規格 (Normalization Contract)**：
   - 若解包器直接將 `6112` 轉為整數 `6112`，會與既有二進位圖檔命名（`006112.png` 還是 `6112.png`？）產生衝突。
   - 現有 `pipeline.validate` 要求 `int(unit_id) >= 100000`，所有小於 100000 的 ID 目前會被 gate 阻攔或忽略。
3. **NPC 中文名稱與 Bundle ID 的映射脫鉤**：
   - 官方 AssetBundle 僅包含編號（如 `006111`），不包含角色中文名稱。
   - 目前 `npc_avatars.json` 是由維護者以手動或半手動方式維護，當新活動引入未見過的 NPC 時，缺乏主動探測與警示機制。

---

## 四、 應對策略與演進路線 (Proposed Roadmap)

### 階段一：立即修復克蕾琪塔秘書 (Phase 1: Immediate Quick-Win)

* **目標**：在不破壞現有 pipeline 門禁前提下，立即讓秘書在閱讀器中正常顯示官方頭像。
* **執行方案**：
  1. 將解出的兩張官方圖片存入資產庫：
     - 常態：`dashboard/icon/unit/006111.png`（或使用自訂 NPC ID 區間如 `196111.png`，視架構規範而定）。
     - 泳裝：`dashboard/icon/unit/006112.png`。
  2. 在 `dashboard/data/npc_avatars.json` 中配置 `"秘書"` 映射。
  3. 在 `dashboard/data/avatar_assets.json` 中登記為 active 資產，確保通過 `pipeline.validate`。

### 階段二：解包器規範升級與 ID 規整化 (Phase 2: Parser Normalization)

* **目標**：讓解包器能夠原生識別官方 `0xxxxx` 體系的 NPC ID。
* **討論焦點**：
  - **方案 A（字串補零 6 碼）**：
    若 `cmd 4` 參數為純數字且 `len(target_str) < 6`，自動透過 `zfill(6)` 補零成 `006112`。
    優點：與官方 CDN Bundle 檔名（`storydata_icon_unit_006112`）100% 吻合。
    缺點：需要調整 `avatar-service.js` 與 `validate.py` 對 `unit_id` 必須為整數且 $\ge 100000$ 的驗證假設。
  - **方案 B（NPC 專用號段映射）**：
    將小於 100000 的前導補零 ID，以固定 offset 映射至 NPC 保留號段（例如 `190000 + num` 或保持原始整數）。
    優點：維持所有 ID 為正整數且不改變既有 pipeline 假設。
    缺點：人為引入 offset，與官方原始 raw data 不再完全 1:1。

### 階段三：全域 NPC 資產自動化探測工具鏈 (Phase 3: Automated NPC Discovery Pipeline)

* **目標**：系統化開採剩餘 544 個官方未使用的頭像 Bundle。
* **工具鏈規劃**：
  1. **靜態索引建立**：對 `storydata2_assetmanifest` 中所有 1,472 個頭像 Bundle 建立 SHA-256 與縮圖庫。
  2. **劇本交叉比對器**：遍歷全量 9,096 篇劇本，掃描所有出現 `cmd 4` 或 `cmd 3` 但在 `npc_avatars.json` 中缺失的角色發言人名稱。
  3. **建議報表生成**：自動輸出 `missing_npc_report.json`，列出高頻缺圖 NPC 建議對應之官方 Bundle，由人工審閱確認後一鍵匯入。

---

## 五、 Evidence Boundary（證據邊界宣告）

| 結論項目 | 證據強度 (Confidence Level) | 依據說明 |
| :--- | :---: | :--- |
| 官方 CDN 存在秘書專屬頭像 | **VERIFIED** | 已直接從 CDN 下載 `006111` 與 `006112` 並以 UnityPy 解出無損 PNG。 |
| 5218004 劇本中秘書使用 `6112` | **VERIFIED** | 解析官方 AssetBundle TextAsset command stream，第 121、873、1074 行明確記載 `cmd 4: ['6112']`。 |
| 解包器過濾規則導致 `unit_id` 遺漏 | **VERIFIED** | `tools/pcrd_fetch.py:503` 明文限制 `len == 6 and >= 100000`，直接導致數值為 6112 時被跳過。 |
| 官方 CDN 共有 546 個未收錄頭像 | **VERIFIED** | 經比對本地 `avatar_assets.json` 與官方 `storydata2_assetmanifest`，數量精確無誤。 |
| 其他 3,347 個佔位符發言人皆有對應官方立繪 | **UNRESOLVED** | 部分名稱可能純屬無立繪路人（如「女性教員」或純語音），需透過 Phase 3 腳本進行個案交叉比對才能確定。 |

---

## 六、 討論問題清單 (Questions for Reviewers & Collaborating AIs)

1. **ID 形態標準化**：
   對於像 `006112` 這樣官方存在前導補零的 NPC ID，建議在專案中是以**六碼補零字串**（`"006112"`）存儲，還是以**純數字**（`6112`）或**映射號段**處理？哪種方案對現有資料庫架構與前端 `AvatarService` 的衝擊最小？
2. **優先修復順序**：
   是否同意先以 Phase 1 方案獨立解決「克蕾琪塔的秘書」（高頻且資產已 100% 驗證），再行展開 Phase 2 的解包器通用重構？
