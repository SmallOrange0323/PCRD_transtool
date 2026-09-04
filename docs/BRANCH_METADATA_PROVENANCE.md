# 第 3 部分支劇情元數據欄位級來源依據 (Branch Metadata Field-Level Provenance)

本文件定義並說明 `dashboard/data/branch_stories.json`（Schema Version 2）各欄位的語意、來源依據（Provenance）與雙軌（Dual-Track）分支編號推導規則。

---

## 一、 背景與改進動機

在早期版本（Schema Version 1）中，各分支話數使用粗粒度的整篇狀態標記：
```json
"metadata_status": "resolved_official_bundle"
```
然而，實際的官方資源解析情況中，不同欄位的證據強度並不相同：
- 副標題（`subtitle`）是直接解析自官方 Story AssetBundle 二進位劇本中的指令（例如 `cmd32` 引導字串）。
- 分支分類（`category`，一般分支 vs 現實分支）在目前解密到的 AssetBundle 劇本結構中並無直接的明文字段，而是依據已驗證之雙軌資料集規則所識別。
- 分支編號標籤（`branch_label`，如羅馬數字或 R 序列）與全名（`title`）係依分類與全域計數推導而得。
- 部分話數另具備直接的官方遊戲 UI 截圖佐證。

為了明確區分「官方資源直接證實之資料」與「規則推導之資料」，Schema Version 2 引入了欄位級的來源標記（Field-Level Provenance）。

---

## 二、 Schema Version 2 結構規範

根物件包含：
- `version`: `2` (整數)
- `part`: `3` (整數)
- `stories`: 陣列，共 63 筆分支劇情物件

每筆分支劇情的欄位定義如下：

```json
{
  "story_id": 2213104,
  "chapter": 13,
  "category": "reality",
  "branch_label": "R V",
  "title": "分支劇情 R V",
  "subtitle": "錢與豐滿與現實",
  "provenance": {
    "subtitle": "PROVEN_FROM_STORY_BUNDLE",
    "category": "DERIVED_FROM_CURRENT_DATASET_RULE",
    "branch_label": "DERIVED_FROM_CATEGORY_AND_GLOBAL_SEQUENCE",
    "title": "DERIVED_FROM_BRANCH_LABEL",
    "official_ui": "VERIFIED_BY_OFFICIAL_UI"
  }
}
```

### 1. 欄位定義說明

| 欄位名稱 | 型別 | 說明 |
| :--- | :--- | :--- |
| `story_id` | 整數 | 官方話數 ID（如 `2213104`），正整數且不可重複。 |
| `chapter` | 整數 | 所屬主線第 3 部之章節（`1` ~ `16`）。 |
| `category` | 字串 | 分支類型，限定為 `"ordinary"`（一般分支）或 `"reality"`（現實分支）。 |
| `branch_label` | 字串 | 分支編號標籤。一般分支為全域羅馬數字（`I`, `II`, ...），現實分支為獨立序列（`R I`, `R II`, ...）。 |
| `title` | 字串 | 分支全名，固定由 `"分支劇情 " + branch_label` 組成。 |
| `subtitle` | 字串 | 官方話數副標題（例如 `"錢與豐滿與現實"`）。 |
| `provenance` | 物件 | 欄位級來源憑據。包含 `subtitle`, `category`, `branch_label`, `title`, `official_ui`。 |

---

## 三、 來源憑據詞彙庫 (Provenance Vocabulary)

| 詞彙代碼 | 意義與證據等級 |
| :--- | :--- |
| `PROVEN_FROM_STORY_BUNDLE` | 直接由官方 Story AssetBundle 二進位劇本（如 `cmd32` 字串）解析所得，具有官方資源直接明文證據。 |
| `DERIVED_FROM_CURRENT_DATASET_RULE` | 依據已驗證之雙軌資料集規則識別判定，非劇本二進位檔直接導出。 |
| `DERIVED_FROM_CATEGORY_AND_GLOBAL_SEQUENCE` | 依據分類與全域第 3 部分支出現順序推導之序號標籤。 |
| `DERIVED_FROM_BRANCH_LABEL` | 依據 `branch_label` 組合產生（`"分支劇情 " + branch_label`）。 |
| `VERIFIED_BY_OFFICIAL_UI` | 經由官方遊戲實機 UI 截圖直接對照確認，具有獨立外部視覺證據。 |
| `null` | 無直接截圖錨點證據（不虛假標註已驗證）。 |

---

## 四、 雙軌分支資料集規則 (Dual-Track Branch Rule)

第 3 部分支劇情在遊戲內呈現為兩種不同性質的劇情：
1. **一般綠色分支（Ordinary Branch）**：共 56 話，按話數 ID 順序依序編列全域羅馬數字（`I`, `II`, ..., `LVI`）。
2. **現實分支（Reality Branch）**：共 7 話，官方在 UI 上以帶有「R」前綴之獨立序號（`R I`, `R II`, ..., `R VII`）進行呈現，不與一般分支混編。

### 現實分支 7 話清單與序列對照表

| Story ID | 章節 | 官方副標題 | 分支標籤 (`branch_label`) | UI 截圖錨點確認 |
| :--- | :--- | :--- | :--- | :--- |
| **2210102** | 第 10 章 | 被虐狂與眼鏡與現實與── | `R I` | - |
| **2211102** | 第 11 章 | 毛茸茸與收容所與現實 | `R II` | - |
| **2212103** | 第 12 章 | 噗吉與mimi與現實 | `R III` | - |
| **2212104** | 第 12 章 | 宅宅與忍者與現實 | `R IV` | - |
| **2213104** | 第 13 章 | 錢與豐滿與現實 | `R V` | **VERIFIED_BY_OFFICIAL_UI** |
| **2214101** | 第 14 章 | 英雄與跑腿與現實 | `R VI` | - |
| **2215102** | 第 15 章 | 大小姐和鯛魚燒和現實和── | `R VII` | - |

---

## 五、 已知官方實機 UI 截圖錨點 (Official UI Anchors)

目前經實機 UI 截圖直接證實的分支劇情包括：
1. **`2213101`**：
   - 標籤：`XLIX`
   - 副標題：`棘手大小姐們的觀光約會？`
   - `official_ui`: `"VERIFIED_BY_OFFICIAL_UI"`
2. **`2213102`**：
   - 標籤：`L`
   - 副標題：`亞里莎，遭遇巨人`
   - `official_ui`: `"VERIFIED_BY_OFFICIAL_UI"`
3. **`2213104`**：
   - 標籤：`R V`
   - 副標題：`錢與豐滿與現實`
   - `official_ui`: `"VERIFIED_BY_OFFICIAL_UI"`

其餘 60 筆紀錄之 `official_ui` 欄位均保持為 `null`，嚴禁在缺乏截圖佐證下虛構標示。

---

## 六、 當前已知限制 (Current Limitations)

1. **官方客戶端底層結構未完全還原**：
   - 目前的 Story AssetBundle 解碼器能穩定取得 `subtitle`，但官方客戶端中如何儲存 `category` 與 `branch_label`（例如是否有獨立的資料庫資料表或特定客戶端邏輯），尚未完全逆向獲取。
2. **非截圖覆蓋話數之序號推導**：
   - 非截圖話數的 `branch_label` 係依據已驗證的雙軌計數規則排序推導，雖然與已知錨點（如 `XLIX`, `L`, `R V`）完全吻合，但在官方客戶端原始資料結構完全公開前，仍應明確標註其來源為 `DERIVED_FROM_CATEGORY_AND_GLOBAL_SEQUENCE`。
