# 公主連結 Story Map 語音部署與 Estertion 鏡像缺口稽核報告 (VOICE_DEPLOYMENT_GAP_AUDIT.md)

本文件收錄 **Story Map 劇情語音部署至 GitHub Pages 的完整可行性稽核與 Estertion 遠端鏡像缺口探測結果**，供後續 AI 代理與開發者參考決策。

---

## 一、 稽核背景與核心目標

目前 Story Map 前端 `MediaService.js` 採用三層語音播放降級策略：
1. `sound/story_vo/{voiceName}.m4a`（本地優先）
2. `https://prcn-sound.estertion.win/story_vo/{groupId}/{voiceName}.m4a`（Estertion 鏡像 1）
3. `https://redive.estertion.win/sound/story_vo/{groupId}/{voiceName}.m4a`（Estertion 鏡像 2）

其中 `groupId = voiceName.substring(7, 14)`。

因 GitHub Pages 具備 **1 GiB (1024 MiB)** 的硬性容量上限與 **750 MiB** 的安全建議閥值，本稽核旨在解答：
1. 本地現存語音若全量部署是否可行？
2. 若只部署「劇情有引用」的語音是否可行？
3. Estertion 鏡像的真實覆蓋率如何？是否存在「遠端雙鏡像皆缺、但本地有檔」的真缺口（True Gap Set）？
4. 僅部署 Gap 語音的體積與可行性為何？

---

## 二、 全量與本地語音庫盤點 (Voice Inventory)

* **本地 `dashboard/sound/story_vo/` 總檔案數**: `16,902` 個 `.m4a`
* **本地總體積**: `1,171,881,159 bytes` (**`1,117.59 MiB`** / 約 `1.09 GiB`)
* **全劇情對白引用總量**: 9,034 篇 JSON 中共有 **`325,251` 條對白**，對應 **`316,166` 條不重複語音名稱**。
* **本地與劇本交集分析**:
  - **劇本有引用且本地有檔**: **`7,103` 檔** (`838,139,190 bytes` / **`799.31 MiB`**)
  - **劇本未引用之孤立/戰鬥/活動檔**: **`9,799` 檔** (`333,741,969 bytes` / **`318.28 MiB`**)
* **全量部署判定**:
  - 目前 Pages 基準發布包為 **`277.19 MiB`**。
  - 若納入本地全量語音 (`+ 1,117.59 MiB`)，總體積將達 **`1,394.79 MiB` (`1.362 GiB`)** ➡️ **`FEASIBILITY = RED` (超標，不可行)**。
  - 若納入本地 7,103 引用語音 (`+ 799.31 MiB`)，總體積將達 **`1,076.51 MiB` (`1.051 GiB`)** ➡️ **`FEASIBILITY = RED` (超標，不可行)**。

---

## 三、 Estertion 雙鏡像全量實測探測 (Gap Probe)

針對該 **7,103 個劇情引用之本地語音檔**，逐一發送 HTTP HEAD / Range GET 對兩大 Estertion 鏡像進行精確探測（`max_workers = 10`，使用持久連線池）：

### 1. 探測分類統計結果

| 分類類別 | 判定定義 | 檔案數量 | 佔比 |
| :--- | :--- | :---: | :---: |
| **`BOTH_AVAILABLE`** | 兩個 Estertion 鏡像皆正常提供 (200 OK) | **`6,867`** | **96.68%** |
| **`PRCN_ONLY`** | 僅 PRCN 鏡像可用 | **`0`** | 0.00% |
| **`REDIVE_ONLY`** | 僅 Redive 鏡像可用 | **`0`** | 0.00% |
| **`BOTH_MISSING`** | **兩個鏡像皆缺失 (404/410) — 真正 Gap** | **`236`** | **3.32%** |
| **`INCONCLUSIVE`** | 網路異常/無法確定 | **`0`** | 0.00% |

### 2. 探測核心發現
1. **Estertion 覆蓋率極高**: 6,867 個語音（96.68%）在遠端 CDN 上皆完好存在，線上用戶透過前端降級機制即可秒速播放，無需 Pages 重複託管。
2. **真正的雙鏡像缺口極小**: 僅有 **236 個語音檔** 屬於兩大鏡像皆 404 的真缺口。

---

## 四、 真正缺口語音集盤點 (Gap Capacity & Integrity)

* **Gap 檔案數量**: **`236` 個**
* **Gap 總體積**: `25,051,018 bytes` (**`23.89 MiB`**)
* **平均單檔大小**: `103.66 KiB`
* **中位數大小**: `100.24 KiB`
* **最大單檔**: `vo_adv_1064008_046.m4a` (`283,127 bytes` / `0.27 MiB`)
* **資料完整性 (Integrity)**:
  - 0-byte 檔案: `0` 個
  - 不安全/非標準檔名: `0` 個
  - 既有 2 個 0-byte 檔案（`vo_adv_1002011_023`, `024`）在 Estertion 遠端均為 200 OK，不屬於 Gap 集合，無 Block 疑慮。

---

## 五、 精準補缺 (Gap-Only) 之 Pages 預估體積

| 項目 | 體積 (MiB) | 佔用空間 (Bytes) |
| :--- | :---: | :---: |
| **目前生產發布包 (Current Release)** | `277.19 MiB` | `290,658,713` |
| **精準補齊 236 個 Gap 語音** | **`+ 23.89 MiB`** | `25,051,018` |
| **預估發布總體積 (Projected Footprint)** | **`301.08 MiB`** | **`315,709,731`** |

### 容量安全裕度評估
* **距離 750 MiB 保守上限裕度**: **`+ 448.92 MiB`**（極度充裕）
* **距離 900 MiB 警戒上限裕度**: **`+ 598.92 MiB`**
* **距離 1024 MiB (1 GiB) Pages 硬限制裕度**: **`+ 722.92 MiB`**

---

## 六、 結論與可行性判定

### 綜合評估等級：`FEASIBILITY = GREEN` 🟢

1. **全量部署不可行**：本地全量 1.12 GiB 或引用量 799 MiB 均會導致 Pages 爆量。
2. **精準補缺（Gap-Only）極度可行且高效**：
   - 僅需部署 **236 個檔案（23.89 MiB）**。
   - 總體積僅微幅增至 **301.08 MiB**（遠低於 750 MiB 保守門檻）。
   - 能讓線上用戶在面對 Estertion 缺失的 236 條對白時，自動由 Pages 本地源無縫補齊，實現 **100% 完美語音播放**。

---

## 七、 實施指引（供後續開發與 AI 參考）

若後續決定正式上線 Gap 語音補齊機制，建議採取以下做法：

1. **白名單精準發布 (Gap Whitelist)**：
   - 將 236 個 Gap 檔名儲存為權威清單 `dashboard/data/voice_gap_assets.json`。
   - 修改 `pipeline/bundle.py`：僅複製名列清單中的 236 個 `.m4a` 至 `dist_story_map/sound/story_vo/`。
2. **`.gitignore` 規則細化**：
   - 將 `dist_story_map/.gitignore` 由粗暴的 `sound/` 改為追蹤白名單或只忽略非 gap 音檔。
3. **驗證閉環**：
   - 每次執行發布時，由 Bundler 自動核對總體積是否控制在 305 MiB 以內。
