# 公主連結 Re:Dive 劇情地圖 — Phase 4: 缺失頭像強證據驗證與資產獲取驗收報告
# (AVATAR MISSING ASSET VERIFICATION & ACQUISITION VALIDATION REPORT - REV. 3)

本文件依據專案長期架構規範與 External Review 要求，對 Phase 2 確定性審查所識別出的 **161 個真正缺失之 Avatar-eligible ID ($\\ge 100000$)** 進行官方資產強證據檢驗、受控下載驗收、現行 dist 與未來 canonical icon tree 之實體遷移淨增量（Real Delta）測量、155 個現存 ID 雙格式差額調查，以及儲存模型 Model B 最終評定。

---

## 一、 核心審查數據摘要 (Authoritative Reconciled Metrics)

```
Canonical dialogue portrait files:
897

Canonical dialogue portrait bytes:
18,208,292 bytes (17.3648 MiB)

Current required IDs represented in dist:
155

Canonical target bytes for those 155 IDs:
3,049,685 bytes (3.0497 MiB)

Current dist bytes associated with those 155 IDs:
4,120,795 bytes (310 files: 155 PNG + 155 WebP)

Reason for difference:
1,071,110 bytes (恰為現行 dist 中為該 155 個 ID 保留之 155 個 duplicate .webp 檔案；其 155 個 .png 與 canonical source 100% 吻合，0 byte 差異)

Current icon/unit total files:
388 files

Current icon/unit total bytes:
5,246,354 bytes (5.0033 MiB)

Future canonical dialogue files:
897 files (18,208,292 bytes)

Future non-dialogue UI files:
30 files (374,932 bytes, 來自 tracked_characters.json 之非對白角色 UI 圖檔)

Future total expected icon/unit files:
927 files (897 + 30)

Future expected icon/unit bytes:
18,583,224 bytes (17.7223 MiB)

Files/bytes added:
742 files / +15,158,607 bytes (+14.4564 MiB)

Files/bytes removed:
203 files / -1,821,737 bytes (-1.7373 MiB, 包含 155 個 duplicate webp 與 48 個歷史殘留檔)

Replacement size delta:
0 bytes (185 個留用檔案與 source 完全一致)

Net icon/unit delta bytes:
+13,336,870 bytes (+12.7190 MiB)

Current Pages footprint:
275,385,660 bytes (262.63 MiB)

Final projected Pages footprint:
288,722,530 bytes (275.35 MiB)

Distance to 750 MiB warning:
497,709,470 bytes (474.65 MiB, 預估僅佔預警線 36.7%)

Distance to 900 MiB hard limit:
654,995,870 bytes (624.65 MiB, 預估僅佔硬上限 30.6%)

Assets downloaded during Phase 4:
158

Acquisition failures:
0

Additional downloads during reconciliation:
0

MODEL B FINAL:
PASS
```

---

## 二、 現行 dist 155 個 ID 之 1,071,110 Bytes 差額深度調和

在前期報告中，897 個必備 ID 的 Canonical 總量（18,208,292 bytes）扣除 742 個未在庫 ID（15,158,607 bytes）後，現行 155 個 ID 的目標容量為 **3,049,685 bytes**，然而現行 dist 對應這 155 個 ID 的實際檔案總合為 **4,120,795 bytes**，產生 **1,071,110 bytes** 之差額。

經逐一對比 `dashboard/icon/unit/<id>.png` 與現行 `dist_story_map/icon/unit/` 中該 155 個 ID 的所有檔案，確切成因如下：
1. **Canonical PNG 實體檔案 (155 檔)**：  
   現行 dist 中針對這 155 個 ID 的 `<id>.png` 檔案共 155 個，總大小剛好為 **3,049,685 bytes**，與 source 端之 SHA-256 及檔案大小 **100% 精確吻合，0 byte 誤差**。
2. **Duplicate WebP 副本檔案 (155 檔)**：  
   現行 dist 中同時針對這 155 個 ID 部署了 `<id>.webp` 副本（舊版雙格式發布殘留），總大小剛好為 **1,071,110 bytes**。
3. **Legacy 前綴檔案**：  
   針對這 155 個 ID，dist 中不存在 `unit_icon_*` 前綴之殘留（0 檔）。
4. **調和結論**：  
   差額 1,071,110 bytes **100% 為這 155 個 ID 的 duplicate `.webp` 檔案所致**。在未來實施「One-file-per-ID」（單一 canonical PNG）發布合約時，這批重複副本將被清理移除。

---

## 三、 未來 Icon 樹實體遷移淨增量 (Real Delta Calculation)

為避免機械性相加導致容量失真，以**現行 dist 生產圖庫目錄**為起點，模擬遷移至**未來預期 canonical icon 目錄**的真實檔案變更：

```text
CURRENT dist icon/unit (388 檔, 5.00 MiB)
    ├── 155 個 Dialogue PNG (3.05 MiB)
    ├── 155 個 Duplicate WebP (1.07 MiB) ──[移除]──> 0 B
    ├── 30 個 合法 Non-Dialogue UI 圖檔 (0.37 MiB) ──[留用]──> 30 檔 (0.37 MiB)
    └── 48 個 歷史殘留圖檔 (0.75 MiB) ──[移除]──> 0 B
         +
    742 個 待補齊 Dialogue PNG (14.46 MiB) ──[新增]──> 742 檔 (14.46 MiB)
         ↓
FUTURE dist icon/unit (927 檔, 17.72 MiB)
    ├── 897 個 Canonical Dialogue PNG (17.36 MiB)
    └── 30 個 Non-Dialogue UI 圖檔 (0.37 MiB)
```

* **Files Added (新增檔案)**：**742 個**（+15,158,607 bytes / +14.46 MiB）
* **Files Removed (修剪重複與殘留)**：**203 個**（-1,821,737 bytes / -1.74 MiB，含 155 個 webp 副本與 48 個歷史殘留檔）
* **Files Retained (留用且無變更)**：**185 個**（155 個 PNG + 30 個 UI 圖檔，replacement size delta = 0 bytes）
* **淨增量 (Net Icon/Unit Delta)**：
  $$15,158,607 - 1,821,737 + 0 = \mathbf{+13,336,870 	ext{ Bytes (+12.72 MiB)}}$$
* **自檢驗算**：
  $$5,246,354 	ext{ (現行)} + 13,336,870 	ext{ (淨增)} = \mathbf{18,583,224 	ext{ Bytes (未來預期)}}$$
  100% 吻合！

---

## 四、 對白頭像 vs 非對白 UI 頭像職責切分 (Set Separation)

為確保未來打包管線（Phase 5）不致誤刪合法之非對白 UI 頭像，資產集合明確分離如下：

1. **Canonical Dialogue Portrait Set (對白頭像集)**：
   - 總量：**897 個 ID / 897 個實體 PNG** (18,208,292 Bytes)。
   - 權威來源：9,033 篇話數對白所要求之明確 `unit_id`。
   - 命名契約：`icon/unit/<unit_id>.png`。
2. **Non-Dialogue UI Set (非對白 UI 圖檔集)**：
   - 總量：**30 個實體檔案** (374,932 Bytes)。
   - 權威來源：`tracked_characters.json` 中定義但未在現行話數對白登場之角色（如真穗、美穗、艾麗卡等新角色或外傳角色）及系統 UI 必備圖標。
3. **Surplus & Legacy Files (歷史殘留與重複集合)**：
   - 總量：**203 個實體檔案** (1,821,737 Bytes)。
   - 性質：舊版 duplicate `.webp` 副本（155 檔）與舊版 `unit_icon_*` 殘留檔（48 檔），未來由打包管線依清單修剪清理。

---

## 五、 161 個缺失 ID 之強證據調查與分類事實

1. **待驗證缺失 ID 基準**：161 個（對白行數 23,714 句）。
2. **VERIFIED_PORTRAIT_ENTITY (158 個 ID，23,682 句)**：
   - 官方 `storydata2_assetmanifest` 具備 1:1 專屬 `storydata_icon_unit_<id>.unity3d`。
   - 經 Phase 4 受控獲取，**158 / 158 全部成功下載並解碼為標準 (128, 128) PNG**（0 失敗，總計 2,891,462 Bytes）。
   - `500095`（志那都）與 `999990`（拉基拉基）證實為具備官方頭像之獨立角色實體。
3. **NOT_A_PORTRAIT_ENTITY (3 個 ID，32 句)**：
   - `190813`（花凜，13 句）、`106913`（霸瞳皇帝，10 句）、`105921`（可可蘿「？？？」，9 句）。
   - 官方僅打包全身立繪（`storydata_spine_full`），無獨立頭像 Bundle。
   - 運行時契約：`exact identity retained -> no exact portrait -> fail-closed placeholder`，身分不猜測、不失真。
4. **懸置或推測項目**：0 個。

---

## 六、 最終權威 Pages 體積與 Model B 評定

* **Current Canonical Pages Footprint**：**262.63 MiB** (275,385,660 Bytes)
* **Net Icon/Unit Delta**：**+12.72 MiB** (+13,336,870 Bytes)
* **Final Projected Canonical Pages Footprint**：**275.35 MiB** (288,722,530 Bytes)
* **專案部署門禁門檻檢驗（[`pipeline/validate.py`](../pipeline/validate.py)）**：
  - **750 MiB Warning threshold**: 786,432,000 Bytes
    - `Distance to 750 MiB warning`: **474.65 MiB** (497,709,470 Bytes，預估僅佔預警線 **36.7%**)
  - **900 MiB Hard limit threshold**: 943,718,400 Bytes
    - `Distance to 900 MiB hard limit`: **624.65 MiB** (654,995,870 Bytes，預估僅佔硬上限 **30.6%**)
* **Model B 最終判定**：**PASS（最終通過）**。
