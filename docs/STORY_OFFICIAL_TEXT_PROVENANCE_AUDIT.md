# Story Map 官方文本來源血統與欄位語意審計報告
# (Official Text Provenance & Semantic Audit)

> **文檔狀態**：Phase 0.5 權威審計完成（含 AssetBundle 二進位流交叉驗證）
> **建立日期**：2026-09-11
> **關聯議題**：`[Story Map] 重製 AI 劇情摘要為可靠的劇情懶人包` (Issue #1)

---

## 一、 核心審計結論 (Executive Summary)

```text
LOCAL DB DIRECT SOURCE
= https://wthee.xyz/db/redive_tw.db (定義於 tools/pcrd_fetch.py:38，透過 HTTP GET 下載明文 SQLite)

ULTIMATE UPSTREAM SOURCE
= So-net CDN / Cygames 原廠 Master DB (經由 wthee 伺服器解密獲取)

WTHEE TRANSFORMATION STATUS
= PARTIALLY (保留原廠表結構與未中文化底層字串，未進行人為竄改，但移除部分非台服表且缺乏直接二進位對齊證明)

STORY ASSETBUNDLE SOURCE
= So-net CDN Pool AssetBundles (經由 Android manifest: {SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest 索引，自 pool/AssetBundles/{hash[:2]}/{hash} 下載)

BUNDLE CMD 0 SEMANTICS
= 主要／顯示標題元數據 (Primary / Display-Title Metadata，語意依劇情類型而異：主線/角色/公會/系統多數為話數序號或章節標籤如「第1章 第1話」；活動劇情則可表現為話數名稱如「回憶的歸途」)

BUNDLE CMD 1 SEMANTICS
= 官方劇情大綱 (Official Synopsis，長度數十至近百字之繁體中文長篇情節概要；本次 25 話抽樣 min=55字, max=87字, avg=71.4字, median=71字)

BUNDLE CMD 32 SEMANTICS
= 官方話數副標題 / 話名 (Official Episode Subtitle / Episode Name，例如「冒失女僕娘的委託」)

BUNDLE CMD 1 VS DB SUB_TITLE
= COMPLETELY DIFFERENT (cmd 1 為長篇劇情概要；DB sub_title 為 5~15 字短話名，兩者在定位與篇幅上皆非同一概念)

BUNDLE CMD 32 VS DB SUB_TITLE
= HIGHLY CONSISTENT (20/25 抽樣逐字完全相同，其餘 5 筆僅為翻譯潤飾或符號全半形差異，語意與定位 100% 同為話名副標題)

IS CMD 1 TRUE OFFICIAL SYNOPSIS?
= OFFICIAL_DISTRIBUTED (由 So-net 官方 CDN 發布之 Story AssetBundle 內建長篇劇情大綱文字；抽樣 25/25 話皆包含非空大綱)

ARE STORY JSONS PERSISTING CMD 1?
= NO (現有 tools/pcrd_fetch.py 於 fetch_story_json_by_id 呼叫 _parse_bundle_dialogues 時未傳入 extract_metadata=True，且目前 schema 僅持久化對白陣列)

STORY JSON PROVENANCE
= OFFICIAL_DERIVED (資料源自 So-net CDN 劇本 AssetBundle，但解析過程包含 SPEAKER_MAP 映射、可可蘿代換及 JSON 結構重組)

IS "官方大綱" ACCURATE FOR CURRENT UI?
= NO (現有 UI 將 DB sub_title / cmd 32 話名冠以「官方大綱」標籤，且在查無值時存在寫死 generic fallback)

FUTURE UI DIRECTION
= SCENARIO A (官方話名 cmd 32 + 官方大綱 cmd 1 補完 + AI 劇情速讀懶人包 + 官方劇情全文四層分工架構)

PROVENANCE CONFIDENCE
= HIGH (已直接向 So-net 官方 CDN 下載 Android AssetBundle 並完成 Unity 二進位流指令級抽樣交叉比對)

SEMANTIC CONFIDENCE
= VERY HIGH (25 筆跨類別抽樣 100% 證實 cmd 1 為劇情大綱、cmd 32 與 DB sub_title 為話名副標題)
```

---

## 二、 資料血統鏈路 (Data Provenance Chain)

```mermaid
graph TD
    subgraph 官方來源與管線 [Official Upstream & Pipeline]
        A["Cygames 原廠 Master DB / 劇本指令流"] -->|授權台服在地化翻譯| B["So-net 台服營運團隊"]
        B -->|打包加密| C1["So-net CDN Master DB<br/>(加密 SQLite)"]
        B -->|打包 AssetBundle| C2["So-net CDN Storydata<br/>(img-pc.so-net.tw/dl/Resources/.../storydata)"]
        C1 -->|定時自動解密提取| D["wthee.xyz 鏡像伺服器<br/>(redive_tw.db)"]
        D -->|tools/pcrd_fetch.py cmd_update_db| E["本地資料庫<br/>dashboard/redive_tw.db"]
        C2 -->|tools/pcrd_fetch.py fetch_story_json_by_id| F["本地劇本解析器<br/>(_parse_bundle_dialogues)"]
    end

    subgraph 本地儲存與變換 [Local Storage & Derived Artifacts]
        E -->|SELECT title, sub_title FROM story_detail| G["話名資料 (DB sub_title)<br/>[OFFICIAL_DERIVED]"]
        F -->|提取對白 + 說話者映射 + 可可蘿代換| H["本地劇情 JSON<br/>dashboard/story/*.json<br/>[OFFICIAL_DERIVED]"]
        F -.->|⚠️ cmd 1 官方大綱未被持久化| I["遺失的官方大綱 (cmd 1)<br/>[NOT PERSISTED]"]
    end

    subgraph 前端呈現與改善目標 [Frontend UI Evolution]
        G -->|❌ 現有錯誤標籤 (含 Fallback)| J["📌 官方大綱 (MISLABELED)"]
        G -.->|✅ 未來標籤 (Scenario A)| K["📜 官方話名 / 副標題"]
        I -.->|✅ 未來補完持久化 (Scenario A)| L["📌 官方大綱 (真正的 cmd 1)"]
        H -->|✅ 現有呈現| M["✦ 劇情全文 ✦ & 語音播放"]
    end

    style J fill:#ff7675,stroke:#d63031,color:#fff
    style K fill:#55efc4,stroke:#00b894,color:#000
    style L fill:#74b9ff,stroke:#0984e3,color:#000
    style M fill:#a29bfe,stroke:#6c5ce7,color:#000
```

---

## 三、 Story AssetBundle Metadata 深度審計 (AssetBundle Metadata Audit)

### 1. 審計方法與工具
為徹底釐清官方劇本 AssetBundle 是否蘊藏真正的大綱，專案團隊於 `tools/diagnostics/audit_bundle_synopsis.py` 建立自動化二進位稽核工具。工具透過 So-net 官方 CDN 資源清單（`storydata2_assetmanifest`）下載原始 AssetBundle，使用 `UnityPy` 解析底層 `TextAsset`，並透過 `pcrd_fetch.py` 的反序列化引擎將二進位流還原為指令陣列 `[(cmd_idx, [args])]`。

### 2. 官方 AssetBundle 指令語意架構
經深入逆向分析，Cygames / So-net 劇本檔案開頭之元數據指令具有以下結構特徵：
* **`cmd 0`**：**主要／顯示標題元數據 (Primary / Display-Title Metadata)**。語意依劇情類型而異：
  - 主線／角色／公會／系統劇情：多數表現為話數序號或章節標籤（如 `第1章 第1話`、`日和　第1話`、`美食殿堂　第3話`）。
  - 活動劇情 (Event)：可直接表現為話數名稱（如 `回憶的歸途`），部分與 `cmd 32` 相同。
* **`cmd 1`**：**官方劇情大綱 (Official Synopsis)**。長度為數十至近百字之繁體中文情節概要（抽樣 25 話統計：min=55字, max=87字, avg=71.4字, median=71字），文本內含主角代稱 `{0}`。
* **`cmd 32`**：**話數副標題／話名 (Episode Subtitle / Episode Name)**。長度約 5~15 字，例如 `冒失女僕娘的委託`、`歡迎來到美食殿堂！`。

### 3. 跨五大劇情類別 25 筆抽樣比對總表

本輪抽樣嚴格涵蓋主線（5 筆）、角色（5 筆）、公會（5 筆）、活動（5 筆）及系統/露娜塔（5 筆）共 25 話真實資料：

| 類型 | Story ID | 資料庫 `title` | 資料庫 `sub_title` | Bundle `cmd 0` (標題元數據) | Bundle `cmd 32` (話名副標題) | Bundle `cmd 1` 是否存在 | `cmd 32` vs DB `sub_title` |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **主線** | 2001001 | 第1章 第1話 | 冒失女僕娘的委託 | 第1章 第1話 | 冒失女僕娘的委託 | ✅ (65字) | 逐字吻合 |
| **主線** | 2001002 | 第1章 第2話 | 不受歡迎的乘客 | 第1章 第2話 | 不請自來的乘客 | ✅ (63字) | 譯名修飾差異 |
| **主線** | 2001003 | 第1章 第3話 | 被盯上的少女 | 第1章 第3話 | 被盯上的少女 | ✅ (79字) | 逐字吻合 |
| **主線** | 2001004 | 第1章 第4話 | 擦身而過的兩人 | 第1章 第4話 | 擦身而過的兩人 | ✅ (84字) | 逐字吻合 |
| **主線** | 2002001 | 第2章 第1話 | 真步公主的招待 | 第2章 第1話 | 真步公主的招待 | ✅ (60字) | 逐字吻合 |
| **角色** | 1001001 | 日和 第1話 | 有困難的時候就互相幫助幫助 | 日和　第1話 | 有困難的時候就互相幫助幫助 | ✅ (60字) | 逐字吻合 |
| **角色** | 1001002 | 日和 第2話 | 打勾勾的誓言 | 日和　第2話 | 打勾勾的誓言 | ✅ (63字) | 逐字吻合 |
| **角色** | 1001003 | 日和 第3話 | 為笑容許下心願 | 日和　第3話 | 為笑容許下心願 | ✅ (69字) | 逐字吻合 |
| **角色** | 1001004 | 日和 第4話 | 走散的貓耳女孩 | 日和　第4話 | 走散的貓耳女孩 | ✅ (71字) | 逐字吻合 |
| **角色** | 1001005 | 日和 第5話 | 尾巴是犯規的？ | 日和　第5話 | 尾巴是犯規的？ | ✅ (71字) | 逐字吻合 |
| **公會** | 3001001 | 美食殿堂 第1話 | 幸福的餐桌有你有我 | 美食殿堂　第1話 | 幸福的餐桌有你有我 | ✅ (80字) | 逐字吻合 |
| **公會** | 3001002 | 美食殿堂 第2話 | 就是黃連也吃得下肚唷♪ | 美食殿堂　第2話 | 吃蓼的蟲也沒問題唷♪ | ✅ (81字) | 譯名修飾差異 |
| **公會** | 3001003 | 美食殿堂 第3話 | 歡迎來到美食殿堂！ | 美食殿堂　第3話 | 歡迎來到美食殿堂！ | ✅ (83字) | 逐字吻合 |
| **公會** | 3002001 | 王宮騎士團 第1話 | 秩序與混沌的騎士團 | 王宮騎士團　第1話 | 秩序與混沌的騎士團 | ✅ (55字) | 逐字吻合 |
| **公會** | 3002002 | 王宮騎士團 第2話 | 潛力股在那任務之中 | 王宮騎士團　第2話 | 黃金蛋的任務途中 | ✅ (76字) | 譯名修飾差異 |
| **活動** | 5001001 | 初音的禮物大作戰 第1話 | 回憶的歸途 | 回憶的歸途 | 回憶的歸途 | ✅ (69字) | 逐字吻合 |
| **活動** | 5001002 | 初音的禮物大作戰 第2話 | 與不可思議之書的相遇 | 與不可思議之書的相遇 | 與不可思議之書的相遇 | ✅ (71字) | 逐字吻合 |
| **活動** | 5001003 | 初音的禮物大作戰 第3話 | Dear‧Sister | Dear・Sister | Dear・Sister | ✅ (62字) | 標點全半形差異 |
| **活動** | 5002001 | 小小甜心大冒險 第1話 | 一起探險的邀請 | 一起探險的邀請 | 一起探險的邀請 | ✅ (62字) | 逐字吻合 |
| **活動** | 5002002 | 小小甜心大冒險 第2話 | 重修舊好的食譜 | 重修舊好的食譜 | 重修舊好的食譜 | ✅ (60字) | 逐字吻合 |
| **系統** | 4001001 | 公會小屋 第1話 | 歡迎來到公會小屋 | 公會小屋 第1話 | 歡迎來到公會小屋 | ✅ (87字) | 逐字吻合 |
| **系統** | 4001002 | 公會小屋 第2話 | 前往被封印的二樓 | 公會小屋 第2話 | 前往被封印的二樓 | ✅ (81字) | 逐字吻合 |
| **系統** | 4001003 | 公會小屋 第3話 | 解除封印的重大危機！？ | 公會小屋 第3話 | 解除封印的重大危機！？ | ✅ (76字) | 逐字吻合 |
| **系統** | 4001004 | 公會小屋 第4話 | 三樓的小小同居人 | 公會小屋 第4話 | 三樓的小小同居人 | ✅ (86字) | 逐字吻合 |
| **系統** | 4001005 | 公會小屋 第5話 | 妖精們的遊戲 | 公會小屋 第5話 | 妖精們的遊戲 | ✅ (70字) | 逐字吻合 |

### 4. 官方大綱 (`cmd 1`) 實體文本範例
以下節錄抽樣中解析出之官方大綱原始字串：
* **主線 2001001（第1章 第1話）**：
  > 「在蘭德索爾展開新生活的一個月後。{0}與可可蘿為了生計而開始尋找工作。正好又遇到了在找人幫忙搬家的冒失女僕鈴莓，便接受了工作委託。」
* **公會 3001003（美食殿堂 第3話）**：
  > 「貪吃佩可、可可蘿及凱留，三人一起吃飯已經成為了慣例。此外，也決定了今後要輪流選擇用餐的餐廳。貪吃佩可在不知不覺間，成立了食遍天下的公會【美食殿堂】，以追逐美食為目標。」
* **系統 4001001（公會小屋 第1話）**：
  > 「獲得了公會小屋的{0}與美食殿堂的成員們。從【公會管理協會】所派來，將會暫時駐守在此的花凜那裡，聽取了說明及注意事項。二樓及三樓因仍處於『調查中』狀態，目前似乎被封鎖了起來。」

### 5. 一致性與差異分析結論
1. **抽樣 25/25 話皆包含非空 `cmd 1`**：
   本次抽樣的所有 25 話中，`cmd 1` 均完備存在，字數落在 55~87 字之間（平均 71.4 字，中位數 71 字），文本皆為繁體中文情節摘要。資料直接取自 So-net 官方 CDN 分發之 Story AssetBundle 二進位流（`OFFICIAL_DISTRIBUTED`）。本結論僅針對抽樣集合驗證，全量覆蓋率將在後續全庫稽核中確認。
2. **`cmd 32` vs `DB sub_title` 一致率 80% (20/25 逐字吻合)**：
   未逐字吻合的 5 筆中，差異均為微幅翻譯潤飾（如「不受歡迎」vs「不請自來」；「黃連」vs「吃蓼的蟲」；或全半形中點 `‧` vs `・`）。兩者語意定位與篇幅 100% 一致，同屬 5~15 字之「話名副標題」，絕非大綱。

---

## 四、 現有管線對 `cmd 1` 的遺漏與 Story JSON 血統校正

### 1. `cmd 1` 遺漏機制分析 (`tools/pcrd_fetch.py`)
經檢查 `tools/pcrd_fetch.py` 的真實 HEAD 實作：
```python
# tools/pcrd_fetch.py:401-466 & 541-625 (真實 HEAD 實作)
def _parse_bundle_dialogues(bundle_data, extract_metadata=False):
    ...
    # 預設 extract_metadata=False 時回傳對白陣列:
    if extract_metadata:
        return dialogues, bundle_metadata
    return dialogues

def fetch_story_json_by_id(
    story_id: int,
    manifest_hash_map: Optional[Dict[int, str]] = None,
    timeout: int = 15
) -> StoryFetchResult:
    ...
    bundle_url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    ...
    # ⚠️ 標準下載原語呼叫時未啟用 extract_metadata=True:
    dialogues = _parse_bundle_dialogues(bundle_data)
    ...
    with open(tmp_path, "w", encoding="utf-8") as f:
        # ⚠️ 目前持久化契約僅序列化儲存對白陣列 (dialogue array contract):
        json.dump(dialogues, f, ensure_ascii=False, indent=2)
    tmp_path.replace(out_path)
    return StoryFetchResult(...)
```
`pcrd_fetch.py` 內部已實作 `_parse_bundle_metadata` 並具備抽取 `cmd 1`（`synopsis`）的能力，但在標準下載原語 `fetch_story_json_by_id` 呼叫時未啟用 `extract_metadata=True`，且目前 `dashboard/story/<story_id>.json` 的持久化契約僅儲存對白陣列（dialogue array contract），導致隨 AssetBundle 發布的官方大綱文字在解析當下被拋棄。

### 2. Story JSON 血統校正 (`OFFICIAL_RAW` ➡️ `OFFICIAL_DERIVED`)
先前文檔將 `dashboard/story/*.json` 歸類為 `OFFICIAL_RAW`，本輪審計依據嚴格血統定義予以校正：
* **變換 1（角色名稱覆寫）**：`_parse_bundle_dialogues` 呼叫 `SPEAKER_MAP.get(speaker, speaker)`，以本地寫死的角色字典覆寫原始角色名稱。
* **變換 2（台詞正則替換）**：特定角色台詞經過字串代換（例如將「主人」替換為「主公大人」等）。
* **變換 3（結構序列化）**：原始二進位 command 流被重構為 JSON 陣列結構。

基於上述文字加工與格式轉換，`dashboard/story/*.json` 應精確分類為 **`OFFICIAL_DERIVED`**。唯有未經解析的原始 `.unity3d` 二進位檔方可稱為 `OFFICIAL_RAW`。

---

## 五、 現存文字來源分類盤點表 (全面校正版)

| 前端顯示項目 / 資料產物 | 實際資料來源 | 分類等級 | 語意與內容定義 | 現存問題與風險說明 |
| :--- | :--- | :---: | :--- | :--- |
| **`📌 官方大綱` (正常有值)** | `story_detail.sub_title` | `OFFICIAL_DERIVED` | **話名 / 副標題**（5~15 字） | **標籤名不符實**：實為話名卻被冠以大綱稱謂 |
| **`📌 官方大綱` (查無值時)** | 寫死字串 `"本話為重要主線..."` | `GENERIC_FALLBACK` | 偽造的佔位描述 | **嚴重違規 (BUG)**：非官方文字被標為官方 |
| **未提取之官方大綱** | AssetBundle `cmd 1` | `OFFICIAL_RAW` (未持久化) | **真正的官方劇情大綱**（數十至近百字，抽樣 avg=71.4字） | **資料遺失**：隨 Bundle 發布但在轉 JSON 時未持久化 |
| **`💡 單話摘要簡介`** | `ChapterDataService` 快取 | `AI_GENERATED` | 舊版 LLM 生成之摘要 | 早期品質粗糙、缺乏一致性，已於 Phase 0 隱藏 |
| **`📖 整章摘要簡介`** | `event_summaries.json` | `AI_GENERATED` / `LOCAL_CURATED` | 舊版章節總結 | 涵蓋不均，已於 Phase 0 隱藏 |
| **`✦ 劇情全文 ✦`** | `dashboard/story/*.json` | `OFFICIAL_DERIVED` | 官方劇本對白（經解析重組） | 正確反映劇本，但包含說話者映射與可可蘿詞彙代換 |

---

## 六、 未來架構演進：Scenario A 落地實施規劃

由於本次審計證實「官方大綱 (`cmd 1`)」確實隨官方 AssetBundle 分發，專案無須在「廢棄官方大綱標籤」與「混淆副標題」之間妥協。未來架構應採行 **Scenario A（四層清晰分工架構）**：

```text
┌─────────────────────────────────────────────────────────────────┐
│                      Story Map 話數卡片未來佈局                  │
├─────────────────────────────────────────────────────────────────┤
│ 標題列：  第 1 章 第 1 話：冒失女僕娘的委託 (cmd 32 / DB sub_title)│
│                                                                 │
│ 📜 官方大綱 (Official Synopsis - cmd 1 補完)                      │
│ 「在蘭德索爾展開新生活的一個月後。佑樹與可可蘿為了生計而開始...」 │
│                                                                 │
│ 🤖 劇情速讀 (AI Summary - Phase C/D 重製高品質懶人包)             │
│ 「關鍵焦點：佑樹與可可蘿接下搬家委託，初次遭遇神秘少女...」      │
│                                                                 │
│ ✦ 劇情全文 ✦ (Dialogue JSON & Audio - 單句語音播放)             │
│ [語音] 可可蘿：「主人，今天也要努力工作喔。」                   │
└─────────────────────────────────────────────────────────────────┘
```

### 後續分階段路線規劃：
1. **Phase 0.5（當前完成）**：完成 AssetBundle 指令深度稽核，確認 `cmd 1` 為官方大綱、`cmd 32` 為話名，並修正血統評級。
2. **Phase A（Story AssetBundle Command & Metadata 盤點與設計評估）**：
   - 全面盤點現有 parser 已知／未知 command IDs。
   - 對 cmd semantics 建立 confidence / evidence table。
   - 找出目前 decoded-but-dropped metadata。
   - 完成 metadata persistence design：評估 sidecar manifest、獨立 metadata JSON、或 story schema migration 之優缺點。
   - 完成向後相容影響分析 (backward compatibility impact analysis)，確保不破壞既有對白消費契約。
   - 通過 Design Review 後才進入管線實作階段。
3. **Phase B（前端 UI 四層分工呈現）**：
   - 將話名（`sub_title`）整合進話數標題。
   - 將 `cmd 1` 正式掛載至真正的「📜 官方大綱」區塊（若無大綱則優雅隱藏，徹底移除寫死的 fallback 文字）。
4. **Phase C / D（AI 劇情懶人包重製）**：
   - 基於官方劇本全文與官方大綱，使用最新大語言模型重製高品質、語意連貫的「🤖 劇情速讀／懶人包」，與官方文本嚴格並存。

---

*審計報告核准者：Antigravity Agentic Auditor*
*核准時間：2026-09-11*
