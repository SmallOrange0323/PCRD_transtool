# AvatarService 頭像資產權威來源與儲存模型決策 (Phase 3 Decision Report - Rev. 2)

> **文件狀態**：Phase 4 實測閉環定案 (Phase 4 Verified - Rev. 3)  
> **決策日期**：2026-09-04  
> **關聯 RFC**：[`docs/AVATAR_SERVICE_EXACT_ID_REFACTOR_PLAN.md`](AVATAR_SERVICE_EXACT_ID_REFACTOR_PLAN.md)  
> **目標系統**：`dashboard/data/avatar_assets.json`、`pipeline/bundle.py`、`dashboard/icon/unit/`  

---

## 一、 決策背景與 Phase 2 審查基準 (Phase 2 Baseline)

依據已通過驗收之 Phase 2 全量確定性審查結果：
* **正規劇本話數**：9,033 篇（對白總行數 1,351,043 句，明確指派 `unit_id` 者 1,302,950 句）。
* **頭像有效 ID (Avatar-Eligible, >= 100000)**：**900 個**（特殊非頭像代碼 `< 100000` 共 440 個已明確分離）。
* **本地已擁有之 Exact ID (Local Hits)**：**739 個**（實體圖檔 100% 存在，覆蓋對白 1,085,487 句，**覆蓋率高達 97.86%**）。
* **實體資產與容量測量事實 (Measured Facts)**：
  - 目前生產環境圖檔目錄 `dist_story_map/icon/unit/` 佔用 **5.00 MiB**（388 檔）。
  - 將本地已擁有但現行管線未發布的 789 個 Exact ID 檔案納入，僅需額外增加 **15.35 MiB**。
  - 專案依 `pipeline/validate.py` 規範排除 `{'.git', 'sound', 'card'}` 後的 **Canonical Pages Footprint 目前為 262.63 MiB**。
  - 納入本地已持有圖檔後，**已知最低 Pages 體積為 277.98 MiB**（遠低於 750 MiB 預警線）。
  - **實體頭像必備 ID 與無頭像實體**：在 900 個 Avatar-eligible ID 中，**897 個為實體頭像必備 ID**（已 100% 在庫）；其餘 **3 個為確認無獨立頭像之演出差分**（`190813`, `106913`, `105921`，僅骨骼立繪無 icon bundle，runtime 契約為 fail-closed placeholder，0 Bytes）。
  - **897 個必備 Exact 頭像 Canonical 實體總容量 (One-File-Per-ID)**：已完全精確測量為 **17.36 MiB** (18,208,292 Bytes)，由 Phase 4 前已在庫之 739 個 PNG (14.61 MiB / 15,316,830 Bytes) 與 Phase 4 獲取之 158 個 PNG (2.76 MiB / 2,891,462 Bytes) 精確組成（調和期間額外下載 0 檔）。
  - **現行 dist 155 個 ID 差額與實體遷移淨增量 (Real Delta)**：現行 dist 針對該 155 個 ID 之 1,071,110 Bytes 差額 100% 來自舊版 duplicate `.webp` 副本。遷移至未來預期圖庫樹（897 個對白 PNG + 30 個合法 UI 圖檔 = 927 檔 / 18,583,224 Bytes）時，新增 742 檔 (+14.46 MiB) 並修剪移除 203 檔重複與殘留 (-1.74 MiB)，**淨增量為 +12.72 MiB (+13,336,870 Bytes)**。
  - **最終權威 Canonical Pages 發布體積與專案門禁**：現行 262.63 MiB + 淨增 12.72 MiB = **275.35 MiB** (288,722,530 Bytes)。距專案 750 MiB 預警線尚有 **474.65 MiB** 裕度，距 900 MiB 硬上限尚有 **624.65 MiB** 裕度，Model B 通過最終容量檢驗！

---

## 二、 161 個缺失頭像 ID 臨時分流檢驗 (Provisional Phase 3 Acquisition Triage)

針對這 161 個在本地尚未具備實體圖檔的 Avatar-eligible ID，經劇本台詞與角色發言人初步關鍵字與上下文篩選，建立**臨時初篩分流（Provisional Triage）**。本分類僅作為獲取策略參考，非最終語意真理；在實際獲取前，異常 ID 必須以官方資料庫與劇情上下文進行單獨驗證，絕不單憑數值區間作語意推論：

### 1. 初篩分流統計 (Provisional Triage Breakdown)
| 類別代號 | 初篩定義 (Provisional Definition) | ID 數量 | 影響對白句數 | 代表性案例與證據等級 |
| :---: | :--- | :---: | :---: | :--- |
| **Bucket A** | **可玩角色 / 換裝變體差分候選** | **123 個** | 18,294 句 | 碧卡拉差分 (`125614`, 1562句)、美空差分 (`131214`, 1356句)、可可蘿差分 (`105912`, 814句)、美里現實造型 (`101532`, 778句)、厄莉絲差分 (`135012`, 745句)、優花梨差分 (`114612`, 727句) 等 |
| **Bucket B** | **NPC / 具名劇情角色** | **24 個** | 4,785 句 | 卡里莎差分 (`191618`, 523句 / `191616`, 496句)、拉基尼卡東 (`191713`)、艾比思 (`191912`~`191915`)、阿佐特 (`192013`~`192015`) 等 |
| **Bucket C** | **魔物 / 召喚物 / 靈獸** | **7 個** | 312 句 | 布爾布幽靈小狗差分 (`133114`, `133117`, `133119`)、鳳凰靈獸差分等 |
| **Bucket D** | **闇影 / 複製體 / 人偶** | **5 個** | 291 句 | 霞的闇影與莉莉闇影相關差分等 |
| **Bucket E** | **未知 / 特殊區間需深度調查** | **2 個** | 32 句 | 志那都 (`500095`，活動劇情 5208006)、拉基拉基 (`999990`，主線 2014009) |

### 2. 獲取候選信心度評估 (Acquisition Confidence)
* **High-Confidence Acquisition Candidates (高信心獲取候選，共 147 個)**：Bucket A (123) 與 Bucket B (24) 的具名角色及關鍵換裝。
* **Likely Acquisition Candidates (可能獲取候選，共 12 個)**：Bucket C (7) 與 Bucket D (5) 的靈獸與闇影差分。
* **Needs Investigation (需深入調查，共 2 個)**：Bucket E 的 `500095` 與 `999990`，需於 Phase 4 查核官方 CDN 與 DB 元資料是否具備獨立實體立繪。

---

## 三、 資產儲存與治理模型評估 (Storage & Governance Models)

### 模型對比矩陣
| 評估維度 | MODEL A (僅 Manifest，二進位忽略) | MODEL B (精選對白頭像子集納入 main) ★推薦方案 | MODEL C (獨立資產倉庫 / Submodule) |
| :--- | :--- | :--- | :--- |
| **Clean-Clone 重現性** | ❌ 差（clone 後無圖，需手動下載） | ✅ **最佳（clone 後頭像即就緒，0 配置）** | ⚠️ 中（需 checkout submodule 或 LFS） |
| **CI 確定性** | ❌ 差（CI 環境無圖，無法離線驗收） | ✅ **最佳（CI 離線確定性比對，100% 驗證）** | ⚠️ 中（需設定額外 token 或 LFS 頻寬） |
| **Git 歷史與體積** | ✅ 極小（僅增加 JSON 清單） | ✅ **良好（已知持有僅增約 15 MB，總量預期輕量）** | ⚠️ 中（分散於不同倉庫） |
| **離線開發體驗** | ❌ 差（新設備無網路無法渲染頭像）| ✅ **最佳（頭像完全離線可視）** | ⚠️ 中 |
| **Vibe-Coding 維護負擔**| ⚠️ 中（多一步管線同步） | ✅ **最低（純 Git 工作流，最直觀）** | ❌ 高（跨倉庫同步易踩坑） |

### 推薦決策：採納 MODEL B 作為推薦架構（待 Phase 4 驗證最終體積後正式切換）
* **精準定義**：  
  **`main` 分支僅追蹤規範之「對白頭像二進位子集（Canonical Dialogue-Avatar Binary Subset）」及其資產登錄表（Asset Registry）**，而非盲目追蹤整個 `dashboard/icon/` 目錄。
* **資產嚴格分界**：  
  - 大圖 CG / 劇情靜態背景繼續維持由外部 EsterTion CDN 託管，嚴禁進入 Git 倉庫。
  - 非對白/快取/除錯用之其他圖檔，維持在列管集合之外。
* **Phase 4 驗收結果 (Phase 4 Gate: PASS)**：  
  Model B 經 Phase 4 實測驗證，已全面達成通過標準（參見 [`docs/AVATAR_MISSING_ASSET_VERIFICATION.md`](AVATAR_MISSING_ASSET_VERIFICATION.md)）：
  1. **實測體積極度輕量**：Phase 4 下載獲取 158 檔 (2.76 MiB / 2,891,462 Bytes，失敗 0，調和期間額外下載 0)，全量 897 個必備 Exact 頭像 Canonical 實體總容量僅 **17.36 MiB** (18,208,292 Bytes)。考慮修剪重複 webp 副本後，遷移至未來圖庫樹（927 檔）之實質淨增量僅 **+12.72 MiB** (+13,336,870 Bytes)。
  2. **無極端異常二進位值**：單圖最大 24,225 Bytes (~23.66 KiB)，最小 2,235 Bytes，規格 100% 為標準 128x128 PNG。
  3. **Pages 總體積絕對安全 (符合 pipeline/validate.py 門禁)**：最終權威 Canonical Pages 預計為 **275.35 MiB** (288,722,530 Bytes)，距專案 750 MiB 預警線尚有 **474.65 MiB** 餘裕（預估僅佔 36.7%），距 900 MiB 硬上限尚有 **624.65 MiB** 餘裕（預估僅佔 30.6%）。
  4. **對白與非對白 UI 集合邊界清晰**：897 個對白頭像與 30 個合法非對白 UI 圖檔職責切分明確，203 個重複與殘留檔將依清單安全清理。
  5. **無頭像實體架構受控**：3 個無頭像演出差分（`190813`, `106913`, `105921`）由 Fail-Closed 佔位符承接，不偽造實體圖檔，身分不失真。
  6. **正式結論**：**MODEL B 評審通過 (PASS)**，核准進入 Phase 5 管線與解析器實作。

---

## 四、 權威來源 (Source of Truth) 與資產登錄表 (Asset Registry) 職責劃分

嚴格禁止將 `avatar_assets.json` 誤當為「決定哪些對白 ID 是必需的」之業務裁決者。系統職責分離合約如下：

```text
1. 劇情劇本資料 (Canonical Stories, 9,033 篇) 
   【唯一權威來源】：對白所需的明確 unit_id 必須且只能由正規劇本導出。
        ↓
2. 資產登錄表 (dashboard/data/avatar_assets.json)
   【權威資產登錄】：記錄這批被劇本要求之頭像的二進位元數據、獲取狀態與實體檔案對照。
        ↓
3. 實體圖庫庫存 (dashboard/icon/unit/)
   【二進位實現】：登錄表所宣告的實體 PNG 檔案。
        ↓
4. 打包管線 (pipeline/bundle.py)
   【發布執行】：將劇本要求且登錄在庫的合法 Exact-ID 100% 打包進 dist 目錄。
```

### 核心合約不變量 (Critical Invariants)
* **不可靜默遺漏不變量**：  
  若正規劇本出現了某個明確的 `unit_id`，但資產登錄表（Manifest）中尚未記錄，**管線驗證必須強制報錯（Validation Failure）或將其明確標記為 `status = missing`，絕不得將其解讀為「不需要此圖檔」**。
* **Clean-Clone 下之資料獲取邊界**：  
  - 目前倉庫依架構忽略了 `dashboard/story/*.json`（劇本由資料管線維護更新）。
  - 因此在乾淨 clone 環境下：
    $$\text{git clone} \longrightarrow \text{列管之頭像二進位資產已直接就緒}$$
    $$\longrightarrow \text{透過既有管線獲取/更新劇本 JSON (pipeline update)}$$
    $$\longrightarrow \text{劇本下載完成後，頭像端即刻 100% 完整顯示，無需額外執行頭像 bootstrap 下載}$$
  - Model B 解決的是**頭像的確定性與重現性**，而非讓全部劇情文本自包含於 main 分支。

---

## 五、 列管資產登錄表設計 (Canonical Avatar Manifest Schema)

規劃於 Phase 4 引入登錄檔案：  
📁 **`dashboard/data/avatar_assets.json`**

### 1. 欄位架構規範
* **權威欄位 (Authoritative Fields - 資產管理與審查依據)**：
  - `unit_id` (int): 官方 6 位數 unit_id。
  - `filename` (string): 實體檔案名稱（如 `106831.png`）。
  - `format` (string): `"png"` 或 `"webp"`。
  - `status` (string): `"active"`（已在庫）、`"missing"`（待獲取）、`"placeholder_only"`（確認無圖檔，走文字佔位符）。
  - `source` (string): 資產來源（`"sonet_cdn"` / `"estertion_mirror"` / `"game_assetbundle"`）。
* **衍生/輔助欄位 (Derived Fields - 由劇本或工具動態計算更新)**：
  - `required_by_dialogue` (bool): 劇本是否有引用。
  - `usage_count` (int): 對白引用總句數。
  - `story_count` (int): 出現之話數總數。
  - `sha256` (string): 實體圖檔校驗雜湊。
  - `size_bytes` (int): 實體圖檔大小。

### 2. 範例 Schema 片段 (Sample Manifest Snippet)
```json
{
  "$schema": "./schema/avatar_assets.schema.json",
  "version": "1.0",
  "assets": [
    {
      "unit_id": 105811,
      "filename": "105811.png",
      "format": "png",
      "status": "active",
      "source": "sonet_cdn",
      "required_by_dialogue": true,
      "usage_count": 18937
    },
    {
      "unit_id": 106831,
      "filename": "106831.png",
      "format": "png",
      "status": "active",
      "source": "sonet_cdn",
      "required_by_dialogue": true,
      "usage_count": 2664
    },
    {
      "unit_id": 133118,
      "filename": "133118.png",
      "format": "png",
      "status": "active",
      "source": "game_assetbundle",
      "required_by_dialogue": true,
      "usage_count": 5
    },
    {
      "unit_id": 193631,
      "filename": "193631.png",
      "format": "png",
      "status": "active",
      "source": "sonet_cdn",
      "required_by_dialogue": true,
      "usage_count": 195
    },
    {
      "unit_id": 125614,
      "filename": "125614.png",
      "format": "png",
      "status": "missing",
      "source": "estertion_mirror",
      "required_by_dialogue": true,
      "usage_count": 1562
    }
  ]
}
```

---

## 六、 打包管線合約與未來 `.gitignore` 邊界規範

### 1. 未來打包管線合約 (Future Bundler Contract)
在 Phase 5 中，`pipeline/bundle.py` 的 `get_expected_icon_unit_mappings` 將重構為：
$$\text{Expected Dist Icons} = \text{Canonical Story Required Exact Set (via Manifest)} \;\cup\; \text{UI Non-Dialogue Icons}$$
* **生產修剪不變量 (Critical Pruning Invariant)**：  
  凡經由正規劇本導出並在 Manifest 中登錄為 `required_by_dialogue = true` 的實體 Exact 頭像，**必須 100% 複製至 `dist_story_map/icon/unit/`，且打包管線絕不得將其修剪或刪除**！
* **舊版集合處理**：  
  - `tracked_characters.json` 保留，作為非對白角色列表與篩選 UI 的輔助圖檔來源（兩者聯集）。
  - 舊版寫死的 `REALITY_UNIT_IDS` (80 個集合) 與 `190000~199999` 區間硬編碼將全面廢除，統一由劇本驅動之登錄表取代。

### 2. 未來 `.gitignore` 治理策略
* 目前倉庫設定：`dashboard/icon/` 全目錄被忽略。
* 未來實作 Model B 時，**嚴禁粗暴地 unignore 整個 `dashboard/icon/` 目錄**。
* 設計方針：僅精確放行由 Manifest 規範核准之對白 Exact-ID 頭像二進位子集，其餘本機快取、除錯或無關圖檔繼續維持被忽略。
* **約束**：*本 Phase 3 階段嚴禁修改 `.gitignore`。*

---

## 七、 資產獲取合約 (Asset Acquisition Contract)

針對 161 個缺失 ID，建立標準獲取流程：
1. **輸入**：由劇本對比產出之 161 個 missing ID 清單。
2. **獲取通道順序**：
   $$\text{So-net 官方 CDN (AssetBundle / 明文)} \longrightarrow \text{EsterTion 鏡像站 (Exact WebP/PNG)}$$
3. **安全合約**：
   - **嚴格保留原始 Exact-ID**，嚴禁自動替換為 base+11 或 base+31。
   - 若經查證屬特殊演出代碼且無圖檔（如 `500095`、`999990`），標記為 `status = "placeholder_only"`，由前端極簡 Fail-Closed 顯示佔位符徽章。
   - 腳本具備冪等性（Idempotent），支援 `--dry-run` 模式。
   - *本 Phase 3 階段嚴禁下載任何資產。*\n