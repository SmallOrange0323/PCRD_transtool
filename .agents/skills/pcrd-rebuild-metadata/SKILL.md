---
name: pcrd-rebuild-metadata
description: >-
  在新主線話數或活動話數加入後，重建前端所需的靜態索引檔，包含章節目錄（chapters.json）與角色登場統計（speaker_appearance.json），確保前端左側章節目錄和角色篩選功能正確反映最新資料。使用時機：pcrd-fetch-new-data 完成且資料已確認無誤後、在執行 pcrd-deploy-website 之前觸發。
---

# PCRD 靜態索引重建 Skill

## Overview

每次新增主線話數或活動話數後，前端所依賴的兩個靜態索引 JSON 必須同步更新，否則網頁的章節目錄不會顯示新章節、角色篩選功能也無法識別新話數中的登場角色。

此 Skill 是 `pcrd-fetch-new-data` 與 `pcrd-deploy-website` 之間的**必要中間步驟**，遺漏此步驟不會直接報錯，但會造成前端靜默資料過舊的問題。

**執行順序**：`pcrd-fetch-new-data` → **`pcrd-rebuild-metadata`（本 Skill）** → `pcrd-deploy-website`

## Dependencies

- `dashboard/redive_tw.db`：台版明文資料庫（由 `update-db` 更新）
- `dashboard/story/`：對白 JSON 目錄（由 `sync-episode` 下載後填入）
- `dashboard/data/chapters.json`：現有章節索引（重建時會被覆寫）

## Quick Start

```
# 新主線章節加入後
「幫我重建章節索引」
「更新 speaker_appearance」
「新劇情的章節資料要更新」

# 確認執行順序
「pcrd-fetch-new-data 完成了，接下來要做什麼？」
```

---

## Utility Scripts

### Script 1：rebuild_chapters.py - 重建章節目錄索引

```bash
python dashboard/scripts/rebuild_chapters.py
```

**輸入**：`dashboard/redive_tw.db`
**輸出**：`dashboard/data/chapters.json`

從資料庫的 `story_detail` 資料表讀取所有主線 `story_group_id`，重建完整的三部章節 JSON 索引。

> **重要**：此腳本內含第一部（2000-2015）、第二部（2101-2116）、第三部（2201-2215）與幕間（3001-4013）的固定標題與摘要字典。**若有新章節上線（第三部新增超過 2215 的 group_id），必須先手動更新腳本中的 `part3_titles` 與 `part3_summaries` 字典，再執行。**

新章節更新流程：
1. 開啟 `dashboard/scripts/rebuild_chapters.py`
2. 在 `part3_titles` 字典中加入新 `story_group_id: "章名"` 映射
3. 在 `part3_summaries` 字典中加入新 `story_group_id: "AI 產出的章節摘要"` 映射
4. 更新腳本頂部的 `p3_gw_gids` 範圍（如 `range(2201, 2217)` 以涵蓋新的 2216 章）
5. 執行腳本

### Script 2：generate_speaker_appearance.py - 重建角色登場統計

```bash
python dashboard/scripts/generate_speaker_appearance.py
```

**輸入**：`dashboard/story/*.json`（所有已下載的對白 JSON）
**輸出**：`dashboard/story/speaker_appearance.json`

掃描所有對白 JSON，統計每個說話者出現過的 `story_id` 清單，供前端的角色篩選功能使用。此腳本完全自動，無需任何參數，每次均全量重建（速度很快，約 5-10 秒）。

### Script 3：export_chapter_template.py - 匯出新章節填寫模板（可選）

```bash
python dashboard/scripts/export_chapter_template.py
```

**輸入**：`dashboard/redive_tw.db` + `dashboard/data/chapters.json`
**輸出**：`dashboard/data/chapters_template.json`

當資料庫中出現了 `chapters.json` 尚未收錄的新 `story_group_id` 時，此腳本會輸出一個帶有 `_note` 欄位的待填模板，方便人工確認並填寫標題與摘要。**建議在 rebuild_chapters.py 之前先執行此腳本，用來確認是否有新章節 ID 需要處理。**

---

## Standard Workflow

### 主線新章節上線後的標準執行流程

1. **確認新 story_group_id**：
   ```bash
   python dashboard/scripts/export_chapter_template.py
   ```
   查看輸出的 `chapters_template.json` 中是否有帶 `_note` 的空白新章節。

2. **更新 rebuild_chapters.py 內的字典**（若有新章節）：
   - AI 閱讀新話數的對白 JSON（例如 `dashboard/story/2216001.json`），產出章節標題與摘要。
   - 將 `part3_titles[{new_gid}]` 與 `part3_summaries[{new_gid}]` 加入腳本。
   - 同步擴充 `p3_gw_gids` 的 range 上界。

3. **執行章節重建**：
   ```bash
   python dashboard/scripts/rebuild_chapters.py
   ```
   確認輸出訊息中「Part 3 game_world」的章數已正確增加。

4. **執行角色登場統計**：
   ```bash
   python dashboard/scripts/generate_speaker_appearance.py
   ```
   確認輸出訊息中已處理的 story JSON 數量包含新話數。

5. **驗收確認**：
   - `dashboard/data/chapters.json` 中新章節的標題、摘要、key、order 均正確。
   - `dashboard/story/speaker_appearance.json` 的最後修改時間已更新。

6. **進入下一階段**：執行 `pcrd-deploy-website` Skill 部署。

---

## Data Structure Reference

### chapters.json 結構

```json
{
  "3": {
    "game_world": {
      "2216": {
        "title": "章節名稱（官方中文）",
        "summary": "100-200 字的章節概述",
        "key": "第16章",
        "order": 16
      }
    },
    "interlude": { ... }
  }
}
```

- `key`：前端顯示用的簡短標籤，格式為「第N章」或「序章」
- `order`：排序用數字，與章節號一致
- `summary`：由 AI 閱讀該章對白後產出的章節概述

### speaker_appearance.json 結構

```json
{
  "貪吃佩可": [2201001, 2201002, 2201003, ...],
  "可可蘿": [2201001, 2201002, ...],
  "旁白": [2201001, ...]
}
```

key 為說話者名稱，value 為該角色出現過的 story_id 陣列。前端用此資料驅動角色篩選功能。

---

## Common Mistakes

1. **忘記更新 rebuild_chapters.py 內的字典就直接執行**：腳本的章節標題與摘要是硬編碼在腳本內的字典中，若新章節的 group_id 不在字典中，雖然章節 JSON 結構仍會生成，但標題會顯示預設值（如「第16章」）而非官方章名，摘要也會是空字串。
2. **只執行 rebuild_chapters.py 忘記執行 generate_speaker_appearance.py**：兩個腳本都需要執行才算完整重建。
3. **chapters.json 被重建後覆蓋了手動填寫的摘要**：`rebuild_chapters.py` 的章節摘要完全來自腳本內的 `part3_summaries` 字典，直接修改 `chapters.json` 的摘要在下次重建時會被覆寫。正確做法是修改腳本中的字典。
4. **新章節的 range 沒有更新**：例如原本 `range(2201, 2216)` 只到 2215，新增第 16 章（2216）時若未改成 `range(2201, 2217)`，新章節不會出現在輸出中。
