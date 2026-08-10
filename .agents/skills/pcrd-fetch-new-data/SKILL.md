---
name: pcrd-fetch-new-data
description: >-
  從台服 So-net CDN 與 wthee 鏡像站下載公主連結 Re:Dive 台版新角色資料，包含解密個人劇情對白 JSON、立繪、頭像美術素材及更新台版明文資料庫，最後輸出驗證報告。使用時機：新角色換裝上線、新主線章節、新活動劇情，需要抓取台版繁體中文原始資料時觸發。
---

# PCRD 台版資料抓取 Skill

## Overview

從台服 So-net CDN 與 wthee 鏡像站下載新角色或新劇情資料，自動解密繁中對白並整理成網頁可直接使用的格式。完成後輸出驗證報告，供使用者確認後再部署網頁。

**此 Skill 負責「抓資料 + 生成 AI 摘要」，不修改網頁前端代碼。** 確認資料無誤後，請使用 `pcrd-rebuild-metadata` Skill 重建索引，再使用 `pcrd-deploy-website` Skill 部署。

## Dependencies

無外部 Skill 依賴。僅需 Python 標準庫 + `UnityPy`（已在工具目錄中使用）。

## Quick Start

```
# 下載新角色資料（以角色名稱告知 AI，由 AI 解析 unit_id）
「幫我抓取阿斯特萊亞佩可的個人劇情和美術」

# 更新資料庫 + 指定 unit_id
「unit_id 138301 的資料需要更新」

# 主線新章節
「主線第三部第五章出了，更新劇情資料」

# 活動劇情
「幫我抓活動 event_id 10096 的劇情」

# 手動探測 CDN 有沒有新東西上架
「幫我探測 So-net CDN 有沒有新素材」
「掃一下 CDN 看有沒有新角色預上架」
```

## Utility Scripts

使用 `tools/pcrd_fetch.py` CLI 工具：

### `update-db` - 更新台版明文資料庫

```bash
python tools/pcrd_fetch.py update-db --output tools/db_update_report.json
```

從 wthee 下載最新 `redive_tw.db`，驗證資料表完整性後輸出報告。

### `fetch-stories` - 下載並解密角色個人劇情

```bash
python tools/pcrd_fetch.py fetch-stories --unit-id 138301 --output tools/story_fetch_report.json
```

自動從 So-net CDN manifest 查找對應 story_id（規則：unit_id x 10 + 1 ~ 4），下載 AssetBundle 並用 UnityPy 解密輸出繁中對白 JSON 到 `dashboard/story/`。

### `fetch-assets` - 下載立繪與頭像

```bash
python tools/pcrd_fetch.py fetch-assets --unit-id 138301 --output tools/asset_fetch_report.json
```

下載頭像（1星/3星）與立繪大圖，儲存至 `dashboard/icon/unit/` 與 `dashboard/card/full/`，同時登錄進 `dashboard/data/tracked_characters.json`。

### `report` - 產出人類可讀驗證報告

```bash
python tools/pcrd_fetch.py report --unit-id 138301 --output tools/fetch_report.md
```

整合 DB 查詢結果、對白句數、素材檔案存在狀況，輸出 Markdown 報告。

### `scan-cdn` - 手動探測 So-net CDN 是否有新內容預上架

```bash
# 自動推算候選 ID（從已知最大 unit_id 往後試探）
python tools/pcrd_fetch.py scan-cdn --output tools/scan_cdn_report.md

# 指定要探測的 ID（你有特定情報時）
python tools/pcrd_fetch.py scan-cdn --probe-ids 138401,138501 --output tools/scan_cdn_report.md
```

**完全不解密資料庫**，僅用 HTTP HEAD request 試探素材 URL 是否回應 200。
偵測到素材時自動下載到 `dashboard/versions/{日期}_{版本號}/`，並輸出偵測報告。

So-net 有時會在維護前數小時預先上傳素材（立繪、頭像），這個指令能第一時間發現。

## Workflow

### 完整抓取新劇情的標準流程（主線/活動）

1. **【前置審查：與更新紀錄 md 對齊】**：
   在執行任何同步指令前，**必須先讀取 `docs/pcrd_version_update_history.md`**：
   - 提取文檔中已記錄的實裝角色 `unit_id`、主線 `story_id` 以及活動 ID。
   - 將這些 ID 作為接下來執行指令的精確參數輸入。嚴禁盲猜或全量下載。
2. **更新資料庫與文本**：
   - 執行 `update-db` 更新台版資料庫，確認新話數已登載。
   - 執行 `sync-episode --story-id {story_id}`：自動下載解密對白 JSON，並下載該話所需之背景與劇照。
3. **同步與解碼語音封包 (AWB/ACB)**：
   - **下載語音封包**：確認下月或最新活動的語音封包 `.acb` 與 `.awb` 已被下載至 `downloaded_sounds/`。
     （主線語音檔名如 `v_t_vo_adv_{story_id_prefix}.acb/.awb`）
   - **局部轉碼**：執行轉檔工具，指定 `prefix` 參數進行局部語音解碼與轉檔，防止全量重建：
     ```bash
     python tools/convert_voices.py --prefix v_t_vo_adv_{story_id_prefix}
     ```
     這會自動將封包解開，並使用 ffmpeg 將轉檔出的 `.m4a` 檔案直接輸出至 `dashboard/sound/story_vo/`。
3. **完整性自檢**：
   - 讀取並檢查 `dashboard/data/story_thumbnails.json`。
   - 檢查本話對白中的語音 ID、劇照、背景檔案是否在 `dashboard/` 對應目錄中完整存在，確認無誤後再引導部署。
4. **AI 摘要生成**（此步驟由 AI 直接執行，不依賴外部 API）：
   - 詳見下方「AI 摘要生成流程」章節。

---

## AI 摘要生成流程（雲端大模型直接執行）

> 此步驟由 AI Agent 自身直接閱讀對白 JSON，不呼叫任何本地 Ollama、GLM 或 OpenCode API。AI 的語言理解能力就是「摘要引擎」本身。

### 何時觸發

- 新主線話數加入後（`dashboard/story/22XXXXX.json` 出現新檔案）
- 新活動劇情加入後（`dashboard/story/` 出現活動話數 JSON）

### Step 1：生成主線話數摘要（寫入 chapters.json）

**適用於**：主線話數，摘要字數上限約 50 字（一句話點出核心事件）。

1. 讀取 `dashboard/data/chapters.json`，找出 `summary` 欄位為空或明顯錯誤的話數。
2. 對每一話，讀取 `dashboard/story/{story_id}.json`，取前 150 句有效對白（過濾空行與純旁白）。
3. 以以下原則產出摘要（AI 自行完成，不需呼叫 API）：
   - 嚴格基於對白內容，不憑印象填充。
   - 不超過 50 字，不加贅詞（不要寫「本話講述了...」）。
   - 角色名嚴格使用台版官方翻譯（貪吃佩可、可可蘿、凱留、佑樹）。
4. 將生成的摘要字串寫入 `chapters.json` 對應 story 物件的 `"summary"` 欄位。
5. 若整章摘要也為空，同樣生成一段 100-200 字的整章摘要寫入章節物件的 `"summary"` 欄位。
6. 最終使用 Python 將更新後的 `chapters.json` 寫回磁碟：
   ```python
   import json
   with open("dashboard/data/chapters.json", "w", encoding="utf-8") as f:
       json.dump(chapters, f, ensure_ascii=False, indent=2)
   ```

### Step 2：生成活動摘要（寫入 event_summaries.json）

**適用於**：活動劇情，摘要字數 300-500 字（完整劇情大綱），大型前後篇活動可達 800-1500 字。

1. 讀取 `dashboard/data/event_summaries.json` 與 `dashboard/data/extra_events.json`，找出缺少摘要的活動（`story_group_id`）。
2. 從 DB 或 extra_events.json 取得該活動的所有 `story_id` 清單。
3. 對每個 `story_id`，讀取 `dashboard/story/{story_id}.json`，均勻抽取最多 150 句對白（每話最多 15 句，優先取前半段與結尾段）。
4. 以以下原則產出摘要（AI 自行完成，不需呼叫 API）：
   - 描述活動核心背景、主要登場角色、核心事件/危機、以及結局如何收場。
   - 嚴禁使用「起承轉合」、「第一部分」等學術分析語氣，使用自然故事敘述體。
   - 最後一個情節結束後直接停止，不加總結或短評。
5. 將生成的摘要字串寫入 `event_summaries.json`，key 為 `str(story_group_id)`：
   ```python
   import json
   summaries = json.load(open("dashboard/data/event_summaries.json", encoding="utf-8"))
   summaries[str(story_group_id)] = summary_text
   with open("dashboard/data/event_summaries.json", "w", encoding="utf-8") as f:
       json.dump(summaries, f, ensure_ascii=False, indent=4)
   ```
6. 大型前後篇活動（如 `5035`+`5036`）：合併兩篇的對白一起生成，並同時將同一份摘要寫入前篇與後篇兩個 key。

### 重要注意事項

- **角色名幻覺防範**：初音活動（`5001`）的妹妹名為「小栞」，不是「小凜」。生成後必須主動校驗。
- **斷點續傳**：已存在摘要的 `story_group_id` 一律跳過，不重新生成。
- **一次只處理新增話數**：不要嘗試重新生成已有摘要的舊話數，節省 token。

---

## Rate Limiting

- **So-net CDN**：無官方文件，預設每次請求間隔 0.5 秒，timeout 15 秒，最多重試 3 次（指數退避）
- **wthee 鏡像站**：單一大檔下載，timeout 60 秒，無需限速

## Data Integrity & Auto-Verification (防錯與自檢機制)

為了防止線上網頁出現灰色預設背景或破圖，抓取完劇情資料後，AI 必須強制執行以下自我驗證流程：

1. **查閱關聯圖片配置**：
   - 讀取並檢查 `dashboard/data/story_thumbnails.json`。
   - 對於新下載的每一話 `story_id`，提取其 `still_id`（劇照 CG）與 `bg_id`（背景圖）。
2. **自動確認實體圖檔存在性**：
   - 劇照路徑：`dashboard/still/scenario/story_still_{still_id}.webp` (或 CG ID 格式)
   - 背景路徑：`dashboard/still/bg/bg_{bg_id}.webp`
   - 若上述檔案於本地不存在，必須立刻呼叫 `python tools/pcrd_fetch.py fetch-story-images --story-id {story_id}` 自動抓取對應素材。
3. **語音音檔完整性確認**：
   - 檢查 `dashboard/sound/story_vo/` 下是否有該話對白 JSON 中列出的所有 `voice` 檔案。
4. **資料庫結構健康檢查**：
   - 執行完資料庫更新後，必須查詢 `story_detail` 與 `event_story_data` 確定該章節/活動的資料列數大於 0。

## Common Mistakes

1. **story_id 推算錯誤**：part_id 有些角色不是從 1 開始，建議先查 DB 的 `chara_story_status` 資料表確認實際話數。
2. **UnityPy 版本衝突**：解密時需設定 `FALLBACK_UNITY_VERSION = '2021.3.20f1'`，否則部分 Bundle 解析失敗。
3. **wthee 更新延遲**：wthee 鏡像有時落後台服 CDN 數小時，若 DB 中尚無新角色，請等待後再試。
4. **漏抓背景圖導致破圖**：只抓取劇情對白卻沒有連帶下載背景圖，會導致前端無法回退顯示背景而顯示灰色塊。必須在報告前進行 Data Integrity 自檢。
5. **全量重新轉換音訊**：執行 `convert_voices.py` 時若未加上 `--prefix` 參數，會預設重新解碼轉檔 `downloaded_sounds/` 下一萬多個歷史封包，極度消耗資源且耗時。必須指定 --prefix。
6. **摘要生成後忘記寫回 JSON**：AI 自身產出的摘要文字必須透過 Python 腳本寫回磁碟，否則只停留在 AI 的上下文中，重啟後即遺失。
