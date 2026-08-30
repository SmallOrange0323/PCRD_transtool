# Story Coverage S1 — 第 3 部「分支劇情（Branch Story）」補充元數據審查報告 (BRANCH_STORY_METADATA_AUDIT.md)

本報告記錄針對《公主連結 Re:Dive》主線第 3 部（第 1 章～第 16 章）中，已下載存在於本地 `dashboard/story/` 但未被官方資料庫 `story_detail` 收錄之「分支劇情（Branch Stories）」所進行的完整資料盤點與元數據審查。

---

## 1. 審查摘要 (Executive Summary)

* **盤點目標**：第 3 部第 1～16 章所有本地已具備對白 JSON、但未列入 `redive_tw.db` 之 `story_detail` 表的分支劇情話數。
* **發現總數 (Total Discovered)**：**63 篇**
* **結構性元數據驗證 (Verified Structural Metadata)**：
  - `story_id`、`part` (3)、`chapter` (1～16) 均通過格式與連續性驗證。
  - `json_exists`：**63 / 63 篇全數存在且為合法非空資料 (100%)**。
  - `story_detail_absence`：**0 筆衝突 (0 Collisions)**，所有 63 個 ID 均未被官方 `story_detail` 表佔用。
* **描述性元數據驗證 (Descriptive Metadata)**：
  - **已確認官方描述性元數據 (Verified Descriptive Metadata)**：**2 篇**（第 13 章 `2213101` 與 `2213104`，由台版遊戲官方截圖確認）。
  - **未確認描述性元數據 (Unresolved Descriptive Metadata)**：**61 篇**（`branch_label`、`title`、`subtitle` 均嚴格設為 `null`，標記 `metadata_status: "unresolved"`，絕不混入人工臆測之 synthetic display labels）。

> [!IMPORTANT]
> **Provisional Display Labels 規範**：
> 未來前端整合層（View / Integration Layer）若需要為尚未解析出官方名稱的 61 篇分支劇情提供臨時導航文字（例如顯示為「分支劇情 1」或「第 N 話」），應由前端 UI 層依 chapter + order 動態產生，該類臨時文字**不屬於** `branch_stories.json` 的權威元數據（Authoritative Metadata）。

---

## 2. 各章節分支話數統計 (Counts by Chapter)

| 章節 | 群組 ID (`story_group_id`) | 分支話數數量 | 分支話數 ID 清單 |
| :--- | :--- | :---: | :--- |
| **第 1 章** | 2201 | 3 篇 | `2201101`, `2201102`, `2201103` |
| **第 2 章** | 2202 | 4 篇 | `2202101`, `2202102`, `2202103`, `2202104` |
| **第 3 章** | 2203 | 4 篇 | `2203101`, `2203102`, `2203103`, `2203104` |
| **第 4 章** | 2204 | 7 篇 | `2204101` ～ `2204107` |
| **第 5 章** | 2205 | 4 篇 | `2205101` ～ `2205104` |
| **第 6 章** | 2206 | 4 篇 | `2206101` ～ `2206104` |
| **第 7 章** | 2207 | 4 篇 | `2207101` ～ `2207104` |
| **第 8 章** | 2208 | 4 篇 | `2208101` ～ `2208104` |
| **第 9 章** | 2209 | 8 篇 | `2209101` ～ `2209108` |
| **第 10 章** | 2210 | 3 篇 | `2210101`, `2210102`, `2210103` |
| **第 11 章** | 2211 | 3 篇 | `2211101`, `2211102`, `2211103` |
| **第 12 章** | 2212 | 4 篇 | `2212101` ～ `2212104` |
| **第 13 章** | 2213 | 4 篇 | `2213101` ～ `2213104` |
| **第 14 章** | 2214 | 3 篇 | `2214101`, `2214102`, `2214103` |
| **第 15 章** | 2215 | 3 篇 | `2215101`, `2215102`, `2215103` |
| **第 16 章** | 2216 | 1 篇 | `2216101` |
| **總計** | **Part 3** | **63 篇** | **3+4+4+7+4+4+4+4+8+3+3+4+4+3+3+1 = 63 篇** |

> [!NOTE]
> 關於第 16 章的額外發現：
> 第 16 章硬碟上有 `2216097`, `2216098`, `2216099` 三篇檔案，其第 5 碼為 `0`，經對話內容比對（彌勒、幻境龍后對決）確認為第 16 章的後續「主線幕間話數」，不屬於分支劇情。真正的分支劇情為 `2216101`（第 5 碼為 `1`）。

---

## 3. 完整 63 篇話數盤點清單 (Full Discovered Inventory)

| 話數 ID (`story_id`) | 部別 | 章節 | 標籤 (`branch_label`) | 標題 (`title`) | 副標題 (`subtitle`) | 元數據狀態 (`metadata_status`) |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `2201101` | 3 | 1 | `null` | `null` | `null` | `unresolved` |
| `2201102` | 3 | 1 | `null` | `null` | `null` | `unresolved` |
| `2201103` | 3 | 1 | `null` | `null` | `null` | `unresolved` |
| `2202101` | 3 | 2 | `null` | `null` | `null` | `unresolved` |
| `2202102` | 3 | 2 | `null` | `null` | `null` | `unresolved` |
| `2202103` | 3 | 2 | `null` | `null` | `null` | `unresolved` |
| `2202104` | 3 | 2 | `null` | `null` | `null` | `unresolved` |
| `2203101` | 3 | 3 | `null` | `null` | `null` | `unresolved` |
| `2203102` | 3 | 3 | `null` | `null` | `null` | `unresolved` |
| `2203103` | 3 | 3 | `null` | `null` | `null` | `unresolved` |
| `2203104` | 3 | 3 | `null` | `null` | `null` | `unresolved` |
| `2204101` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204102` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204103` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204104` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204105` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204106` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2204107` | 3 | 4 | `null` | `null` | `null` | `unresolved` |
| `2205101` | 3 | 5 | `null` | `null` | `null` | `unresolved` |
| `2205102` | 3 | 5 | `null` | `null` | `null` | `unresolved` |
| `2205103` | 3 | 5 | `null` | `null` | `null` | `unresolved` |
| `2205104` | 3 | 5 | `null` | `null` | `null` | `unresolved` |
| `2206101` | 3 | 6 | `null` | `null` | `null` | `unresolved` |
| `2206102` | 3 | 6 | `null` | `null` | `null` | `unresolved` |
| `2206103` | 3 | 6 | `null` | `null` | `null` | `unresolved` |
| `2206104` | 3 | 6 | `null` | `null` | `null` | `unresolved` |
| `2207101` | 3 | 7 | `null` | `null` | `null` | `unresolved` |
| `2207102` | 3 | 7 | `null` | `null` | `null` | `unresolved` |
| `2207103` | 3 | 7 | `null` | `null` | `null` | `unresolved` |
| `2207104` | 3 | 7 | `null` | `null` | `null` | `unresolved` |
| `2208101` | 3 | 8 | `null` | `null` | `null` | `unresolved` |
| `2208102` | 3 | 8 | `null` | `null` | `null` | `unresolved` |
| `2208103` | 3 | 8 | `null` | `null` | `null` | `unresolved` |
| `2208104` | 3 | 8 | `null` | `null` | `null` | `unresolved` |
| `2209101` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209102` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209103` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209104` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209105` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209106` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209107` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2209108` | 3 | 9 | `null` | `null` | `null` | `unresolved` |
| `2210101` | 3 | 10 | `null` | `null` | `null` | `unresolved` |
| `2210102` | 3 | 10 | `null` | `null` | `null` | `unresolved` |
| `2210103` | 3 | 10 | `null` | `null` | `null` | `unresolved` |
| `2211101` | 3 | 11 | `null` | `null` | `null` | `unresolved` |
| `2211102` | 3 | 11 | `null` | `null` | `null` | `unresolved` |
| `2211103` | 3 | 11 | `null` | `null` | `null` | `unresolved` |
| `2212101` | 3 | 12 | `null` | `null` | `null` | `unresolved` |
| `2212102` | 3 | 12 | `null` | `null` | `null` | `unresolved` |
| `2212103` | 3 | 12 | `null` | `null` | `null` | `unresolved` |
| `2212104` | 3 | 12 | `null` | `null` | `null` | `unresolved` |
| `2213101` | 3 | 13 | `L I` | `分支劇情 L I` | `死者的世界裡最臭的東西` | `resolved_official_screenshot` |
| `2213102` | 3 | 13 | `null` | `null` | `null` | `unresolved` |
| `2213103` | 3 | 13 | `null` | `null` | `null` | `unresolved` |
| `2213104` | 3 | 13 | `R V` | `分支劇情 R V` | `錢與豐滿與現實` | `resolved_official_screenshot` |
| `2214101` | 3 | 14 | `null` | `null` | `null` | `unresolved` |
| `2214102` | 3 | 14 | `null` | `null` | `null` | `unresolved` |
| `2214103` | 3 | 14 | `null` | `null` | `null` | `unresolved` |
| `2215101` | 3 | 15 | `null` | `null` | `null` | `unresolved` |
| `2215102` | 3 | 15 | `null` | `null` | `null` | `unresolved` |
| `2215103` | 3 | 15 | `null` | `null` | `null` | `unresolved` |
| `2216101` | 3 | 16 | `null` | `null` | `null` | `unresolved` |

---

## 4. 補充元數據架構 (Supplemental Schema)

於 `dashboard/data/branch_stories.json` 建立嚴謹之確定性結構：

```json
{
  "version": 1,
  "part": 3,
  "stories": [
    {
      "story_id": 2213101,
      "chapter": 13,
      "branch_label": "L I",
      "title": "分支劇情 L I",
      "subtitle": "死者的世界裡最臭的東西",
      "metadata_status": "resolved_official_screenshot"
    },
    {
      "story_id": 2201101,
      "chapter": 1,
      "branch_label": null,
      "title": null,
      "subtitle": null,
      "metadata_status": "unresolved"
    }
  ]
}
```

* **排序規則**：固定按 `chapter ASC` 接著 `story_id ASC` 排序。
* **資料純度**：未確認項目皆為 `null`，無任何自行構造之假性標籤，無絕對路徑與環境依賴。

---

## 5. 資料完整性與衝突審查結論 (Audit Findings)

1. **是否確實為 63 篇？**
   - **是**。第 3 部（第 1～16 章）共有 63 篇符合 `22xx1xx` 編碼格式之分支劇情。
2. **哪幾章有分支劇情？每章各幾篇？**
   - 第 1 章（3 篇）、第 2 章（4 篇）、第 3 章（4 篇）、第 4 章（7 篇）、第 5 章（4 篇）、第 6 章（4 篇）、第 7 章（4 篇）、第 8 章（4 篇）、第 9 章（8 篇）、第 10 章（3 篇）、第 11 章（3 篇）、第 12 章（4 篇）、第 13 章（4 篇）、第 14 章（3 篇）、第 15 章（3 篇）、第 16 章（1 篇）。
3. **是否全部已有本地 JSON？**
   - **是**。63 份檔案在 `dashboard/story/` 中全部存在，大小介於 276 至 784 行指令，對話文本完整無損。
4. **是否有任何 ID 衝突？**
   - **無**。所有 63 個 ID 均未存在於 `story_detail` 資料庫表中，完全不存在碰撞風險。
5. **描述性元數據確認狀態？**
   - 2 篇已由官方遊戲畫面直接核實（`resolved_official_screenshot`）。
   - 61 篇維持 `unresolved`，欄位皆設為 `null`，待日後取得官方命名時再行補全。
